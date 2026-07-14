"""客户管理路由"""

import hashlib
import io
import math
import re
from datetime import datetime

import pandas as pd
from sanic import Blueprint
from sanic.request import Request
from sanic.response import json, raw
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..middleware.auth import auth_required, get_current_user, require_permission
from ..services.customers import (
    CustomerService,
    convert_price_policy_to_display,
    convert_settlement_cycle_to_display,
    convert_settlement_type_to_display,
)
from ..utils.audit_helpers import build_batch_audit_summary, create_audit_entry

customers_bp = Blueprint("customers", url_prefix="/api/v1/customers")


@customers_bp.get("")
@auth_required
@require_permission("customers:view")
async def list_customers(request: Request):
    """
    获取客户列表（支持筛选和排序）

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    - keyword: 关键词（公司名称/公司 ID）
    - account_type: 账号类型
    - industry: 行业类型
    - manager_id: 运营经理 ID
    - sales_manager_id: 商务经理 ID
    - settlement_type: 结算方式
    - is_key_customer: 是否重点客户 (true/false)
    - sort_by: 排序字段 (id, company_id, name, created_at, updated_at，默认 id)
    - sort_order: 排序方向 (asc 或 desc，默认 asc)
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    page_size = min(page_size, 100)

    # 排序参数
    sort_by = request.args.get("sort_by", "company_id")
    sort_order = request.args.get("sort_order", "asc")

    # 构建筛选条件
    filters = {
        "keyword": request.args.get("keyword"),
        "account_type": request.args.get("account_type"),
        "industry": request.args.get("industry"),
        "scale_level": request.args.get("scale_level"),
        "consume_level": request.args.get("consume_level"),
        "manager_id": (
            int(request.args.get("manager_id", 0)) if request.args.get("manager_id") else None
        ),
        "sales_manager_id": (
            int(request.args.get("sales_manager_id", 0))
            if request.args.get("sales_manager_id")
            else None
        ),
        "settlement_type": request.args.get("settlement_type"),
    }

    # 处理布尔值
    is_key = request.args.get("is_key_customer")
    if is_key is not None:
        filters["is_key_customer"] = is_key.lower() == "true"

    is_real_estate = request.args.get("is_real_estate")
    if is_real_estate is not None:
        filters["is_real_estate"] = is_real_estate.lower() == "true"

    # 移除 None 值
    filters = {k: v for k, v in filters.items() if v is not None}

    # 构建缓存键
    filters_hash = hashlib.md5(
        str(sorted(filters.items())).encode(), usedforsecurity=False
    ).hexdigest()[:8]
    cache_key = f"p{page}_ps{page_size}_sb{sort_by}_so{sort_order}_{filters_hash}"

    # 检查是否强制刷新（跳过缓存）
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    # 尝试从缓存获取
    if not force_refresh:
        cached = await cache_service.get("customer_list", cache_key)
        if cached is not None:
            return json(cached)

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    try:
        customers, total = await service.get_all_customers(
            page=page, page_size=page_size, filters=filters, sort_by=sort_by, sort_order=sort_order
        )
    except ValueError as e:
        return json({"code": 40001, "message": str(e)}, status=400)

    result = {
        "code": 0,
        "message": "success",
        "data": {
            "list": [
                {
                    "id": c.id,
                    "company_id": c.company_id,
                    "name": c.name,
                    "account_type": c.account_type,
                    "industry": (
                        c.profile.industry_type.name
                        if (c.profile and c.profile.industry_type)
                        else None
                    ),
                    "industry_type_id": c.profile.industry_type_id if c.profile else None,
                    "price_policy": convert_price_policy_to_display(c.price_policy),
                    "manager_id": c.manager_id,
                    "sales_manager_id": c.sales_manager_id,
                    "settlement_cycle": c.settlement_cycle,
                    "settlement_type": c.settlement_type,
                    "is_key_customer": c.is_key_customer,
                    "is_real_estate": c.is_real_estate,
                    "email": c.email,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    # === 客户列表页新增字段 ===
                    "scale_level": c.profile.scale_level if c.profile else None,
                    "consume_level": c.profile.consume_level if c.profile else None,
                    "balance": (
                        float(c.balance.total_amount)
                        if c.balance
                        else 0.0
                    ),
                    # 以下字段暂为占位，后续画像分析模块完善后补全
                    "usage_30d": None,
                    "usage_30d_amount": None,
                    "health": None,
                }
                for c in customers
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }

    # 写入缓存
    await cache_service.set("customer_list", result, cache_key)

    return json(result)


@customers_bp.get("/<customer_id:int>")
@auth_required
@require_permission("customers:view")
async def get_customer(request: Request, customer_id: int):
    """获取客户详情（包含画像和余额）"""
    # 尝试从缓存获取
    cached = await cache_service.get("customer_detail", customer_id)
    if cached is not None:
        return json(cached)

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    customer = await service.get_customer_by_id(customer_id)

    if not customer:
        return json({"code": 40401, "message": "客户不存在"}, status=404)

    data = {
        "id": customer.id,
        "company_id": customer.company_id,
        "name": customer.name,
        "account_type": customer.account_type,
        "industry": (
            customer.profile.industry_type.name
            if customer.profile and customer.profile.industry_type
            else None
        ),
        "price_policy": convert_price_policy_to_display(customer.price_policy),
        "manager_id": customer.manager_id,
        "settlement_cycle": customer.settlement_cycle,
        "settlement_type": customer.settlement_type,
        "is_key_customer": customer.is_key_customer,
        "email": customer.email,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "erp_system": customer.erp_system,
        "first_payment_date": (
            customer.first_payment_date.isoformat() if customer.first_payment_date else None
        ),
        "onboarding_date": (
            customer.onboarding_date.isoformat() if customer.onboarding_date else None
        ),
        "sales_manager_id": customer.sales_manager_id,
        "cooperation_status": customer.cooperation_status,
        "is_settlement_enabled": customer.is_settlement_enabled,
        "is_disabled": customer.is_disabled,
        "is_real_estate": customer.is_real_estate,
        "notes": customer.notes,
    }

    # 添加画像信息
    if customer.profile:
        data["profile"] = {
            "id": customer.profile.id,
            "scale_level": customer.profile.scale_level,
            "consume_level": customer.profile.consume_level,
            "industry_type_id": customer.profile.industry_type_id,
            "industry": (
                customer.profile.industry_type.name if customer.profile.industry_type else None
            ),
            "is_real_estate": customer.is_real_estate,
            "description": customer.profile.description,
            "monthly_avg_shots": customer.profile.monthly_avg_shots,
            "monthly_avg_shots_estimated": customer.profile.monthly_avg_shots_estimated,
            "estimated_annual_spend": (
                float(customer.profile.estimated_annual_spend)
                if customer.profile.estimated_annual_spend is not None
                else None
            ),
            "actual_annual_spend_2025": (
                float(customer.profile.actual_annual_spend_2025)
                if customer.profile.actual_annual_spend_2025 is not None
                else None
            ),
        }
    else:
        data["profile"] = None

    # 添加余额信息
    if customer.balance:
        data["balance"] = {
            "total_amount": (
                float(customer.balance.total_amount) if customer.balance.total_amount else 0
            ),
            "real_amount": (
                float(customer.balance.real_amount) if customer.balance.real_amount else 0
            ),
            "bonus_amount": (
                float(customer.balance.bonus_amount) if customer.balance.bonus_amount else 0
            ),
            "used_total": float(customer.balance.used_total) if customer.balance.used_total else 0,
            "used_real": float(customer.balance.used_real) if customer.balance.used_real else 0,
            "used_bonus": float(customer.balance.used_bonus) if customer.balance.used_bonus else 0,
        }
    else:
        data["balance"] = None

    result = {"code": 0, "message": "success", "data": data}

    # 写入缓存
    await cache_service.set("customer_detail", result, customer_id)

    return json(result)


@customers_bp.post("")
@auth_required
@require_permission("customers:create")
async def create_customer(request: Request):
    """
    创建客户

    Body:
    {
        "company_id": "integer (required)",
        "name": "string (required)",
        "account_type": "string (optional)",
        "industry": "string (optional)",
        "price_policy": "string (optional)",
        "manager_id": "number (optional)",
        "settlement_cycle": "string (optional)",
        "settlement_type": "string (optional)",
        "is_key_customer": "boolean (optional)",
        "is_real_estate": "boolean (optional)",
        "email": "string (optional)"
    }
    """
    data = request.json

    # 必填字段验证
    if not data.get("company_id") or not data.get("name"):
        return json({"code": 40001, "message": "公司 ID 和客户名称不能为空"}, status=400)

    # 邮箱格式验证
    email = data.get("email")
    if email:
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return json({"code": 40002, "message": "邮箱格式不正确"}, status=400)

    # industry_type_id 存在性验证
    industry_type_id = data.get("industry_type_id")
    if industry_type_id is not None:
        from sqlalchemy import select

        from ..models.industry_type import IndustryType

        db_session: AsyncSession = request.ctx.db_session
        result = await db_session.execute(
            select(IndustryType).where(IndustryType.id == industry_type_id)
        )
        if not result.scalar_one_or_none():
            return json({"code": 40004, "message": "行业类型不存在"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    try:
        customer = await service.create_customer(data)
    except ValueError as e:
        return json({"code": 40003, "message": str(e)}, status=400)
    except Exception as e:
        return json({"code": 40003, "message": str(e)}, status=400)

    # 清除缓存
    await cache_service.invalidate_customer_cache()

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": customer.id,
                "company_id": customer.company_id,
                "name": customer.name,
            },
        },
        status=201,
    )


@customers_bp.put("/<customer_id:int>")
@auth_required
@require_permission("customers:edit")
async def update_customer(request: Request, customer_id: int):
    """
    更新客户信息

    Body:
    {
        "company_id": "integer (optional, 需唯一)",
        "name": "string (optional)",
        "account_type": "string (optional)",
        "industry": "string (optional)",
        "price_policy": "string (optional)",
        "manager_id": "number (optional)",
        "settlement_cycle": "string (optional)",
        "settlement_type": "string (optional)",
        "is_key_customer": "boolean (optional)",
        "is_real_estate": "boolean (optional)",
        "email": "string (optional)"
    }
    """
    data = request.json

    # 邮箱格式验证
    email = data.get("email")
    if email:
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return json({"code": 40002, "message": "邮箱格式不正确"}, status=400)

    # industry_type_id 存在性验证
    industry_type_id = data.get("industry_type_id")
    if industry_type_id is not None:
        from sqlalchemy import select

        from ..models.industry_type import IndustryType

        db_session: AsyncSession = request.ctx.db_session
        result = await db_session.execute(
            select(IndustryType).where(IndustryType.id == industry_type_id)
        )
        if not result.scalar_one_or_none():
            return json({"code": 40004, "message": "行业类型不存在"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    try:
        customer = await service.update_customer(customer_id, data)
    except ValueError as e:
        return json({"code": 40003, "message": str(e)}, status=400)
    except Exception as e:
        return json({"code": 50001, "message": f"更新失败: {str(e)}"}, status=500)

    if not customer:
        return json({"code": 40401, "message": "客户不存在"}, status=404)

    # 清除缓存
    await cache_service.invalidate_customer_cache(customer_id)

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {
                "id": customer.id,
                "company_id": customer.company_id,
                "name": customer.name,
            },
        }
    )


@customers_bp.post("/batch-update")
@auth_required
@require_permission("customers:edit")
async def batch_update_customers(request: Request):
    """
    批量更新客户信息

    Body:
    {
        "customer_ids": [1, 2, 3],  # list[int], 非空，上限 100
        "fields": {                  # dict, 非空，仅包含要更新的字段
            "is_key_customer": true,
            "settlement_cycle": "monthly"
        }
    }
    """
    data = request.json
    if not data:
        return json({"code": 40001, "message": "请求体不能为空"}, status=400)

    customer_ids = data.get("customer_ids")
    fields = data.get("fields")

    if not customer_ids or not isinstance(customer_ids, list) or len(customer_ids) == 0:
        return json({"code": 40002, "message": "customer_ids 不能为空"}, status=400)

    if not fields or not isinstance(fields, dict) or len(fields) == 0:
        return json({"code": 40003, "message": "fields 不能为空"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)
    current_user = get_current_user(request) or {}

    try:
        result = await service.batch_update_customers(
            customer_ids=customer_ids,
            fields=fields,
            current_user=current_user,
        )
    except ValueError as e:
        return json({"code": 40004, "message": str(e)}, status=400)
    except Exception as e:
        return json({"code": 50001, "message": f"批量更新失败: {str(e)}"}, status=500)

    return json(
        {
            "code": 0,
            "message": "批量更新完成",
            "data": {
                "success": True,
                "total": result["total"],
                "success_count": result["success_count"],
                "failed_count": result["failed_count"],
                "failed_list": result["failed_list"],
            },
        }
    )


@customers_bp.delete("/<customer_id:int>")
@auth_required
@require_permission("customers:delete")
async def delete_customer(request: Request, customer_id: int):
    """删除客户（软删除）"""
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    success = await service.delete_customer(customer_id)

    if not success:
        return json({"code": 40401, "message": "客户不存在"}, status=404)

    # 清除缓存
    await cache_service.invalidate_customer_cache(customer_id)

    return json({"code": 0, "message": "删除成功"})


@customers_bp.get("/<customer_id:int>/profile")
@auth_required
@require_permission("customers:view")
async def get_profile(request: Request, customer_id: int):
    """获取客户画像"""
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    # 先检查客户是否存在
    customer = await service.get_customer_by_id(customer_id)
    if not customer:
        return json({"code": 40401, "message": "客户不存在"}, status=404)

    profile = await service.get_customer_profile(customer_id)

    if not profile:
        return json({"code": 0, "message": "success", "data": None})

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": profile.id,
                "scale_level": profile.scale_level,
                "consume_level": profile.consume_level,
                "industry_type_id": profile.industry_type_id,
                "industry": profile.industry_type.name if profile.industry_type else None,
                "is_real_estate": customer.is_real_estate,
                "description": profile.description,
                "monthly_avg_shots": profile.monthly_avg_shots,
                "monthly_avg_shots_estimated": profile.monthly_avg_shots_estimated,
                "estimated_annual_spend": (
                    float(profile.estimated_annual_spend)
                    if profile.estimated_annual_spend is not None
                    else None
                ),
                "actual_annual_spend_2025": (
                    float(profile.actual_annual_spend_2025)
                    if profile.actual_annual_spend_2025 is not None
                    else None
                ),
            },
        }
    )


@customers_bp.put("/<customer_id:int>/profile")
@auth_required
@require_permission("customers:edit")
async def update_profile(request: Request, customer_id: int):
    """
    创建或更新客户画像

    Body:
    {
        "scale_level": "string (optional)",
        "consume_level": "string (optional)",
        "industry": "string (optional)",
        "is_real_estate": "boolean (optional)",
        "description": "string (optional)"
    }
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    # 先检查客户是否存在
    customer = await service.get_customer_by_id(customer_id)
    if not customer:
        return json({"code": 40401, "message": "客户不存在"}, status=404)

    profile = await service.create_or_update_profile(customer_id, request.json)

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {
                "id": profile.id,
                "scale_level": profile.scale_level,
                "consume_level": profile.consume_level,
                "industry_type_id": profile.industry_type_id,
                "industry": profile.industry_type.name if profile.industry_type else None,
                "is_real_estate": customer.is_real_estate,
                "description": profile.description,
                "monthly_avg_shots": profile.monthly_avg_shots,
                "monthly_avg_shots_estimated": profile.monthly_avg_shots_estimated,
                "estimated_annual_spend": (
                    float(profile.estimated_annual_spend)
                    if profile.estimated_annual_spend is not None
                    else None
                ),
                "actual_annual_spend_2025": (
                    float(profile.actual_annual_spend_2025)
                    if profile.actual_annual_spend_2025 is not None
                    else None
                ),
            },
        }
    )


