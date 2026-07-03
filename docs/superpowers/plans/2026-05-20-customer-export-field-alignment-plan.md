# 客户导出功能字段对齐计划

**创建日期**: 2026-05-20  
**目标**: 使客户管理页面的导出表格字段与导入模板字段完全一致  
**影响范围**: `backend/app/routes/customers.py` - `export_customers` 函数

---

## 背景分析

### 当前状态

**导入模板字段（22个）** — `download_import_template()` 第 667-690 行：
```
company_id, name, account_type, industry, price_policy, settlement_type,
settlement_cycle, is_key_customer, email, erp_system, first_payment_date,
onboarding_date, cooperation_status, is_settlement_enabled, is_disabled,
notes, scale_level, consume_level, monthly_avg_shots,
monthly_avg_shots_estimated, estimated_annual_spend, actual_annual_spend_2025
```

**导出功能字段（9个）** — `export_customers()` 第 804-819 行：
```
company_id, name, account_type, industry, price_policy, settlement_cycle,
settlement_type, is_key_customer, email
```

**缺失字段（13个）**：
| 序号 | 字段名                        | 数据源                        | 数据类型     |
| ---- | ----------------------------- | ----------------------------- | ------------ |
| 1    | erp_system                    | `c.erp_system`                | String       |
| 2    | first_payment_date            | `c.first_payment_date`        | Date         |
| 3    | onboarding_date               | `c.onboarding_date`           | Date         |
| 4    | cooperation_status            | `c.cooperation_status`        | String       |
| 5    | is_settlement_enabled         | `c.is_settlement_enabled`     | Boolean      |
| 6    | is_disabled                   | `c.is_disabled`               | Boolean      |
| 7    | notes                         | `c.notes`                     | Text         |
| 8    | scale_level                   | `c.profile.scale_level`       | String       |
| 9    | consume_level                 | `c.profile.consume_level`     | String       |
| 10   | monthly_avg_shots             | `c.profile.monthly_avg_shots` | Integer      |
| 11   | monthly_avg_shots_estimated   | `c.profile...`                | Integer      |
| 12   | estimated_annual_spend        | `c.profile...`                | Numeric      |
| 13   | actual_annual_spend_2025      | `c.profile...`                | Numeric      |

### 现有测试

`test_customers_api.py` 第 1108-1142 行已有字段一致性测试，但仅验证 9 个基础字段。需要更新测试以验证全部 22 个字段。

---

## 实施任务

### Task 1: 修改导出函数 - 添加缺失字段

**文件**: `backend/app/routes/customers.py`  
**位置**: `export_customers()` 函数，第 803-820 行

**修改内容**:

将数据字典从 9 个字段扩展为 22 个字段，保持与导入模板完全一致。

```python
# 原代码（第 804-819 行）：
data.append(
    {
        "company_id": c.company_id,
        "name": c.name,
        "account_type": c.account_type,
        "industry": (
            c.profile.industry_type.name
            if (c.profile and c.profile.industry_type)
            else None
        ),
        "price_policy": convert_price_policy_to_display(c.price_policy),
        "settlement_cycle": c.settlement_cycle,
        "settlement_type": convert_settlement_type_to_display(c.settlement_type),
        "is_key_customer": "是" if c.is_key_customer else "否",
        "email": c.email,
    }
)

# 修改为：
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
            c.first_payment_date.strftime("%Y-%m-%d")
            if c.first_payment_date else None
        ),
        "onboarding_date": (
            c.onboarding_date.strftime("%Y-%m-%d")
            if c.onboarding_date else None
        ),
        "cooperation_status": c.cooperation_status,
        "is_settlement_enabled": (
            "是" if c.is_settlement_enabled else "否"
        ) if c.is_settlement_enabled is not None else None,
        "is_disabled": (
            "是" if c.is_disabled else "否"
        ) if c.is_disabled is not None else None,
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
```

**关键注意事项**:
1. `settlement_cycle` 也需要使用 `convert_settlement_cycle_to_display()` 转换为中文显示
2. 所有关联字段（`c.profile.*`）需要安全访问，防止 `NoneType` 错误
3. 日期字段需要格式化为 `YYYY-MM-DD` 字符串
4. 布尔字段导出为"是"/"否"，与导入模板保持一致
5. 金额字段转换为 float，确保 Excel 中正确显示

---

### Task 2: 更新字段一致性测试

**文件**: `backend/tests/integration/test_customers_api.py`  
**位置**: `test_export_customers_field_consistency()` 函数，第 1108-1142 行

**修改内容**:

将 `template_headers` 从 9 个字段扩展为完整的 22 个字段：

```python
template_headers = [
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
```

---

### Task 3: 运行测试验证

**命令**:
```bash
cd backend && source .venv/bin/activate
pytest tests/integration/test_customers_api.py::test_export_customers_field_consistency -v
pytest tests/integration/test_customers_api.py::test_export_customers_success -v
pytest tests/integration/test_customers_api.py::test_download_import_template_field_structure -v
```

**预期结果**:
- 所有测试通过
- 导出文件包含完整的 22 个字段
- 字段顺序与导入模板一致

---

### Task 4: 代码格式检查

**命令**:
```bash
cd backend && source .venv/bin/activate
ruff check app/routes/customers.py
ruff format app/routes/customers.py --check
```

如有格式问题，运行：
```bash
ruff format app/routes/customers.py
```

---

## 验证清单

- [ ] 导出文件包含全部 22 个字段
- [ ] 字段顺序与导入模板一致
- [ ] 日期字段格式为 YYYY-MM-DD
- [ ] 布尔字段显示为"是"/"否"
- [ ] 枚举字段（price_policy, settlement_type, settlement_cycle）显示为中文
- [ ] 关联字段（profile.*）安全访问，无 NoneType 错误
- [ ] 所有测试通过
- [ ] 代码格式通过 ruff 检查

---

## 风险评估

| 风险项               | 概率 | 影响 | 缓解措施                              |
| -------------------- | ---- | ---- | ------------------------------------- |
| profile 为 None      | 中   | 高   | 所有关联字段使用条件表达式安全访问    |
| 旧数据缺少字段       | 低   | 低   | None 值在 Excel 中显示为空单元格      |
| 日期格式不一致       | 低   | 中   | 使用 strftime 统一格式化              |
| 测试数据集不完整     | 中   | 低   | 测试会使用 fixture 创建完整数据       |

---

## 后续优化建议（可选）

1. **导出文件名优化**: 将 `customers_{timestamp}.xlsx` 改为 `客户列表_{timestamp}.xlsx`，与导入模板命名风格一致
2. **字段顺序说明行**: 导出文件也可以添加类似导入模板的中文说明行（第二行），提升可读性
3. **列宽自适应**: 使用 openpyxl 设置更合理的列宽
