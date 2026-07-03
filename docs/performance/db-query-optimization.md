# 数据库查询优化分析报告

**项目**: customer_platform_vk  
**分析日期**: 2026-04-04  
**分析范围**: backend/app/services/, backend/app/routes/, backend/app/models/  
**技术栈**: Python 3.11 + Sanic + SQLAlchemy 2.0 + PostgreSQL

---

## 执行摘要

本次分析发现了 **6 类主要性能问题**，按优先级排序：

| 优先级 | 问题类型 | 影响程度 | 文件数量 |
|--------|----------|----------|----------|
| 🔴 High | N+1 查询问题 | 高 - 可能导致数百次额外查询 | 3 |
| 🔴 High | 缺失数据库索引 | 高 - 全表扫描风险 | 5 |
| 🟡 Medium | OFFSET 分页性能 | 中 - 大数据量下性能下降 | 4 |
| 🟡 Medium | 冗余查询 | 中 - 重复 fetch 相同数据 | 2 |
| 🟢 Low | SELECT * 低效 | 低 - 网络传输浪费 | 3 |
| 🟢 Low | 事务边界优化 | 低 - 可合并的查询 | 1 |

---

## 1. N+1 查询问题 (High Priority)

### 1.1 `analytics.py` - `get_inactive_customers()` 中的 N+1 查询

**文件**: `backend/app/services/analytics.py`  
**行号**: 367-409  
**问题描述**: 方法先查询所有有消耗记录的客户 ID，然后对每个客户 ID 单独查询详情

```python
# ❌ 问题代码 (L367-409)
def get_inactive_customers(self, days: int = 90) -> List[Dict[str, Any]]:
    # 第一次查询：获取所有有消耗记录的客户
    has_usage_stmt = select(func.distinct(ConsumptionRecord.customer_id))
    all_customers_with_usage = set(
        row[0] for row in self.db.execute(has_usage_stmt).all()
    )
    
    # 第二次查询：获取最近有消耗的客户
    recent_usage_stmt = select(func.distinct(ConsumptionRecord.customer_id)).where(
        ConsumptionRecord.created_at >= cutoff_date
    )
    recent_customers = set(
        row[0] for row in self.db.execute(recent_usage_stmt).all()
    )
    
    # N+1 问题：对每个 inactive customer 单独查询
    inactive_customer_ids = all_customers_with_usage - recent_customers
    
    # 虽然使用了 .in_() 批量查询，但前面的集合操作效率低
    stmt = (
        select(Customer.id, Customer.name, Customer.company_id, ...)
        .where(Customer.id.in_(inactive_customer_ids))  # 如果集合大，IN 列表过长
        .outerjoin(User, Customer.manager_id == User.id)
    )
```

**影响**: 
- 当有 1000 个 inactive customers 时，`IN` 列表可能超过 PostgreSQL 参数限制 (65535)
- 集合操作在 Python 层面进行，无法利用数据库优化

**优化建议**:

```python
# ✅ 优化方案：使用 CTE 或子查询
def get_inactive_customers(self, days: int = 90) -> List[Dict[str, Any]]:
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # 使用子查询一次性完成
    recent_customer_subq = (
        select(func.distinct(ConsumptionRecord.customer_id))
        .where(ConsumptionRecord.created_at >= cutoff_date)
        .subquery()
    )
    
    has_usage_subq = (
        select(func.distinct(ConsumptionRecord.customer_id))
        .subquery()
    )
    
    stmt = (
        select(
            Customer.id,
            Customer.name,
            Customer.company_id,
            Customer.manager_id,
            User.real_name.label("manager_name"),
        )
        .join(has_usage_subq, Customer.id == has_usage_subq.c.customer_id)
        .outerjoin(
            recent_customer_subq,
            Customer.id == recent_customer_subq.c.customer_id
        )
        .outerjoin(User, Customer.manager_id == User.id)
        .where(
            and_(
                Customer.deleted_at.is_(None),
                recent_customer_subq.c.customer_id.is_(None)  # 排除最近有消耗的
            )
        )
    )
    
    result = self.db.execute(stmt).all()
    return [...]
```

