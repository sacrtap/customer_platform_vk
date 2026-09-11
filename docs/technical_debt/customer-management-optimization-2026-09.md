# 客户管理模块产品优化建议

**创建日期**: 2026-09-12
**分析范围**: 客户管理全模块（列表页、详情页、批量操作、筛选、KPI、预览抽屉、编辑表单、导入导出）
**分析方法**: 前后端源码逐行分析 + 产品逻辑走查

---

## 一、问题总览

| 编号 | 严重程度 | 类别 | 问题描述 |
|------|---------|------|---------|
| OPT-01 | 🔴 高 | 性能 | KPI 统计卡片发起 4 次独立 API 请求，每次传 `force_refresh=true` 跳过缓存 |
| OPT-02 | 🔴 高 | 数据一致性 | 健康度在路由层硬编码阈值判断，与详情页 `getCustomerHealthScore` 评分逻辑不一致 |
| OPT-03 | 🔴 高 | 功能缺失 | 批量操作「分配负责人」「设标签」「批量导出」的 confirm handler 为空实现 |
| OPT-04 | 🟡 中 | 数据一致性 | 客户列表接口返回中文健康度（"高风险"/"关注"/"健康"），前端 health map 用英文 key 匹配 |
| OPT-05 | 🟡 中 | 性能 | 详情页 `loadDetail` 并行请求 4 个 API，但 `loadBalance`/`loadProfile` 在切换 Tab 时重复请求已加载的数据 |
| OPT-06 | 🟡 中 | 产品逻辑 | 预览抽屉「预计耗尽天数」前端硬算（balance / 日均消耗），后端 `/balance-forecast` 接口 `daily_avg` 永远返回 0 |
| OPT-07 | 🟡 中 | 产品逻辑 | 筛选器「运营经理」和「销售经理」共用同一个 managers 数据源，无法区分角色 |
| OPT-08 | 🟡 中 | 缓存策略 | 前端 Pinia store 定义了 5/10/15 分钟 TTL 缓存，但 `useCustomerDetail` composable 几乎不使用 store 缓存 |
| OPT-09 | 🟡 中 | 数据一致性 | 编辑弹窗 `EditCustomerDialog` 同时调用 `updateCustomer` + `updateProfile` 两个独立 API，事务不原子 |
| OPT-10 | 🟢 低 | 代码质量 | 规模等级、消费等级、结算周期等选项常量在 5+ 个组件中重复定义 |
| OPT-11 | 🟢 低 | 产品逻辑 | 批量选择仅支持当前页，不支持跨页全选 |
| OPT-12 | 🟢 低 | 用户体验 | 导出接口 `page_size=10000` 硬编码上限，超量客户静默截断 |
| OPT-13 | 🟢 低 | 产品逻辑 | 客户列表默认硬编码行业筛选 `房产经纪,房产ERP,房产平台`，新用户无法感知 |
| OPT-14 | 🟡 中 | 产品逻辑 | 360 预览抽屉的「最近操作」时间轴数据来自 `consumption_history` 字段，但该字段在列表 API 中从未填充 |
| OPT-15 | 🟡 中 | 性能 | 列表接口每次请求都 JOIN `DailyConsumption` 计算 30 天消耗，无聚合缓存 |
| OPT-16 | 🟢 低 | 产品逻辑 | 删除客户只软删除 Customer + Balance，未处理关联的 Invoice、DailyConsumption、Profile 等数据 |
| OPT-17 | 🟡 中 | 产品逻辑 | 新增客户弹窗缺少「合作状态」「ERP 系统」「备注」等字段，创建后需二次编辑 |
| OPT-18 | 🟢 低 | 代码质量 | `useCustomerDetail` composable 返回 50+ 个属性/方法，职责过重 |
| OPT-19 | 🟡 中 | 产品逻辑 | 排序字段 `usage_30d` 和 `health` 在排序时退化或为空操作，但表头仍显示可排序图标 |
| OPT-20 | 🟢 低 | 产品逻辑 | 客户详情页「结算单」Tab 一次性加载 `page_size=100` 条，无分页 |

---

## 二、详细分析与优化方案

### OPT-01: KPI 统计卡片 4 次独立请求 🔴

