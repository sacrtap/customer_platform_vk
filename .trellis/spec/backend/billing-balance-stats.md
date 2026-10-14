# Billing Balance Stats & Settlement Grouping

> 余额管理页 KPI 统计（`/billing/balance-stats`）与余额列表结算类型分组的跨层契约。

---

## Scenario: 余额总览按结算类型拆分

### 1. Scope / Trigger

- Trigger: 跨层请求/响应契约变更 —— `balance-stats` 响应字段重构，余额列表新增 `settlement_group` 参数。
- 背景：原先 `total_balance` 把预付费余额与后付费欠款（负数）混加，且「未设置结算类型」的客户（生产库实测约 12.7%）既不属于预付费筛选、也被 `!= 'postpaid'` 的 SQL 条件静默丢弃。现在统一约定：**未设置结算类型 = 预付费**。

### 2. Signatures

[来源: 项目源码 — `backend/app/routes/billing/balances.py`]

```python
# 分组条件（列表筛选与统计共用，唯一口径来源）
def _settlement_group_condition(group: str):
    if group == "postpaid":
        return Customer.settlement_type == "postpaid"
    return func.coalesce(Customer.settlement_type, "prepaid") != "postpaid"

GET /api/v1/billing/balance-stats?<与列表一致的筛选参数>   # 不接受 settlement_group
GET /api/v1/billing/balances?settlement_group=prepaid|postpaid
GET /api/v1/billing/balances/export?settlement_group=prepaid|postpaid
```

### 3. Contracts

请求字段（列表/导出共用 `_parse_balance_filters`）：

| 字段 | 类型 | 约束 |
|------|------|------|
| `settlement_group` | string | 可选，`prepaid` = 非后付费（含未设置），`postpaid` = 后付费；空串视为未传 |
| `settlement_type` | string | 可选，**严格等值**筛选（`prepaid`/`postpaid`），与 `settlement_group` 语义不同，两者可同时出现 |
| `is_settlement_enabled` | string | 可选，`true`/`false`；客户信息「是否结算」字段（列表与统计均支持） |
| `auto_initiate_settlement` | string | 可选，`true`/`false`；「自动发起结算」（列表/统计/导出均支持），**历史 NULL 视为「是」** |
| `is_disabled` | string | 可选，`true`/`false`；「是否停用」（列表/统计/导出均支持），**历史 NULL 视为未停用** |
| `erp_system` | string | 可选，ERP 系统 `value` 精确匹配；空串视为未传 |
| `cooperation_status` | string | 可选，合作状态 `value` 精确匹配；空串视为未传 |

> 上表后 4 项为「余额管理页第二排筛选项对齐客户管理页」新增，与客户管理页筛选语义一致
> （布尔项历史 NULL 兼容规则对齐 `backend/app/services/customers.py`）。

`balance-stats` 响应 `data` 字段：

| 字段 | 含义 |
|------|------|
| `total_balance_prepaid` | 预付费客户（含未设置）余额合计 |
| `prepaid_customers` | 预付费客户数（含未设置） |
| `total_balance_postpaid` | 后付费客户余额合计（负值 = 已消耗未回款） |
| `postpaid_customers` | 后付费客户数 |
| `postpaid_receivable` | 应收款（净）= `-total_balance_postpaid` |
| `this_month_count` / `this_month_amount` / `this_month_real_amount` / `this_month_bonus_amount` | 本月充值笔数与金额（实充 + 赠送） |
| `low_balance_count` | 余额 < 10000 的**预付费**客户数（含欠费/负余额） |
| `burning_soon_count` | `days_remaining ≤ 7` 的**预付费**客户数 |

已移除字段（前端 KPI 同步删除，勿再消费）：`total_balance`、`total_customers`、`zero_balance_count`。

前端联动：KPI 卡片点击 → `filters.settlement_group`（`prepaid`/`postpaid`）→ 列表查询带该参数；统计接口不接收该参数，两张卡片各自统计，因此卡片数字与列表条数一一对应。

### 4. Validation & Error Matrix