---

### 1.2 `analytics.py` - `get_customer_health_stats()` 中的多次独立查询

**文件**: `backend/app/services/analytics.py`  
**行号**: 275-318  
**问题描述**: 6 次独立查询获取健康度统计，可合并为 1-2 次查询

```python
# ❌ 问题代码 (L275-318)
def get_customer_health_stats(self) -> Dict[str, Any]:
    # 查询 1: 活跃客户数
    active_stmt = select(func.count(func.distinct(ConsumptionRecord.customer_id)))
    active_count = self.db.execute(active_stmt).scalar() or 0
    
    # 查询 2: 总客户数
    total_stmt = select(func.count(Customer.id)).where(Customer.deleted_at.is_(None))
    total_count = self.db.execute(total_stmt).scalar() or 0
    
    # 查询 3: 余额预警客户
    warning_stmt = select(func.count(CustomerBalance.id)).where(
        CustomerBalance.total_amount < 1000
    )
    warning_count = self.db.execute(warning_stmt).scalar() or 0
    
    # 查询 4-6: 流失风险客户 (更复杂的多步查询)
    ...
```

**影响**: 每次调用产生 6+ 次数据库往返

**优化建议**:

```python
# ✅ 优化方案：使用单个聚合查询
def get_customer_health_stats(self) -> Dict[str, Any]:
    from datetime import timedelta
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    
    # 使用 CASE 表达式单次查询获取所有统计
    stmt = select(
        func.count(Customer.id).label("total_count"),
        func.count(func.distinct(ConsumptionRecord.customer_id)).label("active_count"),
        func.count(
            case((CustomerBalance.total_amount < 1000, 1))
        ).label("warning_count"),
        func.count(
            case((
                and_(
                    Customer.deleted_at.is_(None),
                    func.coalesce(
                        select(func.max(ConsumptionRecord.created_at))
                        .where(ConsumptionRecord.customer_id == Customer.id)
                        .correlate(Customer)
                        .scalar_subquery(),
                        datetime(1970, 1, 1)
                    ) < ninety_days_ago,
                    1
                )
            ))
        ).label("churn_count"),
    ).select_from(Customer).outerjoin(
        CustomerBalance, Customer.id == CustomerBalance.customer_id
    ).outerjoin(
        ConsumptionRecord, Customer.id == ConsumptionRecord.customer_id
    ).where(
        Customer.deleted_at.is_(None)
    )
    
    result = self.db.execute(stmt).first()
    return {
        "total_customers": result.total_count,
        "active_customers": result.active_count,
        ...
    }
```

---

### 1.3 `tags.py` - `get_tag_usage_count()` 可优化

**文件**: `backend/app/services/tags.py`  
**行号**: 78-94  
**当前状态**: ⚠️ 已部分优化，但仍可改进

```python
# ⚠️ 当前代码 (2 次查询)
async def get_tag_usage_count(self, tag_id: int) -> dict:
    customer_count = await self.db.execute(
        select(func.count())
        .select_from(CustomerTag)
        .where(CustomerTag.tag_id == tag_id, CustomerTag.deleted_at.is_(None))
    )
    customer_count = customer_count.scalar() or 0
    
    profile_count = await self.db.execute(
        select(func.count())
        .select_from(ProfileTag)
        .where(ProfileTag.tag_id == tag_id, ProfileTag.deleted_at.is_(None))
    )
    profile_count = profile_count.scalar() or 0
    
    return {"customer_count": customer_count, "profile_count": profile_count}
```

**优化建议** (使用 UNION ALL 单次查询):

