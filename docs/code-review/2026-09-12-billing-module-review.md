# 代码审查报告 — 计费模块优化

**日期**: 2026-09-12
**工具**: open-code-review (`ocr`)
**范围**: 22 个文件（暂存 + 未暂存 + 未跟踪变更）
**LLM**: qwen3.7-plus（bifrost 网关）
**审查耗时**: 约 32 分钟
**发现问题**: 1 个严重、2 个高、5 个中、10 个低
**已修复**: 18/18（全部问题已修复）

---

## 审查文件清单

### 后端（6 个文件）
- `backend/app/models/billing.py`
- `backend/app/routes/billing/balances.py`
- `backend/app/routes/billing/packages.py`
- `backend/app/services/billing.py`
- `backend/tests/unit/test_billing_service.py`
- `backend/alembic/versions/s8t9u0v1w2x3_over_limit_unit_price_null_semantics.py`

### 前端（16 个文件）
- `frontend/src/api/billing.ts`
- `frontend/src/components/invoice/InvoiceStatusBadge.vue`
- `frontend/src/components/ui/Pagination.vue`
- `frontend/src/composables/useBalance.ts`
- `frontend/src/composables/useInvoice.ts`
- `frontend/src/constants/invoiceStatus.ts`
- `frontend/src/utils/invoiceFormatters.ts`
- `frontend/src/views/billing/Invoices.vue`
- `frontend/src/views/billing/PackagePlans.vue`
- `frontend/src/views/billing/PricingRules.vue`
- `frontend/src/views/billing/components/BalanceBatchToolbar.vue`
- `frontend/src/views/billing/components/BalanceTable.vue`
- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`
- `frontend/src/views/billing/components/InvoiceFilters.vue`
- `frontend/src/views/billing/components/PricingRuleModal.vue`
- `frontend/src/views/customers/detail/CustomerInvoicesTab.vue`

---

## 业务背景

本次计费模块优化涵盖：
1. `over_limit_unit_price` NULL 语义 — NULL 表示结算时自动按 `base_fee/limit_count` 计算，不再存储计算值
2. `InvoiceService` 套餐内用量 = `min(total_quantity, limit_count)`，套餐内费用不再超出上限
3. 余额惰性补建使用 `try-except + flush` 保证高并发下的唯一索引安全
4. 套餐删除前检查关联计费规则，存在则阻止删除
5. 前端计费视图重构 — 抽取 composables、组件、常量，减小视图文件体积

---

## 问题与修复

### 严重（1 个）

#### 1. `limit_count` 为 0 且 `over_limit_unit_price` 为 NULL 时触发 ZeroDivisionError

- **文件**: `backend/app/services/billing.py:1080-1086`
- **类型**: bug
- **描述**: 当 `limit_count` 为 0 且 `raw_price` 为 `None`（或 <= 0）时，`base_fee / limit_count` 会触发 `ZeroDivisionError`，因为 `limit_count <= 0` 的保护检查位于除法之后。
- **修复**: 将 `limit_count <= 0` 的提前返回块移到 `over_limit_unit_price` 计算之前。在提前返回块内设置 `over_limit_unit_price = Decimal(0)`，因为费用为 0。`over_limit_unit_price` 的自动计算（`base_fee / limit_count`）现在仅在 `limit_count > 0` 时执行。
- **状态**: 已修复

---

### 高（2 个）

#### 2. KPI「余额不足」计数与筛选范围不一致

- **文件**: `frontend/src/composables/useBalance.ts:42`
- **类型**: bug
- **描述**: KPI 卡片显示后端 `low_balance_count`（统计 `total_amount < 10000` 的全部客户，含欠费/零余额）。但点击该卡片设置 `filters.balance_range = 'low'`，其 `min: 0.01` 排除了欠费和零余额客户，导致 KPI 数字（如 50）与筛选列表数（如 30）不匹配。
- **修复**: 将 `'low'` 区间的 `min` 从 `0.01` 改回 `null`，不向后端传 `balance_min`，后端查询 `total_amount < 10000` 与 KPI 计数完全一致。`'debt'` 和 `'zero'` 仍作为独立筛选项保留。
- **状态**: 已修复

#### 3. InvoiceDetailDrawer `STATUS_TO_STEP` 映射 `paid` 和 `completed` 偏移 1

- **文件**: `frontend/src/views/billing/components/InvoiceDetailDrawer.vue:325-326`
- **类型**: bug
- **描述**: 组件有 6 个 `<a-step>`（索引 0-5：创建/运营确认/销售确认/客户确认/已付款/已完成）。但 `paid: 5` 激活了索引 5（"已完成"）而非 4（"已付款"），`completed: 6` 超出最大索引。
- **修复**: `paid: 5 -> 4`，`completed: 6 -> 5`。
- **状态**: 已修复

---

### 中（5 个）

#### 4. 导出失败时静默处理

- **文件**: `frontend/src/views/billing/Invoices.vue:431-433`
- **类型**: bug
- **描述**: 导出失败被静默吞掉（`catch { // 导出失败静默处理 }`），用户无法感知导出是否成功。
- **修复**: 在 catch 块中添加 `Message.error('导出失败，请稍后重试')`，同时在 Arco 导入中补充 `Message`。
- **状态**: 已修复

#### 5. 余额惰性补建异常捕获过于宽泛

- **文件**: `backend/app/routes/billing/balances.py:401-404`
- **类型**: bug
- **描述**: `except Exception` 会吞掉所有异常（包括数据库连接断开、磁盘满等），仅以 `logger.debug` 记录。应仅捕获 `IntegrityError`（唯一索引冲突），让其他真正的数据库错误正常上抛。
- **修复**: 收窄为 `except IntegrityError`，从 `sqlalchemy.exc` 导入 `IntegrityError`。其他数据库错误正常传播。
- **状态**: 已修复

#### 6. `exportInvoices` 参数与后端端点不匹配

- **文件**: `frontend/src/api/billing.ts:485-487`
- **类型**: bug
- **描述**: `exportInvoices` 接受 `keyword` 和 `status` 参数，但后端 `/billing/invoices/export` 仅支持 `customer_id`、`status`、`start_date`、`end_date`。`keyword` 参数被后端静默忽略，导致用户应用关键词筛选后导出的是未筛选的全部结算单。
- **修复**: 函数签名更新为与后端对齐：`{ customer_id?, status?, start_date?, end_date? }`。在 `Invoices.vue` 中移除了 `keyword` 传参。
- **状态**: 已修复

#### 7. Pagination `displayPages` 可能产生错误的页码序列

- **文件**: `frontend/src/components/ui/Pagination.vue:78-82`
- **类型**: bug
- **描述**: `end` 上限 `total - 1` 可能导致中间窗口包含倒数第二页，使尾部省略号在有间隙时消失。省略号条件 `current < total - 2` 未考虑实际窗口结束位置。
- **修复**: `end` 改为 `Math.min(total - 2, current + 1)`，省略号条件改为 `end < total - 2`。
- **状态**: 已修复

#### 8. `loadStats` 重构后测试 mock 不匹配

- **文件**: `frontend/src/composables/useBalance.ts:174-179`
- **类型**: test
- **描述**: `loadStats` 从调用 `getBalances` 重构为调用 `getBalanceStats`，但 `useBalance.test.ts` 中的测试仍 mock `getBalances`，导致测试失败。
- **修复**: 更新了 `useBalance.test.ts` 中 6 个测试用例：将 `total_customers`、`low_balance_count`、`zero_balance_count` 的 mock 从 `getBalances` 改为 `getBalanceStats`；移除了依赖 `getBalances` 调用参数的 `lowParams` 测试；新增验证 `loadStats` 不再调用 `getBalances` 的测试。全部 22 个测试通过。
- **状态**: 已修复

---

### 低（10 个）

#### 9. 动态 `import()` 替换为静态导入

- **文件**: `frontend/src/views/billing/Invoices.vue:423`
- **修复**: 将动态 `import('@/api/billing').then(...)` 替换为静态 `exportInvoices` 导入。
- **状态**: 已修复

#### 10-11. `PackagePlans.vue` 中未使用的 `computed` 导入和无效的 `pageSizeOptions`

- **文件**: `frontend/src/views/billing/PackagePlans.vue:259, 305`
- **修复**: 从 Vue 导入中移除 `computed`；删除无效的 `pageSizeOptions` 变量。
- **状态**: 已修复

#### 12-13. `PricingRules.vue` 中未使用的 `computed` 导入和无效的 `pageSizeOptions`

- **文件**: `frontend/src/views/billing/PricingRules.vue:194, 246`
- **修复**: 同上 — 移除 `computed` 导入，删除无效 `pageSizeOptions`。
- **状态**: 已修复

#### 14. `BalanceTable.vue` 未透传 `pageSizeOptions` 给 `Pagination`

- **文件**: `frontend/src/views/billing/components/BalanceTable.vue:125-131`
- **修复**: 在 `Pagination` 组件上添加 `:page-size-options="pagination.pageSizeOptions"`。
- **状态**: 已修复

#### 15. `PricingRuleModal.vue` 中 `<a>` 缺少 `href` 影响无障碍访问

- **文件**: `frontend/src/views/billing/components/PricingRuleModal.vue:131-138`
- **修复**: 将 `<a>` 改为 `<button type="button">`，添加 CSS 重置（`border: none; background: none; padding: 0`）。
- **状态**: 已修复

#### 16. `PricingRuleModal.vue` 中 null 价格显示为裸 `¥`

- **文件**: `frontend/src/views/billing/components/PricingRuleModal.vue:192`
- **修复**: 添加空值回退：`¥{{ tier.price ?? '-' }}`。
- **状态**: 已修复

#### 17. `Pagination.vue` 中 `parseInt` 缺少 radix 参数

- **文件**: `frontend/src/components/ui/Pagination.vue:97`
- **修复**: 添加 radix 参数：`parseInt(val, 10)`。
- **状态**: 已修复

#### 18. `Pagination.vue` 缺少窄屏隐藏 `.page-size` 和 `.page-jump` 的响应式逻辑

- **文件**: `frontend/src/components/ui/Pagination.vue:212-222`
- **修复**: 添加 `@media (max-width: 640px)` 规则隐藏 `.page-size` 和 `.page-jump`，与原有视图行为一致。
- **状态**: 已修复

---

## 汇总

| 严重程度 | 数量 | 已修复 | 已记录 |
|----------|------|--------|--------|
| 严重 | 1 | 1 | 0 |
| 高 | 2 | 2 | 0 |
| 中 | 5 | 5 | 0 |
| 低 | 10 | 10 | 0 |
| **合计** | **18** | **18** | **0** |

全部 18 项问题已修复，包括源代码问题和测试文件更新。测试文件 `useBalance.test.ts` 已将 mock 从 `getBalances` 更新为 `getBalanceStats`，22 个测试全部通过。