**现状**:
`Index.vue` 的 `loadKpiData()` 使用 `Promise.allSettled` 发起 4 次 `getCustomers` 请求，每次都传 `force_refresh=true` 跳过缓存。这意味着每次进入页面或点击「数据刷新」，后端要执行 4 次完整的客户列表查询（含 JOIN Profile、Balance、DailyConsumption）。

**影响**: 页面加载慢，数据库压力大，尤其在客户量增长后问题加剧。

**优化方案**:
1. 后端新增 `/api/v1/customers/kpi-stats` 聚合接口，一条 SQL 返回所有 KPI 计数
2. 前端改为单次请求获取全部 KPI 数据
3. KPI 统计走独立缓存（TTL 60s），与列表缓存解耦
4. 「数据刷新」按钮仅刷新列表，KPI 走独立刷新逻辑

**涉及文件**:
- `backend/app/routes/customers.py` — 新增聚合路由
- `backend/app/services/customers.py` — 新增聚合查询方法
- `frontend/src/views/customers/Index.vue` — 改为调用聚合接口

---

### OPT-02: 健康度判断逻辑前后端不一致 🔴

**现状**:
- 后端路由 `list_customers` 中硬编码：余额 < 500 → "高风险"，< 1000 → "关注"，30天消耗=0 → "不活跃"，否则 → "健康"
- 前端 `CustomerTable.vue` 的 `getHealthTagClass` 用英文 key（`healthy`/`attention`/`high_risk`）匹配
- 后端返回的是中文值（`"高风险"`/`"关注"`/`"健康"`/`"不活跃"`）
- 详情页使用独立的 `getCustomerHealthScore` API 计算评分

**影响**: 列表页健康度标签全部显示为灰色（因为中文值不匹配英文 key），健康度信息形同虚设。

**优化方案**:
1. 后端统一返回英文枚举值（`healthy`/`attention`/`high_risk`/`inactive`）
2. 将健康度判断逻辑从路由层抽到 service 层，与详情页评分逻辑统一
3. 前端 `getHealthLabel` / `getHealthTagClass` 已支持英文 key，无需改动

**涉及文件**:
- `backend/app/routes/customers.py` — 修改 health 字段返回值为英文枚举
- `backend/app/services/customers.py` 或新建 `health_service.py` — 统一健康度计算逻辑

---

### OPT-03: 批量操作 handler 为空实现 🔴

**现状**:
`Index.vue` 中三个批量操作的 confirm handler 只关闭弹窗并刷新列表，未实际调用 API：

```typescript
// handleBatchLevelConfirm — 未调用 batchUpdateCustomers
const handleBatchLevelConfirm = async (_data) => {
  batchLoading.value = true
  try {
    batchLevelVisible.value = false
    handleSearch()  // ← 只刷新，没提交
  } finally { batchLoading.value = false }
}

// handleSendEmailConfirm — 未调用邮件发送 API
// handleAssignManagerConfirm — 未调用分配负责人 API
```

**影响**: 用户选择批量操作后点击确认，看似成功但数据未变更，属于静默失败。

**优化方案**:
1. `handleBatchLevelConfirm`: 调用 `batchUpdateCustomers(ids, { scale_level, consume_level })`
2. `handleAssignManagerConfirm`: 调用 `batchUpdateCustomers(ids, { manager_id })`
3. `handleSendEmailConfirm`: 调用批量邮件发送 API（需后端支持）
4. 添加操作结果反馈（成功/失败数量）

**涉及文件**:
- `frontend/src/views/customers/Index.vue` — 补全 handler 实现

---

### OPT-04: 健康度中英文 key 不匹配 🟡

**现状**:
后端路由返回中文健康度值：
```python
"health": "高风险" if ... else "关注" if ... else "不活跃" if ... else "健康"
```

前端 `CustomerTable.vue` 的映射表使用英文 key：
```typescript
const getHealthTagClass = (health: string) => {
  const map = { healthy: 'green', attention: 'amber', high_risk: 'red' }
  return map[health] || 'gray'  // ← 中文值永远匹配不到，全部显示灰色
}
```

`PreviewDrawer.vue` 同样使用英文 key 映射。

**影响**: 列表页和预览抽屉的健康度标签全部显示为灰色，无法区分风险等级。

**优化方案**: 同 OPT-02，后端改为返回英文枚举值。

---

### OPT-05: 详情页 Tab 切换重复请求 🟡

