# 消耗分析页面增强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现每日订单同步和费用计算功能，增强消耗分析页面支持订单数量和结算费用双维度切换

**Architecture:** 采用独立同步服务架构，OrderSyncService 负责从外部 MySQL 同步订单数据，CostCalcService 负责根据计费规则计算每日费用。使用 SQLAlchemy 异步引擎和连接池管理外部数据库连接。

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (async), aiomysql, APScheduler, Vue 3, TypeScript, ECharts

---

## 文件结构

### 新建文件

| 文件路径 | 职责 |
|---------|------|
| `backend/app/models/daily_order.py` | DailyOrder 数据模型 |
| `backend/app/models/daily_consumption.py` | DailyConsumption 数据模型 |
| `backend/app/services/dto.py` | 数据传输对象（SyncResult, CalcResult 等） |
| `backend/app/services/order_sync.py` | 订单同步服务 |
| `backend/app/services/cost_calc.py` | 费用计算服务 |
| `backend/app/tasks/order_sync.py` | 订单同步定时任务 |
| `backend/app/tasks/cost_calc.py` | 费用计算定时任务 |
| `backend/tests/unit/services/test_order_sync.py` | OrderSyncService 单元测试 |
| `backend/tests/unit/services/test_cost_calc.py` | CostCalcService 单元测试 |
| `backend/tests/integration/test_order_sync_integration.py` | 订单同步集成测试 |

### 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `backend/app/models/__init__.py` | 导出新模型 |
| `backend/app/config.py` | 添加 EXTERNAL_MYSQL_URL 配置 |
| `backend/app/tasks/scheduler.py` | 注册新定时任务 |
| `backend/app/routes/analytics.py` | 增强 API 接口支持 metric 参数 |
| `frontend/src/api/analytics.ts` | 更新 API 调用 |
| `frontend/src/views/analytics/Consumption.vue` | 添加视图切换功能 |

---

## Task 1: 创建 DailyOrder 数据模型

**Files:**
- Create: `backend/app/models/daily_order.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 DailyOrder 模型文件**

```python
# backend/app/models/daily_order.py
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base


class DailyOrder(Base):
    """每日订单数据模型"""
    __tablename__ = 'daily_orders'
    
    id = Column(Integer, primary_key=True)
    order_code = Column(String(50), nullable=False, comment='订单 ID（外部系统）')
    custom_code = Column(String(50), comment='房源编号')
    nest_id = Column(String(50), comment='模型编号')
    company_name = Column(String(200), comment='公司名称')
    group_type = Column(String(50), comment='客户 ID（外部系统）')
    customer_id = Column(Integer, ForeignKey('customers.id'), comment='系统客户 ID')
    create_date = Column(Date, nullable=False, comment='订单创建时间')
    floor_count = Column(Integer, comment='楼层数')
    device_type = Column(String(10), comment='设备类型（X/N/L）')
    sync_date = Column(Date, nullable=False, comment='同步日期')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    customer = relationship('Customer', backref='daily_orders')
    
    # 索引
    __table_args__ = (
        Index('idx_daily_orders_customer_date', 'customer_id', 'create_date'),
        Index('idx_daily_orders_sync_date', 'sync_date'),
        UniqueConstraint('order_code', 'create_date', name='uq_order_code_date'),
    )
    
    def __repr__(self):
        return f"<DailyOrder(order_code={self.order_code}, create_date={self.create_date})>"
```

- [ ] **Step 2: 更新 models/__init__.py 导出新模型**

```python
# backend/app/models/__init__.py
# 在文件末尾添加：
from app.models.daily_order import DailyOrder
from app.models.daily_consumption import DailyConsumption

__all__ = [
    # ... 现有导出 ...
    'DailyOrder',
    'DailyConsumption',
]
```

- [ ] **Step 3: 验证模型可以导入**

Run: `cd backend && python -c "from app.models.daily_order import DailyOrder; print('✓ DailyOrder imported')"`
Expected: `✓ DailyOrder imported`

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/daily_order.py backend/app/models/__init__.py
git commit -m "feat: add DailyOrder model for order sync"
```

---

## Task 2: 创建 DailyConsumption 数据模型

