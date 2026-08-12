# Design: 余额燃尽列技术设计

## Architecture Overview

```
┌─ Frontend ─────────────────────────────────────────────────────┐
│  Balance.vue                                                    │
│    ├─ KpiCard "即将耗尽" (days_remaining ≤ 7)                   │
│    └─ BalanceTable.vue                                          │
│         ├─ Column: 余额燃尽 (merged from 趋势 + 预计耗尽)       │
│         │    ├─ BurnDownBar (progress bar, 油表隐喻)            │
│         │    ├─ days_remaining text                             │
│         │    └─ tooltip (daily_avg, consumption_days, ...)      │
│         ├─ Row highlight: days_remaining ≤7 red / ≤30 yellow    │
│         └─ Sort: days_remaining ASC NULLS LAST                  │
│                                                                  │
│  API types: Balance interface + 3 new fields                    │
└──────────────────────────────────────────────────────────────────┘
                            ↕ HTTP
┌─ Backend ──────────────────────────────────────────────────────┐
│  GET /billing/balances                                          │
│    ├─ Existing query (CustomerBalance JOIN Customer ...)        │
│    ├─ NEW: CTE consumption_stats                                │
│    │    SELECT customer_id,                                     │
│    │           SUM(total_cost) as total_cost_30d,               │
│    │           COUNT(DISTINCT consumption_date) as consumption_days │
│    │    FROM daily_consumptions                                 │
│    │    WHERE consumption_date >= CURRENT_DATE - 30             │
│    │    GROUP BY customer_id                                    │
│    ├─ NEW: Redis MGET batch read (L1 cache)                     │
│    ├─ NEW: SQL batch query for cache misses                     │
│    ├─ NEW: Compute daily_avg, days_remaining in Python          │
│    └─ Response: +3 fields per record                            │
│                                                                  │
│  GET /billing/balance-stats                                     │
│    └─ NEW: Count days_remaining ≤ 7 for "即将耗尽" KPI          │
│                                                                  │
│  GET /analytics/priority-customers                              │
│    └─ FIX: balance_days calculation                             │
│                                                                  │
│  Cache: cache_service (existing Redis singleton)                │
│    ├─ L1: billing_consumption:{customer_id}:{date} TTL 300s     │
│    └─ Invalidation: sync task complete → invalidate L1          │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Balance List Query Flow

```
Request: GET /billing/balances?page=1&page_size=20&sort_by=days_remaining&sort_order=asc
  │
  ├─ 1. Build base query (existing): CustomerBalance JOIN Customer JOIN CustomerProfile
  │     Apply filters (keyword, industry, etc.)
  │
  ├─ 2. If sort_by == 'days_remaining':
  │     Build CTE: consumption_stats (all matching customers, 30-day aggregation)
  │     LEFT JOIN CTE to base query
  │     ORDER BY days_remaining ASC NULLS LAST
  │   Else:
  │     Execute base query with existing sort → get current page customer_ids
  │     Build CTE: consumption_stats WHERE customer_id IN (current_page_ids)
  │
  ├─ 3. Execute paginated query → get balances list
  │
  ├─ 4. Extract customer_ids from result
  │
  ├─ 5. L1 Cache read:
  │     keys = [f"billing_consumption:{cid}:{today}" for cid in customer_ids]
  │     cached = await redis.mget(keys)
  │     hit_map = {cid: data for cid, data in zip(customer_ids, cached) if data}
  │     missed_ids = [cid for cid in customer_ids if cid not in hit_map]
  │
  ├─ 6. For missed_ids:
  │     SQL: SELECT customer_id, SUM(total_cost), COUNT(DISTINCT consumption_date)
  │          FROM daily_consumptions
  │          WHERE customer_id IN (missed_ids) AND consumption_date >= 30d_ago
  │          GROUP BY customer_id
  │     Write back to Redis (individual SETEX or pipeline)
  │
  ├─ 7. For each balance record:
  │     stats = hit_map.get(cid) or sql_result.get(cid)
  │     if customer.settlement_type == 'postpaid':
  │         daily_avg_cost = None, consumption_days = 0, days_remaining = None
  │     elif stats:
  │         daily_avg = stats.total_cost_30d / max(stats.consumption_days, 7)
  │         remaining = balance.real_amount + balance.bonus_amount
  │         days_remaining = floor(remaining / daily_avg) if daily_avg > 0 else None
  │     else:
  │         daily_avg_cost = None, consumption_days = 0, days_remaining = None
  │
  └─ 8. Response: existing fields + daily_avg_cost, consumption_days, days_remaining
