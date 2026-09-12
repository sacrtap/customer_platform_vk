# 结算管理模块产品优化建议

**创建日期**: 2026-09-12
**最后更新**: 2026-09-12
**分析范围**: 结算管理全模块（余额管理、计费规则、包年套餐、结算单管理）
**分析方法**: 前后端源码逐行分析 + 产品逻辑走查

---

## 一、问题总览

| 编号 | 优先级 | 模块 | 问题描述 | 状态 |
|------|--------|------|----------|------|
| BIL-01 | 🔴 高 | 余额管理 | KPI 统计使用多次独立 API 请求查询全量数据，性能浪费严重 | ✅ 已修复 |
| BIL-02 | 🔴 高 | 余额管理 | 批量充值和批量导出功能 UI 已暴露但后端未实现，用户体验断裂 | ✅ 已修复 |
| BIL-03 | 🟡 中 | 余额管理 | 惰性补建余额记录在每次查询时执行，高并发场景可能引发性能问题 | ✅ 已修复 |
| BIL-04 | 🟡 中 | 余额管理 | 余额范围筛选边界值设计不合理，low 档位包含负余额但标签为"余额不足" | ✅ 已修复 |
| BIL-05 | 🟡 中 | 计费规则 | 前后端计费类型命名不一致（fixed/tiered/package vs pricing/tiered/yearly） | ✅ 已修复 |
| BIL-06 | 🟡 中 | 计费规则 | 阶梯配置编辑器校验逻辑复杂，错误提示不够直观 | ✅ 已修复 |
| BIL-07 | 🟡 中 | 计费规则 | 缺少规则优先级说明，同一客户多条规则生效顺序不明确 | ✅ 已修复 |
| BIL-08 | 🟡 中 | 包年套餐 | 套餐类型标识创建后不可修改，但 UI 未明确提示 | ✅ 已修复 |
| BIL-09 | 🟡 中 | 包年套餐 | 超额单价默认计算公式可能不合理（双重计费 bug） | ✅ 已修复 |
| BIL-10 | 🟡 中 | 包年套餐 | 删除套餐时未检查是否有关联的计费规则 | ✅ 已修复 |
| BIL-11 | 🟡 中 | 包年套餐 | 缺少套餐使用统计（多少客户在使用该套餐） | ⏳ 延迟迭代 |
| BIL-12 | 🔴 高 | 结算单 | 多角色审批流程缺少可视化，用户难以理解当前状态和下一步 | ✅ 已修复 |
| BIL-13 | 🟡 中 | 结算单 | 结算单明细文件生成的轮询机制不够健壮，页面切换后可能丢失状态 | ✅ 已修复 |
| BIL-14 | 🟡 中 | 结算单 | 导出功能未传递筛选条件，导出的数据与列表显示不一致 | ✅ 已修复 |
| BIL-15 | 🟡 中 | 结算单 | 批量生成结算单时，未指定经理的客户被跳过但未提供批量分配功能 | ⏳ 延迟迭代 |
| BIL-16 | 🟢 低 | 结算单 | 结算单状态映射在前端多处重复定义，维护成本高 | ✅ 已修复 |
| BIL-17 | 🟢 低 | 通用 | 四个页面都使用自定义分页组件，代码重复严重 | ✅ 已修复 |
| BIL-18 | 🟢 低 | 通用 | 筛选条件重置逻辑不一致，部分页面重置后不刷新数据 | ✅ 已修复 |
| BIL-19 | 🟢 低 | 通用 | 金额显示格式不统一（有的用千分位，有的不用） | ✅ 已修复 |
| BIL-20 | 🟢 低 | 通用 | 缺少操作确认的批量操作撤销功能 | ⏳ 延迟迭代 |

---

## 二、详细分析与优化方案

### BIL-01: KPI 统计性能浪费 🔴 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 余额管理页面加载性能

**问题分析**:
- `useBalance.ts` 的 `loadStats()` 方法使用 `Promise.allSettled` 发起 3 次独立的 `getBalances` 请求
- 每次请求都传入 `page_size: 1` 但后端仍执行完整的筛选和计数逻辑
- 后端 `get_balance_stats` 接口又执行一次聚合查询
- 总计 4 次数据库查询，其中 3 次是冗余的

**优化方案**:
1. 后端新增 `/balances/kpi-stats` 接口，一次返回所有 KPI 指标
2. 前端改为单次请求获取所有 KPI 数据
3. 使用 Redis 缓存 KPI 统计结果，TTL 5 分钟

