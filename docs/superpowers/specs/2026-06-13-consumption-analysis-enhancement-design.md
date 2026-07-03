# 消耗分析页面增强 - 技术设计文档

**创建日期**: 2026-06-13  
**关联 PRD**: `docs/specs/consumption-analysis-enhancement.md`  
**版本**: v1.0

---

## 1. 架构概览

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      定时任务调度层                          │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ 01:00 订单同步   │      │ 01:30 费用计算   │            │
│  └────────┬─────────┘      └────────┬─────────┘            │
└───────────┼─────────────────────────┼──────────────────────┘
            │                         │
            ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      业务服务层                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  OrderSyncService│      │CostCalcService   │            │
│  │  - 连接池管理    │      │  - 计费规则匹配  │            │
│  │  - 数据同步      │      │  - 费用计算      │            │
│  │  - 重试机制      │      │  - 降级处理      │            │
│  └────────┬─────────┘      └────────┬─────────┘            │
└───────────┼─────────────────────────┼──────────────────────┘
            │                         │
            ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据访问层                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │   DailyOrder     │      │ DailyConsumption │            │
│  │   Repository     │      │   Repository     │            │
│  └────────┬─────────┘      └────────┬─────────┘            │
└───────────┼─────────────────────────┼──────────────────────┘
            │                         │
            ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据存储层                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PostgreSQL (本地)                                    │  │
│  │  - daily_orders 表                                    │  │
│  │  - daily_consumption 表                               │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MySQL (外部，只读)                                   │  │
│  │  - 3dnest_engine_new.nest_model_order                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件

| 组件 | 职责 | 文件位置 |
|------|------|----------|
| `OrderSyncService` | 订单同步、连接池管理、重试机制 | `backend/app/services/order_sync.py` |
| `CostCalcService` | 费用计算、计费规则匹配 | `backend/app/services/cost_calc.py` |
| `DailyOrder` | 订单数据模型 | `backend/app/models/daily_order.py` |
| `DailyConsumption` | 消耗数据模型 | `backend/app/models/daily_consumption.py` |
| `sync_daily_orders` | 定时任务：订单同步 | `backend/app/tasks/order_sync.py` |
| `calc_daily_cost` | 定时任务：费用计算 | `backend/app/tasks/cost_calc.py` |

### 1.3 数据流

```
外部 MySQL ──→ OrderSyncService ──→ daily_orders 表
                                           │
                                           ▼
                                    CostCalcService
                                           │
                                           ▼
                                   daily_consumption 表
                                           │
                                           ▼
                                    API 接口层
                                           │
                                           ▼
                                     前端展示
```

---

## 2. 数据模型设计

### 2.1 DailyOrder 表

存储从外部 MySQL 同步的原始订单数据。

```python
class DailyOrder(Base):
    __tablename__ = 'daily_orders'
    
    id = Column(Integer, primary_key=True)
    order_code = Column(String(50), nullable=False)  # 订单 ID（外部系统）
    custom_code = Column(String(50))  # 房源编号
    nest_id = Column(String(50))  # 模型编号
    company_name = Column(String(200))  # 公司名称
    group_type = Column(String(50))  # 客户 ID（外部系统）
    customer_id = Column(Integer, ForeignKey('customers.id'))  # 系统客户 ID
    create_date = Column(Date, nullable=False)  # 订单创建时间
    floor_count = Column(Integer)  # 楼层数
    device_type = Column(String(10))  # 设备类型（X/N/L）
    sync_date = Column(Date, nullable=False)  # 同步日期
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 索引
    __table_args__ = (
        Index('idx_daily_orders_customer_date', 'customer_id', 'create_date'),
        Index('idx_daily_orders_sync_date', 'sync_date'),
        UniqueConstraint('order_code', 'create_date', name='uq_order_code_date'),
    )
```

**字段说明**：
- `order_code`: 外部系统订单唯一标识
- `group_type`: 外部系统的客户 ID，用于匹配
- `customer_id`: 匹配成功后填入系统客户 ID
- `sync_date`: 记录同步日期，用于追踪数据同步状态

