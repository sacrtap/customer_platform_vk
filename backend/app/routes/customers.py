"""客户管理路由"""

from sanic import Blueprint
from sanic.response import json, file as response_file
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.customers import CustomerService
from ..cache.base import cache_service
from ..middleware.auth import auth_required, require_permission
import pandas as pd
import io
from datetime import datetime
import hashlib

customers_bp = Blueprint("customers", url_prefix="/api/v1/customers")


@customers_bp.get("")
@auth_required
@require_permission("customers:read")
async def list_customers(request: Request):
    """
    获取客户列表（支持筛选）

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    - keyword: 关键词（公司名称/公司 ID）
    - account_type: 账号类型
    - business_type: 业务类型
    - customer_level: 客户等级
    - manager_id: 运营经理 ID
    - settlement_type: 结算方式
    - is_key_customer: 是否重点客户 (true/false)
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    page_size = min(page_size, 100)

    # 构建筛选条件
    filters = {
        "keyword": request.args.get("keyword"),
        "account_type": request.args.get("account_type"),
        "business_type": request.args.get("business_type"),
        "customer_level": request.args.get("customer_level"),
        "manager_id": (
            int(request.args.get("manager_id", 0))
            if request.args.get("manager_id")
            else None
        ),
        "settlement_type": request.args.get("settlement_type"),
    }

    # 处理布尔值
    is_key = request.args.get("is_key_customer")
    if is_key is not None:
        filters["is_key_customer"] = is_key.lower() == "true"

    # 移除 None 值
    filters = {k: v for k, v in filters.items() if v is not None}

    # 尝试从缓存获取
    cache_key = f"p{page}_ps{page_size}_{hashlib.md5(str(sorted(filters.items())).encode()).hexdigest()[:8]}"
    cached = await cache_service.get("customer_list", cache_key)
    if cached is not None:
        return json(cached)

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    customers, total = await service.get_all_customers(
        page=page, page_size=page_size, filters=filters
    )

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
                    "business_type": c.business_type,
                    "customer_level": c.customer_level,
                    "price_policy": c.price_policy,
                    "manager_id": c.manager_id,
                    "settlement_cycle": c.settlement_cycle,
                    "settlement_type": c.settlement_type,
                    "is_key_customer": c.is_key_customer,
                    "email": c.email,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
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
@require_permission("customers:read")
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
        "business_type": customer.business_type,
        "customer_level": customer.customer_level,
        "price_policy": customer.price_policy,
        "manager_id": customer.manager_id,
        "settlement_cycle": customer.settlement_cycle,
        "settlement_type": customer.settlement_type,
        "is_key_customer": customer.is_key_customer,
        "email": customer.email,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
    }

    # 添加画像信息
    if customer.profile:
        data["profile"] = {
            "id": customer.profile.id,
            "scale_level": customer.profile.scale_level,
            "consume_level": customer.profile.consume_level,
            "industry": customer.profile.industry,
            "is_real_estate": customer.profile.is_real_estate,
            "description": customer.profile.description,
        }
    else:
        data["profile"] = None

    # 添加余额信息
    if customer.balance:
        data["balance"] = {
            "total_amount": (
                float(customer.balance.total_amount)
                if customer.balance.total_amount
                else 0
            ),
            "real_amount": (
                float(customer.balance.real_amount)
                if customer.balance.real_amount
                else 0
            ),
            "bonus_amount": (
                float(customer.balance.bonus_amount)
                if customer.balance.bonus_amount
                else 0
            ),
            "used_total": float(customer.balance.used_total)
            if customer.balance.used_total
            else 0,
            "used_real": float(customer.balance.used_real)
            if customer.balance.used_real
            else 0,
            "used_bonus": float(customer.balance.used_bonus)
            if customer.balance.used_bonus
            else 0,
        }
    else:
        data["balance"] = None

    result = {"code": 0, "message": "success", "data": data}

    # 写入缓存
    await cache_service.set("customer_detail", result, customer_id)

    return json(result)


@customers_bp.post("")
@auth_required
@require_permission("customers:write")
async def create_customer(request: Request):
    """
    创建客户

    Body:
    {
        "company_id": "string (required)",
        "name": "string (required)",
        "account_type": "string (optional)",
        "business_type": "string (optional)",
        "customer_level": "string (optional)",
        "price_policy": "string (optional)",
        "manager_id": "number (optional)",
        "settlement_cycle": "string (optional)",
        "settlement_type": "string (optional)",
        "is_key_customer": "boolean (optional)",
        "email": "string (optional)"
    }
    """
    data = request.json

    # 必填字段验证
    if not data.get("company_id") or not data.get("name"):
        return json(
            {"code": 40001, "message": "公司 ID 和客户名称不能为空"}, status=400
        )

    # 邮箱格式验证
    email = data.get("email")
    if email:
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return json({"code": 40002, "message": "邮箱格式不正确"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    try:
        customer = await service.create_customer(data)
    except ValueError as e:
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
@require_permission("customers:write")
async def update_customer(request: Request, customer_id: int):
    """
    更新客户信息

    Body:
    {
        "name": "string (optional)",
        "account_type": "string (optional)",
        "business_type": "string (optional)",
        "customer_level": "string (optional)",
        "price_policy": "string (optional)",
        "manager_id": "number (optional)",
        "settlement_cycle": "string (optional)",
        "settlement_type": "string (optional)",
        "is_key_customer": "boolean (optional)",
        "email": "string (optional)"
    }
    """
    data = request.json

    # 邮箱格式验证
    email = data.get("email")
    if email:
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return json({"code": 40002, "message": "邮箱格式不正确"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    customer = await service.update_customer(customer_id, data)

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
@require_permission("customers:read")
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
                "industry": profile.industry,
                "is_real_estate": profile.is_real_estate,
                "description": profile.description,
            },
        }
    )


@customers_bp.put("/<customer_id:int>/profile")
@auth_required
@require_permission("customers:write")
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
                "industry": profile.industry,
                "is_real_estate": profile.is_real_estate,
                "description": profile.description,
            },
        }
    )


@customers_bp.post("/import")
@auth_required
@require_permission("customers:write")
async def import_customers(request: Request):
    """
    Excel 批量导入客户

    Form:
    - file: Excel 文件 (.xlsx)

    Excel 列要求:
    - company_id (必填)
    - name (必填)
    - account_type (可选)
    - business_type (可选)
    - customer_level (可选)
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
            and isinstance(df.iloc[0].get("company_id"), str)
            and df.iloc[0].get("company_id") in ("必填", "可选")
        ):
            df = pd.read_excel(
                io.BytesIO(excel_file.body), engine="openpyxl", skiprows=[1]
            )

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

        # 处理 is_key_customer 列
        for row in customers_data:
            if "is_key_customer" in row:
                val = row["is_key_customer"]
                if isinstance(val, bool):
                    row["is_key_customer"] = val
                elif isinstance(val, str):
                    row["is_key_customer"] = val.lower() in ["true", "是", "1"]
                else:
                    row["is_key_customer"] = bool(val) if val is not None else False

        db_session: AsyncSession = request.ctx.db_session
        service = CustomerService(db_session)

        success_count, errors = await service.batch_create_customers(customers_data)

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
@require_permission("customers:write")
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
        "business_type",
        "customer_level",
        "price_policy",
        "settlement_cycle",
        "settlement_type",
        "is_key_customer",
        "email",
    ]
    ws.append(headers)

    # 添加中文说明行（不作为数据行，仅提示用户）
    notes = [
        "必填",
        "必填",
        "可选",
        "可选",
        "可选",
        "可选：定价/阶梯/包年",
        "可选",
        "可选：prepaid/postpaid",
        "可选：true/false",
        "可选",
    ]
    ws.append(notes)

    # 设置列宽
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 20

    # 添加示例数据
    example_data = [
        "COMP001",
        "示例公司 1",
        "正式账号",
        "A",
        "KA",
        "定价",
        "月结",
        "prepaid",
        "false",
        "example@company.com",
    ]
    ws.append(example_data)

    # 生成文件
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return await response_file(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="客户导入模板.xlsx"'},
    )


