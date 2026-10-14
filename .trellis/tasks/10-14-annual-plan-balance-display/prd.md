# 包年套餐余额显示优化

## Goal

余额管理页面中，计费类型为「包年结算」（`PricingRule.pricing_type = 'package'`）的客户余额始终显示 ¥0.00，燃尽列异常（显示「已耗尽」或「无消耗」）。根因：余额页数据源是 `CustomerBalance.total_amount`（预付费现金池），而包年客户走「合同式预收费」——年费通过结算单一次性扣款，不进 `CustomerBalance`；包年实际可用额度在 `PricingRule.package_limits.base_fee − DailyConsumption.total_cost 累计` 独立链路中，余额页完全没有反映。

**目标**：余额页为包年客户计算并展示「套餐剩余额度 + 剩余次数」双值，燃尽列展示套餐到期剩余天数，余额范围筛选按剩余额度参与，过期套餐显示 ¥0 并标注「套餐已过期」。

## Requirements

### 用户确认的口径

| 维度 | 决策 |
|---|---|
| 余额口径 | **双值展示**：剩余额度（`base_fee − 累计已消耗`）+ 剩余次数（限量套餐：`limit_count − 累计订单量`；不限量套餐不显示次数） |
| 燃尽口径 | **到期剩余天数**：基于 `PricingRule.expiry_date` − 今天 |
| 过期处理 | 显示 ¥0 并标注「套餐已过期」灰色标签 |
| 筛选口径 | 包年客户按「剩余额度」参与余额范围筛选（balance_min/balance_max） |

### 功能清单

- [ ] 余额列表包含无 `CustomerBalance` 行的包年客户（改 Customer 驱动 + outerjoin）
- [ ] 每行输出包年字段：`price_policy` / `is_package` / `package_remaining_amount` / `package_remaining_count` / `package_base_fee` / `package_limit_count` / `package_is_unlimited` / `package_expired` / `package_expiry_date`
- [ ] 包年客户 `total_amount` 用 `package_remaining_amount` 覆盖（未过期），过期包年客户为 0
- [ ] 燃尽列：有效包年客户显示「剩余 N 天到期」进度条；过期包年客户显示「套餐已过期」灰标签；燃尽排序（days_remaining）按到期天数
- [ ] 余额范围筛选：包年客户按剩余额度参与（SQL 层 COALESCE，保证分页准确）
- [ ] KPI 统计：预付费总余额、余额不足客户数、即将耗尽客户数适配包年剩余额度/到期天数
- [ ] 导出 Excel 增加「套餐剩余额度（元）」「套餐剩余次数」「套餐到期日期」列（不限量显示「不限」）
- [ ] 前端余额列双值展示、燃尽列包年分支、`Balance` 类型扩展
- [ ] 现有定价/阶梯客户余额、燃尽、KPI 无回归

## Acceptance Criteria

- [ ] 包年客户（含无 CustomerBalance 行）出现在余额列表，返回 `package_remaining_amount`/`package_remaining_count`/`days_remaining`
- [ ] 限量包年客户余额列显示「额度 + 次数」两行；不限量显示「额度 + 不限量」标签；非包年客户保持「实充/赠送」展示
- [ ] 有效包年客户燃尽列显示「剩余 N 天到期」进度条；过期显示「套餐已过期」
- [ ] 「1 万以下」筛选按包年剩余额度命中
- [ ] KPI 卡片「预付费总余额 / 余额不足客户数 / 即将耗尽客户数」口径包含包年
- [ ] 导出 Excel 含包年三列
- [ ] 现有定价/阶梯客户无回归（列表、燃尽、KPI 与修改前一致）
- [ ] 单元测试覆盖 `_batch_query_package_info`、`_compute_burn_down` 包年分支、`_assemble_balance_rows` 包年字段

## 追加范围：跨页口径对齐（客户管理页）

余额管理页上线后，客户管理页（列表 / 详情 / 预览 / 余额预测 / 360 摘要 / 导出）仍读 `CustomerBalance.total_amount`，包年客户显示 ¥0 且健康度误判「高风险」，与余额管理页口径矛盾。

**目标**：抽出包年口径共享模块，客户管理页全部余额出口与余额管理页对齐。

### 功能清单（追加）

- [ ] 抽出共享模块 `app/services/package_balance.py`（`build_package_remaining_cte` / `batch_query_package_info` / `resolve_effective_balance`），`balances.py` 改为复用，消除两份口径
- [ ] 客户列表：`balance` 字段按包年口径（套餐剩余额度），`is_package` / `package_expired` 输出，`health` 按有效余额判定
- [ ] 客户列表：`sort_by=balance` 改用 `COALESCE(套餐剩余额度, CustomerBalance, 0)`
- [ ] 客户详情：`balance.total_amount` 按包年口径
- [ ] 余额预测接口：修复 `balance` 返回 ORM 对象（非数值）的 bug，并接入包年口径
- [ ] 360 摘要接口：修复既有 500（调用不存在的方法），余额文案按包年口径
- [ ] 前端：列表 / 预览 / 详情余额 Tab 文案按包年区分（「套餐剩余额度」+ 剩余次数/不限量/已过期）

### 功能清单（补充：开放平台出口）

- [ ] `GET /api/v1/balances`（全量）与 `GET /api/v1/erp/balances`（渠道）：`balance` 接入包年口径，包年客户返回套餐剩余额度（原本恒为 `0.0`）
- [ ] 余额优先级明确：白名单静态余额 > 包年剩余额度 > `total_amount − used_total`
- [ ] 同步更新 `openapi-docs` 两份接口文档的口径说明

### Acceptance Criteria（追加）

- [ ] 同一包年客户在余额管理页与客户管理页显示的余额一致（= 套餐剩余额度）
- [ ] 包年客户在客户列表中不再因 `CustomerBalance=0` 被判「高风险」
- [ ] `/balance-forecast` 返回数值型 `balance`；`/summary` 不再 500
- [ ] 非包年客户列表/详情/排序/健康度与改动前完全一致
- [ ] `/api/v1/balances` 与 `/api/v1/erp/balances` 对包年客户返回套餐剩余额度，与内部余额管理页一致（新乡暴风雨地产 = ¥2880.68）
- [ ] 开放平台接口对非包年客户口径不变；包年命中白名单时静态余额仍优先

## Notes

- 来源：`docs/specs/annual-plan-balance-display.md`（已确认方案）；跨页对齐为余额页上线后的延伸（见 `billing-balance-stats.md` 场景「客户管理页余额口径对齐」）。
- 假设与应对见 design.md（`pricing_rule_id` 关联、年费混合充值、反向关系等）。