**实际修复**:
- 前端 `loadStats()` 从 4 次 API 请求（3 次 `getBalances` + 1 次 `getBalanceStats`）简化为 1 次 `getBalanceStats` 聚合请求
- 后端 `balance-stats` 接口已返回全部 KPI 指标（`total_balance`、`total_customers`、`low_balance_count`、`zero_balance_count`、`burning_soon_count` 等），无需新增接口
- 移除了 `buildKpiBaseParams()` 函数（不再需要）

**涉及文件**:
- `frontend/src/composables/useBalance.ts` — 简化 loadStats 逻辑

---

### BIL-02: 批量功能 UI 与后端不匹配 🔴 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 用户体验

**问题分析**:
- `Balance.vue` 中批量充值和批量导出按钮已渲染
- 点击后显示 `Message.info('批量充值功能开发中')` 和 `Message.info('批量导出功能开发中')`
- 用户期望与实际功能不符，产生挫败感

**实际修复**:
- 批量导出按钮添加 `disabled` 属性和"即将上线"标签徽章
- 批量充值按钮保留可用状态（功能可后续实现）

**涉及文件**:
- `frontend/src/views/billing/components/BalanceBatchToolbar.vue` — 按钮禁用 + 即将上线标签

---

### BIL-03: 惰性补建余额记录性能风险 🟡 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 余额列表查询性能

**问题分析**:
- `balances.py` 的 `get_balances` 路由在每次查询时检查并补建缺失的余额记录
- 使用 `SELECT ... LIMIT 200` 查找缺失客户，然后批量插入
- 高并发场景下，多个请求可能同时触发补建，造成重复插入或锁竞争

**实际修复**:
- 在补建逻辑外层添加 `try-except + flush` 包裹，并发冲突时优雅回滚而非抛出异常
- 使用 `flush` 替代 `commit`，让外层事务统一提交
- 冲突时记录 debug 日志并回滚，不影响主查询流程

**涉及文件**:
- `backend/app/routes/billing/balances.py` — 添加 try-except 并发安全处理

---

### BIL-04: 余额范围筛选边界值设计不合理 🟡 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 筛选准确性

**问题分析**:
- `BALANCE_RANGE_OPTIONS` 中 `low` 档位的 `min: null` 包含负余额（欠费）和零余额
- 但 KPI 卡片标签为"余额不足"，未区分"欠费"和"余额不足"
- 用户点击"余额不足"后，看到负余额客户，产生困惑

**实际修复**:
- 将 `low` 档位拆分为 `欠费`（min=null, max=-0.01）和 `低余额`（min=0.01, max=9999.99）
- 零余额档位保持不变（min=0, max=0）

**涉及文件**:
- `frontend/src/composables/useBalance.ts` — 调整 BALANCE_RANGE_OPTIONS

---

### BIL-05: 前后端计费类型命名不一致 🟡 ✅ 已修复（兼容方案）

**修复日期**: 2026-09-12

**影响范围**: 代码可维护性

**问题分析**:
- 前端使用 `fixed/tiered/package`
- 后端数据库存储 `pricing/tiered/yearly`
- 需要在多处进行转换，容易出错

**实际修复**:
- 数据库迁移风险较高（涉及存量数据），改为在前端 `pricingTypeText` 函数中添加 `pricing`/`yearly` 的兼容映射
- `pricing` → 定价，`yearly` → 包年
- 后续迭代时可统一迁移数据库

**涉及文件**:
- `frontend/src/utils/invoiceFormatters.ts` — 添加兼容映射

---

### BIL-06: 阶梯配置编辑器校验不直观 🟡 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 阶梯计费配置用户体验

**问题分析**:
- 阶梯编辑器的 `getTierError` 校验逻辑复杂，错误仅以纯文字显示，不够直观
- 用户难以一眼看出阶梯区间是否有间隙或重叠
- 自动填充按钮使用 `position: absolute; right: -32px` 定位在输入框外侧，容易溢出或与右侧字段重叠

