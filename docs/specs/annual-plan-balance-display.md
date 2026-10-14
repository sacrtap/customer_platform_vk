# 包年套餐客户余额显示优化

## Context

余额管理页面中，计费类型为"包年结算"（`PricingRule.pricing_type = 'package'`）的客户余额始终显示 ¥0.00，燃尽列也异常（显示"已耗尽"或"无消耗"）。根因：余额页的数据源是 `CustomerBalance.total_amount`（预付费现金池），而包年客户走"合同式预收费"模式——年费通过结算单一次性扣款，不进 `CustomerBalance`；包年实际可用额度在另一条独立链路（`PricingRule.package_limits.base_fee` − `DailyConsumption.total_cost` 累计）中，余额页完全没有反映。

**目标**：余额页为包年客户计算并展示"套餐剩余额度 + 剩余次数"双值，燃尽列展示套餐到期剩余天数，余额范围筛选按剩余额度参与，过期套餐显示 ¥0 并标注"套餐已过期"。

## 用户确认的口径

| 维度 | 决策 |
|---|---|
| 余额口径 | **双值展示**：剩余额度（`base_fee − 累计已消耗`）+ 剩余次数（限量套餐：`limit_count − 累计订单量`；不限量套餐不显示次数） |
| 燃尽口径 | **到期剩余天数**：基于 `PricingRule.expiry_date` − 今天 |
| 过期处理 | 显示 ¥0 并标注"套餐已过期"灰色标签 |
| 筛选口径 | 包年客户按"剩余额度"参与余额范围筛选（balance_min/balance_max） |

## Approach

### Step 1 — 后端：余额列表查询引入包年客户

**目标**：让没有 `CustomerBalance` 行的包年客户也出现在余额列表中。

当前 `_query_balance_rows_raw`（`backend/app/routes/billing/balances.py:372-380`）用 `select(CustomerBalance).join(Customer)`，INNER JOIN 导致无余额行的包年客户不出现。

改为以 `Customer` 为驱动表、`outerjoin(CustomerBalance)`：
- `base_stmt = select(Customer).outerjoin(CustomerBalance, CustomerBalance.customer_id == Customer.id).outerjoin(CustomerProfile, ...)`，保留 `CustomerBalance.deleted_at.is_(None)` 条件移入 outerjoin ON 子句
- 后续 WHERE 中涉及 `CustomerBalance.total_amount` 的余额范围筛选（`:443-446`）改为 `COALESCE` 或仅对非包年客户生效（见 Step 4）
- 排序字段映射 `sort_field_map`（`:363-370`）中 `total_amount` / `used_total` 从 `CustomerBalance.xxx` 改为 `func.coalesce(CustomerBalance.xxx, 0)`
- 行组装（`_assemble_balance_rows`）入参从 `list[CustomerBalance]` 变为 `list[Customer]`，需从 `Customer.balance`（反向关系）或 outerjoin 结果取 `CustomerBalance`；若包年客户无余额行则 `total_amount/real_amount/bonus_amount` 均为 0

**注意**：`Customer` 模型需确认是否有 `balance` 反向关系（`relationship("CustomerBalance", ...)`）。若无，outerjoin 结果中通过 `CustomerBalance` 实体直接取值（SQLAlchemy outerjoin 后 `CustomerBalance` 字段为 NULL 时 ORM 实例属性为 None）。

### Step 2 — 后端：批量查询包年套餐信息

新增 `_batch_query_package_info(db, customer_ids)` 函数（放在 `balances.py`，紧邻 `_batch_query_consumption_stats` 之后），返回 `{customer_id: {pricing_rule, package_limits, consumed_amount, consumed_count, expiry_date, effective_date}}`：

1. **查询生效的包年规则**：批量查 `PricingRule`，条件 `customer_id IN (customer_ids)` + `pricing_type = 'package'` + `effective_date <= now` + `(expiry_date >= now OR expiry_date IS NULL)` + `deleted_at IS NULL`，按 `created_at DESC` 取每客户最新一条。复用 `_get_active_package_rule`（`cost_calc.py:316-342`）的查询逻辑，改为批量版本。

2. **查询累计消耗与累计订单量**（仅在套餐有效期内）：
   - 累计消耗金额：`SELECT customer_id, SUM(total_cost) FROM daily_consumptions WHERE pricing_rule_id = <rule.id> AND deleted_at IS NULL GROUP BY customer_id`
   - 累计订单量（限量套餐用）：`SELECT customer_id, SUM(order_count) FROM daily_consumptions WHERE pricing_rule_id = <rule.id> AND deleted_at IS NULL GROUP BY customer_id`
   - 关联键用 `pricing_rule_id` 精确匹配该套餐规则产生的消费记录

