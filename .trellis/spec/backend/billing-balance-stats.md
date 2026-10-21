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

[来源: 共享模块 `backend/app/services/package_balance.py`；余额管理页 `backend/app/routes/billing/balances.py` 以 `_build_package_remaining_cte` / `_batch_query_package_info` 别名再导出]

```python
def build_package_remaining_cte():
    """每客户最新一条生效包年规则 → remaining = GREATEST(base_fee - 套餐内累计消耗, 0)
    供余额范围筛选 / total_amount 排序 / KPI 统计复用。"""

async def batch_query_package_info(db: AsyncSession, customer_ids: list[int]) -> dict[int, dict]:
    """批量为行组装补充包年字段（含过期判定）。"""

def resolve_effective_balance(
    balance_total: float | None, package_info: dict | None
) -> tuple[float, bool]:
    """跨页统一决策：包年 → (套餐剩余额度, True)；否则 → (CustomerBalance, False)。"""

def _compute_burn_down(real_amount, bonus_amount, settlement_type, stats,
                       package_info: dict | None = None) -> dict:
    """包年分支优先：燃尽 = 套餐到期剩余天数，而非按消耗推算。"""

def _assemble_balance_rows(customers, last_recharge_map, consumption_stats_map,
                           package_info_map) -> list[dict]:
    """以 Customer 为驱动表组装；包年客户 total_amount 覆盖为套餐剩余额度。"""
```

关键 SQL 形态：列表以 `Customer` 为驱动表 `LEFT JOIN customer_balances` + `LEFT JOIN package_remaining`；`total_amount` / 余额范围筛选 / KPI SUM 统一用 `COALESCE(package_remaining.remaining, customer_balances.total_amount, 0)`。

> **口径唯一来源**：CTE 与 Python 批量查询均已迁入 `app/services/package_balance.py`，余额管理页、客户管理页与开放平台 API**必须**从该模块导入，禁止各自重写一份口径（见下节「跨页口径一致」）。

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
| `package_consumed_amount` | number \| null | 套餐内累计消耗（**实时，含未结算**）= `SUM(DailyConsumption.total_cost WHERE pricing_rule_id = 生效规则)`；**包年客户的「已消耗」列与 `used_total` 排序均取此值**；非包年或已过期包年 = `null`（展示层回退 `used_total`） |
| `package_base_fee` | number | 年费（`base_fee`） |
| `package_limit_count` | number \| null | 不限量为 `null` |
| `package_is_unlimited` | bool | 不限量套餐 |
| `package_expired` | bool | 无生效规则但存在已过期包年规则 |
| `package_expiry_date` | string \| null | `YYYY-MM-DD`（CST）；无到期日 = `null` |
| `days_remaining` | number \| null | 包年：有效 = 到期剩余天数（无到期日 = `null`）、过期 = `0`；非包年沿用消耗推算 |

导出 Excel（`_build_excel`）包年新增三列：`套餐剩余额度（元）` / `套餐剩余次数`（不限量显示「不限」）/ `套餐到期日期`。

**「已消耗」列口径（包年 vs 预付费）**：

- 预付费客户：`used_total`（`CustomerBalance` 累计），**仅结算单扣款后更新**。
- 包年客户：`package_consumed_amount`（套餐内累计消耗，**实时，含未结算**），与「余额 = `base_fee − 实时消耗`」同口径，保证「余额 + 已消耗 = `base_fee`」自洽。包年已消耗**不依赖结算单**——年费为合同式预收，不走 `CustomerBalance` 现金池。
- 已过期包年：`package_consumed_amount = null`，展示层回退 `used_total`。
- 排序：`sort_by=used_total` 用 `COALESCE(package_remaining.consumed, customer_balances.used_total, 0)`，与展示值同口径。
- 导出：`已消耗（元）` 列对包年客户取 `package_consumed_amount`。

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
| `test_export_balances_package_columns` | 导出含三列，不限量客户次数列显示「不限」；`已消耗（元）` 对包年取套餐内累计消耗 |
| `test_balance_sort_used_total_uses_package_consumed` | `sort_by=used_total&sort_order=desc`：包年客户以套餐内累计消耗（80000）参与排序，排在 `used_total=5000` 的预付费客户之前 |
| `test_assemble_expired_package_zeroes_balance` / `test_balance_list_expired_package_shows_zero` | 过期包年 `package_consumed_amount = null`（展示层回退 `used_total`） |
| `test_burn_down_valid_package_uses_expiry_days` / `..._without_expiry_returns_none` / `..._expired_package_returns_zero` | 燃尽包年三分支 |
| `test_assemble_package_without_balance_row` / `..._expired_package_zeroes_balance` / `..._unlimited_package_no_count` / `..._non_package_unchanged` | 行组装字段输出（含 `package_consumed_amount`：包年 = 实时累计、非包年/过期 = `null`） |
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