@customers_bp.get("/export")
@auth_required
@require_permission("customers:read")
async def export_customers(request: Request):
    """
    Excel 导出客户列表

    Query:
    - keyword: 关键词
    - account_type: 账号类型
    - business_type: 业务类型
    - customer_level: 客户等级
    - manager_id: 运营经理 ID
    - settlement_type: 结算方式
    - is_key_customer: 是否重点客户
    """
    # 构建筛选条件
    filters = {
        "keyword": request.args.get("keyword"),
        "account_type": request.args.get("account_type"),
        "business_type": request.args.get("business_type"),
        "customer_level": request.args.get("customer_level"),
        "manager_id": (
            int(request.args.get("manager_id"))
            if request.args.get("manager_id")
            else None
        ),
        "settlement_type": request.args.get("settlement_type"),
    }

    is_key = request.args.get("is_key_customer")
    if is_key is not None:
        filters["is_key_customer"] = is_key.lower() == "true"

    filters = {k: v for k, v in filters.items() if v is not None}

    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)

    # 获取所有匹配的客户（不分页）
    customers, _ = await service.get_all_customers(
        page=1, page_size=10000, filters=filters
    )

    # 转换为 DataFrame
    data = []
    for c in customers:
        data.append(
            {
                "company_id": c.company_id,
                "name": c.name,
                "account_type": c.account_type,
                "business_type": c.business_type,
                "customer_level": c.customer_level,
                "price_policy": c.price_policy,
                "settlement_cycle": c.settlement_cycle,
                "settlement_type": c.settlement_type,
                "is_key_customer": "是" if c.is_key_customer else "否",
                "email": c.email,
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
    return await response_file(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
