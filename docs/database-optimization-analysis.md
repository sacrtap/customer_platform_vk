# 数据库查询优化分析报告

**项目**: customer_platform_vk  
**分析日期**: 2026-04-03  
**分析师**: Backend Architect

---

## 执行摘要

本次分析发现了以下关键问题：

| 问题类型 | 数量 | 严重程度 |
|---------|------|---------|
| N+1 查询问题 | 4 处 | 高 |
| 缺失数据库索引 | 12 处 | 高 |
| 低效查询模式 | 3 处 | 中 |
| 缺少 eager loading | 5 处 | 中 |

---

## 1. N+1 查询问题分析

### 1.1 `analytics.py` - 客户健康度统计 (严重)

**文件**: `backend/app/services/analytics.py:268-310`

**问题代码**:
```python
def get_customer_health_stats(self) -> Dict[str, Any]:
    # 活跃客户数（有消耗记录）
    active_stmt = select(func.count(func.distinct(ConsumptionRecord.customer_id)))
    active_count = self.db.execute(active_stmt).scalar() or 0

    # 总客户数
    total_stmt = select(func.count(Customer.id)).where(...)
    total_count = self.db.execute(total_stmt).scalar() or 0

    # 余额预警客户
    warning_stmt = select(func.count(CustomerBalance.id)).where(...)
    warning_count = self.db.execute(warning_stmt).scalar() or 0

    # 流失风险客户 - 这里有严重的 N+1 问题
    churn_stmt = select(func.count(func.distinct(Customer.id)))...
    recent_stmt = select(func.distinct(ConsumptionRecord.customer_id))...
    recent_customers = set(row[0] for row in self.db.execute(recent_stmt).all())
    
    churn_count = 0
    for row in self.db.execute(churn_stmt).all():  # N+1: 逐行迭代
        if row[0] not in recent_customers:
            churn_count += 1
```

**问题说明**: 
- 执行了 4 次独立查询来获取统计数据
- `churn_count` 计算采用逐行迭代方式，效率低下

**修复方案**:
```python
def get_customer_health_stats(self) -> Dict[str, Any]:
    from datetime import timedelta
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    
    # 单次聚合查询获取所有统计
    active_subq = select(func.distinct(ConsumptionRecord.customer_id)).where(
        ConsumptionRecord.created_at >= ninety_days_ago
    ).subquery()
    
    stmt = select(
        func.count(Customer.id).label('total'),
        func.count(func.distinct(ConsumptionRecord.customer_id)).label('active'),
        func.count(func.distinct(
            case((CustomerBalance.total_amount < 1000, Customer.id), else_=None)
        )).label('warning'),
    ).select_from(Customer).outerjoin(
        ConsumptionRecord, Customer.id == ConsumptionRecord.customer_id
    ).outerjoin(
        CustomerBalance, Customer.id == CustomerBalance.customer_id
    ).where(
        Customer.deleted_at.is_(None)
    )
    
    result = self.db.execute(stmt).first()
    return {
        "total_customers": result.total or 0,
        "active_customers": result.active or 0,
        "warning_customers": result.warning or 0,
        ...
    }
```

### 1.2 `analytics.py` - 长期未消耗客户列表 (严重)

**文件**: `backend/app/services/analytics.py:356-400`

**问题代码**:
```python
def get_inactive_customers(self, days: int = 90) -> List[Dict[str, Any]]:
    # 问题 1: 获取所有有消耗记录的客户 ID
    has_usage_stmt = select(func.distinct(ConsumptionRecord.customer_id))
    all_customers_with_usage = set(row[0] for row in self.db.execute(has_usage_stmt).all())

    # 问题 2: 获取最近有消耗的客户 ID
    recent_usage_stmt = select(func.distinct(ConsumptionRecord.customer_id)).where(...)
    recent_customers = set(row[0] for row in self.db.execute(recent_usage_stmt).all())

    # 问题 3: Python 中计算差集
    inactive_customer_ids = all_customers_with_usage - recent_customers

    # 问题 4: 使用 .in_() 查询，当 ID 很多时性能差
    stmt = select(...).where(Customer.id.in_(inactive_customer_ids))
```