```

### 2. Sort by days_remaining — SQL Strategy

When sorting by `days_remaining`, the CTE must cover ALL matching customers (not just current page), because the sort happens before pagination.

```sql
WITH consumption_stats AS (
    SELECT customer_id,
           SUM(total_cost) as total_cost_30d,
           COUNT(DISTINCT consumption_date) as consumption_days
    FROM daily_consumptions
    WHERE consumption_date >= CURRENT_DATE - INTERVAL '30 days'
      AND deleted_at IS NULL
    GROUP BY customer_id
)
SELECT cb.*,
       cs.total_cost_30d,
       cs.consumption_days,
       CASE
         WHEN c.settlement_type = 'postpaid' THEN NULL
         WHEN cs.total_cost_30d IS NULL OR cs.total_cost_30d = 0 THEN NULL
         ELSE (cb.real_amount + cb.bonus_amount) /
              (cs.total_cost_30d / GREATEST(cs.consumption_days, 7))
       END as days_remaining
FROM customer_balances cb
JOIN customers c ON cb.customer_id = c.id
LEFT JOIN consumption_stats cs ON cs.customer_id = cb.customer_id
WHERE cb.deleted_at IS NULL AND c.deleted_at IS NULL
  -- + filter conditions
ORDER BY days_remaining ASC NULLS LAST
LIMIT 20 OFFSET 0
```

**Note**: The `days_remaining` in SQL is a float for sorting purposes. The integer `days_remaining` in the API response is computed in Python (`floor()`).

### 3. Non-sorted Query — Lightweight CTE

When NOT sorting by `days_remaining`, only query current page customers:

```sql
-- Step 1: Existing paginated query (no CTE needed)
SELECT cb.* FROM customer_balances cb JOIN customers c ON ...
ORDER BY <existing sort> LIMIT 20 OFFSET 0

-- Step 2: Batch consumption query for current page only
SELECT customer_id,
       SUM(total_cost) as total_cost_30d,
       COUNT(DISTINCT consumption_date) as consumption_days
FROM daily_consumptions
WHERE customer_id IN (1, 2, 3, ..., 20)
  AND consumption_date >= CURRENT_DATE - INTERVAL '30 days'
  AND deleted_at IS NULL
GROUP BY customer_id
```

### 4. L1 Cache Strategy

**Key format**: `cache:billing_consumption:{customer_id}:{YYYY-MM-DD}`
- Date component ensures daily rotation (no need to invalidate on date change)
- Value: `{"total_cost_30d": 96000.0, "consumption_days": 18}`

**Read flow**:
```python
# Build keys for current page
today = date.today().isoformat()
keys = [f"cache:billing_consumption:{cid}:{today}" for cid in customer_ids]

# MGET batch read
redis = await cache_service._get_redis()
values = await redis.mget(keys)

# Parse hits
hit_map = {}
missed_ids = []
for cid, val in zip(customer_ids, values):
    if val is not None:
        hit_map[cid] = json.loads(val)
    else:
        missed_ids.append(cid)
```

**Write flow** (for missed_ids):
```python
# SQL batch query for missed
stats_map = await _batch_query_consumption(missed_ids, db)

# Write back to Redis
for cid, stats in stats_map.items():
    key = f"cache:billing_consumption:{cid}:{today}"
    await redis.setex(key, 300, json.dumps(stats, default=str))
```

**Invalidation**:
- In `sync_task_service.py` `complete_task()` → `await cache_service.invalidate_pattern("cache:billing_consumption:*")`
- Natural expiry: 5 min TTL

## API Contract

### `GET /billing/balances` Response (Extended)

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "customer_id": 42,
        "company_id": 1001,
        "customer_name": "测试客户A",
        "account_type": "正式账号",
        "industry_type": "房产",
        "settlement_type": "prepaid",
        "is_key_customer": false,
        "total_amount": 100000.0,
        "real_amount": 35000.0,
        "bonus_amount": 5000.0,
        "used_total": 60000.0,
        "used_real": 55000.0,
        "used_bonus": 5000.0,
        "last_recharge_at": "2026-07-15T10:30:00",
        "daily_avg_cost": 3200.0,
        "consumption_days": 18,
        "days_remaining": 12
      },
      {
        "id": 2,
        "customer_id": 43,
        "settlement_type": "postpaid",
        "total_amount": 0.0,
        "real_amount": 0.0,
        "bonus_amount": 0.0,
        "daily_avg_cost": null,
        "consumption_days": 0,
        "days_remaining": null
      }
    ],
    "total": 150,
    "page": 1,
    "page_size": 20
  }
}
```

### `GET /billing/balance-stats` Response (Extended)

