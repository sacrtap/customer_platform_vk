# 消费分析数据同步优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将消费分析数据同步功能从同步全量模式升级为异步周期选择模式，支持双模式（仅补充/强制覆盖）、实时进度反馈、操作审计。

**Architecture:** 新建 `sync_tasks` 表存储任务元数据，扩展现有 `sync_task_logs` 表添加审计字段。使用 Sanic 后台任务异步执行，Redis Hash 存储实时进度，前端每 2 秒轮询更新。

**Tech Stack:** Python 3.12 + Sanic + SQLAlchemy + PostgreSQL + Redis + Vue 3 + TypeScript + Arco Design

## Global Constraints

- 数据库事务：所有修改操作必须在事务中执行
- 并发安全：余额扣款使用行级锁 (FOR UPDATE)
- 权限校验：所有 API 端点必须添加 `@auth_required` 装饰器
- 测试命令：直接使用 `pytest tests/ -v`（不用 `python -m pytest`）
- 代码规范：`ruff` line-length=100，所有函数必须有类型注解
- 前端规范：禁止 `any`，`strict: true`，组件 `PascalCase`

---

## 文件结构

### 新建文件

**后端：**
- `backend/app/models/sync_task.py` — SyncTask 模型定义
- `backend/app/services/sync_task_service.py` — SyncTaskService 业务逻辑
- `backend/app/routes/sync_tasks.py` — /api/v1/sync-tasks 路由
- `backend/migrations/versions/xxxx_add_sync_tasks_table.py` — 数据库迁移脚本
- `backend/tests/services/test_sync_task_service.py` — SyncTaskService 单元测试
- `backend/tests/routes/test_sync_tasks.py` — sync-tasks 路由集成测试

**前端：**
- `frontend/src/views/analytics/components/SyncDialog.vue` — 同步对话框组件
- `frontend/src/views/analytics/components/ProgressView.vue` — 进度展示组件
- `frontend/src/api/syncTasks.ts` — 同步任务 API 调用

### 修改文件

**后端：**
- `backend/app/models/billing.py:173-192` — 扩展 SyncTaskLog 模型（添加 5 个字段）
- `backend/app/routes/sync_logs.py:16-109` — 扩展筛选参数（start_date, end_date, sync_mode, operator_id）
- `backend/app/routes/__init__.py` — 注册新路由
- `backend/app/models/__init__.py` — 导出新模型

**前端：**
- `frontend/src/views/analytics/Consumption.vue:1-100` — 替换同步按钮逻辑，引入 SyncDialog

---

## Task 1: 创建 SyncTask 模型 + 数据库迁移

**Files:**
- Create: `backend/app/models/sync_task.py`
- Create: `backend/migrations/versions/xxxx_add_sync_tasks_table.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: 无
- Produces: `SyncTask` 模型类，包含所有字段定义

- [ ] **Step 1: 创建 SyncTask 模型文件**

```python
# backend/app/models/sync_task.py
"""同步任务模型"""

import uuid
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class SyncTask(BaseModel):
    """同步任务模型"""

    __tablename__ = "sync_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    start_date = Column(Date, nullable=False, comment="同步开始日期")
    end_date = Column(Date, nullable=False, comment="同步结束日期")
    sync_mode = Column(
        String(20),
        nullable=False,
        default="skip_existing",
        comment="同步模式: skip_existing/force_overwrite",
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="任务状态: pending/running/completed/failed",
    )
    total_days = Column(Integer, nullable=False, comment="总天数")
    completed_days = Column(Integer, default=0, comment="已完成天数")
    skipped_days = Column(Integer, default=0, comment="跳过天数")
    current_date = Column(Date, nullable=True, comment="当前处理日期")
    success_count = Column(Integer, default=0, comment="成功同步条数")
    failed_count = Column(Integer, default=0, comment="失败条数")
    error_message = Column(Text, nullable=True, comment="失败原因")
    operator_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, comment="操作人"
    )
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    # 索引
    __table_args__ = (
        Index("idx_sync_tasks_status", "status"),
        Index("idx_sync_tasks_operator", "operator_id"),
        Index("idx_sync_tasks_created", "created_at"),
    )

    def __repr__(self):
        return f"<SyncTask(id={self.id}, status={self.status})>"
```

- [ ] **Step 2: 导出 SyncTask 模型**

```python
# backend/app/models/__init__.py
# 在文件末尾添加
from .sync_task import SyncTask