@customers_bp.post("/import")
@auth_required
@require_permission("customers:import")
async def import_customers(request: Request):
    """
    Excel 批量导入客户

    Form:
    - file: Excel 文件 (.xlsx)

    Excel 列要求:
    - company_id (integer, required)
    - name (必填)
    - account_type (可选)
    - industry (可选)
    - price_policy (可选)
    - settlement_cycle (可选)
    - settlement_type (可选)
    - is_key_customer (可选，true/false)
    - email (可选)
    """
    files = request.files
    if "file" not in files:
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)

    excel_file = files["file"][0]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    try:
        # 读取 Excel 文件
        df = pd.read_excel(io.BytesIO(excel_file.body), engine="openpyxl")

        # 如果第 2 行是中文说明行（模板特征），跳过它
        if (
            len(df) > 0
            and isinstance(df.iloc[0].get("company_id"), (int, float, str))
            and str(df.iloc[0].get("company_id")) in ("必填", "可选")
        ):
            df = pd.read_excel(io.BytesIO(excel_file.body), engine="openpyxl", skiprows=[1])

        # 必填列检查
        required_columns = ["company_id", "name"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {
                    "code": 40003,
                    "message": f"Excel 缺少必填列：{', '.join(missing_columns)}",
                },
                status=400,
            )

        # 转换数据为字典列表
        customers_data = df.to_dict(orient="records")

        # 初始化错误列表
        errors = []

        # 处理 industry 列：将行业类型名称转换为 industry_type_id
        from sqlalchemy import select

        from ..models.industry_type import IndustryType

        db_session: AsyncSession = request.ctx.db_session
        industry_result = await db_session.execute(select(IndustryType))
        industry_map = {it.name: it.id for it in industry_result.scalars().all()}

        for row in customers_data:
            industry_name = row.get("industry")
            if industry_name:
                if industry_name not in industry_map:
                    errors.append(f"行业类型 '{industry_name}' 不存在")
                    continue
                row["industry_type_id"] = industry_map[industry_name]
                del row["industry"]

        # 处理 is_key_customer 列
        for row in customers_data:
            if "is_key_customer" in row:
                val = row["is_key_customer"]
                if isinstance(val, bool):
                    row["is_key_customer"] = val
                elif isinstance(val, str):
                    row["is_key_customer"] = val.lower() in ["true", "是", "1"]
                elif isinstance(val, float) and math.isnan(val):
                    # pandas 空单元格为 NaN，bool(NaN) = True，需特殊处理
                    row["is_key_customer"] = False
                else:
                    row["is_key_customer"] = bool(val) if val is not None else False

        db_session: AsyncSession = request.ctx.db_session
        service = CustomerService(db_session)

        success_count, errors = await service.batch_create_customers(customers_data)

        # 清除客户列表缓存
        await cache_service.invalidate_customer_cache()

        # 记录批量导入审计日志
        summary = build_batch_audit_summary(
            operation="customer_import",
            total_count=len(customers_data),
            success_count=success_count,
            failed_count=len(errors),
            details=errors[:10],
        )

        current_user = get_current_user(request)

        await create_audit_entry(
            db_session=db_session,
            user_id=current_user.get("user_id") if current_user else None,
            action="batch_create",
            module="customers",
            record_id=None,  # 批量操作
            record_type="customer",
            changes={"after": {"count": success_count}},
            operation_type="batch",
            extra_metadata=summary,
            ip_address=request.headers.get(
                "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
            ),
            auto_commit=False,
        )

        return json(
            {
                "code": 0,
                "message": "导入完成",
                "data": {
                    "success_count": success_count,
                    "error_count": len(errors),
                    "errors": errors[:10],  # 最多返回 10 条错误信息
                },
            }
        )

    except Exception as e:
        return json({"code": 50001, "message": f"导入失败：{str(e)}"}, status=500)


