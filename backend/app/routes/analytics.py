"""客户分析 API 路由"""

import logging
import time
from datetime import datetime

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json

from ..cache.base import cache_service
from ..middleware.auth import auth_required
from ..services.analytics import AnalyticsService

logger = logging.getLogger(__name__)

analytics = Blueprint("analytics", url_prefix="/api/v1/analytics")


@analytics.route("/consumption/trend", methods=["GET"])
@auth_required
async def get_consumption_trend(request: Request):
    """获取消耗趋势（支持订单数量和结算费用切换）"""
    import logging

    logger = logging.getLogger(__name__)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    customer_id = request.args.get("customer_id")
    keyword = request.args.get("keyword")
    metric = request.args.get("metric", "cost")  # cost | order_count
    force_refresh_raw = request.args.get("force_refresh", "")
    force_refresh = force_refresh_raw.lower() == "true"

    logger.info(
        f"🔍 Consumption trend request: force_refresh={force_refresh_raw!r} -> {force_refresh}"
    )
    if not start_date_str or not end_date_str:
        # 默认最近 6 个月
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=6)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    cid = keyword or customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}"
    cached = (
        await cache_service.get("analytics_consumption_trend", cache_key)
        if not force_refresh
        else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    # 使用新的带 metric 参数的方法
    if hasattr(service, "get_consumption_trend_with_metric"):
        trend = await service.get_consumption_trend_with_metric(
            start_date,
            end_date,
            metric=metric,
            customer_id=int(customer_id) if customer_id else None,
            keyword=keyword,
        )
    else:
        trend = await service.get_consumption_trend(
            start_date,
            end_date,
            int(customer_id) if customer_id else None,
            keyword,
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
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    metric = request.args.get("metric", "cost")
    cache_key = f"{start_date}:{end_date}:{limit}:{metric}"
    cached = (
        await cache_service.get("analytics_top_customers", cache_key) if not force_refresh else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    top_customers = await service.get_top_customers_with_metric(
        start_date, end_date, metric=metric, limit=limit
    )

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
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    cid = customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}"
    cached = (
        await cache_service.get("analytics_device_distribution", cache_key)
        if not force_refresh
        else None
    )
    if cached is not None:
        return json(cached)

    metric = request.args.get("metric", "cost")

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    distribution = await service.get_device_type_distribution_with_metric(
        start_date, end_date, metric=metric, customer_id=int(customer_id) if customer_id else None
    )

    result = {"code": 0, "message": "success", "data": distribution}
    await cache_service.set("analytics_device_distribution", result, cache_key)
    return json(result)


@analytics.route("/consumption/sync", methods=["POST"])
@auth_required
async def manual_sync_consumption(request: Request):
    """手动触发消耗数据同步"""
    from datetime import date, timedelta

    from ..services.cost_calc import CostCalcService
    from ..services.order_sync import OrderSyncService

    db_session = request.ctx.db_session

    # 并发控制：使用 Redis 分布式锁
    lock_key = "sync_consumption_lock"
    lock_ttl = 300  # 5分钟超时
    redis_client = None

    # 尝试获取锁
    try:
        redis_client = await cache_service._get_redis()
        acquired = await redis_client.set(lock_key, "1", nx=True, ex=lock_ttl)
    except Exception as e:
        logger.error("Redis 锁获取失败: %s", e)
        return json(
            {"code": 503, "message": f"同步服务暂不可用（锁服务异常）：{str(e)}"},
            status=503,
        )

    if not acquired:
        return json(
            {
                "code": 409,
                "message": "同步任务正在执行中，请稍后再试",
            }
        )

    try:
        # 同步订单数据（昨日）
        sync_date = date.today() - timedelta(days=1)
        logger.info("开始数据同步，日期: %s", sync_date)
        external_engine = getattr(request.app.ctx, "external_mysql_engine", None)
        order_service = OrderSyncService(db_session, external_engine=external_engine)
        order_result = await order_service.sync_orders(sync_date=sync_date)
        logger.info(
            "订单同步完成: success=%d, failed=%d, message=%s",
            order_result.success,
            order_result.failed,
            order_result.message,
        )

        # 计算费用（昨日）
        cost_service = CostCalcService(db_session)
        cost_result = await cost_service.calculate_daily_cost(consumption_date=sync_date)
        logger.info(
            "费用计算完成: total=%d, calculated=%d, no_rule=%d",
            cost_result["total_customers"],
            cost_result["calculated"],
            cost_result["no_rule"],
        )

        # 清除消费分析的缓存，确保前端能获取最新数据
        await cache_service.invalidate_pattern("cache:analytics_*")
        logger.info("已清除所有消费分析缓存")

        return json(
            {
                "code": 0,
                "message": "同步成功",
                "data": {
                    "order_sync": {
                        "success": order_result.success,
                        "failed": order_result.failed,
                        "skipped": order_result.skipped,
                        "message": order_result.message,
                    },
                    "cost_calc": {
                        "total_customers": cost_result["total_customers"],
                        "calculated": cost_result["calculated"],
                        "no_rule": cost_result["no_rule"],
                    },
                },
            }
        )
    except Exception as e:
        return json({"code": 500, "message": f"同步失败：{str(e)}"}, status=500)
    finally:
        # 释放锁
        if redis_client:
            try:
                await redis_client.delete(lock_key)
            except Exception:
                logger.warning("Redis 锁释放失败，将等待自动过期")


@analytics.route("/payment/analysis", methods=["GET"])
@auth_required
async def get_payment_analysis(request: Request):
    """获取回款分析"""
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    customer_id = request.args.get("customer_id")
    keyword = request.args.get("keyword")

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = datetime.utcnow().date()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

    cid = keyword or customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}"
    cached = await cache_service.get("analytics_payment_analysis", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    analysis = await service.get_payment_analysis(
        start_date,
        end_date,
        int(customer_id) if customer_id else None,
        keyword,
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

    stats = await service.get_invoice_status_stats(start_date, end_date)

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

    stats = await service.get_customer_health_stats()

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

    warning_list = await service.get_balance_warning_list(threshold)

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

    inactive_list = await service.get_inactive_customers(days)

    result = {"code": 0, "message": "success", "data": inactive_list}
    await cache_service.set("analytics_health_inactive", result, cache_key)
    return json(result)


@analytics.route("/health/customers/<customer_id:int>/score", methods=["GET"])
@auth_required
async def get_customer_health_score(request: Request, customer_id: int):
    """获取客户健康度评分"""
    from sqlalchemy import select as sa_select

    from ..models.customers import Customer

    db_session = request.ctx.db_session

    # 验证客户是否存在
    customer_check = await db_session.execute(
        sa_select(Customer.id).where(
            Customer.id == customer_id,
            Customer.deleted_at.is_(None),
        )
    )
    if customer_check.scalar() is None:
        return json(
            {"code": 404, "message": "Customer not found", "data": None},
            status=404,
        )

    service = AnalyticsService(db_session)
    score = await service.get_customer_health_score(customer_id)

    result = {"code": 0, "message": "success", "data": score}
    return json(result)


@analytics.route("/profile/industry", methods=["GET"])
@auth_required
async def get_industry_distribution(request: Request):
    """获取行业分布"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    hour_bucket = int(time.time() // 3600)
    cached_key = f"industry:{hour_bucket}"

    cached = await cache_service.get("analytics_profile", cached_key) if not force_refresh else None
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    distribution = await service.get_industry_distribution()

    result = {"code": 0, "message": "success", "data": distribution}
    if not force_refresh:
        await cache_service.set("analytics_profile", result, cached_key, ttl=300)
    return json(result)


@analytics.route("/profile/scale", methods=["GET"])
@auth_required
async def get_scale_stats(request: Request):
    """获取客户规模等级统计"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    hour_bucket = int(time.time() // 3600)
    cached_key = f"scale:{hour_bucket}"

    cached = await cache_service.get("analytics_profile", cached_key) if not force_refresh else None
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = await service.get_scale_level_stats()

    result = {"code": 0, "message": "success", "data": stats}
    if not force_refresh:
        await cache_service.set("analytics_profile", result, cached_key, ttl=300)
    return json(result)


@analytics.route("/profile/consume-level", methods=["GET"])
@auth_required
async def get_consume_level_stats(request: Request):
    """获取客户消费等级统计"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    hour_bucket = int(time.time() // 3600)
    cached_key = f"consume_level:{hour_bucket}"

    cached = await cache_service.get("analytics_profile", cached_key) if not force_refresh else None
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = await service.get_consume_level_stats()

    result = {"code": 0, "message": "success", "data": stats}
    if not force_refresh:
        await cache_service.set("analytics_profile", result, cached_key, ttl=300)
    return json(result)


@analytics.route("/profile/real-estate", methods=["GET"])
@auth_required
async def get_real_estate_stats(request: Request):
    """获取房产客户统计"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    hour_bucket = int(time.time() // 3600)
    cached_key = f"real_estate:{hour_bucket}"

    cached = await cache_service.get("analytics_profile", cached_key) if not force_refresh else None
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = await service.get_real_estate_stats()

    result = {"code": 0, "message": "success", "data": stats}
    if not force_refresh:
        await cache_service.set("analytics_profile", result, cached_key, ttl=300)
    return json(result)


@analytics.route("/profile/real-estate-industry", methods=["GET"])
@auth_required
async def get_real_estate_industry_stats(request: Request):
    """获取房产客户行业子分类统计"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    hour_bucket = int(time.time() // 3600)
    cached_key = f"real_estate_industry:{hour_bucket}"

    cached = await cache_service.get("analytics_profile", cached_key) if not force_refresh else None
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = await service.get_real_estate_industry_stats()

    result = {"code": 0, "message": "success", "data": stats}
    if not force_refresh:
        await cache_service.set("analytics_profile", result, cached_key, ttl=300)
    return json(result)


@analytics.route("/prediction/monthly", methods=["GET"])
@auth_required
async def predict_monthly_payment(request: Request):
    """预测月度回款"""
    year = int(request.args.get("year", datetime.utcnow().year))
    month = int(request.args.get("month", datetime.utcnow().month))
    customer_id = request.args.get("customer_id")
    keyword = request.args.get("keyword")

    cid = keyword or customer_id or "all"
    cache_key = f"{year}:{month}:{cid}"
    cached = await cache_service.get("analytics_prediction", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    predictions = await service.predict_monthly_payment(
        year, month, int(customer_id) if customer_id else None, keyword
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

    stats = await service.get_dashboard_stats()

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

    chart_data = await service.get_dashboard_chart_data(months)

    result = {"code": 0, "message": "success", "data": chart_data}
    await cache_service.set("analytics_dashboard_chart", result, cache_key)
    return json(result)


@analytics.route("/billing/trend/<customer_id:int>", methods=["GET"])
@auth_required
async def get_balance_trend(request: Request, customer_id: int):
    """获取客户余额趋势"""
    months = int(request.args.get("months", 6))
    if months > 12:
        months = 12

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    trend = await service.get_balance_trend(customer_id=customer_id, months=months)

    return json({"code": 0, "message": "success", "data": trend})
