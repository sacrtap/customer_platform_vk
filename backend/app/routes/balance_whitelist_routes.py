"""余额白名单管理路由"""

import asyncio
import logging
import math
from decimal import Decimal, InvalidOperation

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ErrorCodes
from ..middleware.auth import auth_required, require_permission
from ..models.balance_whitelist import BalanceWhitelist
from ..models.customers import Customer
from ..services.balance_whitelist_service import BalanceWhitelistService
from ..utils.excel_export import excel_response
from ..utils.excel_import import read_import_dataframe
from ..utils.excel_template import template_response

logger = logging.getLogger(__name__)

balance_whitelist_bp = Blueprint("balance_whitelists", url_prefix="/api/v1/balance-whitelists")


def _parse_balance(value) -> Decimal:
    """解析静态余额（前端可能传 number 或 string）"""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("静态余额格式不正确")


@balance_whitelist_bp.get("")
@auth_required
@require_permission("balance_whitelist:manage")
async def list_balance_whitelists(request: Request):
    """
    获取余额白名单列表（分页）

    Query:
    - page: int (default 1)
    - page_size: int (default 20)
    - keyword: 客户名称模糊 / 公司 ID 精确过滤
    """
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    page = max(int(request.args.get("page", "1")), 1)
    page_size = int(request.args.get("page_size", "20"))
    keyword = request.args.get("keyword")

    items, total = await service.get_all(page=page, page_size=page_size, keyword=keyword)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {"items": items, "total": total},
            "meta": {"page": page, "page_size": page_size, "total": total},
        }
    )


# ==================== Excel 批量导入 / 导出 ====================


@balance_whitelist_bp.get("/export")
@auth_required
@require_permission("balance_whitelist:export")
async def export_balance_whitelist(request: Request):
    """Excel 导出余额白名单（按 keyword 过滤，上限 5 万条）"""
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    keyword = request.args.get("keyword")
    items, total = await service.get_all(page=1, page_size=50000, keyword=keyword)

    records = [
        {
            "id": d["id"],
            "company_id": d["company_id"],
            "customer_name": d["customer_name"],
            "erp_system": d["erp_system"],
            "static_balance": d["static_balance"],
            "remark": d["remark"],
            "created_at": d["created_at"],
        }
        for d in items
    ]
    return await asyncio.to_thread(
        excel_response, records, "余额白名单", "balance_whitelist", total
    )


@balance_whitelist_bp.get("/import-template")
@auth_required
@require_permission("balance_whitelist:import")
async def download_balance_whitelist_template(request: Request):
    """下载余额白名单导入 Excel 模板"""
    columns = [
        ("company_id", "必填：客户编号（整数）"),
        ("static_balance", "可选：静态余额，缺省 1000"),
        ("remark", "可选：备注"),
    ]
    return await asyncio.to_thread(template_response, columns, "余额白名单导入模板.xlsx")