@customers_bp.get("/import-template")
@auth_required
async def download_import_template(request: Request):
    """下载 Excel 导入模板"""
    from openpyxl import Workbook

    # 创建 Excel 工作簿
    wb = Workbook()
    ws = wb.active
    ws.title = "客户导入模板"

    # 设置表头（纯英文列名，与 pd.read_excel 解析的列名一致）
    # 第二行添加中文说明作为提示
    headers = [
        "company_id",
        "name",
        "account_type",
        "industry",
        "price_policy",
        "settlement_type",
        "settlement_cycle",
        "is_key_customer",
        "email",
        "erp_system",
        "first_payment_date",
        "onboarding_date",
        "cooperation_status",
        "is_settlement_enabled",
        "is_disabled",
        "notes",
        "scale_level",
        "consume_level",
        "monthly_avg_shots",
        "monthly_avg_shots_estimated",
        "estimated_annual_spend",
        "actual_annual_spend_2025",
    ]
    ws.append(headers)

    # 添加中文说明行（不作为数据行，仅提示用户）
    notes = [
        "必填：唯一整数",
        "必填：客户名称",
        "可选：正式账号/客户测试账号/内部账号",
        "可选：行业类型",
        "可选：定价/阶梯/包年",
        "可选：prepaid=预付费, postpaid=后付费",
        "可选：daily=日结, weekly=周结, monthly=月结, quarterly=季结, yearly=年结",
        "可选：true/false",
        "可选：邮箱地址",
        "可选：所属 ERP 系统",
        "可选：YYYY-MM-DD 格式",
        "可选：YYYY-MM-DD 格式",
        "可选：active=合作中, suspended=暂停, terminated=终止, noused=近一年未使用",
        "可选：true/false",
        "可选：true/false",
        "可选：备注信息",
        "可选：S/A/B/C/D/E",
        "可选：C1/C2/C3/C4/C5/C6",
        "可选：整数",
        "可选：整数",
        "可选：金额",
        "可选：金额",
    ]
    ws.append(notes)

    # 设置列宽
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 25

    # 添加示例数据
    example_data = [
        100001,
        "示例公司",
        "正式账号",
        "房产经纪",
        "定价",
        "prepaid",
        "monthly",
        "true",
        "example@company.com",
        "易遨",
        "2024-01-15",
        "2024-02-01",
        "active",
        "true",
        "false",
        "备注示例",
        "C",
        "C2",
        500,
        450,
        50000.00,
        45000.00,
    ]
    ws.append(example_data)

    # 生成文件
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="客户导入模板.xlsx"'},
    )


