# 查询优化代码示例

本文档提供具体的代码示例，帮助实施 `db-query-optimization.md` 中推荐的优化方案。

---

## 1. N+1 查询优化示例

### 1.1 优化 `get_inactive_customers()`

**原代码位置**: `backend/app/services/analytics.py:367-409`

```python
# ❌ 原代码 - 多次查询 + Python 集合操作
def get_inactive_customers(self, days: int = 90) -> List[Dict[str, Any]]:
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # 查询 1: 所有有消耗记录的客户
    has_usage_stmt = select(func.distinct(ConsumptionRecord.customer_id))
    all_customers_with_usage = set(
        row[0] for row in self.db.execute(has_usage_stmt).all()
    )
    
    # 查询 2: 最近有消耗的客户
    recent_usage_stmt = select(func.distinct(ConsumptionRecord.customer_id)).where(
        ConsumptionRecord.created_at >= cutoff_date
    )
    recent_customers = set(
        row[0] for row in self.db.execute(recent_usage_stmt).all()
    )
    
    # Python 集合操作
    inactive_customer_ids = all_customers_with_usage - recent_customers
    
    if not inactive_customer_ids:
        return []
    
    # 查询 3: 获取客户详情
    stmt = (
        select(
            Customer.id,
            Customer.name,
            Customer.company_id,
            Customer.manager_id,
            User.real_name.label("manager_name"),
        )
        .where(
            and_(
                Customer.id.in_(inactive_customer_ids),
                Customer.deleted_at.is_(None),
            )
        )
        .outerjoin(User, Customer.manager_id == User.id)
    )
    
    result = self.db.execute(stmt).all()
    return [...]
```

**✅ 优化代码 - 使用子查询一次性完成**:

```python
# ✅ 优化后 - 单次查询
def get_inactive_customers(self, days: int = 90) -> List[Dict[str, Any]]:
    """获取长期未消耗客户列表（优化版）
    
    使用子查询替代 Python 集合操作，避免 IN 列表过长问题
    """
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # 子查询：最近有消耗的客户
    recent_customer_subq = (
        select(func.distinct(ConsumptionRecord.customer_id))
        .where(ConsumptionRecord.created_at >= cutoff_date)
        .subquery()
    )
    
    # 主查询：有消耗记录但最近无消耗的客户
    stmt = (
        select(
            Customer.id,
            Customer.name,
            Customer.company_id,
            Customer.manager_id,
            User.real_name.label("manager_name"),
        )
        .join(
            ConsumptionRecord,
            Customer.id == ConsumptionRecord.customer_id
        )
        .outerjoin(
            recent_customer_subq,
            Customer.id == recent_customer_subq.c.customer_id
        )
        .outerjoin(User, Customer.manager_id == User.id)
        .where(
            and_(
                Customer.deleted_at.is_(None),
                recent_customer_subq.c.customer_id.is_(None),  # 排除最近有消耗的
            )
        )
        .distinct()  # 避免重复
    )
    
    result = self.db.execute(stmt).all()
    return [
        {
            "customer_id": row.id,
            "company_id": row.company_id,
            "customer_name": row.name,
            "manager_id": row.manager_id,
            "manager_name": row.manager_name or "未分配",
        }
        for row in result
    ]
```

---

### 1.2 优化 `get_customer_health_stats()`

**原代码位置**: `backend/app/services/analytics.py:275-318`

```python
# ❌ 原代码 - 6 次独立查询
def get_customer_health_stats(self) -> Dict[str, Any]:
    # 查询 1
    active_stmt = select(func.count(func.distinct(ConsumptionRecord.customer_id)))
    active_count = self.db.execute(active_stmt).scalar() or 0
    
    # 查询 2
    total_stmt = select(func.count(Customer.id)).where(
        Customer.deleted_at.is_(None)
    )
    total_count = self.db.execute(total_stmt).scalar() or 0
    
    # 查询 3
    warning_stmt = select(func.count(CustomerBalance.id)).where(
        CustomerBalance.total_amount < 1000
    )
    warning_count = self.db.execute(warning_stmt).scalar() or 0
    
    # 查询 4-6: 流失风险客户 (更复杂)
    ...
```

**✅ 优化代码 - 使用 CASE 表达式单次查询**:

```python
# ✅ 优化后 - 单次聚合查询
def get_customer_health_stats(self) -> Dict[str, Any]:
    """获取客户健康度统计（优化版）
    
    使用 CASE 表达式和聚合函数，将 6 次查询合并为 1 次
    """
    from datetime import timedelta
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    
    # 子查询：每个客户最近消耗时间
    last_consumption_subq = (
        select(
            ConsumptionRecord.customer_id,
            func.max(ConsumptionRecord.created_at).label("last_consumption")
        )
        .group_by(ConsumptionRecord.customer_id)
        .subquery()
    )
    
    # 主查询：使用 CASE 表达式计算所有统计
    stmt = select(
        func.count(Customer.id).label("total_count"),
        func.count(func.distinct(last_consumption_subq.c.customer_id)).label("active_count"),
        func.sum(
            case(
                (CustomerBalance.total_amount < 1000, 1),
                else_=0
            )
        ).label("warning_count"),
        func.sum(
            case(
                (
                    and_(
                        last_consumption_subq.c.last_consumption < ninety_days_ago,
                        last_consumption_subq.c.last_consumption != None
                    ),
                    1
                ),
                else_=0
            )
        ).label("churn_count"),
    ).select_from(Customer).outerjoin(
        CustomerBalance, Customer.id == CustomerBalance.customer_id
    ).outerjoin(
        last_consumption_subq, Customer.id == last_consumption_subq.c.customer_id
    ).where(
        Customer.deleted_at.is_(None)
    )
    
    result = self.db.execute(stmt).first()
    
    total_count = result.total_count or 0
    active_count = result.active_count or 0
    
    return {
        "total_customers": total_count,
        "active_customers": active_count,
        "inactive_customers": total_count - active_count,
        "warning_customers": result.warning_count or 0,
        "churn_risk_customers": result.churn_count or 0,
        "active_rate": round(active_count / total_count * 100, 2)
        if total_count > 0
        else 0,
    }
```

---

## 2. 游标分页示例

### 2.1 客户列表游标分页

**原代码位置**: `backend/app/services/customers.py:45-85`

```python
# ❌ 原代码 - OFFSET 分页
async def get_all_customers(
    self,
    page: int = 1,
    page_size: int = 20,
    filters: Optional[dict] = None,
) -> Tuple[List[Customer], int]:
    ...
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
```

**✅ 优化代码 - 游标分页**:

```python
# ✅ 优化后 - 游标分页（基于 ID）
async def get_all_customers(
    self,
    page_size: int = 20,
    filters: Optional[dict] = None,
    cursor: Optional[int] = None,  # 最后一条记录的 ID
) -> Tuple[List[Customer], Optional[int], bool]:
    """获取客户列表（游标分页版）
    
    Args:
        page_size: 每页数量
        filters: 筛选条件字典
        cursor: 游标（上一页最后一条记录的 ID）
    
    Returns:
        (customers, next_cursor, has_next)
        - customers: 客户列表
        - next_cursor: 下一页游标（None 表示无更多）
        - has_next: 是否有下一页
    """
    stmt = select(Customer).where(Customer.deleted_at.is_(None))
    
    # 应用筛选条件
    if filters:
        conditions = []
        if filters.get("keyword"):
            keyword = filters["keyword"]
            conditions.append(
                or_(
                    Customer.name.ilike(f"%{keyword}%"),
                    Customer.company_id.ilike(f"%{keyword}%"),
                )
            )
        # ... 其他筛选条件
        if conditions:
            stmt = stmt.where(and_(*conditions))
    
    # 游标过滤：只获取 ID 小于游标的记录
    if cursor:
        stmt = stmt.where(Customer.id < cursor)
    
    # 按 ID 降序，多取 1 条用于判断是否有下一页
    stmt = stmt.order_by(Customer.id.desc()).limit(page_size + 1)
    
    # 添加 eager loading
    stmt = stmt.options(
        selectinload(Customer.profile),
        selectinload(Customer.balance),
    )
    
    result = await self.db.execute(stmt)
    customers = list(result.scalars().all())
    
    # 判断是否有下一页
    has_next = len(customers) > page_size
    if has_next:
        customers = customers[:-1]  # 移除多取的记录
    
    # 计算下一页游标
    next_cursor = customers[-1].id if customers else None
    
    return customers, next_cursor, has_next
```

**对应的路由修改**:

```python
# routes/customers.py
@customers_bp.get("")
async def list_customers(request: Request):
    """获取客户列表（游标分页）
    
    Query:
    - cursor: 游标（上一页最后一条记录的 ID）
    - page_size: 每页数量（默认 20，最大 100）
    - keyword: 关键词
    - ...其他筛选参数
    """
    cursor = request.args.get("cursor", type=int)
    page_size = int(request.args.get("page_size", 20))
    page_size = min(page_size, 100)
    
    # 构建筛选条件
    filters = {...}
    
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)
    
    customers, next_cursor, has_next = await service.get_all_customers(
        page_size=page_size,
        filters=filters,
        cursor=cursor,
    )
    
    # 构建上一页游标（可选，需要额外查询）
    prev_cursor = customers[0].id if customers and cursor else None
    
    return json({
        "data": [...],
        "pagination": {
            "next_cursor": next_cursor,
            "prev_cursor": prev_cursor,
            "has_next": has_next,
            "has_prev": cursor is not None,
        },
    })
```

