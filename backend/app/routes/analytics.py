"""客户分析 API 路由"""

import logging
import time
from datetime import datetime

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json

from ..cache.base import cache_service
from ..middleware.auth import auth_required, require_permission
from ..services.analytics import AnalyticsService
from ..utils.timezone import (
    local_date_range_to_utc,
    local_date_to_utc_end,
    local_date_to_utc_start,
    local_today_utc_start,
)

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
    account_type = request.args.get("account_type")
    industry = request.args.get("industry")
    scale_level = request.args.get("scale_level")
    consume_level = request.args.get("consume_level")
    manager_id = request.args.get("manager_id")
    sales_manager_id = request.args.get("sales_manager_id")
    force_refresh_raw = request.args.get("force_refresh", "")
    force_refresh = force_refresh_raw.lower() == "true"

    logger.info(
        f"🔍 Consumption trend request: force_refresh={force_refresh_raw!r} -> {force_refresh}"
    )
    if not start_date_str or not end_date_str:
        # 默认最近 6 个月
        from dateutil.relativedelta import relativedelta

        end_date = local_today_utc_start()
        start_date = end_date - relativedelta(months=6)
    else:
        start_date, end_date = local_date_range_to_utc(start_date_str, end_date_str)

    cid = keyword or customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}:{account_type}:{industry}:{scale_level}:{consume_level}:{manager_id}:{sales_manager_id}"
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
            account_type=account_type,
            industry=industry,
            scale_level=scale_level,
            consume_level=consume_level,
            manager_id=int(manager_id) if manager_id else None,
            sales_manager_id=int(sales_manager_id) if sales_manager_id else None,
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

        end_date = local_today_utc_start()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date, end_date = local_date_range_to_utc(start_date_str, end_date_str)

    metric = request.args.get("metric", "cost")
    keyword = request.args.get("keyword")
    account_type = request.args.get("account_type")
    industry = request.args.get("industry")
    scale_level = request.args.get("scale_level")
    consume_level = request.args.get("consume_level")
    manager_id = request.args.get("manager_id")
    sales_manager_id = request.args.get("sales_manager_id")

    cache_key = f"{start_date}:{end_date}:{limit}:{metric}:{keyword}:{account_type}:{industry}:{scale_level}:{consume_level}:{manager_id}:{sales_manager_id}"
    cached = (
        await cache_service.get("analytics_top_customers", cache_key) if not force_refresh else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    top_customers = await service.get_top_customers_with_metric(
        start_date,
        end_date,
        metric=metric,
        limit=limit,
        keyword=keyword,
        account_type=account_type,
        industry=industry,
        scale_level=scale_level,
        consume_level=consume_level,
        manager_id=int(manager_id) if manager_id else None,
        sales_manager_id=int(sales_manager_id) if sales_manager_id else None,
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
    keyword = request.args.get("keyword")
    account_type = request.args.get("account_type")
    industry = request.args.get("industry")
    scale_level = request.args.get("scale_level")
    consume_level = request.args.get("consume_level")
    manager_id = request.args.get("manager_id")
    sales_manager_id = request.args.get("sales_manager_id")
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = local_today_utc_start()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date, end_date = local_date_range_to_utc(start_date_str, end_date_str)

    cid = customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}:{keyword}:{account_type}:{industry}:{scale_level}:{consume_level}:{manager_id}:{sales_manager_id}"
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
        start_date,
        end_date,
        metric=metric,
        customer_id=int(customer_id) if customer_id else None,
        keyword=keyword,
        account_type=account_type,
        industry=industry,
        scale_level=scale_level,
        consume_level=consume_level,
        manager_id=int(manager_id) if manager_id else None,
        sales_manager_id=int(sales_manager_id) if sales_manager_id else None,
    )

    result = {"code": 0, "message": "success", "data": distribution}
    await cache_service.set("analytics_device_distribution", result, cache_key)
    return json(result)