**Files:**
- Create: `backend/app/models/daily_consumption.py`

- [ ] **Step 1: 创建 DailyConsumption 模型文件**

```python
# backend/app/models/daily_consumption.py
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base


class DailyConsumption(Base):
    """每日消耗数据模型"""
    __tablename__ = 'daily_consumption'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False, comment='客户 ID')
    consumption_date = Column(Date, nullable=False, comment='消耗日期')
    device_type = Column(String(10), nullable=False, comment='设备类型')
    layer_type = Column(String(20), nullable=False, comment='楼层类型（single/multi）')
    order_count = Column(Integer, nullable=False, default=0, comment='订单数量')
    total_cost = Column(Numeric(12, 2), nullable=False, default=0, comment='结算费用')
    pricing_rule_id = Column(Integer, ForeignKey('pricing_rules.id'), comment='使用的计费规则 ID')
    has_pricing_rule = Column(Boolean, default=True, comment='是否有匹配的计费规则')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    customer = relationship('Customer', backref='daily_consumptions')
    pricing_rule = relationship('PricingRule', backref='daily_consumptions')
    
    # 索引
    __table_args__ = (
        Index('idx_daily_consumption_customer_date', 'customer_id', 'consumption_date'),
        Index('idx_daily_consumption_date', 'consumption_date'),
        UniqueConstraint('customer_id', 'consumption_date', 'device_type', 'layer_type', 
                        name='uq_consumption_unique'),
    )
    
    def __repr__(self):
        return f"<DailyConsumption(customer_id={self.customer_id}, date={self.consumption_date})>"
```

- [ ] **Step 2: 验证模型可以导入**

Run: `cd backend && python -c "from app.models.daily_consumption import DailyConsumption; print('✓ DailyConsumption imported')"`
Expected: `✓ DailyConsumption imported`

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/daily_consumption.py
git commit -m "feat: add DailyConsumption model for cost calculation"
```

---

## Task 3: 创建数据传输对象（DTO）

**Files:**
- Create: `backend/app/services/dto.py`

- [ ] **Step 1: 创建 dto.py 文件**

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

- [ ] **Step 2: 验证可以导入**

Run: `cd backend && python -c "from app.services.dto import SyncResult, CalcResult, CustomerCalcResult; print('✓ DTOs imported')"`
Expected: `✓ DTOs imported`

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/dto.py
git commit -m "feat: add data transfer objects for sync and calc services"
```

---

## Task 4: 添加外部 MySQL 配置

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: 在 Settings 类中添加外部 MySQL 配置**

```python
# backend/app/config.py
# 在 Settings 类中添加：

class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # 外部 MySQL 连接（用于订单同步）
    external_mysql_url: str = Field(
        default="mysql+aiomysql://readonly_user:readonly_password@rm-uf699j4t96r5u634n.mysql.rds.aliyuncs.com:3306/3dnest_engine_new",
        env="EXTERNAL_MYSQL_URL"
    )
```

- [ ] **Step 2: 在 .env 文件中添加配置（如果存在）**

```bash
# .env
EXTERNAL_MYSQL_URL=mysql+aiomysql://readonly_user:readonly_password@rm-uf699j4t96r5u634n.mysql.rds.aliyuncs.com:3306/3dnest_engine_new
```

- [ ] **Step 3: 验证配置可以加载**

Run: `cd backend && python -c "from app.config import settings; print('✓ external_mysql_url:', settings.external_mysql_url[:30])"`
Expected: `✓ external_mysql_url: mysql+aiomysql://readonly_...`

- [ ] **Step 4: 提交**

```bash
git add backend/app/config.py
git commit -m "feat: add external MySQL configuration for order sync"
```

---

## Task 5: 编写 OrderSyncService 单元测试

**Files:**
- Create: `backend/tests/unit/services/test_order_sync.py`

- [ ] **Step 1: 创建测试文件并编写失败测试**

