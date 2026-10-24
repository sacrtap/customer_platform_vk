# 结算单详情"用量总计"改为按单数（order_count）汇总

## Context

结算单详情抽屉（`InvoiceDetailDrawer.vue`）计费明细表格底部的"用量总计"行，预期按**单数**（订单数 / `order_count`）显示，当前实现对 `item.quantity` 求和，而 `quantity` 字段在不同计费类型下口径不一致（有的是楼层数、有的是单数），导致总计混入楼层数、不符合预期。

根因：后端 `calculate_items_from_rules` 在 `fixed`（统一模式）与 `tiered` 两个分支的 item 里**漏填 `order_count`**；前端 `totalUsage` 又只对 `quantity` 求和。`quantity` 口径分布：

| 计费类型 | quantity | order_count | 后端行号 |
|---|---|---|---|
| package-unlimited | 楼层数 | 单数（已有） | 1156-1170 |
| package-limited | 单数 | 单数（已有） | 1182-1200 / 1222-1241 |
| fixed 统一 | 单数 | **缺失** | 1294-1304 |
| fixed 多层递增 | 楼层数 | 单数（已有） | 1277-1290 |
| tiered | 楼层数 | **缺失** | 1316-1327 |

预期终态：详情页"用量总计"= 各明细 `order_count`（单数）之和；无明细不渲染。

## Approach

### 行为 1：后端补全 item 的 order_count（单数口径）

`backend/app/services/billing.py` `calculate_items_from_rules`，为两个漏填分支补 `"order_count": total_quantity`（`total_quantity` 即该 device_type+layer_type 分组的 `SUM(order_count)`，单数，usage 查询第 1094 行已聚合好）：

- **fixed 统一模式** item（约 1294-1304）：在 dict 内追加 `"order_count": total_quantity,`（与 `quantity` 同值，因为该模式 quantity 本就是单数）。
- **tiered** item（约 1316-1327）：在 dict 内追加 `"order_count": total_quantity,`（与 `quantity`=total_floor_count 不同值）。

其余三分支（package 两分支、fixed 多层递增）已有 `order_count`，不动。

详情接口（`invoices.py:285-317`）与预览路由（`invoices.py:476-507`）的序列化已对 `order_count` 做 `float(...) if item.get("order_count") is not None else None` 透传，补全后自动带出，无需改路由。

> 副作用（预期、正向）：`tiered` 用量列原先因无 `order_count` 走 `formatQuantity` 第 38 行回退、只显示楼层数；补全后 `order_count`(单数) ≠ `quantity`(楼层)，触发第 34 行，显示为「X 单 / Y 层」两行，与多层递增一致、信息更完整。`fixed` 统一因 `order_count`==`quantity` 不触发两行、显示不变。

### 行为 2：前端总计改按 order_count 求和

`frontend/src/views/billing/components/InvoiceDetailDrawer.vue` 第 337-339 行 `totalUsage` computed，把求和基准从 `i.quantity` 改为 `i.order_count ?? i.quantity`：

```ts
const totalUsage = computed(() =>
  (props.invoice?.items || []).reduce(
    (s, i) => s + (Number(i.order_count ?? i.quantity) || 0),
    0
  )
)
```

`?? i.quantity` 回退仅防御历史结算单（DB 不存 order_count、详情走实时重算，理论上总有；保留以防异常）。`formatItemNumber`（已 import）继续负责整数/小数格式化，不变。

### 行为 3：后端测试补 order_count 断言 + 新增 tiered 用例

`backend/tests/unit/test_billing_service.py`：

- `test_calculate_items_fixed_unified_multi`（1306-1345）：补 `assert items[0]["order_count"] == Decimal("2")`（total_quantity=2）。
- `test_calculate_items_fixed_incremental`（1260-1304）：补 `assert items[0]["order_count"] == Decimal("1")`（已有 order_count，新增断言固化）。
- 新增 `test_calculate_items_tiered_has_order_count`：参照 `test_calculate_items_fixed_unified_multi` 结构，`usage_row.total_quantity=150`、`total_floor_count=200`，`mock_rule.pricing_type="tiered"` + 有效 `tiers`（格式参照 `normalize_tiers`，实现时读其定义取合法阶梯），断言 `item["order_count"] == Decimal("150")`（单数）且 `item["quantity"] == Decimal("200")`（楼层数，计价基准不变）。