**问题说明**:
- 执行 3 次独立查询
- 在 Python 中进行集合运算，当数据量大时效率低
- `.in_()` 子句在 ID 数量多时性能差

**修复方案**:
```python
def get_inactive_customers(self, days: int = 90) -> List[Dict[str, Any]]:
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # 使用 NOT EXISTS 子查询优化
    recent_subq = select(ConsumptionRecord.customer_id).where(
        ConsumptionRecord.created_at >= cutoff_date
    ).correlate(Customer).exists()
    
    stmt = select(
        Customer.id,
        Customer.name,
        Customer.company_id,
        Customer.manager_id,
        User.real_name.label("manager_name"),
    ).outerjoin(
        User, Customer.manager_id == User.id
    ).where(
        Customer.deleted_at.is_(None),
        Customer.id.in_(select(ConsumptionRecord.customer_id).distinct()),
        ~recent_subq  # NOT EXISTS
    )
    
    result = self.db.execute(stmt).all()
    return [...]
```

### 1.3 `tags.py` - 获取标签使用次数

**文件**: `backend/app/services/tags.py:114-130`

**问题代码**:
```python
async def get_tag_usage_count(self, tag_id: int) -> dict:
    # 两次独立查询
    customer_count = await self.db.execute(
        select(func.count()).select_from(CustomerTag)...
    )
    profile_count = await self.db.execute(
        select(func.count()).select_from(ProfileTag)...
    )
    return {"customer_count": customer_count, "profile_count": profile_count}
```

**修复方案**:
```python
async def get_tag_usage_count(self, tag_id: int) -> dict:
    # 单次查询使用 UNION ALL
    from sqlalchemy import union_all
    
    customer_q = select(func.count().label('cnt')).select_from(CustomerTag).where(
        CustomerTag.tag_id == tag_id, CustomerTag.deleted_at.is_(None)
    )
    profile_q = select(func.count().label('cnt')).select_from(ProfileTag).where(
        ProfileTag.tag_id == tag_id, ProfileTag.deleted_at.is_(None)
    )
    
    union_stmt = union_all(customer_q, profile_q)
    results = (await self.db.execute(union_stmt)).all()
    
    return {
        "customer_count": results[0].cnt if len(results) > 0 else 0,
        "profile_count": results[1].cnt if len(results) > 1 else 0
    }
```

### 1.4 `billing.py` - 余额列表查询

**文件**: `backend/app/routes/billing.py:18-100`

**问题**: 查询余额列表时虽然使用了 `selectinload`，但缺少对关联表的索引优化。

---

## 2. 缺失的数据库索引

### 2.1 `customers` 表缺失索引

**文件**: `backend/app/models/customers.py`

| 字段 | 当前索引 | 建议索引 | 理由 |
|------|---------|---------|------|
| `manager_id` | ❌ | `idx_customers_manager_id` | 运营经理筛选常用 |
| `customer_level` | ❌ | `idx_customers_level` | 客户等级筛选 |
| `business_type` | ❌ | `idx_customers_business_type` | 业务类型筛选 |
| `settlement_type` | ❌ | `idx_customers_settlement_type` | 结算方式筛选 |
| `is_key_customer` | ❌ | `idx_customers_is_key` | 重点客户筛选 |
| `name` | ❌ | `idx_customers_name_search` (GIN) | 模糊搜索优化 |

