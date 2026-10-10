"""开放平台 API 路由 — 客户余额查询

- GET /api/v1/erp/balances   按 ERP 渠道查询客户余额（erp_channel 必填）
- GET /api/v1/balances       全量客户余额查询（不限 ERP 渠道，与 erp 域平级）
"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import outerjoin

from ..constants import ErrorCodes
from ..models.billing import CustomerBalance
from ..models.customers import Customer

openapi_bp = Blueprint("open_platform", url_prefix="/api/v1/erp")
# 全量客户余额接口与 ERP 渠道域平级，使用独立蓝图（url_prefix=/api/v1）
openapi_customer_bp = Blueprint("open_platform_customer", url_prefix="/api/v1")


def _build_customer_balance_stmt(erp_channel: str | None = None) -> Select:
    """构建客户余额查询语句

    - erp_channel 为空：返回全部有效客户（未删除、未停用，不限 ERP 渠道）
    - 指定 erp_channel：仅返回该 ERP 渠道客户

    LEFT JOIN 余额表，无余额记录的客户保留（balance 按 0 处理），
    按 company_id 升序，两个开放平台余额接口共用，保证口径一致。
    """
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
            Customer.deleted_at.is_(None),
            Customer.is_disabled.isnot(True),
        )
        .order_by(Customer.company_id.asc())
    )
    if erp_channel:
        stmt = stmt.where(Customer.erp_system == erp_channel)
    return stmt


def _format_balance_rows(rows) -> list[dict]:
    """将余额查询结果格式化为统一响应结构"""
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
    return data


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
    result = await db_session.execute(_build_customer_balance_stmt(erp_channel))
    payload = {
        "code": 0,
        "message": "success",
        "data": _format_balance_rows(result.all()),
    }
    return json(payload)


@openapi_customer_bp.get("/balances")
async def get_all_customer_balances(request: Request):
    """
    获取所有客户余额

    通过 API-Key 认证，返回全部有效客户（未删除、未停用，不限 ERP 渠道，
    含无 ERP / noerp 客户）的客户ID、名称和当前余额。

    Response:
    - data: [{customer_id, customer_name, balance}, ...]
    """
    db_session: AsyncSession = request.ctx.db_session
    result = await db_session.execute(_build_customer_balance_stmt())
    payload = {
        "code": 0,
        "message": "success",
        "data": _format_balance_rows(result.all()),
    }
    return json(payload)
