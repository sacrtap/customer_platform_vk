# Implement Plan: 余额燃尽列

## Execution Checklist

### Phase A: Backend — API Extension (P0)

- [ ] A1. **`backend/app/cache/base.py`**: Add `"billing_consumption": 300` to `_ttl_config`
- [ ] A2. **`backend/app/routes/billing/balances.py`**: Add consumption stats query to `get_balances`
  - Build helper function `_batch_query_consumption_stats(db, customer_ids) -> dict`
  - Query: `SELECT customer_id, SUM(total_cost), COUNT(DISTINCT consumption_date) FROM daily_consumptions WHERE customer_id IN (...) AND consumption_date >= 30d_ago AND deleted_at IS NULL GROUP BY customer_id`
  - Add L1 cache read (MGET) + write-back for misses
  - Compute `daily_avg_cost`, `consumption_days`, `days_remaining` per record
  - Postpaid customers → all null
  - Add three fields to response JSON
- [ ] A3. **`backend/app/routes/billing/balances.py`**: Add `days_remaining` to `sort_field_map`
  - When `sort_by == 'days_remaining'`: use CTE approach (all matching customers)
  - `ORDER BY days_remaining ASC NULLS LAST`
  - Non-sorted: lightweight query (current page only)
- [ ] A4. **`backend/app/routes/billing/balances.py`**: Add `burning_soon_count` to `get_balance_stats`
  - Count customers where `days_remaining ≤ 7` (needs same CTE logic)
  - Add `"burning_soon_count": N` to response
- [ ] A5. **Validation**: `cd backend && ruff check app/routes/billing/balances.py app/cache/base.py`

### Phase B: Backend — Cache Invalidation (P1)

- [ ] B1. **`backend/app/services/sync_task_service.py`**: In `complete_task()` (or equivalent), add `await cache_service.invalidate_pattern("cache:billing_consumption:*")` after sync completes
- [ ] B2. **`backend/app/routes/billing/balances.py`**: In `recharge` route, add `await cache_service.invalidate_pattern("cache:billing_balances:*")` (for future L2)
- [ ] B3. **Validation**: `cd backend && ruff check app/services/sync_task_service.py`

### Phase C: Backend — Home Page Fix (P2)

- [ ] C1. **`backend/app/routes/analytics.py`**: Fix `getPriorityCustomers` `balance_days` calculation
  - Replace `daily_avg = max(total / 30, 1)` with real consumption data query
  - Use `real_amount + bonus_amount` as remaining balance
  - Use same 30-day window + max(consumption_days, 7) formula
- [ ] C2. **Validation**: `cd backend && ruff check app/routes/analytics.py`

### Phase D: Frontend — Type Extension (P0)

- [ ] D1. **`frontend/src/api/billing.ts`**: Add three fields to `Balance` interface
  ```typescript
  daily_avg_cost: number | null
  consumption_days: number
  days_remaining: number | null
  ```
- [ ] D2. **`frontend/src/api/billing.ts`**: Add `burning_soon_count` to `BalanceStats` interface
- [ ] D3. **`frontend/src/composables/useBalance.ts`**: Add `burning_soon_count` to stats reactive object

### Phase E: Frontend — BurnDownBar Component (P1)

- [ ] E1. **`frontend/src/views/billing/components/BalanceTable.vue`**: Merge columns
  - Remove `trend` and `depletion` from `columns` array
  - Add `{ key: 'burn_down', title: '余额燃尽', sortable: true }` column
- [ ] E2. **`frontend/src/views/billing/components/BalanceTable.vue`**: Replace trend cell + depletion cell with burn-down cell
  - Burn-down progress bar (fill = remaining, empty = exhausted)
  - Core text: "剩余 X天" / "已耗尽" / "无消耗" / ">60天" / "今日耗尽" / "后付费"
  - Tooltip with daily_avg, consumption_days, last_recharge info
  - Coverage <50% → color downgrade + ⚠️ icon
