"""SyncTaskService 单元测试"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_task import SyncTask
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
    redis.exists = AsyncMock(return_value=False)
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

        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # mock execute 返回空活跃任务列表
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

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

    async def test_create_task_lock_conflict(self, service, mock_db, mock_redis):
        """测试锁冲突"""
        # 准备
        mock_redis.set = AsyncMock(return_value=False)  # 锁获取失败
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        # mock execute 返回空活跃任务列表（无活跃任务，进入锁获取阶段）
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        # 执行 & 验证
        with pytest.raises(Exception, match="已有相同周期的同步任务正在执行"):
            await service.create_task(
                start_date=start_date,
                end_date=end_date,
                sync_mode="skip_existing",
                operator_id=1,
            )

    async def test_create_task_recovers_stuck_task_no_redis_progress(
        self, service, mock_db, mock_redis
    ):
        """测试恢复卡死任务：Redis 进度信息已消失"""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        # 模拟一个 running 状态的卡死任务
        stuck_task = MagicMock()
        stuck_task.id = "stuck-uuid"
        stuck_task.status = "running"
        stuck_task.start_date = start_date
        stuck_task.end_date = end_date
        stuck_task.created_at = datetime.now() - timedelta(hours=2)
        stuck_task.error_message = None
        stuck_task.completed_at = None

        # db.execute 返回卡死任务
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stuck_task]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        # Redis 进度不存在（进程已死亡）
        mock_redis.exists = AsyncMock(return_value=False)
        mock_redis.set = AsyncMock(return_value=True)

        with patch.object(SyncTaskService, "_update_redis_progress", new_callable=AsyncMock):
            result = await service.create_task(
                start_date=start_date,
                end_date=end_date,
                sync_mode="skip_existing",
                operator_id=1,
            )

        # 验证：卡死任务被标记为 failed
        assert stuck_task.status == "failed"
        assert stuck_task.error_message is not None
        assert stuck_task.completed_at is not None
        # 验证：新任务成功创建
        assert result is not None
        assert result.status == "pending"

    async def test_create_task_recovers_stuck_task_timeout(self, service, mock_db, mock_redis):
        """测试恢复卡死任务：运行时间超过 30 分钟"""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        # 模拟一个 running 状态的超时任务
        stuck_task = MagicMock()
        stuck_task.id = "stuck-uuid"
        stuck_task.status = "running"
        stuck_task.start_date = start_date
        stuck_task.end_date = end_date
        stuck_task.created_at = datetime.now() - timedelta(minutes=45)
        stuck_task.error_message = None
        stuck_task.completed_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stuck_task]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        # Redis 进度存在，但任务运行超时
        mock_redis.exists = AsyncMock(return_value=True)
        mock_redis.set = AsyncMock(return_value=True)

        with patch.object(SyncTaskService, "_update_redis_progress", new_callable=AsyncMock):
            result = await service.create_task(
                start_date=start_date,
                end_date=end_date,
                sync_mode="skip_existing",
                operator_id=1,
            )

        # 验证：超时任务被标记为 failed
        assert stuck_task.status == "failed"
        assert "30 分钟" in stuck_task.error_message
        # 验证：新任务成功创建
        assert result is not None
        assert result.status == "pending"

    async def test_create_task_blocked_by_truly_active_task(self, service, mock_db, mock_redis):
        """测试真正活跃的任务阻止创建"""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        # 模拟一个 running 状态的任务，运行时间在 30 分钟内
        active_task = MagicMock()
        active_task.id = "active-uuid"
        active_task.status = "running"
        active_task.start_date = start_date
        active_task.end_date = end_date
        active_task.created_at = datetime.now() - timedelta(minutes=10)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active_task]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Redis 进度存在
        mock_redis.exists = AsyncMock(return_value=True)

        with pytest.raises(Exception, match="已有相同周期的同步任务正在执行"):
            await service.create_task(
                start_date=start_date,
                end_date=end_date,
                sync_mode="skip_existing",
                operator_id=1,
            )

        # 验证：活跃任务未被修改
        assert active_task.status == "running"


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
        with (
            patch("app.services.sync_task_service.OrderSyncService") as MockOrderSync,
            patch("app.services.sync_task_service.CostCalcService") as MockCostCalc,
            patch.object(
                SyncTaskService,
                "_check_data_completeness",
                new_callable=AsyncMock,
                return_value=(False, False),
            ),
            patch.object(SyncTaskService, "_update_redis_progress", new_callable=AsyncMock),
            patch.object(SyncTaskService, "_update_audit_log", new_callable=AsyncMock),
        ):
            mock_order_service = AsyncMock()
            mock_order_service.sync_orders = AsyncMock(
                return_value=MagicMock(success=10, failed=0, skipped=0, unmatched=0)
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

        with (
            patch("app.services.sync_task_service.OrderSyncService") as MockOrderSync,
            patch("app.services.sync_task_service.CostCalcService") as MockCostCalc,
            patch.object(SyncTaskService, "_clear_data", new_callable=AsyncMock),
            patch.object(SyncTaskService, "_update_redis_progress", new_callable=AsyncMock),
            patch.object(SyncTaskService, "_update_audit_log", new_callable=AsyncMock),
        ):
            mock_order_service = AsyncMock()
            mock_order_service.sync_orders = AsyncMock(
                return_value=MagicMock(success=10, failed=0, skipped=0, unmatched=0)
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

        with (
            patch("app.services.sync_task_service.OrderSyncService") as MockOrderSync,
            patch("app.services.sync_task_service.CostCalcService") as MockCostCalc,
            patch.object(
                SyncTaskService,
                "_check_data_completeness",
                new_callable=AsyncMock,
                return_value=(False, False),
            ),
            patch.object(SyncTaskService, "_update_redis_progress", new_callable=AsyncMock),
            patch.object(SyncTaskService, "_update_audit_log", new_callable=AsyncMock),
        ):
            mock_order_service = AsyncMock()
            # 第二天失败
            mock_order_service.sync_orders = AsyncMock(
                side_effect=[
                    MagicMock(success=10, failed=0, skipped=0, unmatched=0),  # 第一天成功
                    Exception("外部数据源异常"),  # 第二天失败
                    MagicMock(success=10, failed=0, skipped=0, unmatched=0),  # 第三天成功
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

            # 验证：1 天失败 + 2 天成功 → 部分成功（partial）
            assert task.status == "partial"
            assert task.completed_days == 2
            assert task.failed_count == 1

    async def test_execute_task_cancelled(self, service, mock_db, mock_redis):
        """测试任务取消"""
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
        # 设置取消标志
        mock_redis.exists = AsyncMock(return_value=True)

        with (
            patch.object(SyncTaskService, "_update_redis_progress", new_callable=AsyncMock),
            patch.object(SyncTaskService, "_update_audit_log", new_callable=AsyncMock),
        ):
            await service.execute_task(task_id)

            assert task.status == "cancelled"
            assert task.completed_at is not None

    async def test_cancel_task_success(self, service, mock_db, mock_redis):
        """测试成功取消任务"""
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        task = SyncTask(id=task_id, status="running")
        mock_db.get = AsyncMock(return_value=task)

        result = await service.cancel_task(task_id)

        assert result is True
        mock_redis.set.assert_called_once()

    async def test_cancel_task_not_running(self, service, mock_db):
        """测试取消非运行中的任务"""
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        task = SyncTask(id=task_id, status="completed")
        mock_db.get = AsyncMock(return_value=task)

        with pytest.raises(ValueError, match="任务状态为 completed，无法取消"):
            await service.cancel_task(task_id)


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
        assert progress["percentage"] == 0.71

    async def test_get_progress_from_redis_str_keys(self, service, mock_redis):
        """测试真实客户端配置（decode_responses=True）返回 str 键时的解析

        回归保护：此前用 bytes 键（b"status"）查询 hash，而生产客户端固定
        decode_responses=True（app/cache/base.py 的 redis.from_url），
        导致真实 Redis 路径下所有字段静默取默认值 —— 任务进度恒为空。
        """
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_redis.hgetall = AsyncMock(
            return_value={
                "status": "running",
                "sync_mode": "skip_existing",
                "total_days": "7",
                "completed_days": "5",
                "skipped_days": "2",
                "current_date": "2026-06-22",
                "success_count": "150",
                "failed_count": "0",
                "percentage": "71",
                "error_message": "",
            }
        )

        progress = await service.get_progress(task_id)

        assert progress["status"] == "running"
        assert progress["sync_mode"] == "skip_existing"
        assert progress["total_days"] == 7
        assert progress["completed_days"] == 5
        assert progress["percentage"] == 0.71
        assert progress["current_date"] == "2026-06-22"

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

    async def test_get_progress_redis_empty_values(self, service, mock_redis):
        """测试 Redis 返回空值时的安全解码"""
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_redis.hgetall = AsyncMock(
            return_value={
                b"status": b"running",
                b"sync_mode": b"",
                b"total_days": b"",
                b"completed_days": b"0",
                b"skipped_days": b"0",
                b"current_date": b"",
                b"success_count": b"0",
                b"failed_count": b"0",
                b"percentage": b"0",
                b"error_message": b"",
            }
        )

        progress = await service.get_progress(task_id)

        assert progress["status"] == "running"
        assert progress["total_days"] == 0
        assert progress["current_date"] is None
        assert progress["error_message"] is None

    async def test_get_progress_redis_missing_fields(self, service, mock_redis):
        """测试 Redis 缺少部分字段时的容错"""
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        # 只返回部分字段
        mock_redis.hgetall = AsyncMock(
            return_value={
                b"status": b"running",
                b"percentage": b"50",
            }
        )

        progress = await service.get_progress(task_id)

        assert progress["status"] == "running"
        assert progress["percentage"] == 0.5
        assert progress["total_days"] == 0
        assert progress["completed_days"] == 0


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


class TestExecutionStatus:
    """执行信息三态判定与历史回退逻辑"""

    def test_error_takes_priority(self):
        assert SyncTaskService._execution_status("completed", 1, 0) == "error"
        assert SyncTaskService._execution_status("completed", 3, 2) == "error"

    def test_warning_when_warning_count(self):
        assert SyncTaskService._execution_status("completed", 0, 2) == "warning"

    def test_normal_no_details_completed(self):
        assert SyncTaskService._execution_status("completed", 0, 0) == "normal"

    def test_fallback_failed_to_error(self):
        # 历史任务（无明细）按状态回退
        assert SyncTaskService._execution_status("failed", 0, 0) == "error"

    def test_fallback_partial_to_warning(self):
        assert SyncTaskService._execution_status("partial", 0, 0) == "warning"

    def test_fallback_others_to_normal(self):
        for status in ("cancelled", "pending", "running"):
            assert SyncTaskService._execution_status(status, 0, 0) == "normal"


class TestPersistDetails:
    """执行明细落库"""

    async def test_persist_details_success(self, service, mock_db):
        from app.services.dto import SyncDetail

        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        details = [
            SyncDetail(
                sync_date=date(2026, 9, 16),
                level="info",
                category="order_save",
                message="成功同步 3 条订单",
                customer_id=1,
                customer_name="客户A",
                record_count=3,
            ),
            SyncDetail(
                sync_date=date(2026, 9, 16),
                level="warning",
                category="order_match",
                message="订单未匹配到内部客户",
                external_customer_id="10086",
                company_name="XX公司",
                order_code="NEST-20260916-001",
            ),
        ]

        await service._persist_details("123e4567-e89b-12d3-a456-426614174000", details)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_persist_details_empty_noop(self, service, mock_db):
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await service._persist_details("123e4567-e89b-12d3-a456-426614174000", [])

        mock_db.execute.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_persist_details_error_rollback(self, service, mock_db):
        from app.services.dto import SyncDetail

        mock_db.execute = AsyncMock(side_effect=Exception("db error"))
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        details = [
            SyncDetail(
                sync_date=date(2026, 9, 16),
                level="error",
                category="system",
                message="任务执行异常",
            )
        ]

        await service._persist_details("123e4567-e89b-12d3-a456-426614174000", details)

        mock_db.rollback.assert_called_once()
