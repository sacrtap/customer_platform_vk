# 客户导入功能优化设计文档

**日期**: 2026-04-30
**状态**: 已确认
**涉及模块**: 客户管理 - 导入功能

---

## 一、需求概述

根据客户管理页面-客户详情页面涉及的【基础信息】和【画像信息】所有字段，全面优化导入功能的下载模板，并根据源数据（docs/data.xlsx）进行数据清洗，生成可用于导入的 data_clean.xlsx 文件。

---

## 二、导入模板字段设计

### 2.1 模板字段清单（23 个字段）

| 序号 | 字段名                      | 中文说明           | 必填 | 示例值           | 可选值说明                                              |
| ---- | --------------------------- | ------------------ | ---- | ---------------- | ------------------------------------------------------- |
| 1    | company_id                  | 公司 ID            | 必填 | 100001           | 唯一整数                                                |
| 2    | name                        | 客户名称           | 必填 | 某某公司         |                                                         |
| 3    | account_type                | 账号类型           | 可选 | 正式账号         | 正式账号/客户测试账号/内部账号                          |
| 4    | industry                    | 行业类型           | 可选 | 房产经纪         |                                                         |
| 5    | price_policy                | 计费模式           | 可选 | 定价             | 定价/阶梯/包年                                          |
| 6    | settlement_type             | 结算方式           | 可选 | prepaid          | prepaid=预付费, postpaid=后付费                         |
| 7    | settlement_cycle            | 结算周期           | 可选 | 月结             | 日结/周结/月结/季结                                     |
| 8    | is_key_customer             | 重点客户           | 可选 | true             | true/false                                              |
| 9    | email                       | 邮箱               | 可选 | test@example.com |                                                         |
| 10   | erp_system                  | 所属 ERP           | 可选 | 易遨             |                                                         |
| 11   | first_payment_date          | 首次回款时间       | 可选 | 2024-01-15       | YYYY-MM-DD 格式                                         |
| 12   | onboarding_date             | 接入时间           | 可选 | 2024-02-01       | YYYY-MM-DD 格式                                         |
| 13   | cooperation_status          | 合作状态           | 可选 | active           | active=合作中, suspended=暂停, terminated=终止, noused=近一年未使用 |
| 14   | is_settlement_enabled       | 是否结算           | 可选 | true             | true/false                                              |
| 15   | is_disabled                 | 是否停用           | 可选 | false            | true/false                                              |
| 16   | notes                       | 备注               | 可选 |                  |                                                         |
| 17   | scale_level                 | 规模等级           | 可选 | 500              | 100/500/1000/2000/5000                                  |
| 18   | consume_level               | 消费等级           | 可选 | A                | S/A/B/C/D/E                                             |
| 19   | monthly_avg_shots           | 月均拍摄量（实际） | 可选 | 500              | 整数                                                    |
| 20   | monthly_avg_shots_estimated | 月均拍摄量（测算） | 可选 | 450              | 整数                                                    |
| 21   | estimated_annual_spend      | 预估年消费         | 可选 | 50000            | 金额                                                    |
| 22   | actual_annual_spend_2025    | 25年实际消费       | 可选 | 45000            | 金额                                                    |

### 2.2 排除字段

- **manager_id**（运营经理）：关联 users 表，不放入导入模板
- **sales_manager_id**（商务经理）：关联 users 表，不放入导入模板

这两个字段通过客户详情编辑页面手动设置。

### 2.3 模板格式

- 第 1 行：英文字段名（列名）
- 第 2 行：中文说明 + 必填标记 + 可选值说明（同一单元格内）
- 第 3 行起：示例数据

---

## 三、数据清洗规则

### 3.1 字段映射表