@customers_bp.get("/export")
@auth_required
@require_permission("customers:export")
async def export_customers(request: Request):
    """
    Excel 导出客户列表

    Query:
    - keyword: 关键词
    - account_type: 账号类型
    - industry: 行业类型
    - manager_id: 运营经理 ID
    - settlement_type: 结算方式
    - is_key_customer: 是否重点客户
    """
    # 构建筛选条件
    filters = {
        "keyword": request.args.get("keyword"),
        "account_type": request.args.get("account_type"),
        "industry": request.args.get("industry"),
        "manager_id": (
            int(request.args.get("manager_id")) if request.args.get("manager_id") else None
        ),
        "settlement_type": request.args.get("settlement_type"),
    }

    is_key = request.args.get("is_key_customer")
    if is_key is not None:
        filters["is_key_customer"] = is_key.lower() == "true"

    is_real_estate = request.args.get("is_real_estate")
    if is_real_estate is not None:
        filters["is_real_estate"] = is_real_estate.lower() == "true"

    filters = {k: v for k, v in filters.items() if v is not None}

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    # 获取所有匹配的客户（不分页）
    customers, _ = await service.get_all_customers(page=1, page_size=10000, filters=filters)

    # 转换为 DataFrame
    data = []
    for c in customers:
        data.append(
            {
                # === 基础字段（9个） ===
                "company_id": c.company_id,
                "name": c.name,
                "account_type": c.account_type,
                "industry": (
                    c.profile.industry_type.name
                    if (c.profile and c.profile.industry_type)
                    else None
                ),
                "price_policy": convert_price_policy_to_display(c.price_policy),
                "settlement_type": convert_settlement_type_to_display(c.settlement_type),
                "settlement_cycle": convert_settlement_cycle_to_display(c.settlement_cycle),
                "is_key_customer": "是" if c.is_key_customer else "否",
                "email": c.email,
                # === 扩展字段（13个） ===
                "erp_system": c.erp_system,
                "first_payment_date": (
                    c.first_payment_date.strftime("%Y-%m-%d") if c.first_payment_date else None
                ),
                "onboarding_date": (
                    c.onboarding_date.strftime("%Y-%m-%d") if c.onboarding_date else None
                ),
                "cooperation_status": c.cooperation_status,
                "is_settlement_enabled": ("是" if c.is_settlement_enabled else "否")
                if c.is_settlement_enabled is not None
                else None,
                "is_disabled": ("是" if c.is_disabled else "否")
                if c.is_disabled is not None
                else None,
                "notes": c.notes,
                "scale_level": c.profile.scale_level if c.profile else None,
                "consume_level": c.profile.consume_level if c.profile else None,
                "monthly_avg_shots": c.profile.monthly_avg_shots if c.profile else None,
                "monthly_avg_shots_estimated": (
                    c.profile.monthly_avg_shots_estimated if c.profile else None
                ),
                "estimated_annual_spend": (
                    float(c.profile.estimated_annual_spend)
                    if (c.profile and c.profile.estimated_annual_spend)
                    else None
                ),
                "actual_annual_spend_2025": (
                    float(c.profile.actual_annual_spend_2025)
                    if (c.profile and c.profile.actual_annual_spend_2025)
                    else None
                ),
            }
        )

    df = pd.DataFrame(data)

    # 生成 Excel 文件
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="客户列表")

    output.seek(0)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"customers_{timestamp}.xlsx"

    # 返回文件
    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==================== 客户 360 摘要 ====================