**现状**:
`handleTabChange` 中的条件判断有缺陷：
```typescript
if (tabKey === 'balance' && !balance.value?.total_amount) loadBalance()
```
- 当余额确实为 0 时，`!balance.value?.total_amount` 为 true，每次切换到余额 Tab 都会重新请求
- `profile` Tab 同理：`!profile.value?.scale_level` 在 scale_level 为空时重复请求

**影响**: 用户在 Tab 间切换时产生不必要的网络请求。

**优化方案**:
1. 使用 `loadedTabs` Set 跟踪已加载的 Tab（已有此变量但未在此处使用）
2. 改为 `if (tabKey === 'balance' && !loadedTabs.value.has('balance')) loadBalance()`
3. 加载后标记 `loadedTabs.add('balance')`

**涉及文件**:
- `frontend/src/composables/useCustomerDetail.ts` — 修复 Tab 加载判断逻辑

---

### OPT-06: 预览抽屉「预计耗尽天数」计算无效 🟡

**现状**:
- 前端 `PreviewDrawer.vue` 用 `balance / (usage_30d_amount / 30)` 计算
- 后端 `/balance-forecast` 接口 `daily_avg` 硬编码为 0
- 当 `usage_30d_amount` 为 0 时，前端返回 0 天，显示不合理

**影响**: 预计耗尽天数要么为 0，要么不准确，误导运营判断。

**优化方案**:
1. 后端 `/balance-forecast` 接入 `DailyConsumption` 表计算真实日均消耗
2. 前端优先使用后端返回的预测值，fallback 到前端计算
3. 当无消耗数据时显示 "—" 而非 0

**涉及文件**:
- `backend/app/routes/customers.py` — `get_balance_forecast` 接入真实消耗数据
- `frontend/src/views/customers/components/PreviewDrawer.vue` — 优化显示逻辑

---

### OPT-07: 运营经理和销售经理共用数据源 🟡

