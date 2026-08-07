"""数据库管理路由

提供数据库数据清空等管理功能。
"""

import logging

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..middleware.auth import auth_required, require_permission
from ..models.customers import Customer
from ..utils.audit_helpers import create_audit_entry

logger = logging.getLogger(__name__)

database_bp = Blueprint("database_management", url_prefix="/api/v1/system/database")


@database_bp.post("/clear")
@auth_required
@require_permission("system:database_clear")
async def clear_customer_data(request: Request):
    """
    级联清空所有客户及关联数据

    仅管理员可用，需要 system:database_clear 权限。
    操作不可逆，会删除以下数据：
    - customers (客户主表)
    - customer_profiles (客户画像)
    - customer_balances (客户余额)
    - customer_tags (客户标签关联)
    - profile_tags (画像标签关联)
    - invoices (结算单)
    - invoice_items (结算单明细)
    - consumption_records (消费流水)
    - daily_consumptions (每日消费)
    - daily_orders (每日订单)
    - pricing_rules (计费规则)
    - recharge_records (充值记录)

    操作会记录到 audit_logs 表。
    """
    db_session: AsyncSession = request.ctx.db_session
    user = request.ctx.user

    # 统计即将删除的客户数量
    count_result = await db_session.execute(select(func.count(Customer.id)))
    customer_count = count_result.scalar() or 0

    # 快捷返回：如果无数据则直接返回
    if customer_count == 0:
        return json({"code": 0, "message": "无数据可清空", "data": {"deleted_count": 0}})

    # 创建审计日志条目（在事务中，不自动提交）
    user_id = user["user_id"]
    await create_audit_entry(
        db_session=db_session,
        user_id=user_id,
        action="database_clear",
        module="system",
        record_id=None,  # 批量操作，无单一记录 ID
        record_type="database",  # 标识操作类型
        changes={
            "before": {"customer_count": customer_count},
            "after": {"customer_count": 0},
            "tables_affected": [
                "customers",
                "customer_profiles",
                "customer_balances",
                "customer_tags",
                "profile_tags",
                "invoices",
                "invoice_items",
                "consumption_records",
                "daily_consumptions",
                "daily_orders",
                "pricing_rules",
                "recharge_records",
            ],
        },
        operation_type="sensitive",
        auto_commit=False,
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
    )

    try:
        # 按依赖顺序删除
        # 1. 画像标签关联（通过 profile 关联到 customer）
        await db_session.execute(
            text(
                """
            DELETE FROM profile_tags
            WHERE profile_id IN (
                SELECT id FROM customer_profiles WHERE customer_id IN (SELECT id FROM customers)
            )
            """
            )
        )

        # 2. 客户标签关联
        await db_session.execute(
            text("DELETE FROM customer_tags WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 3. 结算单明细
        await db_session.execute(
            text(
                """
            DELETE FROM invoice_items
            WHERE invoice_id IN (
                SELECT id FROM invoices WHERE customer_id IN (SELECT id FROM customers)
            )
            """
            )
        )

        # 4. 消费流水
        await db_session.execute(
            text("DELETE FROM consumption_records WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 5. 每日消费
        await db_session.execute(
            text("DELETE FROM daily_consumptions WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 6. 每日订单
        await db_session.execute(
            text("DELETE FROM daily_orders WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 7. 充值记录
        await db_session.execute(
            text("DELETE FROM recharge_records WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 8. 计费规则
        await db_session.execute(
            text("DELETE FROM pricing_rules WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 9. 结算单
        await db_session.execute(
            text("DELETE FROM invoices WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 10. 客户余额（有 ondelete=CASCADE，但显式删除更安全）
        await db_session.execute(
            text("DELETE FROM customer_balances WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 11. 客户画像
        await db_session.execute(
            text("DELETE FROM customer_profiles WHERE customer_id IN (SELECT id FROM customers)")
        )

        # 12. 客户主表
        await db_session.execute(text("DELETE FROM customers"))

        # 清除客户相关 Redis 缓存
        await cache_service.invalidate_customer_cache()

        # 提交事务
        await db_session.commit()

        return json(
            {
                "code": 0,
                "message": f"成功清空 {customer_count} 条客户数据",
                "data": {"deleted_count": customer_count},
            },
            status=200,
        )

    except Exception as e:
        logger.exception("数据库清空失败")
        await db_session.rollback()
        return json(
            {
                "code": 500,
                "message": f"数据清空失败: {str(e)}",
            },
            status=500,
        )


@database_bp.post("/clear-consumption")
@auth_required
@require_permission("system:database_clear")
async def clear_consumption_data(request: Request):
    """
    清空消耗分析数据

    仅管理员可用，需要 system:database_clear 权限。
    操作不可逆，会删除以下数据：
    - daily_consumptions (每日消费计算结果)
    - daily_orders (每日订单原始数据)
    - sync_tasks (同步任务记录)
    - sync_task_logs (同步任务日志)

    不会删除客户主表、计费规则、结算单等数据。
    操作会记录到 audit_logs 表。
    """
    db_session: AsyncSession = request.ctx.db_session
    user = request.ctx.user

    # 统计即将删除的数据量
    from ..models.daily_consumption import DailyConsumption
    from ..models.daily_order import DailyOrder

    consumption_count_result = await db_session.execute(select(func.count(DailyConsumption.id)))
    consumption_count = consumption_count_result.scalar() or 0

    order_count_result = await db_session.execute(select(func.count(DailyOrder.id)))
    order_count = order_count_result.scalar() or 0

    total_count = consumption_count + order_count

    # 快捷返回：如果无数据则直接返回
    if total_count == 0:
        return json({"code": 0, "message": "无消耗数据可清空", "data": {"deleted_count": 0}})

    # 创建审计日志条目（在事务中，不自动提交）
    user_id = user["user_id"]
    await create_audit_entry(
        db_session=db_session,
        user_id=user_id,
        action="database_clear_consumption",
        module="system",
        record_id=None,
        record_type="database",
        changes={
            "before": {
                "daily_consumptions_count": consumption_count,
                "daily_orders_count": order_count,
            },
            "after": {
                "daily_consumptions_count": 0,
                "daily_orders_count": 0,
            },
            "tables_affected": [
                "daily_consumptions",
                "daily_orders",
                "sync_tasks",
                "sync_task_logs",
            ],
        },
        operation_type="sensitive",
        auto_commit=False,
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
    )

    try:
        # 按依赖顺序删除
        # 1. 同步任务日志（引用 sync_tasks）
        await db_session.execute(text("DELETE FROM sync_task_logs"))

        # 2. 同步任务
        await db_session.execute(text("DELETE FROM sync_tasks"))

        # 3. 每日消费计算结果（引用 daily_orders 和 pricing_rules）
        await db_session.execute(text("DELETE FROM daily_consumptions"))

        # 4. 每日订单原始数据
        await db_session.execute(text("DELETE FROM daily_orders"))

        # 清除消耗分析相关 Redis 缓存
        await cache_service.invalidate_pattern("cache:analytics_*")

        # 提交事务
        await db_session.commit()

        return json(
            {
                "code": 0,
                "message": f"成功清空消耗分析数据（消费记录 {consumption_count} 条，订单记录 {order_count} 条）",
                "data": {
                    "deleted_count": total_count,
                    "daily_consumptions_deleted": consumption_count,
                    "daily_orders_deleted": order_count,
                },
            },
            status=200,
        )

    except Exception as e:
        logger.exception("消耗分析数据清空失败")
        await db_session.rollback()
        return json(
            {
                "code": 500,
                "message": f"消耗分析数据清空失败: {str(e)}",
            },
            status=500,
        )


@database_bp.post("/clear-balance")
@auth_required
@require_permission("system:database_clear")
async def clear_balance_data(request: Request):
    """
    清空余额数据

    仅管理员可用，需要 system:database_clear 权限。
    操作不可逆，会删除以下数据：
    - customer_balances (客户余额)
    - recharge_records (充值记录)
    - consumption_records (消费流水)

    不会删除客户主表、计费规则、结算单、消耗分析等数据。
    操作会记录到 audit_logs 表。
    """
    db_session: AsyncSession = request.ctx.db_session
    user = request.ctx.user

    # 统计即将删除的数据量
    from ..models.billing import ConsumptionRecord, CustomerBalance, RechargeRecord

    balance_count_result = await db_session.execute(select(func.count(CustomerBalance.id)))
    balance_count = balance_count_result.scalar() or 0

    recharge_count_result = await db_session.execute(select(func.count(RechargeRecord.id)))
    recharge_count = recharge_count_result.scalar() or 0

    consumption_records_result = await db_session.execute(select(func.count(ConsumptionRecord.id)))
    consumption_records_count = consumption_records_result.scalar() or 0

    total_count = balance_count + recharge_count + consumption_records_count

    # 快捷返回：如果无数据则直接返回
    if total_count == 0:
        return json({"code": 0, "message": "无余额数据可清空", "data": {"deleted_count": 0}})

    # 创建审计日志条目（在事务中，不自动提交）
    user_id = user["user_id"]
    await create_audit_entry(
        db_session=db_session,
        user_id=user_id,
        action="database_clear_balance",
        module="system",
        record_id=None,
        record_type="database",
        changes={
            "before": {
                "customer_balances_count": balance_count,
                "recharge_records_count": recharge_count,
                "consumption_records_count": consumption_records_count,
            },
            "after": {
                "customer_balances_count": 0,
                "recharge_records_count": 0,
                "consumption_records_count": 0,
            },
            "tables_affected": [
                "customer_balances",
                "recharge_records",
                "consumption_records",
            ],
        },
        operation_type="sensitive",
        auto_commit=False,
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
    )

    try:
        # 按依赖顺序删除
        # 1. 消费流水（引用 customer_balances 和 invoices）
        await db_session.execute(text("DELETE FROM consumption_records"))

        # 2. 充值记录（引用 customer_balances）
        await db_session.execute(text("DELETE FROM recharge_records"))

        # 3. 客户余额
        await db_session.execute(text("DELETE FROM customer_balances"))

        # 清除余额相关 Redis 缓存
        await cache_service.invalidate_customer_cache()

        # 提交事务
        await db_session.commit()

        return json(
            {
                "code": 0,
                "message": (
                    f"成功清空余额数据"
                    f"（余额 {balance_count} 条，充值记录 {recharge_count} 条，"
                    f"消费流水 {consumption_records_count} 条）"
                ),
                "data": {
                    "deleted_count": total_count,
                    "balances_deleted": balance_count,
                    "recharges_deleted": recharge_count,
                    "consumption_records_deleted": consumption_records_count,
                },
            },
            status=200,
        )

    except Exception as e:
        logger.exception("余额数据清空失败")
        await db_session.rollback()
        return json(
            {
                "code": 500,
                "message": f"余额数据清空失败: {str(e)}",
            },
            status=500,
        )


@database_bp.post("/clear-invoices")
@auth_required
@require_permission("system:database_clear")
async def clear_invoice_data(request: Request):
    """
    清空结算单数据

    仅管理员可用，需要 system:database_clear 权限。
    操作不可逆，会删除以下数据：
    - invoices (结算单)
    - invoice_items (结算单明细)
    - consumption_records 中关联结算单的消费流水（invoice_id IS NOT NULL）

    不会删除客户主表、计费规则、余额、消耗分析等数据。
    操作会记录到 audit_logs 表。
    """
    db_session: AsyncSession = request.ctx.db_session
    user = request.ctx.user

    # 统计即将删除的数据量
    from ..models.billing import ConsumptionRecord, Invoice, InvoiceItem

    invoice_count_result = await db_session.execute(select(func.count(Invoice.id)))
    invoice_count = invoice_count_result.scalar() or 0

    invoice_item_count_result = await db_session.execute(select(func.count(InvoiceItem.id)))
    invoice_item_count = invoice_item_count_result.scalar() or 0

    # 仅统计关联了结算单的消费流水
    consumption_linked_result = await db_session.execute(
        select(func.count(ConsumptionRecord.id)).where(ConsumptionRecord.invoice_id.is_not(None))
    )
    consumption_linked_count = consumption_linked_result.scalar() or 0

    total_count = invoice_count + invoice_item_count + consumption_linked_count

    # 快捷返回：如果无数据则直接返回
    if total_count == 0:
        return json({"code": 0, "message": "无结算单数据可清空", "data": {"deleted_count": 0}})

    # 创建审计日志条目（在事务中，不自动提交）
    user_id = user["user_id"]
    await create_audit_entry(
        db_session=db_session,
        user_id=user_id,
        action="database_clear_invoices",
        module="system",
        record_id=None,
        record_type="database",
        changes={
            "before": {
                "invoices_count": invoice_count,
                "invoice_items_count": invoice_item_count,
                "consumption_records_linked_count": consumption_linked_count,
            },
            "after": {
                "invoices_count": 0,
                "invoice_items_count": 0,
                "consumption_records_linked_count": 0,
            },
            "tables_affected": [
                "invoices",
                "invoice_items",
                "consumption_records (invoice_id IS NOT NULL)",
            ],
        },
        operation_type="sensitive",
        auto_commit=False,
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
    )

    try:
        # 按依赖顺序删除
        # 1. 关联结算单的消费流水（invoice_id 外键无 CASCADE，需先删除）
        await db_session.execute(
            text("DELETE FROM consumption_records WHERE invoice_id IS NOT NULL")
        )

        # 2. 结算单明细（虽有 ondelete=CASCADE，显式删除更安全）
        await db_session.execute(text("DELETE FROM invoice_items"))

        # 3. 结算单
        await db_session.execute(text("DELETE FROM invoices"))

        # 清除结算单相关 Redis 缓存
        await cache_service.invalidate_billing_cache()

        # 提交事务
        await db_session.commit()

        return json(
            {
                "code": 0,
                "message": (
                    f"成功清空结算单数据"
                    f"（结算单 {invoice_count} 条，明细 {invoice_item_count} 条，"
                    f"关联消费流水 {consumption_linked_count} 条）"
                ),
                "data": {
                    "deleted_count": total_count,
                    "invoices_deleted": invoice_count,
                    "invoice_items_deleted": invoice_item_count,
                    "consumption_records_linked_deleted": consumption_linked_count,
                },
            },
            status=200,
        )

    except Exception as e:
        logger.exception("结算单数据清空失败")
        await db_session.rollback()
        return json(
            {
                "code": 500,
                "message": f"结算单数据清空失败: {str(e)}",
            },
            status=500,
        )
