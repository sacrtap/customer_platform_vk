"""客户分析服务"""

from datetime import datetime, date
from calendar import monthrange
from decimal import Decimal
from sqlalchemy import select, func, and_, or_, extract
from sqlalchemy.orm import Session, joinedload
from ..models.customers import Customer, CustomerProfile
from ..models.tags import Tag, CustomerTag, ProfileTag
from ..models.billing import (
    DailyUsage,
    ConsumptionRecord,
    Invoice,
    InvoiceItem,
    CustomerBalance,
    PricingRule,
)
from ..models.users import User
from typing import Dict, List, Any, Optional
from collections import defaultdict


class AnalyticsService:
    """客户分析服务"""

    def __init__(self, db: Session):
        self.db = db

    # ========== 消耗分析 ==========

    def get_consumption_trend(
        self, start_date: date, end_date: date, customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取消耗趋势（月度）"""
        # 按月份聚合消耗金额
        stmt = select(
            extract("year", Invoice.period_start).label("year"),
            extract("month", Invoice.period_start).label("month"),
            func.sum(Invoice.total_amount).label("total_amount"),
        ).where(
            and_(
                Invoice.period_start >= start_date,
                Invoice.period_end <= end_date,
                Invoice.status != "cancelled",
            )
        )

        if customer_id:
            stmt = stmt.where(Invoice.customer_id == customer_id)

        stmt = stmt.group_by(
            extract("year", Invoice.period_start),
            extract("month", Invoice.period_start),
        ).order_by(
            extract("year", Invoice.period_start),
            extract("month", Invoice.period_start),
        )

        result = self.db.execute(stmt).all()
        return [
            {
                "year": int(row.year),
                "month": int(row.month),
                "period": f"{int(row.year)}-{int(row.month):02d}",
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            }
            for row in result
        ]

    def get_top_customers(
        self, start_date: date, end_date: date, limit: int = 10
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

        result = self.db.execute(stmt).all()
        return [
            {
                "customer_id": row.id,
                "company_id": row.company_id,
                "customer_name": row.name,
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            }
            for row in result
        ]

    def get_device_type_distribution(
        self, start_date: date, end_date: date, customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取设备类型分布"""
        stmt = (
            select(
                InvoiceItem.device_type,
                func.sum(InvoiceItem.quantity).label("total_quantity"),
                func.sum(InvoiceItem.quantity * InvoiceItem.unit_price).label(
                    "total_amount"
                ),
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

        result = self.db.execute(stmt).all()
        return [
            {
                "device_type": row.device_type,
                "total_quantity": float(row.total_quantity)
                if row.total_quantity
                else 0.0,
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            }
            for row in result
        ]

    def get_daily_usage_trend(
        self, start_date: date, end_date: date, customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取每日用量趋势"""
        stmt = select(
            DailyUsage.usage_date,
            DailyUsage.device_type,
            func.sum(DailyUsage.quantity).label("total_quantity"),
        ).where(
            and_(
                DailyUsage.usage_date >= start_date,
                DailyUsage.usage_date <= end_date,
            )
        )

        if customer_id:
            stmt = stmt.where(DailyUsage.customer_id == customer_id)

        stmt = stmt.group_by(DailyUsage.usage_date, DailyUsage.device_type).order_by(
            DailyUsage.usage_date
        )

        result = self.db.execute(stmt).all()
        return [
            {
                "usage_date": row.usage_date.isoformat(),
                "device_type": row.device_type,
                "total_quantity": float(row.total_quantity)
                if row.total_quantity
                else 0.0,
            }
            for row in result
        ]

    # ========== 回款分析 ==========

    def get_payment_analysis(
        self, start_date: date, end_date: date, customer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取回款分析数据"""
        # 总结算金额
        invoice_stmt = select(
            func.sum(Invoice.total_amount).label("total_invoiced"),
            func.sum(Invoice.discount_amount).label("total_discount"),
            func.sum(Invoice.total_amount - Invoice.discount_amount).label(
                "total_final"
            ),
        ).where(
            and_(
                Invoice.period_start >= start_date,
                Invoice.period_end <= end_date,
                Invoice.status != "cancelled",
            )
        )

        if customer_id:
            invoice_stmt = invoice_stmt.where(Invoice.customer_id == customer_id)

        invoice_result = self.db.execute(invoice_stmt).first()

        # 已回款金额
        payment_stmt = select(
            func.sum(RechargeRecord.real_amount).label("total_paid")
        ).where(
            and_(
                RechargeRecord.created_at
                >= datetime.combine(start_date, datetime.min.time()),
                RechargeRecord.created_at
                <= datetime.combine(end_date, datetime.max.time()),
            )
        )

        if customer_id:
            payment_stmt = payment_stmt.where(RechargeRecord.customer_id == customer_id)

        payment_result = self.db.execute(payment_stmt).first()

        total_invoiced = float(invoice_result.total_invoiced or 0)
        total_final = float(invoice_result.total_final or 0)
        total_paid = float(payment_result.total_paid or 0)

        return {
            "total_invoiced": total_invoiced,
            "total_discount": float(invoice_result.total_discount or 0),
            "total_final": total_final,
            "total_paid": total_paid,
            "completion_rate": round(total_paid / total_final * 100, 2)
            if total_final > 0
            else 0,
            "difference": total_final - total_paid,
        }

    def get_invoice_status_stats(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """获取结算单状态统计"""
        stmt = (
            select(
                Invoice.status,
                func.count(Invoice.id).label("count"),
                func.sum(Invoice.total_amount - Invoice.discount_amount).label(
                    "total_amount"
                ),
            )
            .where(
                and_(
                    Invoice.period_start >= start_date,
                    Invoice.period_end <= end_date,
                )
            )
            .group_by(Invoice.status)
        )

        result = self.db.execute(stmt).all()
        return [
            {
                "status": row.status,
                "count": row.count,
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            }
            for row in result
        ]

    # ========== 健康度分析 ==========

    def get_customer_health_stats(self) -> Dict[str, Any]:
        """获取客户健康度统计"""
        # 活跃客户数（有消耗记录）
        active_stmt = select(func.count(func.distinct(ConsumptionRecord.customer_id)))
        active_count = self.db.execute(active_stmt).scalar() or 0

        # 总客户数
        total_stmt = select(func.count(Customer.id)).where(
            Customer.deleted_at.is_(None)
        )
        total_count = self.db.execute(total_stmt).scalar() or 0

        # 余额预警客户（余额 < 1000）
        warning_stmt = select(func.count(CustomerBalance.id)).where(
            CustomerBalance.total_amount < 1000
        )
        warning_count = self.db.execute(warning_stmt).scalar() or 0

        # 流失风险客户（90 天无消耗）
        from datetime import timedelta

        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        churn_stmt = (
            select(func.count(func.distinct(Customer.id)))
            .join(ConsumptionRecord, Customer.id == ConsumptionRecord.customer_id)
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    ConsumptionRecord.created_at < ninety_days_ago,
                )
            )
        )
        # 排除最近 90 天有消耗的客户
        recent_stmt = select(func.distinct(ConsumptionRecord.customer_id)).where(
            ConsumptionRecord.created_at >= ninety_days_ago
        )
        recent_customers = set(row[0] for row in self.db.execute(recent_stmt).all())

        churn_count = 0
        for row in self.db.execute(churn_stmt).all():
            if row[0] not in recent_customers:
                churn_count += 1

        return {
            "total_customers": total_count,
            "active_customers": active_count,
            "inactive_customers": total_count - active_count,
            "warning_customers": warning_count,
            "churn_risk_customers": churn_count,
            "active_rate": round(active_count / total_count * 100, 2)
            if total_count > 0
            else 0,
        }

    def get_balance_warning_list(self, threshold: float = 1000) -> List[Dict[str, Any]]:
        """获取余额预警客户列表"""
        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.company_id,
                CustomerBalance.total_amount,
                CustomerBalance.real_amount,
                CustomerBalance.bonus_amount,
            )
            .join(CustomerBalance, Customer.id == CustomerBalance.customer_id)
            .where(
                and_(
                    CustomerBalance.total_amount < threshold,
                    Customer.deleted_at.is_(None),
                )
            )
            .order_by(CustomerBalance.total_amount.asc())
        )

        result = self.db.execute(stmt).all()
        return [
            {
                "customer_id": row.id,
                "company_id": row.company_id,
                "customer_name": row.name,
                "total_amount": float(row.total_amount) if row.total_amount else 0.0,
                "real_amount": float(row.real_amount) if row.real_amount else 0.0,
                "bonus_amount": float(row.bonus_amount) if row.bonus_amount else 0.0,
            }
            for row in result
        ]

    def get_inactive_customers(self, days: int = 90) -> List[Dict[str, Any]]:
        """获取长期未消耗客户列表"""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # 有消耗记录的客户
        has_usage_stmt = select(func.distinct(ConsumptionRecord.customer_id))
        all_customers_with_usage = set(
            row[0] for row in self.db.execute(has_usage_stmt).all()
        )

        # 最近有消耗的客户
        recent_usage_stmt = select(func.distinct(ConsumptionRecord.customer_id)).where(
            ConsumptionRecord.created_at >= cutoff_date
        )
        recent_customers = set(
            row[0] for row in self.db.execute(recent_usage_stmt).all()
        )

        # 长期未消耗的客户
        inactive_customer_ids = all_customers_with_usage - recent_customers

        if not inactive_customer_ids:
            return []

        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.company_id,
                Customer.manager_id,
                User.name.label("manager_name"),
            )
            .where(
                and_(
                    Customer.id.in_(inactive_customer_ids),
                    Customer.deleted_at.is_(None),
                )
            )
            .outerjoin(User, Customer.manager_id == User.id)
        )

        result = self.db.execute(stmt).all()
        return [
            {
                "customer_id": row.id,
                "company_id": row.company_id,
                "customer_name": row.name,
                "manager_id": row.manager_id,
                "manager_name": row.manager_name or "未分配",
            }
            for row in result
        ]

    # ========== 画像分析 ==========

    def get_industry_distribution(self) -> List[Dict[str, Any]]:
        """获取行业分布"""
        stmt = (
            select(
                CustomerProfile.industry,
                func.count(CustomerProfile.id).label("count"),
            )
            .join(Customer, CustomerProfile.customer_id == Customer.id)
            .where(Customer.deleted_at.is_(None))
            .group_by(CustomerProfile.industry)
            .order_by(func.count(CustomerProfile.id).desc())
        )

        result = self.db.execute(stmt).all()
        total = sum(row.count for row in result)

        return [
            {
                "industry": row.industry or "未分类",
                "count": row.count,
                "percentage": round(row.count / total * 100, 2) if total > 0 else 0,
            }
            for row in result
        ]

    def get_customer_level_stats(self) -> List[Dict[str, Any]]:
        """获取客户等级统计"""
        stmt = (
            select(
                Customer.customer_level,
                func.count(Customer.id).label("count"),
            )
            .where(Customer.deleted_at.is_(None))
            .group_by(Customer.customer_level)
            .order_by(func.count(Customer.id).desc())
        )

        result = self.db.execute(stmt).all()
        total = sum(row.count for row in result)

        return [
            {
                "level": row.customer_level or "未分类",
                "count": row.count,
                "percentage": round(row.count / total * 100, 2) if total > 0 else 0,
            }
            for row in result
        ]

    def get_scale_level_stats(self) -> List[Dict[str, Any]]:
        """获取客户规模等级统计"""
        stmt = (
            select(
                CustomerProfile.scale_level,
                func.count(CustomerProfile.id).label("count"),
            )
            .join(Customer, CustomerProfile.customer_id == Customer.id)
            .where(Customer.deleted_at.is_(None))
            .group_by(CustomerProfile.scale_level)
            .order_by(func.count(CustomerProfile.id).desc())
        )

        result = self.db.execute(stmt).all()
        total = sum(row.count for row in result)

        return [
            {
                "scale_level": row.scale_level or "未分类",
                "count": row.count,
                "percentage": round(row.count / total * 100, 2) if total > 0 else 0,
            }
            for row in result
        ]

    def get_consume_level_stats(self) -> List[Dict[str, Any]]:
        """获取客户消费等级统计"""
        stmt = (
            select(
                CustomerProfile.consume_level,
                func.count(CustomerProfile.id).label("count"),
            )
            .join(Customer, CustomerProfile.customer_id == Customer.id)
            .where(Customer.deleted_at.is_(None))
            .group_by(CustomerProfile.consume_level)
            .order_by(func.count(CustomerProfile.id).desc())
        )

        result = self.db.execute(stmt).all()
        total = sum(row.count for row in result)

        return [
            {
                "consume_level": row.consume_level or "未分类",
                "count": row.count,
                "percentage": round(row.count / total * 100, 2) if total > 0 else 0,
            }
            for row in result
        ]

    def get_real_estate_stats(self) -> Dict[str, Any]:
        """获取房产客户统计"""
        total_stmt = select(func.count(Customer.id)).where(
            Customer.deleted_at.is_(None)
        )
        total = self.db.execute(total_stmt).scalar() or 0

        real_estate_stmt = (
            select(func.count(Customer.id))
            .join(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            .where(
                and_(
                    Customer.deleted_at.is_(None),
                    CustomerProfile.is_real_estate == True,
                )
            )
        )
        real_estate = self.db.execute(real_estate_stmt).scalar() or 0

        return {
            "total_customers": total,
            "real_estate_customers": real_estate,
            "non_real_estate_customers": total - real_estate,
            "real_estate_percentage": round(real_estate / total * 100, 2)
            if total > 0
            else 0,
        }

    # ========== 预测回款 ==========

    def predict_monthly_payment(
        self, year: int, month: int, customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """预测月度回款"""
        from calendar import monthrange

        # 获取该月的定价规则
        mid_month = date(year, month, 15)

        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.company_id,
                PricingRule.device_type,
                PricingRule.pricing_type,
                PricingRule.unit_price,
                PricingRule.tiers,
                PricingRule.package_type,
            )
            .join(PricingRule, Customer.id == PricingRule.customer_id)
            .where(
                and_(
                    PricingRule.effective_date <= mid_month,
                    or_(
                        PricingRule.expiry_date.is_(None),
                        PricingRule.expiry_date >= mid_month,
                    ),
                    Customer.deleted_at.is_(None),
                )
            )
        )

        if customer_id:
            stmt = stmt.where(Customer.id == customer_id)

        result = self.db.execute(stmt).all()

        predictions = []
        for row in result:
            # 获取该客户该月的实际用量
            usage_stmt = (
                select(
                    DailyUsage.device_type,
                    func.sum(DailyUsage.quantity).label("total_quantity"),
                )
                .where(
                    and_(
                        DailyUsage.customer_id == row.id,
                        DailyUsage.usage_date >= date(year, month, 1),
                        DailyUsage.usage_date
                        <= date(year, month, monthrange(year, month)[1]),
                    )
                )
                .group_by(DailyUsage.device_type)
            )

            usage_result = self.db.execute(usage_stmt).all()

            for usage_row in usage_result:
                predicted_amount = self._calculate_predicted_amount(
                    pricing_type=row.pricing_type,
                    unit_price=float(row.unit_price)
                    if row.unit_price
                    else Decimal("0"),
                    tiers=row.tiers,
                    package_type=row.package_type,
                    quantity=float(usage_row.total_quantity)
                    if usage_row.total_quantity
                    else 0,
                )

                predictions.append(
                    {
                        "customer_id": row.id,
                        "company_id": row.company_id,
                        "customer_name": row.name,
                        "device_type": usage_row.device_type,
                        "quantity": float(usage_row.total_quantity)
                        if usage_row.total_quantity
                        else 0,
                        "pricing_type": row.pricing_type,
                        "predicted_amount": predicted_amount,
                    }
                )

        return predictions

    def _calculate_predicted_amount(
        self,
        pricing_type: str,
        unit_price: float,
        tiers: Optional[Dict],
        package_type: Optional[str],
        quantity: float,
    ) -> float:
        """计算预测金额"""
        if pricing_type == "fixed":
            return round(quantity * unit_price, 2)

        elif pricing_type == "tiered" and tiers:
            # 阶梯定价计算
            remaining = quantity
            total = 0
            sorted_tiers = sorted(tiers, key=lambda x: x["threshold"])

            for tier in sorted_tiers:
                threshold = tier["threshold"]
                tier_price = tier["price"]
                if remaining <= threshold:
                    total += remaining * tier_price
                    remaining = 0
                    break
                else:
                    total += threshold * tier_price
                    remaining -= threshold

            if remaining > 0:
                total += remaining * unit_price

            return round(total, 2)

        elif pricing_type == "package" and package_type:
            # 包年套餐计算（简化处理）
            package_prices = {"A": 10000, "B": 20000, "C": 30000, "D": 50000}
            return package_prices.get(package_type, 0)

        return round(quantity * unit_price, 2)

    # ========== 首页仪表盘 ==========

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取仪表盘统计数据"""
        # 客户总数
        total_customers = (
            self.db.execute(
                select(func.count(Customer.id)).where(Customer.deleted_at.is_(None))
            ).scalar()
            or 0
        )

        # 重点客户数
        key_customers = (
            self.db.execute(
                select(func.count(Customer.id)).where(
                    and_(
                        Customer.deleted_at.is_(None),
                        Customer.is_key_customer == True,
                    )
                )
            ).scalar()
            or 0
        )

        # 总余额
        balance_result = self.db.execute(
            select(
                func.sum(CustomerBalance.total_amount),
                func.sum(CustomerBalance.real_amount),
                func.sum(CustomerBalance.bonus_amount),
            )
        ).first()

        # 本月结算单数
        today = datetime.utcnow()
        current_month_start = date(today.year, today.month, 1)
        current_month_end = date(
            today.year, today.month, monthrange(today.year, today.month)[1]
        )

        invoice_count = (
            self.db.execute(
                select(func.count(Invoice.id)).where(
                    and_(
                        Invoice.period_start >= current_month_start,
                        Invoice.period_end <= current_month_end,
                    )
                )
            ).scalar()
            or 0
        )

        # 待确认结算单数
        pending_count = (
            self.db.execute(
                select(func.count(Invoice.id)).where(
                    Invoice.status == "pending_customer"
                )
            ).scalar()
            or 0
        )

        # 本月消耗总额
        month_consumption = (
            self.db.execute(
                select(func.sum(Invoice.total_amount)).where(
                    and_(
                        Invoice.period_start >= current_month_start,
                        Invoice.period_end <= current_month_end,
                        Invoice.status != "cancelled",
                    )
                )
            ).scalar()
            or 0
        )

        return {
            "total_customers": total_customers,
            "key_customers": key_customers,
            "total_balance": float(balance_result[0] or 0),
            "real_balance": float(balance_result[1] or 0),
            "bonus_balance": float(balance_result[2] or 0),
            "month_invoice_count": invoice_count,
            "pending_confirmation": pending_count,
            "month_consumption": float(month_consumption),
        }

    def get_dashboard_chart_data(self, months: int = 6) -> Dict[str, Any]:
        """获取仪表盘图表数据"""
        from dateutil.relativedelta import relativedelta

        today = datetime.utcnow()
        end_date = today.date()
        start_date = end_date - relativedelta(months=months)

        # 消耗趋势
        consumption_trend = self.get_consumption_trend(start_date, end_date)

        # 回款趋势
        payment_trend = []
        for i in range(months):
            month_date = end_date - relativedelta(months=i)
            month_start = date(month_date.year, month_date.month, 1)
            month_end = date(
                month_date.year,
                month_date.month,
                monthrange(month_date.year, month_date.month)[1],
            )

            payment_data = self.get_payment_analysis(month_start, month_end)
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