@customers_bp.get("/<customer_id:int>/summary")
@auth_required
async def get_customer_summary(request: Request, customer_id: int):
    """获取客户 360 预览摘要数据"""

    from ..models.customers import Customer

    db: AsyncSession = request.ctx.db_session

    customer = await db.get(Customer, customer_id)
    if not customer:
        return json({"code": 404, "message": "Customer not found"}, status=404)

    service = CustomerService(db)
    # 使用现有服务获取客户健康度等数据
    await service.get_customer_detail(customer_id)

    # 格式化返回数据
    return json({
        "code": 0,
        "data": {
            "name": customer.name,
            "industry": customer.industry_type,
            "scale_level": customer.scale_level,
            "consume_level": customer.consume_level,
            "balance": f"¥{customer.balance:,.0f}" if hasattr(customer, "balance") else "N/A",
            "usage_30d": "N/A",
            "health": "—",
            "health_class": "",
            "forecast_days": "—",
            "recent_events": [],
        }
    })


@customers_bp.get("/<customer_id:int>/related")
@auth_required
async def get_related_customers(request: Request, customer_id: int):
    """获取关联客户推荐（同行业同规模）"""
    from sqlalchemy import select

    from ..models.customers import Customer

    db: AsyncSession = request.ctx.db_session

    customer = await db.get(Customer, customer_id)
    if not customer:
        return json({"code": 404, "message": "Customer not found"}, status=404)

    result = await db.execute(
        select(Customer)
        .where(
            Customer.id != customer_id,
            Customer.industry_type == customer.industry_type,
            Customer.scale_level == customer.scale_level,
        )
        .limit(4)
    )

    related = []
    for c in result.scalars():
        related.append({
            "id": c.id,
            "name": c.name,
            "industry": c.industry_type,
            "scale_level": c.scale_level,
            "health": "—",
        })

    return json({"code": 0, "data": related})