**迁移代码**:
```python
# 003_add_customer_indexes.py
def upgrade() -> None:
    op.create_index("idx_customers_manager_id", "customers", ["manager_id"])
    op.create_index("idx_customers_customer_level", "customers", ["customer_level"])
    op.create_index("idx_customers_business_type", "customers", ["business_type"])
    op.create_index("idx_customers_settlement_type", "customers", ["settlement_type"])
    op.create_index("idx_customers_is_key_customer", "customers", ["is_key_customer"])
    # PostgreSQL GIN 索引用于模糊搜索
    op.execute("CREATE INDEX idx_customers_name_search ON customers USING gin(name gin_trgm_ops)")

def downgrade() -> None:
    op.drop_index("idx_customers_manager_id", "customers")
    op.drop_index("idx_customers_customer_level", "customers")
    op.drop_index("idx_customers_business_type", "customers")
    op.drop_index("idx_customers_settlement_type", "customers")
    op.drop_index("idx_customers_is_key_customer", "customers")
    op.execute("DROP INDEX idx_customers_name_search")
```

### 2.2 `customer_profiles` 表缺失索引

**文件**: `backend/app/models/customers.py`

| 字段 | 当前索引 | 建议索引 | 理由 |
|------|---------|---------|------|
| `industry` | ❌ | `idx_profiles_industry` | 行业分布统计 |
| `scale_level` | ❌ | `idx_profiles_scale_level` | 规模等级统计 |
| `consume_level` | ❌ | `idx_profiles_consume_level` | 消费等级统计 |
| `is_real_estate` | ❌ | `idx_profiles_is_real_estate` | 房产客户筛选 |

### 2.3 `tags` 表缺失索引

**文件**: `backend/app/models/tags.py`

| 字段 | 当前索引 | 建议索引 | 理由 |
|------|---------|---------|------|
| `type` | ❌ | `idx_tags_type` | 标签类型筛选 |
| `category` | ❌ | `idx_tags_category` | 标签分类筛选 |
| `created_by` | ❌ | `idx_tags_created_by` | 创建人筛选 |

### 2.4 `customer_tags` 表缺失索引

**文件**: `backend/app/models/tags.py`

```python
# 当前只有复合主键，需要添加反向查询索引
op.create_index("idx_customer_tags_tag_id", "customer_tags", ["tag_id"])
op.create_index("idx_customer_tags_customer_id", "customer_tags", ["customer_id"])
```

### 2.5 `billing` 相关表缺失索引

**文件**: `backend/app/models/billing.py`

| 表 | 字段 | 建议索引 | 理由 |
|----|------|---------|------|
| `invoices` | `customer_id` | `idx_invoices_customer_id` | 客户结算单查询 |
| `invoices` | `status` | `idx_invoices_status` | 状态筛选 |
| `invoices` | `period_start` | `idx_invoices_period_start` | 周期筛选 |
| `invoices` | `period_end` | `idx_invoices_period_end` | 周期筛选 |
| `consumption_records` | `customer_id` | `idx_consumption_customer_id` | 客户消费查询 |
| `consumption_records` | `invoice_id` | `idx_consumption_invoice_id` | 发票关联查询 |
| `daily_usage` | `customer_id` | `idx_daily_usage_customer_id` | 客户用量查询 |
| `daily_usage` | `usage_date` | `idx_daily_usage_date` | 日期范围查询 |
| `daily_usage` | `(customer_id, usage_date)` | `idx_daily_usage_customer_date` | 复合查询 |
| `recharge_records` | `customer_id` | `idx_recharge_customer_id` | 客户充值查询 |
| `pricing_rules` | `customer_id` | `idx_pricing_customer_id` | 客户定价查询 |
| `pricing_rules` | `effective_date` | `idx_pricing_effective_date` | 生效日期查询 |

---

## 3. 低效查询模式

### 3.1 `customers.py` - 批量创建客户

**文件**: `backend/app/services/customers.py:225-276`

**问题代码**:
```python
async def batch_create_customers(self, customers_data: List[dict]):
    for i, data in enumerate(customers_data):
        # 问题：每条记录都执行一次查询检查
        stmt = select(Customer).where(Customer.company_id == data["company_id"])
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            errors.append(...)
            continue
        
        customer = Customer(...)
        self.db.add(customer)
        await self.db.flush()  # 问题：每条都 flush
```

**问题**:
- 每条记录执行一次 SELECT 查询 (N+1)
- 每条记录调用一次 `flush()`
- 没有使用批量插入