3. **计算剩余额度与剩余次数**：
   - `base_fee = package_limits.get("base_fee", 0)`
   - `remaining_amount = base_fee - consumed_amount`（若 ≤ 0 则为 0）
   - `is_unlimited = package_limits.get("is_unlimited", False)`
   - 限量套餐：`limit_count = package_limits.get("limit_count", 0)`，`remaining_count = limit_count - consumed_count`（若 ≤ 0 则为 0）；不限量套餐：`remaining_count = None`

4. **过期判断**：若该客户在步骤 1 中未命中任何生效包年规则，但 `Customer.price_policy == 'yearly'`，查该客户是否有已过期的包年规则（`expiry_date < now`），有则标记 `is_expired = True`。

### Step 3 — 后端：行组装输出包年字段

修改 `_assemble_balance_rows`（`:704-748`），新增 `package_info_map` 入参，为每行增加字段：

```python
# 包年客户额外字段（非包年客户均为 None）
"price_policy": b.customer.price_policy if b.customer else None,  # 'yearly' 标识
"is_package": bool(pkg_info),  # 是否有生效包年规则
"package_remaining_amount": pkg_info["remaining_amount"] if pkg_info else None,
"package_remaining_count": pkg_info["remaining_count"] if pkg_info else None,
"package_base_fee": pkg_info["base_fee"] if pkg_info else None,
"package_limit_count": pkg_info["limit_count"] if pkg_info else None,
"package_is_unlimited": pkg_info["is_unlimited"] if pkg_info else None,
"package_expired": pkg_info.get("is_expired", False) if pkg_info else False,
"package_expiry_date": pkg_info["expiry_date"].isoformat() if pkg_info and pkg_info.get("expiry_date") else None,
```

包年客户的 `total_amount` 用 `package_remaining_amount` 覆盖（使余额范围筛选与展示一致）；`real_amount` / `bonus_amount` 保持原 `CustomerBalance` 值（通常为 0）。

### Step 4 — 后端：包年客户燃尽改为到期天数

修改 `_compute_burn_down`（`:155-186`），新增 `package_info` 入参：

```python
def _compute_burn_down(real_amount, bonus_amount, settlement_type, stats, package_info=None):
    # 包年客户：燃尽 = 到期剩余天数
    if package_info and package_info.get("is_package"):
        expiry = package_info.get("expiry_date")
        if expiry is None:
            return {"daily_avg_cost": None, "consumption_days": 0, "days_remaining": None}
        days_remaining = (expiry.date() - date.today()).days
        if days_remaining < 0:
            days_remaining = 0
        return {"daily_avg_cost": None, "consumption_days": 0, "days_remaining": days_remaining}
    # 过期包年客户：标记已耗尽
    if package_info and package_info.get("is_expired"):
        return {"daily_avg_cost": None, "consumption_days": 0, "days_remaining": 0}
    # 以下保持原有预付费/后付费逻辑不变
    ...
```

同时更新调用处（`:738-743`）传入 `package_info`。

### Step 5 — 后端：余额范围筛选适配包年客户

当前余额范围筛选（`:443-446`）直接比较 `CustomerBalance.total_amount`。包年客户改用 `package_remaining_amount`，但该值在 Python 层计算（Step 2-3），SQL 层无法直接用。

**方案**：在 SQL 层用子查询计算包年剩余额度，作为 `COALESCE` 替代 `CustomerBalance.total_amount` 参与筛选与排序。具体：

新增一个 CTE `package_remaining`，在 `_query_balance_rows_raw` 中 LEFT JOIN：
```sql
SELECT pr.customer_id,
       pr.package_limits->>'base_fee' AS base_fee,
       pr.expiry_date,
       COALESCE(SUM(dc.total_cost), 0) AS consumed
FROM pricing_rules pr
LEFT JOIN daily_consumptions dc ON dc.pricing_rule_id = pr.id AND dc.deleted_at IS NULL
WHERE pr.pricing_type = 'package' AND pr.deleted_at IS NULL
  AND pr.effective_date <= now()
  AND (pr.expiry_date >= now() OR pr.expiry_date IS NULL)
GROUP BY pr.customer_id, pr.package_limits, pr.expiry_date
```
余额范围筛选改为：`COALESCE(package_remaining.remaining, CustomerBalance.total_amount, 0)` 参与 min/max 比较。排序 `total_amount` 同理用此 COALESCE 表达式。

**备选（若 CTE 方案过重）**：余额范围筛选改为后端 Python 层后过滤——先查全量再在 `_assemble_balance_rows` 后按 `package_remaining_amount` 过滤。缺点是分页不准确。CTE 方案为推荐方案。

### Step 6 — 后端：燃尽排序 SQL CTE 适配包年

