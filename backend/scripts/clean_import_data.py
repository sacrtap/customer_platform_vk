"""
数据清洗脚本：将 docs/data.xlsx 转换为符合导入模板格式的 clean 数据
输出: docs/data_cleaned.xlsx
"""
import openpyxl
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = PROJECT_ROOT / "docs" / "data.xlsx"
OUTPUT_FILE = PROJECT_ROOT / "docs" / "data_cleaned.xlsx"

# 字段映射
FIELD_MAP = {
    "公司id": "company_id",
    "公司名称": "name",
    "账号类型": "account_type",
    "行业类型": "industry",
    "所属ERP": "erp_system",
    "首次回款时间": "first_payment_date",
    "接入时间": "onboarding_date",
    "客户等级": "customer_level",
    "合作状态": "cooperation_status",
    "是否结算": "is_settlement_enabled",
    "是否停用": "is_disabled",
    "备注": "notes",
    "结算方式": "settlement_type",
    "客户消费等级": "consume_level",
    "月均拍摄量": "monthly_avg_shots",
    "月均拍摄量（测算）": "monthly_avg_shots_estimated",
    "预估年消费": "estimated_annual_spend",
    "25年实际消费": "actual_annual_spend_2025",
}

ACCOUNT_TYPE_MAP = {
    "正式": "正式账号",
    "客户测试账号": "客户测试账号",
    "众趣内部": "内部账号",
}


def clean_value(val, field_name):
    """清洗单个值"""
    if val is None:
        return None
    if isinstance(val, str):
        val = val.strip()
        if val in ("#N/A", "#VALUE!", "None", ""):
            return None
    if field_name == "account_type":
        return ACCOUNT_TYPE_MAP.get(str(val), str(val))
    if field_name == "is_settlement_enabled":
        return "是" if str(val).lower() in ("是", "true", "1", "yes") else "否" if str(val).lower() in ("否", "false", "0", "no") else None
    if field_name == "is_disabled":
        return "是" if str(val).lower() in ("是", "true", "1", "yes") else "否" if str(val).lower() in ("否", "false", "0", "no") else None
    if field_name == "first_payment_date" or field_name == "onboarding_date":
        if hasattr(val, "strftime"):
            return val.strftime("%Y-%m-%d")
        return None
    if field_name == "settlement_type":
        return "prepaid"
    return val


def main():
    wb_in = openpyxl.load_workbook(INPUT_FILE, data_only=True)
    ws_in = wb_in.active

    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = "客户导入数据"

    # 写入表头
    output_headers = list(FIELD_MAP.values())
    ws_out.append(output_headers)

    # 添加说明行
    notes = ["必填"] * 2 + ["可选"] * (len(output_headers) - 2)
    ws_out.append(notes)

    # 读取输入数据（跳过表头和 Row 2）
    input_headers = [cell.value for cell in next(ws_in.iter_rows(min_row=1, max_row=1))]
    col_indices = {}
    for cn_name, en_name in FIELD_MAP.items():
        if cn_name in input_headers:
            col_indices[en_name] = input_headers.index(cn_name)

    cleaned_count = 0
    skipped = 0

    for row_idx, row in enumerate(ws_in.iter_rows(min_row=3, max_row=ws_in.max_row, values_only=True), 3):
        company_id = row[input_headers.index("公司id")] if "公司id" in input_headers else None
        name = row[input_headers.index("公司名称")] if "公司名称" in input_headers else None

        # 跳过无效行
        if company_id is None or (isinstance(company_id, float) and str(company_id) == "nan"):
            skipped += 1
            continue
        if name is None or (isinstance(name, float) and str(name) == "nan") or str(name).strip() == "":
            skipped += 1
            continue

        output_row = []
        for en_name in output_headers:
            if en_name not in col_indices:
                output_row.append(None)
                continue
            col_idx = col_indices[en_name]
            raw_val = row[col_idx] if col_idx < len(row) else None
            cleaned = clean_value(raw_val, en_name)
            output_row.append(cleaned)

        ws_out.append(output_row)
        cleaned_count += 1

    wb_out.save(OUTPUT_FILE)
    print(f"清洗完成: {cleaned_count} 行有效数据, {skipped} 行被跳过")
    print(f"输出文件: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