```python
# backend/tests/unit/services/test_order_sync.py
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.order_sync import OrderSyncService
from app.services.dto import SyncResult
from app.models.daily_order import DailyOrder
from app.models.customer import Customer


class TestOrderSyncService:
    """OrderSyncService 单元测试"""
    
    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        db = AsyncMock(spec=AsyncSession)
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        """创建服务实例"""
        with patch('app.services.order_sync.create_async_engine'):
            return OrderSyncService(mock_db)
    
    async def test_check_existing_returns_count(self, service, mock_db):
        """测试 _check_existing 返回已同步记录数"""
        # 模拟查询结果
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result
        
        count = await service._check_existing(date(2026, 6, 12))
        
        assert count == 5
        mock_db.execute.assert_called_once()
    
    async def test_sync_orders_skips_if_already_synced(self, service, mock_db):
        """测试已同步时跳过"""
        # 模拟已存在记录
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        mock_db.execute.return_value = mock_result
        
        result = await service.sync_orders(date(2026, 6, 12))
        
        assert result.skipped == 10
        assert result.message == "Already synced"
    
    async def test_match_customer_by_external_id(self, service, mock_db):
        """测试通过 external_id 匹配客户"""
        # 模拟客户查询
        mock_customer = Customer(id=1, external_id="C001")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer
        mock_db.execute.return_value = mock_result
        
        customer = await service._match_customer("C001")
        
        assert customer is not None
        assert customer.id == 1
        assert customer.external_id == "C001"
    
    async def test_match_customer_returns_none_if_not_found(self, service, mock_db):
        """测试未找到客户时返回 None"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        customer = await service._match_customer("NOT_EXIST")
        
        assert customer is None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/unit/services/test_order_sync.py -v`
Expected: FAIL - "ModuleNotFoundError: No module named 'app.services.order_sync'"

- [ ] **Step 3: 提交失败测试**

```bash
git add backend/tests/unit/services/test_order_sync.py
git commit -m "test: add failing tests for OrderSyncService"
```

---

## Task 6: 实现 OrderSyncService

**Files:**
- Create: `backend/app/services/order_sync.py`

- [ ] **Step 1: 创建 OrderSyncService 实现**

```python
# backend/app/services/order_sync.py
import asyncio
import logging
from datetime import date
from typing import Optional
from decimal import Decimal

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.daily_order import DailyOrder
from app.models.customer import Customer
from app.services.dto import SyncResult

logger = logging.getLogger(__name__)


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
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
    
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
            customer = await self._match_customer(order.get('group_type'))
            
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

- [ ] **Step 2: 运行测试验证通过**

Run: `cd backend && pytest tests/unit/services/test_order_sync.py -v`
Expected: PASS - 4 tests passed

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/order_sync.py
git commit -m "feat: implement OrderSyncService with retry mechanism"
```

---

## Task 7: 编写 CostCalcService 单元测试

**Files:**
- Create: `backend/tests/unit/services/test_cost_calc.py`

- [ ] **Step 1: 创建测试文件并编写失败测试**

```python
# backend/tests/unit/services/test_cost_calc.py
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.services.cost_calc import CostCalcService
from app.services.dto import CalcResult
from app.models.pricing_rule import PricingRule


class TestCostCalcService:
    """CostCalcService 单元测试"""
    
    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_db):
        """创建服务实例"""
        return CostCalcService(mock_db)
    
    def test_calc_fixed(self, service):
        """测试定价结算"""
        result = service._calc_fixed(100, Decimal('10.00'))
        assert result == Decimal('1000.00')
    
    def test_calc_tiered_single_tier(self, service):
        """测试阶梯结算 - 单阶梯"""
        rule = MagicMock(spec=PricingRule)
        rule.tiers = [
            MagicMock(min_quantity=0, max_quantity=1000, unit_price=Decimal('10.00'))
        ]
        
        result = service._calc_tiered(500, rule)
        assert result == Decimal('5000.00')
    
    def test_calc_tiered_multiple_tiers(self, service):
        """测试阶梯结算 - 多阶梯"""
        rule = MagicMock(spec=PricingRule)
        rule.tiers = [
            MagicMock(min_quantity=0, max_quantity=1000, unit_price=Decimal('10.00')),
            MagicMock(min_quantity=1000, max_quantity=5000, unit_price=Decimal('8.00'))
        ]
        
        result = service._calc_tiered(1500, rule)
        # 1000 * 10 + 500 * 8 = 10000 + 4000 = 14000
        assert result == Decimal('14000.00')
    
    def test_calc_package(self, service):
        """测试包年结算 - 按日分摊"""
        result = service._calc_package(Decimal('365000.00'))
        # 365000 / 365 = 1000
        assert result == Decimal('1000.00')
    
    def test_calc_package_with_remainder(self, service):
        """测试包年结算 - 有余数"""
        result = service._calc_package(Decimal('1000.00'))
        # 1000 / 365 = 2.739... → 2.74
        assert result == Decimal('2.74')
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/unit/services/test_cost_calc.py -v`
Expected: FAIL - "ModuleNotFoundError: No module named 'app.services.cost_calc'"

