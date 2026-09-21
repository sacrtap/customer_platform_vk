# Design — 批量编辑弹框新增行业与 ERP 编辑项

## 决策记录

| 候选编辑项 | 决策 | 理由 |
|---|---|---|
| `industry_type_id` 行业类型 | ✅ 纳入 | 用户明确需求；后端白名单已含、已有存在性校验与 profile 更新/自动创建逻辑 |
| `erp_system` ERP 系统 | ✅ 纳入 | 后端白名单已含；整批接入同一 ERP 是高频场景；有现成字典与单条编辑先例 |
| `first_payment_date` / `onboarding_date` | ❌ 不纳入 | 日期批量覆盖场景少，增加弹框复杂度 |
| `notes` 备注 | ❌ 不纳入 | 批量覆盖有误覆盖风险 |
| `name` / `company_id` / `email` | ❌ 不纳入 | 唯一标识/唯一约束/强个性化，不适合批量改写 |

## 改动文件（仅前端 2 个文件）

### 1. `frontend/src/views/customers/components/CustomerBatchEditModal.vue`（主改动）

**props**：新增 `industryTypes?: IndustryType[]`、`erpSystems?: ErpSystem[]`（复用 Index.vue 已加载字典；不传时 fallback 自行加载，与 cooperationStatuses 的 onMounted 模式一致）

**状态扩展**（三处同步加 `industry_type_id` / `erp_system`）：
- `batchForm`：`industry_type_id: null as number | null`、`erp_system: ''`
- `batchFieldsSelected`：`industry_type_id: false`、`erp_system: false`
- `fieldNames`：`'行业类型'`、`'ERP 系统'`

**template**：在「消费等级」后追加两个 `.batch-field-item`，模式与现有 select 项完全一致：
- 行业类型：checkbox + `a-select`（`allow-clear`，`v-for="type in industryTypes"`，`:value="type.id"`，label 为 `type.name`）
- ERP 系统：checkbox + `a-select`（`allow-clear`，`v-for="sys in erpSystems"`，`:value="sys.value"`，label 为 `sys.name`）

**resetForm**：增加 `industry_type_id = null`、`erp_system = ''` 重置。

**加载逻辑**：`onMounted` 内若 props 未传则 `getIndustryTypes()` / `getErpSystemsList()` 自行加载（兜底）。

**无需改动**：`selectedFields` / `previewRows` / `confirmBatchSubmit` 为对象遍历，自动包含新字段。

### 2. `frontend/src/views/customers/Index.vue`

`<CustomerBatchEditModal>` 增加 `:industry-types="industryTypes"`、`:erp-systems="erpSystems"`（数据源已在 setup 中解构）。

## 数据流

```
Index.vue 多选 → 批量编辑 → 勾选字段 checkbox
→ batchForm[key] 赋值 → 预览(遍历 batchFieldsSelected)
→ confirmBatchSubmit 收集勾选字段 → POST /customers/batch-update {customer_ids, fields}
→ 后端白名单校验 + industry_type_id 存在性校验 + profile 更新
→ 返回 success/failed 列表 → 前端 Message/Modal 提示 → emit submitted → 列表刷新
```

## 边界与风险

- **清空语义**：行业 select `allow-clear` 清空后值为 `null`；`previewRows` 对 null 值跳过显示，但提交时携带 null（清空行业）。与现有 `is_real_estate` 行为一致，接受。
- **字段名冲突**：无。`industry_type_id`/`erp_system` 均在现有白名单内。
- **字典兜底**：若 Index.vue 未传字典，弹框内自载兜底，不阻塞功能。
- **后端**：零改动，风险低。
