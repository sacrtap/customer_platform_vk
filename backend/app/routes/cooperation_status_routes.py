"""合作状态管理路由"""

import asyncio
import logging
import math
from typing import Any

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..middleware.auth import auth_required, get_current_user, require_permission
from ..models.cooperation_status import CooperationStatus
from ..services.cooperation_status_service import CooperationStatusService
from ..utils.audit_helpers import build_batch_audit_summary, create_audit_entry
from ..utils.excel_export import excel_response
from ..utils.excel_import import read_import_dataframe
from ..utils.excel_template import template_response

logger = logging.getLogger(__name__)

cooperation_status_bp = Blueprint("cooperation_statuses", url_prefix="/api/v1/cooperation-statuses")


@cooperation_status_bp.get("")
@auth_required
async def get_cooperation_statuses(request: Request):
    """
    获取合作状态列表

    Response:
    - data: list of {id, name, value, sort_order, created_at}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    cooperation_statuses = await service.get_all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": cs.id,
                    "name": cs.name,
                    "value": cs.value,
                    "sort_order": cs.sort_order,
                    "created_at": cs.created_at.isoformat() if cs.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                }
                for cs in cooperation_statuses
            ],
        }
    )


@cooperation_status_bp.post("")
@auth_required
@require_permission("cooperation_statuses:manage")
async def create_cooperation_status(request: Request):
    """
    新增合作状态

    Request Body:
    - name: str (required) - 展示名称，如 "合作中"
    - value: str (required) - 存储值，如 "active"
    - sort_order: int (required)

    Response:
    - data: {id, name, value, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    data = request.json or {}
    name = data.get("name")
    value = data.get("value")
    sort_order = data.get("sort_order")

    if not name or not value or sort_order is None:
        return json(
            {"code": 422, "message": "name、value 和 sort_order 为必填字段"},
            status=422,
        )

    try:
        cooperation_status = await service.create(name, value, sort_order)

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": cooperation_status.id,
                    "name": cooperation_status.name,
                    "value": cooperation_status.value,
                    "sort_order": cooperation_status.sort_order,
                },
            },
            status=201,
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )


@cooperation_status_bp.put("/<id:int>")
@auth_required
@require_permission("cooperation_statuses:manage")
async def update_cooperation_status(request: Request, id: int):
    """
    更新合作状态

    Request Body:
    - name: str (required)
    - value: str (required)
    - sort_order: int (required)

    Response:
    - data: {id, name, value, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    data = request.json or {}
    name = data.get("name")
    value = data.get("value")
    sort_order = data.get("sort_order")

    if not name or not value or sort_order is None:
        return json(
            {"code": 422, "message": "name、value 和 sort_order 为必填字段"},
            status=422,
        )

    try:
        cooperation_status = await service.update(id, name, value, sort_order)

        if cooperation_status is None:
            return json(
                {"code": 404, "message": "合作状态不存在"},
                status=404,
            )

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": cooperation_status.id,
                    "name": cooperation_status.name,
                    "value": cooperation_status.value,
                    "sort_order": cooperation_status.sort_order,
                },
            }
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )
    finally:
        # 合作状态变更后，清除客户列表缓存
        await cache_service.invalidate_customer_cache()


@cooperation_status_bp.delete("/<id:int>")
@auth_required
@require_permission("cooperation_statuses:manage")
async def delete_cooperation_status(request: Request, id: int):
    """
    软删除合作状态

    Response:
    - success: true/false
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    success = await service.soft_delete(id)

    if not success:
        return json(
            {"code": 404, "message": "合作状态不存在"},
            status=404,
        )

    # 合作状态删除后，清除客户列表缓存
    await cache_service.invalidate_customer_cache()

    return json(
        {
            "code": 0,
            "message": "success",
        }
    )


# ==================== 合作状态导入导出 ====================