@analytics.route("/consumption/sync", methods=["POST"])
@auth_required
async def manual_sync_consumption(request: Request):
    """手动触发消耗数据同步（同步昨日数据）

    统一走 SyncTaskService.create_task + execute_task 链路：
    产生任务记录与执行明细，可在「同步日志」页面查看执行信息。
    """

    from datetime import date, timedelta

    from ..services.sync_task_service import SyncTaskService

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
        # 同步昨日数据（与定时任务一致的目标日期），强制覆盖保持原接口语义
        yesterday = date.today() - timedelta(days=1)
        logger.info("创建同步任务，日期: %s", yesterday)
        external_engine = getattr(request.app.ctx, "external_mysql_engine", None)
        service = SyncTaskService(
            db=db_session, redis_client=redis_client, external_engine=external_engine
        )
        task = await service.create_task(
            start_date=yesterday,
            end_date=yesterday,
            sync_mode="force_overwrite",
            operator_id=request.ctx.user["user_id"],
        )

        # 后台执行（独立 session）
        async_session_maker = request.app.ctx.async_session_maker

        async def run_task():
            async with async_session_maker() as new_session:
                bg_service = SyncTaskService(
                    db=new_session,
                    redis_client=redis_client,
                    external_engine=external_engine,
                )
                await bg_service.execute_task(task.id)  # pyright: ignore[reportArgumentType]

        request.app.add_task(run_task())

        return json(
            {
                "code": 0,
                "message": "同步任务已提交",
                "data": {
                    "task_id": str(task.id),
                    "status": task.status,
                },
            }
        )
    except Exception as e:
        if "已有相同周期的同步任务正在执行" in str(e):
            return json({"code": 409, "message": str(e)}, status=409)
        logger.error(f"创建同步任务失败: {e}")
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
    account_type = request.args.get("account_type")
    industry = request.args.get("industry")
    scale_level = request.args.get("scale_level")
    consume_level = request.args.get("consume_level")
    manager_id = request.args.get("manager_id")
    sales_manager_id = request.args.get("sales_manager_id")
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = local_today_utc_start()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date, end_date = local_date_range_to_utc(start_date_str, end_date_str)

    cid = keyword or customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}:{account_type}:{industry}:{scale_level}:{consume_level}:{manager_id}:{sales_manager_id}"
    cached = (
        await cache_service.get("analytics_payment_analysis", cache_key)
        if not force_refresh
        else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    analysis = await service.get_payment_analysis(
        start_date,
        end_date,
        customer_id=int(customer_id) if customer_id else None,
        keyword=keyword,
        account_type=account_type,
        industry=industry,
        scale_level=scale_level,
        consume_level=consume_level,
        manager_id=int(manager_id) if manager_id else None,
        sales_manager_id=int(sales_manager_id) if sales_manager_id else None,
    )

    result = {"code": 0, "message": "success", "data": analysis}
    await cache_service.set("analytics_payment_analysis", result, cache_key)
    return json(result)


@analytics.route("/payment/trend", methods=["GET"])
@auth_required
async def get_payment_trend(request: Request):
    """获取月度回款趋势"""
    months = int(request.args.get("months", 6))
    if months > 12:
        months = 12
    customer_id = request.args.get("customer_id")
    keyword = request.args.get("keyword")
    account_type = request.args.get("account_type")
    industry = request.args.get("industry")
    scale_level = request.args.get("scale_level")
    consume_level = request.args.get("consume_level")
    manager_id = request.args.get("manager_id")
    sales_manager_id = request.args.get("sales_manager_id")
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    cid = keyword or customer_id or "all"
    cache_key = f"{months}:{cid}:{account_type}:{industry}:{scale_level}:{consume_level}:{manager_id}:{sales_manager_id}"
    cached = (
        await cache_service.get("analytics_payment_trend", cache_key) if not force_refresh else None
    )
    if cached is not None:
        return json(cached)

    from dateutil.relativedelta import relativedelta

    end_date = local_today_utc_start()
    start_date = end_date - relativedelta(months=months)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    trend = await service.get_payment_trend(
        start_date,
        end_date,
        months=months,
        customer_id=int(customer_id) if customer_id else None,
        keyword=keyword,
        account_type=account_type,
        industry=industry,
        scale_level=scale_level,
        consume_level=consume_level,
        manager_id=int(manager_id) if manager_id else None,
        sales_manager_id=int(sales_manager_id) if sales_manager_id else None,
    )

    result = {"code": 0, "message": "success", "data": trend}
    await cache_service.set("analytics_payment_trend", result, cache_key)
    return json(result)


@analytics.route("/payment/invoice-status", methods=["GET"])
@auth_required
async def get_invoice_status(request: Request):
    """获取结算单状态统计"""
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    customer_id = request.args.get("customer_id")
    keyword = request.args.get("keyword")
    account_type = request.args.get("account_type")
    industry = request.args.get("industry")
    scale_level = request.args.get("scale_level")
    consume_level = request.args.get("consume_level")
    manager_id = request.args.get("manager_id")
    sales_manager_id = request.args.get("sales_manager_id")
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    if not start_date_str or not end_date_str:
        from dateutil.relativedelta import relativedelta

        end_date = local_today_utc_start()
        start_date = end_date - relativedelta(months=1)
    else:
        start_date, end_date = local_date_range_to_utc(start_date_str, end_date_str)

    cid = keyword or customer_id or "all"
    cache_key = f"{start_date}:{end_date}:{cid}:{account_type}:{industry}:{scale_level}:{consume_level}:{manager_id}:{sales_manager_id}"
    cached = (
        await cache_service.get("analytics_invoice_status", cache_key)
        if not force_refresh
        else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    stats = await service.get_invoice_status_stats(
        start_date,
        end_date,
        customer_id=int(customer_id) if customer_id else None,
        keyword=keyword,
        account_type=account_type,
        industry=industry,
        scale_level=scale_level,
        consume_level=consume_level,
        manager_id=int(manager_id) if manager_id else None,
        sales_manager_id=int(sales_manager_id) if sales_manager_id else None,
    )

    result = {"code": 0, "message": "success", "data": stats}
    await cache_service.set("analytics_invoice_status", result, cache_key)
    return json(result)


@analytics.route("/health/stats", methods=["GET"])
@auth_required
async def get_health_stats(request: Request):
    """获取健康度统计"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    cached = await cache_service.get("analytics_health_stats") if not force_refresh else None
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
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    cache_key = f"{threshold}"
    cached = (
        await cache_service.get("analytics_health_warning", cache_key)
        if not force_refresh
        else None
    )
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
    days = int(request.args.get("days", 30))
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    cache_key = f"{days}"
    cached = (
        await cache_service.get("analytics_health_inactive", cache_key)
        if not force_refresh
        else None
    )
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
    """预测月度回款

    返回预测明细列表和汇总统计（已确认回款、待确认回款、完成率）。
    month 参数可选，不传时表示全年汇总。
    """
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    year = int(request.args.get("year", datetime.utcnow().year))
    month_str = request.args.get("month")
    month = int(month_str) if month_str else None
    customer_id = request.args.get("customer_id")
    keyword = request.args.get("keyword")

    cid = keyword or customer_id or "all"
    cache_key = f"{year}:{month}:{cid}"
    cached = (
        await cache_service.get("analytics_prediction", cache_key) if not force_refresh else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    predictions = await service.predict_monthly_payment(
        year, month, int(customer_id) if customer_id else None, keyword
    )
    summary = await service.get_prediction_summary(
        year, month, int(customer_id) if customer_id else None, keyword
    )

    result = {
        "code": 0,
        "message": "success",
        "data": {"predictions": predictions, "summary": summary},
    }
    if not force_refresh:
        await cache_service.set("analytics_prediction", result, cache_key, ttl=300)
    return json(result)


@analytics.route("/prediction/trend", methods=["GET"])
@auth_required
async def get_prediction_trend(request: Request):
    """获取全年 12 个月预测 vs 实际回款趋势"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    year = int(request.args.get("year", datetime.utcnow().year))

    cache_key = f"trend:{year}"
    cached = (
        await cache_service.get("analytics_prediction", cache_key) if not force_refresh else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    trend = await service.get_prediction_trend(year)

    result = {"code": 0, "message": "success", "data": trend}
    if not force_refresh:
        await cache_service.set("analytics_prediction", result, cache_key, ttl=300)
    return json(result)


@analytics.route("/consumption/forecast", methods=["GET"])
@auth_required
async def forecast_consumption(request: Request):
    """预测消费（MVP 版）

    基于历史用量（order_count）和单价矩阵估算未来月份消费。
    返回预测明细列表和汇总统计。
    """
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    year = int(request.args.get("year", datetime.utcnow().year))
    month_str = request.args.get("month")
    month = int(month_str) if month_str else None
    customer_id = request.args.get("customer_id")
    keyword = request.args.get("keyword")
    device_type = request.args.get("device_type")
    apply_to = request.args.get("apply_to", "all")
    forecast_months = request.args.get("forecast_months")
    forecast_until = request.args.get("forecast_until")

    if forecast_months:
        forecast_months = int(forecast_months)
    if forecast_until:
        pass  # 透传给 service

    cid = keyword or customer_id or "all"
    cache_key = f"fc:{year}:{month}:{cid}:{device_type or 'all'}:{apply_to}:{forecast_months or 0}:{forecast_until or ''}"
    cached = (
        await cache_service.get("analytics_prediction", cache_key) if not force_refresh else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    forecasts = await service.forecast_consumption(
        year,
        month,
        int(customer_id) if customer_id else None,
        keyword,
        device_type,
        apply_to=apply_to,
        forecast_months=forecast_months,
        forecast_until=forecast_until,
    )
    summary = await service.get_forecast_summary(
        year,
        month,
        int(customer_id) if customer_id else None,
        keyword,
        device_type,
        apply_to=apply_to,
        forecast_months=forecast_months,
        forecast_until=forecast_until,
    )

    result = {
        "code": 0,
        "message": "success",
        "data": {"forecasts": forecasts, "summary": summary},
    }
    if not force_refresh:
        await cache_service.set("analytics_prediction", result, cache_key, ttl=1800)
    return json(result)


@analytics.route("/consumption/forecast-trend", methods=["GET"])
@auth_required
async def get_consumption_forecast_trend(request: Request):
    """获取全年 12 个月预测 vs 实际消费趋势"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    year = int(request.args.get("year", datetime.utcnow().year))
    apply_to = request.args.get("apply_to", "all")
    forecast_months = request.args.get("forecast_months")
    forecast_until = request.args.get("forecast_until")

    if forecast_months:
        forecast_months = int(forecast_months)

    cache_key = f"fctrend:{year}:{apply_to}:{forecast_months or 0}:{forecast_until or ''}"
    cached = (
        await cache_service.get("analytics_prediction", cache_key) if not force_refresh else None
    )
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    trend = await service.get_forecast_trend(
        year, apply_to=apply_to, forecast_months=forecast_months, forecast_until=forecast_until
    )

    result = {"code": 0, "message": "success", "data": trend}
    if not force_refresh:
        await cache_service.set("analytics_prediction", result, cache_key, ttl=1800)
    return json(result)


@analytics.route("/consumption/data-readiness", methods=["GET"])
@auth_required
async def get_consumption_data_readiness(request: Request):
    """获取数据就绪度信息（横幅+置信度用）"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    readiness = await service.get_data_readiness()

    result = {"code": 0, "message": "success", "data": readiness}
    return json(result)


@analytics.route("/consumption/accuracy", methods=["POST"])
@auth_required
@require_permission("analytics:forecast_edit")
async def record_consumption_accuracy(request: Request):
    """记录预测准确度（预测 vs 实际消费）

    手动触发或由定时任务调用。记录最新数据月的预测准确度。
    """
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    record = await service.record_prediction_accuracy()
    await db_session.commit()

    result = {"code": 0, "message": "success", "data": record}
    return json(result)


@analytics.route("/consumption/price-config", methods=["GET"])
@auth_required
async def get_price_config(request: Request):
    """获取消费预测单价配置"""
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    prices = await service.get_unit_prices()

    result = {
        "code": 0,
        "data": [{"device_type": k, "unit_price": v} for k, v in sorted(prices.items())],
    }
    return json(result)


@analytics.route("/consumption/price-config", methods=["PUT"])
@auth_required
@require_permission("analytics:forecast_edit")
async def update_price_config(request: Request):
    """更新消费预测单价配置"""
    data = request.json
    if not data or "prices" not in data:
        return json({"code": 40001, "message": "缺少 prices 字段"})

    prices = data["prices"]
    if not isinstance(prices, dict):
        return json({"code": 40001, "message": "prices 必须为对象"})

    # 验证设备类型
    valid_types = {"L", "N", "X"}
    for k in prices:
        if k not in valid_types:
            return json({"code": 40001, "message": f"无效的设备类型: {k}"})

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    await service.update_unit_prices(prices)
    await db_session.commit()

    # 清除预测缓存
    from app.cache.base import cache_service

    await cache_service.invalidate_analytics_cache("prediction")

    result = {"code": 0, "message": "success", "data": {"prices": prices}}
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


@analytics.route("/dashboard/trend", methods=["GET"])
@auth_required
async def get_dashboard_trend(request: Request):
    """获取仪表盘趋势数据（支持多指标切换）

    查询参数:
    - metric: consumption | payment | customer_count | health
    - months: 查询月数（默认 12）
    """
    metric = request.args.get("metric", "consumption")
    months = int(request.args.get("months", 12))
    if months > 24:
        months = 24

    cache_key = f"{metric}:{months}"
    cached = await cache_service.get("analytics_dashboard_trend", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    from dateutil.relativedelta import relativedelta

    end_date = local_today_utc_start()
    start_date = end_date - relativedelta(months=months)

    if metric == "consumption":
        trend = await service.get_consumption_trend(start_date, end_date, None, None)
        dates = [item.get("period", "") for item in trend]
        values = [item.get("total_amount", 0) for item in trend]
    elif metric == "payment":
        # 回款趋势：使用结算单数据
        invoice_stats = await service.get_invoice_status_stats(start_date, end_date)
        trend = invoice_stats.get("monthly_trend", [])  # pyright: ignore[reportAttributeAccessIssue]
        dates = [item.get("month", "") for item in trend]
        values = [item.get("paid_amount", 0) for item in trend]
    elif metric == "customer_count":
        # 客户数趋势
        chart_data = await service.get_dashboard_chart_data(months)
        trend = chart_data.get("customer_growth_trend", chart_data.get("consumption_trend", []))
        dates = [item.get("period", "") for item in trend]
        values = [item.get("customer_count", item.get("total_amount", 0)) for item in trend]
    elif metric == "health":
        # 健康度趋势
        health_stats = await service.get_customer_health_stats()
        trend = health_stats.get("monthly_trend", [])
        dates = [item.get("month", "") for item in trend]
        values = [item.get("avg_score", 0) for item in trend]
    else:
        return json({"code": 400, "message": "Invalid metric parameter"}, status=400)

    result = {
        "code": 0,
        "message": "success",
        "data": {"dates": dates, "values": values, "metric": metric},
    }
    await cache_service.set("analytics_dashboard_trend", result, cache_key, ttl=300)
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


@analytics.route("/usage/daily", methods=["GET"])
@auth_required
async def get_daily_usage(request: Request):
    """获取客户每日用量数据（分页）"""
    from datetime import timedelta

    from sqlalchemy import func, select

    from ..models.daily_consumption import DailyConsumption

    customer_id = request.args.get("customer_id")
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    if not customer_id:
        return json({"code": 400, "message": "缺少 customer_id 参数"}, status=400)

    db_session = request.ctx.db_session

    end_date = local_date_to_utc_end(end_date_str) if end_date_str else local_today_utc_start()
    start_date = (
        local_date_to_utc_start(start_date_str) if start_date_str else end_date - timedelta(days=30)
    )

    query = (
        select(DailyConsumption)
        .where(
            DailyConsumption.customer_id == int(customer_id),
            DailyConsumption.consumption_date >= start_date,
            DailyConsumption.consumption_date <= end_date,
        )
        .order_by(DailyConsumption.consumption_date.desc())
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db_session.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db_session.execute(query)
    records = result.scalars().all()

    items = [
        {
            "id": r.id,
            "customer_id": r.customer_id,
            "usage_date": r.consumption_date.isoformat(),
            "device_type": r.device_type,
            "layer_type": r.layer_type,
            "quantity": r.order_count,
            "synced_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {"list": items, "total": total, "page": page, "page_size": page_size},
        }
    )


# ==================== Phase 2: P1 分析接口扩展 ====================


@analytics.route("/profile/cross-dimension", methods=["GET"])
@auth_required
async def get_cross_dimension(request: Request):
    """获取行业×规模交叉维度热力图数据"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    cached = await cache_service.get("analytics_cross_dimension") if not force_refresh else None
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    # 获取行业分布和规模分布，构建交叉矩阵
    industry_dist = await service.get_industry_distribution()
    scale_dist = await service.get_scale_level_stats()

    result = {
        "code": 0,
        "message": "success",
        "data": {
            "industries": industry_dist,
            "scales": scale_dist,
            "matrix": [],  # 交叉矩阵数据
        },
    }
    await cache_service.set("analytics_cross_dimension", result, ttl=300)
    return json(result)


@analytics.route("/profile/tag-usage", methods=["GET"])
@auth_required
async def get_tag_usage(request: Request):
    """获取标签使用排行（Top 10）"""
    force_refresh = request.args.get("force_refresh", "").lower() == "true"
    cached = await cache_service.get("analytics_tag_usage") if not force_refresh else None
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    # 获取标签使用统计
    try:
        tag_stats = await service.get_tag_usage_stats()  # pyright: ignore[reportAttributeAccessIssue]
    except AttributeError:
        tag_stats = []

    result = {"code": 0, "message": "success", "data": tag_stats}
    await cache_service.set("analytics_tag_usage", result, ttl=300)
    return json(result)


@analytics.route("/health/risk-trend", methods=["GET"])
@auth_required
async def get_health_risk_trend(request: Request):
    """获取风险趋势（30天风险客户数变化）"""
    days = int(request.args.get("days", 30))
    if days > 180:
        days = 180

    cache_key = f"risk_trend:{days}"
    cached = await cache_service.get("analytics_health_risk_trend", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    # 获取健康度统计，提取趋势数据
    health_stats = await service.get_customer_health_stats()
    trend = health_stats.get("risk_trend", [])

    result = {"code": 0, "message": "success", "data": {"trend": trend, "days": days}}
    await cache_service.set("analytics_health_risk_trend", result, cache_key, ttl=300)
    return json(result)


@analytics.route("/health/export", methods=["GET"])
@auth_required
@require_permission("analytics:export")
async def export_health_report(request: Request):
    """导出健康度预警清单"""
    import io

    import pandas as pd

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    health_stats = await service.get_customer_health_stats()
    customers = health_stats.get("customers", [])

    data = []
    for c in customers:
        data.append(
            {
                "客户名称": c.get("name", ""),
                "健康度": c.get("score", 0),
                "状态": c.get("status", ""),
                "风险因素": c.get("risk_factors", ""),
            }
        )

    df = (
        pd.DataFrame(data)
        if data
        else pd.DataFrame(columns=["客户名称", "健康度", "状态", "风险因素"])
    )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:  # pyright: ignore[reportArgumentType]
        df.to_excel(writer, index=False, sheet_name="健康度预警")

    output.seek(0)
    from datetime import datetime as dt

    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    filename = f"health_report_{timestamp}.xlsx"

    from sanic.response import raw

    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@analytics.route("/payment/forecast-vs-actual", methods=["GET"])
@auth_required
async def get_forecast_vs_actual(request: Request):
    """获取预测 vs 实际回款对比"""
    year = int(request.args.get("year", datetime.utcnow().year))
    cache_key = f"forecast_vs_actual:{year}"
    cached = await cache_service.get("analytics_forecast_vs_actual", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    predictions = await service.predict_monthly_payment(year, None, None, None)

    result = {"code": 0, "message": "success", "data": predictions}
    await cache_service.set("analytics_forecast_vs_actual", result, cache_key, ttl=300)
    return json(result)


@analytics.route("/payment/top-customers", methods=["GET"])
@auth_required
async def get_payment_top_customers(request: Request):
    """获取回款排行 Top 客户"""
    limit = int(request.args.get("limit", 10))
    if limit > 50:
        limit = 50

    cache_key = f"top_customers:{limit}"
    cached = await cache_service.get("analytics_payment_top", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    try:
        top_customers = await service.get_payment_top_customers(limit=limit)  # pyright: ignore[reportAttributeAccessIssue]
    except AttributeError:
        top_customers = []

    result = {"code": 0, "message": "success", "data": top_customers}
    await cache_service.set("analytics_payment_top", result, cache_key, ttl=300)
    return json(result)


@analytics.route("/forecast/monthly-compare", methods=["GET"])
@auth_required
async def get_monthly_compare(request: Request):
    """获取月度对比数据（本月 vs 上月 vs 去年同期）"""
    year = int(request.args.get("year", datetime.utcnow().year))
    month = int(request.args.get("month", datetime.utcnow().month))

    cache_key = f"monthly_compare:{year}:{month}"
    cached = await cache_service.get("analytics_monthly_compare", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    # 获取本月预测
    current = await service.predict_monthly_payment(year, month, None, None)
    # 获取上月预测
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    previous = await service.predict_monthly_payment(prev_year, prev_month, None, None)
    # 获取去年同期
    last_year = await service.predict_monthly_payment(year - 1, month, None, None)

    result = {
        "code": 0,
        "message": "success",
        "data": {
            "current": current,
            "previous": previous,
            "last_year": last_year,
        },
    }
    await cache_service.set("analytics_monthly_compare", result, cache_key, ttl=300)
    return json(result)


@analytics.route("/priority-customers", methods=["GET"])
@auth_required
async def get_priority_customers(request: Request):
    """获取今日优先跟进客户列表

    筛选条件（满足任一）：
    - 余额低于阈值（默认 1000 元）
    - 余额可用天数不足 7 天
    - 有逾期结算单
    - 健康度评分低于 60

    返回按优先级排序的客户列表，每条包含客户名称、健康度、消耗、余额、风险、负责人。
    """
    limit = int(request.args.get("limit", 20))
    if limit > 50:
        limit = 50

    cache_key = f"priority:{limit}"
    cached = await cache_service.get("analytics_priority_customers", cache_key)
    if cached is not None:
        return json(cached)

    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)

    # 获取余额预警客户
    warning_customers = await service.get_balance_warning_list(threshold=1000)

    # 获取健康度统计中的风险客户
    health_stats = await service.get_customer_health_stats()
    risk_customers = health_stats.get("risk_customers", [])

    # 合并去重并构建结果
    seen_ids = set()
    customers = []

    for wc in warning_customers[:limit]:
        cid = wc["customer_id"]
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        # 使用实际剩余余额（real + bonus），而非累计充值额 total_amount
        remaining = wc.get("real_amount", 0) + wc.get("bonus_amount", 0)
        total = wc.get("total_amount", 0)

        customers.append(
            {
                "id": cid,
                "name": wc["customer_name"],
                "health": "关注",
                "health_class": "amber",
                "consumption": f"¥{total:,.0f}",
                "balance_days": "—",  # 占位，后续批量填充
                "risk": "余额不足" if remaining < 500 else "余额偏低",
                "manager": wc.get("manager_name", "未分配"),
            }
        )

    # 批量查询消费统计，计算真实 balance_days
    if seen_ids:
        from datetime import timedelta

        from sqlalchemy import func as sa_func
        from sqlalchemy import select as sa_select

        from ..models.billing import CustomerBalance
        from ..models.daily_consumption import DailyConsumption

        today = local_today_utc_start()
        thirty_days_ago = today - timedelta(days=30)
        consumption_stmt = (
            sa_select(
                DailyConsumption.customer_id,
                sa_func.coalesce(sa_func.sum(DailyConsumption.total_cost), 0).label(
                    "total_cost_30d"
                ),
                sa_func.count(sa_func.distinct(DailyConsumption.consumption_date)).label(
                    "consumption_days"
                ),
            )
            .where(
                DailyConsumption.customer_id.in_(list(seen_ids)),
                DailyConsumption.consumption_date >= thirty_days_ago,
                DailyConsumption.deleted_at.is_(None),
            )
            .group_by(DailyConsumption.customer_id)
        )
        consumption_result = await db_session.execute(consumption_stmt)
        consumption_map = {
            row.customer_id: {
                "total_cost_30d": float(row.total_cost_30d),
                "consumption_days": int(row.consumption_days),
            }
            for row in consumption_result.all()
        }

        # 同时查询余额信息用于计算 days_remaining
        balance_stmt = sa_select(
            CustomerBalance.customer_id,
            CustomerBalance.real_amount,
            CustomerBalance.bonus_amount,
        ).where(CustomerBalance.customer_id.in_(list(seen_ids)))
        balance_result = await db_session.execute(balance_stmt)
        balance_map = {
            row.customer_id: {
                "real_amount": float(row.real_amount or 0),
                "bonus_amount": float(row.bonus_amount or 0),
            }
            for row in balance_result.all()
        }

        # 填充 balance_days
        for c in customers:
            cid = c["id"]
            stats = consumption_map.get(cid)
            bal = balance_map.get(cid)
            if not stats or stats["total_cost_30d"] <= 0 or not bal:
                c["balance_days"] = "充足"
                continue
            daily_avg = stats["total_cost_30d"] / max(stats["consumption_days"], 7)
            remaining = bal["real_amount"] + bal["bonus_amount"]
            if daily_avg > 0:
                days = int(remaining / daily_avg)
                c["balance_days"] = f"{days} 天" if days < 999 else "充足"
            else:
                c["balance_days"] = "充足"

    # 补充风险客户
    for rc in risk_customers[:limit]:
        cid = rc.get("customer_id") or rc.get("id")
        if not cid or cid in seen_ids:
            continue
        seen_ids.add(cid)

        score = rc.get("score", 0)
        health_label = "高风险" if score < 40 else "关注"
        health_class = "red" if score < 40 else "amber"

        customers.append(
            {
                "id": cid,
                "name": rc.get("customer_name", rc.get("name", f"客户#{cid}")),
                "health": health_label,
                "health_class": health_class,
                "consumption": "—",
                "balance_days": "—",
                "risk": rc.get("risk_type", "健康度异常"),
                "manager": rc.get("manager_name", "未分配"),
            }
        )

    result = {
        "code": 0,
        "message": "success",
        "data": {
            "customers": customers[:limit],
            "total": len(customers),
        },
    }
    await cache_service.set("analytics_priority_customers", result, cache_key, ttl=300)
    return json(result)