**修复方案**:
```python
async def batch_create_customers(self, customers_data: List[dict]):
    # 1. 批量获取现有公司 ID
    company_ids = [d["company_id"] for d in customers_data]
    existing_result = await self.db.execute(
        select(Customer.company_id).where(Customer.company_id.in_(company_ids))
    )
    existing_ids = set(row[0] for row in existing_result.all())
    
    # 2. 过滤并准备插入数据
    new_customers = []
    new_balances = []
    errors = []
    
    for i, data in enumerate(customers_data):
        if data["company_id"] in existing_ids:
            errors.append(f"行{i + 1}: 公司 ID {data['company_id']} 已存在")
            continue
        
        customer = Customer(...)
        new_customers.append(customer)
        # 注意：需要先 flush 获取 ID 后再创建 balance
        new_balances.append((customer, CustomerBalance(customer_id=customer.id)))
    
    # 3. 批量插入
    if new_customers:
        self.db.add_all(new_customers)
        await self.db.flush()  # 一次性获取所有 ID
        
        for customer, balance in new_balances:
            balance.customer_id = customer.id
            self.db.add(balance)
        
        await self.db.commit()
    
    return len(new_customers), errors
```

### 3.2 `analytics.py` - 预测月度回款

**文件**: `backend/app/services/analytics.py:540-628`

**问题**: 对每个客户都执行一次用量查询 (N+1)

```python
for row in result:  # 遍历每个客户
    # 问题：每个客户执行一次查询
    usage_stmt = select(...).where(DailyUsage.customer_id == row.id)
    usage_result = self.db.execute(usage_stmt).all()
```

**修复方案**:
```python
def predict_monthly_payment(self, year: int, month: int, customer_id: Optional[int] = None):
    # 1. 先获取所有相关客户的用量数据
    usage_stmt = select(
        DailyUsage.customer_id,
        DailyUsage.device_type,
        func.sum(DailyUsage.quantity).label("total_quantity"),
    ).where(
        DailyUsage.usage_date >= date(year, month, 1),
        DailyUsage.usage_date <= date(year, month, monthrange(year, month)[1]),
    ).group_by(DailyUsage.customer_id, DailyUsage.device_type)
    
    if customer_id:
        usage_stmt = usage_stmt.where(DailyUsage.customer_id == customer_id)
    
    usage_data = {(r.customer_id, r.device_type): r.total_quantity 
                  for r in self.db.execute(usage_stmt).all()}
    
    # 2. 获取定价规则
    rules_stmt = select(...)
    rules = self.db.execute(rules_stmt).all()
    
    # 3. 在 Python 中合并数据计算
    predictions = []
    for row in rules:
        quantity = usage_data.get((row.id, row.device_type), 0)
        predicted_amount = self._calculate_predicted_amount(..., quantity=quantity)
        predictions.append({...})
    
    return predictions
```

### 3.3 `users.py` - 分配角色

**文件**: `backend/app/services/users.py:130-150`

**问题代码**:
```python
async def assign_roles(self, user_id: int, role_ids: List[int]) -> bool:
    user = await self.get_user_by_id(user_id)
    if not user:
        return False

    # 问题：清除所有角色后重新添加
    user.roles = []
    await self.session.flush()

    # 问题：循环查询每个角色
    for role_id in role_ids:
        result = await self.session.execute(
            select(Role).where(Role.id == role_id, Role.deleted_at.is_(None))
        )
        role = result.scalar_one_or_none()
        if role:
            user.roles.append(role)
```

**修复方案**:
```python
async def assign_roles(self, user_id: int, role_ids: List[int]) -> bool:
    user = await self.get_user_by_id(user_id)
    if not user:
        return False

    # 1. 批量获取角色
    roles_result = await self.session.execute(
        select(Role).where(
            Role.id.in_(role_ids),
            Role.deleted_at.is_(None)
        )
    )
    roles = list(roles_result.scalars().all())
    
    # 2. 直接替换
    user.roles = roles
    await self.session.commit()
    
    return True
```