## Scenario: 客户管理页余额口径对齐（列表 / 详情 / 预测 / 360 摘要）

### 1. Scope / Trigger

- Trigger: 跨层契约变更 —— 客户管理页（`backend/app/routes/customers.py`）的余额展示口径需与余额管理页一致；修复 `/summary` 端点既有 500、`/balance-forecast` 返回 ORM 对象两个缺陷。
- 背景：包年客户年费不进 `CustomerBalance`，客户管理页若继续显示 `CustomerBalance.total_amount`（=0），会与余额管理页「套餐剩余额度」矛盾，并使健康度误判为「高风险」。

### 2. Signatures

[来源: `backend/app/routes/customers.py`，均从共享模块导入]

```python
from ..services.package_balance import (
    batch_query_package_info,     # 列表当前页 / 详情 / 预测 / 摘要 批量补充包年字段
    resolve_effective_balance,    # 详情余额 Tab 端点决策口径
)
```

### 3. Contracts

客户列表 `data.list[]` 包年相关字段（非包年客户 `is_package=false`、`package_expired=false`，`balance` 仍取 `CustomerBalance`）：

| 字段 | 类型 | 含义 |
|------|------|------|
| `balance` | number | 包年 → 套餐剩余额度（无 `CustomerBalance` 行也不为 0）；非包年 → `CustomerBalance.total_amount`（无余额行 = `0`） |
| `is_package` | bool | 命中包年（生效或已过期规则）；前端据此把「余额」文案标注为「套餐剩余额度」 |
| `package_expired` | bool | 无生效规则但存在已过期包年规则 |

- 排序：`sort_by=balance` 对包年客户以套餐剩余额度参与排序（服务层 `COALESCE(package_remaining.remaining, customer_balances.total_amount, 0)`），排序与展示同口径。
- 健康度：`health` 以**有效余额**（包年 = 套餐剩余额度）判定，避免年费不入账导致的 0 余额「高风险」误判。
- 客户详情 `data.balance.total_amount`：包年 = 套餐剩余额度；无 `CustomerBalance` 行时以 0/0/0 结构返回（不返回 `null`）。详情写缓存后须与列表同口径。
- 详情余额 Tab 端点 `GET /api/v1/billing/customers/<id>/balance`：`total_amount = resolve_effective_balance(...)`，并附包年字段（`is_package` / `package_remaining_amount` / `package_remaining_count` / `package_is_unlimited` / `package_expired` / `package_consumed_amount`）。
- 余额预测 `GET /api/v1/customers/<id>/balance-forecast`：`balance` 必须为**数值**（此前误将 ORM `CustomerBalance` 对象直接返回导致前端拿不到数字）；包年取套餐剩余额度。
- 360 摘要 `GET /api/v1/customers/<id>/summary`：`balance` 文案按包年口径（`¥` 千分位）。
- 导出 Excel `_build_excel`：`余额` 列对包年客户输出套餐剩余额度。

### 4. Validation & Error Matrix

| 条件 | 结果 |
|------|------|
| 包年有生效规则 | 列表/详情/预测/摘要的余额均为套餐剩余额度；`is_package=true` |
| 包年规则已过期 | 余额 = `0`、`package_expired=true`（不落回 `CustomerBalance` 的欠费负值） |
| 包年无 `CustomerBalance` 行 | 列表仍出现且余额 = 剩余额度；详情 `balance` 以 0/0/0 结构返回 |
| 非包年客户 | 余额/健康度/排序与改动前完全一致（回归基线） |

