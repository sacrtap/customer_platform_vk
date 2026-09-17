"""同步任务服务"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SyncTaskLog, SyncTaskLogDetail
from app.models.daily_consumption import DailyConsumption
from app.models.daily_order import DailyOrder
from app.models.sync_task import SyncTask
from app.services.cost_calc import CostCalcService
from app.services.dto import SyncDetail, SyncResult
from app.services.order_sync import OrderSyncService
from app.utils.timezone import local_date_to_utc_start

logger = logging.getLogger(__name__)


class SyncTaskService:
    """同步任务服务"""

    def __init__(self, db: AsyncSession, redis_client=None, external_engine=None):
        self.db = db
        self.redis_client = redis_client
        self.external_engine = external_engine

    async def create_task(
        self,
        start_date: date,
        end_date: date,
        sync_mode: str,
        operator_id: Optional[int] = None,
    ) -> SyncTask:
        """创建同步任务

        Args:
            start_date: 同步开始日期
            end_date: 同步结束日期
            sync_mode: 同步模式 skip_existing/force_overwrite
            operator_id: 操作人ID；定时任务自动触发时为 None（页面显示「系统自动」）
        """
        # 校验日期范围
        if end_date < start_date:
            raise ValueError("结束日期不能早于开始日期")

        days_delta = (end_date - start_date).days + 1
        if days_delta > 31:
            raise ValueError("日期跨度不能超过31天")

        # 尝试获取分布式锁
        lock_key = f"sync_lock:{start_date}:{end_date}"

        # 先检查数据库中是否有相同日期范围的活跃任务（pending/running）
        # 如果没有活跃任务但 Redis 锁仍然存在（任务已 failed/cancelled/completed 但锁未释放），
        # 则清理过期锁后再获取新锁
        active_task_result = await self.db.execute(
            select(SyncTask).where(
                SyncTask.start_date == start_date,
                SyncTask.end_date == end_date,
                SyncTask.status.in_(["pending", "running"]),
            )
        )
        active_tasks = active_task_result.scalars().all()

        if active_tasks:
            # 检查活跃任务是否实际已卡死（Redis 进度信息已消失或运行超时）
            truly_active = []
            for t in active_tasks:
                progress_key = f"sync_progress:{t.id}"
                has_progress = await self.redis_client.exists(progress_key)  # pyright: ignore[reportOptionalMemberAccess]
                if has_progress:
                    # Redis 进度仍存在，任务可能确实在运行
                    # 但再检查运行时间是否超时（超过 30 分钟视为卡死）
                    if t.created_at:
                        running_minutes = (datetime.now() - t.created_at).total_seconds() / 60
                        if running_minutes > 30:
                            logger.warning(
                                f"活跃任务 {t.id} 运行已超过 30 分钟（{running_minutes:.1f}分钟），"
                                f"判定为卡死，标记为 failed"
                            )
                            t.status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
                            t.error_message = (
                                f"任务运行超过 30 分钟（实际 {running_minutes:.1f} 分钟），"
                                f"判定为卡死并自动标记为失败"
                            )
                            t.completed_at = datetime.now(timezone.utc)  # pyright: ignore[reportAttributeAccessIssue]
                            await self.db.commit()
                            # 清理该任务的 Redis 进度和锁
                            await self.redis_client.delete(progress_key)  # pyright: ignore[reportOptionalMemberAccess]
                            stale_lock = f"sync_lock:{t.start_date}:{t.end_date}"
                            await self.redis_client.delete(stale_lock)  # pyright: ignore[reportOptionalMemberAccess]
                        else:
                            truly_active.append(t)
                    else:
                        truly_active.append(t)
                else:
                    # Redis 进度信息已消失，任务执行进程已异常终止
                    logger.warning(
                        f"活跃任务 {t.id} 的 Redis 进度信息已消失，"
                        f"判定为进程异常终止，标记为 failed"
                    )
                    t.status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
                    t.error_message = "任务执行进程异常终止（Redis 进度信息已消失）"
                    t.completed_at = datetime.now(timezone.utc)  # pyright: ignore[reportAttributeAccessIssue]
                    await self.db.commit()
                    # 清理该任务的锁
                    stale_lock = f"sync_lock:{t.start_date}:{t.end_date}"
                    await self.redis_client.delete(stale_lock)  # pyright: ignore[reportOptionalMemberAccess]

            if truly_active:
                # 确实有活跃任务在运行，拒绝创建
                raise Exception("已有相同周期的同步任务正在执行")

        # 没有活跃任务，清理可能存在的过期锁
        await self.redis_client.delete(lock_key)  # pyright: ignore[reportOptionalMemberAccess]

        # 获取新锁
        lock_acquired = await self.redis_client.set(  # pyright: ignore[reportOptionalMemberAccess]
            lock_key,
            "1",
            nx=True,
            ex=1800,  # 30分钟TTL
        )
        if not lock_acquired:
            # 极端情况：并发竞争，锁刚被其他请求获取
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
                executed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            self.db.add(audit_log)
            await self.db.commit()

            # 初始化 Redis 进度
            await self._update_redis_progress(task)

            return task
        except Exception:
            # 创建失败时释放锁
            await self.redis_client.delete(lock_key)  # pyright: ignore[reportOptionalMemberAccess]
            raise

    async def execute_task(self, task_id: UUID) -> None:
        """执行同步任务（后台异步）"""
        logger.info(f"[{task_id}] 开始执行同步任务")

        lock_key = None  # 初始化为 None，防止 db.get 失败时 finally 块 NameError
        cancel_key = f"sync_cancel:{task_id}"  # 取消标志 key

        # 重新加载任务对象，确保在当前 session 上下文中
        task = await self.db.get(SyncTask, task_id)
        if not task:
            logger.error(f"[{task_id}] 任务不存在")
            raise ValueError(f"任务不存在: {task_id}")

        logger.info(
            f"[{task_id}] 任务信息: 周期 {task.start_date} ~ {task.end_date}, 模式 {task.sync_mode}"
        )
        lock_key = f"sync_lock:{task.start_date}:{task.end_date}"

        try:
            # 检查任务是否在 pending 阶段已被取消
            if await self.redis_client.exists(cancel_key):  # pyright: ignore[reportOptionalMemberAccess]
                logger.info(f"[{task_id}] 任务在 pending 阶段已被取消")
                task.status = "cancelled"  # pyright: ignore[reportAttributeAccessIssue]
                task.completed_at = datetime.now(timezone.utc)  # pyright: ignore[reportAttributeAccessIssue]
                await self.db.commit()
                await self._update_redis_progress(task)
                return

            # 更新状态为 running
            logger.info(f"[{task_id}] 更新状态为 running")
            task.status = "running"  # pyright: ignore[reportAttributeAccessIssue]
            await self.db.commit()
            await self._update_redis_progress(task)

            start_time = datetime.now(timezone.utc)

            # 执行明细收集器：同步链路各环节产生的 warning/error/info 明细，
            # 任务结束（成功或异常）时一次性落库
            details: List[SyncDetail] = []

            try:
                # 生成日期列表
                current_date = task.start_date
                dates = []
                while current_date <= task.end_date:  # pyright: ignore[reportGeneralTypeIssues]
                    dates.append(current_date)
                    current_date += timedelta(days=1)  # pyright: ignore[reportOperatorIssue]

                logger.info(
                    f"[{task_id}] 待处理日期: {len(dates)} 天, 从 {dates[0]} 到 {dates[-1]}"
                )

                # 逐天执行
                for idx, sync_date in enumerate(dates):
                    # 将 date 转为 UTC datetime（供下游服务使用）
                    sync_date_dt = local_date_to_utc_start(sync_date.isoformat())
                    logger.info(f"[{task_id}] 处理第 {idx + 1}/{len(dates)} 天: {sync_date}")

                    # 检查取消标志
                    if await self.redis_client.exists(cancel_key):  # pyright: ignore[reportOptionalMemberAccess]
                        logger.info(f"[{task_id}] 检测到取消标志，停止处理")
                        task.status = "cancelled"  # pyright: ignore[reportAttributeAccessIssue]
                        task.completed_at = datetime.now(timezone.utc)  # pyright: ignore[reportAttributeAccessIssue]
                        duration = (task.completed_at - start_time).total_seconds()
                        await self._update_audit_log(task, "cancelled", duration)
                        await self.db.commit()
                        await self._update_redis_progress(task)
                        return  # 提前退出，不回滚

                    task.current_date = sync_date  # pyright: ignore[reportAttributeAccessIssue]
                    await self.db.commit()
                    await self._update_redis_progress(task)

                    try:
                        skip_order_sync = False

                        # skip_existing 模式：分层检查数据完整性
                        if task.sync_mode == "skip_existing":  # pyright: ignore[reportGeneralTypeIssues]
                            has_orders, has_consumptions = await self._check_data_completeness(
                                sync_date_dt
                            )
                            if has_orders and has_consumptions:
                                # 订单和费用数据都存在，整体跳过
                                logger.info(f"[{task_id}] {sync_date} 已有完整数据，跳过")
                                task.skipped_days += 1  # pyright: ignore[reportAttributeAccessIssue]
                                task.completed_days += 1  # pyright: ignore[reportAttributeAccessIssue]
                                details.append(
                                    SyncDetail(
                                        sync_date=sync_date,
                                        level="info",
                                        category="data_check",
                                        message=f"{sync_date} 已有完整数据，跳过同步",
                                    )
                                )
                                await self.db.commit()
                                await self._update_redis_progress(task)
                                continue
                            elif has_orders and not has_consumptions:
                                # 订单已存在但费用缺失，仅补充费用计算
                                logger.info(
                                    f"[{task_id}] {sync_date} 订单已存在但费用缺失，仅计算费用"
                                )
                                skip_order_sync = True

                        # force_overwrite 模式：sync_orders 内部已实现先拉取后清除的逻辑
                        # （_fetch_orders 成功后才 _clear_orders），
                        # 不再在此处预先 _clear_data，避免拉取失败时数据被误删

                        # 同步订单（skip_existing 模式下可能已跳过）
                        if not skip_order_sync:
                            logger.info(f"[{task_id}] {sync_date} 开始同步订单")
                            order_service = OrderSyncService(
                                self.db, external_engine=self.external_engine
                            )
                            order_result = await order_service.sync_orders(
                                sync_date_dt, detail_collector=details
                            )
                            logger.info(
                                f"[{task_id}] {sync_date} 订单同步完成: "
                                f"成功 {order_result.success}, 失败 {order_result.failed}, "
                                f"跳过 {order_result.skipped}, 未匹配 {order_result.unmatched}, "
                                f"消息={order_result.message}"
                            )
                            # 如果有未匹配的订单，记录 warning 便于排查
                            if order_result.unmatched > 0:
                                logger.warning(
                                    f"[{task_id}] {sync_date} 有 {order_result.unmatched} 条订单未匹配到内部客户"
                                )
                        else:
                            order_result = SyncResult(
                                success=0,
                                failed=0,
                                skipped=0,
                                unmatched=0,
                                message="订单已存在，跳过同步",
                            )

                        # 计算费用
                        logger.info(f"[{task_id}] {sync_date} 开始计算费用")
                        cost_service = CostCalcService(self.db)
                        await cost_service.calculate_daily_cost(
                            sync_date_dt, detail_collector=details
                        )
                        logger.info(f"[{task_id}] {sync_date} 费用计算完成")

                        # 刷新 task 对象，因为 sync_orders 和 calculate_daily_cost 内部调用了 commit()
                        # 导致 task 属性过期，后续访问会触发 MissingGreenlet
                        await self.db.refresh(task)

                        # 更新统计
                        task.completed_days += 1  # pyright: ignore[reportAttributeAccessIssue]
                        task.success_count += order_result.success  # pyright: ignore[reportAttributeAccessIssue]
                        task.failed_count += order_result.failed  # pyright: ignore[reportAttributeAccessIssue]
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
                        task.failed_count += 1  # pyright: ignore[reportAttributeAccessIssue]
                        await self.db.commit()

                    # 更新 Redis 进度
                    await self._update_redis_progress(task)

                # 数据完整性校验：检查每个同步日期是否都有数据
                await self._verify_data_completeness(task_id, dates, details)

                # 任务完成 — 根据成功/失败比例确定最终状态
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(f"[{task_id}] 任务执行耗时: {duration:.2f} 秒")

                if task.failed_count > 0 and task.success_count == 0 and task.skipped_days == 0:
                    # 全部失败，无成功无跳过
                    task.status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
                    task.error_message = f"全部 {task.failed_count} 天处理失败，无成功数据"
                    logger.info(f"[{task_id}] 全部失败，状态标记为 failed")
                    audit_status = "failed"
                elif task.failed_count > 0:
                    # 部分失败
                    task.status = "partial"  # pyright: ignore[reportAttributeAccessIssue]
                    task.error_message = (
                        f"部分失败: 成功 {task.success_count} 天, "
                        f"失败 {task.failed_count} 天, 跳过 {task.skipped_days} 天"
                    )
                    logger.info(f"[{task_id}] 部分失败，状态标记为 partial")
                    audit_status = "partial"
                else:
                    task.status = "completed"  # pyright: ignore[reportAttributeAccessIssue]
                    task.error_message = None  # pyright: ignore[reportAttributeAccessIssue]
                    logger.info(f"[{task_id}] 全部成功，状态标记为 completed")
                    audit_status = "success"

                task.completed_at = datetime.now(timezone.utc)  # pyright: ignore[reportAttributeAccessIssue]

                # 更新审计日志
                await self._update_audit_log(
                    task,
                    audit_status,
                    duration,  # pyright: ignore[reportGeneralTypeIssues]
                    task.error_message,
                )
                logger.info(f"[{task_id}] 审计日志已更新")

            except Exception as e:
                logger.error(
                    f"[{task_id}] 任务执行过程中发生异常: {type(e).__name__}: {e}", exc_info=True
                )
                # 记录任务级错误明细（失败任务也可查明细）
                details.append(
                    SyncDetail(
                        sync_date=task.start_date,  # pyright: ignore[reportGeneralTypeIssues]
                        level="error",
                        category="system",
                        message=f"任务执行过程中发生异常: {type(e).__name__}: {e}",
                    )
                )
                task.status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
                task.error_message = str(e)  # pyright: ignore[reportAttributeAccessIssue]
                task.completed_at = datetime.now(timezone.utc)  # pyright: ignore[reportAttributeAccessIssue]
                duration = (task.completed_at - start_time).total_seconds()

                await self._update_audit_log(task, "failed", duration, str(e))

            finally:
                logger.info(f"[{task_id}] 提交最终状态到数据库")
                await self.db.commit()
                # 任务结束（成功或异常）一次性写入执行明细
                await self._persist_details(task.id, details)
                await self._update_redis_progress(task)
                # 清除消费分析缓存，确保前端能获取最新数据
                try:
                    from app.cache.base import cache_service

                    await cache_service.invalidate_pattern("cache:analytics_*")
                    await cache_service.invalidate_pattern("cache:billing_consumption:*")
                    logger.info(f"[{task_id}] 已清除消费分析缓存")
                except Exception as cache_err:
                    logger.warning(f"[{task_id}] 清除缓存失败: {cache_err}")

        finally:
            # 无论发生什么，确保释放锁和清理取消标志
            logger.info(f"[{task_id}] 清理 Redis 锁和取消标志")
            if lock_key:
                await self.redis_client.delete(lock_key)  # pyright: ignore[reportOptionalMemberAccess]
            await self.redis_client.delete(cancel_key)  # pyright: ignore[reportOptionalMemberAccess]
            logger.info(f"[{task_id}] 任务执行流程结束")

    async def cancel_task(self, task_id: UUID) -> bool:
        """取消同步任务

        - pending: 后台执行尚未开始，立即标记为 cancelled 并释放锁
        - running: 后台执行进行中，设置 Redis 取消标志 + 立即更新状态为 cancelled，
          执行循环检测到标志后会跳过剩余天数，锁由 execute_task 的 finally 块释放
        """
        task = await self.db.get(SyncTask, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if task.status not in ["pending", "running"]:
            raise ValueError(f"任务状态为 {task.status}，无法取消")

        original_status = task.status  # 记录原始状态，用于决定是否主动释放锁

        # 设置 Redis 取消标志，供 execute_task 循环检测
        cancel_key = f"sync_cancel:{task_id}"
        await self.redis_client.set(cancel_key, "1", ex=3600)  # pyright: ignore[reportOptionalMemberAccess]

        # 立即更新数据库状态为 cancelled，让前端列表即时反映取消结果
        task.status = "cancelled"  # pyright: ignore[reportAttributeAccessIssue]
        task.completed_at = datetime.now(timezone.utc)  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()

        # 更新 Redis 进度缓存
        await self._update_redis_progress(task)

        # 如果任务原来是 pending 状态（execute_task 尚未启动或尚未执行到 finally 块），
        # 主动释放分布式锁，避免锁残留导致无法重新创建相同日期范围的任务。
        # running 状态的任务锁由 execute_task 的 finally 块负责释放。
        if original_status == "pending":  # pyright: ignore[reportGeneralTypeIssues]
            lock_key = f"sync_lock:{task.start_date}:{task.end_date}"
            try:
                await self.redis_client.delete(lock_key)  # pyright: ignore[reportOptionalMemberAccess]
                logger.info(f"[{task_id}] 已释放分布式锁 {lock_key}（pending 任务取消）")
            except Exception as e:
                logger.warning(f"[{task_id}] 释放锁失败，将等待自动过期: {e}")

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
            if not await self.redis_client.exists(progress_key):  # pyright: ignore[reportOptionalMemberAccess]
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
                task.status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
                task.error_message = reason  # pyright: ignore[reportAttributeAccessIssue]
                task.completed_at = now  # pyright: ignore[reportAttributeAccessIssue]
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
            task.status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
            task.error_message = f"任务运行超过 {max_running_minutes} 分钟，疑似卡住"  # pyright: ignore[reportAttributeAccessIssue]
            task.completed_at = datetime.now()  # pyright: ignore[reportAttributeAccessIssue]
            await self.db.commit()

        return len(stuck_tasks)

    async def get_progress(self, task_id: UUID) -> dict:
        """获取任务进度"""
        # 优先从 Redis 读取
        progress_key = f"sync_progress:{task_id}"
        progress_data = await self.redis_client.hgetall(progress_key)  # pyright: ignore[reportOptionalMemberAccess]

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
        percentage: float = task.completed_days / task.total_days if task.total_days > 0 else 0.0  # pyright: ignore[reportGeneralTypeIssues, reportAssignmentType]

        return {
            "task_id": str(task.id),
            "status": task.status,
            "sync_mode": task.sync_mode,
            "total_days": task.total_days,
            "completed_days": task.completed_days,
            "skipped_days": task.skipped_days,
            "current_date": task.current_date.isoformat() if task.current_date else None,  # pyright: ignore[reportGeneralTypeIssues]
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
        status: str = None,  # pyright: ignore[reportArgumentType]
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

        # 一次性聚合本页任务的明细级别计数（避免 N+1）
        detail_counts: Dict[UUID, Dict[str, int]] = {}
        if tasks:
            count_result = await self.db.execute(
                select(
                    SyncTaskLogDetail.task_id,
                    SyncTaskLogDetail.level,
                    func.count(SyncTaskLogDetail.id),
                )
                .where(SyncTaskLogDetail.task_id.in_([t.id for t in tasks]))
                .group_by(SyncTaskLogDetail.task_id, SyncTaskLogDetail.level)
            )
            for task_id, level, cnt in count_result.all():
                detail_counts.setdefault(task_id, {"info": 0, "warning": 0, "error": 0})[level] = (
                    cnt
                )

        return {
            "list": [self._task_to_dict(task, detail_counts.get(task.id)) for task in tasks],
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

    @staticmethod
    def _execution_status(status: str, error_count: int, warning_count: int) -> str:
        """执行信息三态：错误 > 警告 > 正常

        历史任务（无明细，counts 均为 0）按任务状态回退：
        failed → error；partial → warning；其余 → normal。
        """
        if error_count > 0:
            return "error"
        if warning_count > 0:
            return "warning"
        if status == "failed":
            return "error"
        if status == "partial":
            return "warning"
        return "normal"

    def _task_to_dict(self, task: SyncTask, detail_counts: Optional[Dict[str, int]] = None) -> dict:
        """将任务对象转换为字典"""
        info_count = (detail_counts or {}).get("info", 0)
        warning_count = (detail_counts or {}).get("warning", 0)
        error_count = (detail_counts or {}).get("error", 0)
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
            "execution_status": self._execution_status(task.status, error_count, warning_count),
            "info_count": info_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "created_at": task.created_at.isoformat() if task.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }

    async def _update_redis_progress(self, task: SyncTask) -> None:
        """更新 Redis 进度"""
        progress_key = f"sync_progress:{task.id}"
        total_days = task.total_days or 0
        completed_days = task.completed_days or 0
        percentage = int((completed_days / total_days) * 100) if total_days > 0 else 0  # pyright: ignore[reportGeneralTypeIssues, reportArgumentType]

        progress_data = {
            "status": task.status,
            "sync_mode": task.sync_mode,
            "total_days": str(task.total_days),
            "completed_days": str(task.completed_days),
            "skipped_days": str(task.skipped_days),
            "current_date": task.current_date.isoformat() if task.current_date else "",  # pyright: ignore[reportGeneralTypeIssues]
            "success_count": str(task.success_count),
            "failed_count": str(task.failed_count),
            "percentage": str(percentage),
            "error_message": task.error_message or "",
        }

        await self.redis_client.hset(progress_key, mapping=progress_data)  # pyright: ignore[reportOptionalMemberAccess]
        await self.redis_client.expire(
            progress_key, 3600
        )  # 1小时TTL  # pyright: ignore[reportOptionalMemberAccess]

    async def _verify_data_completeness(
        self,
        task_id: UUID,
        dates: list,
        detail_collector: Optional[List[SyncDetail]] = None,
    ) -> None:
        """同步任务完成后，验证每个日期是否都有订单数据

        检查 daily_orders 和 daily_consumptions 表，如果某天数据缺失
        则记录 warning 日志（并写入执行明细），便于后续排查。
        """
        from sqlalchemy import func

        for sync_date in dates:
            sync_date_dt = local_date_to_utc_start(sync_date.isoformat())
            day_end = sync_date_dt + timedelta(days=1)

            # 检查订单数
            order_result = await self.db.execute(
                select(func.count(DailyOrder.id)).where(
                    DailyOrder.sync_date >= sync_date_dt,
                    DailyOrder.sync_date < day_end,
                )
            )
            order_count = order_result.scalar() or 0

            # 检查消费记录数
            consumption_result = await self.db.execute(
                select(func.count(DailyConsumption.id)).where(
                    DailyConsumption.consumption_date >= sync_date_dt,
                    DailyConsumption.consumption_date < day_end,
                )
            )
            consumption_count = consumption_result.scalar() or 0

            if order_count == 0:
                logger.warning(
                    f"[{task_id}] 数据完整性校验: {sync_date} 无订单数据，"
                    f"可能是外部数据源该天确实无订单，或同步异常"
                )
                if detail_collector is not None:
                    detail_collector.append(
                        SyncDetail(
                            sync_date=sync_date,
                            level="warning",
                            category="data_check",
                            message=f"数据完整性校验: {sync_date} 无订单数据，"
                            f"可能是外部数据源该天确实无订单，或同步异常",
                        )
                    )
            if consumption_count == 0:
                logger.warning(
                    f"[{task_id}] 数据完整性校验: {sync_date} 无消费记录，可能是费用计算异常"
                )
                if detail_collector is not None:
                    detail_collector.append(
                        SyncDetail(
                            sync_date=sync_date,
                            level="warning",
                            category="data_check",
                            message=f"数据完整性校验: {sync_date} 无消费记录，可能是费用计算异常",
                        )
                    )

    async def _persist_details(self, task_id: UUID, details: List[SyncDetail]) -> None:
        """批量写入任务执行明细（独立提交，失败不影响主流程）"""
        if not details:
            return
        try:
            from sqlalchemy import insert

            rows = [
                {
                    "task_id": task_id,
                    "sync_date": d.sync_date,
                    "level": d.level,
                    "category": d.category,
                    "message": d.message,
                    "customer_id": d.customer_id,
                    "customer_name": d.customer_name,
                    "external_customer_id": d.external_customer_id,
                    "company_name": d.company_name,
                    "order_code": d.order_code,
                    "record_count": d.record_count,
                }
                for d in details
            ]
            await self.db.execute(insert(SyncTaskLogDetail), rows)
            await self.db.commit()
            logger.info(f"[{task_id}] 已写入 {len(rows)} 条执行明细")
        except Exception as e:
            logger.error(f"[{task_id}] 写入执行明细失败: {e}", exc_info=True)
            await self.db.rollback()

    async def _check_data_completeness(self, sync_date: datetime) -> tuple[bool, bool]:
        """检查指定日期的订单数据和费用数据是否都已存在

        分别查询 DailyOrder 和 DailyConsumption 表，判断数据完整性。
        用于 skip_existing 模式下的分层跳过决策：
        - (True, True)   → 订单和费用都存在，整体跳过
        - (True, False)  → 订单存在但费用缺失，仅补充费用计算
        - (False, *)     → 订单不存在，执行完整同步

        Args:
            sync_date: 同步日期（UTC datetime）

        Returns:
            (has_orders, has_consumptions)
        """
        from sqlalchemy import func

        day_end = sync_date + timedelta(days=1)
        order_result = await self.db.execute(
            select(func.count(DailyOrder.id)).where(
                DailyOrder.sync_date >= sync_date,
                DailyOrder.sync_date < day_end,
            )
        )
        has_orders = order_result.scalar() > 0  # pyright: ignore[reportOptionalOperand]

        consumption_result = await self.db.execute(
            select(func.count(DailyConsumption.id)).where(
                DailyConsumption.consumption_date >= sync_date,
                DailyConsumption.consumption_date < day_end,
            )
        )
        has_consumptions = consumption_result.scalar() > 0  # pyright: ignore[reportOptionalOperand]

        return has_orders, has_consumptions

    async def _clear_data(self, sync_date: datetime) -> None:
        """清空指定日期的数据"""
        day_end = sync_date + timedelta(days=1)
        # 删除订单
        await self.db.execute(
            DailyOrder.__table__.delete().where(  # pyright: ignore[reportAttributeAccessIssue]
                DailyOrder.sync_date >= sync_date,
                DailyOrder.sync_date < day_end,
            )
        )
        # 删除消费记录
        await self.db.execute(
            DailyConsumption.__table__.delete().where(  # pyright: ignore[reportAttributeAccessIssue]
                DailyConsumption.consumption_date >= sync_date,
                DailyConsumption.consumption_date < day_end,
            )
        )
        await self.db.commit()

    async def _update_audit_log(
        self,
        task: SyncTask,
        status: str,
        duration: float,
        error: str = None,  # pyright: ignore[reportArgumentType]
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
                executed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