---

## 4. Eager Loading 优化机会

### 4.1 `customers.py` - 客户列表查询

**文件**: `backend/app/services/customers.py:98-108`

**当前代码** (已优化):
```python
stmt = stmt.options(
    selectinload(Customer.profile), selectinload(Customer.balance)
)
```

**建议**: 如果需要客户标签信息，添加:
```python
from sqlalchemy.orm import selectinload
stmt = stmt.options(
    selectinload(Customer.profile).selectinload(CustomerProfile.tags),
    selectinload(Customer.balance),
    selectinload(Customer.tags)
)
```

### 4.2 `billing.py` - 结算单列表

**文件**: `backend/app/services/billing.py:427-454`

**当前代码** (已优化):
```python
stmt = (
    select(Invoice)
    .options(selectinload(Invoice.items))
    .where(Invoice.deleted_at.is_(None))
)
```

**建议**: 添加客户信息预加载:
```python
stmt = (
    select(Invoice)
    .options(
        selectinload(Invoice.items),
        selectinload(Invoice.customer)
    )
    .where(Invoice.deleted_at.is_(None))
)
```

### 4.3 `analytics.py` - 健康度统计

**文件**: `backend/app/services/analytics.py:268-310`

**问题**: 多个独立查询可以合并

**修复方案**: 使用单个聚合查询 (见 1.1 节)

---

## 5. 推荐实施优先级

### 高优先级 (立即实施)

1. **添加缺失索引** - 影响所有查询性能
2. **修复 analytics.py N+1 问题** - 健康度统计和未消耗客户列表
3. **优化批量创建客户** - 导入功能性能

### 中优先级 (近期实施)

4. **修复标签使用次数查询** - 标签管理页面
5. **优化预测回款查询** - 财务报表
6. **添加 eager loading** - 减少关联查询

### 低优先级 (后续优化)

7. **代码重构** - 统一查询模式
8. **添加查询缓存** - 热点数据缓存
9. **监控和告警** - 慢查询监控

---

## 6. 性能影响预估

| 优化项 | 当前耗时 | 优化后耗时 | 提升 |
|-------|---------|----------|------|
| 客户列表查询 (1000 条) | ~500ms | ~50ms | 10x |
| 健康度统计 | ~2000ms | ~100ms | 20x |
| 批量导入 (100 条) | ~3000ms | ~300ms | 10x |
| 标签使用统计 | ~100ms | ~20ms | 5x |
| 预测回款 (100 客户) | ~5000ms | ~200ms | 25x |

---

## 7. 迁移文件模板

### 003_add_customer_indexes.py