### 5. Good/Base/Bad Cases

- Good: 包年客户 `base_fee=120000`、套餐内消耗 `30000` → 列表 `balance=90000`、`health=healthy`；余额管理页同一客户显示一致。
- Base: 非包年客户 `is_package=false`，其余字段不变。
- Bad: 列表/详情仍读 `CustomerBalance.total_amount` → 包年客户全为 0 并与余额管理页矛盾；`balance-forecast` 直接 `json({"balance": customer.balance})` → 序列化 ORM 对象报错或前端拿到非数字。

### 6. Tests Required

[来源: `backend/tests/integration/test_customers_package_balance.py`、`frontend/src/views/customers/detail/__tests__/CustomerBalanceTab.test.ts`]

| 用例 | 断言点 |
|------|--------|
| `test_customer_list_package_balance_uses_remaining` | 列表包年客户 `balance` = 剩余额度（非 0），`is_package=true` |
| `test_customer_list_package_health_not_high_risk` | 包年有消耗不因 0 余额误报 `high_risk` |
| `test_customer_detail_package_balance` | 详情 `balance.total_amount` = 剩余额度 |
| `test_billing_customer_balance_endpoint_package` | 余额 Tab 端点返回剩余额度 + 包年字段 |
| `test_balance_forecast_returns_numeric_balance` | 预测 `balance` 为数值且 = 剩余额度 |
| `test_customer_summary_package_balance_text` | 摘要余额文案为套餐剩余额度 |
| `test_customer_list_sort_by_balance_package_first` | `sort_by=balance` 包年客户以剩余额度参与排序 |
| `CustomerBalanceTab`（前端 4 例） | 非包年四卡片；包年三卡片 + 不显示实充/赠送；不限量显示「不限量」；过期显示「套餐已过期」标签 |

### 7. Wrong vs Correct

#### Wrong

```python
# 1) 客户管理页各自重写口径 → 与余额管理页漂移
balance = customer.balance.total_amount if customer.balance else 0

# 2) 预测接口直接返回 ORM 对象
return json({"code": 0, "data": {"balance": customer.balance}})

# 3) 调用不存在的方法（既有 500）
await service.get_customer_detail(customer_id)
```

#### Correct

```python
# 1) 统一走共享模块
from ..services.package_balance import batch_query_package_info
info = (await batch_query_package_info(db, [customer_id])).get(customer_id)
amount, _ = resolve_effective_balance(
    float(customer.balance.total_amount) if customer.balance else 0.0, info
)

# 2) 预测接口只返回数值
return json({"code": 0, "data": {"balance": amount}})

# 3) 摘要端点改用存在的服务方法（已 selectinload profile/balance）
customer = await CustomerService(db).get_customer_by_id(customer_id)
```

---

## Scenario: 开放平台余额接口口径（`/api/v1/balances`、`/api/v1/erp/balances`）

### 1. Scope / Trigger

- Trigger: 对外契约修正 —— 开放平台两个余额接口此前只算 `CustomerBalance.total_amount − used_total`，包年客户恒返回 `0.0`，与内部页面矛盾。
- 背景: 包年客户年费走合同式预收、不进 `CustomerBalance`；开放接口是 ERP 下游对账数据源，返回 0 会让下游误判「余额耗尽」。
- 路由: `backend/app/routes/openapi.py`（`openapi_bp` = `/api/v1/erp`、`openapi_customer_bp` = `/api/v1`），认证走 API-Key（`Authorization: Bearer vk_...`，见 `OPENAPI_PREFIXES`）。

### 2. Signatures

[来源: `backend/app/routes/openapi.py`，复用共享模块 `build_package_remaining_cte`]

```python
def _build_customer_balance_stmt(erp_channel: str | None = None) -> Select:
    """Customer 驱动 + LEFT JOIN customer_balances + LEFT JOIN package_remaining。
    第 6 列返回 package_remaining.remaining（非包年 → NULL）。"""

def _format_balance_rows(rows, whitelist_map=None) -> list[dict]:
    """余额优先级：白名单静态值 > 包年剩余额度 > total_amount - used_total。"""
```

### 3. Contracts

响应结构不变（`customer_id` / `customer_name` / `balance`），仅 `balance` 取值口径变更：