__all__ = [
    # ... 现有导出
    "SyncTask",
]
```

- [ ] **Step 3: 创建数据库迁移脚本**

```python
# backend/migrations/versions/20260624_add_sync_tasks_table.py
"""add sync_tasks table

Revision ID: 20260624_001
Revises: [previous_revision]
Create Date: 2026-06-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260624_001"
down_revision = "[previous_revision]"  # 需要替换为实际的父 revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 sync_tasks 表
    op.create_table(
        "sync_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "sync_mode",
            sa.String(20),
            nullable=False,
            server_default="skip_existing",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("total_days", sa.Integer(), nullable=False),
        sa.Column("completed_days", sa.Integer(), server_default="0"),
        sa.Column("skipped_days", sa.Integer(), server_default="0"),
        sa.Column("current_date", sa.Date(), nullable=True),
        sa.Column("success_count", sa.Integer(), server_default="0"),
        sa.Column("failed_count", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # 创建索引
    op.create_index("idx_sync_tasks_status", "sync_tasks", ["status"])
    op.create_index("idx_sync_tasks_operator", "sync_tasks", ["operator_id"])
    op.create_index("idx_sync_tasks_created", "sync_tasks", ["created_at"])

    # 创建外键约束
    op.create_foreign_key(
        "fk_sync_tasks_operator_id",
        "sync_tasks",
        "users",
        ["operator_id"],
        ["id"],
    )

    # 扩展 sync_task_logs 表
    op.add_column(
        "sync_task_logs",
        sa.Column(
            "task_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.add_column(
        "sync_task_logs",
        sa.Column("operator_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sync_task_logs",
        sa.Column("start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "sync_task_logs",
        sa.Column("end_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "sync_task_logs",
        sa.Column("sync_mode", sa.String(20), nullable=True),
    )

    # 创建外键约束
    op.create_foreign_key(
        "fk_sync_task_logs_task_id",
        "sync_task_logs",
        "sync_tasks",
        ["task_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_sync_task_logs_operator_id",
        "sync_task_logs",
        "users",
        ["operator_id"],
        ["id"],
    )


def downgrade() -> None:
    # 删除外键约束
    op.drop_constraint("fk_sync_task_logs_operator_id", "sync_task_logs", type_="foreignkey")
    op.drop_constraint("fk_sync_task_logs_task_id", "sync_task_logs", type_="foreignkey")

    # 删除 sync_task_logs 新增字段
    op.drop_column("sync_task_logs", "sync_mode")
    op.drop_column("sync_task_logs", "end_date")
    op.drop_column("sync_task_logs", "start_date")
    op.drop_column("sync_task_logs", "operator_id")
    op.drop_column("sync_task_logs", "task_id")

    # 删除 sync_tasks 表
    op.drop_index("idx_sync_tasks_created", table_name="sync_tasks")
    op.drop_index("idx_sync_tasks_operator", table_name="sync_tasks")
    op.drop_index("idx_sync_tasks_status", table_name="sync_tasks")
    op.drop_table("sync_tasks")
```

- [ ] **Step 4: 运行数据库迁移**

```bash
cd backend
alembic upgrade head
```

Expected: 迁移成功，`sync_tasks` 表创建，`sync_task_logs` 表扩展

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/sync_task.py backend/app/models/__init__.py backend/migrations/versions/20260624_add_sync_tasks_table.py
git commit -m "feat: add SyncTask model and database migration"
```

---

## Task 2: 扩展 SyncTaskLog 模型

**Files:**
- Modify: `backend/app/models/billing.py:173-192`

**Interfaces:**
- Consumes: 无
- Produces: 扩展后的 `SyncTaskLog` 模型

- [ ] **Step 1: 扩展 SyncTaskLog 模型**

```python
# backend/app/models/billing.py:173-192
class SyncTaskLog(BaseModel):
    """同步任务日志表"""

    __tablename__ = "sync_task_logs"

    task_name = Column(String(100), nullable=False, index=True, comment="任务名称")
    status = Column(String(20), nullable=False, comment="任务状态")  # success/partial/failed

    # 统计数据
    total_count = Column(Integer, default=0, comment="总处理数量")
    success_count = Column(Integer, default=0, comment="成功数量")
    failed_count = Column(Integer, default=0, comment="失败数量")
    skipped_count = Column(Integer, default=0, comment="跳过数量")

    # 执行时间
    executed_at = Column(String(50), comment="执行时间")
    duration_seconds = Column(Integer, nullable=True, comment="执行耗时 (秒)")

    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 扩展字段（消费同步审计）
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sync_tasks.id"),
        nullable=True,
        comment="关联任务ID",
    )
    operator_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        comment="操作人",
    )
    start_date = Column(Date, nullable=True, comment="同步开始日期")
    end_date = Column(Date, nullable=True, comment="同步结束日期")
    sync_mode = Column(
        String(20),
        nullable=True,
        comment="同步模式: skip_existing/force_overwrite",
    )
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/models/billing.py
git commit -m "feat: extend SyncTaskLog model with audit fields"
```

---

## Task 3: 实现 SyncTaskService（TDD）

**Files:**
- Create: `backend/app/services/sync_task_service.py`
- Create: `backend/tests/services/test_sync_task_service.py`

**Interfaces:**
- Consumes: `SyncTask` 模型，`OrderSyncService`，`CostCalcService`，Redis 缓存服务
- Produces: `SyncTaskService` 类，包含 `create_task`、`execute_task`、`get_progress`、`get_task` 方法

- [ ] **Step 1: 编写 create_task 测试**

```python
# backend/tests/services/test_sync_task_service.py
"""SyncTaskService 单元测试"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sync_task_service import SyncTaskService
from app.models.sync_task import SyncTask


@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    """模拟 Redis 客户端"""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.hset = AsyncMock()
    redis.expire = AsyncMock()
    redis.delete = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    return redis


@pytest.fixture
def service(mock_db, mock_redis):
    """创建服务实例"""
    return SyncTaskService(db=mock_db, redis_client=mock_redis)