### 2.2 DailyConsumption 表

存储按计费规则计算的每日消耗费用。

```python
class DailyConsumption(Base):
    __tablename__ = 'daily_consumption'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    consumption_date = Column(Date, nullable=False)
    device_type = Column(String(10), nullable=False)
    layer_type = Column(String(20), nullable=False)  # single/multi
    order_count = Column(Integer, nullable=False, default=0)
    total_cost = Column(Numeric(12, 2), nullable=False, default=0)
    pricing_rule_id = Column(Integer, ForeignKey('pricing_rules.id'))
    has_pricing_rule = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 索引
    __table_args__ = (
        Index('idx_daily_consumption_customer_date', 'customer_id', 'consumption_date'),
        Index('idx_daily_consumption_date', 'consumption_date'),
        UniqueConstraint('customer_id', 'consumption_date', 'device_type', 'layer_type', 
                        name='uq_consumption_unique'),
    )
```

**字段说明**：
- `order_count`: 当日该设备类型+楼层类型的订单数量
- `total_cost`: 当日该设备类型+楼层类型的结算费用
- `has_pricing_rule`: 是否有匹配的计费规则
- `pricing_rule_id`: 使用的计费规则 ID（可为 NULL）
- `layer_type`: 根据 `floor_count` 推导，`floor_count == 1` → `single`，`floor_count > 1` → `multi`

### 2.3 辅助数据类

```python
# backend/app/services/dto.py

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SyncResult:
    """订单同步结果"""
    success: int = 0
    failed: int = 0
    skipped: int = 0
    unmatched: list = field(default_factory=list)
    message: str = ""

@dataclass
class CalcResult:
    """费用计算结果"""
    total_customers: int = 0
    calculated: int = 0
    no_rule: int = 0

@dataclass
class CustomerCalcResult:
    """单客户计算结果"""
    has_rule: bool = False
```

### 2.4 SyncTaskLog 扩展

---

## 3. 服务层设计

### 3.1 OrderSyncService

```python
class OrderSyncService:
    """订单同步服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.external_engine = create_async_engine(
            settings.external_mysql_url,
            pool_size=5,
            pool_recycle=3600,
            pool_pre_ping=True
        )
    
    async def sync_orders(self, sync_date: date) -> SyncResult:
        """
        同步指定日期的订单数据
        
        Args:
            sync_date: 同步日期
            
        Returns:
            SyncResult: 同步结果（成功数、失败数、跳过数）
    async def sync_orders(self, sync_date: date) -> SyncResult:
        """
        同步指定日期的订单数据
        
        Args:
            sync_date: 同步日期
            
        Returns:
            SyncResult: 同步结果（成功数、失败数、跳过数）
        """
        # 1. 检查是否已同步
        existing_count = await self._check_existing(sync_date)
        if existing_count > 0:
            return SyncResult(skipped=existing_count, message="Already synced")
        
        # 2. 从外部 MySQL 查询订单
        orders = await self._fetch_orders_with_retry(sync_date)
        if not orders:
            return SyncResult(success=0, message="No orders found")
        
        # 3. 匹配客户并写入
        result = await self._match_and_save(orders, sync_date)
        
        return result
    
    async def _check_existing(self, sync_date: date) -> int:
        """检查指定日期是否已同步，返回已同步记录数"""
        result = await self.db.execute(
            select(func.count(DailyOrder.id)).where(
                DailyOrder.sync_date == sync_date
            )
        )
        return result.scalar() or 0
        # 2. 从外部 MySQL 查询订单
        orders = await self._fetch_orders_with_retry(sync_date)
        if not orders:
            return SyncResult(success=0, message="No orders found")
        
        # 3. 匹配客户并写入
        result = await self._match_and_save(orders, sync_date)
        
        return result
    
    async def _fetch_orders_with_retry(
        self, 
        sync_date: date, 
        max_retries: int = 3
    ) -> list[dict]:
        """带重试的订单查询"""
        for attempt in range(max_retries):
            try:
                return await self._fetch_orders(sync_date)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(wait_time)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
    
    async def _fetch_orders(self, sync_date: date) -> list[dict]:
        """从外部 MySQL 查询订单"""
        query = """
            SELECT 
                id, custom_code, nest_id, company_name,
                group_type, create_date, floor_count, device_type
            FROM 3dnest_engine_new.nest_model_order
            WHERE DATE(create_date) = %s
        """
        
        async with self.external_engine.connect() as conn:
            result = await conn.execute(text(query), {"date": sync_date})
            return [dict(row._mapping) for row in result]
    
    async def _match_and_save(
        self, 
        orders: list[dict], 
        sync_date: date
    ) -> SyncResult:
        """匹配客户并保存订单"""
        success_count = 0
        failed_count = 0
        unmatched = []
        
        for order in orders:
            # 匹配客户
            customer = await self._match_customer(order['group_type'])
            
            daily_order = DailyOrder(
                order_code=str(order['id']),
                custom_code=order.get('custom_code'),
                nest_id=order.get('nest_id'),
                company_name=order.get('company_name'),
                group_type=order.get('group_type'),
                customer_id=customer.id if customer else None,
                create_date=order['create_date'],
                floor_count=order.get('floor_count'),
                device_type=order.get('device_type'),
                sync_date=sync_date
            )
            
            self.db.add(daily_order)
            
            if customer:
                success_count += 1
            else:
                failed_count += 1
                unmatched.append(order['id'])
        
        await self.db.commit()
        
        return SyncResult(
            success=success_count,
            failed=failed_count,
            unmatched=unmatched
        )
    
    async def _match_customer(self, group_type: str) -> Optional[Customer]:
        """根据 external_id 匹配客户"""
        if not group_type:
            return None
        
        result = await self.db.execute(
            select(Customer).where(Customer.external_id == group_type)
        )
        return result.scalar_one_or_none()
```

