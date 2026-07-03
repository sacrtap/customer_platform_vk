# 客户数据导入功能扩展实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展客户导入功能，支持从 `docs/data.xlsx` 导入 18+ 个字段到 Customer 和 CustomerProfile 表

**Architecture:** 在现有 `batch_create_customers` 方法上新增字段映射逻辑，同步更新导入模板和路由文档。数据清洗脚本生成验证后的 Excel 文件。

**Tech Stack:** Python 3.12, Sanic, SQLAlchemy 2.0, openpyxl, pandas

---

### Task 1: 新增字段映射转换函数

**Files:**
- Modify: `backend/app/services/customers.py`

- [ ] **Step 1: 在 `customers.py` 文件顶部（VALID_SETTLEMENT_TYPES 之后）添加新的映射常量和转换函数**

```python
# 账号类型映射：Excel 值 → 数据库存储值
ACCOUNT_TYPE_MAP = {
    "正式": "正式账号",
    "客户测试账号": "客户测试账号",
    "众趣内部": "内部账号",
}


def convert_account_type(value: Optional[str]) -> Optional[str]:
    """将 Excel 中的账号类型转换为数据库存储值"""
    if not value:
        return None
    return ACCOUNT_TYPE_MAP.get(str(value).strip(), str(value).strip())


def convert_bool_field(value) -> Optional[bool]:
    """将 Excel 中的是/否转换为布尔值"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    val = str(value).strip().lower()
    if val in ("是", "true", "1", "yes"):
        return True
    if val in ("否", "false", "0", "no"):
        return False
    return None


def convert_date_field(value) -> Optional[str]:
    """将 Excel 日期值转换为 YYYY-MM-DD 字符串"""
    if value is None:
        return None
    # 如果是 datetime 对象
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    # 如果是字符串，尝试解析
    val = str(value).strip()
    if not val or val in ("#N/A", "None", ""):
        return None
    # 尝试常见格式
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None  # 无法解析则返回 None
```

- [ ] **Step 2: 运行代码质量检查**

```bash
cd backend && source .venv/bin/activate && black app/services/customers.py && flake8 app/services/customers.py --max-line-length=120 --extend-ignore=E203
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/customers.py
git commit -m "feat: add field mapping functions for customer import extension"
```

---

### Task 2: 扩展 `batch_create_customers` 支持新字段

**Files:**
- Modify: `backend/app/services/customers.py` (batch_create_customers 方法)

- [ ] **Step 1: 修改 `batch_create_customers` 方法，添加新字段的 NaN 清洗和导入逻辑**

找到现有的 `optional_fields` 列表（约第 388 行），扩展为：

```python
                # Convert NaN to None for all optional fields
                optional_fields = [
                    "account_type",
                    "customer_level",
                    "industry",
                    "price_policy",
                    "settlement_cycle",
                    "settlement_type",
                    "email",
                    "erp_system",
                    "notes",
                    # 新增字段
                    "cooperation_status",
                    "is_settlement_enabled",
                    "is_disabled",
                    "first_payment_date",
                    "onboarding_date",
                    "consume_level",
                    "monthly_avg_shots",
                    "monthly_avg_shots_estimated",
                    "estimated_annual_spend",
                    "actual_annual_spend_2025",
                ]
                for field in optional_fields:
                    val = data.get(field)
                    if isinstance(val, float) and math.isnan(val):
                        data[field] = None
                    # 额外清洗 #N/A 字符串
                    if isinstance(val, str) and val.strip() == "#N/A":
                        data[field] = None
```

- [ ] **Step 2: 在 price_policy 转换逻辑之后、检查是否已存在之前，添加新字段的转换逻辑**

在 `storage_value = None` 之后（约第 439 行），添加：

```python
                # 转换账号类型
                account_type = data.get("account_type")
                data["account_type"] = convert_account_type(account_type)

                # 转换布尔字段
                data["is_settlement_enabled"] = convert_bool_field(
                    data.get("is_settlement_enabled")
                )
                data["is_disabled"] = convert_bool_field(data.get("is_disabled"))

                # 转换日期字段
                data["first_payment_date"] = convert_date_field(
                    data.get("first_payment_date")
                )
                data["onboarding_date"] = convert_date_field(
                    data.get("onboarding_date")
                )

                # 结算方式统一设为 prepaid
                if data.get("settlement_type") is None:
                    data["settlement_type"] = "prepaid"

                # 数值字段清洗（月均拍摄量等）
                for num_field in [
                    "monthly_avg_shots",
                    "monthly_avg_shots_estimated",
                ]:
                    val = data.get(num_field)
                    if val is not None:
                        try:
                            data[num_field] = int(float(str(val).strip()))
                        except (ValueError, TypeError):
                            data[num_field] = None

                # 金额字段清洗
                for money_field in [
                    "estimated_annual_spend",
                    "actual_annual_spend_2025",
                ]:
                    val = data.get(money_field)
                    if val is not None:
                        try:
                            data[money_field] = float(str(val).strip())
                        except (ValueError, TypeError):
                            data[money_field] = None
```