**现状**:
`CustomerFilters.vue` 中：
```typescript
const managerOptions = computed(() =>
  props.managers.map(m => ({ label: m.real_name || `#${m.id}`, value: String(m.id) }))
)
const salesOptions = computed(() =>
  props.managers.map(m => ({ label: m.real_name || `#${m.id}`, value: String(m.id) }))
)
```
两个下拉框使用完全相同的数据源（都是 `managers`），无法区分运营经理和销售经理的角色。

**影响**: 用户无法按角色筛选，且两个下拉框展示完全相同的人员列表，体验困惑。

**优化方案**:
1. 后端新增按角色筛选的用户列表 API（或扩展现有 `getManagers` 支持 `role` 参数）
2. 前端分别请求运营经理列表和销售经理列表
3. 如果角色体系不支持区分，至少在 UI 上说明两个字段的关系

**涉及文件**:
- `frontend/src/api/users.ts` — 扩展 API 支持角色筛选
- `frontend/src/views/customers/components/CustomerFilters.vue` — 分别加载
- `backend/app/routes/users.py` — 新增角色筛选参数

---

### OPT-08: Pinia store 缓存未被使用 🟡

**现状**:
`stores/customer.ts` 定义了完善的缓存机制（customerCache、tagsCache、managersCache + TTL），但 `useCustomerDetail.ts` 中：
- 仅在 `loadCustomerTags` 中使用了 `customerStore.getCachedTags` / `cacheTagsData`
- `loadDetail`、`loadBalance`、`loadProfile` 均未使用 store 缓存
- `managers` 数据在 `useCustomerList` 和 `useCustomerDetail` 中各自独立请求

**影响**: 缓存层形同虚设，相同数据在多个组件中重复请求。

**优化方案**:
1. `loadDetail` 优先检查 store 缓存，命中则跳过 API
2. `managers` 数据提升到 store 级别，全局共享
3. 数据变更时主动 invalidate 相关缓存

**涉及文件**:
- `frontend/src/composables/useCustomerDetail.ts` — 接入 store 缓存
- `frontend/src/composables/useCustomerList.ts` — managers 使用 store 缓存

---

### OPT-09: 编辑弹窗非原子事务 🟡

**现状**:
`EditCustomerDialog.vue` 的 `handleSubmit` 并行调用 `updateCustomer` + `updateProfile`：
```typescript
await Promise.all([
  updateCustomer(customerId, basicData),
  updateProfile(customerId, profileData),
])
```
如果 `updateCustomer` 成功但 `updateProfile` 失败，数据处于不一致状态。

**影响**: 部分更新成功、部分失败时，客户数据不一致，用户难以感知。

**优化方案**:
1. 后端新增统一的 `PUT /customers/:id` 接口，同时处理 customer + profile 更新
2. 或后端新增事务包装，确保两个操作原子性
3. 前端在失败时给出明确提示，告知哪些字段更新成功/失败

**涉及文件**:
- `backend/app/routes/customers.py` — 扩展 update 接口支持 profile 字段
- `backend/app/services/customers.py` — 事务内同时更新
- `frontend/src/views/customers/detail/EditCustomerDialog.vue` — 改为单次请求

---

### OPT-10: 选项常量重复定义 🟢

**现状**:
规模等级选项在以下位置重复定义：
- `CustomerFilters.vue` — scaleOptions
- `CustomerTable.vue` — 无（直接使用后端值）
- `EditCustomerDialog.vue` — `<a-option>` 硬编码
- `CustomerBatchEditModal.vue` — `<a-option>` 硬编码
- `constants/customerOptions.ts` — 已存在但未被使用

消费等级、结算周期、结算方式等同样在 3-5 个组件中重复。

**优化方案**:
1. 统一使用 `constants/customerOptions.ts` 中的常量
2. 所有表单组件引用共享常量
3. 添加单元测试确保常量一致性

**涉及文件**:
- `frontend/src/constants/customerOptions.ts` — 补全所有选项常量
- 所有使用硬编码选项的组件 — 改为引用常量

---

### OPT-11: 批量选择仅支持当前页 🟢

**现状**:
`handleBatchSelectAll` 仅选择当前页的 customer IDs：
```typescript
const handleBatchSelectAll = (checked: boolean) => {
  if (checked) {
    selectedCustomerIds.value = customers.value.map(c => c.id)
  }
}
```

**影响**: 用户无法对筛选结果的全部记录执行批量操作。

**优化方案**:
1. 添加「全选所有 N 条记录」选项（在分页信息旁显示）
2. 支持 `selectAll=true` 参数，后端执行全量批量操作
3. 或引入「选择模式」：当前页 / 全部匹配

**涉及文件**:
- `frontend/src/views/customers/components/CustomerTable.vue` — 添加全量选择 UI
- `frontend/src/composables/useCustomerList.ts` — 支持全量选择模式
- `backend/app/routes/customers.py` — batch-update 支持 `select_all` + `filters` 模式

---

### OPT-12: 导出硬编码上限 🟢

**现状**:
```python
customers, _ = await service.get_all_customers(page=1, page_size=10000, filters=filters)
```
超过 10000 条客户时，导出静默截断，用户无感知。

**优化方案**:
1. 导出前返回预估总数，让用户确认
2. 超量时使用异步导出 + 下载中心
3. 至少在导出结果中提示「已导出前 10000 条，共 N 条」

**涉及文件**:
- `backend/app/routes/customers.py` — `export_customers` 添加总量提示
- `frontend/src/composables/useCustomerList.ts` — 导出结果提示

---

### OPT-13: 默认行业筛选硬编码 🟢

**现状**:
```typescript
const DEFAULT_INDUSTRY = '房产经纪,房产ERP,房产平台'
```
列表默认只显示这三个行业的客户，新用户可能误以为系统只有这些客户。

**优化方案**:
1. 将默认行业筛选改为可配置（用户偏好设置）
2. 首次使用时默认显示全部行业，用户可自行筛选
3. 在筛选区域明确提示「已筛选：房产经纪/房产ERP/房产平台」

**涉及文件**:
- `frontend/src/composables/useCustomerList.ts` — 默认筛选改为可配置
- `frontend/src/views/customers/Index.vue` — KPI 统计同步调整

---

### OPT-14: 预览抽屉时间轴数据未填充 🟡

**现状**:
`PreviewDrawer.vue` 显示 `customer.consumption_history`，但列表 API 返回的客户对象中从未包含此字段。`Customer` 类型定义中有 `consumption_history?: ConsumptionHistoryItem[]`，但后端 `list_customers` 路由未填充。

**影响**: 预览抽屉的「最近操作」始终显示「暂无操作记录」。

**优化方案**:
1. 后端在列表接口中填充 `consumption_history`（从审计日志或消耗记录中获取最近 5 条）
2. 或前端在打开预览抽屉时单独请求 `/customers/:id/summary` 获取
3. 如果短期无法实现，隐藏该区域或显示 loading 占位

**涉及文件**:
- `backend/app/routes/customers.py` — 填充 consumption_history 或优化 summary 接口
- `frontend/src/views/customers/components/PreviewDrawer.vue` — 按需加载

---

### OPT-15: 列表接口 30 天消耗无聚合缓存 🟡

**现状**:
每次请求客户列表，后端都执行 `DailyConsumption` 的聚合子查询：
```python
usage_stmt = select(
    DailyConsumption.customer_id,
    func.coalesce(func.sum(DailyConsumption.order_count), 0),
    func.coalesce(func.sum(DailyConsumption.total_cost), 0),
).where(DailyConsumption.consumption_date >= thirty_days_ago)
  .group_by(DailyConsumption.customer_id)