### 行为 4：前端测试改断言 + 新增混合计费类型用例

`frontend/src/views/billing/components/__tests__/InvoiceDetailDrawer.usageTotal.test.ts`：

- 现有两用例（447 / 2.5）的 items 补 `order_count` 字段、值 = quantity（反映 fixed 统一模式后端真实输出，使求和真正走 `order_count` 分支而非回退），断言数值不变。
- 新增「混合计费类型按单数汇总」用例：items =
  - fixed 多层递增 `{ pricing_type:'fixed', quantity:100, order_count:80 }`（100 层 / 80 单）
  - tiered `{ pricing_type:'tiered', quantity:200, order_count:150 }`（200 层 / 150 单）
  - package-unlimited `{ pricing_type:'package', package_type:'unlimited', quantity:50, order_count:30 }`（50 层 / 30 单）
  - 断言 tfoot 文本含 `260`（80+150+30，单数），**不含** `350`（100+200+50，楼层数和）。

## Critical files & anchors

- `backend/app/services/billing.py` — `calculate_items_from_rules`：fixed 统一 item ~1294-1304、tiered item ~1316-1327 各补 `order_count: total_quantity`；usage 聚合在 ~1094（total_quantity=单数、total_floor_count=楼层数，已就绪）。
- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` — `totalUsage` computed 337-339 改基准；tfoot 模板 179-185 不变。
- `frontend/src/utils/invoiceFormatters.ts` — `formatQuantity` 30-39：tiered 补 order_count 后自动变两行，**不改此文件**，仅为副作用知晓点。
- `backend/app/routes/billing/invoices.py` — 详情接口 285-317、预览 476-507：序列化已透传 order_count，**不改**，仅为确认点。
- 测试：`backend/tests/unit/test_billing_service.py`（1260-1345 区）与 `frontend/src/views/billing/components/__tests__/InvoiceDetailDrawer.usageTotal.test.ts`。

## Verification

前置：后端 `backend/.venv`（Python 3.12）、前端 `pnpm` 依赖已就绪。

1. **后端单测**（行为 1/3）：
   ```bash
   cd backend && .venv/bin/python -m pytest tests/unit/test_billing_service.py -k "calculate_items" -q
   ```
   全绿，含新 tiered 用例与 order_count 断言。
2. **前端组件测试**（行为 2/4）：
   ```bash
   cd frontend && npx vitest run src/views/billing/components/__tests__/InvoiceDetailDrawer.usageTotal.test.ts
   ```
   全绿，混合用例断言含 `260`。
3. **端到端（浏览器，行为 1+2 联动）**：打开一个含混合计费类型（如 fixed 多层递增 + tiered）的 completed 结算单详情抽屉 → 计费明细表格底部"用量总计"值 = 各行单数（order_count）之和，而非楼层数之和；对照各行"用量"列显示的单数相加一致。
4. **回归**：`cd backend && .venv/bin/python -m pytest tests/unit/test_billing_service.py tests/integration/test_billing_api.py -q` 与 `cd frontend && npx vitest run` 全绿（现有 quantity 口径断言 fixed 统一 quantity==单数 不受影响）。

## Assumptions & contingencies

- 「单数」= `order_count` = `SUM(DailyConsumption.order_count)`（订单数/套数），与 spec `analytics-forecast.md`「正确用量口径 = order_count（套数）」一致。若实际业务口径另有所指，需用户确认后调整求和字段。
- tiered 用量列变两行（单/层）视为正向副作用、保留；若产品要求 tiered 用量列保持只显示楼层数，则在 `formatQuantity` 对 tiered 单独绕过 order_count 检查（届时反馈再定）。
- 历史结算单详情走实时重算（`calculate_items_from_rules`），补全后即生效，无需数据迁移；若发现某详情接口读 DB 而非重算（与 invoices.py:272 注释矛盾），则回退为前端 `?? quantity` 兜底并补充后端持久化——目前 272 行确认是重算路径。