```json
{
  "code": 0,
  "data": {
    "total_balance": 5000000.0,
    "total_customers": 150,
    "this_month_count": 12,
    "this_month_amount": 500000.0,
    "this_month_real_amount": 400000.0,
    "this_month_bonus_amount": 100000.0,
    "low_balance_count": 15,
    "zero_balance_count": 3,
    "burning_soon_count": 8
  }
}
```

### Sort Parameter

- `sort_by=days_remaining` → SQL CTE + ORDER BY days_remaining ASC NULLS LAST
- Existing sort fields unchanged

## Frontend Component Design

### BalanceTable.vue — Column Definition Change

```typescript
// Before (8 columns):
const columns = [
  { key: 'company_id', title: '客户ID', sortable: true },
  { key: 'customer_name', title: '客户名称', sortable: true },
  { key: 'industry_type', title: '行业' },
  { key: 'total_amount', title: '余额', sortable: true },
  { key: 'trend', title: '趋势' },           // ← REMOVE
  { key: 'depletion', title: '预计耗尽' },    // ← REMOVE
  { key: 'used_total', title: '已消耗', sortable: true },
  { key: 'last_recharge_at', title: '最新充值', sortable: true },
]

// After (7 columns):
const columns = [
  { key: 'company_id', title: '客户ID', sortable: true },
  { key: 'customer_name', title: '客户名称', sortable: true },
  { key: 'industry_type', title: '行业' },
  { key: 'total_amount', title: '余额', sortable: true },
  { key: 'burn_down', title: '余额燃尽', sortable: true },  // ← NEW (merged)
  { key: 'used_total', title: '已消耗', sortable: true },
  { key: 'last_recharge_at', title: '最新充值', sortable: true },
]
```

### Burn-down Cell Template

```html
<td>
  <!-- Postpaid: show tag -->
  <span v-if="record.settlement_type === 'postpaid'" class="tag gray">后付费</span>
  <!-- Burn-down visualization -->
  <div v-else class="burn-cell">
    <div class="burn-bar" :class="getBurnBarClass(record)" :title="getBurnTooltip(record)">
      <div class="burn-fill" :style="{ width: getBurnFillPct(record) + '%' }"></div>
    </div>
    <span class="burn-text" :class="getBurnTextClass(record)">
      {{ getBurnLabel(record) }}
    </span>
  </div>
</td>
```

### Burn-down Logic

```typescript
const BURN_MAX_DAYS = 60

const getBurnFillPct = (record: Balance): number => {
  if (record.days_remaining == null) return 100  // no consumption → full gray
  if (record.days_remaining <= 0) return 0        // exhausted → empty red
  return Math.min((record.days_remaining / BURN_MAX_DAYS) * 100, 100)
}

const getBurnBarClass = (record: Balance): string => {
  if (record.settlement_type === 'postpaid') return 'postpaid'
  if (record.days_remaining == null) return 'no-data'
  if (record.days_remaining <= 0) return 'danger'
  if (record.days_remaining <= 7) return 'danger'
  if (record.days_remaining <= 30) return 'warn'
  // Coverage degradation
  if (record.consumption_days < 15) return 'warn'  // <50% coverage → downgrade
  return 'safe'
}

const getBurnLabel = (record: Balance): string => {
  if (record.days_remaining == null) return '无消耗'
  if (record.days_remaining <= 0) return '已耗尽'
  if (record.days_remaining < 1) return '今日耗尽'
  if (record.days_remaining > BURN_MAX_DAYS) return '>60天'
  return `剩余 ${Math.floor(record.days_remaining)}天`
}
```

### API Type Extension

```typescript
// frontend/src/api/billing.ts
export interface Balance {
  // ... existing fields ...
  settlement_type?: string
  daily_avg_cost: number | null
  consumption_days: number
  days_remaining: number | null
}
```

## Tradeoffs

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Compute location | Backend | Frontend | Sort support + single source of truth |
| Time window | 30 days | 7 days | Dilutes sync gaps, gives earlier warning |
| Min denominator | 7 | 1 or 30 | Prevents 1-day spike from skewing avg |
| Progress metaphor | Fill = remaining | Fill = used | "Fuel gauge" matches operator mental model |
| Max scale | 60 days | 90 days | Resolution concentrated in actionable range |
| Cache layer | L1 per-customer | L2 per-page | L1 is filter-independent, higher hit rate |

## Rollback

- **Backend**: Revert `get_balances` route to original (remove CTE + new fields). Frontend gracefully handles missing fields with `?? null` defaults.
- **Frontend**: Revert `BalanceTable.vue` to two-column layout. API ignores extra fields.
- **No schema changes** → no migration rollback needed.
- **Redis cache keys** self-expire in 5 minutes.