| 源数据列           | 目标字段                    | 清洗规则                                                                              |
| ------------------ | --------------------------- | ------------------------------------------------------------------------------------- |
| 公司 id            | company_id                  | 直接映射，必填校验                                                                    |
| 公司名称           | name                        | 直接映射，必填校验                                                                    |
| 账号类型           | account_type                | 正式→正式账号，客户测试账号→客户测试账号，众趣内部→内部账号                           |
| 行业类型           | industry                    | 直接映射，"无"→空                                                                     |
| 结算方式           | price_policy                | 定价结算→定价，包年套餐→包年，包年限量套餐→包年，易遨结算→定价                        |
| 结算方式           | settlement_cycle            | 从结算方式列推断（定价结算→月结，包年套餐→年结）                                      |
| 结算方式           | settlement_type             | 统一设为 prepaid                                                                      |
| 客户等级           | is_key_customer             | S/A→true，其他→false                                                                  |
| 所属 ERP           | erp_system                  | 直接映射                                                                              |
| 首次回款时间       | first_payment_date          | 标准日期直接映射，非标准日期→空                                                       |
| 接入时间           | onboarding_date             | 文字描述（25上半年等）→原文追加到 notes                                               |
| 合作状态           | cooperation_status          | 正常使用→active，近一年未使用→noused，商务阶段→noused，待确认→noused，终止→terminated |
| 是否结算           | is_settlement_enabled       | 是→true，否→false                                                                     |
| 是否停用           | is_disabled                 | 是→true，否→false                                                                     |
| 备注               | notes                       | 直接映射，如有接入时间文字也追加                                                      |
| 客户消费等级       | consume_level               | C2→A, C3→B, C4→C, C5→D, C6→E, 0→空                                                    |
| 月均拍摄量         | monthly_avg_shots           | 整数映射，0→空                                                                        |
| 月均拍摄量（测算） | monthly_avg_shots_estimated | 整数映射，0→空                                                                        |
| 预估年消费         | estimated_annual_spend      | 金额映射，0/#VALUE!→空                                                                |
| 25年实际消费       | actual_annual_spend_2025    | 金额映射，0/#VALUE!→空                                                                |
| 客户等级           | scale_level                 | 不映射（客户等级≠规模等级）                                                           |

### 3.2 新增 cooperation_status 值

系统新增 `noused` 值，表示"近一年未使用"状态。

### 3.3 新增 consume_level 值

系统新增 `E` 选项，对应源数据中的 C6 等级。

---

## 四、代码变更清单

| 文件                                    | 变更内容                                                                                                              |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `backend/app/routes/customers.py`         | 修改 `download_import_template` 函数，更新模板字段列表和说明                                                            |
| `backend/app/services/customers.py`       | 1. 增加 `noused` 到 cooperation_status 映射；2. 增加消费等级 E 选项支持；3. 增加 price_policy/settlement_cycle 转换逻辑 |
| `backend/app/models/customers.py`         | cooperation_status 字段注释更新（增加 noused）                                                                        |
| `frontend/src/views/customers/Detail.vue` | 1. 消费等级选项增加 E；2. cooperation_status 展示增加 noused 映射                                                     |
| `backend/scripts/clean_import_data.py`    | 重写数据清洗脚本，按新映射规则处理                                                                                    |
| `docs/data_clean.xlsx`                    | 生成清洗后的数据文件                                                                                                  |

---

## 五、实现步骤

1. **更新后端模板**：修改 `download_import_template` 函数，包含 23 个字段及中文说明
2. **更新后端服务**：增加 cooperation_status `noused` 值处理、consume_level `E` 选项、price_policy 转换逻辑
3. **更新前端展示**：Detail.vue 中消费等级增加 E 选项，cooperation_status 增加 noused 映射
4. **重写数据清洗脚本**：按映射规则处理 docs/data.xlsx
5. **生成 data_clean.xlsx**：运行清洗脚本生成最终数据文件

---

## 六、验证要点

- [ ] 模板下载后包含 23 个字段，第 2 行有中文说明
- [ ] 导入功能能正确处理新增字段（price_policy, settlement_cycle, cooperation_status=noused, consume_level=E）
- [ ] data_clean.xlsx 中的数据格式符合导入模板要求
- [ ] 前端详情页能正确显示 noused 合作状态和 E 消费等级