| 条件 | 结果 |
|------|------|
| `settlement_group` ∈ {`prepaid`, `postpaid`} | 正常过滤 |
| `settlement_group` 为空串 | 视为未传 |
| `settlement_group` 其他取值 | `400` + `code 40001`（message 含 `settlement_group`） |
| `auto_initiate_settlement` / `is_disabled` 非 `true`/`false` | `400` + `code 40001`（message 含对应字段名） |
| `erp_system` / `cooperation_status` 为空串 | 视为未传（不做校验） |
| 缺少 `billing:view` 权限 | `403`（由 `@require_permission` 处理） |

布尔筛选 NULL 兼容（`_bool_filter_condition`，语义对齐客户管理页）：

| 字段 | `=true` | `=false` |
|------|---------|----------|
| `auto_initiate_settlement`（默认「是」） | `列 IS TRUE OR IS NULL` | `列 IS FALSE` |
| `is_disabled`（默认否） | `列 IS TRUE` | `列 IS FALSE OR IS NULL` |

### 5. Good/Base/Bad Cases

- Good: `settlement_type IS NULL` 的客户余额计入 `total_balance_prepaid`，且 `settlement_group=prepaid` 能列出该客户。
- Base: 无后付费客户 → `total_balance_postpaid = 0`、`postpaid_receivable = 0`。
- Bad: 用 `Customer.settlement_type != "postpaid"` 表达「预付费」——SQL 三值逻辑会把 NULL 行整体丢弃（该写法曾让「即将耗尽」漏统计未设置结算类型的客户）。

### 6. Tests Required

[来源: `backend/tests/integration/test_billing_api.py`、`frontend/src/composables/__tests__/useBalance.test.ts`]

| 用例 | 断言点 |
|------|--------|
| `test_balance_stats_splits_prepaid_and_postpaid` | 预付费 5000 + 未设置 7000 → `total_balance_prepaid=12000`、`prepaid_customers=2`；后付费 -3000 → `postpaid_receivable=3000`；`low_balance_count=2`（后付费欠款不计入） |
| `test_balance_stats_burning_soon_includes_unset_settlement` | 未设置结算类型且预计 3.5 天耗尽 → `burning_soon_count=1`，同数据后付费客户不计入 |
| `test_get_balances_filter_settlement_group_prepaid_includes_unset` | 未设置结算类型客户出现在 `prepaid` 结果中，后付费客户不出现 |
| `test_get_balances_filter_settlement_group_postpaid` | 仅后付费客户命中 |
| `test_get_balances_filter_settlement_group_invalid` | `400` 且 message 含 `settlement_group` |
| `test_get_balances_filter_erp_system_and_cooperation_status` | `erp_system`/`cooperation_status` 精确匹配命中目标客户、排除其他；统计跟随筛选 |
| `test_get_balances_filter_auto_initiate_null_compat` | `=true` 命中 `True` 与 `NULL`、排除 `False`；`=false` 仅命中 `False`；非法值 `400` |
| `test_get_balances_filter_is_disabled_null_compat` | `=true` 仅命中 `True`；`=false` 命中 `False` 与 `NULL`、排除 `True` |
| `useBalance.test.ts`「结算类型分组筛选」 | 列表请求带 `settlement_group`；`getBalanceStats` 不带该参数且仍按默认筛选口径统计 |
| `useBalance.test.ts`「新增筛选项」 | 四个新字段默认值；列表/统计请求携带；导出参数布尔序列化为字符串；`handleReset` 清空 |

变异校验（防止断言空转）：把 `_settlement_group_condition("prepaid")` 换回 `!= "postpaid"`、或从 `low_balance_count` 去掉分组条件，上述前两条用例必须失败。

### 7. Wrong vs Correct

#### Wrong

```python
# 预付费卡片：NULL 客户被静默丢弃；且与列表筛选口径不一致
stmt = stmt.where(Customer.settlement_type != "postpaid")
```

#### Correct

```python
# 唯一口径来源，统计与列表筛选共用
stmt = stmt.where(_settlement_group_condition("prepaid"))   # coalesce(settlement_type,'prepaid') != 'postpaid'
```

---

## Scenario: 包年套餐客户的余额/燃尽/KPI 口径

### 1. Scope / Trigger

