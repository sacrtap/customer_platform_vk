"""Token 黑名单服务"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.token_blacklist import TokenBlacklist


class TokenBlacklistService:
    """Token 黑名单服务类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_to_blacklist(
        self, jti: str, token_type: str, expires_at: datetime
    ) -> None:
        """
        将 Token 加入黑名单

        Args:
            jti: Token 的唯一标识
            token_type: Token 类型 (access/refresh)
            expires_at: Token 过期时间
        """
        blacklist_entry = TokenBlacklist(
            jti=jti,
            token_type=token_type,
            expires_at=expires_at,
        )
        self.session.add(blacklist_entry)
        await self.session.commit()

    async def is_blacklisted(self, jti: str) -> bool:
        """
        检查 Token 是否在黑名单中

        Args:
            jti: Token 的唯一标识

        Returns:
            是否在黑名单中
        """
        query = select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        result = await self.session.execute(query)
        entry = result.scalar_one_or_none()
        return entry is not None

    async def cleanup_expired(self) -> int:
        """
        清理过期的黑名单记录

        Returns:
            清理的记录数
        """
        from sqlalchemy import delete

        now = datetime.utcnow()
        query = delete(TokenBlacklist).where(TokenBlacklist.expires_at < now)
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount or 0