```
虽然有 Redis 缓存，但缓存 key 包含筛选参数的 hash，不同筛选条件下缓存命中率低。

**优化方案**:
1. 新增 `daily_consumption_summary` 物化视图或定时聚合任务
2. 将 30 天消耗聚合结果缓存为独立 key（TTL 5 分钟），列表接口直接读取
3. 数据变更时（新消耗记录入库）主动 invalidate

**涉及文件**:
- `backend/app/routes/customers.py` — 使用缓存的聚合数据
- `backend/app/tasks/scheduler.py` — 新增定时聚合任务

---

### OPT-16: 删除客户未清理关联数据 🟢

**现状**:
`delete_customer` 只软删除 Customer 和 CustomerBalance，未处理：
- CustomerProfile
- DailyConsumption
- Invoice
- Tag associations
- SyncTask logs

**影响**: 已删除客户的数据残留，可能影响统计准确性。

**优化方案**:
1. 删除时级联软删除所有关联记录
2. 或添加 `deleted_at` 过滤条件到所有查询（确保已删除客户不出现在统计中）
3. 定期清理任务处理孤立数据

**涉及文件**:
- `backend/app/services/customers.py` — `delete_customer` 扩展级联删除

---

### OPT-17: 新增客户弹窗字段不完整 🟡

**现状**:
`AddCustomerModal.vue` 仅包含 11 个字段，缺少：
- 合作状态
- ERP 系统
- 备注
- 首次回款时间
- 接入时间
- 是否启用结算
- 是否停用

创建后需要立即编辑补充信息，增加操作步骤。

**优化方案**:
1. 将新增弹窗改为与编辑弹窗相同的完整字段集
2. 或提供「高级选项」折叠区域，包含非必填字段
3. 创建成功后提示「是否继续完善客户信息」

**涉及文件**:
- `frontend/src/views/customers/components/AddCustomerModal.vue` — 补充缺失字段

---

### OPT-18: useCustomerDetail 职责过重 🟢

**现状**:
`useCustomerDetail` 返回 50+ 个属性/方法，包含：
- 客户数据加载（detail、balance、profile、invoices、usage）
- 表单管理（editForm、validation、submit）
- 标签管理（tags、addTag、removeTag）
- 字典加载（managers、industryTypes、cooperationStatuses、erpSystems）
- Tab 管理（activeTab、loadedTabs、chartRenderState）
- 健康度评分

**影响**: 可维护性差，难以测试，修改一个功能可能影响其他功能。

**优化方案**:
1. 拆分为多个 composable：
   - `useCustomerData` — 客户数据加载
   - `useCustomerEdit` — 编辑表单逻辑
   - `useCustomerTags` — 标签管理
   - `useCustomerTabs` — Tab 切换与懒加载
2. `useCustomerDetail` 作为门面（facade）组合以上 composable

**涉及文件**:
- `frontend/src/composables/useCustomerDetail.ts` — 拆分

---

### OPT-19: 不可排序字段显示可排序图标 🟢

**现状**:
- `health` 字段排序退化为按 `Customer.id` 排序（无实际意义）
- `usage_30d` 排序需要 JOIN 聚合子查询，性能开销大
- 但表头仍显示排序图标，用户点击后体验不佳

**优化方案**:
1. `health` 字段移除排序功能（或实现真正的健康度排序）
2. `usage_30d` 保留排序但添加 loading 提示
3. 表头排序图标仅在有效排序时显示

**涉及文件**:
- `frontend/src/views/customers/components/CustomerTable.vue` — 调整 sortable 配置
- `backend/app/services/customers.py` — 优化 health 排序逻辑

---

### OPT-20: 结算单 Tab 无分页 🟢

**现状**:
```typescript
const res = await getInvoices({ customer_id: customerId.value, page_size: 100 })
```
一次性加载 100 条结算单，对于长期客户可能不够，且无分页控件。

**优化方案**:
1. 添加分页控件
2. 默认 `page_size=20`，支持加载更多
3. 添加结算单状态筛选

**涉及文件**:
- `frontend/src/views/customers/detail/CustomerInvoicesTab.vue` — 添加分页

---

## 三、优先级排序与实施建议

### 第一优先级（立即修复）

| 编号 | 预计工时 | 说明 |
|------|---------|------|
| OPT-02/04 | 0.5d | 健康度中英文不匹配，导致功能完全失效 |
| OPT-03 | 1d | 批量操作空实现，用户操作静默失败 |
| OPT-01 | 1.5d | KPI 4 次请求性能问题，影响页面加载速度 |

### 第二优先级（本迭代修复）

| 编号 | 预计工时 | 说明 |
|------|---------|------|
| OPT-05 | 0.5d | Tab 重复请求，修复简单 |
| OPT-06 | 1d | 预计耗尽天数不准确 |
| OPT-09 | 1d | 编辑非原子事务 |
| OPT-14 | 0.5d | 预览抽屉时间轴无数据 |
| OPT-17 | 1d | 新增弹窗字段不完整 |

### 第三优先级（后续迭代）

| 编号 | 预计工时 | 说明 |
|------|---------|------|
| OPT-07 | 1.5d | 经理数据源区分 |
| OPT-08 | 1d | store 缓存接入 |
| OPT-10 | 1d | 常量提取 |
| OPT-15 | 2d | 消耗聚合缓存 |
| OPT-11 | 1.5d | 跨页全选 |
| OPT-12 | 1d | 导出上限 |
| OPT-16 | 1d | 级联删除 |
| OPT-18 | 2d | composable 拆分 |
| OPT-13 | 0.5d | 默认筛选可配置 |
| OPT-19 | 0.5d | 排序图标修正 |
| OPT-20 | 0.5d | 结算单分页 |

---

## 四、与已有技术债务的关系

本文档中的问题与 `docs/technical_debt/defect-fix-plan-2026-09.md` 中的 DF-01~DF-14 有部分重叠：
- DF-01~DF-02（字段选项不一致）→ 与 OPT-10（常量重复定义）属同一根因
- DF-03（AddCustomerModal 未传 industry_type_id）→ 与 OPT-17（新增弹窗字段不完整）相关
- DF-05~DF-06（结算单状态缺失）→ 独立问题，不在本文档范围

建议将本文档与 `defect-fix-plan-2026-09.md` 合并管理，统一排期。

---

## 五、附录：分析覆盖文件清单

**前端**:
- `views/customers/Index.vue` — 列表页主组件
- `views/customers/Detail.vue` — 详情页主组件
- `views/customers/components/CustomerFilters.vue` — 筛选器
- `views/customers/components/CustomerTable.vue` — 表格
- `views/customers/components/CustomerKpi.vue` — KPI 卡片
- `views/customers/components/PreviewDrawer.vue` — 360 预览抽屉
- `views/customers/components/AddCustomerModal.vue` — 新增弹窗
- `views/customers/components/BatchToolbar.vue` — 批量操作工具栏
- `views/customers/components/CustomerBatchEditModal.vue` — 批量编辑弹窗
- `views/customers/detail/EditCustomerDialog.vue` — 编辑弹窗
- `views/customers/detail/CustomerBasicTab.vue` — 基础信息 Tab
- `views/customers/detail/CustomerProfileTab.vue` — 画像信息 Tab
- `views/customers/detail/CustomerBalanceTab.vue` — 余额信息 Tab
- `composables/useCustomerList.ts` — 列表 composable
- `composables/useCustomerDetail.ts` — 详情 composable
- `stores/customer.ts` — Pinia store
- `api/customers.ts` — API 层
- `router/index.ts` — 路由配置

**后端**:
- `app/routes/customers.py` — 客户路由
- `app/services/customers.py` — 客户服务
- `app/repository/customer_repo.py` — 客户数据访问层
- `app/models/customers.py` — 客户模型
- `app/cache/base.py` — 缓存服务