- Trigger: 跨层契约变更 —— 余额列表响应新增包年字段、余额范围筛选与排序口径改按「套餐剩余额度」、KPI 与导出同步。
- 背景：包年客户的年费只存在 `PricingRule.package_limits.base_fee`，**不写入 `CustomerBalance`**。原列表以 `CustomerBalance` 为驱动表，导致包年客户要么完全不出现、要么余额恒为 `0`；`price_policy='yearly'` 却看不到可用额度。现约定：包年客户的「余额」= 套餐剩余额度。

### 2. Signatures

[来源: `backend/app/routes/billing/balances.py`]

```python
def _build_package_remaining_cte():
    """每客户最新一条生效包年规则 → remaining = GREATEST(base_fee - 套餐内累计消耗, 0)
    供余额范围筛选 / total_amount 排序 / KPI 统计复用。"""

async def _batch_query_package_info(db: AsyncSession, customer_ids: list[int]) -> dict[int, dict]:
    """批量为行组装补充包年字段（含过期判定）。"""

def _compute_burn_down(real_amount, bonus_amount, settlement_type, stats,
                       package_info: dict | None = None) -> dict:
    """包年分支优先：燃尽 = 套餐到期剩余天数，而非按消耗推算。"""

def _assemble_balance_rows(customers, last_recharge_map, consumption_stats_map,
                           package_info_map) -> list[dict]:
    """以 Customer 为驱动表组装；包年客户 total_amount 覆盖为套餐剩余额度。"""
```

关键 SQL 形态：列表以 `Customer` 为驱动表 `LEFT JOIN customer_balances` + `LEFT JOIN package_remaining`；`total_amount` / 余额范围筛选 / KPI SUM 统一用 `COALESCE(package_remaining.remaining, customer_balances.total_amount, 0)`。

### 3. Contracts

`PricingRule.package_limits`（JSON）字段：`base_fee` / `is_unlimited` / `limit_count` / `over_limit_unit_price`。

余额列表 `data.list[]` 包年字段（非包年客户均为 `null`/`false`）：

| 字段 | 类型 | 含义 |
|------|------|------|
| `price_policy` | string | `Customer.price_policy`，`yearly` = 包年 |
| `is_package` | bool | 是否命中包年（有生效或已过期包年规则） |
| `total_amount` | number | 包年覆盖为套餐剩余额度（过期 = `0`）；非包年 = `CustomerBalance.total_amount` |
| `package_remaining_amount` | number | `max(base_fee - 套餐内累计消耗, 0)`；过期 = `0` |
| `package_remaining_count` | number \| null | `max(limit_count - 累计订单量, 0)`；**不限量或过期 = `null`** |
| `package_base_fee` | number | 年费（`base_fee`） |
| `package_limit_count` | number \| null | 不限量为 `null` |
| `package_is_unlimited` | bool | 不限量套餐 |
| `package_expired` | bool | 无生效规则但存在已过期包年规则 |
| `package_expiry_date` | string \| null | `YYYY-MM-DD`（CST）；无到期日 = `null` |
| `days_remaining` | number \| null | 包年：有效 = 到期剩余天数（无到期日 = `null`）、过期 = `0`；非包年沿用消耗推算 |

导出 Excel（`_build_excel`）包年新增三列：`套餐剩余额度（元）` / `套餐剩余次数`（不限量显示「不限」）/ `套餐到期日期`。

### 4. Validation & Error Matrix

| 条件 | 结果 |
|------|------|
| 包年且 `expiry_date >= now()` 或 `IS NULL`，且 `effective_date <= now()` | 生效：剩余额度参与筛选/排序/KPI，燃尽 = 到期天数 |
| 包年且 `expiry_date < now()`（无生效规则） | 过期：`total_amount = 0`、`package_expired = true`、`days_remaining = 0`、前端标「套餐已过期」 |
| 包年无 `expiry_date` | 视为生效（长期有效）：`days_remaining = null`，燃尽列显示「无到期日」 |
| 同一客户多条生效包年规则 | 取 `created_at` 最新一条（列表 CTE 用 `row_number()`，Python 侧按 `created_at desc` 首条，两处口径须一致） |
| `is_unlimited = true` | `remaining_count = null`；剩余额度仍按 `base_fee - 累计消耗` 计算 |
| 累计消耗超过 `base_fee` | `GREATEST(..., 0)` 下限为 0，不出现负余额 |

**口径一致性要求**：CTE（SQL 侧）与 `_batch_query_package_info`（Python 侧）是同一口径的两份独立实现，改一处必须同步另一处，否则筛选/KPI 与列表展示会相互矛盾。

