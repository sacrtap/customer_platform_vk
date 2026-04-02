"""
P6-8: Webhook 签名清理任务
每日清理已过期的 Webhook 签名记录，防止数据库膨胀
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.webhooks import WebhookSignature

logger = logging.getLogger(__name__)

# 签名保留天数（5 天）
SIGNATURE_RETENTION_DAYS = 5


async def cleanup_webhook_signatures(session: AsyncSession):
    """
    清理过期的 Webhook 签名记录

    保留最近 5 天的签名记录，删除更早的记录
    """
    try:
        # 计算过期时间阈值
        cutoff_time = datetime.utcnow() - timedelta(days=SIGNATURE_RETENTION_DAYS)

        # 查询过期记录数量
        count_result = await session.execute(
            select(WebhookSignature).where(
                WebhookSignature.timestamp < cutoff_time,
                WebhookSignature.deleted_at.is_(None),
            )
        )
        expired_signatures = count_result.scalars().all()
        expired_count = len(expired_signatures)

        if expired_count == 0:
            logger.debug("✅ Webhook 签名清理：无过期记录")
            return

        # 删除过期记录
        await session.execute(
            delete(WebhookSignature).where(
                WebhookSignature.timestamp < cutoff_time,
                WebhookSignature.deleted_at.is_(None),
            )
        )

        await session.commit()

        logger.info(
            f"✅ Webhook 签名清理完成 | "
            f"删除记录数：{expired_count} | "
            f"保留天数：{SIGNATURE_RETENTION_DAYS} | "
            f"截止时间：{cutoff_time.isoformat()}"
        )

    except Exception as e:
        logger.error(f"❌ Webhook 签名清理失败：{str(e)}")
        await session.rollback()
        raise
