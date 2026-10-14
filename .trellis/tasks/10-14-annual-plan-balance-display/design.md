# 包年套餐余额显示优化 — 技术设计

## 1. 数据模型确认（已核实）

- `Customer.price_policy`（'yearly' = 包年客户）、`Customer.balance` 反向关系存在（`uselist=False`，`back_populates="customer"`）
- `CustomerBalance`：`customer_id` unique，无余额行时 `Customer.balance` 为 None
- `PricingRule`：`pricing_type`（'fixed'/'tier'/'package'）、`package_limits`（JSON：`base_fee`/`is_unlimited`/`limit_count`）、`effective_date`/`expiry_date`（`DateTime(timezone=True)`，**UTC 存储**）、`created_at`
- `DailyConsumption`：`customer_id`、`consumption_date`、`order_count`、`total_cost`、`pricing_rule_id`（可空，指向计费规则）
- 时区约定：DB 存 UTC，前端为 CST；`app/utils/timezone.py` 提供 `CST`/`UTC`/`utc_now()`

## 2. 总体结构

SQL 层（`_query_balance_rows_raw` / `get_balance_stats`）负责**驱动查询、筛选、排序、KPI 聚合**——包年剩余额度以 `package_remaining` CTE 参与；Python 层（`_batch_query_package_info` + `_assemble_balance_rows`）负责**展示字段计算**（remaining_amount / remaining_count / is_expired / expiry_date 等）。两处计算口径一致：**每客户最新一条生效包年规则**（`ORDER BY created_at DESC`）。

### 2.1 驱动表改造（Step 1）

`base_stmt` 从 `select(CustomerBalance).join(Customer)` 改为 `select(Customer).outerjoin(...)`：

- `outerjoin(CustomerBalance, (CustomerBalance.customer_id == Customer.id) & (CustomerBalance.deleted_at.is_(None)))`——deleted_at 条件移入 ON 子句
- `outerjoin(CustomerProfile, ...)` 保持
- count_stmt 同步改为 `count(Customer.id)` + 相同 outerjoin
- 所有 `CustomerBalance.customer_id == x` 引用改为 `Customer.id == x`（last_recharge 子查询 outerjoin、consumption_cte outerjoin、recharge 筛选、tag 筛选等）
- 预加载：`selectinload(Customer.balance)` + `selectinload(Customer.profile).selectinload(CustomerProfile.industry_type)`；`result.scalars()` 取 Customer 列表
- `_assemble_balance_rows` 入参从 `list[CustomerBalance]` 改为 `list[Customer]`，余额字段从 `b.balance` 取（None 时各字段为 0）
- `sort_field_map`：`total_amount`/`used_total` 改为 `func.coalesce(CustomerBalance.xxx, 0)`

### 2.2 package_remaining CTE（Step 5/6 共用）

```sql
SELECT cid, base_fee - consumed AS remaining, expiry_date FROM (
  SELECT pr.customer_id AS cid,
         CAST(pr.package_limits->>'base_fee' AS NUMERIC(12,2)) AS base_fee,
         pr.expiry_date,
         COALESCE(SUM(dc.total_cost), 0) AS consumed,
         ROW_NUMBER() OVER (PARTITION BY pr.customer_id ORDER BY pr.created_at DESC) AS rn
  FROM pricing_rules pr
  LEFT JOIN daily_consumptions dc ON dc.pricing_rule_id = pr.id AND dc.deleted_at IS NULL
  WHERE pr.pricing_type = 'package' AND pr.deleted_at IS NULL
    AND pr.effective_date <= now() AND (pr.expiry_date >= now() OR pr.expiry_date IS NULL)
  GROUP BY pr.customer_id, pr.package_limits, pr.expiry_date, pr.created_at
) t WHERE rn = 1
```

- 窗口函数保证与 Python 层「最新一条」语义一致（防异常多生效规则）
- 筛选：`COALESCE(package_remaining.remaining, CustomerBalance.total_amount, 0)` 参与 min/max
- 排序：`total_amount` 用同一 COALESCE 表达式
- `days_remaining` 排序：CASE 增加包年分支（`package_remaining.cid IS NOT NULL` 时用 `CAST(expiry_date AS DATE) - CURRENT_DATE` 天数差；expiry_date 为 NULL 时返回 NULL 排最后）

### 2.3 _batch_query_package_info（Step 2）

紧邻 `_batch_query_consumption_stats` 之后。返回 `{customer_id: {...}}`：