| 客户类型 | `balance` |
|---|---|
| 命中余额白名单 | 白名单 `static_balance`（优先级最高，人工覆盖） |
| 包年客户（有效规则） | 套餐剩余额度 `max(base_fee − 套餐内累计消耗, 0)` |
| 非包年客户 | `total_amount − used_total`（无余额记录 = `0.0`） |

- 包年剩余额度按共享 CTE 计算，**每客户取最新一条生效规则**，与内部页面同口径。
- 返回全部有效客户（未删除、未停用），按 `company_id` 升序；ERP 渠道接口额外按 `erp_system` 过滤。

### 4. Validation & Error Matrix

| 条件 | 结果 |
|------|------|
| 包年客户无 `CustomerBalance` 行 | 返回套餐剩余额度（**不再**是 `0.0`） |
| 非包年客户无余额行 | `0.0`（口径不变） |
| 包年客户命中白名单 | 静态余额优先 |
| 缺少 API-Key / 无效 Key | `401` + `40104`（不变） |
| ERP 接口缺 `erp_channel` | `400` + `40004`（不变） |

### 5. Good/Base/Bad Cases

- Good: 包年客户 `base_fee=2980`、套餐内消耗 `99.32` → 接口返回 `2880.68`，与内部余额管理页一致。
- Base: 非包年客户 `5000/1500` → `3500.0`，与改动前一致。
- Bad: 仅用 `total_amount − used_total` → 8 个包年客户全部返回 `0.0`，ERP 下游对账错误。

### 6. Tests Required

[来源: `backend/tests/integration/test_openapi_api.py`]

| 用例 | 断言点 |
|------|--------|
| `test_all_balances_package_customer_uses_remaining_amount` | 包年无余额行客户 → `balance = 2880.68` |
| `test_all_balances_non_package_unchanged` | 非包年 = `total - used`；包年 = 剩余额度（回归基线） |
| `test_all_balances_package_whitelist_still_wins` | 包年命中白名单 → 静态余额优先 |
| `test_erp_balances_package_customer_uses_remaining_amount` | 渠道接口同样接入包年口径 |
| `test_all_balances_success` / `test_all_balances_whitelist_*` / `test_erp_balances_*` | 既有契约无回归 |

### 7. Wrong vs Correct

#### Wrong

```python
# 仅算现金池：包年客户恒为 0
select(CustomerBalance.total_amount, CustomerBalance.used_total)
balance = round(total - used, 2)
```

#### Correct

```python
# 复用共享 CTE，包年取剩余额度
package_cte = build_package_remaining_cte()
stmt = (... .outerjoin(package_cte, Customer.id == package_cte.c.cid))
if package_remaining is not None:
    balance = round(float(package_remaining), 2)
else:
    balance = round(total - used, 2)
```

---

## Scenario: 结算单列表按客户行业/ERP 筛选

### 1. Scope / Trigger

- Trigger: 跨层契约变更 —— `GET /api/v1/billing/invoices` 新增 `industry_type` / `erp_system` 查询参数，前端筛选栏新增对应两个单选下拉。
- 背景：结算单管理页原先只有「客户名称」「状态」两个筛选项。行业与 ERP 属性归属客户（`Customer.erp_system`、`CustomerProfile.industry_type_id` → `IndustryType`），需在结算单列表上按客户属性过滤。**筛选语义沿用客户列表后端既有约定**（`backend/app/services/customers.py:276-284,313-314`），不新建第二套口径。

### 2. Signatures

[来源: 项目源码 — `backend/app/services/billing.py` `InvoiceService.get_invoices`、`backend/app/routes/billing/invoices.py` `get_invoices`]

```python
async def get_invoices(
    self,
    customer_id: Optional[int] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    industry_type: Optional[str] = None,   # 行业名称，按 IndustryType.name 匹配
    erp_system: Optional[str] = None,      # ErpSystem.value，按 Customer.erp_system 精确匹配
    ...
    mine_user_id: Optional[int] = None,
) -> Tuple[List[Invoice], int]:
```

```
GET /api/v1/billing/invoices?industry_type=互联网&erp_system=yonyou
```

### 3. Contracts

