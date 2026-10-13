"""余额白名单服务

开放平台 /api/v1/balances 接口对白名单客户返回静态余额（优先于计算余额）。
管理操作：列表、按 ERP 批量导入、单独添加、编辑余额、移出白名单。
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import outerjoin
from sqlalchemy.sql.elements import ColumnElement

from ..models.balance_whitelist import BalanceWhitelist
from ..models.customers import Customer

DEFAULT_STATIC_BALANCE = Decimal("1000.00")


class BalanceWhitelistService:
    """余额白名单服务类"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    # ========== 查询 ==========

    async def get_all(
        self, page: int = 1, page_size: int = 20, keyword: Optional[str] = None
    ) -> tuple[list[dict], int]:
        """
        分页获取白名单列表（JOIN 客户表展示公司 ID/名称/ERP）

        Query:
        - keyword: 按客户名称模糊或公司 ID 精确过滤
        """
        base_conditions: list[ColumnElement[bool]] = [BalanceWhitelist.deleted_at.is_(None)]
        if keyword:
            kw = keyword.strip()
            if kw:
                # 公司 ID 精确匹配（整数）或名称模糊匹配
                try:
                    company_id = int(kw)
                    base_conditions.append(
                        or_(Customer.company_id == company_id, Customer.name.ilike(f"%{kw}%"))
                    )
                except ValueError:
                    base_conditions.append(Customer.name.ilike(f"%{kw}%"))

        count_stmt = (
            select(func.count(BalanceWhitelist.id))
            .select_from(
                outerjoin(BalanceWhitelist, Customer, BalanceWhitelist.customer_id == Customer.id)
            )
            .where(*base_conditions)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(
                BalanceWhitelist.id,
                BalanceWhitelist.customer_id,
                Customer.company_id,
                Customer.name,
                Customer.erp_system,
                BalanceWhitelist.static_balance,
                BalanceWhitelist.remark,
                BalanceWhitelist.created_at,
            )
            .select_from(
                outerjoin(BalanceWhitelist, Customer, BalanceWhitelist.customer_id == Customer.id)
            )
            .where(*base_conditions)
            .order_by(BalanceWhitelist.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        items = []
        for row in rows:
            (
                wid,
                customer_id,
                company_id,
                name,
                erp_system,
                static_balance,
                remark,
                created_at,
            ) = row
            items.append(
                {
                    "id": wid,
                    "customer_id": customer_id,
                    "company_id": company_id,
                    "customer_name": name,
                    "erp_system": erp_system,
                    "static_balance": float(static_balance),
                    "remark": remark,
                    "created_at": created_at.isoformat() if created_at else None,
                }
            )
        return items, total

    async def list_whitelist_map(self) -> dict[int, float]:
        """
        获取白名单映射（customer_id → static_balance），供开放平台接口覆盖余额。

        Returns:
            dict[客户主键 id, 静态余额 float]
        """
        stmt = select(BalanceWhitelist.customer_id, BalanceWhitelist.static_balance).where(
            BalanceWhitelist.deleted_at.is_(None)
        )
        result = await self.db.execute(stmt)
        return {cid: float(sb) for cid, sb in result.all()}

    # ========== 写操作（事务：async with db.begin()） ==========

    async def batch_import_by_erp(
        self, erp_system_value: str, dry_run: bool = False
    ) -> tuple[int, int]:
        """
        按 ERP 名单批量导入该 ERP 下所有有效客户（未删除、未停用）。

        幂等语义（AC6）：
        - 已存在（未删）→ 跳过，不覆盖其既有静态余额
        - 存在软删记录 → 恢复记录，保留既有 static_balance（不覆盖人工调整值）
        - 全新客户 → 新建，静态余额默认 1000 元

        dry_run=True 时仅计算「将导入 / 将跳过」数量，不落库、无副作用
        （前端预检展示后二次确认再真实导入，与客户导入 dry_run 契约一致）。

        Returns:
            (imported, skipped)
        """
        # 查询该 ERP 下所有有效客户
        customer_stmt = (
            select(Customer.id)
            .where(
                Customer.erp_system == erp_system_value,
                Customer.deleted_at.is_(None),
                Customer.is_disabled.isnot(True),
            )
            .order_by(Customer.id.asc())
        )
        customer_result = await self.db.execute(customer_stmt)
        customer_ids = [row[0] for row in customer_result.all()]

        if not customer_ids:
            return 0, 0

        # 批量查询白名单现状（含软删记录，区分跳过/恢复）
        whitelist_stmt = select(
            BalanceWhitelist.id, BalanceWhitelist.customer_id, BalanceWhitelist.deleted_at
        ).where(BalanceWhitelist.customer_id.in_(customer_ids))
        whitelist_result = await self.db.execute(whitelist_stmt)

        existing_active: dict[int, int] = {}  # customer_id -> id（未删）
        existing_deleted: dict[int, int] = {}  # customer_id -> id（软删）
        for wid, cid, deleted_at in whitelist_result.all():
            if deleted_at is None:
                existing_active[cid] = wid
            else:
                existing_deleted[cid] = wid

        imported = 0
        skipped = 0
        now = datetime.utcnow()

        for cid in customer_ids:
            if cid in existing_active:
                skipped += 1
                continue
            if cid in existing_deleted:
                if not dry_run:
                    # 恢复软删记录：保留既有 static_balance，不覆盖
                    record = await self.db.get(BalanceWhitelist, existing_deleted[cid])
                    if record is not None:
                        record.deleted_at = None  # pyright: ignore[reportAttributeAccessIssue]
                        record.updated_at = now  # pyright: ignore[reportAttributeAccessIssue]
                imported += 1
                continue
            if not dry_run:
                self.db.add(
                    BalanceWhitelist(
                        customer_id=cid,
                        static_balance=DEFAULT_STATIC_BALANCE,
                    )
                )
            imported += 1

        if not dry_run:
            await self.db.commit()  # pyright: ignore[reportGeneralTypeIssues]
        return imported, skipped

    async def add(
        self, customer_id: int, static_balance: Decimal | None = None
    ) -> BalanceWhitelist:
        """
        单独添加单个客户到白名单。

        Raises:
            ValueError: 客户不存在/已停用；客户已在白名单中；余额格式非法
        """
        balance = self._validate_balance(
            static_balance if static_balance is not None else DEFAULT_STATIC_BALANCE
        )

        customer_result = await self.db.execute(
            select(Customer.id).where(
                Customer.id == customer_id,
                Customer.deleted_at.is_(None),
                Customer.is_disabled.isnot(True),
            )
        )
        customer = customer_result.scalar_one_or_none()
        if not customer:
            raise ValueError("客户不存在或已停用")

        existing_result = await self.db.execute(
            select(BalanceWhitelist).where(
                BalanceWhitelist.customer_id == customer_id,
            )
        )
        existing = existing_result.scalars().first()
        if existing is not None and existing.deleted_at is None:
            raise ValueError("该客户已在余额白名单中")
        if existing is not None:
            # 恢复软删记录并更新余额
            existing.deleted_at = None  # pyright: ignore[reportAttributeAccessIssue]
            existing.static_balance = balance  # pyright: ignore[reportAttributeAccessIssue]
            await self.db.commit()  # pyright: ignore[reportGeneralTypeIssues]
            return existing

        record = BalanceWhitelist(customer_id=customer_id, static_balance=balance)
        self.db.add(record)
        await self.db.flush()  # pyright: ignore[reportGeneralTypeIssues]
        await self.db.commit()  # pyright: ignore[reportGeneralTypeIssues]
        return record

    async def update(
        self,
        id: int,
        static_balance: Decimal,
        remark: str | None = None,
        remark_provided: bool = False,
    ) -> Optional[BalanceWhitelist]:
        """
        编辑白名单客户静态余额（可选同时更新备注）。

        Args:
            id: 白名单记录 id
            static_balance: 新静态余额
            remark: 新备注；未提供时不改动
            remark_provided: 是否显式提供了 remark（区分「未传」与「传空/清空」）

        Raises:
            ValueError: 余额格式非法；备注超长
        """
        balance = self._validate_balance(static_balance)
        normalized_remark = self._normalize_remark(remark) if remark_provided else None

        record = await self.db.get(BalanceWhitelist, id)
        if record is None or record.deleted_at is not None:
            return None
        record.static_balance = balance  # pyright: ignore[reportAttributeAccessIssue]
        if remark_provided:
            record.remark = normalized_remark  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()  # pyright: ignore[reportGeneralTypeIssues]
        return record

    async def soft_delete(self, id: int) -> bool:
        """移出白名单（软删除）"""
        record = await self.db.get(BalanceWhitelist, id)
        if record is None or record.deleted_at is not None:
            return False
        record.deleted_at = datetime.utcnow()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()  # pyright: ignore[reportGeneralTypeIssues]
        return True

    # ========== 校验 ==========

    @staticmethod
    def _validate_balance(value: Decimal) -> Decimal:
        """静态余额校验：非负、可解析为 DECIMAL(12,2)。返回规范化值。"""
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("静态余额格式不正确")
        if parsed < 0:
            raise ValueError("静态余额不能为负数")
        return parsed

    @staticmethod
    def _normalize_remark(value: str | None) -> str | None:
        """备注规范化：去首尾空白；空值 → None；超长（>200）报错。"""
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if len(text) > 200:
            raise ValueError("备注最长 200 字符")
        return text