@cooperation_status_bp.get("/export")
@auth_required
@require_permission("cooperation_statuses:export")
async def export_cooperation_statuses(request: Request):
    """导出合作状态为 Excel（全量，上限 50000 条）"""
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    cooperation_statuses = await service.get_all()

    records = [
        {
            "name": cs.name,
            "value": cs.value,
            "sort_order": cs.sort_order,
        }
        for cs in cooperation_statuses
    ]

    return await asyncio.to_thread(
        excel_response, records, "合作状态", "cooperation_statuses", len(records)
    )


@cooperation_status_bp.get("/import-template")
@auth_required
@require_permission("cooperation_statuses:import")
async def download_cooperation_status_import_template(request: Request):
    """下载合作状态导入 Excel 模板"""
    columns = [
        ("name", "必填：合作状态展示名（≤50，不可重复），如 合作中"),
        ("value", "必填：合作状态存储值（不可重复），如 active"),
        ("sort_order", "可选：排序序号，缺省 0"),
    ]
    return await asyncio.to_thread(template_response, columns, "合作状态导入模板.xlsx")


@cooperation_status_bp.post("/import")
@auth_required
@require_permission("cooperation_statuses:import")
async def import_cooperation_statuses(request: Request):
    """
    Excel 批量导入合作状态

    Form:
    - file: Excel 文件 (.xlsx)

    Excel 列要求:
    - name (必填) - 合作状态展示名（≤50，不可重复）
    - value (必填) - 合作状态存储值（不可重复）
    - sort_order (可选) - 排序序号，缺省 0
    """
    files = request.files
    if "file" not in files:  # pyright: ignore[reportOperatorIssue]
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)

    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    try:
        # 读取 Excel 文件（自动丢弃模板第 2 行的中文说明行）。pd.read_excel 为 CPU+I/O
        # 密集操作，移到线程执行避免阻塞事件循环。
        df = await asyncio.to_thread(read_import_dataframe, excel_file.body, "name")

        # 必填列检查
        required_columns = ["name", "value"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {
                    "code": 40003,
                    "message": f"Excel 缺少必填列：{', '.join(missing_columns)}",
                },
                status=400,
            )

        db_session: AsyncSession = request.ctx.db_session

        # 预检查（dry_run=true）：完整行级校验但不落库、不写审计/缓存，返回可入库
        # 条数与错误明细（含行号），供前端二次确认后才真正导入（与客户/计费规则/
        # 套餐/余额/结算单导入预检查同模式）。
        dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes", "on")

        # 预加载已存在的 name / value（含软删除记录：唯一索引对软删记录仍生效，
        # 漏查会让 INSERT 撞唯一约束报 500）。
        existing_names_result = await db_session.execute(select(CooperationStatus.name))
        existing_names = set(existing_names_result.scalars().all())
        existing_values_result = await db_session.execute(select(CooperationStatus.value))
        existing_values = set(existing_values_result.scalars().all())

        current_user = get_current_user(request)
        operator_id = current_user.get("user_id") if current_user else 1

        # 逐行校验并创建
        errors: list[str] = []
        valid_rows: list[CooperationStatus] = []
        for idx, row in df.iterrows():
            # pandas-stubs 将 Series.get 的返回值推断为 Dtype，导致 pd.isna(...)
            # 误报；标注 Any 消除误报，不改变语义。
            row: Any = row
            row_num = int(str(idx)) + 2  # Excel 行号（含表头）
            try:
                # 名称
                name_raw = row.get("name")
                if (
                    name_raw is None
                    or (isinstance(name_raw, float) and math.isnan(name_raw))
                    or str(name_raw).strip() == ""
                ):
                    errors.append(f"第 {row_num} 行：合作状态名称不能为空")
                    continue
                name = str(name_raw).strip()
                if len(name) > 50:
                    errors.append(f"第 {row_num} 行：合作状态名称 '{name}' 超过 50 个字符")
                    continue

                # 存储值
                value_raw = row.get("value")
                if (
                    value_raw is None
                    or (isinstance(value_raw, float) and math.isnan(value_raw))
                    or str(value_raw).strip() == ""
                ):
                    errors.append(f"第 {row_num} 行：合作状态存储值不能为空")
                    continue
                value = str(value_raw).strip()

                # 查重（含软删记录）：按命中字段报告
                if name in existing_names:
                    errors.append(f"第 {row_num} 行：合作状态 '{name}' 已存在")
                    continue
                if value in existing_values:
                    errors.append(f"第 {row_num} 行：合作状态存储值 '{value}' 已存在")
                    continue

                # 排序序号（可选，缺省 0）
                sort_order = 0
                sort_order_raw = row.get("sort_order")
                if (
                    sort_order_raw is not None
                    and not (isinstance(sort_order_raw, float) and math.isnan(sort_order_raw))
                    and str(sort_order_raw).strip() != ""
                ):
                    try:
                        # pandas 把混合空单元格的整数列提升为 float64，禁止 int(str(x))：
                        # float 先过 is_integer() 守卫，int 透传，str strip 后 int()。
                        if isinstance(sort_order_raw, float):
                            if not sort_order_raw.is_integer():
                                errors.append(f"第 {row_num} 行：排序序号必须为整数")
                                continue
                            sort_order = int(sort_order_raw)
                        elif isinstance(sort_order_raw, int):
                            sort_order = sort_order_raw
                        else:
                            sort_order = int(str(sort_order_raw).strip())
                    except (ValueError, TypeError):
                        errors.append(f"第 {row_num} 行：排序序号格式错误")
                        continue

                status = CooperationStatus(
                    name=name,
                    value=value,
                    sort_order=sort_order,
                )
                # 预检查模式：校验完成即计成功，不落库
                if not dry_run:
                    # 行级 savepoint：flush 失败只回滚该行，不影响已成功行
                    async with db_session.begin_nested():
                        db_session.add(status)
                        await db_session.flush()
                # 预检查也维护已见集合，保证与真实导入的去重结果一致
                existing_names.add(name)
                existing_values.add(value)
                valid_rows.append(status)
            except Exception as e:  # 兜底，避免单行异常中断整个导入
                logger.warning("合作状态导入第 %d 行失败: %s", row_num, e)
                errors.append(f"第 {row_num} 行：{str(e)}")

        success_count = len(valid_rows)

        # 预检查：返回校验结果，不落库、不写审计、不动缓存。
        # 必须先于 commit/缓存失效/审计：dry_run 请求不应产生任何副作用。
        if dry_run:
            return json(
                {
                    "code": 0,
                    "message": "预检查完成",
                    "data": {
                        "dry_run": True,
                        "success_count": success_count,
                        "error_count": len(errors),
                        "errors": errors[:50],
                    },
                }
            )

        await db_session.commit()

        # 合作状态变更后，清除客户列表缓存
        await cache_service.invalidate_customer_cache()

        # 记录审计日志
        summary = build_batch_audit_summary(
            operation="cooperation_status_import",
            total_count=len(df),
            success_count=success_count,
            failed_count=len(errors),
            details=errors[:10],
        )

        await create_audit_entry(
            db_session=db_session,
            user_id=operator_id,
            action="batch_create",
            module="cooperation_statuses",
            record_id=None,
            record_type="cooperation_status",
            changes={"after": {"count": success_count}},
            operation_type="batch",
            extra_metadata=summary,
            ip_address=request.headers.get(
                "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
            ),
            auto_commit=True,
        )

        return json(
            {
                "code": 0,
                "message": "导入完成",
                "data": {
                    "success_count": success_count,
                    "error_count": len(errors),
                    "errors": errors[:10],
                },
            }
        )
    except Exception:
        # 外层失败（如最终 commit 或审计 commit 抛错）也需回滚，避免把 PendingRollback
        # 会话归还连接池
        logger.exception("合作状态导入失败")
        await request.ctx.db_session.rollback()
        return json({"code": 50001, "message": "导入失败，请稍后重试"}, status=500)
