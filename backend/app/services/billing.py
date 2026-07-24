"""结算与余额管理服务"""

import random
import string
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..models.billing import (
    ConsumptionRecord,
    CustomerBalance,
    Invoice,
    InvoiceItem,
    PricingRule,
    RechargeRecord,
)
from ..models.customers import Customer
from ..models.daily_consumption import DailyConsumption
from ..repository import (
    BalanceRepository,
    BalanceRepositoryProtocol,
    InvoiceRepositoryProtocol,
    PricingRepositoryProtocol,
)


class BalanceService:
    """余额服务类"""

    def __init__(self, balance_repo: BalanceRepositoryProtocol):
        self.balance_repo = balance_repo

    @property
    def db(self) -> AsyncSession:
        return self.balance_repo.db  # pyright: ignore[reportAttributeAccessIssue]

    async def get_balance_by_customer_id(self, customer_id: int) -> Optional[CustomerBalance]:
        """获取客户余额"""
        return await self.balance_repo.get_by_customer_id(customer_id)

    async def get_or_create_balance(self, customer_id: int) -> CustomerBalance:
        """获取或创建客户余额"""
        return await self.balance_repo.get_or_create(customer_id)

    async def recharge(
        self,
        customer_id: int,
        real_amount: Decimal,
        bonus_amount: Decimal,
        operator_id: int,
        payment_proof: Optional[str] = None,
        remark: Optional[str] = None,
    ) -> RechargeRecord:
        """
        客户充值

        Args:
            customer_id: 客户 ID
            real_amount: 实充金额
            bonus_amount: 赠金金额
            operator_id: 操作人 ID
            payment_proof: 支付凭证路径
            remark: 备注

        Returns:
            RechargeRecord
        """
        # 创建充值记录
        record = RechargeRecord(
            customer_id=customer_id,
            real_amount=real_amount,
            bonus_amount=bonus_amount,
            operator_id=operator_id,
            payment_proof=payment_proof,
            remark=remark,
        )
        self.db.add(record)

        # 更新余额
        balance = await self.get_or_create_balance(customer_id)
        balance.real_amount = (balance.real_amount or 0) + real_amount  # pyright: ignore[reportAttributeAccessIssue]
        balance.bonus_amount = (balance.bonus_amount or 0) + bonus_amount  # pyright: ignore[reportAttributeAccessIssue]
        balance.total_amount = (balance.total_amount or 0) + real_amount + bonus_amount  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()
        await self.db.refresh(record)

        return record

    async def batch_import_recharge(
        self,
        rows: List[Dict[str, Any]],
        operator_id: int,
    ) -> Tuple[int, List[str]]:
        """
        批量导入充值

        Args:
            rows: 校验通过的数据行列表，每行包含 customer_id, real_amount, bonus_amount, remark
            operator_id: 操作人 ID

        Returns:
            (success_count, errors)
        """
        success_count = 0
        errors: List[str] = []

        for idx, row in enumerate(rows, start=1):
            customer_id = row["customer_id"]
            real_amount = Decimal(str(row.get("real_amount", 0) or 0))
            bonus_amount = Decimal(str(row.get("bonus_amount", 0) or 0))
            remark = row.get("remark")

            try:
                # 创建充值记录
                record = RechargeRecord(
                    customer_id=customer_id,
                    real_amount=real_amount,
                    bonus_amount=bonus_amount,
                    operator_id=operator_id,
                    payment_proof="批量导入",
                    remark=remark,
                )
                self.db.add(record)

                # 更新余额
                balance = await self.get_or_create_balance(customer_id)
                balance.real_amount = (balance.real_amount or 0) + real_amount  # pyright: ignore[reportAttributeAccessIssue]
                balance.bonus_amount = (balance.bonus_amount or 0) + bonus_amount  # pyright: ignore[reportAttributeAccessIssue]
                balance.total_amount = (balance.total_amount or 0) + real_amount + bonus_amount  # pyright: ignore[reportAttributeAccessIssue]

                await self.db.flush()
                success_count += 1
            except Exception as e:
                errors.append(f"第 {idx} 行：充值失败 - {str(e)}")

        # 统一提交
        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise e

        return success_count, errors

    async def consume(
        self,
        customer_id: int,
        amount: Decimal,
        invoice_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        消费扣款（先赠后实）- 带事务保护和行级锁

        Args:
            customer_id: 客户 ID
            amount: 消费金额
            invoice_id: 关联发票 ID

        Returns:
            (success, message)

        Raises:
            OperationalError: 数据库操作错误（重试后仍失败则抛出）
        """
        # 死锁重试配置
        # - 3 次尝试：平衡死锁恢复与用户体验
        # - 0.1s 最小等待：快速恢复瞬时锁
        # - 1.0s 最大等待：防止过度延迟
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=0.1, max=1.0),
            retry=retry_if_exception_type(OperationalError),
            reraise=True,
        ):
            with attempt:
                # 每次重试获得新的事务边界
                async with self.db.begin():
                    # 使用行级锁获取余额记录，防止并发修改
                    # with_for_update() 会锁定选中的行，其他事务必须等待当前事务提交
                    result = await self.db.execute(
                        select(CustomerBalance)
                        .where(
                            CustomerBalance.customer_id == customer_id,
                            CustomerBalance.deleted_at.is_(None),
                        )
                        .with_for_update()  # SELECT FOR UPDATE - 行级排他锁
                    )
                    balance = result.scalar_one_or_none()

                    if not balance:
                        return False, "客户余额账户不存在"

                    total_balance = (balance.real_amount or 0) + (balance.bonus_amount or 0)
                    if total_balance < amount:  # pyright: ignore[reportGeneralTypeIssues]
                        return False, f"余额不足，当前余额：{total_balance:.2f}元"

                    # 先消耗赠金，再消耗实充
                    remaining = amount
                    bonus_used = Decimal(0)
                    real_used = Decimal(0)

                    if balance.bonus_amount and balance.bonus_amount > 0:  # pyright: ignore[reportGeneralTypeIssues]
                        if balance.bonus_amount >= remaining:  # pyright: ignore[reportGeneralTypeIssues]
                            bonus_used = remaining
                            balance.bonus_amount -= remaining  # pyright: ignore[reportAttributeAccessIssue]
                            remaining = Decimal(0)
                        else:
                            bonus_used = balance.bonus_amount
                            remaining -= balance.bonus_amount
                            balance.bonus_amount = Decimal(0)  # pyright: ignore[reportAttributeAccessIssue]

                    if remaining > 0 and balance.real_amount and balance.real_amount > 0:  # pyright: ignore[reportGeneralTypeIssues]
                        if balance.real_amount >= remaining:  # pyright: ignore[reportGeneralTypeIssues]
                            real_used = remaining
                            balance.real_amount -= remaining  # pyright: ignore[reportAttributeAccessIssue]
                        else:
                            real_used = balance.real_amount
                            balance.real_amount = Decimal(0)  # pyright: ignore[reportAttributeAccessIssue]

                    # 更新总额
                    balance.used_total = (balance.used_total or 0) + amount  # pyright: ignore[reportAttributeAccessIssue]
                    balance.used_bonus = (balance.used_bonus or 0) + bonus_used  # pyright: ignore[reportAttributeAccessIssue]
                    balance.used_real = (balance.used_real or 0) + real_used  # pyright: ignore[reportAttributeAccessIssue]

                    # 创建消费记录
                    consumption = ConsumptionRecord(
                        customer_id=customer_id,
                        invoice_id=invoice_id,
                        amount=amount,
                        bonus_used=bonus_used,
                        real_used=real_used,
                        balance_after=(balance.real_amount or 0) + (balance.bonus_amount or 0),
                    )
                    self.db.add(consumption)

                    # 提交事务
                    await self.db.commit()

                    return True, "扣款成功"

        # 不应到达此处（reraise=True 会抛出最后一次异常）
        return False, "扣款失败：数据库操作超时"

    async def get_recharge_records(
        self,
        customer_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RechargeRecord], int]:
        """获取充值记录列表"""
        stmt = select(RechargeRecord).where(RechargeRecord.deleted_at.is_(None))

        if customer_id:
            stmt = stmt.where(RechargeRecord.customer_id == customer_id)

        # 总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar()

        # 分页
        stmt = stmt.order_by(RechargeRecord.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        records = result.scalars().all()

        return list(records), total  # pyright: ignore[reportReturnType]


class PricingService:
    """定价规则服务类"""

    def __init__(self, pricing_repo: PricingRepositoryProtocol):
        self.pricing_repo = pricing_repo

    @property
    def db(self) -> AsyncSession:
        return self.pricing_repo.db  # pyright: ignore[reportAttributeAccessIssue]

    async def get_pricing_rules(
        self,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        device_type: Optional[str] = None,
        layer_type: Optional[str] = None,
        pricing_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PricingRule], int]:
        """获取定价规则列表（支持分页）"""
        from ..models.customers import Customer

        base_stmt = (
            select(PricingRule)
            .join(Customer, PricingRule.customer_id == Customer.id, isouter=True)
            .where(PricingRule.deleted_at.is_(None), Customer.deleted_at.is_(None))
        )

        if customer_id:
            base_stmt = base_stmt.where(PricingRule.customer_id == customer_id)
        if keyword:
            base_stmt = base_stmt.where(Customer.name.ilike(f"%{keyword}%"))
        if device_type:
            base_stmt = base_stmt.where(PricingRule.device_type == device_type)
        if layer_type:
            base_stmt = base_stmt.where(PricingRule.layer_type == layer_type)
        if pricing_type:
            base_stmt = base_stmt.where(PricingRule.pricing_type == pricing_type)

        # 总数
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar()

        # 分页
        stmt = base_stmt.options(selectinload(PricingRule.customer))
        stmt = stmt.order_by(PricingRule.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        return list(rules), total  # pyright: ignore[reportReturnType]

    async def _check_overlap(
        self,
        customer_id: int,
        device_type: str,
        layer_type: Optional[str],
        effective_date: date,
        expiry_date: Optional[date],
        exclude_id: Optional[int] = None,
    ) -> None:
        """检查是否存在有效期重叠的规则，存在则抛出 ValueError"""
        # 构建 layer_type 匹配条件（处理 NULL 情况）
        if layer_type is None:
            layer_condition = PricingRule.layer_type.is_(None)
        else:
            layer_condition = PricingRule.layer_type == layer_type

        conflict_stmt = select(PricingRule).where(
            PricingRule.customer_id == customer_id,
            PricingRule.device_type == device_type,
            layer_condition,
            PricingRule.deleted_at.is_(None),
        )

        if exclude_id is not None:
            conflict_stmt = conflict_stmt.where(PricingRule.id != exclude_id)

        result = await self.db.execute(conflict_stmt)
        existing_rules = result.scalars().all()

        for rule in existing_rules:
            rule_expiry = rule.expiry_date
            new_expiry = expiry_date

            # 检查有效期是否有交集
            if rule_expiry is None or new_expiry is None:
                if rule_expiry is None and new_expiry is None:
                    raise ValueError("该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠")
                elif rule_expiry is None:
                    if new_expiry >= rule.effective_date:  # pyright: ignore[reportGeneralTypeIssues]
                        raise ValueError(
                            "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                        )
                else:
                    if effective_date <= rule_expiry:  # pyright: ignore[reportGeneralTypeIssues]
                        raise ValueError(
                            "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                        )
            else:
                if effective_date <= rule_expiry and new_expiry >= rule.effective_date:  # pyright: ignore[reportGeneralTypeIssues]
                    raise ValueError("该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠")

    async def create_pricing_rule(self, data: Dict[str, Any]) -> PricingRule:
        """创建定价规则"""
        customer_id = data.get("customer_id")
        device_type = data["device_type"]
        layer_type = data.get("layer_type")
        effective_date = data["effective_date"]
        expiry_date = data.get("expiry_date")

        # 使用统一的校验方法
        await self._check_overlap(
            customer_id=customer_id,  # pyright: ignore[reportArgumentType]
            device_type=device_type,
            layer_type=layer_type,
            effective_date=effective_date,
            expiry_date=expiry_date,
        )

        rule = PricingRule(
            customer_id=data.get("customer_id"),
            device_type=data["device_type"],
            layer_type=data.get("layer_type"),
            pricing_type=data["pricing_type"],
            unit_price=data.get("unit_price"),
            tiers=data.get("tiers"),
            package_type=data.get("package_type"),
            package_limits=data.get("package_limits"),
            effective_date=data["effective_date"],
            expiry_date=data.get("expiry_date"),
            created_by=data.get("created_by"),
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def update_pricing_rule(
        self, rule_id: int, data: Dict[str, Any]
    ) -> Optional[PricingRule]:
        """更新定价规则"""
        result = await self.db.execute(
            select(PricingRule).where(PricingRule.id == rule_id, PricingRule.deleted_at.is_(None))
        )
        rule = result.scalar_one_or_none()

        if not rule:
            return None

        # 检查是否需要重叠校验
        overlap_fields = {
            "effective_date",
            "expiry_date",
            "customer_id",
            "device_type",
            "layer_type",
        }
        needs_overlap_check = any(f in data for f in overlap_fields)

        if needs_overlap_check:
            # 使用修改后的值（如果提供了）或原始值
            check_customer_id = data.get("customer_id", rule.customer_id)
            check_device_type = data.get("device_type", rule.device_type)
            check_layer_type = data.get("layer_type", rule.layer_type)
            check_effective_date = data.get("effective_date", rule.effective_date)
            check_expiry_date = data.get("expiry_date", rule.expiry_date)

            await self._check_overlap(
                customer_id=check_customer_id,
                device_type=check_device_type,
                layer_type=check_layer_type,
                effective_date=check_effective_date,
                expiry_date=check_expiry_date,
                exclude_id=rule_id,
            )

        # 可更新字段
        updatable = [
            "device_type",
            "layer_type",
            "pricing_type",
            "unit_price",
            "tiers",
            "package_type",
            "package_limits",
            "effective_date",
            "expiry_date",
        ]

        for field in updatable:
            if field in data:
                setattr(rule, field, data[field])

        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    async def check_pricing_rule_conflict(
        self,
        customer_id: int,
        device_type: str,
        layer_type: Optional[str],
        effective_date: date,
        expiry_date: Optional[date],
        exclude_id: Optional[int] = None,
    ) -> List[PricingRule]:
        """查询与给定条件存在有效期重叠的规则，返回冲突列表"""
        if layer_type is None:
            layer_condition = PricingRule.layer_type.is_(None)
        else:
            layer_condition = PricingRule.layer_type == layer_type

        conflict_stmt = select(PricingRule).where(
            PricingRule.customer_id == customer_id,
            PricingRule.device_type == device_type,
            layer_condition,
            PricingRule.deleted_at.is_(None),
        )

        if exclude_id is not None:
            conflict_stmt = conflict_stmt.where(PricingRule.id != exclude_id)

        result = await self.db.execute(conflict_stmt)
        existing_rules = result.scalars().all()

        conflicting = []
        for rule in existing_rules:
            rule_expiry = rule.expiry_date
            new_expiry = expiry_date

            if rule_expiry is None or new_expiry is None:
                if rule_expiry is None and new_expiry is None:
                    conflicting.append(rule)
                elif rule_expiry is None:
                    if new_expiry >= rule.effective_date:  # pyright: ignore[reportGeneralTypeIssues]
                        conflicting.append(rule)
                else:
                    if effective_date <= rule_expiry:  # pyright: ignore[reportGeneralTypeIssues]
                        conflicting.append(rule)
            else:
                if effective_date <= rule_expiry and new_expiry >= rule.effective_date:  # pyright: ignore[reportGeneralTypeIssues]
                    conflicting.append(rule)

        return conflicting

    async def delete_pricing_rule(self, rule_id: int) -> bool:
        """删除定价规则（软删除）"""
        result = await self.db.execute(
            select(PricingRule).where(PricingRule.id == rule_id, PricingRule.deleted_at.is_(None))
        )
        rule = result.scalar_one_or_none()

        if not rule:
            return False

        rule.deleted_at = func.now()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()

        return True


class InvoiceService:
    """结算单服务类"""

    def __init__(
        self,
        invoice_repo: InvoiceRepositoryProtocol,
        pricing_repo: PricingRepositoryProtocol,
    ):
        self.invoice_repo = invoice_repo
        self.pricing_repo = pricing_repo

    @property
    def db(self) -> AsyncSession:
        return self.invoice_repo.db  # pyright: ignore[reportAttributeAccessIssue]

    async def calculate_items_from_rules(
        self,
        customer_id: int,
        period_start: date,
        period_end: date,
    ) -> Tuple[List[Dict[str, Any]], Decimal]:
        """
        根据计费规则 + 用量数据计算结算明细

        逻辑：
        1. 查询客户在结算周期内的每日用量（按 device_type + layer_type 分组汇总）
        2. 查询客户生效中的定价规则
        3. 根据 pricing_type 计算每项费用：
           - fixed: 总用量 × 单价
           - tiered: 按阶梯单价计算
           - package: 按包年规则计算
        4. 返回 items 列表和总金额

        Args:
            customer_id: 客户 ID
            period_start: 结算周期开始
            period_end: 结算周期结束

        Returns:
            (items, total_amount)
            items: [
                {
                    "device_type": "N",
                    "layer_type": "single",
                    "quantity": 1234,
                    "unit_price": 10.0,
                    "subtotal": 12340.0,
                    "pricing_rule_id": 2,
                }
            ]
        """
        from sqlalchemy import func as sa_func

        # 1. 查询结算周期内的用量汇总（按 device_type + layer_type 分组）
        usage_stmt = (
            select(
                DailyConsumption.device_type,
                DailyConsumption.layer_type,
                sa_func.sum(DailyConsumption.order_count).label("total_quantity"),
            )
            .where(
                DailyConsumption.customer_id == customer_id,
                DailyConsumption.consumption_date >= period_start,
                DailyConsumption.consumption_date <= period_end,
            )
            .group_by(DailyConsumption.device_type, DailyConsumption.layer_type)
        )
        usage_result = await self.db.execute(usage_stmt)
        usage_rows = usage_result.all()

        if not usage_rows:
            return [], Decimal(0)

        # 2. 查询客户生效中的定价规则
        rules_stmt = select(PricingRule).where(
            PricingRule.customer_id == customer_id,
            PricingRule.effective_date <= period_end,
            (PricingRule.expiry_date.is_(None)) | (PricingRule.expiry_date >= period_start),
        )
        rules_result = await self.db.execute(rules_stmt)
        pricing_rules = rules_result.scalars().all()

        # 构建规则查找字典：(device_type, layer_type) -> PricingRule
        # layer_type 为 NULL 时默认为 'single'
        rules_map: Dict[Tuple[str, str], PricingRule] = {  # pyright: ignore[reportAssignmentType]
            (r.device_type, r.layer_type or "single"): r for r in pricing_rules
        }

        # 3. 计算每项费用
        items: List[Dict[str, Any]] = []
        total_amount = Decimal(0)

        for row in usage_rows:
            device_type = row.device_type
            layer_type = row.layer_type or "single"
            total_quantity = Decimal(str(row.total_quantity))

            # 先尝试精确匹配 (device_type, layer_type)，再回退到 (device_type, 'single')
            rule = rules_map.get((device_type, layer_type)) or rules_map.get(
                (device_type, "single")
            )
            if not rule:
                # 没有匹配的定价规则，跳过
                continue

            if rule.pricing_type == "fixed":  # pyright: ignore[reportGeneralTypeIssues]
                # 定价结算：总用量 × 单价
                unit_price = Decimal(str(rule.unit_price or 0))
                subtotal = total_quantity * unit_price
                items.append(
                    {
                        "device_type": device_type,
                        "layer_type": layer_type,
                        "quantity": total_quantity,
                        "unit_price": unit_price,
                        "subtotal": subtotal,
                        "pricing_rule_id": rule.id,
                    }
                )
                total_amount += subtotal

            elif rule.pricing_type == "tiered":  # pyright: ignore[reportGeneralTypeIssues]
                # 阶梯结算：按阶梯单价计算
                tiers = rule.tiers or {}
                subtotal = self._calculate_tiered_price(total_quantity, tiers)  # pyright: ignore[reportArgumentType]
                # 阶梯计价的 unit_price 显示为平均单价
                avg_unit_price = subtotal / total_quantity if total_quantity > 0 else Decimal(0)
                items.append(
                    {
                        "device_type": device_type,
                        "layer_type": layer_type,
                        "quantity": total_quantity,
                        "unit_price": avg_unit_price,
                        "subtotal": subtotal,
                        "pricing_rule_id": rule.id,
                    }
                )
                total_amount += subtotal

            elif rule.pricing_type == "package":  # pyright: ignore[reportGeneralTypeIssues]
                # 包年结算：按包年固定费用
                package_limits = rule.package_limits or {}
                # 简化实现：使用包年基础费用作为单价
                base_fee = Decimal(str(package_limits.get("base_fee", 0)))
                items.append(
                    {
                        "device_type": device_type,
                        "layer_type": layer_type,
                        "quantity": total_quantity,
                        "unit_price": base_fee,
                        "subtotal": base_fee,  # 包年固定费用
                        "pricing_rule_id": rule.id,
                    }
                )
                total_amount += base_fee

        return items, total_amount

    def _calculate_tiered_price(self, quantity: Decimal, tiers: Dict[str, Any]) -> Decimal:
        """
        计算阶梯价格

        tiers 格式示例：
        {
            "ranges": [
                {"min": 0, "max": 1000, "price": 10},
                {"min": 1001, "max": 5000, "price": 8},
                {"min": 5001, "max": null, "price": 5}
            ]
        }
        """
        ranges = tiers.get("ranges", [])
        if not ranges:
            return Decimal(0)

        remaining = quantity
        total = Decimal(0)

        for tier in sorted(ranges, key=lambda x: x.get("min", 0)):
            if remaining <= 0:
                break

            tier_min = Decimal(str(tier.get("min", 0)))
            tier_max = tier.get("max")
            tier_price = Decimal(str(tier.get("price", 0)))

            if tier_max is not None:
                tier_max = Decimal(str(tier_max))
                tier_capacity = tier_max - tier_min + 1
            else:
                tier_capacity = remaining  # 无上限，使用剩余数量

            # 计算实际使用的数量（不能超过剩余数量）
            used = min(remaining, tier_capacity)
            total += used * tier_price
            remaining -= used

        return total

    async def generate_invoice(
        self,
        customer_id: int,
        period_start: date,
        period_end: date,
        items: List[Dict[str, Any]],
        created_by: int,
        is_auto_generated: bool = False,
    ) -> Invoice:
        """
        生成结算单

        Args:
            customer_id: 客户 ID
            period_start: 结算周期开始
            period_end: 结算周期结束
            items: 结算项列表 [{'device_type': 'X', 'layer_type': 'single', 'quantity': 100, 'unit_price': 10}]
            created_by: 创建人 ID
            is_auto_generated: 是否自动生成

        Returns:
            Invoice
        """
        # 生成结算单号：INV-生成日期-客户ID-4位随机码
        random_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        invoice_no = f"INV-{datetime.now().strftime('%Y%m%d')}-{customer_id}-{random_code}"

        # 计算总金额
        total_amount = sum(
            Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"])) for item in items
        )

        # 创建结算单
        invoice = Invoice(
            invoice_no=invoice_no,
            customer_id=customer_id,
            period_start=period_start,
            period_end=period_end,
            total_amount=total_amount,
            discount_amount=Decimal(0),
            status="draft",
            is_auto_generated=is_auto_generated,
            created_by=created_by,
        )
        self.db.add(invoice)
        await self.db.flush()

        # 创建结算单项
        for item in items:
            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                device_type=item["device_type"],
                layer_type=item.get("layer_type"),
                quantity=Decimal(str(item["quantity"])),
                unit_price=Decimal(str(item["unit_price"])),
            )
            self.db.add(invoice_item)

        await self.db.commit()
        await self.db.refresh(invoice)

        return invoice

    async def get_invoices(
        self,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "",
        sort_order: str = "desc",
    ) -> Tuple[List[Invoice], int]:
        """获取结算单列表（支持服务端排序）"""
        stmt = (
            select(Invoice)
            .options(selectinload(Invoice.items), selectinload(Invoice.customer))
            .join(Customer, Invoice.customer_id == Customer.id)
            .where(Invoice.deleted_at.is_(None), Customer.deleted_at.is_(None))
        )

        if customer_id:
            stmt = stmt.where(Invoice.customer_id == customer_id)
        if keyword:
            stmt = stmt.where(Customer.name.ilike(f"%{keyword}%"))
        if status:
            stmt = stmt.where(Invoice.status == status)
        if period_start:
            stmt = stmt.where(Invoice.period_start >= period_start)
        if period_end:
            stmt = stmt.where(Invoice.period_end <= period_end)

        # 总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar()

        # 排序字段映射（前端字段 -> SQLAlchemy 列表达式）
        sort_field_map = {
            "invoice_no": Invoice.invoice_no,
            "total_amount": Invoice.total_amount,
            "final_amount": Invoice.total_amount - (Invoice.discount_amount or 0),
            "created_at": Invoice.created_at,
        }

        if sort_by and sort_by in sort_field_map:
            order_expr = sort_field_map[sort_by]
            if sort_order == "asc":
                stmt = stmt.order_by(order_expr.asc(), Invoice.id.asc())
            else:
                stmt = stmt.order_by(order_expr.desc(), Invoice.id.asc())
        else:
            # 默认排序：按创建时间降序
            stmt = stmt.order_by(Invoice.created_at.desc(), Invoice.id.asc())

        # 分页
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        invoices = result.scalars().unique().all()

        return list(invoices), total  # pyright: ignore[reportReturnType]

    async def get_invoice_by_id(self, invoice_id: int) -> Optional[Invoice]:
        """获取结算单详情"""
        result = await self.db.execute(
            select(Invoice)
            .options(selectinload(Invoice.items), selectinload(Invoice.customer))
            .where(
                Invoice.id == invoice_id,
                Invoice.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def apply_discount(
        self,
        invoice_id: int,
        discount_amount: Decimal,
        discount_reason: str,
        discount_attachment: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """应用减免"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status not in ["draft", "pending_ops", "pending_sales", "pending_customer"]:
            return False, f"当前状态不能修改减免：{invoice.status}"

        if discount_amount > invoice.total_amount:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "减免金额不能大于结算总额"

        invoice.discount_amount = discount_amount  # pyright: ignore[reportAttributeAccessIssue]
        invoice.discount_reason = discount_reason  # pyright: ignore[reportAttributeAccessIssue]
        invoice.discount_attachment = discount_attachment  # pyright: ignore[reportAttributeAccessIssue]
        invoice.discount_applied_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "减免应用成功"

    async def submit_invoice(self, invoice_id: int, approver_id: int) -> Tuple[bool, str]:
        """提交结算单（进入运营经理确认阶段）

        新流程：draft → pending_ops
        旧流程兼容：draft → pending_customer（当客户未指定运营经理时回退）
        """
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "draft":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态不能提交：{invoice.status}"

        # 查询客户是否指定了运营经理
        customer = await self._get_customer(invoice.customer_id)  # pyright: ignore[reportArgumentType]
        if customer and customer.manager_id:  # pyright: ignore[reportGeneralTypeIssues]
            invoice.status = "pending_ops"  # pyright: ignore[reportAttributeAccessIssue]
        else:
            # 未指定运营经理，回退到旧流程（直接待客户确认）
            invoice.status = "pending_customer"  # pyright: ignore[reportAttributeAccessIssue]

        invoice.approver_id = approver_id  # pyright: ignore[reportAttributeAccessIssue]
        invoice.approved_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "提交成功"

    async def confirm_ops(self, invoice_id: int, user_id: int) -> Tuple[bool, str]:
        """运营经理确认（第一步）

        pending_ops → pending_sales
        校验：操作人必须为该客户指定的运营经理（customer.manager_id）
        """
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "pending_ops":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态不能进行运营经理确认：{invoice.status}"

        customer = await self._get_customer(invoice.customer_id)  # pyright: ignore[reportArgumentType]
        if not customer:
            return False, "客户不存在"

        if customer.manager_id != user_id:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "您不是该客户指定的运营经理，无权确认"

        invoice.status = "pending_sales"  # pyright: ignore[reportAttributeAccessIssue]
        invoice.ops_confirmed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        invoice.ops_confirmed_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "运营经理确认成功"

    async def confirm_sales(self, invoice_id: int, user_id: int) -> Tuple[bool, str]:
        """销售经理确认（第二步）

        pending_sales → pending_customer
        校验：操作人必须为该客户指定的销售经理（customer.sales_manager_id）
        """
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "pending_sales":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态不能进行销售经理确认：{invoice.status}"

        customer = await self._get_customer(invoice.customer_id)  # pyright: ignore[reportArgumentType]
        if not customer:
            return False, "客户不存在"

        if customer.sales_manager_id != user_id:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "您不是该客户指定的销售经理，无权确认"

        invoice.status = "pending_customer"  # pyright: ignore[reportAttributeAccessIssue]
        invoice.sales_confirmed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        invoice.sales_confirmed_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "销售经理确认成功"

    async def confirm_invoice(self, invoice_id: int, user_id: int) -> Tuple[bool, str]:
        """客户确认结算单（第三步，线下确认后线上录入）

        pending_customer → customer_confirmed → 自动扣款 → completed
        扣款失败时保持 customer_confirmed 状态，可调用 retry_deduction 重试
        """
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "pending_customer":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态不能确认：{invoice.status}"

        invoice.status = "customer_confirmed"  # pyright: ignore[reportAttributeAccessIssue]
        invoice.customer_confirmed_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]
        invoice.customer_confirmed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()

        # 自动执行扣款
        return await self._execute_deduction(invoice, user_id=user_id)

    async def retry_deduction(self, invoice_id: int, user_id: int = 1) -> Tuple[bool, str]:
        """重试扣款（扣款失败后手动重试）

        仅当状态为 customer_confirmed 时可执行
        """
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "customer_confirmed":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态不能重试扣款：{invoice.status}"

        success, message = await self._execute_deduction(invoice, user_id=user_id)

        if success:
            return True, "重试扣款成功"
        else:
            # _execute_deduction 返回的 message 带有 "客户确认成功，但扣款失败：" 前缀
            # 对重试场景需要去掉该前缀
            clean_msg = message.replace("客户确认成功，但扣款失败：", "")
            return False, f"扣款失败：{clean_msg}"

    async def _execute_deduction(self, invoice: Invoice, user_id: int = 1) -> Tuple[bool, str]:
        """执行余额扣款（内部方法）

        customer_confirmed → completed（扣款成功）
        失败时保持 customer_confirmed
        """
        # 提交当前事务，避免与 consume 内部的 db.begin() 冲突
        await self.db.commit()

        final_amount = invoice.total_amount - (invoice.discount_amount or 0)
        balance_service = BalanceService(BalanceRepository(self.db))
        success, message = await balance_service.consume(
            customer_id=invoice.customer_id,  # pyright: ignore[reportArgumentType]
            amount=final_amount,  # pyright: ignore[reportArgumentType]
            invoice_id=invoice.id,  # pyright: ignore[reportArgumentType]
        )

        if not success:
            # 扣款失败，保持 customer_confirmed 状态
            return False, f"客户确认成功，但扣款失败：{message}"

        invoice.status = "completed"  # pyright: ignore[reportAttributeAccessIssue]
        invoice.completed_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]
        invoice.completed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()

        return True, "客户确认成功，已自动完成扣款"

    async def _get_customer(self, customer_id: int) -> Optional[Customer]:
        """查询客户信息（内部方法）"""
        result = await self.db.execute(
            select(Customer).where(Customer.id == customer_id, Customer.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def pay_invoice(
        self, invoice_id: int, payment_proof: Optional[str] = None
    ) -> Tuple[bool, str]:
        """确认付款"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "customer_confirmed":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态不能付款：{invoice.status}"

        invoice.status = "paid"  # pyright: ignore[reportAttributeAccessIssue]
        invoice.paid_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]
        invoice.payment_proof = payment_proof  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "付款成功"

    async def complete_invoice(self, invoice_id: int, user_id: int = 1) -> Tuple[bool, str]:
        """完成结算（扣款）"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "paid":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态不能完成：{invoice.status}"

        # 提交当前事务（get_invoice_by_id 的 autobegin 事务），
        # 避免与 consume 内部的 db.begin() 冲突
        await self.db.commit()

        # 执行扣款
        final_amount = invoice.total_amount - (invoice.discount_amount or 0)
        balance_service = BalanceService(BalanceRepository(self.db))
        success, message = await balance_service.consume(
            customer_id=invoice.customer_id,  # pyright: ignore[reportArgumentType]
            amount=final_amount,  # pyright: ignore[reportArgumentType]
            invoice_id=invoice_id,
        )

        if not success:
            return False, message

        invoice.status = "completed"  # pyright: ignore[reportAttributeAccessIssue]
        invoice.completed_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]
        invoice.completed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "结算完成"

    async def cancel_invoice(self, invoice_id: int, user_id: int) -> Tuple[bool, str]:
        """取消结算单"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        # 草稿、待运营经理确认、待销售经理确认、待客户确认状态可以取消
        if invoice.status not in ("draft", "pending_ops", "pending_sales", "pending_customer"):
            return False, f"当前状态不能取消：{invoice.status}"

        invoice.status = "cancelled"  # pyright: ignore[reportAttributeAccessIssue]
        invoice.cancelled_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]
        invoice.cancelled_by = user_id  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "取消成功"

    async def delete_invoice(self, invoice_id: int) -> bool:
        """删除结算单（软删除）"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False

        invoice.deleted_at = func.now()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()

        return True

    async def get_customers_for_batch(
        self,
        pricing_type: Optional[str] = None,
        industry_type_ids: Optional[List[int]] = None,
        scale_levels: Optional[List[str]] = None,
        consume_levels: Optional[List[str]] = None,
        is_real_estate: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """按条件查询匹配的客户列表（用于批量生成结算单预览）

        Args:
            pricing_type: 计费类型（fixed/tiered/package），通过 PricingRule 关联
            industry_type_ids: 行业类型 ID 列表
            scale_levels: 规模等级列表（S/A/B/C/D/E）
            consume_levels: 消费等级列表（C1-C6）
            is_real_estate: 是否房产客户

        Returns:
            客户列表 [{ id, name, company_id, manager_id, sales_manager_id }]
        """
        from ..models.customers import CustomerProfile

        stmt = select(
            Customer.id,
            Customer.name,
            Customer.company_id,
            Customer.manager_id,
            Customer.sales_manager_id,
        ).where(Customer.deleted_at.is_(None), Customer.is_disabled.is_(False))

        # 通过 PricingRule 关联筛选计费类型
        if pricing_type:
            stmt = stmt.where(
                Customer.id.in_(
                    select(PricingRule.customer_id).where(
                        PricingRule.deleted_at.is_(None),
                        PricingRule.pricing_type == pricing_type,
                    )
                )
            )

        # 是否房产客户
        if is_real_estate is not None:
            stmt = stmt.where(Customer.is_real_estate.is_(is_real_estate))

        # 通过 CustomerProfile 关联筛选行业/规模/消费等级
        needs_profile_join = any([industry_type_ids, scale_levels, consume_levels])
        if needs_profile_join:
            stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            if industry_type_ids:
                stmt = stmt.where(CustomerProfile.industry_type_id.in_(industry_type_ids))
            if scale_levels:
                stmt = stmt.where(CustomerProfile.scale_level.in_(scale_levels))
            if consume_levels:
                stmt = stmt.where(CustomerProfile.consume_level.in_(consume_levels))

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": row.id,
                "name": row.name,
                "company_id": row.company_id,
                "manager_id": row.manager_id,
                "sales_manager_id": row.sales_manager_id,
            }
            for row in rows
        ]

    async def generate_invoices_batch(
        self,
        pricing_type: Optional[str] = None,
        industry_type_ids: Optional[List[int]] = None,
        scale_levels: Optional[List[str]] = None,
        consume_levels: Optional[List[str]] = None,
        is_real_estate: Optional[bool] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        created_by: int = 1,
    ) -> Dict[str, Any]:
        """批量生成结算单

        为每个匹配的客户独立生成一张结算单（状态 draft）。
        跳过无用量数据/无计费规则/未指定经理的客户。

        Returns:
            {
                "success_count": int,
                "skipped": [{"customer_id": int, "name": str, "reason": str}],
                "generated": [{"customer_id": int, "name": str, "invoice_id": int, "invoice_no": str, "total_amount": float}]
            }
        """
        customers = await self.get_customers_for_batch(
            pricing_type=pricing_type,
            industry_type_ids=industry_type_ids,
            scale_levels=scale_levels,
            consume_levels=consume_levels,
            is_real_estate=is_real_estate,
        )

        generated: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        for cust in customers:
            # 校验客户已指定运营经理和销售经理
            if not cust["manager_id"]:
                skipped.append(
                    {"customer_id": cust["id"], "name": cust["name"], "reason": "未指定运营经理"}
                )
                continue
            if not cust["sales_manager_id"]:
                skipped.append(
                    {"customer_id": cust["id"], "name": cust["name"], "reason": "未指定销售经理"}
                )
                continue

            # 计算结算明细
            try:
                items, total_amount = await self.calculate_items_from_rules(
                    customer_id=cust["id"],
                    period_start=period_start,  # pyright: ignore[reportArgumentType]
                    period_end=period_end,  # pyright: ignore[reportArgumentType]
                )
            except Exception:
                items, total_amount = [], Decimal(0)

            if not items:
                skipped.append(
                    {
                        "customer_id": cust["id"],
                        "name": cust["name"],
                        "reason": "结算周期内无用量数据或无匹配的计费规则",
                    }
                )
                continue

            # 生成结算单（状态 draft）
            invoice = await self.generate_invoice(
                customer_id=cust["id"],
                period_start=period_start,  # pyright: ignore[reportArgumentType]
                period_end=period_end,  # pyright: ignore[reportArgumentType]
                items=items,
                created_by=created_by,
                is_auto_generated=True,
            )

            generated.append(
                {
                    "customer_id": cust["id"],
                    "name": cust["name"],
                    "invoice_id": invoice.id,
                    "invoice_no": invoice.invoice_no,
                    "total_amount": float(total_amount),
                }
            )

        return {
            "success_count": len(generated),
            "skipped": skipped,
            "generated": generated,
        }
