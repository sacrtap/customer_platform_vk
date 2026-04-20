# 客户数据导入功能扩展设计

**日期**: 2026-04-20

## 背景

`docs/data.xlsx` 包含 1338 行房产客户数据，36 列。现有导入功能仅支持 10 个字段，需要扩展以支持更多字段的数据导入。

## 数据源分析

| Excel 列名         | 目标表/字段                                | 映射规则                                   |
| ------------------ | ------------------------------------------ | ------------------------------------------ |
| 公司id             | Customer.company_id                        | 必填，整数                                 |
| 公司名称           | Customer.name                              | 必填                                       |
| 账号类型           | Customer.account_type                      | 正式→正式账号, 众趣内部→内部账号           |
| 行业类型           | CustomerProfile.industry                   | 直接导入                                   |
| 所属ERP            | Customer.erp_system                        | 直接导入                                   |
| 首次回款时间       | Customer.first_payment_date                | Excel 日期 → Python date                   |
| 接入时间           | Customer.onboarding_date                   | Excel 日期 → Python date                   |
| 客户等级           | Customer.customer_level                    | 直接导入 (S/A/B/C/D)                       |
| 合作状态           | Customer.cooperation_status                | 直接导入                                   |
| 是否结算           | Customer.is_settlement_enabled             | 是→True, 否→False                          |
| 是否停用           | Customer.is_disabled                       | 是→True, 否→False                          |
| 备注               | Customer.notes                             | 直接导入                                   |
| 结算方式           | Customer.settlement_type                   | 统一设为 prepaid                           |
| 客户消费等级       | CustomerProfile.consume_level              | 直接导入 (C2-C6)                           |
| 月均拍摄量         | CustomerProfile.monthly_avg_shots          | 整数                                       |
| 月均拍摄量（测算） | CustomerProfile.monthly_avg_shots_estimated| 整数                                       |
| 预估年消费         | CustomerProfile.estimated_annual_spend     | Decimal                                    |
| 25年实际消费       | CustomerProfile.actual_annual_spend_2025   | Decimal                                    |

**不导入的字段**: App配置, 销售负责人, 运营负责人, 单层/多层定价, 1-12月数量, 全年合计

## 设计方案

### 1. 后端：扩展 `batch_create_customers`

- 新增字段映射转换函数
- 支持 Customer 和 CustomerProfile 同时创建
- 处理 NaN/#N/A 值清洗

### 2. 后端：更新导入模板

- 增加新列到模板 headers
- 更新说明行和示例数据

### 3. 数据清洗

- 生成清洗后的 `docs/data_cleaned.xlsx`
- 验证数据质量