修改燃尽排序 SQL（`:602-657`），`days_remaining_expr` 的 `CASE` 增加包年分支：
```python
case(
    (Customer.settlement_type == "postpaid", None),
    (package_cte.c.customer_id != None,  # 包年客户
        func.extract('day', func.age(package_cte.c.expiry_date, func.now()))
    ),
    (func.coalesce(consumption_cte.c.total_cost_30d, 0) <= 0, None),
    else_=<原有预付费公式>,
)
```
需 LEFT JOIN `package_remaining` CTE 到 `base_stmt`。

### Step 7 — 后端：KPI 统计适配包年

修改 `get_balance_stats`（`:924-1265`）：

1. **总余额**（`:1135-1147` `_balance_totals`）：预付费总余额中，包年客户用 `package_remaining.remaining` 替代 `CustomerBalance.total_amount`。需 LEFT JOIN `package_remaining` CTE，SUM 改为 `COALESCE(package_remaining.remaining, CustomerBalance.total_amount, 0)`。

2. **余额不足客户数**（`:1184-1194`）：同上，`< LOW_BALANCE_THRESHOLD` 改为 `COALESCE(package_remaining.remaining, CustomerBalance.total_amount, 0) < LOW_BALANCE_THRESHOLD`。

3. **即将耗尽客户数**（`:1223-1245`）：包年客户用到期天数替代消耗推算天数。`burning_soon_days_expr` 增加包年分支（到期 ≤ 7 天）。

### Step 8 — 后端：导出 Excel 适配

修改 `_build_excel`（`:877-902`），包年客户导出列增加：
- "套餐剩余额度（元）"：`package_remaining_amount`
- "套餐剩余次数"：`package_remaining_count`（不限量显示"不限"）
- "套餐到期日期"：`package_expiry_date`

### Step 9 — 前端：Balance 类型扩展

修改 `frontend/src/api/billing.ts:31-53` 的 `Balance` 接口，新增字段：
```ts
price_policy?: string
is_package?: boolean
package_remaining_amount?: number | null
package_remaining_count?: number | null
package_base_fee?: number | null
package_limit_count?: number | null
package_is_unlimited?: boolean | null
package_expired?: boolean
package_expiry_date?: string | null
```

### Step 10 — 前端：余额列双值展示

修改 `frontend/src/views/billing/components/BalanceTable.vue:38-51` 余额列模板：

```vue
<td>
  <div class="balance-info" v-if="!record.is_package">
    <!-- 原有预付费/后付费余额展示 -->
  </div>
  <div class="balance-info" v-else>
    <div class="balance-amount">
      <b :class="{ danger: record.package_expired }">¥{{ formatAmount(record.package_remaining_amount) }}</b>
      <span v-if="record.package_expired" class="tag gray">套餐已过期</span>
      <span v-else-if="record.package_is_unlimited" class="tag blue">不限量</span>
    </div>
    <div class="balance-detail">
      <span class="real">额度：¥{{ formatAmount(record.package_remaining_amount) }}</span>
      <span v-if="!record.package_is_unlimited && record.package_remaining_count != null"
            class="bonus">次数：{{ record.package_remaining_count }}</span>
    </div>
  </div>
</td>
```

### Step 11 — 前端：燃尽列包年到期展示

修改 `BalanceTable.vue:52-65` 燃尽列模板，增加包年分支：

```vue
<td>
  <span v-if="record.settlement_type === 'postpaid'" class="tag gray">后付费</span>
  <span v-else-if="record.package_expired" class="tag gray">套餐已过期</span>
  <a-tooltip v-else-if="record.is_package" :content="getPackageBurnTooltip(record)">
    <div class="burn-cell">
      <div class="burn-bar" :class="getPackageBurnBarClass(record)">
        <div class="burn-fill" :style="{ width: getPackageBurnFillPct(record) + '%' }"></div>
      </div>
      <span class="burn-text" :class="getPackageBurnTextClass(record)">
        {{ getPackageBurnLabel(record) }}
      </span>
    </div>
  </a-tooltip>
  <a-tooltip v-else :content="getBurnTooltip(record)">
    <!-- 原有预付费燃尽展示 -->
  </a-tooltip>
</td>
```

新增包年燃尽辅助函数（`BalanceTable.vue` script 部分）：
- `getPackageBurnFillPct`：基于到期天数，`min(days_remaining / 365 * 100, 100)`（满格=安全）
- `getPackageBurnBarClass`：≤30天红、31-90黄、其余绿
- `getPackageBurnLabel`：`剩余N天到期` 或 `已到期`
- `getPackageBurnTooltip`：显示套餐到期日期、剩余额度、剩余次数