@balance_whitelist_bp.post("/import")
@auth_required
@require_permission("balance_whitelist:import")
async def import_balance_whitelist(request: Request):
    """
    Excel 批量导入余额白名单

    Form:
    - file: Excel 文件 (.xlsx)

    Excel 列要求:
    - company_id (必填) - 客户编号（与 Customer.company_id 对应）
    - static_balance (可选) - 静态余额，缺省 1000
    - remark (可选) - 备注

    Query:
    - dry_run: true/1/yes/on 时仅预检查（行级校验不落库），供前端二次确认
    """

    files = request.files
    if "file" not in files:  # pyright: ignore[reportOperatorIssue]
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)

    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    db_session: AsyncSession = request.ctx.db_session

    try:
        # 读取 Excel（自动丢弃模板第 2 行说明行）；同步 CPU 密集，移到线程避免阻塞事件循环
        df = await asyncio.to_thread(read_import_dataframe, excel_file.body, "company_id")

        # 必填列检查
        required_columns = ["company_id"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {"code": 40003, "message": f"Excel 缺少必填列：{', '.join(missing_columns)}"},
                status=400,
            )

        # 空文件（仅表头）直接拒绝，避免虚假的导入成功反馈
        if df.empty:
            return json(
                {"code": 40003, "message": "文件中没有可导入的数据"},
                status=400,
            )

        dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes", "on")

        records = df.to_dict(orient="records")
        for rec, idx in zip(records, df.index):
            rec["_row_num"] = int(idx) + 2  # 真实 Excel 行号（含表头 + 说明行）

        # ---- 行级预检（事务外只读查询，避免 N+1）----

        # 批量解析本批所有 company_id 取值（去空、去 NaN），用于一次性查客户映射与查重
        raw_company_ids: list = []
        for rec in records:
            v = rec.get("company_id")
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            raw_company_ids.append(v)

        # 解析为整数集合（pandas 会把带空单元格的整数列提升为 float64，须按类型分支，
        # 禁止 int(str(x))：str(1001.0)="1001.0" 会抛 ValueError，详见 import-export 规范）
        parsed_company_ids: set[int] = set()
        for v in raw_company_ids:
            try:
                if isinstance(v, float):
                    if not v.is_integer():
                        continue  # 非整数行由行级循环报错
                    parsed_company_ids.add(int(v))
                elif isinstance(v, int):
                    parsed_company_ids.add(v)
                else:
                    parsed_company_ids.add(int(str(v).strip()))
            except (ValueError, TypeError):
                continue  # 无法解析的由行级循环报错

        # 一次性查有效客户 company_id -> customer.id 映射（排除软删除客户，
        # 与列表/导出口径一致；软删客户不可在页面选择，导入若命中会形成不可见脏数据）
        company_to_customer: dict[int, int] = {}
        if parsed_company_ids:
            cust_result = await db_session.execute(
                select(Customer.id, Customer.company_id).where(
                    Customer.company_id.in_(parsed_company_ids),
                    Customer.deleted_at.is_(None),
                )
            )
            for cid, comp_id in cust_result.all():
                company_to_customer[comp_id] = cid

        # 查重：含软删记录（唯一索引对软删记录仍生效，漏查会撞约束 500）
        existing_customer_ids: set[int] = set()
        if company_to_customer:
            dup_result = await db_session.execute(
                select(BalanceWhitelist.customer_id).where(
                    BalanceWhitelist.customer_id.in_(company_to_customer.values())
                )
            )
            existing_customer_ids = set(dup_result.scalars().all())

        errors: list[str] = []
        valid_rows: list[tuple[int, Decimal | None, str | None]] = []
        for rec in records:
            row_num = rec["_row_num"]
            try:
                # company_id 解析
                raw = rec.get("company_id")
                if (
                    raw is None
                    or (isinstance(raw, float) and math.isnan(raw))
                    or str(raw).strip() == ""
                ):
                    errors.append(f"第 {row_num} 行：客户编号不能为空")
                    continue
                # 按类型分支解析（禁止 int(str(x))，详见 import-export 规范）
                if isinstance(raw, float):
                    if not raw.is_integer():
                        errors.append(f"第 {row_num} 行：客户编号 '{raw}' 不是有效整数")
                        continue
                    company_id = int(raw)
                elif isinstance(raw, int):
                    company_id = raw
                else:
                    s = str(raw).strip()
                    try:
                        company_id = int(s)
                    except (ValueError, TypeError):
                        errors.append(f"第 {row_num} 行：客户编号 '{raw}' 不是有效整数")
                        continue

                if company_id not in company_to_customer:
                    errors.append(f"第 {row_num} 行：客户编号 '{company_id}' 不存在")
                    continue

                customer_id = company_to_customer[company_id]

                # 查重（含软删记录）
                if customer_id in existing_customer_ids:
                    errors.append(f"第 {row_num} 行：客户 '{company_id}' 已在余额白名单中")
                    continue

                # static_balance（可选，缺省 1000）
                static_balance: Decimal | None = None
                sb_raw = rec.get("static_balance")
                if (
                    sb_raw is not None
                    and not (isinstance(sb_raw, float) and math.isnan(sb_raw))
                    and str(sb_raw).strip() != ""
                ):
                    try:
                        static_balance = Decimal(str(sb_raw))
                        if not static_balance.is_finite():
                            errors.append(f"第 {row_num} 行：静态余额格式错误")
                            continue
                    except (ValueError, TypeError, InvalidOperation):
                        errors.append(f"第 {row_num} 行：静态余额格式错误")
                        continue

                # remark（可选）
                remark_raw = rec.get("remark")
                if (
                    remark_raw is None
                    or (isinstance(remark_raw, float) and math.isnan(remark_raw))
                    or str(remark_raw).strip() == ""
                ):
                    remark = None
                else:
                    remark = str(remark_raw).strip()
                    if len(remark) > 200:
                        errors.append(f"第 {row_num} 行：备注长度不能超过 200 字符")
                        continue

                valid_rows.append((customer_id, static_balance, remark))
            except Exception as e:  # 兜底，避免单行异常中断整个导入
                logger.warning("余额白名单导入第 %d 行失败: %s", row_num, e)
                errors.append(f"第 {row_num} 行：导入失败，请检查该行数据")

        # 预检查：返回校验结果，不落库、不写审计、不动缓存（请求不产生任何副作用）
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

        # 落库：路由层直接 db.add（不调 service.add，其内部自带 commit 会与
        # db_session.begin() 嵌套冲突）；逐行 begin_nested 隔离，单行 DB 错误只回滚该行
        async with db_session.begin():
            for customer_id, static_balance, remark in valid_rows:
                async with db_session.begin_nested():
                    db_session.add(
                        BalanceWhitelist(
                            customer_id=customer_id,
                            static_balance=static_balance
                            if static_balance is not None
                            else Decimal("1000.00"),
                            remark=remark,
                        )
                    )
                    await db_session.flush()

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
        logger.exception("余额白名单导入失败")
        return json({"code": 50001, "message": "导入失败，请稍后重试"}, status=500)