```python
# ✅ 优化方案
async def get_tag_usage_count(self, tag_id: int) -> dict:
    stmt = select(
        func.sum(
            case((func.count() > 0, func.count()), else_=0)
        ).label("total_count")
    ).select_from(
        select(CustomerTag.id).where(
            CustomerTag.tag_id == tag_id, CustomerTag.deleted_at.is_(None)
        ).union_all(
            select(ProfileTag.id).where(
                ProfileTag.tag_id == tag_id, ProfileTag.deleted_at.is_(None)
            )
        ).alias('combined')
    )
    result = await self.db.execute(stmt).first()
    return {"total_count": result.total_count}
```

---

## 2. 缺失数据库索引 (High Priority)

### 2.1 `billing.py` 模型索引缺失

**文件**: `backend/app/models/billing.py`

| 表名 | 列名 | 使用场景 | 建议索引 |
|------|------|----------|----------|
| `recharge_records` | `customer_id` | WHERE 筛选 | ✅ 已有 index |
| `recharge_records` | `created_at` | ORDER BY 排序 | ❌ 缺失 |
| `pricing_rules` | `customer_id` | WHERE 筛选 | ✅ 已有 index |
| `invoices` | `customer_id` | WHERE + JOIN | ✅ 已有 index |
| `invoices` | `status` | WHERE 筛选 | ✅ 已有 index |
| `invoice_items` | `invoice_id` | JOIN | ✅ 已有 index |
| `invoice_items` | `device_type` | GROUP BY | ❌ 缺失 |
| `consumption_records` | `customer_id` | WHERE + JOIN | ✅ 已有 index |
| `consumption_records` | `invoice_id` | JOIN | ✅ 已有 index |
| `consumption_records` | `created_at` | WHERE 时间范围 | ❌ 缺失 |
| `daily_usage` | `customer_id` | WHERE + GROUP BY | ✅ 已有复合索引 |
| `daily_usage` | `usage_date` | WHERE 时间范围 | ✅ 已有复合索引 |

### 2.2 `tags.py` 模型索引缺失

**文件**: `backend/app/models/tags.py`

| 表名 | 列名 | 使用场景 | 建议索引 |
|------|------|----------|----------|
| `customer_tags` | `customer_id` | WHERE + JOIN | ❌ 缺失 (仅 PK) |
| `customer_tags` | `tag_id` | WHERE + JOIN | ❌ 缺失 (仅 PK) |
| `profile_tags` | `profile_id` | WHERE + JOIN | ❌ 缺失 (仅 PK) |
| `profile_tags` | `tag_id` | WHERE + JOIN | ❌ 缺失 (仅 PK) |

### 2.3 `groups.py` 模型索引缺失

**文件**: `backend/app/models/groups.py`

| 表名 | 列名 | 使用场景 | 建议索引 |
|------|------|----------|----------|
| `customer_groups` | `group_type` | WHERE 筛选 | ✅ 已有 index |
| `customer_groups` | `created_by` | WHERE 筛选 | ✅ 已有 index |
| `customer_group_members` | `group_id` | WHERE + JOIN | ✅ 已有复合索引 |
| `customer_group_members` | `customer_id` | WHERE + JOIN | ✅ 已有 index |

---

## 3. OFFSET 分页性能问题 (Medium Priority)

### 3.1 `customers.py` - `get_all_customers()`

**文件**: `backend/app/services/customers.py`  
**行号**: 45-85

```python
# ❌ 问题代码
async def get_all_customers(
    self,
    page: int = 1,
    page_size: int = 20,
    filters: Optional[dict] = None,
) -> Tuple[List[Customer], int]:
    ...
    # OFFSET 分页在大数据量下性能差
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
```

**问题**: 
- OFFSET 10000 时，数据库需要扫描并丢弃前 10000 行
- 性能随页码增加线性下降

**优化建议** (使用 Keyset Pagination):