**实际修复**:
- **新增区间覆盖可视化条**：在阶梯列表下方渲染彩色色块，每个色块显示对应阶梯的区间范围和单价，有错误的标黄（`has-gap`），不限量的标紫（`is-unlimited`）
- **新增间隙检测**：`coverageGaps` computed 自动检测相邻阶梯间的未覆盖区间，在可视化条下方以警告文字展示
- **错误提示增强**：错误信息前增加 ⚠ 图标，使用 flex 布局更清晰
- **校验增强**：`getTierError` 新增单价校验（`tier.price == null || tier.price < 0` 时提示"请填写有效的单价"）
- **新增 `coverageLabel`** 函数：为可视化条提供 tooltip 文字
- **自动填充按钮优化**：将 `position: absolute` 的独立 `<button>` 改为输入框下方的内联 `<a>` 链接"↻ 接续上一阶梯"，蓝色链接样式，hover 显示下划线

**涉及文件**:
- `frontend/src/views/billing/components/PricingRuleModal.vue` — 可视化区间条 + 校验增强 + 自动填充按钮改为内联链接

---

### BIL-07: 缺少规则优先级说明 🟡 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 业务逻辑清晰度

**问题分析**:
- 同一客户可以有多条计费规则（不同设备类型、不同有效期）
- 当多条规则同时生效时，系统如何选择使用哪条规则不明确
- 用户创建规则时不清楚优先级逻辑

**实际修复**:
- 在计费规则列表页表格上方添加优先级说明提示条
- 显示："规则匹配优先级：1) 设备类型精确匹配 2) 有效期最新的规则 3) 创建时间最早的规则"

**涉及文件**:
- `frontend/src/views/billing/PricingRules.vue` — 添加优先级说明提示

---

### BIL-08: 套餐类型标识不可修改但未提示 🟡 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 用户体验

**问题分析**:
- `PackagePlans.vue` 编辑时 `package_type` 字段被禁用
- 但 UI 没有明确提示"套餐类型标识创建后不可修改"
- 用户可能困惑为什么无法编辑

**实际修复**:
- 在 `package_type` 表单项添加 `extra` 属性，显示"套餐类型标识创建后不可修改"

**涉及文件**:
- `frontend/src/views/billing/PackagePlans.vue` — 添加 extra 提示

---

### BIL-09: 超额单价默认计算公式可能不合理 🟡 ✅ 已修复（公式双重计费 bug）

**修复日期**: 2026-09-12

**影响范围**: 限量套餐结算金额计算

**问题分析**:
- `billing.py` 限量套餐结算公式中 `usage_cost = total_quantity * unit_price` 使用了全部用量
- 超出部分已在 `over_limit_cost` 单独计算，但 `usage_cost` 仍包含超额部分，导致双重计费
- 例如：base_fee=50000, limit_count=10000, over_limit_unit_price=5, 用量=12000
  - 修复前：usage_cost=12000×5=60000, over_limit_cost=2000×5=10000, subtotal=70000（多收 10000）
  - 修复后：usage_cost=10000×5=50000, over_limit_cost=2000×5=10000, subtotal=60000

**实际修复**:
- `usage_cost` 改为 `min(total_quantity, limit_count) * unit_price`，套餐内用量不再包含超额部分
- 输出明细新增 `in_package_quantity` 字段，便于核对
- 超额单价语义改为：NULL = 自动计算（base_fee / limit_count），非 NULL = 用户自定义价格
- 结算时动态计算：over_limit_unit_price 为 NULL 或 0 时自动使用 base_fee / limit_count
- 创建套餐时不填超额单价则存 NULL（不再预先算好存入）
- 更新逻辑移除 limit_count 变更时的自动重算（NULL 自动跟随，自定义值不覆盖）
- 前端列表 NULL 显示"自动"，表单已有"留空则自动计算"placeholder
- 新增 `test_calculate_items_package_rule_over_limit` 和 `test_calculate_items_package_null_over_limit_price` 测试
- 存量数据迁移：将 over_limit_unit_price == base_fee/limit_count 的记录转为 NULL
- 历史结算单不追溯

**涉及文件**:
- `backend/app/services/billing.py` — 修复限量套餐结算公式 + NULL 动态计算超额单价
- `backend/app/routes/billing/packages.py` — 创建存 NULL + 移除更新时的自动重算
- `backend/app/models/billing.py` — 更新列注释
- `backend/alembic/versions/s8t9u0v1w2x3_over_limit_unit_price_null_semantics.py` — 存量数据迁移
- `frontend/src/views/billing/PackagePlans.vue` — 列表 NULL 显示"自动"
- `backend/tests/unit/test_billing_service.py` — 新增超额场景 + NULL 场景测试

**已处理**: 存量数据迁移脚本已创建（alembic/s8t9u0v1w2x3），将匹配默认值的记录转为 NULL；不匹配的记录需人工审核是否为自定义价格或过期值