- [ ] **Step 3: 提交失败测试**

```bash
git add backend/tests/unit/services/test_cost_calc.py
git commit -m "test: add failing tests for CostCalcService"
```

---

## Task 8: 实现 CostCalcService

**Files:**
- Create: `backend/app/services/cost_calc.py`

- [ ] **Step 1: 创建 CostCalcService 实现**

```python
# backend/app/services/cost_calc.py
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_order import DailyOrder
from app.models.daily_consumption import DailyConsumption
from app.models.pricing_rule import PricingRule
from app.services.dto import CalcResult, CustomerCalcResult

logger = logging.getLogger(__name__)


class CostCalcService:
    """费用计算服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
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
    
    async def _get_customers_with_orders(self, consumption_date: date) -> list[int]:
        """查询指定日期有订单的客户 ID 列表（去重）"""
        result = await self.db.execute(
            select(DailyOrder.customer_id).where(
                DailyOrder.create_date == consumption_date,
                DailyOrder.customer_id.isnot(None)
            ).distinct()
        )
        return [row[0] for row in result.all()]
    
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
```

- [ ] **Step 2: 运行测试验证通过**

Run: `cd backend && pytest tests/unit/services/test_cost_calc.py -v`
Expected: PASS - 5 tests passed

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/cost_calc.py
git commit -m "feat: implement CostCalcService with three pricing modes"
```

---

## Task 9: 创建订单同步定时任务

**Files:**
- Create: `backend/app/tasks/order_sync.py`
- Modify: `backend/app/tasks/scheduler.py`

- [ ] **Step 1: 创建订单同步定时任务**

```python
# backend/app/tasks/order_sync.py
import logging
from datetime import date, timedelta

from app.database import get_db_session
from app.models.sync_task_log import SyncTaskLog
from app.services.order_sync import OrderSyncService
from app.utils.alert import send_alert

logger = logging.getLogger(__name__)


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
            
            logger.info(f"Order sync completed: success={result.success}, failed={result.failed}, skipped={result.skipped}")
            
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

- [ ] **Step 2: 在 scheduler.py 中注册任务**

```python
# backend/app/tasks/scheduler.py
# 在 register_tasks() 函数中添加：

from app.tasks.order_sync import sync_daily_orders
from app.tasks.cost_calc import calc_daily_cost

def register_tasks():
    # ... 现有任务 ...
    
    # 订单同步：每日 01:00
    scheduler.add_job(
        sync_daily_orders,
        "cron",
        hour=1,
        minute=0,
        id="sync_daily_orders",
        name="每日订单同步"
    )
    
    # 费用计算：每日 01:30
    scheduler.add_job(
        calc_daily_cost,
        "cron",
        hour=1,
        minute=30,
        id="calc_daily_cost",
        name="每日费用计算"
    )
```

- [ ] **Step 3: 验证任务可以注册**

Run: `cd backend && python -c "from app.tasks.scheduler import register_tasks; register_tasks(); print('✓ Tasks registered')"`
Expected: `✓ Tasks registered`

- [ ] **Step 4: 提交**

```bash
git add backend/app/tasks/order_sync.py backend/app/tasks/scheduler.py
git commit -m "feat: add order sync scheduled task at 01:00 daily"
```

---

## Task 10: 创建费用计算定时任务

**Files:**
- Create: `backend/app/tasks/cost_calc.py`

- [ ] **Step 1: 创建费用计算定时任务**