### 3.2 CostCalcService

```python
class CostCalcService:
    """费用计算服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.invoice_service = InvoiceService(db)
    
    async def calculate_daily_cost(self, consumption_date: date) -> CalcResult:
        """
        计算指定日期的消耗费用
        
        Args:
            consumption_date: 消耗日期
            
        Returns:
            CalcResult: 计算结果
        """
        # 1. 查询当日有订单的客户
        customer_ids = await self._get_customers_with_orders(consumption_date)
        
        total_customers = len(customer_ids)
        calculated_count = 0
        no_rule_count = 0
        
        # 2. 对每个客户计算费用
        for customer_id in customer_ids:
            result = await self._calculate_customer_cost(
                customer_id, consumption_date
            )
            if result.has_rule:
                calculated_count += 1
            else:
                no_rule_count += 1
        
        return CalcResult(
            total_customers=total_customers,
            calculated=calculated_count,
            no_rule=no_rule_count
        )
    
    async def _calculate_customer_cost(
        self, 
        customer_id: int, 
        consumption_date: date
    ) -> CustomerCalcResult:
        """计算单个客户的消耗费用"""
        # 1. 查询当日订单（按设备类型+楼层类型分组）
        order_groups = await self._get_order_groups(customer_id, consumption_date)
        
        # 2. 查询客户生效中的计费规则
        pricing_rule = await self._get_active_pricing_rule(customer_id)
        
        has_rule = pricing_rule is not None
        
        # 3. 计算费用
        for group in order_groups:
            if has_rule:
                cost = self._calculate_cost(group, pricing_rule)
            else:
                cost = Decimal('0')
            
            # 4. 写入 daily_consumption
            consumption = DailyConsumption(
                customer_id=customer_id,
                consumption_date=consumption_date,
                device_type=group['device_type'],
                layer_type=group['layer_type'],
                order_count=group['order_count'],
                total_cost=cost,
                pricing_rule_id=pricing_rule.id if pricing_rule else None,
                has_pricing_rule=has_rule
            )
            self.db.add(consumption)
        
        await self.db.commit()
        
        return CustomerCalcResult(has_rule=has_rule)
    
    def _calculate_cost(
        self, 
        order_group: dict, 
        pricing_rule: PricingRule
    ) -> Decimal:
        """根据计费规则计算费用"""
        quantity = order_group['total_floor_count']
        
        if pricing_rule.pricing_type == 'fixed':
            return self._calc_fixed(quantity, pricing_rule.unit_price)
        
        elif pricing_rule.pricing_type == 'tiered':
            return self._calc_tiered(quantity, pricing_rule)
        
        elif pricing_rule.pricing_type == 'package':
            return self._calc_package(pricing_rule.base_fee)
        
        else:
            logger.error(f"Unknown pricing_type: {pricing_rule.pricing_type}")
            return Decimal('0')
    
    def _calc_fixed(self, quantity: int, unit_price: Decimal) -> Decimal:
        """定价结算：数量 × 单价"""
        return Decimal(quantity) * unit_price
    
    def _calc_tiered(self, quantity: int, pricing_rule: PricingRule) -> Decimal:
        """阶梯结算：按区间累加"""
        tiers = sorted(pricing_rule.tiers, key=lambda t: t.min_quantity)
        total_cost = Decimal('0')
        remaining = quantity
        
        for tier in tiers:
            if remaining <= 0:
                break
            
            tier_range = tier.max_quantity - tier.min_quantity
            tier_quantity = min(remaining, tier_range)
            total_cost += Decimal(tier_quantity) * tier.unit_price
            remaining -= tier_quantity
        
        return total_cost.quantize(Decimal('0.01'))
    
    def _calc_package(self, base_fee: Decimal) -> Decimal:
        """包年结算：按日分摊"""
        return (base_fee / Decimal('365')).quantize(Decimal('0.01'))
    
    async def _get_customers_with_orders(self, consumption_date: date) -> list[int]:
        """查询指定日期有订单的客户 ID 列表（去重）"""
        result = await self.db.execute(
            select(DailyOrder.customer_id).where(
                DailyOrder.create_date == consumption_date,
                DailyOrder.customer_id.isnot(None)
            ).distinct()
        )
        return [row[0] for row in result.all()]
    
    async def _get_order_groups(
        self, customer_id: int, consumption_date: date
    ) -> list[dict]:
        """
        查询客户当日订单，按设备类型+楼层类型分组
        
        layer_type 推导规则：
        - floor_count == 1 → 'single'
        - floor_count > 1  → 'multi'
        - floor_count NULL → 'single'（默认）
        """
        result = await self.db.execute(
            select(
                DailyOrder.device_type,
                DailyOrder.floor_count,
                func.count(DailyOrder.id).label('order_count'),
                func.coalesce(func.sum(DailyOrder.floor_count), 0).label('total_floor_count')
            ).where(
                DailyOrder.customer_id == customer_id,
                DailyOrder.create_date == consumption_date
            ).group_by(DailyOrder.device_type, DailyOrder.floor_count)
        )
        
        groups = []
        for row in result.all():
            floor_count = row.floor_count or 1
            layer_type = 'single' if floor_count <= 1 else 'multi'
            groups.append({
                'device_type': row.device_type,
                'layer_type': layer_type,
                'order_count': row.order_count,
                'total_floor_count': row.total_floor_count
            })
        
        return groups
    
    async def _get_active_pricing_rule(
        self, customer_id: int
    ) -> Optional[PricingRule]:
        """查询客户当前生效中的计费规则"""
        today = date.today()
        result = await self.db.execute(
            select(PricingRule).where(
                PricingRule.customer_id == customer_id,
                PricingRule.status == 'active',
                PricingRule.start_date <= today,
                (PricingRule.end_date >= today) | (PricingRule.end_date.is_(None))
            ).order_by(PricingRule.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

---

## 4. 定时任务设计

### 4.1 订单同步任务

```python
# backend/app/tasks/order_sync.py