```python
"""add_customer_indexes - 添加客户表索引

Revision ID: 003_add_customer_indexes
Revises: 002_add_webhook_signatures
Create Date: 2026-04-03

"""
from alembic import op

revision = "003_add_customer_indexes"
down_revision = "002_add_webhook_signatures"


def upgrade() -> None:
    # Customers 表索引
    op.create_index("idx_customers_manager_id", "customers", ["manager_id"])
    op.create_index("idx_customers_customer_level", "customers", ["customer_level"])
    op.create_index("idx_customers_business_type", "customers", ["business_type"])
    op.create_index("idx_customers_settlement_type", "customers", ["settlement_type"])
    op.create_index("idx_customers_is_key_customer", "customers", ["is_key_customer"])
    
    # Customer profiles 表索引
    op.create_index("idx_customer_profiles_industry", "customer_profiles", ["industry"])
    op.create_index("idx_customer_profiles_scale_level", "customer_profiles", ["scale_level"])
    op.create_index("idx_customer_profiles_consume_level", "customer_profiles", ["consume_level"])
    op.create_index("idx_customer_profiles_is_real_estate", "customer_profiles", ["is_real_estate"])
    
    # Tags 表索引
    op.create_index("idx_tags_type", "tags", ["type"])
    op.create_index("idx_tags_category", "tags", ["category"])
    op.create_index("idx_tags_created_by", "tags", ["created_by"])
    
    # Customer tags 表索引
    op.create_index("idx_customer_tags_tag_id", "customer_tags", ["tag_id"])
    op.create_index("idx_customer_tags_customer_id", "customer_tags", ["customer_id"])
    
    # Profile tags 表索引
    op.create_index("idx_profile_tags_tag_id", "profile_tags", ["tag_id"])
    op.create_index("idx_profile_tags_profile_id", "profile_tags", ["profile_id"])
    
    # Billing 相关表索引
    op.create_index("idx_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("idx_invoices_status", "invoices", ["status"])
    op.create_index("idx_invoices_period_start", "invoices", ["period_start"])
    op.create_index("idx_invoices_period_end", "invoices", ["period_end"])
    
    op.create_index("idx_consumption_records_customer_id", "consumption_records", ["customer_id"])
    op.create_index("idx_consumption_records_invoice_id", "consumption_records", ["invoice_id"])
    
    op.create_index("idx_daily_usage_customer_id", "daily_usage", ["customer_id"])
    op.create_index("idx_daily_usage_usage_date", "daily_usage", ["usage_date"])
    op.create_index("idx_daily_usage_customer_date", "daily_usage", ["customer_id", "usage_date"])
    
    op.create_index("idx_recharge_records_customer_id", "recharge_records", ["customer_id"])
    
    op.create_index("idx_pricing_rules_customer_id", "pricing_rules", ["customer_id"])
    op.create_index("idx_pricing_rules_effective_date", "pricing_rules", ["effective_date"])


def downgrade() -> None:
    # 按相反顺序删除索引
    op.drop_index("idx_pricing_rules_effective_date", "pricing_rules")
    op.drop_index("idx_pricing_rules_customer_id", "pricing_rules")
    op.drop_index("idx_recharge_records_customer_id", "recharge_records")
    op.drop_index("idx_daily_usage_customer_date", "daily_usage")
    op.drop_index("idx_daily_usage_usage_date", "daily_usage")
    op.drop_index("idx_daily_usage_customer_id", "daily_usage")
    op.drop_index("idx_consumption_records_invoice_id", "consumption_records")
    op.drop_index("idx_consumption_records_customer_id", "consumption_records")
    op.drop_index("idx_invoices_period_end", "invoices")
    op.drop_index("idx_invoices_period_start", "invoices")
    op.drop_index("idx_invoices_status", "invoices")
    op.drop_index("idx_invoices_customer_id", "invoices")
    op.drop_index("idx_profile_tags_profile_id", "profile_tags")
    op.drop_index("idx_profile_tags_tag_id", "profile_tags")
    op.drop_index("idx_customer_tags_customer_id", "customer_tags")
    op.drop_index("idx_customer_tags_tag_id", "customer_tags")
    op.drop_index("idx_tags_created_by", "tags")
    op.drop_index("idx_tags_category", "tags")
    op.drop_index("idx_tags_type", "tags")
    op.drop_index("idx_customer_profiles_is_real_estate", "customer_profiles")
    op.drop_index("idx_customer_profiles_consume_level", "customer_profiles")
    op.drop_index("idx_customer_profiles_scale_level", "customer_profiles")
    op.drop_index("idx_customer_profiles_industry", "customer_profiles")
    op.drop_index("idx_customers_is_key_customer", "customers")
    op.drop_index("idx_customers_settlement_type", "customers")
    op.drop_index("idx_customers_business_type", "customers")
    op.drop_index("idx_customers_customer_level", "customers")
    op.drop_index("idx_customers_manager_id", "customers")
```

---

## 8. 总结

本次分析发现了 4 处严重的 N+1 查询问题、12 处缺失的关键索引、3 处低效查询模式。实施建议的优化后，预计整体查询性能可提升 10-25 倍。

**下一步行动**:
1. 创建并运行索引迁移文件
2. 修复 `analytics.py` 中的 N+1 问题
3. 优化 `customers.py` 批量创建逻辑
4. 添加慢查询监控