```python
# backend/app/tasks/cost_calc.py
import logging
from datetime import date, timedelta

from app.database import get_db_session
from app.models.sync_task_log import SyncTaskLog
from app.services.cost_calc import CostCalcService
from app.utils.alert import send_alert

logger = logging.getLogger(__name__)


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
            
            logger.info(f"Cost calculation completed: total={result.total_customers}, calculated={result.calculated}, no_rule={result.no_rule}")
            
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

- [ ] **Step 2: 验证任务可以导入**

Run: `cd backend && python -c "from app.tasks.cost_calc import calc_daily_cost; print('✓ calc_daily_cost imported')"`
Expected: `✓ calc_daily_cost imported`

- [ ] **Step 3: 提交**

```bash
git add backend/app/tasks/cost_calc.py
git commit -m "feat: add cost calculation scheduled task at 01:30 daily"
```

---

## Task 11: 增强消耗趋势 API

**Files:**
- Modify: `backend/app/routes/analytics.py`

- [ ] **Step 1: 修改 get_consumption_trend 接口支持 metric 参数**

```python
# backend/app/routes/analytics.py
# 找到 get_consumption_trend 函数，修改为：

@router.get("/consumption/trend")
async def get_consumption_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    keyword: Optional[str] = None,
    metric: str = "cost",  # 新增参数：cost | order_count
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
    
    # 返回包含 order_count 和 cost 的数据
    data = []
    for row in rows:
        data.append({
            "date": row.consumption_date.isoformat(),
            "order_count": row.order_count,
            "cost": float(row.cost)
        })
    
    return {"code": 0, "data": data}
```

- [ ] **Step 2: 验证 API 可以启动**

Run: `cd backend && python -c "from app.routes.analytics import get_consumption_trend; print('✓ API imported')"`
Expected: `✓ API imported`

- [ ] **Step 3: 提交**

```bash
git add backend/app/routes/analytics.py
git commit -m "feat: enhance consumption trend API with metric parameter"
```

---

## Task 12: 增强设备分布 API

**Files:**
- Modify: `backend/app/routes/analytics.py`

- [ ] **Step 1: 修改 get_device_distribution 接口支持 metric 参数**

```python
# backend/app/routes/analytics.py
# 找到 get_device_distribution 函数，修改为：

