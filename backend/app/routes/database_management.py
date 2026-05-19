"""数据库管理路由

提供数据库数据清空等管理功能。
"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import auth_required, require_permission
from ..models.customers import Customer
from ..utils.audit_helpers import create_audit_entry

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
    - daily_usage (每日用量)
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
    user_id = user.get("user_id")
    if user_id:
        await create_audit_entry(
            db_session=db_session,
            user_id=user_id,
            action="database_clear",
            module="system",
            changes={
                "deleted_count": customer_count,
                "tables_affected": [
                    "customers",
                    "customer_profiles",
                    "customer_balances",
                    "customer_tags",
                    "profile_tags",
                    "invoices",
                    "invoice_items",
                    "consumption_records",
                    "daily_usage",
                    "pricing_rules",
                    "recharge_records",
                ],
            },
            operation_type="sensitive",
            auto_commit=False,
        )

    try:
        # 按依赖顺序删除
        # 1. 画像标签关联（通过 profile 关联到 customer）
        await db_session.execute(
            """
            DELETE FROM profile_tags
            WHERE profile_id IN (
                SELECT id FROM customer_profiles WHERE customer_id IN (SELECT id FROM customers)
            )
            """
        )

        # 2. 客户标签关联
        await db_session.execute(
            "DELETE FROM customer_tags WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 3. 结算单明细
        await db_session.execute(
            """
            DELETE FROM invoice_items
            WHERE invoice_id IN (
                SELECT id FROM invoices WHERE customer_id IN (SELECT id FROM customers)
            )
            """
        )

        # 4. 消费流水
        await db_session.execute(
            "DELETE FROM consumption_records WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 5. 每日用量
        await db_session.execute(
            "DELETE FROM daily_usage WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 6. 充值记录
        await db_session.execute(
            "DELETE FROM recharge_records WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 7. 计费规则
        await db_session.execute(
            "DELETE FROM pricing_rules WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 8. 结算单
        await db_session.execute(
            "DELETE FROM invoices WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 9. 客户余额（有 ondelete=CASCADE，但显式删除更安全）
        await db_session.execute(
            "DELETE FROM customer_balances WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 10. 客户画像
        await db_session.execute(
            "DELETE FROM customer_profiles WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 11. 客户主表
        await db_session.execute("DELETE FROM customers")

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
        await db_session.rollback()
        return json(
            {
                "code": 500,
                "message": f"数据清空失败: {str(e)}",
            },
            status=500,
        )