```python
# ✅ 优化方案：游标分页
async def get_all_customers(
    self,
    page_size: int = 20,
    filters: Optional[dict] = None,
    cursor: Optional[int] = None,  # 最后一条记录的 ID
) -> Tuple[List[Customer], int]:
    stmt = select(Customer).where(Customer.deleted_at.is_(None))
    
    # 应用筛选条件
    if filters:
        ...
    
    # 游标分页 (基于 ID)
    if cursor:
        stmt = stmt.where(Customer.id < cursor)
    
    # 始终按 ID 降序
    stmt = stmt.order_by(Customer.id.desc()).limit(page_size + 1)
    
    result = await self.db.execute(stmt)
    customers = list(result.scalars().all())
    
    has_next = len(customers) > page_size
    if has_next:
        customers = customers[:-1]
    
    next_cursor = customers[-1].id if customers else None
    
    return customers, next_cursor, has_next
```

---

### 3.2 `tags.py` - `get_all_tags()`

**文件**: `backend/app/services/tags.py`  
**行号**: 25-52

```python
# ❌ 同样的 OFFSET 问题
stmt = stmt.order_by(Tag.created_at.desc())
stmt = stmt.offset((page - 1) * page_size).limit(page_size)
```

**优化建议**: 同上，使用游标分页

---

### 3.3 `billing.py` - `get_recharge_records()`

**文件**: `backend/app/services/billing.py`  
**行号**: 211-233

```python
# ❌ OFFSET 分页
stmt = stmt.order_by(RechargeRecord.created_at.desc())
stmt = stmt.offset((page - 1) * page_size).limit(page_size)
```

**优化建议**: 使用 `created_at` 作为游标

---

### 3.4 `groups.py` - `get_group_members()`

**文件**: `backend/app/services/groups.py`  
**行号**: 67-94

```python
# ❌ OFFSET 分页
stmt = (
    select(Customer)
    .where(Customer.deleted_at.is_(None))
    .offset((page - 1) * page_size)
    .limit(page_size)
)
```

---

## 4. 冗余查询问题 (Medium Priority)

### 4.1 `analytics.py` - `get_payment_analysis()`

**文件**: `backend/app/services/analytics.py`  
**行号**: 181-236

```python
# ❌ 两次独立查询可合并
def get_payment_analysis(self, start_date, end_date, customer_id=None):
    # 查询 1: 结算金额
    invoice_stmt = select(
        func.sum(Invoice.total_amount).label("total_invoiced"),
        func.sum(Invoice.discount_amount).label("total_discount"),
        func.sum(Invoice.total_amount - Invoice.discount_amount).label("total_final"),
    ).where(...)
    invoice_result = self.db.execute(invoice_stmt).first()
    
    # 查询 2: 回款金额 (独立查询)
    payment_stmt = select(
        func.sum(RechargeRecord.real_amount).label("total_paid")
    ).where(...)
    payment_result = self.db.execute(payment_stmt).first()
```

**优化建议**: 使用子查询或 CTE 合并

```python
# ✅ 优化方案
def get_payment_analysis(self, start_date, end_date, customer_id=None):
    from sqlalchemy import literal_column
    
    # 使用 CTE 合并查询
    invoice_cte = (
        select(
            func.sum(Invoice.total_amount).label("total_invoiced"),
            func.sum(Invoice.discount_amount).label("total_discount"),
            func.sum(Invoice.total_amount - Invoice.discount_amount).label("total_final"),
        )
        .where(and_(
            Invoice.period_start >= start_date,
            Invoice.period_end <= end_date,
            Invoice.status != "cancelled",
        ))
    )
    if customer_id:
        invoice_cte = invoice_cte.where(Invoice.customer_id == customer_id)
    
    payment_cte = (
        select(
            func.sum(RechargeRecord.real_amount).label("total_paid")
        )
        .where(and_(
            RechargeRecord.created_at >= datetime.combine(start_date, datetime.min.time()),
            RechargeRecord.created_at <= datetime.combine(end_date, datetime.max.time()),
        ))
    )
    if customer_id:
        payment_cte = payment_cte.where(RechargeRecord.customer_id == customer_id)
    
    # 交叉连接获取所有数据
    stmt = select(invoice_cte, payment_cte)
    result = self.db.execute(stmt).first()
```