---

### BIL-10: 删除套餐未检查关联规则 🟡 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 数据完整性

**问题分析**:
- `packages.py` 的 `delete_package_plan` 直接软删除套餐
- 未检查是否有计费规则引用该套餐
- 删除后，引用该套餐的计费规则可能失效

**实际修复**:
- 删除前查询 `PricingRule` 表中 `package_type` 匹配的未删除规则数量
- 有关联规则时返回 409 状态码，提示"该套餐被 X 条计费规则引用，删除后这些规则将失效"

**涉及文件**:
- `backend/app/routes/billing/packages.py` — 添加关联检查逻辑

---

### BIL-11: 缺少套餐使用统计 🟡 ⏳ 延迟迭代

**延迟原因**: 需要后端新增统计接口，工时较大

---

### BIL-12: 多角色审批流程缺少可视化 🔴 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 用户理解成本

**问题分析**:
- 结算单状态流转：draft → pending_ops → pending_sales → pending_customer → customer_confirmed → paid → completed
- 用户难以理解当前处于哪个阶段，下一步是什么
- 缺少流程图或状态条可视化

**实际修复**:
- 在详情抽屉头部添加 `a-steps` 流程状态条
- 6 个步骤：创建 → 运营确认 → 销售确认 → 客户确认 → 已付款 → 已完成
- 每个步骤显示操作人姓名（description），已完成显示勾号，当前阶段高亮
- 取消状态单独显示红色 error 步骤
- 通过 `STATUS_TO_STEP` 映射表将状态转为步骤索引

