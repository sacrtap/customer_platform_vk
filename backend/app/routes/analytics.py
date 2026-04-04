"""客户分析 API 路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from datetime import datetime, date
from ..middleware.auth import auth_required
from ..services.analytics import AnalyticsService
from ..cache.base import cache_service

analytics = Blueprint("analytics", url_prefix="/api/v1/analytics")


@analytics.route("/consumption/trend", methods=["GET"])
@auth_required
async def get_consumption_trend(request: Request):
    """获取消耗趋势"""
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

    cid = customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}"
    cached = await cache_service.get("analytics_consumption_trend", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    trend = service.get_consumption_trend(
        start_date, end_date, int(customer_id) if customer_id else None
    )

    result = {"code": 0, "message": "success", "data": trend}
    await cache_service.set("analytics_consumption_trend", result, cache_key)
    return json(result)


@analytics.route("/consumption/top", methods=["GET"])
@auth_required
async def get_top_customers(request: Request):
    """获取 Top 消耗客户"""
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

    cache_key = f"{start_date}:{end_date}:{limit}"
    cached = await cache_service.get("analytics_top_customers", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    top_customers = service.get_top_customers(start_date, end_date, limit)

    result = {"code": 0, "message": "success", "data": top_customers}
    await cache_service.set("analytics_top_customers", result, cache_key)
    return json(result)


@analytics.route("/consumption/device-distribution", methods=["GET"])
@auth_required
async def get_device_distribution(request: Request):
    """获取设备类型分布"""
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

    cid = customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}"
    cached = await cache_service.get("analytics_device_distribution", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    distribution = service.get_device_type_distribution(
        start_date, end_date, int(customer_id) if customer_id else None
    )

    result = {"code": 0, "message": "success", "data": distribution}
    await cache_service.set("analytics_device_distribution", result, cache_key)
    return json(result)


@analytics.route("/payment/analysis", methods=["GET"])
@auth_required
async def get_payment_analysis(request: Request):
    """获取回款分析"""
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

    cid = customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}"
    cached = await cache_service.get("analytics_payment_analysis", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    analysis = service.get_payment_analysis(
        start_date, end_date, int(customer_id) if customer_id else None
    )

    result = {"code": 0, "message": "success", "data": analysis}
    await cache_service.set("analytics_payment_analysis", result, cache_key)
    return json(result)


@analytics.route("/payment/invoice-status", methods=["GET"])
@auth_required
async def get_invoice_status(request: Request):
    """获取结算单状态统计"""
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    cache_key = f"{start_date}:{end_date}"
    cached = await cache_service.get("analytics_invoice_status", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_invoice_status_stats(start_date, end_date)

    result = {"code": 0, "message": "success", "data": stats}
    await cache_service.set("analytics_invoice_status", result, cache_key)
    return json(result)


@analytics.route("/health/stats", methods=["GET"])
@auth_required
async def get_health_stats(request: Request):
    """获取健康度统计"""
    cached = await cache_service.get("analytics_health_stats")
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_customer_health_stats()

    result = {"code": 0, "message": "success", "data": stats}
    await cache_service.set("analytics_health_stats", result)
    return json(result)


@analytics.route("/health/warning-list", methods=["GET"])
@auth_required
async def get_warning_list(request: Request):
    """获取余额预警客户列表"""
    threshold = float(request.args.get("threshold", 1000))

    cache_key = f"{threshold}"
    cached = await cache_service.get("analytics_health_warning", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    warning_list = service.get_balance_warning_list(threshold)

    result = {"code": 0, "message": "success", "data": warning_list}
    await cache_service.set("analytics_health_warning", result, cache_key)
    return json(result)


@analytics.route("/health/inactive-list", methods=["GET"])
@auth_required
async def get_inactive_list(request: Request):
    """获取长期未消耗客户列表"""
    days = int(request.args.get("days", 90))

    cache_key = f"{days}"
    cached = await cache_service.get("analytics_health_inactive", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    inactive_list = service.get_inactive_customers(days)

    result = {"code": 0, "message": "success", "data": inactive_list}
    await cache_service.set("analytics_health_inactive", result, cache_key)
    return json(result)


@analytics.route("/profile/industry", methods=["GET"])
@auth_required
async def get_industry_distribution(request: Request):
    """获取行业分布"""
    cached = await cache_service.get("analytics_profile", "industry")
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    distribution = service.get_industry_distribution()

    result = {"code": 0, "message": "success", "data": distribution}
    await cache_service.set("analytics_profile", result, "industry")
    return json(result)


@analytics.route("/profile/level", methods=["GET"])
@auth_required
async def get_level_stats(request: Request):
    """获取客户等级统计"""
    cached = await cache_service.get("analytics_profile", "level")
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_customer_level_stats()

    result = {"code": 0, "message": "success", "data": stats}
    await cache_service.set("analytics_profile", result, "level")
    return json(result)


@analytics.route("/profile/scale", methods=["GET"])
@auth_required
async def get_scale_stats(request: Request):
    """获取客户规模等级统计"""
    cached = await cache_service.get("analytics_profile", "scale")
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_scale_level_stats()

    result = {"code": 0, "message": "success", "data": stats}
    await cache_service.set("analytics_profile", result, "scale")
    return json(result)


@analytics.route("/profile/consume-level", methods=["GET"])
@auth_required
async def get_consume_level_stats(request: Request):
    """获取客户消费等级统计"""
    cached = await cache_service.get("analytics_profile", "consume_level")
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_consume_level_stats()

    result = {"code": 0, "message": "success", "data": stats}
    await cache_service.set("analytics_profile", result, "consume_level")
    return json(result)


@analytics.route("/profile/real-estate", methods=["GET"])
@auth_required
async def get_real_estate_stats(request: Request):
    """获取房产客户统计"""
    cached = await cache_service.get("analytics_profile", "real_estate")
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_real_estate_stats()

    result = {"code": 0, "message": "success", "data": stats}
    await cache_service.set("analytics_profile", result, "real_estate")
    return json(result)


@analytics.route("/prediction/monthly", methods=["GET"])
@auth_required
async def predict_monthly_payment(request: Request):
    """预测月度回款"""
    year = int(request.args.get("year", datetime.utcnow().year))
    month = int(request.args.get("month", datetime.utcnow().month))
    customer_id = request.args.get("customer_id")

    cid = customer_id or "all"
    cache_key = f"{year}:{month}:{cid}"
    cached = await cache_service.get("analytics_prediction", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    predictions = service.predict_monthly_payment(
        year, month, int(customer_id) if customer_id else None
    )

    result = {"code": 0, "message": "success", "data": predictions}
    await cache_service.set("analytics_prediction", result, cache_key)
    return json(result)


@analytics.route("/dashboard/stats", methods=["GET"])
@auth_required
async def get_dashboard_stats(request: Request):
    """获取仪表盘统计数据"""
    cached = await cache_service.get("analytics_dashboard_stats")
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = service.get_dashboard_stats()

    result = {"code": 0, "message": "success", "data": stats}
    await cache_service.set("analytics_dashboard_stats", result)
    return json(result)


@analytics.route("/dashboard/chart-data", methods=["GET"])
@auth_required
async def get_dashboard_chart_data(request: Request):
    """获取仪表盘图表数据"""
    months = int(request.args.get("months", 6))

    cache_key = f"{months}"
    cached = await cache_service.get("analytics_dashboard_chart", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    chart_data = service.get_dashboard_chart_data(months)

    result = {"code": 0, "message": "success", "data": chart_data}
    await cache_service.set("analytics_dashboard_chart", result, cache_key)
    return json(result)