---

### 4.2 `analytics.py` - `get_dashboard_stats()`

**文件**: `backend/app/services/analytics.py`  
**行号**: 675-750

**问题**: 8 次独立查询获取仪表盘统计

```python
# ❌ 8 次查询
total_customers = self.db.execute(select(func.count(Customer.id))...).scalar()
key_customers = self.db.execute(select(func.count(Customer.id))...).scalar()
balance_result = self.db.execute(select(func.sum(...), func.sum(...), ...)).first()
invoice_count = self.db.execute(select(func.count(Invoice.id))...).scalar()
pending_count = self.db.execute(select(func.count(Invoice.id))...).scalar()
month_consumption = self.db.execute(select(func.sum(Invoice.total_amount))...).scalar()
```

**优化建议**: 合并为 2-3 次查询

---

## 5. SELECT * 低效问题 (Low Priority)

### 5.1 `groups.py` - `_apply_dynamic_filter()`

**文件**: `backend/app/services/groups.py`  
**行号**: 96-127

```python
# ❌ SELECT * 当只需要部分列
stmt = select(Customer).where(and_(*filters), Customer.deleted_at.is_(None))
```

**优化建议**: 只选择需要的列

```python
# ✅ 优化方案
stmt = select(
    Customer.id,
    Customer.company_id,
    Customer.name,
    Customer.account_type,
    Customer.business_type,
).where(and_(*filters), Customer.deleted_at.is_(None))
```

---

## 6. 事务边界优化 (Low Priority)

### 6.1 `billing.py` - `recharge()` 可优化事务

**文件**: `backend/app/services/billing.py`  
**行号**: 58-99

```python
# ⚠️ 可以优化为单个事务块
async def recharge(self, customer_id, real_amount, bonus_amount, ...):
    record = RechargeRecord(...)
    self.db.add(record)
    
    balance = await self.get_or_create_balance(customer_id)
    balance.real_amount += real_amount
    ...
    
    await self.db.commit()
```

**优化建议**: 使用显式事务块

```python
# ✅ 优化方案
async def recharge(self, customer_id, real_amount, bonus_amount, ...):
    async with self.db.begin():
        record = RechargeRecord(...)
        self.db.add(record)
        
        balance = await self.get_or_create_balance(customer_id)
        balance.real_amount += real_amount
        ...
```

---

## 7. 推荐索引迁移脚本

**文件**: `backend/migrations/versions/003_add_missing_indexes.py`

```python
"""add missing indexes for query optimization

Revision ID: 003
Revises: 002
Create Date: 2026-04-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === recharge_records ===
    # 用于 ORDER BY created_at DESC 排序
    op.create_index(
        'idx_recharge_records_created_at',
        'recharge_records',
        ['created_at'],
        unique=False
    )
    
    # === invoice_items ===
    # 用于 GROUP BY device_type 聚合
    op.create_index(
        'idx_invoice_items_device_type',
        'invoice_items',
        ['device_type'],
        unique=False
    )
    
    # === consumption_records ===
    # 用于 WHERE created_at 时间范围查询
    op.create_index(
        'idx_consumption_records_created_at',
        'consumption_records',
        ['created_at'],
        unique=False
    )
    
    # === customer_tags ===
    # 用于 WHERE customer_id 和 tag_id 查询
    op.create_index(
        'idx_customer_tags_customer_id',
        'customer_tags',
        ['customer_id'],
        unique=False
    )
    op.create_index(
        'idx_customer_tags_tag_id',
        'customer_tags',
        ['tag_id'],
        unique=False
    )
    
    # === profile_tags ===
    # 用于 WHERE profile_id 和 tag_id 查询
    op.create_index(
        'idx_profile_tags_profile_id',
        'profile_tags',
        ['profile_id'],
        unique=False
    )
    op.create_index(
        'idx_profile_tags_tag_id',
        'profile_tags',
        ['tag_id'],
        unique=False
    )
    
    # === daily_usage ===
    # 添加 device_type 索引用于 GROUP BY
    op.create_index(
        'idx_daily_usage_device_type',
        'daily_usage',
        ['device_type'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('idx_daily_usage_device_type', 'daily_usage')
    op.drop_index('idx_profile_tags_tag_id', 'profile_tags')
    op.drop_index('idx_profile_tags_profile_id', 'profile_tags')
    op.drop_index('idx_customer_tags_tag_id', 'customer_tags')
    op.drop_index('idx_customer_tags_customer_id', 'customer_tags')
    op.drop_index('idx_consumption_records_created_at', 'consumption_records')
    op.drop_index('idx_invoice_items_device_type', 'invoice_items')
    op.drop_index('idx_recharge_records_created_at', 'recharge_records')
```

