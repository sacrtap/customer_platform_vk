"""结算与余额管理服务"""

from typing import Optional, List, Tuple, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import OperationalError
from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from ..models.billing import (
    CustomerBalance,
    RechargeRecord,
    PricingRule,
    Invoice,
    InvoiceItem,
    ConsumptionRecord,
    DailyUsage,
)
import uuid


class BalanceService:
    """余额服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_balance_by_customer_id(self, customer_id: int) -> Optional[CustomerBalance]:
        """获取客户余额"""
        result = await self.db.execute(
            select(CustomerBalance).where(
                CustomerBalance.customer_id == customer_id,
                CustomerBalance.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_balance(self, customer_id: int) -> CustomerBalance:
        """获取或创建客户余额"""
        balance = await self.get_balance_by_customer_id(customer_id)
        if not balance:
            balance = CustomerBalance(customer_id=customer_id)
            self.db.add(balance)
            await self.db.flush()
        return balance

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
        balance.real_amount = (balance.real_amount or 0) + real_amount
        balance.bonus_amount = (balance.bonus_amount or 0) + bonus_amount
        balance.total_amount = (balance.total_amount or 0) + real_amount + bonus_amount

        await self.db.commit()
        await self.db.refresh(record)

        return record

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
                    if total_balance < amount:
                        return False, f"余额不足，当前余额：{total_balance:.2f}元"

                    # 先消耗赠金，再消耗实充
                    remaining = amount
                    bonus_used = Decimal(0)
                    real_used = Decimal(0)

                    if balance.bonus_amount and balance.bonus_amount > 0:
                        if balance.bonus_amount >= remaining:
                            bonus_used = remaining
                            balance.bonus_amount -= remaining
                            remaining = Decimal(0)
                        else:
                            bonus_used = balance.bonus_amount
                            remaining -= balance.bonus_amount
                            balance.bonus_amount = Decimal(0)

                    if remaining > 0 and balance.real_amount and balance.real_amount > 0:
                        if balance.real_amount >= remaining:
                            real_used = remaining
                            balance.real_amount -= remaining
                        else:
                            real_used = balance.real_amount
                            balance.real_amount = Decimal(0)

                    # 更新总额
                    balance.used_total = (balance.used_total or 0) + amount
                    balance.used_bonus = (balance.used_bonus or 0) + bonus_used
                    balance.used_real = (balance.used_real or 0) + real_used

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

        return list(records), total


class PricingService:
    """定价规则服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_pricing_rules(
        self,
        customer_id: Optional[int] = None,
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
            .where(PricingRule.deleted_at.is_(None))
        )

        if customer_id:
            base_stmt = base_stmt.where(PricingRule.customer_id == customer_id)
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

        return list(rules), total

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
                    raise ValueError(
                        "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                    )
                elif rule_expiry is None:
                    if new_expiry >= rule.effective_date:
                        raise ValueError(
                            "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                        )
                else:
                    if effective_date <= rule_expiry:
                        raise ValueError(
                            "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                        )
            else:
                if effective_date <= rule_expiry and new_expiry >= rule.effective_date:
                    raise ValueError(
                        "该客户已存在相同设备类型和楼层类型的定价规则，有效期存在重叠"
                    )

    async def create_pricing_rule(self, data: Dict[str, Any]) -> PricingRule:
        """创建定价规则"""
        customer_id = data.get("customer_id")
        device_type = data["device_type"]
        layer_type = data.get("layer_type")
        effective_date = data["effective_date"]
        expiry_date = data.get("expiry_date")

        # 使用统一的校验方法
        await self._check_overlap(
            customer_id=customer_id,
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
        overlap_fields = {"effective_date", "expiry_date", "customer_id", "device_type", "layer_type"}
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
                    if new_expiry >= rule.effective_date:
                        conflicting.append(rule)
                else:
                    if effective_date <= rule_expiry:
                        conflicting.append(rule)
            else:
                if effective_date <= rule_expiry and new_expiry >= rule.effective_date:
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

        rule.deleted_at = func.now()
        await self.db.commit()

        return True


class InvoiceService:
    """结算单服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

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
            items: [{"device_type": "N", "layer_type": "single", "quantity": 1234, "unit_price": 10.0, "subtotal": 12340.0, "pricing_rule_id": 2}]
        """
        from sqlalchemy import func as sa_func

        # 1. 查询结算周期内的用量汇总（按 device_type + layer_type 分组）
        usage_stmt = (
            select(
                DailyUsage.device_type,
                DailyUsage.layer_type,
                sa_func.sum(DailyUsage.quantity).label("total_quantity"),
            )
            .where(
                DailyUsage.customer_id == customer_id,
                DailyUsage.usage_date >= period_start,
                DailyUsage.usage_date <= period_end,
            )
            .group_by(DailyUsage.device_type, DailyUsage.layer_type)
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
        rules_map: Dict[Tuple[str, str], PricingRule] = {
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
            rule = rules_map.get((device_type, layer_type)) or rules_map.get((device_type, "single"))
            if not rule:
                # 没有匹配的定价规则，跳过
                continue

            if rule.pricing_type == "fixed":
                # 定价结算：总用量 × 单价
                unit_price = Decimal(str(rule.unit_price or 0))
                subtotal = total_quantity * unit_price
                items.append({
                    "device_type": device_type,
                    "layer_type": layer_type,
                    "quantity": total_quantity,
                    "unit_price": unit_price,
                    "subtotal": subtotal,
                    "pricing_rule_id": rule.id,
                })
                total_amount += subtotal

            elif rule.pricing_type == "tiered":
                # 阶梯结算：按阶梯单价计算
                tiers = rule.tiers or {}
                subtotal = self._calculate_tiered_price(total_quantity, tiers)
                # 阶梯计价的 unit_price 显示为平均单价
                avg_unit_price = subtotal / total_quantity if total_quantity > 0 else Decimal(0)
                items.append({
                    "device_type": device_type,
                    "layer_type": layer_type,
                    "quantity": total_quantity,
                    "unit_price": avg_unit_price,
                    "subtotal": subtotal,
                    "pricing_rule_id": rule.id,
                })
                total_amount += subtotal

            elif rule.pricing_type == "package":
                # 包年结算：按包年固定费用
                package_type = rule.package_type
                package_limits = rule.package_limits or {}
                # 简化实现：使用包年基础费用作为单价
                base_fee = Decimal(str(package_limits.get("base_fee", 0)))
                items.append({
                    "device_type": device_type,
                    "layer_type": layer_type,
                    "quantity": total_quantity,
                    "unit_price": base_fee,
                    "subtotal": base_fee,  # 包年固定费用
                    "pricing_rule_id": rule.id,
                })
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
        # 生成结算单号
        invoice_no = (
            f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
        )

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
        status: Optional[str] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Invoice], int]:
        """获取结算单列表"""
        stmt = (
            select(Invoice)
            .options(selectinload(Invoice.items), selectinload(Invoice.customer))
            .where(Invoice.deleted_at.is_(None))
        )

        if customer_id:
            stmt = stmt.where(Invoice.customer_id == customer_id)
        if status:
            stmt = stmt.where(Invoice.status == status)
        if period_start:
            stmt = stmt.where(Invoice.period_start >= period_start)
        if period_end:
            stmt = stmt.where(Invoice.period_end <= period_end)

        # 总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar()

        # 分页
        stmt = stmt.order_by(Invoice.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        invoices = result.scalars().unique().all()

        return list(invoices), total

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

        if invoice.status not in ["draft", "pending_customer"]:
            return False, f"当前状态不能修改减免：{invoice.status}"

        if discount_amount > invoice.total_amount:
            return False, "减免金额不能大于结算总额"

        invoice.discount_amount = discount_amount
        invoice.discount_reason = discount_reason
        invoice.discount_attachment = discount_attachment

        await self.db.commit()

        return True, "减免应用成功"

    async def submit_invoice(self, invoice_id: int, approver_id: int) -> Tuple[bool, str]:
        """提交结算单（商务确认）"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "draft":
            return False, f"当前状态不能提交：{invoice.status}"

        invoice.status = "pending_customer"
        invoice.approver_id = approver_id
        invoice.approved_at = datetime.now().isoformat()

        await self.db.commit()

        return True, "提交成功"

    async def confirm_invoice(self, invoice_id: int) -> Tuple[bool, str]:
        """客户确认结算单"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "pending_customer":
            return False, f"当前状态不能确认：{invoice.status}"

        invoice.status = "customer_confirmed"
        invoice.customer_confirmed_at = datetime.now().isoformat()

        await self.db.commit()

        return True, "确认成功"

    async def pay_invoice(
        self, invoice_id: int, payment_proof: Optional[str] = None
    ) -> Tuple[bool, str]:
        """确认付款"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "customer_confirmed":
            return False, f"当前状态不能付款：{invoice.status}"

        invoice.status = "paid"
        invoice.paid_at = datetime.now().isoformat()
        invoice.payment_proof = payment_proof

        await self.db.commit()

        return True, "付款成功"

    async def complete_invoice(self, invoice_id: int) -> Tuple[bool, str]:
        """完成结算（扣款）"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        if invoice.status != "paid":
            return False, f"当前状态不能完成：{invoice.status}"

        # 执行扣款
        final_amount = invoice.total_amount - (invoice.discount_amount or 0)
        balance_service = BalanceService(self.db)
        success, message = await balance_service.consume(
            customer_id=invoice.customer_id,
            amount=final_amount,
            invoice_id=invoice_id,
        )

        if not success:
            return False, message

        invoice.status = "completed"
        invoice.completed_at = datetime.now().isoformat()

        await self.db.commit()

        return True, "结算完成"

    async def cancel_invoice(self, invoice_id: int) -> Tuple[bool, str]:
        """取消结算单"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False, "结算单不存在"

        # 只有草稿和待客户确认状态可以取消
        if invoice.status not in ("draft", "pending_customer"):
            return False, f"当前状态不能取消：{invoice.status}"

        invoice.status = "cancelled"
        invoice.cancelled_at = datetime.now().isoformat()

        await self.db.commit()

        return True, "取消成功"

    async def delete_invoice(self, invoice_id: int) -> bool:
        """删除结算单（软删除）"""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice:
            return False

        invoice.deleted_at = func.now()
        await self.db.commit()

        return True