1. 生效规则（每客户最新一条）：`PricingRule.customer_id IN (...) + pricing_type='package' + effective_date <= utc_now + (expiry_date >= utc_now OR NULL) + deleted_at IS NULL`，`ORDER BY customer_id, created_at DESC`
2. 消费聚合：`SELECT pricing_rule_id, SUM(total_cost), SUM(order_count) FROM daily_consumptions WHERE pricing_rule_id IN (rule_ids) AND deleted_at IS NULL GROUP BY pricing_rule_id`
3. 过期判断：无生效规则但 `Customer.price_policy='yearly'` 的客户，查是否存在已过期包年规则（`expiry_date < utc_now`），有则 `is_expired=True`，`remaining_amount=0`
4. 计算：`base_fee = package_limits.get('base_fee', 0)`；`remaining_amount = max(base_fee - consumed, 0)`；限量：`remaining_count = max(limit_count - consumed_count, 0)`；不限量：`remaining_count = None`

### 2.4 燃尽计算（Step 4）

`_compute_burn_down` 增加 `package_info` 入参：

- 有效包年（`is_package` 且未过期）：`days_remaining = (expiry.astimezone(CST).date() - date.today()).days`（下限 0），`daily_avg_cost=None`，`consumption_days=0`
- 过期包年：`days_remaining=0`
- 其余保持原预付费/后付费逻辑

### 2.5 KPI 统计（Step 7）

`get_balance_stats` 三处适配，均改 Customer 驱动 + outerjoin CustomerBalance（deleted_at 移入 ON）+ LEFT JOIN package_remaining CTE：

- `_balance_totals("prepaid")`：`SUM(COALESCE(package_remaining.remaining, CustomerBalance.total_amount, 0))`，`count(Customer.id)`
- `low_balance_count`：`COALESCE(package_remaining.remaining, CustomerBalance.total_amount, 0) < 10000`
- `burning_soon_count`：CASE 包年分支（到期 ≤ 7 天）接入 `burning_soon_days_expr`
- `apply_balance_filters` 移除 `CustomerBalance.deleted_at.is_(None)`（改由各语句 outerjoin ON 携带）

### 2.6 导出（Step 8）

`_build_excel` 增加三列：套餐剩余额度（元）`package_remaining_amount`、套餐剩余次数 `package_remaining_count`（不限量显示「不限」）、套餐到期日期 `package_expiry_date`（UTC→CST 日期串）。

### 2.7 行组装字段（Step 3）

```python
"price_policy": b.price_policy if b else None,
"is_package": bool(pkg_info),                      # 有包年规则信息（含过期）
"package_remaining_amount": pkg_info["remaining_amount"] if pkg_info else None,
"package_remaining_count": pkg_info["remaining_count"] if pkg_info else None,
"package_base_fee": pkg_info["base_fee"] if pkg_info else None,
"package_limit_count": pkg_info["limit_count"] if pkg_info else None,
"package_is_unlimited": pkg_info["is_unlimited"] if pkg_info else None,
"package_expired": pkg_info["is_expired"] if pkg_info else False,
"package_expiry_date": pkg_info["expiry_date"] 的 CST 日期串 if ...,
"total_amount": package_remaining_amount if 包年(未过期) else (0 if 过期 else 原值),
```

`real_amount`/`bonus_amount` 保持 CustomerBalance 原值。

## 3. 前端设计（Step 9-11）

- `Balance` 接口新增 9 个可选字段（price_policy / is_package / package_remaining_amount / package_remaining_count / package_base_fee / package_limit_count / package_is_unlimited / package_expired / package_expiry_date）
- 余额列：`!is_package` 走原展示；`is_package` 走双值：`¥{package_remaining_amount}` + 过期灰标签 / 不限量蓝标签 + 明细行（额度 + 次数）
- 燃尽列：postpaid 灰标签 → `package_expired` 灰标签 → `is_package` 到期进度条（辅助函数 `getPackageBurnFillPct`/`getPackageBurnBarClass`/`getPackageBurnLabel`/`getPackageBurnTooltip`）→ 原预付费
- 行高亮：复用后端 `days_remaining`（包年客户即到期天数），`isBurningSoon`/`isBurningWarn` 无需改动

## 4. 边界与假设

| 假设 | 应对 |
|---|---|
| `DailyConsumption.pricing_rule_id` 正确指向包年规则 | 按 pricing_rule_id 聚合；若为空则无法精确关联（历史数据缺失，标注不处理，Plan 备选方案：回退 customer_id + 日期范围聚合，因实现复杂度高且数据影响面未知，仅在本实现按 pricing_rule_id 处理并在导出/展示无差异时接受） |
| 包年年费不进 CustomerBalance | 若混充，展示以 `package_remaining_amount` 为准（Plan 口径）；tooltip 不额外展示（前端燃尽 tooltip 已含到期信息） |
| `Customer.balance` 反向关系 | 已确认存在（customers.py:80） |
| 同客户多条生效包年规则（异常数据） | SQL CTE 与 Python 层均按 `created_at DESC` 取最新一条 |

## 5. 回归保护

- 非包年客户路径不变：COALESCE 退化为 CustomerBalance 原值；`is_package=False` 时前端走原模板
- 现有 `test_balance_filters.py`（_query_balance_rows_raw WHERE 组装）需同步更新