@balance_whitelist_bp.post("/batch-import")
@auth_required
@require_permission("balance_whitelist:manage")
async def batch_import_by_erp(request: Request):
    """
    按 ERP 名单批量导入该 ERP 下所有有效客户（幂等）

    Request Body:
    - erp_system_value: str (required) — ERP 系统存储值（如 "erp_cloud"）

    Query:
    - dry_run: 可选，true/1/yes/on 时仅预检（计算将导入/跳过数量，不落库），
      前端据此二次确认后真实导入

    Response:
    - data: {imported, skipped}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    data = request.json or {}
    erp_system_value = data.get("erp_system_value")
    if not erp_system_value or not str(erp_system_value).strip():
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "缺少必要参数: erp_system_value"},
            status=400,
        )

    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes", "on")

    try:
        imported, skipped = await service.batch_import_by_erp(
            str(erp_system_value).strip(), dry_run=dry_run
        )
    except ValueError as e:
        return json({"code": ErrorCodes.BAD_REQUEST, "message": str(e)}, status=400)

    return json(
        {
            "code": 0,
            "message": "预检查完成" if dry_run else "success",
            "data": {
                "dry_run": dry_run,
                "imported": imported,
                "skipped": skipped,
            },
        }
    )


@balance_whitelist_bp.post("")
@auth_required
@require_permission("balance_whitelist:manage")
async def add_balance_whitelist(request: Request):
    """
    单独添加单个客户到白名单

    Request Body:
    - customer_id: int (required) — 客户主键 id
    - static_balance: number (optional, default 1000) — 静态余额（元）
    """
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    data = request.json or {}
    customer_id = data.get("customer_id")
    if customer_id is None:
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "缺少必要参数: customer_id"},
            status=400,
        )

    static_balance_raw = data.get("static_balance", 1000)
    try:
        static_balance = _parse_balance(static_balance_raw)
    except ValueError as e:
        return json({"code": ErrorCodes.INVALID_FORMAT, "message": str(e)}, status=400)

    try:
        record = await service.add(int(customer_id), static_balance)
    except ValueError as e:
        return json({"code": ErrorCodes.BAD_REQUEST, "message": str(e)}, status=400)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": record.id,
                "customer_id": record.customer_id,
                "static_balance": float(record.static_balance),
            },
        },
        status=201,
    )


@balance_whitelist_bp.put("/<id:int>")
@auth_required
@require_permission("balance_whitelist:manage")
async def update_balance_whitelist(request: Request, id: int):
    """
    编辑白名单客户静态余额（可选更新备注）

    Request Body:
    - static_balance: number (required)
    - remark: string | null (optional) — 未提供时保持原备注；传空/null 清空备注
    """
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    data = request.json or {}
    static_balance_raw = data.get("static_balance")
    if static_balance_raw is None:
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "缺少必要参数: static_balance"},
            status=400,
        )

    try:
        static_balance = _parse_balance(static_balance_raw)
    except ValueError as e:
        return json({"code": ErrorCodes.INVALID_FORMAT, "message": str(e)}, status=400)

    remark_provided = "remark" in data
    remark_raw = data.get("remark")

    try:
        record = await service.update(
            id, static_balance, remark=remark_raw, remark_provided=remark_provided
        )
    except ValueError as e:
        return json({"code": ErrorCodes.BAD_REQUEST, "message": str(e)}, status=400)

    if record is None:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "白名单记录不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": record.id,
                "customer_id": record.customer_id,
                "static_balance": float(record.static_balance),
                "remark": record.remark,
            },
        }
    )


@balance_whitelist_bp.delete("/<id:int>")
@auth_required
@require_permission("balance_whitelist:manage")
async def remove_balance_whitelist(request: Request, id: int):
    """移出白名单（软删除）"""
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    success = await service.soft_delete(id)
    if not success:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "白名单记录不存在"}, status=404)

    return json({"code": 0, "message": "success"})