- [ ] E3. **`frontend/src/views/billing/components/BalanceTable.vue`**: Remove old helper functions
  - Delete: `getUtilization`, `getDailyAvg`, `getDaysLeft`, `getDaysSinceRecharge`, `getUtilBarClass`, `getUtilTextClass`, `getTrendArrowIcon`, `getTrendArrowClass`, `getTrendTooltip`, `getDepletionLabel`, `getDepletionTagClass`
  - Add: `getBurnFillPct`, `getBurnBarClass`, `getBurnTextClass`, `getBurnLabel`, `getBurnTooltip`
- [ ] E4. **`frontend/src/views/billing/components/BalanceTable.vue`**: Update row highlight logic
  - `isLowBalance` → `isBurningSoon`: `days_remaining != null && days_remaining <= 7`
  - Add `isBurningWarn`: `days_remaining != null && days_remaining > 7 && days_remaining <= 30`
  - CSS: `.row-warning` for ≤7, `.row-warn` for ≤30
- [ ] E5. **`frontend/src/views/billing/components/BalanceTable.vue`**: Update CSS
  - Rename `.trend-cell` → `.burn-cell`
  - Rename `.util-bar` → `.burn-bar`
  - Rename `.util-fill` → `.burn-fill`
  - Add `.burn-bar.no-data .burn-fill { background: #cbd5e1; }` (gray)
  - Add `.burn-bar.postpaid` style (hidden bar, show tag)
  - Keep `.safe`/`.warn`/`.danger` color classes
- [ ] E6. **`frontend/src/views/billing/components/BalanceTable.vue`**: Add `burn_down` to sort field mapping
  - In `toggleSort`, map `burn_down` → emit `sortChange` with `days_remaining`

### Phase F: Frontend — KPI Card (P2)

- [ ] F1. **`frontend/src/views/billing/Balance.vue`**: Add "即将耗尽" KPI card
  - Between "余额不足" and "零余额客户"
  - Value: `stats.burning_soon_count`
  - Trend: "需立即充值"
  - Trend-type: "warn"
  - Click filter: set `filters.balance_range` to a new value or custom filter
- [ ] F2. **`frontend/src/views/billing/Balance.vue`**: Add KPI filter logic for "即将耗尽"
  - `activeKpi` type: add `'burning'`
  - `applyKpiFilter('burning')`: needs backend filter support or client-side filter on `days_remaining`
  - Simplest: pass `balance_range=burning` to backend, or add `days_remaining_max=7` param
- [ ] F3. **`frontend/src/composables/useBalance.ts`**: Add `burning` to `activeKpi` type and `kpiBadgeText`

### Phase G: Validation & Testing

- [ ] G1. **Backend lint**: `cd backend && ruff check app/`
- [ ] G2. **Frontend type-check**: `cd frontend && pnpm type-check`
- [ ] G3. **Frontend lint**: `cd frontend && pnpm lint` (if configured)
- [ ] G4. **Manual test**: Start dev servers, verify:
  - Balance list shows burn-down column with correct colors
  - Sorting by days_remaining works
  - Postpaid customers show "后付费" tag
  - Tooltip shows consumption details
  - KPI "即将耗尽" shows correct count
  - Row highlighting works (≤7 red, ≤30 yellow)
  - Home page priority customers show non-30 balance_days

## Validation Commands

```bash
# Backend
cd backend && ruff check app/routes/billing/balances.py app/cache/base.py app/services/sync_task_service.py app/routes/analytics.py

# Frontend
cd frontend && pnpm type-check
```

## Review Gates

1. **After Phase A+B**: Backend API returns correct data → test with curl/Postman
2. **After Phase D+E**: Frontend renders burn-down column → visual verification
3. **After Phase F**: KPI card + filter works → end-to-end test
4. **After Phase G**: All lint/type checks pass → ready for commit

## Rollback Points

- After A: Revert `balances.py` (API returns without new fields, frontend uses `?? null`)
- After E: Revert `BalanceTable.vue` (two-column layout, API ignores extra fields)
- No schema migration → no DB rollback needed