@router.get("/consumption/device-distribution")
async def get_device_distribution(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    keyword: Optional[str] = None,
    metric: str = "cost",  # 新增参数
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

- [ ] **Step 2: 提交**

```bash
git add backend/app/routes/analytics.py
git commit -m "feat: enhance device distribution API with metric parameter"
```

---

## Task 13: 增强 Top10 API

**Files:**
- Modify: `backend/app/routes/analytics.py`

- [ ] **Step 1: 修改 get_top_customers 接口支持 metric 参数**

```python
# backend/app/routes/analytics.py
# 找到 get_top_customers 函数，修改为：

@router.get("/consumption/top")
async def get_top_customers(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 10,
    metric: str = "cost",  # 新增参数
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

- [ ] **Step 2: 提交**

```bash
git add backend/app/routes/analytics.py
git commit -m "feat: enhance top customers API with metric parameter"
```

---

## Task 14: 添加手动同步 API

**Files:**
- Modify: `backend/app/routes/analytics.py`

- [ ] **Step 1: 添加手动同步接口**

```python
# backend/app/routes/analytics.py
# 在文件末尾添加：

from fastapi import BackgroundTasks, HTTPException
from app.services.order_sync import OrderSyncService
from app.models.daily_order import DailyOrder
from app.auth import get_current_user
from app.models.user import User

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
    async def _run_sync(sync_date: date):
        async with get_db_session() as db:
            service = OrderSyncService(db)
            await service.sync_orders(sync_date)
    
    background_tasks.add_task(_run_sync, sync_date)
    
    return {
        "code": 0,
        "message": "Sync task started",
        "data": {"status": "running", "date": sync_date.isoformat()}
    }
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/routes/analytics.py
git commit -m "feat: add manual sync API for admin users"
```

---

## Task 15: 生成数据库迁移

**Files:**
- Create: `backend/alembic/versions/xxxx_add_daily_orders_and_consumption.py`

- [ ] **Step 1: 生成迁移文件**

Run: `cd backend && alembic revision --autogenerate -m "Add daily_orders and daily_consumption tables"`
Expected: 生成迁移文件

- [ ] **Step 2: 检查迁移文件内容**

Run: `cd backend && ls -la alembic/versions/ | grep daily`
Expected: 显示新生成的迁移文件

- [ ] **Step 3: 执行迁移**

Run: `cd backend && alembic upgrade head`
Expected: `INFO  [alembic] Running upgrade xxxx -> yyyy, Add daily_orders and daily_consumption tables`

- [ ] **Step 4: 验证表已创建**

Run: `cd backend && python -c "from app.database import engine; from sqlalchemy import inspect; inspector = inspect(engine); print('Tables:', [t for t in inspector.get_table_names() if 'daily' in t])"`
Expected: `Tables: ['daily_orders', 'daily_consumption']`

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/
git commit -m "migration: add daily_orders and daily_consumption tables"
```

---

## Task 16: 更新前端 API 调用

**Files:**
- Modify: `frontend/src/api/analytics.ts`

- [ ] **Step 1: 更新 API 接口定义**

```typescript
// frontend/src/api/analytics.ts
// 找到相关接口，添加 metric 参数：

export interface TrendParams {
  start_date?: string;
  end_date?: string;
  keyword?: string;
  metric?: 'cost' | 'order_count';  // 新增
}

export interface DeviceDistributionParams {
  start_date?: string;
  end_date?: string;
  keyword?: string;
  metric?: 'cost' | 'order_count';  // 新增
}

export interface TopCustomersParams {
  start_date?: string;
  end_date?: string;
  limit?: number;
  metric?: 'cost' | 'order_count';  // 新增
}

export interface TrendItem {
  date: string;
  order_count: number;  // 新增
  cost: number;
}

export interface DeviceDistributionItem {
  device_type: string;
  order_count: number;  // 新增
  cost: number;
}

export interface TopCustomerItem {
  customer_id: number;
  customer_name: string;
  order_count: number;  // 新增
  cost: number;
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/analytics.ts
git commit -m "feat: update frontend API types with metric parameter"
```

---

## Task 17: 前端消耗趋势图添加视图切换

**Files:**
- Modify: `frontend/src/views/analytics/Consumption.vue`

- [ ] **Step 1: 添加视图切换状态和逻辑**

```vue
<!-- frontend/src/views/analytics/Consumption.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { analyticsApi } from '@/api/analytics';

// 添加视图模式状态
const trendMetricMode = ref<'cost' | 'order_count'>('cost');

// 修改 fetchTrendData 函数
const fetchTrendData = async () => {
  const res = await analyticsApi.getConsumptionTrend({
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
    metric: trendMetricMode.value
  });
  
  trendData.value = res.data.map(item => ({
    date: item.date,
    value: trendMetricMode.value === 'cost' ? item.cost : item.order_count
  }));
};

// 添加切换函数
const toggleTrendMetric = (mode: 'cost' | 'order_count') => {
  trendMetricMode.value = mode;
  fetchTrendData();
};
</script>

<template>
  <!-- 在消耗趋势图卡片标题区域添加切换按钮 -->
  <a-card title="消耗趋势">
    <template #extra>
      <a-radio-group 
        v-model="trendMetricMode" 
        type="button" 
        size="small"
        @change="toggleTrendMetric"
      >
        <a-radio value="cost">结算费用</a-radio>
        <a-radio value="order_count">订单数量</a-radio>
      </a-radio-group>
    </template>
    
    <!-- 图表组件 -->
    <TrendChart :data="trendData" :metric="trendMetricMode" />
  </a-card>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/analytics/Consumption.vue
git commit -m "feat: add metric toggle for consumption trend chart"
```

---

## Task 18: 前端设备分布图添加视图切换

**Files:**
- Modify: `frontend/src/views/analytics/Consumption.vue`

- [ ] **Step 1: 添加设备分布视图切换**

```vue
<!-- frontend/src/views/analytics/Consumption.vue -->
<script setup lang="ts">
// 添加设备分布视图模式状态
const deviceMetricMode = ref<'cost' | 'order_count'>('cost');

// 修改 fetchDeviceDistribution 函数
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

// 添加切换函数
const toggleDeviceMetric = (mode: 'cost' | 'order_count') => {
  deviceMetricMode.value = mode;
  fetchDeviceDistribution();
};
</script>

<template>
  <!-- 在设备分布图卡片标题区域添加切换按钮 -->
  <a-card title="设备类型分布">
    <template #extra>
      <a-radio-group 
        v-model="deviceMetricMode" 
        type="button" 
        size="small"
        @change="toggleDeviceMetric"
      >
        <a-radio value="cost">结算费用</a-radio>
        <a-radio value="order_count">订单数量</a-radio>
      </a-radio-group>
    </template>
    
    <!-- 饼图组件 -->
    <DevicePieChart :data="deviceData" :metric="deviceMetricMode" />
  </a-card>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/analytics/Consumption.vue
git commit -m "feat: add metric toggle for device distribution chart"
```

---

## Task 19: 前端 Top10 排行榜添加视图切换

**Files:**
- Modify: `frontend/src/views/analytics/Consumption.vue`

- [ ] **Step 1: 添加 Top10 视图切换**

```vue
<!-- frontend/src/views/analytics/Consumption.vue -->
<script setup lang="ts">
// 添加 Top10 视图模式状态
const topMetricMode = ref<'cost' | 'order_count'>('cost');

// 修改 fetchTopCustomers 函数
const fetchTopCustomers = async () => {
  const res = await analyticsApi.getTopCustomers({
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
    limit: 10,
    metric: topMetricMode.value
  });
  
  topData.value = res.data;
};

// 添加切换函数
const toggleTopMetric = (mode: 'cost' | 'order_count') => {
  topMetricMode.value = mode;
  fetchTopCustomers();
};
</script>

<template>
  <!-- 在 Top10 卡片标题区域添加切换按钮 -->
  <a-card title="Top10 客户排行">
    <template #extra>
      <a-radio-group 
        v-model="topMetricMode" 
        type="button" 
        size="small"
        @change="toggleTopMetric"
      >
        <a-radio value="cost">结算费用</a-radio>
        <a-radio value="order_count">订单数量</a-radio>
      </a-radio-group>
    </template>
    
    <!-- 排行榜组件 -->
    <TopCustomersList :data="topData" :metric="topMetricMode" />
  </a-card>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/analytics/Consumption.vue
git commit -m "feat: add metric toggle for top 10 customers list"
```

---

## Task 20: 运行完整测试套件

- [ ] **Step 1: 运行后端单元测试**

Run: `cd backend && pytest tests/unit/services/test_order_sync.py tests/unit/services/test_cost_calc.py -v`
Expected: All tests passed

- [ ] **Step 2: 运行集成测试（如果存在）**

Run: `cd backend && pytest tests/integration/test_order_sync_integration.py -v`
Expected: Tests passed (or skipped if no external MySQL available)

- [ ] **Step 3: 验证后端服务可以启动**

Run: `cd backend && timeout 5 python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 || true`
Expected: Server starts without errors

- [ ] **Step 4: 验证前端可以构建**

Run: `cd frontend && npm run build`
Expected: Build completed successfully

- [ ] **Step 5: 提交最终验证**

```bash
git add .
git commit -m "test: verify all tests pass and services start correctly"
```

---

## 完成标准

- [ ] 所有 20 个任务已完成
- [ ] 后端单元测试全部通过
- [ ] 数据库迁移成功执行
- [ ] 后端服务可以正常启动
- [ ] 前端可以正常构建
- [ ] 定时任务已注册（01:00 订单同步，01:30 费用计算）
- [ ] API 接口支持 metric 参数切换
- [ ] 前端页面支持订单数量/结算费用双视图切换

---

## 后续步骤

计划已完成并保存到 `docs/superpowers/plans/2026-06-13-consumption-analysis-enhancement.md`。

**两种执行方式：**

1. **Subagent-Driven（推荐）** - 每个任务分派一个独立子代理，任务间进行审查，快速迭代

2. **Inline Execution** - 在当前会话中使用 executing-plans 执行，批量执行并设置检查点

**选择哪种方式？**