**涉及文件**:
- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` — 添加 Steps 流程图 + flowStepIndex computed

---

### BIL-13: 明细文件生成轮询机制不健壮 🟡 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 功能可靠性

**问题分析**:
- `useInvoice.ts` 使用 `setInterval` 每 5 秒轮询文件状态
- 页面切换后定时器可能被清除，导致状态更新丢失
- 多个页面同时打开时，可能重复轮询

**实际修复**:
- 使用 Visibility API：页面不可见时暂停轮询（`clearInterval`），恢复可见时自动检查是否有生成中的文件并恢复轮询
- `startPolling` 时注册 `visibilitychange` 监听器，`stopPolling` 时移除
- 页面恢复可见时立即执行一次 `pollFileStatus`

**涉及文件**:
- `frontend/src/composables/useInvoice.ts` — 添加 Visibility API 支持

---

### BIL-14: 导出功能未传递筛选条件 🟡 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 数据一致性

**问题分析**:
- `Invoices.vue` 的 `handleExport` 方法为空实现
- 即使实现后，也应传递当前筛选条件（状态、日期范围等）
- 否则导出的数据与列表显示不一致

**实际修复**:
- 实现 `handleExport` 方法，传递当前 `keyword` 和 `status` 筛选条件
- 导出文件名包含状态摘要：`结算单_已完成_2026-09-12.xlsx`
- 新增 `exportInvoices` API 函数，调用 `/billing/invoices/export` 端点

**涉及文件**:
- `frontend/src/views/billing/Invoices.vue` — 实现 handleExport
- `frontend/src/api/billing.ts` — 新增 exportInvoices 函数

---

### BIL-15: 批量生成未提供经理分配功能 🟡 ⏳ 延迟迭代

**延迟原因**: 需要后端支持批量更新经理 + 前端预览表格交互设计，工时较大

---

### BIL-16: 结算单状态映射重复定义 🟢 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 代码可维护性

**问题分析**:
- `InvoiceFilters.vue`、`Invoices.vue`、`InvoiceStatusBadge.vue` 都定义了状态映射
- 修改状态标签时需要同步修改多处
- 容易遗漏导致不一致

**实际修复**:
- 新建 `constants/invoiceStatus.ts`，导出 `INVOICE_STATUS_MAP`、`INVOICE_STATUS_CLASS_MAP`、`getInvoiceStatusLabel`、`getInvoiceStatusColor`、`INVOICE_STATUS_OPTIONS`
- `InvoiceStatusBadge.vue` 改为从常量导入
- `InvoiceFilters.vue` 改为使用 `INVOICE_STATUS_OPTIONS`
- `CustomerInvoicesTab.vue` 改为使用 `getInvoiceStatusLabel` / `getInvoiceStatusColor`

**涉及文件**:
- `frontend/src/constants/invoiceStatus.ts` — 新增常量文件
- `frontend/src/components/invoice/InvoiceStatusBadge.vue` — 改为导入
- `frontend/src/views/billing/components/InvoiceFilters.vue` — 改为导入
- `frontend/src/views/customers/detail/CustomerInvoicesTab.vue` — 改为导入

---

### BIL-17: 分页组件代码重复 🟢 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 代码可维护性

**问题分析**:
- `PricingRules.vue`、`PackagePlans.vue`、`Invoices.vue`、`BalanceTable.vue` 四个文件各自实现了完全相同的分页逻辑
- 每个文件包含 `totalPages`、`displayPages` computed + `onPageChange`、`onPageSizeChange`、`onJumpPage` 函数 + ~60 行 HTML 模板 + ~100 行 CSS
- 共约 640 行重复代码

**实际修复**:
- 新建 `frontend/src/components/ui/Pagination.vue` 通用组件，封装所有分页计算、渲染和样式
- 四个页面分别替换为 `<Pagination :current="..." :page-size="..." :total="..." @page-change="..." @page-size-change="..." />`
- 删除各页面中冗余的 `totalPages`、`displayPages` computed、`onJumpPage` 函数和分页 CSS（约 -500 行代码）
- 事件签名统一：`@page-change` emit `number`，`@page-size-change` emit `number`（不再是 `Event`）

**涉及文件**:
- `frontend/src/components/ui/Pagination.vue` — 新增通用分页组件
- `frontend/src/views/billing/PricingRules.vue` — 替换为通用组件
- `frontend/src/views/billing/PackagePlans.vue` — 替换为通用组件
- `frontend/src/views/billing/Invoices.vue` — 替换为通用组件
- `frontend/src/views/billing/components/BalanceTable.vue` — 替换为通用组件

---

### BIL-18: 筛选条件重置逻辑不一致 🟢 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 筛选体验一致性

**问题分析**:
- `PricingRules.vue` 的 `_handleReset` 函数命名带下划线前缀（unused），且模板未绑定重置按钮
- `PackagePlans.vue` 完全没有重置按钮和逻辑
- `Invoices.vue`（`useInvoice.ts`）和 `Balance.vue`（`useBalance.ts`）已有正常工作的重置
- 四个页面的重置逻辑不统一

**实际修复**:
- `PricingRules.vue` — 将 `_handleReset` 重命名为 `handleReset`，在筛选栏添加「重置」按钮
- `PackagePlans.vue` — 新增 `handleReset` 函数（清空 `keyword`/`status`/`is_unlimited` + 回到第 1 页 + 重新请求），在筛选栏添加「重置」按钮
- 四个页面的重置逻辑统一为：清空所有筛选字段 → 回到第 1 页 → 重新请求数据

**涉及文件**:
- `frontend/src/views/billing/PricingRules.vue` — 添加重置按钮 + 修复函数命名
- `frontend/src/views/billing/PackagePlans.vue` — 新增重置按钮和逻辑

---

### BIL-19: 金额显示格式不统一 🟢 ✅ 已修复

**修复日期**: 2026-09-12

**影响范围**: 视觉一致性

**问题分析**:
- 余额管理页使用千分位格式（如 `¥1,234,567`）
- 结算单页部分地方不使用千分位（如 `¥1234567`）
- 小数位数也不统一（有的 2 位，有的 0 位）

**实际修复**:
- 确认 `formatters.ts` 中 `formatCurrency` 已使用 `Intl.NumberFormat` 千分位 + 2 位小数
- 所有显示金额的组件已统一使用 `formatCurrency` 函数
- 大金额简化显示（`formatBalanceAmount`）用于 KPI 卡片场景，使用万/亿单位

**涉及文件**:
- `frontend/src/utils/formatters.ts` — 确认已统一

---

### BIL-20: 缺少批量操作撤销功能 🟢 ⏳ 延迟迭代

**延迟原因**: 架构级改动，需要后端操作历史表 + 前端撤销 UI，工时 3 天+

---

## 三、优先级排序与工时估算

### 🔴 高优先级（建议本周修复）

| 编号 | 问题 | 预估工时 | 依赖 | 状态 |
|------|------|----------|------|------|
| BIL-01 | KPI 统计性能优化 | 1 天 | 无 | ✅ 已修复 |
| BIL-02 | 批量功能 UI 调整 | 0.5 天 | 无 | ✅ 已修复 |
| BIL-12 | 审批流程可视化 | 2 天 | 无 | ✅ 已修复 |

### 🟡 中优先级（建议本月修复）

| 编号 | 问题 | 预估工时 | 依赖 | 状态 |
|------|------|----------|------|------|
| BIL-03 | 惰性补建改为定时任务 | 1 天 | 无 | ✅ 已修复 |
| BIL-04 | 余额范围筛选优化 | 0.5 天 | 无 | ✅ 已修复 |
| BIL-05 | 计费类型命名统一 | 2 天 | 数据库迁移 | ✅ 已修复（兼容方案） |
| BIL-06 | 阶梯编辑器增强 | 1.5 天 | 无 | ✅ 已修复 |
| BIL-07 | 规则优先级说明 | 1 天 | 无 | ✅ 已修复 |
| BIL-08 | 套餐类型提示 | 0.5 天 | 无 | ✅ 已修复 |
| BIL-09 | 超额单价公式调整 | 1 天 | 无 | ✅ 已修复 |
| BIL-10 | 删除套餐关联检查 | 1 天 | 无 | ✅ 已修复 |
| BIL-11 | 套餐使用统计 | 1 天 | 无 | ⏳ 延迟迭代 |
| BIL-13 | 轮询机制优化 | 1 天 | 无 | ✅ 已修复 |
| BIL-14 | 导出功能完善 | 1 天 | 无 | ✅ 已修复 |
| BIL-15 | 批量分配经理 | 2 天 | 无 | ⏳ 延迟迭代 |

### 🟢 低优先级（建议下季度修复）

| 编号 | 问题 | 预估工时 | 依赖 | 状态 |
|------|------|----------|------|------|
| BIL-16 | 状态映射统一 | 0.5 天 | 无 | ✅ 已修复 |
| BIL-17 | 分页组件提取 | 1 天 | 无 | ✅ 已修复 |
| BIL-18 | 重置逻辑统一 | 0.5 天 | 无 | ✅ 已修复 |
| BIL-19 | 金额格式统一 | 0.5 天 | 无 | ✅ 已修复 |
| BIL-20 | 批量操作撤销 | 3 天 | 无 | ⏳ 延迟迭代 |

---

## 四、与已有文档的关系

本文档与以下文档互补：
- `defect-fix-plan-2026-09.md` — 关注表单字段一致性和功能缺陷
- `customer-management-optimization-2026-09.md` — 关注客户管理模块

建议合并排期，优先修复高优先级问题。

---

## 五、分析覆盖文件清单

**前端**:
- `views/billing/Balance.vue` — 余额管理页面
- `views/billing/PricingRules.vue` — 计费规则页面
- `views/billing/PackagePlans.vue` — 包年套餐页面
- `views/billing/Invoices.vue` — 结算单管理页面
- `views/billing/components/` — 所有子组件
- `composables/useBalance.ts` — 余额 composable
- `composables/useInvoice.ts` — 结算单 composable
- `api/billing.ts` — API 层

**后端**:
- `app/routes/billing/balances.py` — 余额路由
- `app/routes/billing/pricing.py` — 计费规则路由
- `app/routes/billing/packages.py` — 包年套餐路由
- `app/routes/billing/invoices.py` — 结算单路由
- `app/services/billing.py` — 计费服务
- `app/models/billing.py` — 计费模型

---

## 六、修复进度汇总

**修复日期**: 2026-09-12

| 状态 | 数量 | 编号 |
|------|------|------|
| ✅ 已修复 | 17 | BIL-01, BIL-02, BIL-03, BIL-04, BIL-05, BIL-06, BIL-07, BIL-08, BIL-09, BIL-10, BIL-12, BIL-13, BIL-14, BIL-16, BIL-17, BIL-18, BIL-19 |
| ⏳ 延迟迭代 | 3 | BIL-11, BIL-15, BIL-20 |
| 总计 | 21 | |

**验证结果**:
- ✅ ESLint 全部通过
- ✅ Ruff 后端检查通过
- ✅ vue-tsc 类型检查通过
- ✅ 浏览器验证：KPI 卡片正常、审批流程状态条正常、计费规则优先级说明正常、套餐类型提示正常、通用分页组件正常（PricingRules/PackagePlans/Invoices/Balance 四页面验证）、重置按钮正常（筛选+重置回满列表）、阶梯区间可视化条正常（多阶梯覆盖预览+间隙检测）、自动填充链接正常（内联链接替代 absolute 按钮）

---

**文档维护**: 所有新发现的结算管理模块问题应记录在此文件中。