行高亮 `isBurningSoon` / `isBurningWarn`（`:247-254`）增加包年到期判断：包年客户 `days_remaining <= 7` 触发红色、`8-30` 触发黄色。

## Critical Files & Anchors

| 文件 | 区域 | 原因 |
|---|---|---|
| `backend/app/routes/billing/balances.py:312-748` | `_query_balance_rows_raw` + `_assemble_balance_rows` + `_compute_burn_down` | 核心数据查询、行组装、燃尽计算，包年逻辑全部在此注入 |
| `backend/app/routes/billing/balances.py:924-1265` | `get_balance_stats` KPI | 预付费总余额、余额不足、即将耗尽三处统计需适配包年 |
| `backend/app/services/cost_calc.py:316-342, 470-512` | `_get_active_package_rule` + `_calc_package` | 包年规则查询与套餐结构参考，Step 2 批量版本复用其查询逻辑 |
| `frontend/src/views/billing/components/BalanceTable.vue:38-65, 244-327` | 余额列+燃尽列模板与辅助函数 | 前端双值展示与到期燃尽 |
| `frontend/src/api/billing.ts:31-53` | `Balance` 接口 | 新增包年字段类型定义 |

## Verification

### 前置条件
- 后端服务运行在 `localhost:8000`（`make backend` 或 `cd backend && python -m uvicorn app.main:app`）
- 前端开发服务运行在 `localhost:5173`（`make frontend` 或 `cd frontend && npm run dev`）
- 数据库中存在至少 1 个包年客户（`Customer.price_policy = 'yearly'`，且有关联的 `PricingRule` `pricing_type = 'package'`）

### 验证步骤

1. **包年客户出现在余额列表**：
   - 访问余额管理页面，确认 `price_policy = 'yearly'` 的客户出现在列表中（即使无 `CustomerBalance` 行）
   - 命令：`curl 'localhost:8000/billing/balances?page=1&page_size=100' -H 'Authorization: Bearer <token>' | jq '.data.list[] | select(.is_package == true) | {customer_name, package_remaining_amount, package_remaining_count, days_remaining}'`

2. **余额双值展示**：
   - 限量包年客户：余额列显示"剩余额度 + 剩余次数"两行
   - 不限量包年客户：余额列显示"剩余额度 + 不限量"标签
   - 非包年客户：余额列保持原有"实充/赠送"展示不变

3. **燃尽列到期天数**：
   - 有效包年客户：燃尽列显示"剩余N天到期"进度条
   - 过期包年客户：燃尽列显示"套餐已过期"灰色标签

4. **余额范围筛选**：
   - 选择"1万以下"筛选，包年客户按剩余额度参与筛选
   - 确认包年客户（剩余额度 < 10000）被选中

5. **KPI 卡片一致性**：
   - "预付费总余额"包含包年客户剩余额度
   - "余额不足客户数"包含剩余额度 < 10000 的包年客户

6. **导出 Excel**：
   - 导出余额列表，确认包年客户行有"套餐剩余额度""套餐剩余次数""套餐到期日期"列

7. **现有定价/阶梯客户无回归**：
   - 确认定价/阶梯客户余额、燃尽、KPI 数据与修改前一致

### 单元测试
- `_batch_query_package_info`：mock PricingRule + DailyConsumption，验证剩余额度/次数计算
- `_compute_burn_down` 包年分支：验证到期天数计算、过期返回 0
- `_assemble_balance_rows`：验证包年字段输出、非包年客户不受影响

## Assumptions & Contingencies

- **假设**：包年客户每日消费记录（`DailyConsumption`）的 `pricing_rule_id` 正确指向对应的包年 `PricingRule`。若历史数据中 `pricing_rule_id` 为 NULL 但 `customer.price_policy = 'yearly'`，累计消耗将不准确。**应对**：Step 2 中若 `pricing_rule_id` 关联不到消耗记录，回退为按 `customer_id + 有效期内日期范围` 聚合 `DailyConsumption.total_cost`（不限定 `pricing_rule_id`）。

- **假设**：包年客户年费仅存于 `PricingRule.package_limits.base_fee`，不存在单独的"年费充值"记录进 `CustomerBalance`。若实际数据中有年费充入 `CustomerBalance` 的混合情况，剩余额度计算需避免重复。**应对**：若包年客户 `CustomerBalance.total_amount > 0` 且有生效包年规则，以 `package_remaining_amount` 为准展示，但在 tooltip 中同时显示 `CustomerBalance` 余额。

- **假设**：`Customer` 模型存在到 `CustomerBalance` 的反向关系（`relationship`）。**应对**：实现时先确认；若无，outerjoin 后直接从查询结果取 `CustomerBalance` 字段（NULL 时为 None）。
