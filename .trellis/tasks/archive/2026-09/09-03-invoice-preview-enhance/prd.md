# 结算单生成优化-周期保留与计费明细预览增强

## Goal

优化生成结算单弹窗（GenerateInvoiceModal）的用户体验：
1. 每次打开弹窗时保留上次选择的结算周期，但清空客户输入框
2. 客户选择或结算周期变化时自动刷新计费明细预览
3. 计费明细预览严格按照计费规则配置呈现，直观展示每种计费类型的计算明细

## Background

### 当前行为

- 弹窗打开时**完全重置所有字段**（包括结算周期和客户）
- 按指定客户模式下，**仅在结算周期变化时**调用 `calculateInvoiceItems`，选择客户时不会自动刷新预览
- 计费明细预览表格列固定为：设备类型 | 楼层 | 数量 | 单价 | 小计，**不区分**计费类型（fixed/tiered/package）
- 后端 `calculate-items` 路由在格式化返回数据时丢弃了 `pricing_type`、`package_type`、`tiers`、`period_days`、`limit_count`、`over_limit_*` 等字段（service 层已计算但路由未透传）

### 三种计费类型的 item 结构差异

| 字段 | fixed（定价） | tiered（阶梯） | package-unlimited | package-limited |
|------|-------|---------|---------|---------|
| device_type | ✅ | ✅ | None | None |
| layer_type | ✅ | ✅ | None | None |
| quantity | 订单数/楼层数 | 楼层数 | 楼层数 | 订单数 |
| unit_price | 单价 | 平均单价 | 日费 | base_fee/limit_count |
| subtotal | ✅ | ✅ | 周期基础费 | 用量费+超量费 |
| order_count | 多层递增时有 | ❌ | ✅ | ✅ |
| additional_floor_price | 多层递增时有 | ❌ | ❌ | ❌ |
| multi_floor_pricing_type | 多层递增时有 | ❌ | ❌ | ❌ |
| package_type | ❌ | ❌ | "unlimited" | "limited" |
| limit_count | ❌ | ❌ | ❌ | ✅ |
| over_limit_quantity | ❌ | ❌ | ❌ | ✅ |
| over_limit_unit_price | ❌ | ❌ | ❌ | ✅ |
| over_limit_cost | ❌ | ❌ | ❌ | ✅ |
| period_days | ❌ | ❌ | ✅ | ❌ |
| pricing_rule_id | ✅ | ✅ | ✅ | ✅ |

## Requirements

### R1: 结算周期保留

- 每次打开弹窗时，保留上次选择的结算周期（`periodRange` 和 `batchPeriodRange`）
- 同时清空客户输入框（`form.customer_id = undefined`，CustomerAutoComplete 的显示文本清空）
- 计费明细预览数据也一并清空（因为客户已变）

### R2: 自动刷新计费明细预览

- 在"按指定客户"模式下，当以下任一条件满足时自动调用 `calculateInvoiceItems` 刷新预览：
  - 客户选择变化（`form.customer_id` 改变）且结算周期已选择
  - 结算周期变化且客户已选择
- 当前 `handlePeriodChange` 已处理周期变化场景，需要新增 `watch(form.customer_id)` 处理客户变化场景

### R3: 计费明细预览按计费规则呈现

#### 后端改动

`calculate-items` 路由（`backend/app/routes/billing/invoices.py:295`）格式化时补充返回以下字段：
- `pricing_type`（fixed / tiered / package）
- `package_type`（unlimited / limited）
- `limit_count`、`over_limit_quantity`、`over_limit_unit_price`、`over_limit_cost`
- `usage_cost`（包年限量时套餐内用量费用）
- `period_days`
- `pricing_rule_id`
- `tiers`（阶梯配置，用于前端展示阶梯明细）

#### 前端改动

计费明细预览表格重构为统一表格 + 条件列扩展：

| 列名 | 适用类型 | 数据来源 | 说明 |
|------|---------|---------|------|
| 计费类型 | 全部 | `pricing_type` | 定价/阶梯/包年 |
| 设备类型 | fixed / tiered | `device_type` | 包年时显示 "—" |
| 楼层 | fixed / tiered | `layer_type` | 单层/多层/— |
| 用量 | 全部 | `order_count` 或 `quantity` | 按类型选择合适字段 |
| 计费规则 | 全部 | 按类型动态渲染 | 见下方 |
| 小计 | 全部 | `subtotal` | 格式化为金额 |

「计费规则」列按类型渲染：
- **fixed**：`单价 ¥10.00/单`；多层递增时显示 `基础 ¥10.00/单 + 附加 ¥5.00/层（订单1234 + 附加56层）`
- **tiered**：展示阶梯配置 `0-1000@¥10 → 1001-5000@¥8 → 5001+@¥5`，平均单价
- **package-unlimited**：`不限量套餐，年费¥36,500 → 日费¥100.00 × 30天 = ¥3,000.00`
- **package-limited**：`限量套餐(A)，套餐内5000单@¥7.30=¥36,500 + 超量200单@¥7.30=¥1,460`

## Acceptance Criteria

- [x] AC1: 打开弹窗 → 选择客户和结算周期 → 关闭弹窗 → 再次打开弹窗，结算周期保留显示，客户输入框为空
- [x] AC2: 打开弹窗 → 结算周期已有值 → 选择客户后自动刷新计费明细预览（无需手动改周期）
- [x] AC3: 已选客户 → 修改结算周期 → 预览自动刷新
- [x] AC4: 客户为定价结算 → 预览表格显示"定价"计费类型列、单价、小计
- [x] AC5: 客户为阶梯结算 → 预览表格显示"阶梯"计费类型列、阶梯配置明细、平均单价、小计
- [x] AC6: 客户为包年不限量 → 预览表格显示"包年-不限量"、年费/日费/周期天数/周期费
- [x] AC7: 客户为包年限量 → 预览表格显示"包年-限量"、套餐内用量费+超量费明细
- [x] AC8: 客户有多条不同设备/楼层的定价规则 → 预览表格显示多行，每行对应一条规则
- [x] AC9: `calculate-items` API 返回数据包含所有计费规则相关字段
- [x] AC10: 批量模式下结算周期也保留

## Out of Scope

- 批量模式（"按计费类型"）下的计费明细预览（仅保留客户列表预览）
- 结算单详情页面的明细展示优化
- 后端 `calculate_items_from_rules` 计算逻辑的修改（仅改路由格式化层）
- 前端 `CustomerAutoComplete` 组件本身的修改

## Technical Notes

### 受影响文件

| 文件 | 变更 |
|------|------|
| `backend/app/routes/billing/invoices.py` | `calculate-items` 路由格式化补充字段 |
| `frontend/src/views/billing/components/GenerateInvoiceModal.vue` | 周期保留、客户变化自动刷新、表格列重构 |
| `frontend/src/api/billing.ts` | 更新返回类型定义（如有需要） |

### 不需修改的文件

- `frontend/src/components/CustomerAutoComplete.vue` — 已通过 v-model 正确传递 customer_id
- `frontend/src/views/billing/Invoices.vue` — 仅通过 v-model:visible 和 @success 引用
