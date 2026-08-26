"""API-Key 管理服务"""

import hashlib
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.api_key import ApiKey

# Key 格式: vk_ + 32 字符随机字符串
KEY_PREFIX = "vk_"
KEY_RANDOM_LENGTH = 32
DISPLAY_PREFIX_LENGTH = 8  # 列表展示前 8 位


class ApiKeyService:
    """API-Key 服务类"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    @staticmethod
    def _generate_key() -> str:
        """生成随机 API-Key 明文"""
        return KEY_PREFIX + secrets.token_urlsafe(KEY_RANDOM_LENGTH)[:KEY_RANDOM_LENGTH]

    @staticmethod
    def _hash_key(key: str) -> str:
        """计算 API-Key 的 SHA-256 哈希"""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _get_display_prefix(key: str) -> str:
        """获取用于列表展示的前缀"""
        return key[:DISPLAY_PREFIX_LENGTH]

    async def create_key(
        self,
        name: str,
        created_by: Optional[int] = None,
        description: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> tuple[ApiKey, str]:
        """
        创建 API-Key

        Returns:
            (ApiKey 对象, 明文 Key) — 明文 Key 仅此一次返回

        Raises:
            ValueError: 当名称为空时
        """
        if not name or not name.strip():
            raise ValueError("API-Key 名称不能为空")

        raw_key = self._generate_key()
        key_hash = self._hash_key(raw_key)
        key_prefix = self._get_display_prefix(raw_key)

        api_key = ApiKey(
            name=name.strip(),
            key_prefix=key_prefix,
            key_hash=key_hash,
            status="active",
            description=description,
            created_by=created_by,
            expires_at=expires_at,
        )

        self.db_session.add(api_key)
        await self.db_session.commit()
        await self.db_session.refresh(api_key)

        return api_key, raw_key

    async def get_all(self, page: int = 1, page_size: int = 20) -> tuple[list[ApiKey], int]:
        """
        分页获取 API-Key 列表

        Returns:
            (API-Key 列表, 总数)
        """
        # 查询总数
        count_stmt = select(func.count()).select_from(ApiKey).where(ApiKey.deleted_at.is_(None))
        total_result = await self.db_session.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分页查询
        stmt = (
            select(ApiKey)
            .where(ApiKey.deleted_at.is_(None))
            .order_by(ApiKey.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db_session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_id(self, key_id: int) -> Optional[ApiKey]:
        """根据 ID 获取 API-Key"""
        result = await self.db_session.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def toggle_status(self, key_id: int) -> Optional[ApiKey]:
        """
        切换 API-Key 状态（active ↔ disabled）

        Returns:
            更新后的 ApiKey 对象，或 None（不存在时）
        """
        api_key = await self.get_by_id(key_id)
        if not api_key:
            return None

        api_key.status = "disabled" if api_key.status == "active" else "active"  # pyright: ignore[reportAttributeAccessIssue]
        await self.db_session.commit()
        await self.db_session.refresh(api_key)

        return api_key

    async def soft_delete(self, key_id: int) -> bool:
        """
        软删除 API-Key

        Returns:
            True: 删除成功
            False: API-Key 不存在
        """
        api_key = await self.get_by_id(key_id)
        if not api_key:
            return False

        api_key.deleted_at = datetime.utcnow()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db_session.commit()

        return True

    async def verify_key(self, raw_key: str) -> Optional[ApiKey]:
        """
        验证 API-Key（用于开放平台认证）

        Returns:
            ApiKey 对象（有效），或 None（无效/停用/过期）
        """
        if not raw_key:
            return None

        key_hash = self._hash_key(raw_key)
        result = await self.db_session.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.status == "active",
                ApiKey.deleted_at.is_(None),
            )
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            return None

        # 检查是否过期
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None

        return api_key

    async def update_last_used(self, key_id: int) -> None:
        """更新最后使用时间（fire-and-forget，不阻塞响应）"""
        await self.db_session.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(last_used_at=datetime.utcnow())
        )
        await self.db_session.commit()