- [ ] **Step 3: 修改 Customer 创建逻辑，添加新字段**

找到 Customer 创建代码（约第 446 行），修改为：

```python
                customer = Customer(
                    company_id=company_id,
                    name=name,
                    account_type=data.get("account_type"),
                    customer_level=data.get("customer_level"),
                    price_policy=storage_value,
                    manager_id=data.get("manager_id"),
                    settlement_cycle=data.get("settlement_cycle"),
                    settlement_type=data.get("settlement_type"),
                    is_key_customer=data.get("is_key_customer", False),
                    email=data.get("email"),
                    # 新增字段
                    erp_system=data.get("erp_system"),
                    first_payment_date=data.get("first_payment_date"),
                    onboarding_date=data.get("onboarding_date"),
                    cooperation_status=data.get("cooperation_status"),
                    is_settlement_enabled=data.get("is_settlement_enabled"),
                    is_disabled=data.get("is_disabled"),
                    notes=data.get("notes"),
                )
```

- [ ] **Step 4: 在 Customer 创建后、添加 customer 到 db 之前，添加 Profile 创建逻辑**

在 `self.db.add(customer)` 之后（约第 459 行），添加：

```python
                existing_company_ids.add(company_id)  # 防止同批次重复

                # 如果提供了 profile 相关字段，创建 profile 记录
                profile_fields = {
                    "industry": data.get("industry"),
                    "consume_level": data.get("consume_level"),
                    "monthly_avg_shots": data.get("monthly_avg_shots"),
                    "monthly_avg_shots_estimated": data.get(
                        "monthly_avg_shots_estimated"
                    ),
                    "estimated_annual_spend": data.get("estimated_annual_spend"),
                    "actual_annual_spend_2025": data.get("actual_annual_spend_2025"),
                }
                # 如果至少有一个 profile 字段有值，则创建 profile
                if any(v is not None for v in profile_fields.values()):
                    profile = CustomerProfile(
                        customer_id=customer.id if customer.id else None,  # Will be set after flush
                        industry=profile_fields["industry"],
                        consume_level=profile_fields["consume_level"],
                        monthly_avg_shots=profile_fields["monthly_avg_shots"],
                        monthly_avg_shots_estimated=profile_fields[
                            "monthly_avg_shots_estimated"
                        ],
                        estimated_annual_spend=profile_fields["estimated_annual_spend"],
                        actual_annual_spend_2025=profile_fields[
                            "actual_annual_spend_2025"
                        ],
                    )
                    self.db.add(profile)
```

注意：由于 `customer.id` 在 flush 之前为 None，需要将 profile 创建移到 flush 之后。修改余额创建逻辑附近：

```python
        # 批量创建余额记录和 profile 关联
        if success_count > 0:
            await self.db.flush()
            new_customers = [c for c in self.db.new if isinstance(c, Customer)]
            balances = [CustomerBalance(customer_id=c.id) for c in new_customers]
            self.db.add_all(balances)
            
            # 关联 profile 到正确的 customer_id
            new_profiles = [p for p in self.db.new if isinstance(p, CustomerProfile)]
            # 通过 company_id 匹配
            company_id_to_customer = {
                c.company_id: c for c in new_customers
            }
            # 注意：上面的 profile 创建时 customer_id 为 None，需要重新设置
            # 这里需要修改上面的 profile 创建逻辑
```

**修正方案**：将 profile 创建移到 flush 之后。在 Customer 创建时不立即创建 profile，而是在 flush 后统一处理。

修改 Step 4 的逻辑为：在 Customer 创建时暂存 profile 数据，在 flush 后统一创建。

在 Customer 创建代码之前（约第 446 行之前），添加 profile 数据暂存：

```python
                # 暂存 profile 数据
                profile_data = None
                profile_fields = {
                    "industry": data.get("industry"),
                    "consume_level": data.get("consume_level"),
                    "monthly_avg_shots": data.get("monthly_avg_shots"),
                    "monthly_avg_shots_estimated": data.get(
                        "monthly_avg_shots_estimated"
                    ),
                    "estimated_annual_spend": data.get("estimated_annual_spend"),
                    "actual_annual_spend_2025": data.get("actual_annual_spend_2025"),
                }
                if any(v is not None for v in profile_fields.values()):
                    profile_data = profile_fields
```

