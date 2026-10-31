"""行业类型管理路由"""

import asyncio
import logging
import math

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..middleware.auth import auth_required, require_permission
from ..models.industry_type import IndustryType
from ..services.industry_type_service import IndustryTypeService
from ..utils.excel_export import excel_response
from ..utils.excel_import import read_import_dataframe
from ..utils.excel_template import template_response

industry_type_bp = Blueprint("industry_types", url_prefix="/api/v1/industry-types")

logger = logging.getLogger(__name__)


@industry_type_bp.get("")
@auth_required
@require_permission("industry_types:manage")
async def get_industry_types(request: Request):
    """
    获取行业类型列表

    Response:
    - data: list of {id, name, sort_order, created_at}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    industry_types = await service.get_all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": it.id,
                    "name": it.name,
                    "sort_order": it.sort_order,
                    "created_at": it.created_at.isoformat() if it.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                }
                for it in industry_types
            ],
        }
    )


@industry_type_bp.post("")
@auth_required
@require_permission("industry_types:manage")
async def create_industry_type(request: Request):
    """
    新增行业类型

    Request Body:
    - name: str (required)
    - sort_order: int (required)
    - id: int (optional) 指定行业类型 ID；缺省自增。已被占用（含软删记录）时返回 409

    Response:
    - data: {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    data = request.json or {}
    name = data.get("name")
    sort_order = data.get("sort_order")
    id = data.get("id")

    if not name or sort_order is None:
        return json(
            {"code": 422, "message": "name 和 sort_order 为必填字段"},
            status=422,
        )

    # id 可选；提供时必须为正整数
    if id is not None and (not isinstance(id, int) or isinstance(id, bool) or id <= 0):
        return json(
            {"code": 422, "message": "id 必须为正整数"},
            status=422,
        )

    try:
        industry_type = await service.create(name, sort_order, id=id)

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": industry_type.id,
                    "name": industry_type.name,
                    "sort_order": industry_type.sort_order,
                },
            },
            status=201,
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )


@industry_type_bp.put("/<id:int>")
@auth_required
@require_permission("industry_types:manage")
async def update_industry_type(request: Request, id: int):
    """
    更新行业类型

    Request Body:
    - name: str (required)
    - sort_order: int (required)
    - id: int (optional) 新 ID；缺省保持不变。与当前 id 不同时执行主键修改，
      目标 id 已被占用（含软删记录）或行业正被客户引用时返回 409

    Response:
    - data: {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    data = request.json or {}
    name = data.get("name")
    sort_order = data.get("sort_order")
    new_id = data.get("id")

    if not name or sort_order is None:
        return json(
            {"code": 422, "message": "name 和 sort_order 为必填字段"},
            status=422,
        )

    # 新 id 可选；提供时必须为正整数
    if new_id is not None and (
        not isinstance(new_id, int) or isinstance(new_id, bool) or new_id <= 0
    ):
        return json(
            {"code": 422, "message": "id 必须为正整数"},
            status=422,
        )

    try:
        industry_type = await service.update(id, name, sort_order, new_id=new_id)

        if industry_type is None:
            return json(
                {"code": 404, "message": "行业类型不存在"},
                status=404,
            )

        # 审计由全局中间件 middleware/audit.py 自动记录（industry-types 已映射），
        # 此处不再手动写，避免每次更新产生两条审计日志。

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": industry_type.id,
                    "name": industry_type.name,
                    "sort_order": industry_type.sort_order,
                },
            }
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )
    finally:
        # 行业类型名称变更后，清除客户列表缓存
        await cache_service.invalidate_customer_cache()


@industry_type_bp.delete("/<id:int>")
@auth_required
@require_permission("industry_types:manage")
async def delete_industry_type(request: Request, id: int):
    """
    软删除行业类型

    Response:
    - success: true/false
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    try:
        success = await service.soft_delete(id)
    except ValueError as e:
        # 引用保护：被客户画像使用的行业禁止删除
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )

    if not success:
        return json(
            {"code": 404, "message": "行业类型不存在"},
            status=404,
        )

    # 审计由全局中间件 middleware/audit.py 自动记录（industry-types 已映射），
    # 此处不再手动写，避免每次删除产生两条审计日志。

    # 行业类型删除后，清除客户列表缓存
    await cache_service.invalidate_customer_cache()

    return json(
        {
            "code": 0,
            "message": "success",
        }
    )


# ==================== 行业类型导入导出 ====================


@industry_type_bp.get("/export")
@auth_required
@require_permission("industry_types:export")
async def export_industry_types(request: Request):
    """导出行业类型为 Excel（全量，上限 50000 条）"""
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    industry_types = await service.get_all()

    records = [{"name": t.name, "sort_order": t.sort_order} for t in industry_types]

    # openpyxl/pandas 生成 xlsx 为 CPU 密集操作，移到线程避免阻塞事件循环
    return await asyncio.to_thread(
        excel_response, records, "行业类型", "industry_types", len(records)
    )


