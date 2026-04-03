"""客户分析 API 路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from datetime import datetime, date
from ..middleware.auth import auth_required
from ..services.analytics import AnalyticsService

analytics = Blueprint("analytics", url_prefix="/api/v1/analytics")


@analytics.route("/consumption/trend", methods=["GET"])
@auth_required
async def get_consumption_trend(request: Request):
    """获取消耗趋势"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    customer_id = request.args.get("customer_id")

    if not start_date_str or not end_date_str:
        # 默认最近 6 个月
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=6)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    trend = service.get_consumption_trend(
        start_date, end_date, int(customer_id) if customer_id else None
    )

    return json({"code": 0, "message": "success", "data": trend})


@analytics.route("/consumption/top", methods=["GET"])
@auth_required
async def get_top_customers(request: Request):
    """获取 Top 消耗客户"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    limit = int(request.args.get("limit", 10))

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    top_customers = service.get_top_customers(start_date, end_date, limit)

    return json({"code": 0, "message": "success", "data": top_customers})


@analytics.route("/consumption/device-distribution", methods=["GET"])
@auth_required
async def get_device_distribution(request: Request):
    """获取设备类型分布"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    customer_id = request.args.get("customer_id")

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    distribution = service.get_device_type_distribution(
        start_date, end_date, int(customer_id) if customer_id else None
    )

    return json({"code": 0, "message": "success", "data": distribution})


@analytics.route("/payment/analysis", methods=["GET"])
@auth_required
async def get_payment_analysis(request: Request):
    """获取回款分析"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    customer_id = request.args.get("customer_id")

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    analysis = service.get_payment_analysis(
        start_date, end_date, int(customer_id) if customer_id else None
    )

    return json({"code": 0, "message": "success", "data": analysis})


@analytics.route("/payment/invoice-status", methods=["GET"])
@auth_required
async def get_invoice_status(request: Request):
    """获取结算单状态统计"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    stats = service.get_invoice_status_stats(start_date, end_date)

    return json({"code": 0, "message": "success", "data": stats})


@analytics.route("/health/stats", methods=["GET"])
@auth_required
async def get_health_stats(request: Request):
    """获取健康度统计"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_customer_health_stats()

    return json({"code": 0, "message": "success", "data": stats})


@analytics.route("/health/warning-list", methods=["GET"])
@auth_required
async def get_warning_list(request: Request):
    """获取余额预警客户列表"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    threshold = float(request.args.get("threshold", 1000))

    warning_list = service.get_balance_warning_list(threshold)

    return json({"code": 0, "message": "success", "data": warning_list})


@analytics.route("/health/inactive-list", methods=["GET"])
@auth_required
async def get_inactive_list(request: Request):
    """获取长期未消耗客户列表"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    days = int(request.args.get("days", 90))

    inactive_list = service.get_inactive_customers(days)

    return json({"code": 0, "message": "success", "data": inactive_list})


@analytics.route("/profile/industry", methods=["GET"])
@auth_required
async def get_industry_distribution(request: Request):
    """获取行业分布"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    distribution = service.get_industry_distribution()

    return json({"code": 0, "message": "success", "data": distribution})


@analytics.route("/profile/level", methods=["GET"])
@auth_required
async def get_level_stats(request: Request):
    """获取客户等级统计"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_customer_level_stats()

    return json({"code": 0, "message": "success", "data": stats})


@analytics.route("/profile/scale", methods=["GET"])
@auth_required
async def get_scale_stats(request: Request):
    """获取客户规模等级统计"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_scale_level_stats()

    return json({"code": 0, "message": "success", "data": stats})


@analytics.route("/profile/consume-level", methods=["GET"])
@auth_required
async def get_consume_level_stats(request: Request):
    """获取客户消费等级统计"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_consume_level_stats()

    return json({"code": 0, "message": "success", "data": stats})


@analytics.route("/profile/real-estate", methods=["GET"])
@auth_required
async def get_real_estate_stats(request: Request):
    """获取房产客户统计"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_real_estate_stats()

    return json({"code": 0, "message": "success", "data": stats})


@analytics.route("/prediction/monthly", methods=["GET"])
@auth_required
async def predict_monthly_payment(request: Request):
    """预测月度回款"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    year = int(request.args.get("year", datetime.utcnow().year))
    month = int(request.args.get("month", datetime.utcnow().month))
    customer_id = request.args.get("customer_id")

    predictions = service.predict_monthly_payment(
        year, month, int(customer_id) if customer_id else None
    )

    return json({"code": 0, "message": "success", "data": predictions})


@analytics.route("/dashboard/stats", methods=["GET"])
@auth_required
async def get_dashboard_stats(request: Request):
    """获取仪表盘统计数据"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_dashboard_stats()

    return json({"code": 0, "message": "success", "data": stats})


@analytics.route("/dashboard/chart-data", methods=["GET"])
@auth_required
async def get_dashboard_chart_data(request: Request):
    """获取仪表盘图表数据"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    months = int(request.args.get("months", 6))

    chart_data = service.get_dashboard_chart_data(months)

    return json({"code": 0, "message": "success", "data": chart_data})