---

### 2.2 时间戳游标分页（用于充值记录）

```python
# ✅ 基于时间戳的游标分页
async def get_recharge_records(
    self,
    customer_id: Optional[int] = None,
    page_size: int = 20,
    cursor: Optional[str] = None,  # ISO 8601 时间戳
) -> Tuple[List[RechargeRecord], Optional[str], bool]:
    """获取充值记录列表（游标分页版）
    
    Args:
        customer_id: 客户 ID
        page_size: 每页数量
        cursor: 游标（上一页最后一条记录的 created_at）
    
    Returns:
        (records, next_cursor, has_next)
    """
    stmt = select(RechargeRecord).where(RechargeRecord.deleted_at.is_(None))
    
    if customer_id:
        stmt = stmt.where(RechargeRecord.customer_id == customer_id)
    
    # 游标过滤
    if cursor:
        stmt = stmt.where(RechargeRecord.created_at < cursor)
    
    # 按 created_at 降序
    stmt = stmt.order_by(RechargeRecord.created_at.desc()).limit(page_size + 1)
    
    result = await self.db.execute(stmt)
    records = list(result.scalars().all())
    
    has_next = len(records) > page_size
    if has_next:
        records = records[:-1]
    
    next_cursor = records[-1].created_at.isoformat() if records else None
    
    return records, next_cursor, has_next
```

---

## 3. 合并冗余查询示例

### 3.1 优化 `get_payment_analysis()`

**原代码位置**: `backend/app/services/analytics.py:181-236`

```python
# ✅ 优化后 - 使用 CTE 合并查询
def get_payment_analysis(
    self, start_date: date, end_date: date, customer_id: Optional[int] = None
) -> Dict[str, Any]:
    """获取回款分析数据（优化版）
    
    使用 CTE 将 2 次查询合并为 1 次
    """
    from sqlalchemy import literal_column
    
    # CTE 1: 结算金额统计
    invoice_cte = (
        select(
            func.sum(Invoice.total_amount).label("total_invoiced"),
            func.sum(Invoice.discount_amount).label("total_discount"),
            func.sum(Invoice.total_amount - Invoice.discount_amount).label("total_final"),
        )
        .where(
            and_(
                Invoice.period_start >= start_date,
                Invoice.period_end <= end_date,
                Invoice.status != "cancelled",
            )
        )
    )
    if customer_id:
        invoice_cte = invoice_cte.where(Invoice.customer_id == customer_id)
    
    # CTE 2: 回款金额统计
    payment_cte = (
        select(
            func.sum(RechargeRecord.real_amount).label("total_paid"),
        )
        .where(
            and_(
                RechargeRecord.created_at >= datetime.combine(start_date, datetime.min.time()),
                RechargeRecord.created_at <= datetime.combine(end_date, datetime.max.time()),
            )
        )
    )
    if customer_id:
        payment_cte = payment_cte.where(RechargeRecord.customer_id == customer_id)
    
    # 交叉连接获取所有数据
    stmt = select(invoice_cte, payment_cte)
    result = self.db.execute(stmt).first()
    
    total_invoiced = float(result.total_invoiced or 0)
    total_final = float(result.total_final or 0)
    total_paid = float(result.total_paid or 0)
    
    return {
        "total_invoiced": total_invoiced,
        "total_discount": float(result.total_discount or 0),
        "total_final": total_final,
        "total_paid": total_paid,
        "completion_rate": round(total_paid / total_final * 100, 2)
        if total_final > 0
        else 0,
        "difference": total_final - total_paid,
    }
```

---

### 3.2 优化 `get_dashboard_stats()`

