"""客户分析服务"""

import logging
from calendar import monthrange
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, case, extract, func, or_, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import (
    AuditLog,
    CustomerBalance,
    Invoice,
    InvoiceItem,
    PricingRule,
    RechargeRecord,
)
from ..models.customers import Customer, CustomerProfile
from ..models.daily_consumption import DailyConsumption
from ..models.forecast_config import ForecastUnitPrice
from ..models.industry_type import IndustryType
from ..models.users import User
from ..utils.tiers import TierFormatError, normalize_tiers

logger = logging.getLogger(__name__)


class AnalyticsService:
    """客户分析服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 消耗分析 ==========

    async def _get_package_over_limit_estimates(
        self,
        start_date: datetime,
        end_date: datetime,
        customer_id: Optional[int] = None,
    ) -> Dict[int, Dict[str, Any]]:
        """计算限量套餐客户的超量费用估算

        查询指定时间段内所有限量套餐客户的累计订单数，
        与 limit_count 对比计算超量费用。

        Returns:
            {customer_id: {"over_limit_cost": float, "total_order_count": int, "limit_count": int}}
        """
        from decimal import Decimal

        # 查询限量套餐规则
        rule_stmt = select(PricingRule).where(
            PricingRule.pricing_type == "package",
            PricingRule.deleted_at.is_(None),
            PricingRule.effective_date <= end_date,
            (PricingRule.expiry_date.is_(None)) | (PricingRule.expiry_date >= start_date),
        )
        if customer_id:
            rule_stmt = rule_stmt.where(PricingRule.customer_id == customer_id)

        rule_result = await self.db.execute(rule_stmt)
        rules = rule_result.scalars().all()

        # 筛选限量套餐
        limited_rules = []
        for r in rules:
            pl = r.package_limits or {}
            if not pl.get("is_unlimited", False):
                limited_rules.append(r)

        if not limited_rules:
            return {}

        estimates: Dict[int, Dict[str, Any]] = {}
        for rule in limited_rules:
            pl = rule.package_limits or {}
            limit_count = Decimal(str(pl.get("limit_count", 0) or 0))
            if limit_count <= 0:
                continue
            over_limit_unit_price = Decimal(str(pl.get("over_limit_unit_price", 0) or 0))

            # 查询该客户在时间段内的累计订单数
            usage_stmt = select(func.sum(DailyConsumption.order_count).label("total_orders")).where(
                DailyConsumption.customer_id == rule.customer_id,
                DailyConsumption.consumption_date >= start_date,
                DailyConsumption.consumption_date <= end_date,
                DailyConsumption.deleted_at.is_(None),
            )
            usage_result = await self.db.execute(usage_stmt)
            total_orders = Decimal(str(usage_result.scalar() or 0))

            # 计算超量
            over_limit_quantity = max(Decimal(0), total_orders - limit_count)
            over_limit_cost = float(
                (over_limit_quantity * over_limit_unit_price).quantize(Decimal("0.01"))
            )

            # 如果已存在该客户的估算，取较大的（多条规则时不叠加）
            existing = estimates.get(rule.customer_id)
            if existing is None or over_limit_cost > existing["over_limit_cost"]:
                estimates[rule.customer_id] = {
                    "over_limit_cost": over_limit_cost,
                    "total_order_count": int(total_orders),
                    "limit_count": int(limit_count),
                    "over_limit_quantity": int(over_limit_quantity),
                }

        return estimates

    async def get_consumption_trend(
        self,
        start_date: datetime,
        end_date: datetime,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取消耗趋势（月度）"""
        # 按月份聚合消耗金额
        stmt = (
            select(
                extract("year", Invoice.period_start).label("year"),
                extract("month", Invoice.period_start).label("month"),
                func.sum(Invoice.total_amount).label("total_amount"),
            )
            .join(Customer, Invoice.customer_id == Customer.id)
            .where(
                and_(
                    Invoice.period_start >= start_date,
                    Invoice.period_end <= end_date,
                    Invoice.status != "cancelled",
                    Customer.deleted_at.is_(None),
                )
            )
        )

        if customer_id:
            stmt = stmt.where(Invoice.customer_id == customer_id)
        if keyword:
            stmt = stmt.where(Customer.name.ilike(f"%{keyword}%"))

        stmt = stmt.group_by(
            extract("year", Invoice.period_start),
            extract("month", Invoice.period_start),
        ).order_by(
            extract("year", Invoice.period_start),
            extract("month", Invoice.period_start),
        )

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "year": int(row.year),
                "month": int(row.month),
                "period": f"{int(row.year)}-{int(row.month):02d}",
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            }
            for row in result
        ]

    async def get_consumption_trend_with_metric(
        self,
        start_date: datetime,
        end_date: datetime,
        metric: str = "cost",
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
        industry: Optional[str] = None,
        scale_level: Optional[str] = None,
        consume_level: Optional[str] = None,
        manager_id: Optional[int] = None,
        sales_manager_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取消耗趋势（支持订单数量和结算费用切换，支持多维度筛选）"""
        from ..models.daily_consumption import DailyConsumption

        # 按日期聚合
        stmt = (
            select(
                DailyConsumption.consumption_date.label("date"),
                func.sum(DailyConsumption.order_count).label("order_count"),
                func.sum(DailyConsumption.total_cost).label("cost"),
            )
            .join(Customer, DailyConsumption.customer_id == Customer.id)
            .where(
                and_(
                    DailyConsumption.consumption_date >= start_date,
                    DailyConsumption.consumption_date <= end_date,
                    Customer.deleted_at.is_(None),
                )
            )
        )

        if customer_id:
            stmt = stmt.where(DailyConsumption.customer_id == customer_id)
        if keyword:
            stmt = stmt.where(Customer.name.ilike(f"%{keyword}%"))
        if account_type:
            stmt = stmt.where(Customer.account_type == account_type)
        if manager_id:
            stmt = stmt.where(Customer.manager_id == manager_id)
        if sales_manager_id:
            stmt = stmt.where(Customer.sales_manager_id == sales_manager_id)
        # 需要关联 CustomerProfile 的筛选条件
        if industry or scale_level or consume_level:
            stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            if scale_level:
                stmt = stmt.where(CustomerProfile.scale_level == scale_level)
            if consume_level:
                stmt = stmt.where(CustomerProfile.consume_level == consume_level)
            if industry:
                industry_names = [n.strip() for n in industry.split(",") if n.strip()]
                if industry_names:
                    stmt = stmt.outerjoin(
                        IndustryType, CustomerProfile.industry_type_id == IndustryType.id
                    )
                    stmt = stmt.where(IndustryType.name.in_(industry_names))

        stmt = stmt.group_by(DailyConsumption.consumption_date).order_by(
            DailyConsumption.consumption_date
        )

        result = (await self.db.execute(stmt)).all()
        trend_data = [
            {
                "date": row.date.isoformat(),
                "order_count": int(row.order_count) if row.order_count else 0,
                "cost": float(row.cost) if row.cost else 0.0,
            }
            for row in result
        ]

        # 限量套餐超量费用估算：加到最后一天的费用中
        if trend_data and metric == "cost":
            over_limit_estimates = await self._get_package_over_limit_estimates(
                start_date, end_date, customer_id=customer_id
            )
            if over_limit_estimates:
                total_over_limit = sum(e["over_limit_cost"] for e in over_limit_estimates.values())
                if total_over_limit > 0:
                    trend_data[-1]["cost"] = round(trend_data[-1]["cost"] + total_over_limit, 2)
                    trend_data[-1]["over_limit_cost_estimate"] = round(total_over_limit, 2)

        return trend_data

    async def get_device_type_distribution_with_metric(
        self,
        start_date: datetime,
        end_date: datetime,
        metric: str = "cost",
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
        industry: Optional[str] = None,
        scale_level: Optional[str] = None,
        consume_level: Optional[str] = None,
        manager_id: Optional[int] = None,
        sales_manager_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取设备类型分布（支持订单数量和结算费用切换，支持多维度筛选）"""
        from ..models.daily_consumption import DailyConsumption

        stmt = (
            select(
                DailyConsumption.device_type,
                func.sum(DailyConsumption.order_count).label("order_count"),
                func.sum(DailyConsumption.total_cost).label("cost"),
            )
            .join(Customer, DailyConsumption.customer_id == Customer.id)
            .where(
                and_(
                    DailyConsumption.consumption_date >= start_date,
                    DailyConsumption.consumption_date <= end_date,
                    Customer.deleted_at.is_(None),
                )
            )
        )

        if customer_id:
            stmt = stmt.where(DailyConsumption.customer_id == customer_id)
        if keyword:
            stmt = stmt.where(Customer.name.ilike(f"%{keyword}%"))
        if account_type:
            stmt = stmt.where(Customer.account_type == account_type)
        if manager_id:
            stmt = stmt.where(Customer.manager_id == manager_id)
        if sales_manager_id:
            stmt = stmt.where(Customer.sales_manager_id == sales_manager_id)
        # 需要关联 CustomerProfile 的筛选条件
        if industry or scale_level or consume_level:
            stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            if scale_level:
                stmt = stmt.where(CustomerProfile.scale_level == scale_level)
            if consume_level:
                stmt = stmt.where(CustomerProfile.consume_level == consume_level)
            if industry:
                industry_names = [n.strip() for n in industry.split(",") if n.strip()]
                if industry_names:
                    stmt = stmt.outerjoin(
                        IndustryType, CustomerProfile.industry_type_id == IndustryType.id
                    )
                    stmt = stmt.where(IndustryType.name.in_(industry_names))

        stmt = stmt.group_by(DailyConsumption.device_type)

        result = (await self.db.execute(stmt)).all()

        # 计算总数用于百分比
        total_order_count = sum(int(row.order_count) for row in result if row.order_count)
        total_cost = sum(float(row.cost) for row in result if row.cost)

        dist_data = [
            {
                "device_type": row.device_type,
                "order_count": int(row.order_count) if row.order_count else 0,
                "cost": float(row.cost) if row.cost else 0.0,
                "order_count_percentage": round(int(row.order_count) / total_order_count * 100, 2)
                if total_order_count > 0
                else 0,
                "cost_percentage": round(float(row.cost) / total_cost * 100, 2)
                if total_cost > 0
                else 0,
            }
            for row in result
        ]

        # 限量套餐超量费用估算：加到 "package" 设备类型上
        if dist_data and metric == "cost":
            over_limit_estimates = await self._get_package_over_limit_estimates(
                start_date, end_date, customer_id=customer_id
            )
            if over_limit_estimates:
                total_over_limit = sum(e["over_limit_cost"] for e in over_limit_estimates.values())
                if total_over_limit > 0:
                    # 找到 package 设备类型，加到其费用中
                    for d in dist_data:
                        if d["device_type"] == "package":
                            d["cost"] = round(d["cost"] + total_over_limit, 2)
                            d["over_limit_cost_estimate"] = round(total_over_limit, 2)
                            break
                    else:
                        # 如果没有 package 设备类型，新增一条
                        dist_data.append(
                            {
                                "device_type": "package",
                                "order_count": 0,
                                "cost": round(total_over_limit, 2),
                                "order_count_percentage": 0,
                                "cost_percentage": 0,
                                "over_limit_cost_estimate": round(total_over_limit, 2),
                            }
                        )
                    # 重新计算百分比
                    new_total_cost = sum(d["cost"] for d in dist_data)
                    for d in dist_data:
                        d["cost_percentage"] = (
                            round(d["cost"] / new_total_cost * 100, 2) if new_total_cost > 0 else 0
                        )

        return dist_data

    async def get_top_customers(
        self, start_date: datetime, end_date: datetime, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取 Top 消耗客户"""
        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.company_id,
                func.sum(Invoice.total_amount).label("total_amount"),
            )
            .join(Invoice, Customer.id == Invoice.customer_id)
            .where(
                and_(
                    Invoice.period_start >= start_date,
                    Invoice.period_end <= end_date,
                    Invoice.status != "cancelled",
                    Customer.deleted_at.is_(None),
                )
            )
            .group_by(Customer.id, Customer.name, Customer.company_id)
            .order_by(func.sum(Invoice.total_amount).desc())
            .limit(limit)
        )

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "customer_id": row.id,
                "company_id": row.company_id,
                "customer_name": row.name,
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            }
            for row in result
        ]

    async def get_top_customers_with_metric(
        self,
        start_date: datetime,
        end_date: datetime,
        metric: str = "cost",
        limit: int = 10,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
        industry: Optional[str] = None,
        scale_level: Optional[str] = None,
        consume_level: Optional[str] = None,
        manager_id: Optional[int] = None,
        sales_manager_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取 Top 客户排行（支持多维度筛选）"""
        from ..models.daily_consumption import DailyConsumption

        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.company_id,
                func.sum(DailyConsumption.order_count).label("order_count"),
                func.sum(DailyConsumption.total_cost).label("cost"),
            )
            .join(DailyConsumption, DailyConsumption.customer_id == Customer.id)
            .where(
                and_(
                    DailyConsumption.consumption_date >= start_date,
                    DailyConsumption.consumption_date <= end_date,
                    Customer.deleted_at.is_(None),
                )
            )
        )

        if keyword:
            stmt = stmt.where(Customer.name.ilike(f"%{keyword}%"))
        if account_type:
            stmt = stmt.where(Customer.account_type == account_type)
        if manager_id:
            stmt = stmt.where(Customer.manager_id == manager_id)
        if sales_manager_id:
            stmt = stmt.where(Customer.sales_manager_id == sales_manager_id)
        # 需要关联 CustomerProfile 的筛选条件
        if industry or scale_level or consume_level:
            stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            if scale_level:
                stmt = stmt.where(CustomerProfile.scale_level == scale_level)
            if consume_level:
                stmt = stmt.where(CustomerProfile.consume_level == consume_level)
            if industry:
                industry_names = [n.strip() for n in industry.split(",") if n.strip()]
                if industry_names:
                    stmt = stmt.outerjoin(
                        IndustryType, CustomerProfile.industry_type_id == IndustryType.id
                    )
                    stmt = stmt.where(IndustryType.name.in_(industry_names))

        stmt = stmt.group_by(Customer.id, Customer.name, Customer.company_id)

        # 根据 metric 排序
        if metric == "order_count":
            stmt = stmt.order_by(func.sum(DailyConsumption.order_count).desc())
        else:
            stmt = stmt.order_by(func.sum(DailyConsumption.total_cost).desc())

        stmt = stmt.limit(limit)

        result = (await self.db.execute(stmt)).all()
        customers_data = [
            {
                "customer_id": row.id,
                "company_id": row.company_id,
                "customer_name": row.name,
                "order_count": int(row.order_count) if row.order_count else 0,
                "cost": float(row.cost) if row.cost else 0.0,
            }
            for row in result
        ]

        # 限量套餐超量费用估算：加到每个客户的总费用中
        if customers_data and metric == "cost":
            over_limit_estimates = await self._get_package_over_limit_estimates(
                start_date, end_date
            )
            for c in customers_data:
                est = over_limit_estimates.get(c["customer_id"])
                if est and est["over_limit_cost"] > 0:
                    c["cost"] = round(c["cost"] + est["over_limit_cost"], 2)
                    c["over_limit_cost_estimate"] = round(est["over_limit_cost"], 2)

        return customers_data

    async def get_device_type_distribution(
        self, start_date: datetime, end_date: datetime, customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取设备类型分布"""
        stmt = (
            select(
                InvoiceItem.device_type,
                func.sum(InvoiceItem.quantity).label("total_quantity"),
                func.sum(InvoiceItem.quantity * InvoiceItem.unit_price).label("total_amount"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .where(
                and_(
                    Invoice.period_start >= start_date,
                    Invoice.period_end <= end_date,
                    Invoice.status != "cancelled",
                )
            )
        )

        if customer_id:
            stmt = stmt.where(Invoice.customer_id == customer_id)

        stmt = stmt.group_by(InvoiceItem.device_type)

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "device_type": row.device_type,
                "total_quantity": float(row.total_quantity) if row.total_quantity else 0.0,
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            }
            for row in result
        ]

    async def get_daily_usage_trend(
        self, start_date: datetime, end_date: datetime, customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取每日用量趋势"""
        stmt = select(
            DailyConsumption.consumption_date.label("usage_date"),
            DailyConsumption.device_type,
            func.sum(DailyConsumption.order_count).label("total_quantity"),
        ).where(
            and_(
                DailyConsumption.consumption_date >= start_date,
                DailyConsumption.consumption_date <= end_date,
            )
        )

        if customer_id:
            stmt = stmt.where(DailyConsumption.customer_id == customer_id)

        stmt = stmt.group_by(
            DailyConsumption.consumption_date, DailyConsumption.device_type
        ).order_by(DailyConsumption.consumption_date)

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "usage_date": row.usage_date.isoformat(),
                "device_type": row.device_type,
                "total_quantity": float(row.total_quantity) if row.total_quantity else 0.0,
            }
            for row in result
        ]

    # ========== 回款分析 ==========

    def _apply_customer_filters(
        self,
        stmt,
        *,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
        industry: Optional[str] = None,
        scale_level: Optional[str] = None,
        consume_level: Optional[str] = None,
        manager_id: Optional[int] = None,
        sales_manager_id: Optional[int] = None,
    ):
        """对已 JOIN Customer 的查询追加多维度筛选条件，返回新 stmt"""
        if customer_id:
            stmt = stmt.where(Invoice.customer_id == customer_id)
        if keyword:
            stmt = stmt.where(Customer.name.ilike(f"%{keyword}%"))
        if account_type:
            stmt = stmt.where(Customer.account_type == account_type)
        if scale_level:
            stmt = stmt.where(Customer.scale_level == scale_level)  # pyright: ignore[reportAttributeAccessIssue]
        if consume_level:
            stmt = stmt.where(Customer.consume_level == consume_level)  # pyright: ignore[reportAttributeAccessIssue]
        if manager_id:
            stmt = stmt.where(Customer.manager_id == manager_id)
        if sales_manager_id:
            stmt = stmt.where(Customer.sales_manager_id == sales_manager_id)
        if industry:
            industry_names = [n.strip() for n in industry.split(",") if n.strip()]
            if industry_names:
                stmt = stmt.outerjoin(
                    CustomerProfile, Customer.id == CustomerProfile.customer_id
                ).outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
                stmt = stmt.where(IndustryType.name.in_(industry_names))
        return stmt

    async def get_payment_analysis(
        self,
        start_date: datetime,
        end_date: datetime,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
        industry: Optional[str] = None,
        scale_level: Optional[str] = None,
        consume_level: Optional[str] = None,
        manager_id: Optional[int] = None,
        sales_manager_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取回款分析数据

        应收总额：非草稿、非取消的结算单 total_amount 之和
        减免总额：同上范围的 discount_amount 之和
        已回款：状态为 paid/completed 的结算单 (total_amount - discount_amount) 之和
        回款率：已回款 / 应收净额 × 100
        待回款：应收净额 - 已回款
        """
        # 排除草稿和已取消的结算单（草稿尚未发出，不计入应收）
        active_status_filter = and_(
            Invoice.status != "cancelled",
            Invoice.status != "draft",
        )

        filter_kwargs = dict(
            customer_id=customer_id,
            keyword=keyword,
            account_type=account_type,
            industry=industry,
            scale_level=scale_level,
            consume_level=consume_level,
            manager_id=manager_id,
            sales_manager_id=sales_manager_id,
        )

        # 应收金额（非草稿、非取消）
        invoice_stmt = (
            select(
                func.sum(Invoice.total_amount).label("total_invoiced"),
                func.sum(Invoice.discount_amount).label("total_discount"),
                func.sum(Invoice.total_amount - Invoice.discount_amount).label("total_final"),
            )
            .join(Customer, Invoice.customer_id == Customer.id)
            .where(
                and_(
                    Invoice.period_start >= start_date,
                    Invoice.period_end <= end_date,
                    active_status_filter,
                    Customer.deleted_at.is_(None),
                )
            )
        )
        invoice_stmt = self._apply_customer_filters(invoice_stmt, **filter_kwargs)  # pyright: ignore[reportArgumentType]

        # 已回款金额（状态为 paid/completed 的结算单净额）
        paid_stmt = (
            select(func.sum(Invoice.total_amount - Invoice.discount_amount).label("total_paid"))
            .join(Customer, Invoice.customer_id == Customer.id)
            .where(
                and_(
                    Invoice.period_start >= start_date,
                    Invoice.period_end <= end_date,
                    Invoice.status.in_(["paid", "completed"]),
                    Customer.deleted_at.is_(None),
                )
            )
        )
        paid_stmt = self._apply_customer_filters(paid_stmt, **filter_kwargs)  # pyright: ignore[reportArgumentType]

        invoice_result = (await self.db.execute(invoice_stmt)).first()
        paid_result = (await self.db.execute(paid_stmt)).first()

        total_invoiced = float(invoice_result.total_invoiced or 0)  # pyright: ignore[reportOptionalMemberAccess]
        total_final = float(invoice_result.total_final or 0)  # pyright: ignore[reportOptionalMemberAccess]
        total_paid = float(paid_result.total_paid or 0)  # pyright: ignore[reportOptionalMemberAccess]

        return {
            "total_invoiced": total_invoiced,
            "total_discount": float(invoice_result.total_discount or 0),  # pyright: ignore[reportOptionalMemberAccess]
            "total_final": total_final,
            "total_paid": total_paid,
            "completion_rate": round(total_paid / total_final * 100, 2) if total_final > 0 else 0,
            "difference": round(total_final - total_paid, 2),
        }

    async def get_invoice_status_stats(
        self,
        start_date: datetime,
        end_date: datetime,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
        industry: Optional[str] = None,
        scale_level: Optional[str] = None,
        consume_level: Optional[str] = None,
        manager_id: Optional[int] = None,
        sales_manager_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取结算单状态统计

        返回字段包含 name（状态标识）、count（数量）、percentage（占比）、total_amount（金额）
        """
        filter_kwargs = dict(
            customer_id=customer_id,
            keyword=keyword,
            account_type=account_type,
            industry=industry,
            scale_level=scale_level,
            consume_level=consume_level,
            manager_id=manager_id,
            sales_manager_id=sales_manager_id,
        )

        stmt = (
            select(
                Invoice.status,
                func.count(Invoice.id).label("count"),
                func.sum(Invoice.total_amount - Invoice.discount_amount).label("total_amount"),
            )
            .join(Customer, Invoice.customer_id == Customer.id)
            .where(
                and_(
                    Invoice.period_start >= start_date,
                    Invoice.period_end <= end_date,
                    Customer.deleted_at.is_(None),
                )
            )
        )
        stmt = self._apply_customer_filters(stmt, **filter_kwargs)  # pyright: ignore[reportArgumentType]
        stmt = stmt.group_by(Invoice.status)

        result = (await self.db.execute(stmt)).all()
        total_count = sum(row.count for row in result)  # pyright: ignore[reportArgumentType, reportCallIssue]

        return [
            {
                "name": row.status,
                "count": row.count,
                "percentage": round(row.count / total_count * 100, 1) if total_count > 0 else 0,
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            }
            for row in result
        ]

    async def get_payment_trend(
        self,
        start_date: datetime,
        end_date: datetime,
        months: int = 6,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
        industry: Optional[str] = None,
        scale_level: Optional[str] = None,
        consume_level: Optional[str] = None,
        manager_id: Optional[int] = None,
        sales_manager_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取月度回款趋势数据

        按月聚合应收和已回款金额，用于图表展示。
        """
        from dateutil.relativedelta import relativedelta

        trend: List[Dict[str, Any]] = []
        now = datetime.utcnow().date()

        for i in range(months - 1, -1, -1):
            month_date = now - relativedelta(months=i)
            from datetime import datetime as dt

            from ..utils.timezone import CST, UTC

            month_start = dt(month_date.year, month_date.month, 1, 0, 0, 0, tzinfo=CST).astimezone(
                UTC
            )
            month_end = dt(
                month_date.year,
                month_date.month,
                monthrange(month_date.year, month_date.month)[1],
                23,
                59,
                59,
                tzinfo=CST,
            ).astimezone(UTC)

            data = await self.get_payment_analysis(
                month_start,
                month_end,
                customer_id=customer_id,
                keyword=keyword,
                account_type=account_type,
                industry=industry,
                scale_level=scale_level,
                consume_level=consume_level,
                manager_id=manager_id,
                sales_manager_id=sales_manager_id,
            )
            trend.append(
                {
                    "period": f"{month_date.year}-{month_date.month:02d}",
                    "invoiced": data["total_invoiced"],
                    "discount": data["total_discount"],
                    "paid": data["total_paid"],
                    "completion_rate": data["completion_rate"],
                }
            )

        return trend

    # ========== 健康度分析 ==========

    async def get_customer_health_stats(self) -> Dict[str, Any]:
        """获取客户健康度统计

        活跃客户：最近 90 天有 DailyConsumption 记录的客户
        余额预警：余额 < 1000 的客户
        流失风险：曾有过消耗但最近 90 天无消耗的客户
        """
        from datetime import timedelta

        ninety_days_ago = datetime.utcnow() - timedelta(days=90)

        # 查询 1: 总客户数 + 活跃客户数（通过 DailyConsumption 关联）
        # 拆分为独立查询避免与 CustomerBalance 的笛卡尔积
        active_stmt = (
            select(func.count(func.distinct(DailyConsumption.customer_id)))
            .join(Customer, DailyConsumption.customer_id == Customer.id)
            .where(
                and_(
                    DailyConsumption.consumption_date >= ninety_days_ago.date(),
                    Customer.deleted_at.is_(None),
                )
            )
        )
        active_count = (await self.db.execute(active_stmt)).scalar() or 0

        # 查询 2: 总客户数
        total_stmt = select(func.count(Customer.id)).where(
            and_(Customer.deleted_at.is_(None), Customer.is_disabled.is_(False))
        )
        total_count = (await self.db.execute(total_stmt)).scalar() or 0

        # 查询 3: 余额预警数（独立查询避免笛卡尔积）
        warning_stmt = select(func.count(CustomerBalance.customer_id)).where(
            and_(
                CustomerBalance.total_amount < 1000,
                CustomerBalance.deleted_at.is_(None),
            )
        )
        warning_count = (await self.db.execute(warning_stmt)).scalar() or 0

        # 查询 4: 流失风险客户（曾有过消耗但最近 90 天无消耗）
        # 使用 DailyConsumption 而非 ConsumptionRecord
        has_usage_subq = (
            select(func.distinct(DailyConsumption.customer_id).label("customer_id"))
            .where(DailyConsumption.deleted_at.is_(None))
            .subquery()
        )
        recent_usage_subq = (
            select(func.distinct(DailyConsumption.customer_id).label("customer_id"))
            .where(
                and_(
                    DailyConsumption.consumption_date >= ninety_days_ago.date(),
                    DailyConsumption.deleted_at.is_(None),
                )
            )
            .subquery()
        )
        churn_stmt = (
            select(func.count(Customer.id))
            .join(has_usage_subq, Customer.id == has_usage_subq.c.customer_id)
            .outerjoin(recent_usage_subq, Customer.id == recent_usage_subq.c.customer_id)
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    recent_usage_subq.c.customer_id.is_(None),
                )
            )
        )
        churn_count = (await self.db.execute(churn_stmt)).scalar() or 0

        return {
            "total_customers": total_count,
            "active_customers": active_count,
            "inactive_customers": total_count - active_count,
            "warning_customers": warning_count,
            "churn_risk_customers": churn_count,
            "active_rate": round(active_count / total_count * 100, 2) if total_count > 0 else 0,
        }

    async def get_balance_warning_list(self, threshold: float = 1000) -> List[Dict[str, Any]]:
        """获取余额预警客户列表"""
        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.company_id,
                CustomerBalance.total_amount,
                CustomerBalance.real_amount,
                CustomerBalance.bonus_amount,
                User.real_name.label("manager_name"),
            )
            .join(CustomerBalance, Customer.id == CustomerBalance.customer_id)
            .outerjoin(User, Customer.manager_id == User.id)
            .where(
                and_(
                    CustomerBalance.total_amount < threshold,
                    Customer.deleted_at.is_(None),
                )
            )
            .order_by(CustomerBalance.total_amount.asc())
        )

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "customer_id": row.id,
                "company_id": row.company_id,
                "customer_name": row.name,
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
                "real_amount": float(row.real_amount) if row.real_amount else 0.0,
                "bonus_amount": float(row.bonus_amount) if row.bonus_amount else 0.0,
                "manager_name": row.manager_name or "未分配",
            }
            for row in result
        ]

    async def get_inactive_customers(
        self, days: int = 30, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取长期未消耗客户列表

        基于 DailyConsumption 表查找：曾经有消耗记录但最近 N 天无消耗的客户。
        返回 days 字段表示距离上次消耗的天数。
        """
        from datetime import timedelta

        cutoff_date = (datetime.utcnow() - timedelta(days=days)).date()

        # 子查询：每个客户最近一次消耗日期
        last_usage_subq = (
            select(
                DailyConsumption.customer_id.label("customer_id"),
                func.max(DailyConsumption.consumption_date).label("last_date"),
            )
            .where(DailyConsumption.deleted_at.is_(None))
            .group_by(DailyConsumption.customer_id)
            .subquery()
        )

        # 子查询：最近 N 天内有消耗的客户
        recent_usage_subq = (
            select(func.distinct(DailyConsumption.customer_id).label("customer_id"))
            .where(
                and_(
                    DailyConsumption.consumption_date >= cutoff_date,
                    DailyConsumption.deleted_at.is_(None),
                )
            )
            .subquery()
        )

        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.company_id,
                Customer.manager_id,
                User.real_name.label("manager_name"),
                last_usage_subq.c.last_date.label("last_consumption_date"),
            )
            .join(last_usage_subq, Customer.id == last_usage_subq.c.customer_id)
            .outerjoin(recent_usage_subq, Customer.id == recent_usage_subq.c.customer_id)
            .outerjoin(User, Customer.manager_id == User.id)
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    recent_usage_subq.c.customer_id.is_(None),
                )
            )
            .order_by(last_usage_subq.c.last_date.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        now = datetime.utcnow().date()
        result = (await self.db.execute(stmt)).all()
        items = []
        for row in result:
            # consumption_date 为 timestamptz（datetime），统一转为 date 再计算天数
            last_date = row.last_consumption_date
            if isinstance(last_date, datetime):
                last_date = last_date.date()
            items.append(
                {
                    "customer_id": row.id,
                    "company_id": row.company_id,
                    "customer_name": row.name,
                    "manager_id": row.manager_id,
                    "manager_name": row.manager_name or "未分配",
                    "last_consumption_date": (
                        row.last_consumption_date.isoformat() if row.last_consumption_date else None
                    ),
                    "days": (now - last_date).days if last_date else days,
                }
            )
        return items

    # ========== 画像分析 ==========

    async def get_industry_distribution(self) -> List[Dict[str, Any]]:
        """获取行业分布

        以 Customer 为主表 LEFT JOIN CustomerProfile + IndustryType，
        确保所有未删除客户都被统计（无画像的客户归入"未分类"）。
        """
        stmt = (
            select(
                IndustryType.name,
                func.count(Customer.id).label("count"),
            )
            .select_from(Customer)
            .outerjoin(
                CustomerProfile,
                and_(
                    Customer.id == CustomerProfile.customer_id,
                    CustomerProfile.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                IndustryType,
                and_(
                    CustomerProfile.industry_type_id == IndustryType.id,
                    IndustryType.deleted_at.is_(None),
                ),
            )
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    Customer.is_disabled.is_(False),
                )
            )
            .group_by(IndustryType.name)
            .order_by(func.count(Customer.id).desc())
        )

        result = (await self.db.execute(stmt)).all()
        total = sum(row.count for row in result)  # pyright: ignore[reportArgumentType, reportCallIssue]

        return [
            {
                "industry": row.name or "未分类",
                "count": row.count,
                "percentage": round(row.count / total * 100, 2) if total > 0 else 0,
            }
            for row in result
        ]

    async def get_scale_level_stats(self) -> List[Dict[str, Any]]:
        """获取客户规模等级统计

        以 Customer 为主表 LEFT JOIN CustomerProfile，确保所有未删除客户都被统计。
        将非标准值（NULL 或不在 S/A/B/C/D/E 中的旧值）归类为"未分类"，
        并按 S→A→B→C→D→E→未分类 的固定顺序返回。
        """
        valid_levels = ["S", "A", "B", "C", "D", "E"]
        normalized_level = case(
            (CustomerProfile.scale_level.in_(valid_levels), CustomerProfile.scale_level),
            else_="未分类",
        ).label("scale_level")

        stmt = (
            select(
                normalized_level,
                func.count(Customer.id).label("count"),
            )
            .select_from(Customer)
            .outerjoin(
                CustomerProfile,
                and_(
                    Customer.id == CustomerProfile.customer_id,
                    CustomerProfile.deleted_at.is_(None),
                ),
            )
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    Customer.is_disabled.is_(False),
                )
            )
            .group_by(normalized_level)
        )

        result = (await self.db.execute(stmt)).all()
        total = sum(row.count for row in result)  # pyright: ignore[reportArgumentType, reportCallIssue]

        # 构建 level -> count 映射，按固定顺序输出
        count_map = {row.scale_level: row.count for row in result}
        ordered_levels = valid_levels + ["未分类"]

        return [
            {
                "scale_level": level,
                "count": count_map.get(level, 0),
                "percentage": round(count_map.get(level, 0) / total * 100, 2) if total > 0 else 0,
            }
            for level in ordered_levels
            if count_map.get(level, 0)
            > 0  # 隐藏 count=0 的分类  # pyright: ignore[reportOperatorIssue]
        ]

    async def get_consume_level_stats(self) -> List[Dict[str, Any]]:
        """获取客户消费等级统计

        以 Customer 为主表 LEFT JOIN CustomerProfile，确保所有未删除客户都被统计。
        """
        stmt = (
            select(
                CustomerProfile.consume_level,
                func.count(Customer.id).label("count"),
            )
            .select_from(Customer)
            .outerjoin(
                CustomerProfile,
                and_(
                    Customer.id == CustomerProfile.customer_id,
                    CustomerProfile.deleted_at.is_(None),
                ),
            )
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    Customer.is_disabled.is_(False),
                )
            )
            .group_by(CustomerProfile.consume_level)
            .order_by(func.count(Customer.id).desc())
        )

        result = (await self.db.execute(stmt)).all()
        total = sum(row.count for row in result)  # pyright: ignore[reportArgumentType, reportCallIssue]

        return [
            {
                "consume_level": row.consume_level or "未分类",
                "count": row.count,
                "percentage": round(row.count / total * 100, 2) if total > 0 else 0,
            }
            for row in result
        ]

    async def get_real_estate_stats(self) -> Dict[str, Any]:
        """获取房产客户统计

        is_real_estate 是 Customer 表字段，无需 JOIN CustomerProfile。
        同时返回有画像的客户数，供前端计算"画像覆盖率"。
        """
        total_stmt = select(func.count(Customer.id)).where(
            and_(
                Customer.deleted_at.is_(None),
                Customer.is_disabled.is_(False),
            )
        )
        total = (await self.db.execute(total_stmt)).scalar() or 0

        # 房产客户数：直接查 Customer 表，不 JOIN Profile
        real_estate_stmt = select(func.count(Customer.id)).where(
            and_(
                Customer.deleted_at.is_(None),
                Customer.is_disabled.is_(False),
                Customer.is_real_estate.is_(True),
            ),
        )
        real_estate = (await self.db.execute(real_estate_stmt)).scalar() or 0

        # 有画像的客户数（用于画像覆盖率）
        profile_stmt = (
            select(func.count(CustomerProfile.id))
            .join(Customer, CustomerProfile.customer_id == Customer.id)
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    Customer.is_disabled.is_(False),
                    CustomerProfile.deleted_at.is_(None),
                )
            )
        )
        profile_count = (await self.db.execute(profile_stmt)).scalar() or 0

        return {
            "total_customers": total,
            "real_estate_customers": real_estate,
            "non_real_estate_customers": total - real_estate,
            "real_estate_percentage": round(real_estate / total * 100, 2) if total > 0 else 0,
            "profile_count": profile_count,
            "profile_coverage_rate": round(profile_count / total * 100, 2) if total > 0 else 0,
        }

    async def get_real_estate_industry_stats(self) -> List[Dict[str, Any]]:
        """获取房产客户行业子分类统计

        以 Customer 为主表 LEFT JOIN CustomerProfile + IndustryType，
        确保所有房产客户都被统计（无画像的归入"未分类"）。
        """
        stmt = (
            select(
                IndustryType.name,
                func.count(Customer.id).label("count"),
            )
            .select_from(Customer)
            .outerjoin(
                CustomerProfile,
                and_(
                    Customer.id == CustomerProfile.customer_id,
                    CustomerProfile.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                IndustryType,
                and_(
                    CustomerProfile.industry_type_id == IndustryType.id,
                    IndustryType.deleted_at.is_(None),
                ),
            )
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    Customer.is_disabled.is_(False),
                    Customer.is_real_estate.is_(True),
                )
            )
            .group_by(IndustryType.name)
            .order_by(func.count(Customer.id).desc())
        )

        result = (await self.db.execute(stmt)).all()
        total = sum(row.count for row in result)  # pyright: ignore[reportArgumentType, reportCallIssue]

        return [
            {
                "industry": row.name or "未分类",
                "count": row.count,
                "percentage": round(row.count / total * 100, 2) if total > 0 else 0,
            }
            for row in result
        ]

    # ========== 预测回款 ==========

    async def predict_monthly_payment(
        self,
        year: int,
        month: Optional[int] = None,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """预测月度回款

        基于客户该时段的实际消耗数据（DailyConsumption.total_cost）预测回款金额。
        month=None 表示全年汇总。

        以 DailyConsumption 为主表聚合（按 customer_id + device_type），
        再 LEFT JOIN PricingRule 获取计费类型，避免定价规则重复导致的笛卡尔积膨胀。

        Returns:
            预测明细列表，每条记录包含客户、设备类型、用量（订单数）、预测金额等信息。
        """
        # 确定查询的时间范围（转为 UTC datetime）
        from datetime import datetime as dt

        from ..utils.timezone import CST, UTC

        if month is not None:
            period_start = dt(year, month, 1, 0, 0, 0, tzinfo=CST).astimezone(UTC)
            last_day = monthrange(year, month)[1]
            period_end = dt(year, month, last_day, 23, 59, 59, tzinfo=CST).astimezone(UTC)
        else:
            period_start = dt(year, 1, 1, 0, 0, 0, tzinfo=CST).astimezone(UTC)
            period_end = dt(year, 12, 31, 23, 59, 59, tzinfo=CST).astimezone(UTC)

        # 以 DailyConsumption 为主表聚合消耗，再关联 Customer 和 PricingRule
        # 使用子查询先聚合消耗，避免 LEFT JOIN PricingRule 多行导致 SUM 翻倍
        usage_subq = (
            select(
                DailyConsumption.customer_id.label("customer_id"),
                DailyConsumption.device_type.label("device_type"),
                func.coalesce(func.sum(DailyConsumption.total_cost), 0).label("total_cost"),
                func.coalesce(func.sum(DailyConsumption.order_count), 0).label("total_orders"),
            )
            .where(
                DailyConsumption.consumption_date >= period_start,
                DailyConsumption.consumption_date <= period_end,
            )
            .group_by(DailyConsumption.customer_id, DailyConsumption.device_type)
            .subquery()
        )

        stmt = (
            select(
                Customer.id.label("customer_id"),
                Customer.name.label("customer_name"),
                Customer.company_id,
                usage_subq.c.device_type,
                usage_subq.c.total_cost,
                usage_subq.c.total_orders,
                func.max(PricingRule.pricing_type).label("pricing_type"),
            )
            .select_from(usage_subq)
            .join(Customer, usage_subq.c.customer_id == Customer.id)
            .outerjoin(
                PricingRule,
                and_(
                    Customer.id == PricingRule.customer_id,
                    usage_subq.c.device_type == PricingRule.device_type,
                    PricingRule.deleted_at.is_(None),
                    PricingRule.effective_date <= period_end,
                    or_(
                        PricingRule.expiry_date.is_(None),
                        PricingRule.expiry_date >= period_start,
                    ),
                ),
            )
            .where(Customer.deleted_at.is_(None))
            .group_by(
                Customer.id,
                Customer.name,
                Customer.company_id,
                usage_subq.c.device_type,
                usage_subq.c.total_cost,
                usage_subq.c.total_orders,
            )
        )

        if customer_id:
            stmt = stmt.where(Customer.id == customer_id)
        if keyword:
            stmt = stmt.where(Customer.name.ilike(f"%{keyword}%"))

        result = (await self.db.execute(stmt)).all()

        predictions = []
        for row in result:
            predicted_amount = float(row.total_cost or 0)
            if predicted_amount <= 0:
                continue

            predictions.append(
                {
                    "customer_id": row.customer_id,
                    "company_id": row.company_id,
                    "customer_name": row.customer_name,
                    "device_type": row.device_type,
                    "quantity": int(row.total_orders or 0),
                    "pricing_type": row.pricing_type or "unknown",
                    "predicted_amount": predicted_amount,
                }
            )

        # 按预测金额降序排列
        predictions.sort(key=lambda x: x["predicted_amount"], reverse=True)

        return predictions

    async def get_prediction_summary(
        self,
        year: int,
        month: Optional[int] = None,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取预测回款汇总统计

        返回预测总额、已确认回款（已支付结算单）、待确认回款、完成率等。
        """
        from calendar import monthrange

        predictions = await self.predict_monthly_payment(year, month, customer_id, keyword)

        total_predicted = sum(p["predicted_amount"] for p in predictions)
        predicted_customers = len({p["customer_id"] for p in predictions})

        # 查询已确认回款（已支付/已完成的结算单净额）
        if month is not None:
            period_start = date(year, month, 1)
            period_end = date(year, month, monthrange(year, month)[1])
        else:
            period_start = date(year, 1, 1)
            period_end = date(year, 12, 31)

        confirmed_stmt = (
            select(
                func.coalesce(func.sum(Invoice.total_amount - Invoice.discount_amount), 0).label(
                    "confirmed_amount"
                )
            )
            .join(Customer, Invoice.customer_id == Customer.id)
            .where(
                and_(
                    Invoice.period_start >= period_start,
                    Invoice.period_end <= period_end,
                    Invoice.status.in_(["paid", "completed"]),
                    Customer.deleted_at.is_(None),
                )
            )
        )
        if customer_id:
            confirmed_stmt = confirmed_stmt.where(Invoice.customer_id == customer_id)
        if keyword:
            confirmed_stmt = confirmed_stmt.where(Customer.name.ilike(f"%{keyword}%"))

        confirmed_amount = float((await self.db.execute(confirmed_stmt)).scalar() or 0)

        pending_amount = round(total_predicted - confirmed_amount, 2)
        completion_rate = (
            round(confirmed_amount / total_predicted * 100, 2) if total_predicted > 0 else 0
        )

        return {
            "total_predicted": round(total_predicted, 2),
            "confirmed_amount": round(confirmed_amount, 2),
            "pending_amount": pending_amount,
            "completion_rate": completion_rate,
            "predicted_customers": predicted_customers,
        }

    # ========== 预测消费（新引擎，替代 predict_monthly_payment） ==========

    async def forecast_consumption(
        self,
        year: int,
        month: Optional[int] = None,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        device_type: Optional[str] = None,
        apply_to: str = "all",
        forecast_months: Optional[int] = None,
        forecast_until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """预测消费（MVP 版）

        基于历史用量（order_count）和单价矩阵估算未来月份消费。
        渐进式算法：数据不足时用最近月份保持，数据积累后自动升级。

        Args:
            year: 目标年份
            month: 目标月份（None=全年）
            customer_id: 按客户筛选
            keyword: 按名称搜索
            device_type: 按设备类型筛选
            apply_to: 'all' 更新历史及后续 / 'future_only' 仅后续月份
            forecast_months: 预测月份数（1-24）
            forecast_until: 截止月份 YYYY-MM

        Returns:
            预测明细列表，含估算用量、单价、预测金额、方法标注、活跃标记
        """
        from calendar import monthrange

        unit_prices = await self.get_unit_prices()

        # 1. 获取最新完整月作为用量基线（MVP 预测基于最新月保持）
        latest_month = await self._get_latest_usage_month()
        if not latest_month:
            return []

        latest_start = date(latest_month.year, latest_month.month, 1)
        latest_end = date(
            latest_month.year,
            latest_month.month,
            monthrange(latest_month.year, latest_month.month)[1],
        )

        # 3. 查询最新完整月的客户×设备用量
        usage_subq = (
            select(
                DailyConsumption.customer_id.label("customer_id"),
                DailyConsumption.device_type.label("device_type"),
                func.coalesce(func.sum(DailyConsumption.order_count), 0).label("total_orders"),
            )
            .where(
                DailyConsumption.consumption_date >= latest_start,
                DailyConsumption.consumption_date <= latest_end,
            )
            .group_by(DailyConsumption.customer_id, DailyConsumption.device_type)
            .subquery()
        )

        # 4. 查询活跃度（最近 3 个月有消费记录）
        from dateutil.relativedelta import relativedelta

        active_start = latest_start - relativedelta(months=2)

        # 活跃客户子查询
        active_subq = (
            select(DailyConsumption.customer_id.label("active_cid"))
            .where(
                DailyConsumption.consumption_date >= active_start,
                DailyConsumption.consumption_date <= latest_end,
            )
            .group_by(DailyConsumption.customer_id)
            .subquery()
        )

        # 5. 查询消费等级（冷启动用）
        profile_subq = (
            select(
                CustomerProfile.customer_id.label("profile_cid"),
                CustomerProfile.consume_level.label("consume_level"),
            )
            .where(CustomerProfile.customer_id.isnot(None))
            .subquery()
        )

        # 主查询
        stmt = (
            select(
                Customer.id.label("customer_id"),
                Customer.name.label("customer_name"),
                Customer.company_id,
                usage_subq.c.device_type,
                usage_subq.c.total_orders,
                profile_subq.c.consume_level,
                active_subq.c.active_cid.isnot(None).label("is_active"),
            )
            .select_from(usage_subq)
            .join(Customer, usage_subq.c.customer_id == Customer.id)
            .outerjoin(profile_subq, usage_subq.c.customer_id == profile_subq.c.profile_cid)
            .outerjoin(active_subq, usage_subq.c.customer_id == active_subq.c.active_cid)
            .where(Customer.deleted_at.is_(None))
        )

        if customer_id:
            stmt = stmt.where(Customer.id == customer_id)
        if keyword:
            stmt = stmt.where(Customer.name.ilike(f"%{keyword}%"))
        if device_type:
            stmt = stmt.where(usage_subq.c.device_type == device_type)

        result = (await self.db.execute(stmt)).all()

        # 6. 收集所有设备类型的用量分布（冷启动用）
        median_usage = await self._get_median_usage_by_type_and_level(device_type)

        # 7. 构建预测结果
        forecasts = []
        for row in result:
            original_orders = int(row.total_orders or 0)
            orders = original_orders
            dev_type = row.device_type
            consume_level = row.consume_level
            is_active = bool(row.is_active)

            # 7a. 冷启动：如果客户该设备类型有 0 用量，用同类型+同等级中位数
            used_cold_start = False
            if orders <= 0 and consume_level:
                key = (dev_type, consume_level)
                if key in median_usage:
                    orders = median_usage[key]
                    used_cold_start = True
                elif dev_type in median_usage:
                    orders = median_usage[dev_type]
                    used_cold_start = True

            # 7b. 离群截断
            capped_orders = await self._cap_outlier(orders, dev_type)

            # 7c. 应用单价
            unit_price = unit_prices.get(dev_type, 10.0)
            forecast_amount = round(capped_orders * unit_price, 2)

            # 7d. 方法标注（基于原始用量判断）
            method = "historical_hold"
            if used_cold_start:
                method = "cold_start"
            elif original_orders > 0 and capped_orders != orders:
                method = "trimmed"

            if forecast_amount <= 0:
                continue

            forecasts.append(
                {
                    "customer_id": row.customer_id,
                    "company_id": row.company_id,
                    "customer_name": row.customer_name,
                    "device_type": dev_type,
                    "estimated_usage": capped_orders,
                    "unit_price": unit_price,
                    "forecast_amount": forecast_amount,
                    "forecast_method": method,
                    "is_active": is_active,
                    "consume_level": consume_level or "",
                }
            )

        forecasts.sort(key=lambda x: x["forecast_amount"], reverse=True)

        # 限制预测返回条数（forecast_months 参数影响趋势图范围）
        if forecast_months and forecast_months > 0 and len(forecasts) > forecast_months:
            forecasts = forecasts[:forecast_months]

        return forecasts

    async def get_forecast_summary(
        self,
        year: int,
        month: Optional[int] = None,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        device_type: Optional[str] = None,
        apply_to: str = "all",
        forecast_months: Optional[int] = None,
        forecast_until: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取消费预测汇总统计"""
        from calendar import monthrange

        forecasts = await self.forecast_consumption(
            year,
            month,
            customer_id,
            keyword,
            device_type,
            apply_to=apply_to,
            forecast_months=forecast_months,
            forecast_until=forecast_until,
        )

        # 活跃客户的总预测
        active_forecasts = [f for f in forecasts if f["is_active"]]
        total_forecast = sum(f["forecast_amount"] for f in active_forecasts)
        active_count = len({f["customer_id"] for f in active_forecasts})
        total_count = len({f["customer_id"] for f in forecasts})

        # 本月实际消耗（实盘数据）
        now = datetime.utcnow()
        from datetime import datetime as dt

        from ..utils.timezone import CST, UTC

        if month is not None:
            actual_start = dt(year, month, 1, 0, 0, 0, tzinfo=CST).astimezone(UTC)
            last_day = monthrange(year, month)[1]
            actual_end = dt(year, month, last_day, 23, 59, 59, tzinfo=CST).astimezone(UTC)
        else:
            actual_start = dt(year, 1, 1, 0, 0, 0, tzinfo=CST).astimezone(UTC)
            actual_end = now.date()

        actual_stmt = select(func.coalesce(func.sum(DailyConsumption.total_cost), 0)).where(
            DailyConsumption.consumption_date >= actual_start,
            DailyConsumption.consumption_date <= actual_end,
        )
        actual_this_month = float((await self.db.execute(actual_stmt)).scalar() or 0)

        # 环比变化（上月 vs 本月实际）
        from dateutil.relativedelta import relativedelta

        last_month = now.date().replace(day=1) - relativedelta(days=1)
        mom_change = 0.0
        if actual_this_month > 0:
            last_stmt = select(func.coalesce(func.sum(DailyConsumption.total_cost), 0)).where(
                DailyConsumption.consumption_date >= date(last_month.year, last_month.month, 1),
                DailyConsumption.consumption_date
                <= date(
                    last_month.year,
                    last_month.month,
                    monthrange(last_month.year, last_month.month)[1],
                ),
            )
            last_actual = float((await self.db.execute(last_stmt)).scalar() or 0)
            if last_actual > 0:
                mom_change = round((actual_this_month / last_actual - 1) * 100, 2)

        # 置信度
        confidence = await self._calculate_confidence()

        return {
            "total_forecast": round(total_forecast, 2),
            "actual_this_month": round(actual_this_month, 2),
            "month_over_month_change": mom_change,
            "active_customer_count": active_count,
            "total_customer_count": total_count,
            "confidence": confidence,
        }

    async def get_forecast_trend(
        self,
        year: int,
        apply_to: str = "all",
        forecast_months: Optional[int] = None,
        forecast_until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取预测 vs 实际消费趋势

        Args:
            year: 目标年份
            apply_to: 'all' 返回全年 / 'future_only' 从当前月开始
            forecast_months: 预测月份数（从起始月开始）
            forecast_until: 截止月份 YYYY-MM

        每月返回预测金额（用量×单价）和实际消费（已发生实盘）。
        """
        from calendar import monthrange
        from datetime import datetime

        # 计算月份范围
        current_month = datetime.now().month

        # 确定起始月份
        if apply_to == "future_only":
            start_month = current_month
        else:
            start_month = 1

        # 确定结束月份
        if forecast_until:
            # 解析截止月份
            try:
                end_year, end_month_num = map(int, forecast_until.split("-"))
                if end_year == year:
                    end_month = min(end_month_num, 12)
                else:
                    end_month = 12
            except (ValueError, TypeError):
                end_month = 12
        elif forecast_months and forecast_months > 0:
            # 从起始月开始计算 N 个月，最多 12 月
            end_month = min(start_month + forecast_months - 1, 12)
        else:
            end_month = 12

        # 边界条件：如果起始月份超过结束月份，返回空数组
        if start_month > end_month:
            return []

        # 一次性计算未来月份的预测值（口径与 forecast_consumption 一致）
        future_forecast = await self._estimate_future_consumption()

        trend = []
        for m in range(start_month, end_month + 1):
            from datetime import datetime as dt

            from ..utils.timezone import CST, UTC

            month_start = dt(year, m, 1, 0, 0, 0, tzinfo=CST).astimezone(UTC)
            last_day_m = monthrange(year, m)[1]
            month_end = dt(year, m, last_day_m, 23, 59, 59, tzinfo=CST).astimezone(UTC)

            # 实际消费
            actual_stmt = select(func.coalesce(func.sum(DailyConsumption.total_cost), 0)).where(
                DailyConsumption.consumption_date >= month_start,
                DailyConsumption.consumption_date <= month_end,
            )
            actual = float((await self.db.execute(actual_stmt)).scalar() or 0)

            # 判断是否已发生：只有有实际数据才标记为实盘
            is_actual = actual > 0

            # 预测值：如果是实际月份，用实际值；否则用统一预测值
            forecast = actual if is_actual else future_forecast

            trend.append(
                {
                    "month": f"{year}-{m:02d}",
                    "actual": round(actual, 2) if actual > 0 else None,
                    "forecast": round(forecast, 2),
                    "is_actual": is_actual,
                }
            )

        return trend

    async def get_data_readiness(self) -> Dict[str, Any]:
        """获取数据就绪度信息（横幅+置信度用）"""
        # 查询有数据的最早和最晚月份
        stmt = select(
            func.min(DailyConsumption.consumption_date),
            func.max(DailyConsumption.consumption_date),
        )
        row = (await self.db.execute(stmt)).one()
        min_date, max_date = row[0], row[1]

        if not min_date or not max_date:
            return {
                "months_with_data": 0,
                "total_months_target": 12,
                "customer_coverage_pct": 0.0,
                "confidence": "low",
                "earliest_data_month": None,
                "latest_data_month": None,
            }

        # 客户总数
        total_customers = (
            await self.db.execute(
                select(func.count(Customer.id)).where(Customer.deleted_at.is_(None))
            )
        ).scalar() or 0

        # 有消费数据的客户数
        customers_with_data = (
            await self.db.execute(select(func.count(func.distinct(DailyConsumption.customer_id))))
        ).scalar() or 0

        # 有数据的月份数
        months_with_data = (
            await self.db.execute(
                select(
                    func.count(
                        func.distinct(
                            func.concat(
                                func.extract("year", DailyConsumption.consumption_date),
                                "-",
                                func.extract("month", DailyConsumption.consumption_date),
                            )
                        )
                    )
                )
            )
        ).scalar() or 0

        coverage_pct = (
            round(customers_with_data / total_customers * 100, 1) if total_customers > 0 else 0.0
        )
        confidence = "low"
        if months_with_data >= 12:
            confidence = "high"
        elif months_with_data >= 3:
            confidence = "medium"

        return {
            "months_with_data": months_with_data,
            "total_months_target": 12,
            "customer_coverage_pct": coverage_pct,
            "confidence": confidence,
            "earliest_data_month": str(min_date) if min_date else None,
            "latest_data_month": str(max_date) if max_date else None,
        }

    # ========== 预测消费辅助方法 ==========

    @staticmethod
    def _month_key(month_str: str) -> int:
        """将 'YYYY-MM' 转换为可比较的整数键"""
        year_s, month_s = month_str.split("-")
        return int(year_s) * 12 + int(month_s)

    async def _get_latest_usage_month(self) -> Optional[date]:
        """获取有消费数据的最新完整月"""
        stmt = select(func.max(DailyConsumption.consumption_date))
        max_date = (await self.db.execute(stmt)).scalar()
        if not max_date:
            return None
        return date(max_date.year, max_date.month, 1)

    async def _get_median_usage_by_type_and_level(self, device_type: Optional[str] = None) -> Dict:
        """获取各设备类型×消费等级的平均用量（冷启动用）

        用 AVG 近似中位数，MVP 阶段精度足够。
        """
        stmt = (
            select(
                DailyConsumption.device_type,
                CustomerProfile.consume_level,
                func.avg(DailyConsumption.order_count).label("avg_orders"),
            )
            .join(CustomerProfile, DailyConsumption.customer_id == CustomerProfile.customer_id)
            .where(
                DailyConsumption.order_count > 0,
            )
            .group_by(
                DailyConsumption.device_type,
                CustomerProfile.consume_level,
            )
        )

        if device_type:
            stmt = stmt.where(DailyConsumption.device_type == device_type)

        result = (await self.db.execute(stmt)).all()

        medians = {}
        for row in result:
            if row.consume_level:
                key = (row.device_type, row.consume_level)
                medians[key] = int(row.avg_orders or 0)
            # 设备类型级兜底
            type_key = row.device_type
            if type_key not in medians:
                medians[type_key] = int(row.avg_orders or 0)
            else:
                medians[type_key] = max(medians[type_key], int(row.avg_orders or 0))

        return medians

    async def _cap_outlier(self, orders: int, device_type: str) -> int:
        """离群截断：超过同设备类型 3 倍均值时截断"""
        stmt = select(func.avg(DailyConsumption.order_count)).where(
            DailyConsumption.device_type == device_type,
            DailyConsumption.order_count > 0,
        )
        avg = (await self.db.execute(stmt)).scalar()
        if avg is None or avg <= 0:
            return orders
        cap = int(avg * 3)
        return min(orders, cap) if orders > cap else orders

    async def _calculate_confidence(self) -> str:
        """计算置信度（基于数据月份数）"""
        months = (
            await self.db.execute(
                select(
                    func.count(
                        func.distinct(
                            func.concat(
                                func.extract("year", DailyConsumption.consumption_date),
                                "-",
                                func.extract("month", DailyConsumption.consumption_date),
                            )
                        )
                    )
                )
            )
        ).scalar() or 0
        if months >= 12:
            return "high"
        if months >= 3:
            return "medium"
        return "low"

    async def _estimate_future_consumption(self) -> float:
        """估算未来月份的总消费（活跃客户预测口径，与 summary 一致）"""
        # 复用 forecast_consumption 计算活跃客户的预测总额
        now = datetime.utcnow()
        forecasts = await self.forecast_consumption(year=now.year)
        active_forecasts = [f for f in forecasts if f["is_active"]]
        return sum(f["forecast_amount"] for f in active_forecasts)

    # ========== 单价配置 ==========

    async def get_unit_prices(self) -> Dict[str, float]:
        """获取单价配置：优先从配置表，无数据时回退到 config.py 默认值"""
        try:
            stmt = select(ForecastUnitPrice)
            result = (await self.db.execute(stmt)).scalars().all()
        except ProgrammingError as exc:
            # 表缺失（远程未跑迁移）时兜底，避免预测消费接口 500
            logger.warning("读取 forecast_unit_prices 表失败，回退默认单价: %s", exc)
            from ..config import get_settings

            return dict(get_settings().consumption_forecast_unit_prices)
        if result:
            return {row.device_type: float(row.unit_price) for row in result}
        from ..config import get_settings

        return dict(get_settings().consumption_forecast_unit_prices)

    async def update_unit_prices(self, prices: Dict[str, float]) -> None:
        """更新单价配置"""
        for device_type, unit_price in prices.items():
            stmt = select(ForecastUnitPrice).where(ForecastUnitPrice.device_type == device_type)
            existing = (await self.db.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.unit_price = unit_price
            else:
                self.db.add(ForecastUnitPrice(device_type=device_type, unit_price=unit_price))

    async def get_prediction_trend(self, year: int) -> List[Dict[str, Any]]:
        """获取全年 12 个月预测 vs 实际回款趋势

        每月返回预测金额（消耗总额）和实际回款（已支付结算单净额）。
        """
        from calendar import monthrange

        trend = []
        for m in range(1, 13):
            from datetime import datetime as dt

            from ..utils.timezone import CST, UTC

            month_start = dt(year, m, 1, 0, 0, 0, tzinfo=CST).astimezone(UTC)
            last_day_m = monthrange(year, m)[1]
            month_end = dt(year, m, last_day_m, 23, 59, 59, tzinfo=CST).astimezone(UTC)

            # 预测金额 = 当月消耗总额
            predicted_stmt = select(
                func.coalesce(func.sum(DailyConsumption.total_cost), 0).label("predicted")
            ).where(
                DailyConsumption.consumption_date >= month_start,
                DailyConsumption.consumption_date <= month_end,
            )
            predicted = float((await self.db.execute(predicted_stmt)).scalar() or 0)

            # 实际回款 = 当月已支付/已完成结算单净额
            actual_stmt = select(
                func.coalesce(func.sum(Invoice.total_amount - Invoice.discount_amount), 0).label(
                    "actual"
                )
            ).where(
                Invoice.period_start >= month_start,
                Invoice.period_end <= month_end,
                Invoice.status.in_(["paid", "completed"]),
            )
            actual = float((await self.db.execute(actual_stmt)).scalar() or 0)

            trend.append(
                {
                    "month": f"{year}-{m:02d}",
                    "predicted": round(predicted, 2),
                    "actual": round(actual, 2),
                }
            )

        return trend

    # ========== 预测准确度追踪 ==========

    async def record_prediction_accuracy(self) -> Dict[str, Any]:
        """记录预测准确度（预测 vs 实际消费）

        每月结束后，用 AuditLog.extra_metadata 记录预测与实际的偏差，
        计算 MAPE 和偏差百分比。偏差 >30% 时返回告警标记。

        Returns:
            准确度记录 dict（含 mape, deviation_pct, alert 标记）
        """
        from calendar import monthrange

        # 取最新数据月作为实际数据
        latest = await self._get_latest_usage_month()
        if not latest:
            return {"recorded": False, "reason": "no_data"}

        # 预测值（活跃客户预测口径，与 summary 一致）
        forecast_total = await self._estimate_future_consumption()

        # 实际值（最新完整月的 total_cost，注意开发环境 total_cost 可能不可信）
        latest_start = date(latest.year, latest.month, 1)
        latest_end = date(latest.year, latest.month, monthrange(latest.year, latest.month)[1])
        actual_stmt = select(func.coalesce(func.sum(DailyConsumption.total_cost), 0)).where(
            DailyConsumption.consumption_date >= latest_start,
            DailyConsumption.consumption_date <= latest_end,
        )
        actual_total = float((await self.db.execute(actual_stmt)).scalar() or 0)

        if actual_total <= 0:
            return {"recorded": False, "reason": "no_actual_data"}

        # MAPE 和偏差
        mape = round(abs(forecast_total - actual_total) / actual_total * 100, 2)
        deviation_pct = round((forecast_total - actual_total) / actual_total * 100, 2)
        alert = deviation_pct > 30

        # 记录到审计日志
        log = AuditLog(
            user_id=None,
            action="forecast_accuracy",
            module="analytics",
            record_id=latest.year,
            record_type="monthly_forecast",
            changes=None,
            operation_type="standard",
            extra_metadata={
                "year": latest.year,
                "month": latest.month,
                "forecast_total": round(forecast_total, 2),
                "actual_total": round(actual_total, 2),
                "mape": mape,
                "deviation_pct": deviation_pct,
                "alert": alert,
            },
        )
        self.db.add(log)
        await self.db.flush()

        return {
            "recorded": True,
            "year": latest.year,
            "month": latest.month,
            "forecast_total": round(forecast_total, 2),
            "actual_total": round(actual_total, 2),
            "mape": mape,
            "deviation_pct": deviation_pct,
            "alert": alert,
        }

    # ========== 余额趋势 ==========

    async def get_balance_trend(self, customer_id: int, months: int = 6) -> List[Dict[str, Any]]:
        """获取客户余额趋势（按月聚合）"""
        from dateutil.relativedelta import relativedelta

        now = datetime.utcnow()
        end_date = now.date()
        start_date = end_date - relativedelta(months=months - 1)
        start_of_period = date(start_date.year, start_date.month, 1)

        # 获取当前余额
        current_balance = await self._get_current_balance(customer_id)
        if current_balance is None:
            return []

        # 查询趋势窗口内的充值记录（按月聚合）
        recharge_stmt = select(
            extract("year", RechargeRecord.created_at).label("year"),
            extract("month", RechargeRecord.created_at).label("month"),
            func.sum(RechargeRecord.real_amount).label("real_amount"),
            func.sum(RechargeRecord.bonus_amount).label("bonus_amount"),
        ).where(
            and_(
                RechargeRecord.customer_id == customer_id,
                RechargeRecord.created_at >= datetime.combine(start_of_period, datetime.min.time()),
                RechargeRecord.created_at <= datetime.combine(end_date, datetime.max.time()),
            )
        )
        recharge_stmt = recharge_stmt.group_by(
            extract("year", RechargeRecord.created_at),
            extract("month", RechargeRecord.created_at),
        )
        recharge_result = (await self.db.execute(recharge_stmt)).all()

        # 查询趋势窗口内的结算单（按月聚合）
        invoice_stmt = select(
            extract("year", Invoice.period_start).label("year"),
            extract("month", Invoice.period_start).label("month"),
            func.sum(Invoice.total_amount).label("total_amount"),
        ).where(
            and_(
                Invoice.customer_id == customer_id,
                Invoice.period_start >= start_of_period,
                Invoice.period_end <= end_date,
                Invoice.status != "cancelled",
            )
        )
        invoice_stmt = invoice_stmt.group_by(
            extract("year", Invoice.period_start),
            extract("month", Invoice.period_start),
        )
        invoice_result = (await self.db.execute(invoice_stmt)).all()

        # 构建月度查找字典
        recharge_by_month: Dict[str, Dict[str, float]] = {}
        for row in recharge_result:
            key = f"{int(row.year)}-{int(row.month):02d}"
            recharge_by_month[key] = {
                "real_amount": float(row.real_amount) if row.real_amount else 0.0,
                "bonus_amount": float(row.bonus_amount) if row.bonus_amount else 0.0,
            }

        invoice_by_month: Dict[str, float] = {}
        for row in invoice_result:
            key = f"{int(row.year)}-{int(row.month):02d}"
            invoice_by_month[key] = float(row.total_amount) if row.total_amount else 0.0

        # 计算趋势窗口开始前的历史累计充值和消耗
        historical_recharge_stmt = select(
            func.sum(RechargeRecord.real_amount).label("real_amount"),
            func.sum(RechargeRecord.bonus_amount).label("bonus_amount"),
        ).where(
            and_(
                RechargeRecord.customer_id == customer_id,
                RechargeRecord.created_at < datetime.combine(start_of_period, datetime.min.time()),
            )
        )
        await self.db.execute(historical_recharge_stmt)

        historical_invoice_stmt = select(func.sum(Invoice.total_amount)).where(
            and_(
                Invoice.customer_id == customer_id,
                Invoice.period_start < start_of_period,
                Invoice.status != "cancelled",
            )
        )
        await self.db.execute(historical_invoice_stmt)

        # 计算起始余额 = 当前余额 - 窗口内净变化
        window_recharge_real = sum(v["real_amount"] for v in recharge_by_month.values())
        window_recharge_bonus = sum(v["bonus_amount"] for v in recharge_by_month.values())
        window_invoice = sum(invoice_by_month.values())

        start_total = (
            current_balance["total_amount"]
            - (window_recharge_real + window_recharge_bonus)
            + window_invoice
        )
        start_real = current_balance["real_amount"] - window_recharge_real + window_invoice
        start_bonus = current_balance["bonus_amount"] - window_recharge_bonus

        # 逐月计算余额
        result = []
        running_total = start_total
        running_real = start_real
        running_bonus = start_bonus

        for i in range(months):
            month_date = start_date + relativedelta(months=i)
            month_key = f"{month_date.year}-{month_date.month:02d}"

            recharge = recharge_by_month.get(month_key, {"real_amount": 0.0, "bonus_amount": 0.0})
            invoice = invoice_by_month.get(month_key, 0.0)

            running_total += recharge["real_amount"] + recharge["bonus_amount"]
            running_total -= invoice
            running_real += recharge["real_amount"]
            running_real -= invoice
            running_bonus += recharge["bonus_amount"]

            result.append(
                {
                    "month": month_key,
                    "total_amount": round(running_total, 2),
                    "real_amount": round(running_real, 2),
                    "bonus_amount": round(running_bonus, 2),
                }
            )

        return result

    async def _get_current_balance(self, customer_id: int) -> Optional[Dict[str, float]]:
        """获取客户当前余额"""
        stmt = select(
            CustomerBalance.total_amount,
            CustomerBalance.real_amount,
            CustomerBalance.bonus_amount,
        ).where(
            and_(
                CustomerBalance.customer_id == customer_id,
                CustomerBalance.deleted_at.is_(None),
            )
        )
        result = (await self.db.execute(stmt)).first()
        if result is None or result.total_amount is None:
            return None
        return {
            "total_amount": float(result.total_amount),
            "real_amount": float(result.real_amount) if result.real_amount else 0.0,
            "bonus_amount": float(result.bonus_amount) if result.bonus_amount else 0.0,
        }

    # ========== 客户健康度评分 ==========

    async def get_customer_health_score(self, customer_id: int) -> Dict[str, Any]:
        """获取单个客户的健康度评分

        健康度 = 用量达标率 × 50% + 余额充足率 × 30% + 回款及时率 × 20%

        Returns:
            {
                "score": float,           # 健康度总分 (0-100)
                "usage_rate": float,      # 用量达标率 (0-100)
                "balance_rate": float,    # 余额充足率 (0-100)
                "payment_rate": float,    # 回款及时率 (0-100)
                "health_level": str,      # healthy/normal/unhealthy
            }
        """
        from datetime import timedelta

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        # 历史基线窗口下限：第 31~120 天（= 前 90 天，排除最近 30 天）
        one_twenty_days_ago = datetime.utcnow() - timedelta(days=120)

        # 1. 获取近30天实际用量
        usage_stmt = select(
            func.coalesce(func.sum(DailyConsumption.order_count), 0).label("total_quantity")
        ).where(
            and_(
                DailyConsumption.customer_id == customer_id,
                DailyConsumption.consumption_date >= thirty_days_ago.date(),
            )
        )
        usage_result = (await self.db.execute(usage_stmt)).first()
        actual_usage = float(usage_result.total_quantity or 0)  # pyright: ignore[reportOptionalMemberAccess]

        # 2. 获取预期用量（从定价规则取期望值，如果没有则用近30天日均 * 30）
        pricing_stmt = select(PricingRule).where(
            and_(
                PricingRule.customer_id == customer_id,
                PricingRule.effective_date <= datetime.utcnow().date(),
                or_(
                    PricingRule.expiry_date.is_(None),
                    PricingRule.expiry_date >= datetime.utcnow().date(),
                ),
            )
        )
        pricing_result = (await self.db.execute(pricing_stmt)).first()
        expected_usage = 0.0
        if pricing_result and pricing_result.tiers:
            # 从 tiers 中提取预期用量（如果有配置）
            # 历史脏数据可能无法归一化：该分支只影响预测展示，降级为「无阶梯配置」而非报错
            try:
                tiers = normalize_tiers(pricing_result.tiers) or []
            except TierFormatError as e:
                logger.warning("定价规则 tiers 形态非法，已忽略预期用量：%s", e)
                tiers = []
            if len(tiers) > 0:
                # 取最后一个 tier 的 max 作为预期用量参考
                last_tier = tiers[-1]
                last_max = last_tier.get("max")
                if last_max is not None:
                    expected_usage = float(last_max)
                else:
                    # 末档无上界（max=null，规范阶梯形态）：退用其入口边界 min 作为预期用量，
                    # 语义最接近旧实现读末档 threshold 的有限值，避免落入 usage_rate=100% 的回退
                    expected_usage = float(last_tier.get("min", 0))
        if expected_usage == 0:
            # 无有效阈值参照：无阶梯配置，或单档无上界且首档 min=0（模板推荐的统一定价形态）。
            # 此时改用「客户自身历史节奏」作预期——前 90 天的日均用量 × 30。
            #
            # 注意不要用「近 30 天日均 × 30」：actual_usage 本身就是近 30 天总量，那样算恰好等于
            # actual_usage，达标率恒为 100%（旧实现即 `expected_usage = actual_usage`，用量维度
            # 对平板定价客户完全失效，占健康度 50% 权重形同虚设）。
            # 基线窗口刻意排除最近 30 天：用量上升时达标率封顶 100%，用量下滑时才会低于 100%。
            baseline_stmt = select(
                func.coalesce(func.sum(DailyConsumption.order_count), 0).label("total_quantity"),
                func.min(DailyConsumption.consumption_date).label("earliest"),
            ).where(
                and_(
                    DailyConsumption.customer_id == customer_id,
                    DailyConsumption.consumption_date >= one_twenty_days_ago.date(),
                    DailyConsumption.consumption_date < thirty_days_ago.date(),
                )
            )
            baseline_result = (await self.db.execute(baseline_stmt)).first()
            baseline_total = float(
                baseline_result.total_quantity or 0  # pyright: ignore[reportOptionalMemberAccess]
            )
            earliest = baseline_result.earliest  # pyright: ignore[reportOptionalMemberAccess]
            if baseline_total > 0 and earliest:
                # 按窗口内实际覆盖天数折算日均，避免开户不足 90 天的客户被低估预期用量
                covered_days = min(90, (thirty_days_ago.date() - earliest).days + 1)
                expected_usage = baseline_total / covered_days * 30

        # 3. 获取当前余额
        balance_result = await self._get_current_balance(customer_id)
        current_balance = balance_result["total_amount"] if balance_result else 0.0

        # 4. 获取月均消耗（过去90天，基于 DailyConsumption）
        avg_consumption_stmt = select(
            func.avg(DailyConsumption.total_cost).label("avg_amount")
        ).where(
            and_(
                DailyConsumption.customer_id == customer_id,
                DailyConsumption.consumption_date >= ninety_days_ago.date(),
            )
        )
        avg_result = (await self.db.execute(avg_consumption_stmt)).first()
        monthly_avg = float(avg_result.avg_amount or 0)  # pyright: ignore[reportOptionalMemberAccess]

        # 5. 计算各项指标
        usage_rate = await self._calculate_usage_rate(actual_usage, expected_usage)
        balance_rate = await self._calculate_balance_rate(current_balance, monthly_avg)
        payment_rate = await self._calculate_payment_rate(customer_id)

        # 6. 综合评分
        score = round(usage_rate * 0.5 + balance_rate * 0.3 + payment_rate * 0.2, 2)

        # 7. 健康等级映射
        if score >= 80:
            health_level = "healthy"
        elif score >= 60:
            health_level = "normal"
        else:
            health_level = "unhealthy"

        return {
            "score": score,
            "usage_rate": round(usage_rate, 2),
            "balance_rate": round(balance_rate, 2),
            "payment_rate": round(payment_rate, 2),
            "health_level": health_level,
        }

    async def _calculate_usage_rate(self, actual_usage: float, expected_usage: float) -> float:
        """计算用量达标率

        用量达标率 = min(实际用量 / 预期用量，1.0) × 100
        """
        if expected_usage <= 0:
            return 0.0
        return min(actual_usage / expected_usage, 1.0) * 100

    async def _calculate_balance_rate(self, current_balance: float, monthly_avg: float) -> float:
        """计算余额充足率

        余额充足率 = min(当前余额 / 月均消耗，1.0) × 100
        """
        if monthly_avg <= 0:
            return 0.0
        return min(current_balance / monthly_avg, 1.0) * 100

    async def _calculate_payment_rate(self, customer_id: int) -> float:
        """计算回款及时率

        回款及时率 = 按时付款结算单数 / 总结算单数 × 100
        按时付款定义为：结算单状态为 paid 或 completed
        """
        # 总结算单数
        total_stmt = select(func.count(Invoice.id)).where(
            and_(
                Invoice.customer_id == customer_id,
                Invoice.status != "cancelled",
                Invoice.status != "draft",
            )
        )
        total_count = (await self.db.execute(total_stmt)).scalar() or 0

        if total_count == 0:
            return 0.0

        # 按时付款结算单数
        paid_stmt = select(func.count(Invoice.id)).where(
            and_(
                Invoice.customer_id == customer_id,
                Invoice.status.in_(["paid", "completed"]),
            )
        )
        paid_count = (await self.db.execute(paid_stmt)).scalar() or 0

        return paid_count / total_count * 100

    # ========== 首页仪表盘 ==========

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取仪表盘统计数据（修复笛卡尔积：拆分为 2 个独立查询）"""
        today = datetime.utcnow()
        current_month_start = date(today.year, today.month, 1)
        current_month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])

        # 查询 1: 客户统计 + 余额（仅 JOIN 1:1 关系的 CustomerBalance，避免笛卡尔积）
        balance_stmt = (
            select(
                func.count(Customer.id).label("total_customers"),
                func.count(
                    case(
                        (Customer.is_key_customer, Customer.id),
                    )
                ).label("key_customers"),
                func.sum(CustomerBalance.total_amount).label("total_balance"),
                func.sum(CustomerBalance.real_amount).label("real_balance"),
                func.sum(CustomerBalance.bonus_amount).label("bonus_balance"),
            )
            .select_from(Customer)
            .outerjoin(
                CustomerBalance,
                and_(
                    Customer.id == CustomerBalance.customer_id,
                    CustomerBalance.deleted_at.is_(None),
                ),
            )
            .where(Customer.deleted_at.is_(None))
        )
        balance_result = (await self.db.execute(balance_stmt)).first()

        # 查询 2: 结算单统计（独立查询，不与 CustomerBalance JOIN）
        invoice_stmt = (
            select(
                func.count(
                    case(
                        (
                            and_(
                                Invoice.period_start >= current_month_start,
                                Invoice.period_end <= current_month_end,
                            ),
                            Invoice.id,
                        )
                    )
                ).label("month_invoice_count"),
                func.count(case((Invoice.status == "pending_customer", Invoice.id))).label(
                    "pending_confirmation"
                ),
                func.sum(
                    case(
                        (
                            and_(
                                Invoice.period_start >= current_month_start,
                                Invoice.period_end <= current_month_end,
                                Invoice.status != "cancelled",
                            ),
                            Invoice.total_amount,
                        )
                    )
                ).label("month_consumption"),
            )
            .select_from(Customer)
            .outerjoin(Invoice, Customer.id == Invoice.customer_id)
            .where(Customer.deleted_at.is_(None))
        )
        invoice_result = (await self.db.execute(invoice_stmt)).first()

        return {
            "total_customers": balance_result.total_customers or 0,  # pyright: ignore[reportOptionalMemberAccess]
            "key_customers": balance_result.key_customers or 0,  # pyright: ignore[reportOptionalMemberAccess]
            "total_balance": float(balance_result.total_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
            "real_balance": float(balance_result.real_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
            "bonus_balance": float(balance_result.bonus_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
            "month_invoice_count": invoice_result.month_invoice_count or 0,  # pyright: ignore[reportOptionalMemberAccess]
            "pending_confirmation": invoice_result.pending_confirmation or 0,  # pyright: ignore[reportOptionalMemberAccess]
            "month_consumption": float(invoice_result.month_consumption or 0),  # pyright: ignore[reportOptionalMemberAccess]
        }

    async def get_dashboard_chart_data(self, months: int = 6) -> Dict[str, Any]:
        """获取仪表盘图表数据"""
        from dateutil.relativedelta import relativedelta

        today = datetime.utcnow()
        end_date = today.date()
        start_date = end_date - relativedelta(months=months)

        # 消耗趋势
        consumption_trend = await self.get_consumption_trend(start_date, end_date)

        # 回款趋势
        payment_trend = []
        for i in range(months):
            month_date = end_date - relativedelta(months=i)
            from datetime import datetime as dt

            from ..utils.timezone import CST, UTC

            month_start = dt(month_date.year, month_date.month, 1, 0, 0, 0, tzinfo=CST).astimezone(
                UTC
            )
            month_end = dt(
                month_date.year,
                month_date.month,
                monthrange(month_date.year, month_date.month)[1],
                23,
                59,
                59,
                tzinfo=CST,
            ).astimezone(UTC)

            payment_data = await self.get_payment_analysis(month_start, month_end)
            payment_trend.append(
                {
                    "period": f"{month_date.year}-{month_date.month:02d}",
                    "invoiced": payment_data["total_invoiced"],
                    "paid": payment_data["total_paid"],
                    "completion_rate": payment_data["completion_rate"],
                }
            )

        return {
            "consumption_trend": consumption_trend,
            "payment_trend": list(reversed(payment_trend)),  # 按时间正序
        }

    async def get_consumption_trend_daily(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """获取仪表盘消耗趋势（基于每日消耗数据，按月聚合）

        与 get_consumption_trend（Invoice 维度）不同，本方法基于 DailyConsumption，
        反映真实消耗流水，供运营工作台「经营趋势」图表使用。
        """
        from ..models.daily_consumption import DailyConsumption

        stmt = (
            select(
                extract("year", DailyConsumption.consumption_date).label("year"),
                extract("month", DailyConsumption.consumption_date).label("month"),
                func.sum(DailyConsumption.total_cost).label("total_amount"),
            )
            .where(
                and_(
                    DailyConsumption.consumption_date >= start_date,
                    DailyConsumption.consumption_date <= end_date,
                    DailyConsumption.deleted_at.is_(None),
                )
            )
            .group_by(
                extract("year", DailyConsumption.consumption_date),
                extract("month", DailyConsumption.consumption_date),
            )
            .order_by(
                extract("year", DailyConsumption.consumption_date),
                extract("month", DailyConsumption.consumption_date),
            )
        )

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "period": f"{int(row.year)}-{int(row.month):02d}",
                "total_amount": float(row.total_amount or 0),
            }
            for row in result
        ]

    async def get_customer_count_trend(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """获取仪表盘客户数趋势（按月统计当月有消耗的去重客户数）"""
        from ..models.daily_consumption import DailyConsumption

        stmt = (
            select(
                extract("year", DailyConsumption.consumption_date).label("year"),
                extract("month", DailyConsumption.consumption_date).label("month"),
                func.count(func.distinct(DailyConsumption.customer_id)).label("customer_count"),
            )
            .where(
                and_(
                    DailyConsumption.consumption_date >= start_date,
                    DailyConsumption.consumption_date <= end_date,
                    DailyConsumption.deleted_at.is_(None),
                )
            )
            .group_by(
                extract("year", DailyConsumption.consumption_date),
                extract("month", DailyConsumption.consumption_date),
            )
            .order_by(
                extract("year", DailyConsumption.consumption_date),
                extract("month", DailyConsumption.consumption_date),
            )
        )

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "period": f"{int(row.year)}-{int(row.month):02d}",
                "customer_count": int(row.customer_count or 0),
            }
            for row in result
        ]

    async def get_risk_customers(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取风险客户列表（余额覆盖不足 + 流失风险）

        余额风险：近 90 天有消耗记录，但余额缺失或不足 1000 元
        流失风险：曾有消耗但最近 90 天无消耗
        """
        from datetime import timedelta

        from ..models.daily_consumption import DailyConsumption

        now = datetime.utcnow()
        ninety_days_ago = now - timedelta(days=90)

        # 近 90 天有消耗的客户
        active_ids_stmt = (
            select(DailyConsumption.customer_id.label("customer_id"))
            .where(
                and_(
                    DailyConsumption.consumption_date >= ninety_days_ago,
                    DailyConsumption.deleted_at.is_(None),
                )
            )
            .distinct()
            .subquery()
        )

        # 余额信息（LEFT JOIN 保留无余额记录客户）
        # 余额风险判定下沉 SQL：余额缺失（无余额记录）优先，其次余额不足（<1000 元）
        remaining_expr = func.coalesce(CustomerBalance.real_amount, 0) + func.coalesce(
            CustomerBalance.bonus_amount, 0
        )
        balance_missing = and_(
            CustomerBalance.real_amount.is_(None),
            CustomerBalance.bonus_amount.is_(None),
        )
        risk_score = case((balance_missing, 50), else_=30)
        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.manager_id,
                User.real_name.label("manager_name"),
                CustomerBalance.real_amount,
                CustomerBalance.bonus_amount,
                risk_score.label("risk_score"),
            )
            .join(active_ids_stmt, Customer.id == active_ids_stmt.c.customer_id)
            .outerjoin(User, Customer.manager_id == User.id)
            .outerjoin(
                CustomerBalance,
                and_(
                    CustomerBalance.customer_id == Customer.id,
                    CustomerBalance.deleted_at.is_(None),
                ),
            )
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    or_(balance_missing, remaining_expr < 1000),
                )
            )
            .order_by(risk_score.desc(), Customer.id)
            .limit(limit)
        )
        result = (await self.db.execute(stmt)).all()

        customers: List[Dict[str, Any]] = []
        for row in result:
            has_balance = row.real_amount is not None or row.bonus_amount is not None
            remaining = float(row.real_amount or 0) + float(row.bonus_amount or 0)
            if not has_balance:
                risk_type, score = "余额缺失", 50
            elif remaining < 1000:
                risk_type, score = "余额不足", 30
            else:
                continue  # 余额充足（防御：SQL 已过滤）
            customers.append(
                {
                    "customer_id": row.id,
                    "customer_name": row.name,
                    "score": score,
                    "risk_type": risk_type,
                    "manager_name": row.manager_name or "未分配",
                }
            )

        # 补充流失风险客户（曾有消耗但近 90 天无消耗）
        if len(customers) < limit:
            inactive = await self.get_inactive_customers(days=90, limit=limit - len(customers))
            existing_ids = {c["customer_id"] for c in customers}
            for ic in inactive:
                if ic["customer_id"] in existing_ids:
                    continue
                existing_ids.add(ic["customer_id"])
                customers.append(
                    {
                        "customer_id": ic["customer_id"],
                        "customer_name": ic["customer_name"],
                        "score": 40,
                        "risk_type": "流失风险",
                        "manager_name": ic.get("manager_name", "未分配"),
                    }
                )
                if len(customers) >= limit:
                    break

        return customers