在 `self.db.add(customer)` 之后：

```python
                # 暂存 profile 数据（等待 flush 后设置 customer_id）
                if profile_data:
                    if not hasattr(self, '_pending_profiles'):
                        self._pending_profiles = []
                    self._pending_profiles.append({
                        'data': profile_data,
                        'company_id': company_id,
                    })
```

在 flush 之后（约第 468 行），修改为：

```python
        # 批量创建余额记录和 profile
        if success_count > 0:
            await self.db.flush()
            new_customers = [c for c in self.db.new if isinstance(c, Customer)]
            balances = [CustomerBalance(customer_id=c.id) for c in new_customers]
            self.db.add_all(balances)

            # 创建 profile 记录
            if hasattr(self, '_pending_profiles'):
                company_id_to_id = {c.company_id: c.id for c in new_customers}
                for p_info in self._pending_profiles:
                    customer_id = company_id_to_id.get(p_info['company_id'])
                    if customer_id:
                        pd = p_info['data']
                        profile = CustomerProfile(
                            customer_id=customer_id,
                            industry=pd.get("industry"),
                            consume_level=pd.get("consume_level"),
                            monthly_avg_shots=pd.get("monthly_avg_shots"),
                            monthly_avg_shots_estimated=pd.get("monthly_avg_shots_estimated"),
                            estimated_annual_spend=pd.get("estimated_annual_spend"),
                            actual_annual_spend_2025=pd.get("actual_annual_spend_2025"),
                        )
                        self.db.add(profile)
                self._pending_profiles = []  # 清理
```

- [ ] **Step 5: 在方法开头初始化 pending_profiles**

在 `success_count = 0` 之前添加：

```python
        self._pending_profiles = []
```

- [ ] **Step 6: 运行代码质量检查**

```bash
cd backend && source .venv/bin/activate && black app/services/customers.py && flake8 app/services/customers.py --max-line-length=120 --extend-ignore=E203
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/customers.py
git commit -m "feat: extend batch_create_customers with new fields for import
- Add account_type, erp_system, dates, cooperation_status, boolean fields
- Add CustomerProfile fields: consume_level, monthly_shots, annual_spend
- Add field conversion functions for account type, booleans, dates
- Settlement type defaults to prepaid when not specified"
```

---

### Task 3: 更新导入模板

**Files:**
- Modify: `backend/app/routes/customers.py` (download_import_template 函数)

- [ ] **Step 1: 修改 headers 和 notes**

找到 headers 列表（约第 549 行），替换为：

```python
    headers = [
        "company_id",
        "name",
        "account_type",
        "industry",
        "customer_level",
        "price_policy",
        "settlement_cycle",
        "settlement_type",
        "is_key_customer",
        "email",
        # 新增字段
        "erp_system",
        "first_payment_date",
        "onboarding_date",
        "cooperation_status",
        "is_settlement_enabled",
        "is_disabled",
        "notes",
        "consume_level",
        "monthly_avg_shots",
        "monthly_avg_shots_estimated",
        "estimated_annual_spend",
        "actual_annual_spend_2025",
    ]
```

修改 notes 列表（约第 564 行）：

```python
    notes = [
        "必填",
        "必填",
        "可选：正式/客户测试账号/众趣内部",
        "可选",
        "可选：S/A/B/C/D",
        "可选：定价/阶梯/包年",
        "可选",
        "可选：默认prepaid",
        "可选：true/false",
        "可选",
        # 新增字段说明
        "可选",
        "可选：YYYY-MM-DD",
        "可选：YYYY-MM-DD",
        "可选",
        "可选：是/否",
        "可选：是/否",
        "可选",
        "可选：C2/C3/C4/C5/C6",
        "可选：整数",
        "可选：整数",
        "可选：金额",
        "可选：金额",
    ]
```

修改 example_data（约第 583 行）：

```python
    example_data = [
        1001,
        "示例公司 1",
        "正式",
        "项目",
        "KA",
        "定价",
        "月结",
        "prepaid",
        "false",
        "example@company.com",
        # 新增字段示例
        "某某ERP",
        "2024-01-15",
        "2024-02-01",
        "正常使用",
        "是",
        "否",
        "备注示例",
        "C3",
        500,
        450,
        50000.00,
        45000.00,
    ]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/customers.py
git commit -m "feat: update import template with new extended fields"
```

---

### Task 4: 数据清洗脚本