```python
# ✅ 优化后 - 合并为 3 次查询
def get_dashboard_stats(self) -> Dict[str, Any]:
    """获取仪表盘统计数据（优化版）
    
    将 8 次查询合并为 3 次
    """
    today = datetime.utcnow()
    current_month_start = date(today.year, today.month, 1)
    current_month_end = date(
        today.year, today.month, monthrange(today.year, today.month)[1]
    )
    
    # 查询 1: 客户统计
    customer_stmt = select(
        func.count(Customer.id).label("total"),
        func.sum(
            case((Customer.is_key_customer == True, 1), else_=0)
        ).label("key_count"),
    ).where(Customer.deleted_at.is_(None))
    customer_result = self.db.execute(customer_stmt).first()
    
    # 查询 2: 余额统计
    balance_stmt = select(
        func.sum(CustomerBalance.total_amount).label("total_balance"),
        func.sum(CustomerBalance.real_amount).label("real_balance"),
        func.sum(CustomerBalance.bonus_amount).label("bonus_balance"),
    )
    balance_result = self.db.execute(balance_stmt).first()
    
    # 查询 3: 结算单统计
    invoice_stmt = select(
        func.count(Invoice.id).label("month_count"),
        func.sum(
            case((Invoice.status == "pending_customer", 1), else_=0)
        ).label("pending_count"),
        func.sum(
            case((
                and_(
                    Invoice.period_start >= current_month_start,
                    Invoice.period_end <= current_month_end,
                    Invoice.status != "cancelled",
                ),
                Invoice.total_amount
            ), else_=0)
        ).label("month_consumption"),
    ).where(Invoice.deleted_at.is_(None))
    invoice_result = self.db.execute(invoice_stmt).first()
    
    return {
        "total_customers": customer_result.total or 0,
        "key_customers": customer_result.key_count or 0,
        "total_balance": float(balance_result.total_balance or 0),
        "real_balance": float(balance_result.real_balance or 0),
        "bonus_balance": float(balance_result.bonus_amount or 0),
        "month_invoice_count": invoice_result.month_count or 0,
        "pending_confirmation": invoice_result.pending_count or 0,
        "month_consumption": float(invoice_result.month_consumption or 0),
    }
```

---

## 4. SELECT * 优化示例

### 4.1 只选择需要的列

```python
# ❌ 原代码 - SELECT *
async def _apply_dynamic_filter(
    self, conditions: Optional[Dict[str, Any]], page: int, page_size: int
) -> Tuple[List[Customer], int]:
    stmt = select(Customer).where(and_(*filters), Customer.deleted_at.is_(None))
```

```python
# ✅ 优化后 - 只选择需要的列
async def _apply_dynamic_filter(
    self, conditions: Optional[Dict[str, Any]], page: int, page_size: int
) -> Tuple[List[Customer], int]:
    """应用动态筛选条件（优化版）
    
    只查询需要的列，减少网络传输
    """
    # 只选择列表展示需要的列
    stmt = select(
        Customer.id,
        Customer.company_id,
        Customer.name,
        Customer.account_type,
        Customer.business_type,
        Customer.customer_level,
        Customer.manager_id,
        Customer.is_key_customer,
        Customer.created_at,
    ).where(and_(*filters), Customer.deleted_at.is_(None))
    
    # 总数查询
    count_stmt = select(func.count(Customer.id)).where(
        and_(*filters), Customer.deleted_at.is_(None)
    )
    total = (await self.db.execute(count_stmt)).scalar() or 0
    
    # 分页排序
    stmt = stmt.order_by(Customer.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    
    result = await self.db.execute(stmt)
    customers = result.all()  # 注意：返回的是 Row 对象，不是 Customer 实体
    
    # 转换为字典列表
    return [
        {
            "id": row.id,
            "company_id": row.company_id,
            "name": row.name,
            "account_type": row.account_type,
            "business_type": row.business_type,
            "customer_level": row.customer_level,
            "manager_id": row.manager_id,
            "is_key_customer": row.is_key_customer,
            "created_at": row.created_at,
        }
        for row in customers
    ], total
```

---

## 5. Eager Loading 最佳实践

### 5.1 使用 selectinload 避免 N+1

```python
# ✅ 正确的 eager loading 用法
async def get_customer_by_id(self, customer_id: int) -> Optional[Customer]:
    """获取客户详情（带关联数据）"""
    result = await self.db.execute(
        select(Customer)
        .options(
            selectinload(Customer.profile),      # 加载画像
            selectinload(Customer.balance),      # 加载余额
            selectinload(Customer.tags),         # 加载标签
            selectinload(Customer.group_memberships),  # 加载群组关系
        )
        .where(Customer.id == customer_id, Customer.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()
```

### 5.2 深度 eager loading

```python
# ✅ 多层级 eager loading
from sqlalchemy.orm import selectinload, joinedload

async def get_invoice_with_details(self, invoice_id: int):
    """获取结算单及所有关联数据"""
    result = await self.db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.items),  # 加载结算项
            joinedload(Invoice.customer)  # 加载客户（使用 joinedload 因为是一对一）
                .selectinload(Customer.profile),  # 继续加载客户画像
        )
        .where(Invoice.id == invoice_id)
    )
    return result.scalar_one_or_none()
```

---

## 6. 性能监控 SQL

### 6.1 启用 pg_stat_statements

```sql
-- 在 PostgreSQL 配置中添加
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
pg_stat_statements.max = 10000
```

### 6.2 查询最慢的 SQL

```sql
-- 查看最慢的 10 个查询
SELECT 
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    rows
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### 6.3 查看表索引使用情况

```sql
-- 查看索引使用统计
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

---

**文档版本**: 1.0  
**最后更新**: 2026-04-04
