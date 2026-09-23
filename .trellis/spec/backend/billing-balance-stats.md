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
| 缺少 `billing:view` 权限 | `403`（由 `@require_permission` 处理） |

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
| `useBalance.test.ts`「结算类型分组筛选」 | 列表请求带 `settlement_group`；`getBalanceStats` 不带该参数且仍按默认筛选口径统计 |

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

## 相关约定

- 余额范围档位（前端 `BALANCE_RANGE_OPTIONS`）中「1万以下」的 `min` 有意为 `null`（含欠费与零余额），与 `low_balance_count` 口径保持一致；「欠费」是其中只看负余额的窄档，重叠属预期。
- 余额列表默认排序仍为 `company_id` 升序；零余额客户在列表中保持中性色（不标红），仅负余额标红并加「欠费」标签。