@scheduler.task("cron", hour=1, minute=0, id="sync_daily_orders")
async def sync_daily_orders():
    """每日 01:00 同步订单数据"""
    sync_date = date.today() - timedelta(days=1)
    
    logger.info(f"Starting order sync for {sync_date}")
    
    async with get_db_session() as db:
        service = OrderSyncService(db)
        
        try:
            result = await service.sync_orders(sync_date)
            
            # 记录同步日志
            log = SyncTaskLog(
                task_type="order_sync",
                status="success" if result.failed == 0 else "partial",
                total_count=result.success + result.failed,
                success_count=result.success,
                failed_count=result.failed,
                skipped_count=result.skipped,
                error_message=f"Unmatched orders: {result.unmatched}" if result.unmatched else None
            )
            db.add(log)
            await db.commit()
            
            logger.info(f"Order sync completed: {result}")
            
        except Exception as e:
            logger.error(f"Order sync failed: {e}")
            
            # 记录失败日志
            log = SyncTaskLog(
                task_type="order_sync",
                status="failed",
                error_message=str(e)
            )
            db.add(log)
            await db.commit()
            
            # 发送告警通知
            await send_alert(f"订单同步失败: {e}")
```

### 4.2 费用计算任务

```python
# backend/app/tasks/cost_calc.py

