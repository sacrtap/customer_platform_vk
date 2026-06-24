"""同步任务服务"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SyncTaskLog
from app.models.daily_consumption import DailyConsumption
from app.models.daily_order import DailyOrder
from app.models.sync_task import SyncTask
from app.services.cost_calc import CostCalcService
from app.services.order_sync import OrderSyncService


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
            lock_key,
            "1",
            nx=True,
            ex=1800,  # 30分钟TTL
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

    async def execute_task(self, task_id: UUID) -> None:
        """执行同步任务（后台异步）"""
        task = await self.db.get(SyncTask, task_id)
        if not task:
            # 任务不存在时尝试释放锁
            lock_key = f"sync_lock:{task_id}"
            await self.redis_client.delete(lock_key)
            raise ValueError(f"任务不存在: {task_id}")

        lock_key = f"sync_lock:{task.start_date}:{task.end_date}"

        try:
            # 更新状态为 running
            task.status = "running"
            await self.db.commit()
            await self._update_redis_progress(task)

            start_time = datetime.now(timezone.utc)

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

                    except Exception:
                        # 单天失败不中断整体流程
                        task.failed_count += 1

                    await self.db.commit()
                    await self._update_redis_progress(task)

                # 任务完成
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                duration = (task.completed_at - start_time).total_seconds()

                # 更新审计日志
                await self._update_audit_log(
                    task, "success" if task.status == "completed" else "failed", duration
                )

            except Exception as e:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now(timezone.utc)
                duration = (task.completed_at - start_time).total_seconds()

                await self._update_audit_log(task, "failed", duration, str(e))

            finally:
                await self.db.commit()
                await self._update_redis_progress(task)

        finally:
            # 无论发生什么，确保释放锁
            await self.redis_client.delete(lock_key)

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

        percentage = (
            int((task.completed_days / task.total_days) * 100) if task.total_days > 0 else 0
        )

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

    async def _update_redis_progress(self, task: SyncTask) -> None:
        """更新 Redis 进度"""
        progress_key = f"sync_progress:{task.id}"
        percentage = (
            int((task.completed_days / task.total_days) * 100) if task.total_days > 0 else 0
        )

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

    async def _check_data_exists(self, sync_date: date) -> bool:
        """检查指定日期是否已有数据"""
        result = await self.db.execute(
            select(DailyOrder).where(DailyOrder.sync_date == sync_date).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _clear_data(self, sync_date: date) -> None:
        """清空指定日期的数据"""
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
