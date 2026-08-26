"""开放平台 API 路由 — ERP 渠道客户余额查询"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import outerjoin

from ..constants import ErrorCodes
from ..models.billing import CustomerBalance
from ..models.customers import Customer

openapi_bp = Blueprint("open_platform", url_prefix="/api/v1/erp")


@openapi_bp.get("/balances")
async def get_erp_balances(request: Request):
    """
    获取 ERP 渠道下游客户余额

    通过 API-Key 认证，返回指定 ERP 渠道下所有企业的客户ID、名称和当前余额。

    Query:
    - erp_channel: str (required) — ERP 渠道编码，如 "qiaofang"

    Response:
    - data: [{customer_id, customer_name, balance}, ...]
    """
    erp_channel = request.args.get("erp_channel")

    if not erp_channel or not erp_channel.strip():
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "缺少必要参数: erp_channel"},
            status=400,
        )

    erp_channel = erp_channel.strip()

    db_session: AsyncSession = request.ctx.db_session

    # 查询指定 ERP 渠道下未删除、未停用的客户，LEFT JOIN 余额表
    stmt = (
        select(
            Customer.company_id,
            Customer.name,
            CustomerBalance.total_amount,
            CustomerBalance.used_total,
        )
        .select_from(
            outerjoin(Customer, CustomerBalance, Customer.id == CustomerBalance.customer_id)
        )
        .where(
            Customer.erp_system == erp_channel,
            Customer.deleted_at.is_(None),
            Customer.is_disabled.isnot(True),
        )
        .order_by(Customer.company_id.asc())
    )

    result = await db_session.execute(stmt)
    rows = result.all()

    data = []
    for row in rows:
        company_id, name, total_amount, used_total = row
        total = float(total_amount) if total_amount else 0.0
        used = float(used_total) if used_total else 0.0
        balance = round(total - used, 2)

        data.append(
            {
                "customer_id": str(company_id),
                "customer_name": name,
                "balance": balance,
            }
        )

    return json(
        {
            "code": 0,
            "message": "success",
            "data": data,
        }
    )