@scheduler.task("cron", hour=1, minute=30, id="calc_daily_cost")
async def calc_daily_cost():
    """每日 01:30 计算消耗费用"""
    consumption_date = date.today() - timedelta(days=1)
    
    logger.info(f"Starting cost calculation for {consumption_date}")
    
    async with get_db_session() as db:
        service = CostCalcService(db)
        
        try:
            result = await service.calculate_daily_cost(consumption_date)
            
            # 记录计算日志
            log = SyncTaskLog(
                task_type="cost_calc",
                status="success",
                total_count=result.total_customers,
                success_count=result.calculated,
                failed_count=0,
                error_message=f"No pricing rule: {result.no_rule}" if result.no_rule else None
            )
            db.add(log)
            await db.commit()
            
            logger.info(f"Cost calculation completed: {result}")
            
        except Exception as e:
            logger.error(f"Cost calculation failed: {e}")
            
            log = SyncTaskLog(
                task_type="cost_calc",
                status="failed",
                error_message=str(e)
            )
            db.add(log)
            await db.commit()
            
            await send_alert(f"费用计算失败: {e}")
```

---

## 5. API 接口设计

### 5.1 消耗趋势 API 增强

```python
# backend/app/routes/analytics.py

@router.get("/consumption/trend")
async def get_consumption_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    keyword: Optional[str] = None,
    metric: str = "cost",  # cost | order_count
    db: AsyncSession = Depends(get_db)
):
    """获取消耗趋势数据"""
    # 默认时间范围：最近 30 天
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # 构建查询
    query = select(
        DailyConsumption.consumption_date,
        func.sum(DailyConsumption.order_count).label('order_count'),
        func.sum(DailyConsumption.total_cost).label('cost')
    ).where(
        DailyConsumption.consumption_date >= start_date,
        DailyConsumption.consumption_date <= end_date
    )
    
    if keyword:
        query = query.join(Customer).where(
            Customer.name.ilike(f"%{keyword}%")
        )
    
    query = query.group_by(DailyConsumption.consumption_date).order_by(
        DailyConsumption.consumption_date
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    # 根据 metric 返回对应数据
    data = []
    for row in rows:
        item = {
            "date": row.consumption_date.isoformat(),
            "order_count": row.order_count,
            "cost": float(row.cost)
        }
        # 前端根据 metric 选择显示字段
        data.append(item)
    
    return {"code": 0, "data": data}
```

### 5.2 设备分布 API 增强

```python
@router.get("/consumption/device-distribution")
async def get_device_distribution(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    keyword: Optional[str] = None,
    metric: str = "cost",
    db: AsyncSession = Depends(get_db)
):
    """获取设备类型分布"""
    # 默认时间范围：最近 30 天
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    query = select(
        DailyConsumption.device_type,
        func.sum(DailyConsumption.order_count).label('order_count'),
        func.sum(DailyConsumption.total_cost).label('cost')
    ).where(
        DailyConsumption.consumption_date >= start_date,
        DailyConsumption.consumption_date <= end_date
    )
    
    if keyword:
        query = query.join(Customer).where(
            Customer.name.ilike(f"%{keyword}%")
        )
    
    query = query.group_by(DailyConsumption.device_type)
    
    result = await db.execute(query)
    rows = result.all()
    
    data = []
    for row in rows:
        data.append({
            "device_type": row.device_type,
            "order_count": row.order_count,
            "cost": float(row.cost)
        })
    
    return {"code": 0, "data": data}
```

### 5.3 Top10 API 增强

```python
@router.get("/consumption/top")
async def get_top_customers(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 10,
    metric: str = "cost",
    db: AsyncSession = Depends(get_db)
):
    """获取 Top10 客户"""
    # 默认时间范围：最近 30 天
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    query = select(
        Customer.id,
        Customer.name,
        func.sum(DailyConsumption.order_count).label('order_count'),
        func.sum(DailyConsumption.total_cost).label('cost')
    ).join(DailyConsumption).where(
        DailyConsumption.consumption_date >= start_date,
        DailyConsumption.consumption_date <= end_date
    ).group_by(Customer.id, Customer.name)
    
    # 根据 metric 排序
    if metric == "order_count":
        query = query.order_by(desc('order_count'))
    else:
        query = query.order_by(desc('cost'))
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    data = []
    for row in rows:
        data.append({
            "customer_id": row.id,
            "customer_name": row.name,
            "order_count": row.order_count,
            "cost": float(row.cost)
        })
    
    return {"code": 0, "data": data}
```

### 5.4 手动同步 API

```python
@router.post("/consumption/sync")
async def manual_sync_orders(
    background_tasks: BackgroundTasks,
    sync_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """手动触发订单同步"""
    # 权限检查：仅管理员可调用
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can trigger sync")
    
    if not sync_date:
        sync_date = date.today() - timedelta(days=1)
    
    # 检查是否已同步
    existing = await db.execute(
        select(DailyOrder).where(DailyOrder.sync_date == sync_date).limit(1)
    )
    if existing.scalar_one_or_none():
        return {
            "code": 0,
            "message": "Already synced",
            "data": {"status": "skipped", "date": sync_date.isoformat()}
        }
    
    # 异步执行同步
    background_tasks.add_task(_run_sync, sync_date)
    
    return {
        "code": 0,
        "message": "Sync task started",
        "data": {"status": "running", "date": sync_date.isoformat()}
    }

async def _run_sync(sync_date: date):
    """后台执行同步任务"""
    async with get_db_session() as db:
        service = OrderSyncService(db)
        await service.sync_orders(sync_date)
```

---

## 6. 前端设计

### 6.1 消耗趋势图切换

```typescript
// frontend/src/views/analytics/Consumption.vue

const metricMode = ref<'cost' | 'order_count'>('cost');

const fetchTrendData = async () => {
  const res = await analyticsApi.getConsumptionTrend({
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
    metric: metricMode.value
  });
  
  trendData.value = res.data.map(item => ({
    date: item.date,
    value: metricMode.value === 'cost' ? item.cost : item.order_count
  }));
};

const toggleMetric = (mode: 'cost' | 'order_count') => {
  metricMode.value = mode;
  fetchTrendData();
};
```

### 6.2 设备分布切换

```typescript
const deviceMetricMode = ref<'cost' | 'order_count'>('cost');

const fetchDeviceDistribution = async () => {
  const res = await analyticsApi.getDeviceDistribution({
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
    metric: deviceMetricMode.value
  });
  
  deviceData.value = res.data.map(item => ({
    name: item.device_type,
    value: deviceMetricMode.value === 'cost' ? item.cost : item.order_count
  }));
};
```

### 6.3 Top10 切换

```typescript
const topMetricMode = ref<'cost' | 'order_count'>('cost');

const fetchTopCustomers = async () => {
  const res = await analyticsApi.getTopCustomers({
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
    limit: 10,
    metric: topMetricMode.value
  });
  
  topData.value = res.data;
};
```

---

## 7. 错误处理

### 7.1 外部 MySQL 连接失败

- **现象**: 连接超时或认证失败
- **处理**: 重试 3 次（指数退避），失败后记录日志并告警
- **恢复**: 下次定时任务自动重试

### 7.2 客户匹配失败

- **现象**: `group_type` 在系统中找不到对应客户
- **处理**: 记录 `customer_id = NULL`，写入 `unmatched` 列表
- **恢复**: 人工在管理后台处理未匹配订单

### 7.3 计费规则不存在

- **现象**: 客户没有生效中的 `PricingRule`
- **处理**: `has_pricing_rule = false`，`total_cost = 0`
- **恢复**: 人工配置计费规则后重新计算

### 7.4 费用计算异常

- **现象**: 计费规则配置错误导致计算异常
- **处理**: 捕获异常，记录日志，跳过该客户
- **恢复**: 修正计费规则后手动触发重新计算

---

## 8. 测试策略

### 8.1 单元测试

- **OrderSyncService**: mock 外部 MySQL，测试同步逻辑
- **CostCalcService**: mock 数据库，测试费用计算逻辑
- **API 接口**: 测试参数校验、权限检查、响应格式

### 8.2 集成测试

- **订单同步**: 连接测试环境的外部 MySQL，验证数据写入
- **费用计算**: 创建测试客户和计费规则，验证计算结果
- **定时任务**: 验证任务调度、日志记录、告警通知

### 8.3 性能测试

- **大量订单同步**: 测试 10000+ 订单的同步性能
- **并发计算**: 测试多客户并发费用计算的性能
- **查询性能**: 测试大数据量下的 API 响应时间

---

## 9. 部署计划

### 9.1 数据库迁移

```bash
# 创建新表
alembic revision --autogenerate -m "Add daily_orders and daily_consumption tables"
alembic upgrade head
```

### 9.2 配置更新

```python
# backend/app/config.py

class Settings(BaseSettings):
    # 外部 MySQL 连接（加密存储）
    external_mysql_url: str = Field(..., env="EXTERNAL_MYSQL_URL")
```

### 9.3 环境变量

```bash
# .env
EXTERNAL_MYSQL_URL=mysql+aiomysql://readonly_user:password@rm-uf699j4t96r5u634n.mysql.rds.aliyuncs.com:3306/3dnest_engine_new
```

### 9.4 上线步骤

1. 执行数据库迁移
2. 配置环境变量
3. 部署后端服务
4. 验证定时任务注册
5. 手动触发一次同步测试
6. 部署前端服务
7. 验证页面功能

---

## 10. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 外部 MySQL 连接不稳定 | 同步失败 | 重试机制 + 告警通知 |
| 客户匹配率低 | 数据不完整 | 人工处理未匹配订单 |
| 计费规则配置错误 | 费用计算异常 | 异常捕获 + 人工修正 |
| 大数据量查询慢 | API 响应慢 | 添加索引 + 分页查询 |

---

## 附录

### A. 外部 MySQL 查询 SQL

```sql
SELECT 
    id,
    custom_code,
    nest_id,
    company_name,
    group_type,
    create_date,
    floor_count,
    device_type
FROM 3dnest_engine_new.nest_model_order
WHERE DATE(create_date) = :date
```

### B. 计费规则计算示例

**定价结算**:
- 订单数量: 100 层
- 单价: ¥10/层
- 费用: 100 × 10 = ¥1000

**阶梯结算**:
- 订单数量: 1500 层
- 阶梯 1 (0-1000): ¥10/层 → 1000 × 10 = ¥10000
- 阶梯 2 (1001-5000): ¥8/层 → 500 × 8 = ¥4000
- 费用: 10000 + 4000 = ¥14000

**包年结算**:
- 包年费用: ¥365000/年
- 日费用: 365000 / 365 = ¥1000/日