请求字段（均为可选，空串视为未传）：

| 字段 | 类型 | 匹配口径 |
|------|------|----------|
| `industry_type` | string | **行业名称**（`IndustryType.name` 精确匹配），非 ID。经 `CustomerProfile.industry_type_id` 外键关联 |
| `erp_system` | string | **`ErpSystem.value`**（`Customer.erp_system` 精确匹配），非名称 |

关键实现约束：

- ERP 筛选复用 `get_invoices` 已有的 `Customer` inner join，**不加额外 join**；行业筛选按 `customers.py` 范式追加 `CustomerProfile`、`IndustryType` 两个 **outerjoin**。
- join/where 必须在 `count_stmt = select(func.count()).select_from(stmt.subquery())` **之前**完成，使计数与数据查询同口径。
- `CustomerProfile.customer_id` 唯一，outerjoin 不产生重复行；`result.scalars().unique().all()` 二次去重兜底。
- 响应字段不增不减（列表项不回显这两个筛选值）；权限（`billing:view`）与 `customer_scope_user_id` 数据可见性逻辑不变。

前端契约：

- `useInvoice` 的 `defaultFilters()` 新增 `industry_type: ''` / `erp_system: ''`；`loadInvoices` 仅在非空时拼参。
- `InvoiceFilters.vue` 字典复用 `getIndustryTypes()`（`/dicts/industry_types`）与 `getErpSystemsList()`（`/erp-systems`），防御式解包 `res.data?.data || res.data || []`；选项 value 分别为行业 `name` 与 ERP `value`，与后端匹配口径对齐。
- 导出（`exportInvoices`）不传这两个参数，仅 `status`——列表筛选语义不扩展到导出。

### 4. Validation & Error Matrix

| 条件 | 行为 |
|------|------|
| `industry_type` / `erp_system` 为空串或缺失 | 不加对应 where，返回全量 |
| 行业名称不存在 | 结果为空列表（`total=0`），非报错 |
| 互斥组合（`industry_type=A&erp_system=B`，A/B 属不同客户） | 空列表 |
| 非法参数名 | 忽略（Sanic `request.args.get` 返回 None） |

### 5. Good/Base/Bad Cases

- Good：客户A（互联网 + yonyou）、客户B（房地产 + kingdee）各一条结算单；`?industry_type=互联网` 仅含 A；`?erp_system=kingdee` 仅含 B；无筛选两条都在。
- Base：行业名称带前后空格不匹配（精确等值，无 trim）；客户无 profile 时行业筛选不命中（outerjoin 保证不因缺 profile 丢行——只在传行业筛选时才 join）。
- Bad：把 `industry_type` 当 ID 传（`industry_type=1`）→ 空列表，与既有 name 口径不符。

### 6. Tests Required

| 测试 | 断言点 |
|------|--------|
| `test_billing_api.py::test_get_invoices_filter_industry_type_and_erp_system` | 行业名称筛选仅含目标客户；ERP value 筛选仅含目标客户；互斥组合为空；无筛选两条都在；`total >= 2`（计数与数据同口径） |
| `test_billing_api.py::test_get_invoices_list`（既有） | 无筛选不回归 |
| 前端 `useInvoice.test.ts`（既有） | `defaultFilters` 扩展未破坏排序逻辑 |

### 7. Wrong vs Correct

#### Wrong

```python
# 新建 ID 口径：与客户列表 name 匹配语义分裂
if industry_type:
    stmt = stmt.where(CustomerProfile.industry_type_id == int(industry_type))
```

#### Correct

```python
# 镜像 customers.py：outerjoin 后按 IndustryType.name 匹配
if industry_type:
    stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
    stmt = stmt.outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
    stmt = stmt.where(IndustryType.name == industry_type)
```

---

## 相关约定

- 余额范围档位（前端 `BALANCE_RANGE_OPTIONS`）中「1万以下」的 `min` 有意为 `null`（含欠费与零余额），与 `low_balance_count` 口径保持一致；「欠费」是其中只看负余额的窄档，重叠属预期。
- 余额列表默认排序仍为 `company_id` 升序；零余额客户在列表中保持中性色（不标红），仅负余额标红并加「欠费」标签。