**Files:**
- Create: `backend/scripts/clean_import_data.py`
- Output: `docs/data_cleaned.xlsx`

- [ ] **Step 1: 创建数据清洗脚本**

```python
"""
数据清洗脚本：将 docs/data.xlsx 转换为符合导入模板格式的 clean 数据
输出: docs/data_cleaned.xlsx
"""
import openpyxl
from datetime import datetime

INPUT_FILE = "docs/data.xlsx"
OUTPUT_FILE = "docs/data_cleaned.xlsx"

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
        if val in ("#N/A", "None", ""):
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
        return "prepaid"  # 统一设为 prepaid
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
```

- [ ] **Step 2: 运行清洗脚本**

```bash
cd backend && source .venv/bin/activate && python scripts/clean_import_data.py
```

Expected: `清洗完成: XXX 行有效数据, YYY 行被跳过`

- [ ] **Step 3: 验证输出文件**

```bash
cd backend && source .venv/bin/activate && python -c "
import openpyxl
wb = openpyxl.load_workbook('docs/data_cleaned.xlsx')
ws = wb.active
print(f'Sheet: {ws.title}')
print(f'Headers: {[c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]}')
print(f'Total rows (including header+notes): {ws.max_row}')
print(f'Data rows: {ws.max_row - 2}')
print(f'Sample row 3: {[c.value for c in next(ws.iter_rows(min_row=3, max_row=3))]}')
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/clean_import_data.py docs/data_cleaned.xlsx
git commit -m "feat: add data cleaning script and generate cleaned import data"
```

---

### Task 5: 添加单元测试

**Files:**
- Create: `backend/tests/unit/test_import_field_mapping.py`

- [ ] **Step 1: 创建测试文件**

```python
"""测试导入字段映射转换函数"""
import pytest
from app.services.customers import (
    convert_account_type,
    convert_bool_field,
    convert_date_field,
)


class TestConvertAccountType:
    def test_formal_account(self):
        assert convert_account_type("正式") == "正式账号"

    def test_test_account(self):
        assert convert_account_type("客户测试账号") == "客户测试账号"

    def test_internal_account(self):
        assert convert_account_type("众趣内部") == "内部账号"

    def test_unknown_value_passthrough(self):
        assert convert_account_type("其他") == "其他"

    def test_none_value(self):
        assert convert_account_type(None) is None

    def test_whitespace_stripped(self):
        assert convert_account_type(" 正式 ") == "正式账号"


class TestConvertBoolField:
    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("是", True),
            ("否", False),
            ("true", True),
            ("false", False),
            ("1", True),
            ("0", False),
            (True, True),
            (False, False),
            (None, None),
            ("yes", True),
            ("no", False),
        ],
    )
    def test_bool_conversion(self, input_val, expected):
        assert convert_bool_field(input_val) == expected


class TestConvertDateField:
    def test_none_value(self):
        assert convert_date_field(None) is None

    def test_na_value(self):
        assert convert_date_field("#N/A") is None

    def test_date_format_yyyy_mm_dd(self):
        assert convert_date_field("2024-01-15") == "2024-01-15"

    def test_date_format_yyyy_mm_dd_slash(self):
        assert convert_date_field("2024/01/15") == "2024-01-15"

    def test_empty_string(self):
        assert convert_date_field("") is None
```

- [ ] **Step 2: 运行测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_import_field_mapping.py -v
```

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_import_field_mapping.py
git commit -m "test: add unit tests for import field mapping functions"
```

---

### Task 6: 运行完整测试验证

**Files:**
- Modify: 现有测试可能需要更新

- [ ] **Step 1: 运行所有客户相关测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_customer_service.py tests/unit/test_import_field_mapping.py tests/integration/test_customers_api.py -v --timeout=60
```

- [ ] **Step 2: 如果现有导入测试失败，更新测试数据以匹配新字段**

检查 `test_import_customers_success` 等测试是否需要更新 Excel 数据来包含新列。

- [ ] **Step 3: 运行覆盖率检查**

```bash
cd backend && source .venv/bin/activate && pytest --cov=app/services/customers --cov-report=term-missing
```

Expected: Coverage >= 50%

- [ ] **Step 4: 提交修复**

```bash
git add -A
git commit -m "fix: update existing tests for import field extension"
```

---

## 自审检查

1. **Spec 覆盖**: 所有 spec 中的字段映射规则都有对应的 Task 实现
2. **无占位符**: 每个 step 都有完整代码
3. **类型一致性**: 所有函数签名和类型注解一致
4. **测试覆盖**: 新增映射函数有完整单元测试
