"""客户分析服务"""

from calendar import monthrange
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, case, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import (
    CustomerBalance,
    Invoice,
    InvoiceItem,
    PricingRule,
    RechargeRecord,
)
from ..models.customers import Customer, CustomerProfile
from ..models.daily_consumption import DailyConsumption
from ..models.industry_type import IndustryType
from ..models.users import User


class AnalyticsService:
    """客户分析服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 消耗分析 ==========

    async def get_consumption_trend(
        self,
        start_date: date,
        end_date: date,
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
        start_date: date,
        end_date: date,
        metric: str = "cost",
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
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

        stmt = stmt.group_by(DailyConsumption.consumption_date).order_by(
            DailyConsumption.consumption_date
        )

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "date": row.date.isoformat(),
                "order_count": int(row.order_count) if row.order_count else 0,
                "cost": float(row.cost) if row.cost else 0.0,
            }
            for row in result
        ]

    async def get_device_type_distribution_with_metric(
        self,
        start_date: date,
        end_date: date,
        metric: str = "cost",
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        account_type: Optional[str] = None,
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

        stmt = stmt.group_by(DailyConsumption.device_type)

        result = (await self.db.execute(stmt)).all()

        # 计算总数用于百分比
        total_order_count = sum(int(row.order_count) for row in result if row.order_count)
        total_cost = sum(float(row.cost) for row in result if row.cost)

        return [
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

    async def get_top_customers(
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
        start_date: date,
        end_date: date,
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
        if scale_level:
            stmt = stmt.where(Customer.scale_level == scale_level)
        if consume_level:
            stmt = stmt.where(Customer.consume_level == consume_level)
        if manager_id:
            stmt = stmt.where(Customer.manager_id == manager_id)
        if sales_manager_id:
            stmt = stmt.where(Customer.sales_manager_id == sales_manager_id)

        # 行业筛选需要 JOIN CustomerProfile + IndustryType
        if industry:
            industry_names = [n.strip() for n in industry.split(",") if n.strip()]
            if industry_names:
                stmt = stmt.outerjoin(
                    CustomerProfile, Customer.id == CustomerProfile.customer_id
                ).outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
                stmt = stmt.where(IndustryType.name.in_(industry_names))

        stmt = stmt.group_by(Customer.id, Customer.name, Customer.company_id)

        # 根据 metric 排序
        if metric == "order_count":
            stmt = stmt.order_by(func.sum(DailyConsumption.order_count).desc())
        else:
            stmt = stmt.order_by(func.sum(DailyConsumption.total_cost).desc())

        stmt = stmt.limit(limit)

        result = (await self.db.execute(stmt)).all()
        return [
            {
                "customer_id": row.id,
                "company_id": row.company_id,
                "customer_name": row.name,
                "order_count": int(row.order_count) if row.order_count else 0,
                "cost": float(row.cost) if row.cost else 0.0,
            }
            for row in result
        ]

    async def get_device_type_distribution(
        self, start_date: date, end_date: date, customer_id: Optional[int] = None
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
        self, start_date: date, end_date: date, customer_id: Optional[int] = None
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
            stmt = stmt.where(Customer.scale_level == scale_level)
        if consume_level:
            stmt = stmt.where(Customer.consume_level == consume_level)
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
        start_date: date,
        end_date: date,
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
        invoice_stmt = self._apply_customer_filters(invoice_stmt, **filter_kwargs)

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
        paid_stmt = self._apply_customer_filters(paid_stmt, **filter_kwargs)

        invoice_result = (await self.db.execute(invoice_stmt)).first()
        paid_result = (await self.db.execute(paid_stmt)).first()

        total_invoiced = float(invoice_result.total_invoiced or 0)
        total_final = float(invoice_result.total_final or 0)
        total_paid = float(paid_result.total_paid or 0)

        return {
            "total_invoiced": total_invoiced,
            "total_discount": float(invoice_result.total_discount or 0),
            "total_final": total_final,
            "total_paid": total_paid,
            "completion_rate": round(total_paid / total_final * 100, 2) if total_final > 0 else 0,
            "difference": round(total_final - total_paid, 2),
        }

    async def get_invoice_status_stats(
        self,
        start_date: date,
        end_date: date,
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
        stmt = self._apply_customer_filters(stmt, **filter_kwargs)
        stmt = stmt.group_by(Invoice.status)

        result = (await self.db.execute(stmt)).all()
        total_count = sum(row.count for row in result)

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
        start_date: date,
        end_date: date,
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
            month_start = date(month_date.year, month_date.month, 1)
            month_end = date(
                month_date.year,
                month_date.month,
                monthrange(month_date.year, month_date.month)[1],
            )

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

    async def get_inactive_customers(self, days: int = 30) -> List[Dict[str, Any]]:
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

        now = datetime.utcnow().date()
        result = (await self.db.execute(stmt)).all()
        return [
            {
                "customer_id": row.id,
                "company_id": row.company_id,
                "customer_name": row.name,
                "manager_id": row.manager_id,
                "manager_name": row.manager_name or "未分配",
                "last_consumption_date": (
                    row.last_consumption_date.isoformat() if row.last_consumption_date else None
                ),
                "days": (now - row.last_consumption_date).days
                if row.last_consumption_date
                else days,
            }
            for row in result
        ]

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
        total = sum(row.count for row in result)

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
        total = sum(row.count for row in result)

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
            if count_map.get(level, 0) > 0  # 隐藏 count=0 的分类
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
        total = sum(row.count for row in result)

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
        total = sum(row.count for row in result)

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
        # 确定查询的时间范围
        if month is not None:
            period_start = date(year, month, 1)
            period_end = date(year, month, monthrange(year, month)[1])
        else:
            period_start = date(year, 1, 1)
            period_end = date(year, 12, 31)

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

    async def get_prediction_trend(self, year: int) -> List[Dict[str, Any]]:
        """获取全年 12 个月预测 vs 实际回款趋势

        每月返回预测金额（消耗总额）和实际回款（已支付结算单净额）。
        """
        from calendar import monthrange

        trend = []
        for m in range(1, 13):
            month_start = date(year, m, 1)
            month_end = date(year, m, monthrange(year, m)[1])

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
        actual_usage = float(usage_result.total_quantity or 0)

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
            tiers = pricing_result.tiers
            if isinstance(tiers, list) and len(tiers) > 0:
                # 取最后一个 tier 的 threshold 作为预期用量参考
                expected_usage = float(tiers[-1].get("threshold", 0))
        if expected_usage == 0:
            # 回退：用近30天的日均 * 30 作为预期
            expected_usage = actual_usage if actual_usage > 0 else 0

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
        monthly_avg = float(avg_result.avg_amount or 0)

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
            "total_customers": balance_result.total_customers or 0,
            "key_customers": balance_result.key_customers or 0,
            "total_balance": float(balance_result.total_balance or 0),
            "real_balance": float(balance_result.real_balance or 0),
            "bonus_balance": float(balance_result.bonus_balance or 0),
            "month_invoice_count": invoice_result.month_invoice_count or 0,
            "pending_confirmation": invoice_result.pending_confirmation or 0,
            "month_consumption": float(invoice_result.month_consumption or 0),
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
            month_start = date(month_date.year, month_date.month, 1)
            month_end = date(
                month_date.year,
                month_date.month,
                monthrange(month_date.year, month_date.month)[1],
            )

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
