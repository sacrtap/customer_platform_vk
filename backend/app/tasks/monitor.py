"""定时任务监控工具

提供任务执行追踪、状态记录和健康检查功能。
执行结果存储在 Redis 中，key 格式: task_monitor:{job_id}
"""

import functools
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Redis key 前缀
MONITOR_KEY_PREFIX = "task_monitor"

# 监控数据保留时间（7 天）
MONITOR_TTL = 7 * 24 * 3600


async def record_task_result(
    redis_client,
    job_id: str,
    job_name: str,
    status: str,
    duration_ms: int,
    error: Optional[str] = None,
    result: Optional[Any] = None,
):
    """记录任务执行结果到 Redis"""
    try:
        data = {
            "job_id": job_id,
            "job_name": job_name,
            "status": status,  # success / failed
            "duration_ms": duration_ms,
            "executed_at": datetime.utcnow().isoformat(),
            "error": error,
            "result": str(result) if result else None,
        }
        key = f"{MONITOR_KEY_PREFIX}:{job_id}"
        await redis_client.setex(key, MONITOR_TTL, json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Failed to record task result for {job_id}: {e}")


async def get_task_results(redis_client, job_ids: list) -> list:
    """获取多个任务的最近执行结果"""
    results = []
    for job_id in job_ids:
        try:
            key = f"{MONITOR_KEY_PREFIX}:{job_id}"
            data = await redis_client.get(key)
            if data:
                results.append(json.loads(data))
            else:
                results.append({"job_id": job_id, "status": "never_executed"})
        except Exception as e:
            logger.warning(f"Failed to get task result for {job_id}: {e}")
            results.append({"job_id": job_id, "status": "error", "error": str(e)})
    return results


def monitored_task(job_id: str, job_name: str):
    """任务监控装饰器

    自动记录任务的执行状态、耗时和错误信息到 Redis。

    用法:
        @monitored_task("generate_monthly_invoices", "月度结算单自动生成")
        async def generate_monthly_invoices(session):
            ...
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.monotonic()
            logger.info(f"📋 任务开始: {job_name} ({job_id})")

            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(f"✅ 任务完成: {job_name} ({job_id}), 耗时 {duration_ms}ms")

                # 记录到 Redis
                try:
                    from ..cache.base import cache_service

                    redis_client = await cache_service._get_redis()
                    await record_task_result(
                        redis_client, job_id, job_name, "success", duration_ms, result=result
                    )
                except Exception:
                    pass  # Redis 记录失败不影响任务执行

                return result

            except Exception as e:
                duration_ms = int((time.monotonic() - start_time) * 1000)
                logger.error(
                    f"❌ 任务失败: {job_name} ({job_id}), 耗时 {duration_ms}ms, 错误: {e}",
                    exc_info=True,
                )

                # 记录到 Redis
                try:
                    from ..cache.base import cache_service

                    redis_client = await cache_service._get_redis()
                    await record_task_result(
                        redis_client, job_id, job_name, "failed", duration_ms, error=str(e)
                    )
                except Exception:
                    pass

                raise

        return wrapper

    return decorator