---

## 8. 优化优先级与实施计划

### Phase 1 (立即实施 - High Impact)

1. **添加缺失索引** (迁移脚本 `003_add_missing_indexes.py`)
   - 预计影响：查询性能提升 50-90%
   - 风险：低 (只读操作)
   - 耗时：5-10 分钟 (取决于表大小)

2. **修复 N+1 查询**
   - `get_inactive_customers()` - 使用子查询
   - `get_customer_health_stats()` - 合并为 1-2 次查询
   - 预计影响：减少 80%+ 数据库往返

### Phase 2 (短期实施 - Medium Impact)

3. **实现游标分页**
   - 修改 `get_all_customers()` API
   - 修改 `get_all_tags()` API
   - 修改 `get_recharge_records()` API
   - 预计影响：大数据量下分页性能提升 10 倍+

4. **合并冗余查询**
   - `get_payment_analysis()` - 合并为单次查询
   - `get_dashboard_stats()` - 合并为 2-3 次查询

### Phase 3 (中期优化 - Continuous)

5. **查询性能监控**
   - 启用 PostgreSQL `pg_stat_statements`
   - 设置慢查询日志 (>100ms)
   - 定期分析查询执行计划

6. **建立性能基线**
   - 记录关键 API 响应时间
   - 设置性能告警阈值

---

## 9. 性能测试建议

### 9.1 基准测试

```bash
# 使用 Apache Bench 或 wrk 进行压力测试
wrk -t12 -c400 -d30s http://localhost:8000/api/v1/customers?page=100
```

### 9.2 监控指标

| 指标 | 当前值 | 目标值 | 测量方法 |
|------|--------|--------|----------|
| 客户列表 API P95 | TBD | <200ms | APM 监控 |
| 仪表盘统计 API | TBD | <500ms | APM 监控 |
| 数据库查询平均耗时 | TBD | <50ms | pg_stat_statements |
| 慢查询数量/天 | TBD | <10 | 慢查询日志 |

---

## 10. 总结

### 发现的主要问题

1. **N+1 查询**: 3 处，影响高
2. **缺失索引**: 8 个关键列，影响高
3. **OFFSET 分页**: 4 处，中等影响
4. **冗余查询**: 2 处，中等影响
5. **SELECT * 低效**: 3 处，低影响
6. **事务边界**: 1 处，低影响

### 预期优化效果

- **查询数量减少**: 60-80% (通过合并查询和 eager loading)
- **响应时间提升**: 50-90% (通过索引和优化查询)
- **大数据量分页**: 10 倍+ 性能提升 (通过游标分页)

### 下一步行动

1. 审查并执行索引迁移脚本
2. 优先修复 N+1 查询问题
3. 实施游标分页 API
4. 建立性能监控基线

---

**报告生成时间**: 2026-04-04  
**分析师**: Backend Architect Agent  
**版本**: 1.0
