"""SyncTaskService 单元测试"""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_task import SyncTask
from app.models.billing import SyncTaskLog
from app.services.sync_task_service import SyncTaskService


@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def mock_redis():
    """模拟 Redis 客户端"""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    redis.hset = AsyncMock()
    redis.expire = AsyncMock()
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

        # 模拟数据库返回的任务
        mock_task = SyncTask(
            id="123e4567-e89b-12d3-a456-426614174000",
            start_date=start_date,
            end_date=end_date,
            sync_mode=sync_mode,
            status="pending",
            total_days=8,
            operator_id=operator_id,
        )
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # 执行
        with patch.object(SyncTaskService, "_update_redis_progress", new_callable=AsyncMock):
            result = await service.create_task(
                start_date=start_date,
                end_date=end_date,
                sync_mode=sync_mode,
                operator_id=operator_id,
            )

        # 验证
        assert result is not None
        assert result.start_date == start_date
        assert result.end_date == end_date
        assert result.sync_mode == sync_mode
        assert result.status == "pending"
        assert result.total_days == 8
        assert result.operator_id == operator_id
        mock_db.add.assert_called()
        assert mock_db.add.call_count == 2  # SyncTask + SyncTaskLog

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
        mock_redis.set = AsyncMock(return_value=False)  # 锁获取失败
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


class TestExecuteTask:
    """execute_task 方法测试"""

    async def test_execute_task_skip_existing_mode(self, service, mock_db):
        """测试 skip_existing 模式执行"""
        # 准备
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        task = SyncTask(
            id=task_id,
            start_date=date.today() - timedelta(days=2),
            end_date=date.today(),
            sync_mode="skip_existing",
            status="pending",
            total_days=3,
            completed_days=0,
            skipped_days=0,
            success_count=0,
            failed_count=0,
            operator_id=1,
        )
        mock_db.get = AsyncMock(return_value=task)
        mock_db.commit = AsyncMock()

        # Mock OrderSyncService 和 CostCalcService
        with patch(
            "app.services.sync_task_service.OrderSyncService"
        ) as MockOrderSync, patch(
            "app.services.sync_task_service.CostCalcService"
        ) as MockCostCalc, patch.object(
            SyncTaskService, "_check_data_exists", new_callable=AsyncMock, return_value=False
        ), patch.object(
            SyncTaskService, "_update_redis_progress", new_callable=AsyncMock
        ), patch.object(
            SyncTaskService, "_update_audit_log", new_callable=AsyncMock
        ):
            mock_order_service = AsyncMock()
            mock_order_service.sync_orders = AsyncMock(
                return_value=MagicMock(success=10, failed=0, skipped=0)
            )
            MockOrderSync.return_value = mock_order_service

            mock_cost_service = AsyncMock()
            mock_cost_service.calculate_daily_cost = AsyncMock(
                return_value={"total_customers": 5, "calculated": 5, "no_rule": 0}
            )
            MockCostCalc.return_value = mock_cost_service

            # 执行
            await service.execute_task(task_id)

            # 验证
            assert task.status == "completed"
            assert task.completed_days == 3
            assert task.success_count == 30  # 3天 * 10条/天

    async def test_execute_task_force_overwrite_mode(self, service, mock_db):
        """测试 force_overwrite 模式执行"""
        # 准备
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        task = SyncTask(
            id=task_id,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today(),
            sync_mode="force_overwrite",
            status="pending",
            total_days=2,
            completed_days=0,
            skipped_days=0,
            success_count=0,
            failed_count=0,
            operator_id=1,
        )
        mock_db.get = AsyncMock(return_value=task)
        mock_db.commit = AsyncMock()

        with patch(
            "app.services.sync_task_service.OrderSyncService"
        ) as MockOrderSync, patch(
            "app.services.sync_task_service.CostCalcService"
        ) as MockCostCalc, patch.object(
            SyncTaskService, "_clear_data", new_callable=AsyncMock
        ), patch.object(
            SyncTaskService, "_update_redis_progress", new_callable=AsyncMock
        ), patch.object(
            SyncTaskService, "_update_audit_log", new_callable=AsyncMock
        ):
            mock_order_service = AsyncMock()
            mock_order_service.sync_orders = AsyncMock(
                return_value=MagicMock(success=10, failed=0, skipped=0)
            )
            MockOrderSync.return_value = mock_order_service

            mock_cost_service = AsyncMock()
            mock_cost_service.calculate_daily_cost = AsyncMock(
                return_value={"total_customers": 5, "calculated": 5, "no_rule": 0}
            )
            MockCostCalc.return_value = mock_cost_service

            # 执行
            await service.execute_task(task_id)

            # 验证
            assert task.status == "completed"
            assert task.completed_days == 2

    async def test_execute_task_single_day_failure(self, service, mock_db):
        """测试单天失败不中断整体流程"""
        # 准备
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        task = SyncTask(
            id=task_id,
            start_date=date.today() - timedelta(days=2),
            end_date=date.today(),
            sync_mode="skip_existing",
            status="pending",
            total_days=3,
            completed_days=0,
            skipped_days=0,
            success_count=0,
            failed_count=0,
            operator_id=1,
        )
        mock_db.get = AsyncMock(return_value=task)
        mock_db.commit = AsyncMock()

        with patch(
            "app.services.sync_task_service.OrderSyncService"
        ) as MockOrderSync, patch(
            "app.services.sync_task_service.CostCalcService"
        ) as MockCostCalc, patch.object(
            SyncTaskService, "_check_data_exists", new_callable=AsyncMock, return_value=False
        ), patch.object(
            SyncTaskService, "_update_redis_progress", new_callable=AsyncMock
        ), patch.object(
            SyncTaskService, "_update_audit_log", new_callable=AsyncMock
        ):
            mock_order_service = AsyncMock()
            # 第二天失败
            mock_order_service.sync_orders = AsyncMock(
                side_effect=[
                    MagicMock(success=10, failed=0, skipped=0),  # 第一天成功
                    Exception("外部数据源异常"),  # 第二天失败
                    MagicMock(success=10, failed=0, skipped=0),  # 第三天成功
                ]
            )
            MockOrderSync.return_value = mock_order_service

            mock_cost_service = AsyncMock()
            mock_cost_service.calculate_daily_cost = AsyncMock(
                return_value={"total_customers": 5, "calculated": 5, "no_rule": 0}
            )
            MockCostCalc.return_value = mock_cost_service

            # 执行
            await service.execute_task(task_id)

            # 验证
            assert task.status == "completed"  # 部分成功也算完成
            assert task.completed_days == 2
            assert task.failed_count == 1


class TestGetProgress:
    """get_progress 方法测试"""

    async def test_get_progress_from_redis(self, service, mock_redis):
        """测试从 Redis 获取进度"""
        # 准备
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_redis.hgetall = AsyncMock(
            return_value={
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
        )

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
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_redis.hgetall = AsyncMock(return_value={})  # Redis 无数据

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
        task_id = "123e4567-e89b-12d3-a456-426614174000"
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
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_db.get = AsyncMock(return_value=None)

        # 执行 & 验证
        with pytest.raises(ValueError, match="任务不存在"):
            await service.get_task(task_id)