@industry_type_bp.get("/import-template")
@auth_required
@require_permission("industry_types:import")
async def download_industry_type_import_template(request: Request):
    """下载行业类型导入 Excel 模板"""
    columns = [
        ("name", "必填：行业类型名称（≤50，不可重复），如 房产经纪"),
        ("sort_order", "可选：排序序号，缺省 0"),
    ]
    return await asyncio.to_thread(template_response, columns, "行业类型导入模板.xlsx")


@industry_type_bp.post("/import")
@auth_required
@require_permission("industry_types:import")
async def import_industry_types(request: Request):
    """Excel 批量导入行业类型

    Form:
    - file: Excel 文件 (.xlsx)

    Excel 列要求:
    - name (必填) - 行业类型名称（≤50，不可重复，含软删记录比对）
    - sort_order (可选) - 排序序号，缺省 0
    """
    files = request.files
    if "file" not in files:  # pyright: ignore[reportOperatorIssue]
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)

    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    try:
        # 读取 Excel（自动丢弃模板第 2 行中文说明行），保留原始索引标签供行号定位
        df = await asyncio.to_thread(read_import_dataframe, excel_file.body, "name")

        required = ["name"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return json(
                {"code": 40003, "message": f"Excel 缺少必填列：{', '.join(missing)}"},
                status=400,
            )

        db_session: AsyncSession = request.ctx.db_session

        # 查重含软删记录：name 唯一索引对软删记录仍生效，仅查未删除会漏掉占位
        # → INSERT 撞数据库唯一约束 → 500（与 create/update 含软删校验同源）
        existing_result = await db_session.execute(select(IndustryType.name))
        existing_names = set(existing_result.scalars().all())

        dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes", "on")

        valid_rows: list[dict] = []
        errors: list[str] = []
        for idx, row in df.iterrows():
            row_num = int(str(idx)) + 2  # Excel 行号（含表头，第 1 行数据 = 行 2）

            # 行业类型名称（必填）
            name_raw = row.get("name")
            if (
                name_raw is None
                or (isinstance(name_raw, float) and math.isnan(name_raw))
                or str(name_raw).strip() == ""
            ):
                errors.append(f"第 {row_num} 行：行业类型名称不能为空")
                continue
            name = str(name_raw).strip()

            if name in existing_names:
                errors.append(f"第 {row_num} 行：行业类型 '{name}' 已存在")
                continue

            # 排序序号（可选，缺省 0）
            sort_order = 0
            sort_raw = row.get("sort_order")
            if (
                sort_raw is not None
                and not (isinstance(sort_raw, float) and math.isnan(sort_raw))
                and str(sort_raw).strip() != ""
            ):
                try:
                    # 数值列按类型分支解析：混合空单元格的整数列会被 pandas 提升为
                    # float64，禁止 int(str(x))（"1.0" → ValueError）；float 先过
                    # is_integer() 守卫拒绝小数，int 透传，str 走 strip 后 int()
                    if isinstance(sort_raw, float):
                        if not sort_raw.is_integer():
                            errors.append(f"第 {row_num} 行：排序序号必须为整数")
                            continue
                        sort_order = int(sort_raw)
                    elif isinstance(sort_raw, int) and not isinstance(sort_raw, bool):
                        sort_order = int(sort_raw)
                    else:
                        sort_order = int(str(sort_raw).strip())
                except (ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：排序序号格式错误")
                    continue

            valid_rows.append({"name": name, "sort_order": sort_order})
            # 维护判重集合，保证批次内同名也报重复（预检查与真实导入去重一致）
            existing_names.add(name)

        # 预检查：返回校验结果，不落库、不动缓存（请求不产生任何副作用）
        if dry_run:
            return json(
                {
                    "code": 0,
                    "message": "预检查完成",
                    "data": {
                        "dry_run": True,
                        "success_count": len(valid_rows),
                        "error_count": len(errors),
                        "errors": errors[:50],
                    },
                }
            )

        # 预检阶段的只读查询已触发 autobegin 隐式事务，先 commit 断开，
        # 否则下方 begin() 抛 InvalidRequestError（SQLAlchemy 2.0 autobegin）
        await db_session.commit()

        async with db_session.begin():
            for rec in valid_rows:
                db_session.add(IndustryType(name=rec["name"], sort_order=rec["sort_order"]))

        # 行业类型变更影响客户列表行业列，清除缓存（与 create/update/delete 同模式）
        await cache_service.invalidate_customer_cache()

        return json(
            {
                "code": 0,
                "message": "导入完成",
                "data": {
                    "success_count": len(valid_rows),
                    "error_count": len(errors),
                    "errors": errors[:10],
                },
            }
        )
    except Exception:
        logger.exception("行业类型导入失败")
        return json({"code": 50001, "message": "导入失败，请稍后重试"}, status=500)
