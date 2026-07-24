"""余额导入路由 — 导入和模板下载"""

import io

from openpyxl import Workbook
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...middleware.auth import auth_required, get_current_user, require_permission
from ...repository import BalanceRepository
from ...services.billing import BalanceService
from ...utils.audit_helpers import build_batch_audit_summary, create_audit_entry
from . import billing_bp


@billing_bp.post("/import")
@auth_required
@require_permission("billing:import")
async def import_balance(request: Request):
    """
    Excel 批量充值导入

    Form:
    - file: Excel 文件 (.xlsx)

    Excel 列要求:
    - company_id (integer, required) - 客户编号
    - real_amount (number >= 0, required) - 实充金额
    - bonus_amount (number >= 0, required) - 赠送金额
    - remark (text, optional) - 备注
    """

    import pandas as pd
    from sqlalchemy import select

    from ...models.customers import Customer

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
        required_columns = ["company_id", "real_amount", "bonus_amount"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {
                    "code": 40003,
                    "message": f"Excel 缺少必填列：{', '.join(missing_columns)}",
                },
                status=400,
            )

        # 行数限制
        if len(df) > 1000:
            return json(
                {"code": 40004, "message": "单次最多导入 1000 条记录"},
                status=400,
            )

        db_session: AsyncSession = request.ctx.db_session

        # 预加载所有客户 company_id -> customer_id 映射
        result = await db_session.execute(select(Customer.id, Customer.company_id))
        company_to_customer = {row[1]: row[0] for row in result.all()}

        # 逐行校验
        errors = []
        valid_rows = []

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel 行号（含表头）

            # 校验 company_id
            company_id = row.get("company_id")
            if pd.isna(company_id) or company_id is None:
                errors.append(f"第 {row_num} 行：客户编号为空")
                continue
            try:
                company_id = int(company_id)
            except (ValueError, TypeError):
                errors.append(f"第 {row_num} 行：客户编号 '{company_id}' 不是有效整数")
                continue

            if company_id not in company_to_customer:
                errors.append(f"第 {row_num} 行：客户编号 {company_id} 不存在")
                continue

            customer_id = company_to_customer[company_id]

            # 校验 real_amount
            real_amount = row.get("real_amount")
            if pd.isna(real_amount) or real_amount is None:
                real_amount = 0
            else:
                try:
                    real_amount = float(real_amount)
                    if real_amount < 0:
                        errors.append(f"第 {row_num} 行：实充金额不能为负数")
                        continue
                except (ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：实充金额格式错误")
                    continue

            # 校验 bonus_amount
            bonus_amount = row.get("bonus_amount")
            if pd.isna(bonus_amount) or bonus_amount is None:
                bonus_amount = 0
            else:
                try:
                    bonus_amount = float(bonus_amount)
                    if bonus_amount < 0:
                        errors.append(f"第 {row_num} 行：赠送金额不能为负数")
                        continue
                except (ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：赠送金额格式错误")
                    continue

            # 校验实充+赠送不能同时为 0
            if real_amount == 0 and bonus_amount == 0:
                errors.append(f"第 {row_num} 行：实充金额和赠送金额不能同时为 0")
                continue

            # 备注
            remark = row.get("remark")
            if pd.isna(remark) or remark is None:
                remark = None
            else:
                remark = str(remark)[:200]  # 截断到 200 字符

            valid_rows.append(
                {
                    "customer_id": customer_id,
                    "real_amount": real_amount,
                    "bonus_amount": bonus_amount,
                    "remark": remark,
                }
            )

        if not valid_rows:
            return json(
                {
                    "code": 0,
                    "message": "导入完成",
                    "data": {
                        "success_count": 0,
                        "error_count": len(errors),
                        "errors": errors[:10],
                    },
                }
            )

        # 执行批量充值
        current_user = get_current_user(request)
        operator_id = current_user.get("user_id") if current_user else 1

        service = BalanceService(BalanceRepository(db_session))
        success_count, batch_errors = await service.batch_import_recharge(
            rows=valid_rows,
            operator_id=operator_id,
        )
        errors.extend(batch_errors)

        # 清除缓存
        await cache_service.invalidate_analytics_cache("health")
        await cache_service.invalidate_analytics_cache("dashboard")

        # 记录审计日志
        summary = build_batch_audit_summary(
            operation="balance_import",
            total_count=len(df),
            success_count=success_count,
            failed_count=len(errors),
            details=errors[:10],
        )

        await create_audit_entry(
            db_session=db_session,
            user_id=operator_id,
            action="batch_recharge",
            module="billing",
            record_id=None,
            record_type="recharge",
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

    except Exception as e:
        return json({"code": 50001, "message": f"导入失败：{str(e)}"}, status=500)


@billing_bp.get("/import-template")
@auth_required
async def download_balance_import_template(request: Request):
    """下载余额导入 Excel 模板"""
    from sanic.response import raw

    wb = Workbook()
    ws = wb.active
    ws.title = "余额导入模板"

    # 表头
    headers = ["company_id", "real_amount", "bonus_amount", "remark"]
    ws.append(headers)

    # 中文说明行
    notes = [
        "必填：客户编号（整数）",
        "必填：实充金额（>=0）",
        "必填：赠送金额（>=0）",
        "可选：备注（最长200字符）",
    ]
    ws.append(notes)

    # 设置列宽
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 25

    # 示例数据
    ws.append([100001, 10000.00, 2000.00, "月初充值"])

    # 生成文件
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="余额导入模板.xlsx"'},
    )


# ==================== 包年套餐管理 ====================
