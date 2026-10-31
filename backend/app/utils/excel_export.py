"""Excel 批量导出的公共响应构造器"""

import io
from datetime import datetime

from sanic.response import json, raw

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# 导出上限：与客户/余额导出一致，超出截断并置 X-Truncated 响应头
EXPORT_LIMIT = 50000


def excel_response(
    records: list[dict],
    sheet_name: str,
    filename_prefix: str,
    total: int | None = None,
):
    """records → DataFrame → xlsx → raw 响应（GET /export 端点统一出口）。

    Args:
        records: 已按导出列构造的 dict 列表（列序即 dict 键序）
        sheet_name: 工作表名
        filename_prefix: 文件名前缀，实际文件名为 `{prefix}_{YYYYmmdd_HHMMSS}.xlsx`
        total: 匹配总数（service 返回值）；缺省时按 records 长度判断。
            传真实 total 才能正确判定截断——查询本身已按 page_size=50000 取回，
            records 长度恒 ≤ 50000，只用长度判断会漏报截断。

    Returns:
        空数据返回 40002（与余额导出一致，不下发空文件）；
        否则返回 xlsx raw 响应，截断时带 `X-Truncated: true` 响应头。
    """
    import pandas as pd

    if not records:
        return json({"code": 40002, "message": "没有找到符合条件的数据"}, status=400)

    matched = total if total is not None else len(records)
    truncated = matched > EXPORT_LIMIT
    df = pd.DataFrame(records[:EXPORT_LIMIT])

    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name=sheet_name, engine="openpyxl")  # pyright: ignore[reportArgumentType]  # pandas-stubs 的 WriteExcelBuffer 未含 BytesIO（运行时支持）
    output.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename_prefix}_{timestamp}.xlsx"',
        "X-Total-Count": str(matched),
        "X-Truncated": "true" if truncated else "false",
    }
    return raw(output.read(), content_type=XLSX_MIME, headers=headers)