class TestCreateTask:
    """create_task 方法测试"""

    async def test_create_task_success(self, service, mock_db):
        """测试成功创建任务"""
        # 准备
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        sync_mode = "skip_existing"
        operator_id = 1

        # 执行
        task = await service.create_task(
            start_date=start_date,
            end_date=end_date,
            sync_mode=sync_mode,
            operator_id=operator_id,
        )

        # 验证
        assert task is not None
        assert task.start_date == start_date
        assert task.end_date == end_date
        assert task.sync_mode == sync_mode
        assert task.status == "pending"
        assert task.total_days == 8  # 包含起止日期
        assert task.operator_id == operator_id
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_create_task_date_range_exceeded(self, service):
        """测试日期跨度超过31天"""
        # 准备
        start_date = date.today() - timedelta(days=60)
        end_date = date.today()

        # 执行 & 验证
        with pytest.raises(ValueError, match="日期跨度不能超过31天"):
            await service.create_task(
                start_date=start_date,
                end_date=end_date,
                sync_mode="skip_existing",
                operator_id=1,
            )

    async def test_create_task_invalid_date_range(self, service):
        """测试结束日期早于开始日期"""
        # 准备
        start_date = date.today()
        end_date = date.today() - timedelta(days=7)

        # 执行 & 验证
        with pytest.raises(ValueError, match="结束日期不能早于开始日期"):
            await service.create_task(
                start_date=start_date,
                end_date=end_date,
                sync_mode="skip_existing",
                operator_id=1,
            )

    async def test_create_task_lock_conflict(self, service, mock_redis):
        """测试锁冲突"""
        # 准备
        mock_redis.set.return_value = False  # 锁获取失败
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        # 执行 & 验证
        with pytest.raises(Exception, match="已有相同周期的同步任务正在执行"):
            await service.create_task(
                start_date=start_date,
                end_date=end_date,
                sync_mode="skip_existing",
                operator_id=1,
            )
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
pytest tests/services/test_sync_task_service.py::TestCreateTask -v
```

Expected: FAIL（SyncTaskService 未定义）

- [ ] **Step 3: 实现 create_task 方法**

```python
# backend/app/services/sync_task_service.py
"""同步任务服务"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_task import SyncTask
from app.models.billing import SyncTaskLog
from app.services.order_sync import OrderSyncService
from app.services.cost_calc import CostCalcService
from app.cache.base import cache_service

logger = logging.getLogger(__name__)


class SyncTaskService:
    """同步任务服务"""

    def __init__(self, db: AsyncSession, redis_client=None):
        self.db = db
        self.redis_client = redis_client

    async def create_task(
        self,
        start_date: date,
        end_date: date,
        sync_mode: str,
        operator_id: int,
    ) -> SyncTask:
        """创建同步任务"""
        # 校验日期范围
        if end_date < start_date:
            raise ValueError("结束日期不能早于开始日期")

        days_delta = (end_date - start_date).days + 1
        if days_delta > 31:
            raise ValueError("日期跨度不能超过31天")

        # 尝试获取分布式锁
        lock_key = f"sync_lock:{start_date}:{end_date}"
        lock_acquired = await self.redis_client.set(
            lock_key, "1", nx=True, ex=1800  # 30分钟TTL
        )
        if not lock_acquired:
            raise Exception("已有相同周期的同步任务正在执行")

        # 创建任务记录
        task = SyncTask(
            start_date=start_date,
            end_date=end_date,
            sync_mode=sync_mode,
            status="pending",
            total_days=days_delta,
            operator_id=operator_id,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # 写入审计日志
        audit_log = SyncTaskLog(
            task_name="consumption_sync",
            status="pending",
            task_id=task.id,
            operator_id=operator_id,
            start_date=start_date,
            end_date=end_date,
            sync_mode=sync_mode,
        )
        self.db.add(audit_log)
        await self.db.commit()

        # 初始化 Redis 进度
        await self._update_redis_progress(task)

        return task

    async def _update_redis_progress(self, task: SyncTask) -> None:
        """更新 Redis 进度"""
        progress_key = f"sync_progress:{task.id}"
        percentage = int((task.completed_days / task.total_days) * 100) if task.total_days > 0 else 0

        progress_data = {
            "status": task.status,
            "sync_mode": task.sync_mode,
            "total_days": str(task.total_days),
            "completed_days": str(task.completed_days),
            "skipped_days": str(task.skipped_days),
            "current_date": task.current_date.isoformat() if task.current_date else "",
            "success_count": str(task.success_count),
            "failed_count": str(task.failed_count),
            "percentage": str(percentage),
            "error_message": task.error_message or "",
        }

        await self.redis_client.hset(progress_key, mapping=progress_data)
        await self.redis_client.expire(progress_key, 3600)  # 1小时TTL
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend
pytest tests/services/test_sync_task_service.py::TestCreateTask -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/sync_task_service.py backend/tests/services/test_sync_task_service.py
git commit -m "feat: implement SyncTaskService.create_task with TDD"
```

- [ ] **Step 6: 编写 execute_task 测试**

```python
# backend/tests/services/test_sync_task_service.py（续）
class TestExecuteTask:
    """execute_task 方法测试"""

    async def test_execute_task_skip_existing_mode(self, service, mock_db):
        """测试 skip_existing 模式执行"""
        # 准备
        task = SyncTask(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            start_date=date.today() - timedelta(days=2),
            end_date=date.today(),
            sync_mode="skip_existing",
            status="pending",
            total_days=3,
            operator_id=1,
        )
        mock_db.get = AsyncMock(return_value=task)

        # Mock OrderSyncService 和 CostCalcService
        with patch(
            "app.services.sync_task_service.OrderSyncService"
        ) as MockOrderSync, patch(
            "app.services.sync_task_service.CostCalcService"
        ) as MockCostCalc:
            mock_order_service = AsyncMock()
            mock_order_service.sync_orders.return_value = MagicMock(
                success=10, failed=0, skipped=0
            )
            MockOrderSync.return_value = mock_order_service

            mock_cost_service = AsyncMock()
            mock_cost_service.calculate_daily_cost.return_value = {
                "total_customers": 5,
                "calculated": 5,
                "no_rule": 0,
            }
            MockCostCalc.return_value = mock_cost_service

            # 执行
            await service.execute_task(task.id)

            # 验证
            assert task.status == "completed"
            assert task.completed_days == 3
            assert task.success_count == 30  # 3天 * 10条/天

    async def test_execute_task_force_overwrite_mode(self, service, mock_db):
        """测试 force_overwrite 模式执行"""
        # 准备
        task = SyncTask(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            start_date=date.today() - timedelta(days=1),
            end_date=date.today(),
            sync_mode="force_overwrite",
            status="pending",
            total_days=2,
            operator_id=1,
        )
        mock_db.get = AsyncMock(return_value=task)

        with patch(
            "app.services.sync_task_service.OrderSyncService"
        ) as MockOrderSync, patch(
            "app.services.sync_task_service.CostCalcService"
        ) as MockCostCalc:
            mock_order_service = AsyncMock()
            mock_order_service.sync_orders.return_value = MagicMock(
                success=10, failed=0, skipped=0
            )
            MockOrderSync.return_value = mock_order_service

            mock_cost_service = AsyncMock()
            mock_cost_service.calculate_daily_cost.return_value = {
                "total_customers": 5,
                "calculated": 5,
                "no_rule": 0,
            }
            MockCostCalc.return_value = mock_cost_service

            # 执行
            await service.execute_task(task.id)

            # 验证
            assert task.status == "completed"
            assert task.completed_days == 2

    async def test_execute_task_single_day_failure(self, service, mock_db):
        """测试单天失败不中断整体流程"""
        # 准备
        task = SyncTask(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            start_date=date.today() - timedelta(days=2),
            end_date=date.today(),
            sync_mode="skip_existing",
            status="pending",
            total_days=3,
            operator_id=1,
        )
        mock_db.get = AsyncMock(return_value=task)

        with patch(
            "app.services.sync_task_service.OrderSyncService"
        ) as MockOrderSync:
            mock_order_service = AsyncMock()
            # 第二天失败
            mock_order_service.sync_orders.side_effect = [
                MagicMock(success=10, failed=0, skipped=0),  # 第一天成功
                Exception("外部数据源异常"),  # 第二天失败
                MagicMock(success=10, failed=0, skipped=0),  # 第三天成功
            ]
            MockOrderSync.return_value = mock_order_service

            with patch(
                "app.services.sync_task_service.CostCalcService"
            ) as MockCostCalc:
                mock_cost_service = AsyncMock()
                mock_cost_service.calculate_daily_cost.return_value = {
                    "total_customers": 5,
                    "calculated": 5,
                    "no_rule": 0,
                }
                MockCostCalc.return_value = mock_cost_service

                # 执行
                await service.execute_task(task.id)

                # 验证
                assert task.status == "completed"  # 部分成功也算完成
                assert task.completed_days == 2
                assert task.failed_count == 1
```

- [ ] **Step 7: 运行测试验证失败**

```bash
cd backend
pytest tests/services/test_sync_task_service.py::TestExecuteTask -v
```

Expected: FAIL（execute_task 未实现）

- [ ] **Step 8: 实现 execute_task 方法**

```python
# backend/app/services/sync_task_service.py（续）
    async def execute_task(self, task_id: UUID) -> None:
        """执行同步任务（后台异步）"""
        task = await self.db.get(SyncTask, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        # 更新状态为 running
        task.status = "running"
        await self.db.commit()
        await self._update_redis_progress(task)

        lock_key = f"sync_lock:{task.start_date}:{task.end_date}"
        start_time = datetime.now()

        try:
            # 生成日期列表
            current_date = task.start_date
            dates = []
            while current_date <= task.end_date:
                dates.append(current_date)
                current_date += timedelta(days=1)

            # 逐天执行
            for sync_date in dates:
                task.current_date = sync_date
                await self.db.commit()

                try:
                    # skip_existing 模式：检查是否已有数据
                    if task.sync_mode == "skip_existing":
                        has_data = await self._check_data_exists(sync_date)
                        if has_data:
                            task.skipped_days += 1
                            task.completed_days += 1
                            await self.db.commit()
                            await self._update_redis_progress(task)
                            continue

                    # force_overwrite 模式：删除旧数据
                    if task.sync_mode == "force_overwrite":
                        await self._clear_data(sync_date)

                    # 同步订单
                    order_service = OrderSyncService(self.db)
                    order_result = await order_service.sync_orders(sync_date)

                    # 计算费用
                    cost_service = CostCalcService(self.db)
                    await cost_service.calculate_daily_cost(sync_date)

                    # 更新统计
                    task.completed_days += 1
                    task.success_count += order_result.success
                    task.failed_count += order_result.failed

                except Exception as e:
                    logger.error(f"同步 {sync_date} 失败: {e}")
                    task.failed_count += 1
                    task.completed_days += 1

                await self.db.commit()
                await self._update_redis_progress(task)

            # 任务完成
            task.status = "completed" if task.completed_days > 0 else "failed"
            task.completed_at = datetime.now()
            duration = (task.completed_at - start_time).total_seconds()

            # 更新审计日志
            await self._update_audit_log(
                task, "success" if task.status == "completed" else "failed", duration
            )

        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            duration = (task.completed_at - start_time).total_seconds()

            await self._update_audit_log(task, "failed", duration, str(e))

        finally:
            await self.db.commit()
            await self._update_redis_progress(task)
            # 释放锁
            await self.redis_client.delete(lock_key)

    async def _check_data_exists(self, sync_date: date) -> bool:
        """检查指定日期是否已有数据"""
        from app.models.daily_order import DailyOrder

        result = await self.db.execute(
            select(DailyOrder).where(DailyOrder.sync_date == sync_date).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _clear_data(self, sync_date: date) -> None:
        """清空指定日期的数据"""
        from app.models.daily_order import DailyOrder
        from app.models.daily_consumption import DailyConsumption

        # 删除订单
        await self.db.execute(
            DailyOrder.__table__.delete().where(DailyOrder.sync_date == sync_date)
        )
        # 删除消费记录
        await self.db.execute(
            DailyConsumption.__table__.delete().where(
                DailyConsumption.consumption_date == sync_date
            )
        )
        await self.db.commit()

    async def _update_audit_log(
        self, task: SyncTask, status: str, duration: float, error: str = None
    ) -> None:
        """更新审计日志"""
        from sqlalchemy import update

        await self.db.execute(
            update(SyncTaskLog)
            .where(SyncTaskLog.task_id == task.id)
            .values(
                status=status,
                duration_seconds=int(duration),
                success_count=task.success_count,
                failed_count=task.failed_count,
                skipped_count=task.skipped_days,
                error_message=error,
            )
        )
```

- [ ] **Step 9: 运行测试验证通过**

```bash
cd backend
pytest tests/services/test_sync_task_service.py::TestExecuteTask -v
```

Expected: PASS

- [ ] **Step 10: 提交**

```bash
git add backend/app/services/sync_task_service.py backend/tests/services/test_sync_task_service.py
git commit -m "feat: implement SyncTaskService.execute_task with TDD"
```

- [ ] **Step 11: 编写 get_progress 和 get_task 测试**

```python
# backend/tests/services/test_sync_task_service.py（续）
class TestGetProgress:
    """get_progress 方法测试"""

    async def test_get_progress_from_redis(self, service, mock_redis):
        """测试从 Redis 获取进度"""
        # 准备
        task_id = UUID("12345678-1234-5678-1234-567812345678")
        mock_redis.hgetall.return_value = {
            b"status": b"running",
            b"sync_mode": b"skip_existing",
            b"total_days": b"7",
            b"completed_days": b"5",
            b"skipped_days": b"2",
            b"current_date": b"2026-06-22",
            b"success_count": b"150",
            b"failed_count": b"0",
            b"percentage": b"71",
            b"error_message": b"",
        }

        # 执行
        progress = await service.get_progress(task_id)

        # 验证
        assert progress["status"] == "running"
        assert progress["completed_days"] == 5
        assert progress["skipped_days"] == 2
        assert progress["percentage"] == 71

    async def test_get_progress_fallback_to_db(self, service, mock_db, mock_redis):
        """测试 Redis 无数据时回退到数据库"""
        # 准备
        task_id = UUID("12345678-1234-5678-1234-567812345678")
        mock_redis.hgetall.return_value = {}  # Redis 无数据

        task = SyncTask(
            id=task_id,
            status="completed",
            sync_mode="skip_existing",
            total_days=7,
            completed_days=7,
            skipped_days=3,
            success_count=200,
            failed_count=0,
        )
        mock_db.get = AsyncMock(return_value=task)

        # 执行
        progress = await service.get_progress(task_id)

        # 验证
        assert progress["status"] == "completed"
        assert progress["completed_days"] == 7


class TestGetTask:
    """get_task 方法测试"""

    async def test_get_task_success(self, service, mock_db):
        """测试成功获取任务"""
        # 准备
        task_id = UUID("12345678-1234-5678-1234-567812345678")
        task = SyncTask(
            id=task_id,
            status="completed",
            sync_mode="skip_existing",
            total_days=7,
        )
        mock_db.get = AsyncMock(return_value=task)

        # 执行
        result = await service.get_task(task_id)

        # 验证
        assert result.id == task_id
        assert result.status == "completed"

    async def test_get_task_not_found(self, service, mock_db):
        """测试任务不存在"""
        # 准备
        task_id = UUID("12345678-1234-5678-1234-567812345678")
        mock_db.get = AsyncMock(return_value=None)

        # 执行 & 验证
        with pytest.raises(ValueError, match="任务不存在"):
            await service.get_task(task_id)
```

- [ ] **Step 12: 运行测试验证失败**

```bash
cd backend
pytest tests/services/test_sync_task_service.py::TestGetProgress -v
pytest tests/services/test_sync_task_service.py::TestGetTask -v
```

Expected: FAIL（方法未实现）

- [ ] **Step 13: 实现 get_progress 和 get_task 方法**

```python
# backend/app/services/sync_task_service.py（续）
    async def get_progress(self, task_id: UUID) -> dict:
        """获取任务进度"""
        # 优先从 Redis 读取
        progress_key = f"sync_progress:{task_id}"
        progress_data = await self.redis_client.hgetall(progress_key)

        if progress_data:
            # 解码 Redis 数据
            return {
                "task_id": str(task_id),
                "status": progress_data.get(b"status", b"").decode(),
                "sync_mode": progress_data.get(b"sync_mode", b"").decode(),
                "total_days": int(progress_data.get(b"total_days", 0)),
                "completed_days": int(progress_data.get(b"completed_days", 0)),
                "skipped_days": int(progress_data.get(b"skipped_days", 0)),
                "current_date": progress_data.get(b"current_date", b"").decode() or None,
                "success_count": int(progress_data.get(b"success_count", 0)),
                "failed_count": int(progress_data.get(b"failed_count", 0)),
                "percentage": int(progress_data.get(b"percentage", 0)),
                "error_message": progress_data.get(b"error_message", b"").decode() or None,
            }

        # 回退到数据库
        task = await self.db.get(SyncTask, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        percentage = int((task.completed_days / task.total_days) * 100) if task.total_days > 0 else 0

        return {
            "task_id": str(task.id),
            "status": task.status,
            "sync_mode": task.sync_mode,
            "total_days": task.total_days,
            "completed_days": task.completed_days,
            "skipped_days": task.skipped_days,
            "current_date": task.current_date.isoformat() if task.current_date else None,
            "success_count": task.success_count,
            "failed_count": task.failed_count,
            "percentage": percentage,
            "error_message": task.error_message,
        }

    async def get_task(self, task_id: UUID) -> SyncTask:
        """获取任务详情"""
        task = await self.db.get(SyncTask, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        return task
```

- [ ] **Step 14: 运行测试验证通过**

```bash
cd backend
pytest tests/services/test_sync_task_service.py -v
```

Expected: ALL PASS

- [ ] **Step 15: 提交**

```bash
git add backend/app/services/sync_task_service.py backend/tests/services/test_sync_task_service.py
git commit -m "feat: implement SyncTaskService.get_progress and get_task with TDD"
```

---

## Task 4: 实现 /api/v1/sync-tasks 路由

**Files:**
- Create: `backend/app/routes/sync_tasks.py`
- Modify: `backend/app/routes/__init__.py`

**Interfaces:**
- Consumes: `SyncTaskService`
- Produces: POST /api/v1/sync-tasks, GET /api/v1/sync-tasks/{task_id}, GET /api/v1/sync-tasks/{task_id}/progress

- [ ] **Step 1: 创建路由文件**

```python
# backend/app/routes/sync_tasks.py
"""同步任务 API 路由"""

import logging
from uuid import UUID

from sanic import Blueprint, Request
from sanic.response import json

from app.middleware.auth import auth_required
from app.services.sync_task_service import SyncTaskService
from app.cache.base import cache_service

logger = logging.getLogger(__name__)

sync_tasks_bp = Blueprint("sync_tasks", url_prefix="/api/v1/sync-tasks")


@sync_tasks_bp.post("/")
@auth_required
async def create_sync_task(request: Request):
    """创建同步任务"""
    try:
        data = request.json
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        sync_mode = data.get("sync_mode", "skip_existing")

        # 参数校验
        if not start_date or not end_date:
            return json(
                {"code": 400, "message": "开始日期和结束日期不能为空"},
                status=400,
            )

        if sync_mode not in ["skip_existing", "force_overwrite"]:
            return json(
                {"code": 400, "message": "无效的同步模式"},
                status=400,
            )

        # 解析日期
        from datetime import date

        try:
            start_date = date.fromisoformat(start_date)
            end_date = date.fromisoformat(end_date)
        except ValueError:
            return json(
                {"code": 400, "message": "日期格式错误，应为 YYYY-MM-DD"},
                status=400,
            )

        # 获取操作人
        operator_id = request.ctx.user.id

        # 创建服务
        redis_client = await cache_service._get_redis()
        service = SyncTaskService(db=request.ctx.db_session, redis_client=redis_client)

        # 创建任务
        task = await service.create_task(
            start_date=start_date,
            end_date=end_date,
            sync_mode=sync_mode,
            operator_id=operator_id,
        )

        # 启动后台任务
        request.app.add_task(service.execute_task(task.id))

        return json(
            {
                "code": 0,
                "message": "任务创建成功",
                "data": {
                    "task_id": str(task.id),
                    "status": task.status,
                    "sync_mode": task.sync_mode,
                    "total_days": task.total_days,
                },
            },
            status=201,
        )

    except ValueError as e:
        return json({"code": 400, "message": str(e)}, status=400)
    except Exception as e:
        if "已有相同周期的同步任务正在执行" in str(e):
            return json({"code": 409, "message": str(e)}, status=409)
        logger.error(f"创建同步任务失败: {e}")
        return json({"code": 500, "message": f"创建任务失败: {str(e)}"}, status=500)


@sync_tasks_bp.get("/<task_id:uuid>")
@auth_required
async def get_sync_task(request: Request, task_id: UUID):
    """获取任务详情"""
    try:
        service = SyncTaskService(db=request.ctx.db_session)
        task = await service.get_task(task_id)

        return json(
            {
                "code": 0,
                "data": {
                    "task_id": str(task.id),
                    "start_date": task.start_date.isoformat(),
                    "end_date": task.end_date.isoformat(),
                    "sync_mode": task.sync_mode,
                    "status": task.status,
                    "total_days": task.total_days,
                    "completed_days": task.completed_days,
                    "skipped_days": task.skipped_days,
                    "success_count": task.success_count,
                    "failed_count": task.failed_count,
                    "operator_id": task.operator_id,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "error_message": task.error_message,
                },
            }
        )

    except ValueError as e:
        return json({"code": 404, "message": str(e)}, status=404)
    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        return json({"code": 500, "message": f"获取任务失败: {str(e)}"}, status=500)


@sync_tasks_bp.get("/<task_id:uuid>/progress")
@auth_required
async def get_sync_task_progress(request: Request, task_id: UUID):
    """获取任务进度"""
    try:
        redis_client = await cache_service._get_redis()
        service = SyncTaskService(db=request.ctx.db_session, redis_client=redis_client)
        progress = await service.get_progress(task_id)

        return json({"code": 0, "data": progress})

    except ValueError as e:
        return json({"code": 404, "message": str(e)}, status=404)
    except Exception as e:
        logger.error(f"获取任务进度失败: {e}")
        return json({"code": 500, "message": f"获取进度失败: {str(e)}"}, status=500)
```

- [ ] **Step 2: 注册路由**

```python
# backend/app/routes/__init__.py
# 在文件末尾添加
from .sync_tasks import sync_tasks_bp

__all__ = [
    # ... 现有导出
    "sync_tasks_bp",
]
```

- [ ] **Step 3: 在主应用中注册蓝图**

```python
# backend/app/main.py
# 在注册蓝图的部分添加
from app.routes import sync_tasks_bp

app.blueprint(sync_tasks_bp)
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/routes/sync_tasks.py backend/app/routes/__init__.py backend/app/main.py
git commit -m "feat: implement /api/v1/sync-tasks routes"
```

---

## Task 5: 扩展 /api/v1/sync-logs 路由

**Files:**
- Modify: `backend/app/routes/sync_logs.py:16-109`

**Interfaces:**
- Consumes: `SyncTaskLog` 模型
- Produces: 扩展筛选参数的 GET /api/v1/sync-logs

- [ ] **Step 1: 扩展筛选参数**

```python
# backend/app/routes/sync_logs.py:16-109
@sync_logs_bp.get("/")
@auth_required
async def get_sync_logs(request):
    """
    获取同步任务日志列表

    Query Params:
        page: 页码 (default: 1)
        page_size: 每页数量 (default: 20)
        task_name: 任务名称筛选
        status: 状态筛选 (success/partial/failed)
        start_date: 同步开始日期筛选 (YYYY-MM-DD)
        end_date: 同步结束日期筛选 (YYYY-MM-DD)
        sync_mode: 同步模式筛选 (skip_existing/force_overwrite)
        operator_id: 操作人ID筛选

    Response:
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [...],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total": 100
                }
            }
        }
    """
    try:
        session: AsyncSession = request.ctx.db_session

        # 解析参数
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        task_name = request.args.get("task_name")
        status = request.args.get("status")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        sync_mode = request.args.get("sync_mode")
        operator_id = request.args.get("operator_id")

        # 构建查询
        query = select(SyncTaskLog)

        if task_name:
            query = query.where(SyncTaskLog.task_name == task_name)
        if status:
            query = query.where(SyncTaskLog.status == status)
        if start_date:
            from datetime import date
            query = query.where(SyncTaskLog.start_date >= date.fromisoformat(start_date))
        if end_date:
            from datetime import date
            query = query.where(SyncTaskLog.end_date <= date.fromisoformat(end_date))
        if sync_mode:
            query = query.where(SyncTaskLog.sync_mode == sync_mode)
        if operator_id:
            query = query.where(SyncTaskLog.operator_id == int(operator_id))

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar()

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(desc(SyncTaskLog.executed_at)).offset(offset).limit(page_size)
        result = await session.execute(query)
        logs = result.scalars().all()

        # 序列化
        logs_data = []
        for log in logs:
            logs_data.append(
                {
                    "id": log.id,
                    "task_name": log.task_name,
                    "status": log.status,
                    "total_count": log.total_count,
                    "success_count": log.success_count,
                    "failed_count": log.failed_count,
                    "skipped_count": log.skipped_count,
                    "executed_at": log.executed_at,
                    "duration_seconds": log.duration_seconds,
                    "error_message": log.error_message,
                    "task_id": str(log.task_id) if log.task_id else None,
                    "operator_id": log.operator_id,
                    "start_date": log.start_date.isoformat() if log.start_date else None,
                    "end_date": log.end_date.isoformat() if log.end_date else None,
                    "sync_mode": log.sync_mode,
                }
            )

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "list": logs_data,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total": total,
                    },
                },
            }
        )

    except Exception as e:
        logger.error(f"获取同步日志失败: {e}")
        return json(
            {"code": 500, "message": f"获取日志失败: {str(e)}"},
            status=500,
        )
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/routes/sync_logs.py
git commit -m "feat: extend /api/v1/sync-logs with audit filters"
```

---

## Task 6: 前端 API 调用

**Files:**
- Create: `frontend/src/api/syncTasks.ts`

**Interfaces:**
- Consumes: Axios 实例
- Produces: `createSyncTask`、`getSyncTaskProgress`、`getSyncTask` 函数

- [ ] **Step 1: 创建 API 文件**

```typescript
// frontend/src/api/syncTasks.ts
import request from './index'

export interface CreateSyncTaskParams {
  start_date: string
  end_date: string
  sync_mode: 'skip_existing' | 'force_overwrite'
}

export interface SyncTask {
  task_id: string
  status: string
  sync_mode: string
  total_days: number
  completed_days: number
  skipped_days: number
  current_date: string | null
  success_count: number
  failed_count: number
  percentage: number
  error_message: string | null
  start_date?: string
  end_date?: string
  operator_id?: number
  created_at?: string
  completed_at?: string
}

export async function createSyncTask(params: CreateSyncTaskParams): Promise<SyncTask> {
  const res = await request.post('/sync-tasks', params)
  return res.data
}

export async function getSyncTaskProgress(taskId: string): Promise<SyncTask> {
  const res = await request.get(`/sync-tasks/${taskId}/progress`)
  return res.data
}

export async function getSyncTask(taskId: string): Promise<SyncTask> {
  const res = await request.get(`/sync-tasks/${taskId}`)
  return res.data
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/syncTasks.ts
git commit -m "feat: add sync tasks API calls"
```

---

## Task 7: 前端 ProgressView 组件

**Files:**
- Create: `frontend/src/views/analytics/components/ProgressView.vue`

**Interfaces:**
- Consumes: `SyncTask` 类型
- Produces: 进度展示组件

- [ ] **Step 1: 创建 ProgressView 组件**

```vue
<!-- frontend/src/views/analytics/components/ProgressView.vue -->
<template>
  <div class="progress-view">
    <a-progress :percent="progress.percentage / 100" :stroke-width="20" />
    <div class="status-text">
      {{ statusText }}
    </div>
    <div v-if="isFinished" class="summary">
      <a-space>
        <a-tag color="green">成功 {{ progress.success_count }} 条</a-tag>
        <a-tag color="red">失败 {{ progress.failed_count }} 条</a-tag>
        <a-tag v-if="progress.skipped_days > 0" color="orange">
          跳过 {{ progress.skipped_days }} 天
        </a-tag>
      </a-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SyncTask } from '@/api/syncTasks'

const props = defineProps<{
  progress: SyncTask
}>()

const isFinished = computed(() => {
  return props.progress.status === 'completed' || props.progress.status === 'failed'
})

const statusText = computed(() => {
  const { status, sync_mode, completed_days, total_days, skipped_days, current_date } = props.progress

  if (status === 'running') {
    const modeText = sync_mode === 'skip_existing' ? `（跳过 ${skipped_days} 天）` : ''
    return `正在同步 ${current_date} 的数据... 已完成 ${completed_days}/${total_days} 天${modeText}`
  } else if (status === 'completed') {
    return '同步完成'
  } else if (status === 'failed') {
    return `同步失败：${props.progress.error_message || '未知错误'}`
  }
  return ''
})
</script>

<style scoped>
.progress-view {
  padding: 20px;
}

.status-text {
  margin-top: 16px;
  font-size: 14px;
  color: var(--color-text-2);
}

.summary {
  margin-top: 16px;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/analytics/components/ProgressView.vue
git commit -m "feat: add ProgressView component"
```

---

## Task 8: 前端 SyncDialog 组件

**Files:**
- Create: `frontend/src/views/analytics/components/SyncDialog.vue`

**Interfaces:**
- Consumes: `createSyncTask`、`getSyncTaskProgress` API，`ProgressView` 组件
- Produces: 同步对话框组件

- [ ] **Step 1: 创建 SyncDialog 组件**

```vue
<!-- frontend/src/views/analytics/components/SyncDialog.vue -->
<template>
  <a-modal
    v-model:visible="visible"
    :title="title"
    :ok-text="okText"
    :cancel-text="cancelText"
    :ok-loading="loading"
    :on-before-ok="handleBeforeOk"
    @cancel="handleCancel"
  >
    <!-- 输入阶段 -->
    <div v-if="state === 'input'">
      <a-form :model="form" layout="vertical">
        <a-form-item label="开始日期" required>
          <a-date-picker
            v-model="form.start_date"
            style="width: 100%"
            :disabled-date="disableStartDate"
          />
        </a-form-item>
        <a-form-item label="结束日期" required>
          <a-date-picker
            v-model="form.end_date"
            style="width: 100%"
            :disabled-date="disableEndDate"
          />
        </a-form-item>
        <a-form-item v-if="dateRangeError" :error="dateRangeError">
          <a-alert type="error">{{ dateRangeError }}</a-alert>
        </a-form-item>
        <a-form-item label="同步模式">
          <a-radio-group v-model="form.sync_mode">
            <a-radio value="skip_existing">仅补充缺失数据</a-radio>
            <a-radio value="force_overwrite">强制重新同步</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-alert
          v-if="form.sync_mode === 'force_overwrite'"
          type="warning"
          style="margin-top: 12px"
        >
          将删除并重新同步选定周期内的所有数据，此操作不可撤销
        </a-alert>
      </a-form>
    </div>

    <!-- 进度阶段 -->
    <div v-else-if="state === 'polling' || state === 'result'">
      <ProgressView :progress="progress" />
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { createSyncTask, getSyncTaskProgress, type SyncTask } from '@/api/syncTasks'
import ProgressView from './ProgressView.vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const state = ref<'input' | 'creating' | 'polling' | 'result'>('input')
const loading = ref(false)
const taskId = ref<string>('')
const progress = ref<SyncTask>({
  task_id: '',
  status: '',
  sync_mode: '',
  total_days: 0,
  completed_days: 0,
  skipped_days: 0,
  current_date: null,
  success_count: 0,
  failed_count: 0,
  percentage: 0,
  error_message: null,
})

const form = reactive({
  start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), // 7天前
  end_date: new Date(),
  sync_mode: 'skip_existing' as 'skip_existing' | 'force_overwrite',
})

const dateRangeError = computed(() => {
  if (!form.start_date || !form.end_date) return ''
  const start = new Date(form.start_date)
  const end = new Date(form.end_date)

  if (end < start) {
    return '结束日期不能早于开始日期'
  }

  const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1
  if (days > 31) {
    return '时间跨度不能超过31天'
  }

  return ''
})

const title = computed(() => {
  if (state.value === 'input') return '数据同步'
  if (state.value === 'polling') return '同步中...'
  if (state.value === 'result') {
    return progress.value.status === 'completed' ? '同步完成' : '同步失败'
  }
  return '数据同步'
})

const okText = computed(() => {
  if (state.value === 'input') return '开始同步'
  if (state.value === 'polling') return '取消'
  if (state.value === 'result') {
    return progress.value.status === 'failed' ? '重试' : '关闭'
  }
  return '确定'
})

const cancelText = computed(() => {
  return state.value === 'input' ? '取消' : '关闭'
})

let pollInterval: number | null = null

const disableStartDate = (date: Date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date > today
}

const disableEndDate = (date: Date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date > today
}

const handleBeforeOk = async () => {
  if (state.value === 'input') {
    if (dateRangeError.value) {
      Message.error(dateRangeError.value)
      return false
    }

    loading.value = true
    try {
      const start_date = formatDate(form.start_date)
      const end_date = formatDate(form.end_date)

      const result = await createSyncTask({
        start_date,
        end_date,
        sync_mode: form.sync_mode,
      })

      taskId.value = result.task_id
      state.value = 'polling'
      startPolling()
      return false // 不关闭对话框
    } catch (error: any) {
      Message.error(error.message || '创建任务失败')
      return false
    } finally {
      loading.value = false
    }
  } else if (state.value === 'result') {
    if (progress.value.status === 'failed') {
      // 重试
      state.value = 'input'
      return false
    }
    return true // 关闭对话框
  }
  return false
}

const handleCancel = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
  state.value = 'input'
  emit('update:visible', false)
}

const startPolling = () => {
  pollInterval = window.setInterval(async () => {
    try {
      const result = await getSyncTaskProgress(taskId.value)
      progress.value = result

      if (result.status === 'completed' || result.status === 'failed') {
        if (pollInterval) {
          clearInterval(pollInterval)
          pollInterval = null
        }
        state.value = 'result'
        if (result.status === 'completed') {
          emit('success')
        }
      }
    } catch (error) {
      console.error('轮询进度失败:', error)
    }
  }, 2000)
}

const formatDate = (date: Date): string => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

watch(
  () => props.visible,
  (newVal) => {
    if (!newVal) {
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
      state.value = 'input'
    }
  }
)

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})
</script>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/analytics/components/SyncDialog.vue
git commit -m "feat: add SyncDialog component"
```

---

## Task 9: 修改 Consumption.vue 集成 SyncDialog

**Files:**
- Modify: `frontend/src/views/analytics/Consumption.vue`

**Interfaces:**
- Consumes: `SyncDialog` 组件
- Produces: 替换原有同步按钮逻辑

- [ ] **Step 1: 引入 SyncDialog 组件**

```vue
<!-- frontend/src/views/analytics/Consumption.vue -->
<!-- 在 <script setup> 部分添加导入 -->
import SyncDialog from './components/SyncDialog.vue'
```

- [ ] **Step 2: 添加状态和
