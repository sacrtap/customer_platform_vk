"""同步任务服务"""

import logging
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
            lock_key,
            "1",
            nx=True,
            ex=1800,  # 30分钟TTL
        )
        if not lock_acquired:
            raise Exception("已有相同周期的同步任务正在执行")

        try:
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
            # 不需要 refresh：task.id 是客户端生成的 UUID，已立即可用

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
        except Exception:
            # 创建失败时释放锁
            await self.redis_client.delete(lock_key)
            raise

    async def execute_task(self, task_id: UUID) -> None:
        """执行同步任务（后台异步）"""
        logger.info(f"[{task_id}] 开始执行同步任务")

        # 重新加载任务对象，确保在当前 session 上下文中
        task = await self.db.get(SyncTask, task_id)
        if not task:
            logger.error(f"[{task_id}] 任务不存在")
            # 任务不存在时尝试释放锁
            lock_key = f"sync_lock:{task_id}"
            await self.redis_client.delete(lock_key)
            raise ValueError(f"任务不存在: {task_id}")

        logger.info(
            f"[{task_id}] 任务信息: 周期 {task.start_date} ~ {task.end_date}, 模式 {task.sync_mode}"
        )
        lock_key = f"sync_lock:{task.start_date}:{task.end_date}"
        cancel_key = f"sync_cancel:{task_id}"  # 取消标志 key

        try:
            # 检查任务是否在 pending 阶段已被取消
            if await self.redis_client.exists(cancel_key):
                logger.info(f"[{task_id}] 任务在 pending 阶段已被取消")
                task.status = "cancelled"
                task.completed_at = datetime.now(timezone.utc)
                await self.db.commit()
                await self._update_redis_progress(task)
                return

            # 更新状态为 running
            logger.info(f"[{task_id}] 更新状态为 running")
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

                logger.info(
                    f"[{task_id}] 待处理日期: {len(dates)} 天, 从 {dates[0]} 到 {dates[-1]}"
                )

                # 逐天执行
                for idx, sync_date in enumerate(dates):
                    logger.info(f"[{task_id}] 处理第 {idx + 1}/{len(dates)} 天: {sync_date}")

                    # 检查取消标志
                    if await self.redis_client.exists(cancel_key):
                        logger.info(f"[{task_id}] 检测到取消标志，停止处理")
                        task.status = "cancelled"
                        task.completed_at = datetime.now(timezone.utc)
                        duration = (task.completed_at - start_time).total_seconds()
                        await self._update_audit_log(task, "cancelled", duration)
                        await self.db.commit()
                        await self._update_redis_progress(task)
                        return  # 提前退出，不回滚

                    task.current_date = sync_date
                    await self.db.commit()
                    await self._update_redis_progress(task)

                    try:
                        # skip_existing 模式：检查是否已有数据
                        if task.sync_mode == "skip_existing":
                            has_data = await self._check_data_exists(sync_date)
                            if has_data:
                                logger.info(f"[{task_id}] {sync_date} 已有数据，跳过")
                                task.skipped_days += 1
                                task.completed_days += 1
                                await self.db.commit()
                                await self._update_redis_progress(task)
                                continue

                        # force_overwrite 模式：删除旧数据
                        if task.sync_mode == "force_overwrite":
                            logger.info(f"[{task_id}] {sync_date} 强制覆盖模式，清除旧数据")
                            await self._clear_data(sync_date)

                        # 同步订单
                        logger.info(f"[{task_id}] {sync_date} 开始同步订单")
                        order_service = OrderSyncService(self.db)
                        order_result = await order_service.sync_orders(sync_date)
                        logger.info(
                            f"[{task_id}] {sync_date} 订单同步完成: 成功 {order_result.success}, 失败 {order_result.failed}"
                        )

                        # 计算费用
                        logger.info(f"[{task_id}] {sync_date} 开始计算费用")
                        cost_service = CostCalcService(self.db)
                        await cost_service.calculate_daily_cost(sync_date)
                        logger.info(f"[{task_id}] {sync_date} 费用计算完成")

                        # 刷新 task 对象，因为 sync_orders 和 calculate_daily_cost 内部调用了 commit()
                        # 导致 task 属性过期，后续访问会触发 MissingGreenlet
                        await self.db.refresh(task)

                        # 更新统计
                        task.completed_days += 1
                        task.success_count += order_result.success
                        task.failed_count += order_result.failed
                        await self.db.commit()  # 立即提交进度，使前端轮询能读取到最新值
                        logger.info(
                            f"[{task_id}] {sync_date} 处理完成，累计完成 {task.completed_days}/{len(dates)} 天"
                        )

                    except Exception as e:
                        logger.error(
                            f"[{task_id}] {sync_date} 处理失败: {type(e).__name__}: {e}",
                            exc_info=True,
                        )
                        # 单天失败不中断整体流程
                        # 先回滚，确保 session 状态正确
                        await self.db.rollback()
                        # 重新加载任务对象，避免 MissingGreenlet 错误
                        await self.db.refresh(task)
                        task.failed_count += 1
                        await self.db.commit()

                    # 更新 Redis 进度
                    await self._update_redis_progress(task)

                # 任务完成
                logger.info(f"[{task_id}] 所有日期处理完成，更新状态为 completed")
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                duration = (task.completed_at - start_time).total_seconds()
                logger.info(f"[{task_id}] 任务执行耗时: {duration:.2f} 秒")

                # 更新审计日志
                await self._update_audit_log(
                    task, "success" if task.status == "completed" else "failed", duration
                )
                logger.info(f"[{task_id}] 审计日志已更新")

            except Exception as e:
                logger.error(
                    f"[{task_id}] 任务执行过程中发生异常: {type(e).__name__}: {e}", exc_info=True
                )
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now(timezone.utc)
                duration = (task.completed_at - start_time).total_seconds()

                await self._update_audit_log(task, "failed", duration, str(e))

            finally:
                logger.info(f"[{task_id}] 提交最终状态到数据库")
                await self.db.commit()
                await self._update_redis_progress(task)

        finally:
            # 无论发生什么，确保释放锁和清理取消标志
            logger.info(f"[{task_id}] 清理 Redis 锁和取消标志")
            await self.redis_client.delete(lock_key)
            await self.redis_client.delete(cancel_key)
            logger.info(f"[{task_id}] 任务执行流程结束")

    async def cancel_task(self, task_id: UUID) -> bool:
        """取消同步任务

        - pending: 后台执行尚未开始，立即标记为 cancelled
        - running: 后台执行进行中，设置 Redis 取消标志 + 立即更新状态为 cancelled，
          执行循环检测到标志后会跳过剩余天数
        """
        task = await self.db.get(SyncTask, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if task.status not in ["pending", "running"]:
            raise ValueError(f"任务状态为 {task.status}，无法取消")

        # 设置 Redis 取消标志，供 execute_task 循环检测
        cancel_key = f"sync_cancel:{task_id}"
        await self.redis_client.set(cancel_key, "1", ex=3600)

        # 立即更新数据库状态为 cancelled，让前端列表即时反映取消结果
        task.status = "cancelled"
        task.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        # 更新 Redis 进度缓存
        await self._update_redis_progress(task)

        return True

    async def recover_stuck_tasks(self, max_running_minutes: int = 30) -> int:
        """恢复卡住的任务：将 running 状态的任务标记为 failed

        判断条件（满足任一即恢复）：
        1. Redis 中不存在对应的进度 key（进程已死亡）
        2. 任务运行时间超过 max_running_minutes（疑似卡住）

        Args:
            max_running_minutes: 最大允许运行时间（分钟），默认 30 分钟

        Returns:
            恢复的任务数量
        """
        result = await self.db.execute(select(SyncTask).where(SyncTask.status == "running"))
        running_tasks = result.scalars().all()

        recovered = 0
        now = datetime.now()

        for task in running_tasks:
            progress_key = f"sync_progress:{task.id}"
            should_recover = False
            reason = ""

            # 检查 1: Redis 进度 key 是否存在
            if not await self.redis_client.exists(progress_key):
                should_recover = True
                reason = "任务执行进程异常终止（Redis 进度信息已消失）"
            else:
                # 检查 2: 任务运行时长是否超过阈值
                running_duration = now - task.created_at
                running_minutes = running_duration.total_seconds() / 60

                if running_minutes > max_running_minutes:
                    should_recover = True
                    reason = f"任务运行超过 {max_running_minutes} 分钟（实际 {running_minutes:.1f} 分钟），疑似卡住"

            if should_recover:
                task.status = "failed"
                task.error_message = reason
                task.completed_at = now
                await self.db.commit()
                recovered += 1

        return recovered

    async def check_stuck_tasks(self, max_running_minutes: int = 60) -> int:
        """检测并处理卡住的任务（定期检测用）

        判断条件：status = 'running' 且运行时间超过 max_running_minutes

        Args:
            max_running_minutes: 最大允许运行时间（分钟），默认 60 分钟

        Returns:
            标记为 failed 的任务数量
        """
        threshold = datetime.now() - timedelta(minutes=max_running_minutes)

        result = await self.db.execute(
            select(SyncTask).where(
                SyncTask.status == "running",
                SyncTask.created_at < threshold,
            )
        )
        stuck_tasks = result.scalars().all()

        for task in stuck_tasks:
            task.status = "failed"
            task.error_message = f"任务运行超过 {max_running_minutes} 分钟，疑似卡住"
            task.completed_at = datetime.now()
            await self.db.commit()

        return len(stuck_tasks)

    async def get_progress(self, task_id: UUID) -> dict:
        """获取任务进度"""
        # 优先从 Redis 读取
        progress_key = f"sync_progress:{task_id}"
        progress_data = await self.redis_client.hgetall(progress_key)

        if progress_data:
            # 辅助函数：安全解码 bytes 值
            def decode_bytes(val, default=""):
                if val is None:
                    return default
                if isinstance(val, bytes):
                    return val.decode("utf-8")
                return str(val)

            # 解码 Redis 数据
            # percentage 从 0-100 整数转换为 0-1 小数（Arco Design 期望格式）
            percentage_int = int(decode_bytes(progress_data.get(b"percentage"), "0") or "0")
            return {
                "task_id": str(task_id),
                "status": decode_bytes(progress_data.get(b"status")),
                "sync_mode": decode_bytes(progress_data.get(b"sync_mode")),
                "total_days": int(decode_bytes(progress_data.get(b"total_days"), "0") or "0"),
                "completed_days": int(
                    decode_bytes(progress_data.get(b"completed_days"), "0") or "0"
                ),
                "skipped_days": int(decode_bytes(progress_data.get(b"skipped_days"), "0") or "0"),
                "current_date": decode_bytes(progress_data.get(b"current_date")) or None,
                "success_count": int(decode_bytes(progress_data.get(b"success_count"), "0") or "0"),
                "failed_count": int(decode_bytes(progress_data.get(b"failed_count"), "0") or "0"),
                "percentage": percentage_int / 100.0,  # 转换为 0-1 小数
                "error_message": decode_bytes(progress_data.get(b"error_message")) or None,
            }

        # 回退到数据库
        task = await self.db.get(SyncTask, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        # percentage 转换为 0-1 小数（Arco Design 期望格式）
        percentage: float = task.completed_days / task.total_days if task.total_days > 0 else 0.0

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
            "percentage": percentage,  # 0-1 小数
            "error_message": task.error_message,
        }

    async def get_task(self, task_id: UUID) -> SyncTask:
        """获取任务详情"""
        task = await self.db.get(SyncTask, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        return task

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str = None,
    ) -> dict:
        """获取任务列表（分页）"""
        from sqlalchemy import desc as sa_desc
        from sqlalchemy import func
        from sqlalchemy.orm import selectinload

        query = select(SyncTask).options(selectinload(SyncTask.operator))
        count_query = select(func.count(SyncTask.id))

        if status:
            query = query.where(SyncTask.status == status)
            count_query = count_query.where(SyncTask.status == status)

        # 获取总数
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(sa_desc(SyncTask.created_at)).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return {
            "list": [self._task_to_dict(task) for task in tasks],
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }

    async def get_stats(self) -> dict:
        """获取任务统计数据"""
        from datetime import datetime, timedelta

        from sqlalchemy import func

        # 总任务数
        total_result = await self.db.execute(select(func.count(SyncTask.id)))
        total_tasks = total_result.scalar() or 0

        # 成功任务数
        success_result = await self.db.execute(
            select(func.count(SyncTask.id)).where(SyncTask.status == "completed")
        )
        success_count = success_result.scalar() or 0

        # 成功率 = 成功完成的任务数 / 总提交任务数 × 100%（PRD 定义）
        success_rate = round((success_count / total_tasks * 100), 1) if total_tasks > 0 else 0

        # 24 小时内统计（使用 naive datetime 匹配数据库）
        now = datetime.now()
        last_24h = now - timedelta(hours=24)

        last_24h_total_result = await self.db.execute(
            select(func.count(SyncTask.id)).where(SyncTask.created_at >= last_24h)
        )
        last_24h_total = last_24h_total_result.scalar() or 0

        last_24h_failed_result = await self.db.execute(
            select(func.count(SyncTask.id)).where(
                SyncTask.created_at >= last_24h,
                SyncTask.status == "failed",
            )
        )
        last_24h_failed = last_24h_failed_result.scalar() or 0

        return {
            "total_tasks": total_tasks,
            "success_rate": success_rate,
            "last_24h": {
                "total": last_24h_total,
                "failed": last_24h_failed,
            },
        }

    def _task_to_dict(self, task: SyncTask) -> dict:
        """将任务对象转换为字典"""
        return {
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
            "error_message": task.error_message,
            "operator_id": task.operator_id,
            "operator_name": task.operator.real_name if task.operator else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    async def _update_redis_progress(self, task: SyncTask) -> None:
        """更新 Redis 进度"""
        progress_key = f"sync_progress:{task.id}"
        total_days = task.total_days or 0
        completed_days = task.completed_days or 0
        percentage = int((completed_days / total_days) * 100) if total_days > 0 else 0

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
        from sqlalchemy import func

        result = await self.db.execute(
            select(func.count(DailyOrder.id)).where(DailyOrder.sync_date == sync_date)
        )
        return result.scalar() > 0

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