@customers_bp.get("/<customer_id:int>/balance-forecast")
@auth_required
async def get_balance_forecast(request: Request, customer_id: int):
    """余额耗尽预测"""

    from ..models.customers import Customer

    db: AsyncSession = request.ctx.db_session

    customer = await db.get(Customer, customer_id)
    if not customer:
        return json({"code": 404, "message": "Customer not found"}, status=404)

    # 简单预测：如果有余额和消耗数据，计算预计天数
    balance = getattr(customer, "balance", 0) or 0
    # 日均消耗暂时返回 0，需要消耗记录表来计算
    daily_avg = 0

    if daily_avg > 0:
        days_left = int(balance / daily_avg)
        status = "warning" if days_left <= 7 else "ok"
    else:
        days_left = None
        status = "safe"

    return json({
        "code": 0,
        "data": {
            "days_left": days_left,
            "daily_avg": daily_avg,
            "balance": balance,
            "status": status,
        }
    })


@customers_bp.post("/<customer_id:int>/follow-up")
@auth_required
async def create_follow_up(request: Request, customer_id: int):
    """创建客户跟进记录"""
    from ..models.customers import Customer

    db: AsyncSession = request.ctx.db_session

    customer = await db.get(Customer, customer_id)
    if not customer:
        return json({"code": 404, "message": "Customer not found"}, status=404)

    data = request.json or {}
    follow_up_type = data.get("type", "general")
    note = data.get("note", "")

    # 记录审计日志
    operator_id = request.ctx.user["user_id"]
    await create_audit_entry(
        db,
        operator_id=operator_id,
        action="customer_follow_up",
        resource_type="customer",
        resource_id=customer_id,
        detail={"type": follow_up_type, "note": note},
    )

    async with db.begin():
        pass  # audit entry already created

    return json({
        "code": 0,
        "message": "跟进记录已创建",
        "data": {"customer_id": customer_id, "type": follow_up_type, "note": note},
    })
