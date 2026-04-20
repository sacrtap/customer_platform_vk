"""
数据转换脚本：将 docs/data.xlsx 转换为系统导入模板格式
输出: docs/customer_import_20260417.xlsx
"""

import pandas as pd

# 源文件路径
SOURCE_FILE = "docs/data.xlsx"
OUTPUT_FILE = "docs/customer_import_20260417.xlsx"


# 字段映射函数
def map_account_type(value):
    """映射账号类型"""
    if pd.isna(value) or value is None:
        return ""
    mapping = {
        "正式": "正式账号",
        "客户测试账号": "测试账号",
        "众点内部": "内部账号",
    }
    return mapping.get(str(value).strip(), "")


def map_price_policy(value):
    """根据结算方式推断计费模式"""
    if pd.isna(value) or value is None:
        return ""
    val = str(value).strip()
    mapping = {
        "定价结算": "定价",
        "易遨结算": "定价",
        "包年套餐": "包年",
        "包年限量套餐": "包年",
    }
    return mapping.get(val, "")


def map_settlement_cycle(value):
    """映射结算周期"""
    if pd.isna(value) or value is None:
        return ""
    val = str(value).strip()
    if val in ["#N/A", "待确认", "0", "None", "nan"]:
        return ""
    return val


def map_is_key_customer(value):
    """根据客户消费等级推断是否重点客户"""
    if pd.isna(value) or value is None:
        return False
    val = str(value).strip()
    # C2 = A 级（重点客户）
    return val == "C2"


def clean_value(value):
    """清理值：#N/A, None, NaN → 空"""
    if pd.isna(value) or value is None:
        return ""
    val = str(value).strip()
    if val in ["#N/A", "None", "nan"]:
        return ""
    return val


# 读取源数据
print(f"读取源数据: {SOURCE_FILE}")
df_source = pd.read_excel(SOURCE_FILE, sheet_name="房产客户分月用量1225（L）")

print(f"源数据行数: {len(df_source)}")
print(f"源数据列数: {len(df_source.columns)}")

# 转换数据
converted_data = []

for _, row in df_source.iterrows():
    converted_data.append(
        {
            "company_id": int(row["公司id"]) if not pd.isna(row["公司id"]) else None,
            "name": clean_value(row["公司名称"]),
            "account_type": map_account_type(row["账号类型"]),
            "industry": clean_value(row["行业类型"]),
            "price_policy": map_price_policy(row["结算方式"]),
            "settlement_cycle": map_settlement_cycle(row["结算方式"]),
            "settlement_type": "prepaid",
            "is_key_customer": map_is_key_customer(row["客户消费等级"]),
            "email": "",
        }
    )

# 创建输出 DataFrame
df_output = pd.DataFrame(converted_data)

# 验证
print("\n=== 验证 ===")
print(f"输出行数: {len(df_output)}")
print(f"输出列数: {len(df_output.columns)}")

# 检查必填字段
null_company_id = df_output["company_id"].isna().sum()
null_name = df_output["name"].eq("").sum()
print(f"空 company_id: {null_company_id}")
print(f"空 name: {null_name}")

# 检查枚举值
valid_price_policies = {"定价", "阶梯", "包年", ""}
actual_policies = set(df_output["price_policy"].unique())
invalid_policies = actual_policies - valid_price_policies
if invalid_policies:
    print(f"警告：发现无效的 price_policy 值: {invalid_policies}")

# 保存文件
print(f"\n保存到: {OUTPUT_FILE}")
df_output.to_excel(OUTPUT_FILE, index=False, sheet_name="客户导入模板")

print("转换完成！")
print(f"输出文件: {OUTPUT_FILE}")