### 5. Good/Base/Bad Cases

- Good: 包年客户无 `CustomerBalance` 行 → 仍出现在列表，`is_package = true`、`total_amount = package_remaining_amount`；余额范围「1万以下」能筛到它。
- Base: 非包年客户字段保持 `is_package = false`、包年字段 `null`，余额/燃尽/KPI 与改动前一致。
- Bad: 继续用 `CustomerBalance` 内连接作驱动表 —— 包年客户被静默丢弃；或在 `total_amount` 排序里仍用 `CustomerBalance.total_amount` —— 包年客户全部排到 0 值区，与展示值不符。

### 6. Tests Required

[来源: `backend/tests/integration/test_billing_balance_package.py`、`backend/tests/unit/test_balance_package.py`]

| 用例 | 断言点 |
|------|--------|
| `test_balance_list_includes_package_customer_without_balance_row` | 无余额行包年客户出现在列表，`is_package=true` 且余额 = 剩余额度 |
| `test_balance_list_unlimited_package_has_no_count` | 不限量：`package_remaining_count=null` |
| `test_balance_list_expired_package_shows_zero` | 过期：`total_amount=0`、`package_expired=true`、`days_remaining=0` |
| `test_balance_filter_package_remaining_amount` | 余额范围筛选按剩余额度命中/排除包年客户 |
| `test_balance_stats_includes_package_remaining` | 「预付费总余额」「余额不足」计入包年剩余额度 |
| `test_export_balances_package_columns` | 导出含三列，不限量客户次数列显示「不限」 |
| `test_burn_down_valid_package_uses_expiry_days` / `..._without_expiry_returns_none` / `..._expired_package_returns_zero` | 燃尽包年三分支 |
| `test_assemble_package_without_balance_row` / `..._expired_package_zeroes_balance` / `..._unlimited_package_no_count` / `..._non_package_unchanged` | 行组装字段输出 |
| `test_batch_query_package_info_*`（limit_and_count / unlimited_has_no_count / clamps_negative / expired_flag / empty_ids） | 批量查询剩余额度与次数、负值截断、过期标记、空入参 |

变异校验：把列表 `total_amount` 排序表达式从 `COALESCE(package_cte..., ...)` 换回 `CustomerBalance.total_amount`，`test_balance_filter_package_remaining_amount` 必须失败。

### 7. Wrong vs Correct

#### Wrong

```python
# 以 CustomerBalance 为驱动表：无余额行的包年客户被整体过滤掉
select(CustomerBalance).join(Customer, ...)
# 且把 deleted_at 过滤写在 WHERE，会连带丢掉无余额行客户
.outerjoin(CustomerBalance, CustomerBalance.customer_id == Customer.id)
.where(CustomerBalance.deleted_at.is_(None))
```

#### Correct

```python
# Customer 驱动 + outerjoin；软删条件必须放进 ON 子句
select(Customer)
.outerjoin(CustomerBalance,
           (CustomerBalance.customer_id == Customer.id)
           & (CustomerBalance.deleted_at.is_(None)))
.outerjoin(package_cte, Customer.id == package_cte.c.cid)
.where(Customer.deleted_at.is_(None))
# 余额口径统一 COALESCE，筛选/排序/KPI 共用
balance_expr = func.coalesce(package_cte.c.remaining, CustomerBalance.total_amount, 0)
```

> **PG JSON 陷阱**：`package_limits` 是 `json` 类型，PostgreSQL 的 `json` 无相等操作符，**不能出现在 `GROUP BY` / `DISTINCT`**。套餐内累计消耗须用按 `pricing_rule_id` 关联的标量子查询（`.correlate(PricingRule).scalar_subquery()`）聚合，不要 `GROUP BY pr.package_limits`。

---

## 相关约定

- 余额范围档位（前端 `BALANCE_RANGE_OPTIONS`）中「1万以下」的 `min` 有意为 `null`（含欠费与零余额），与 `low_balance_count` 口径保持一致；「欠费」是其中只看负余额的窄档，重叠属预期。
- 余额列表默认排序仍为 `company_id` 升序；零余额客户在列表中保持中性色（不标红），仅负余额标红并加「欠费」标签。
