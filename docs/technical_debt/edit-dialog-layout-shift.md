# EditCustomerDialog 编辑弹框布局抖动问题排查报告

**创建日期**: 2026-09-11
**排查方法**: 源码逐行分析 + Arco Design Form 组件行为推演
**涉及文件**: `frontend/src/views/customers/detail/EditCustomerDialog.vue`

---

## 一、问题描述

在「编辑客户」弹框中，当用户清空任意带 `allow-clear` 的下拉选择字段（如结算周期、价格策略、行业类型等）后，弹框内的布局会产生可见的动态变化（抖动/重排）。

---

## 二、根因分析

### 根因 1：三列布局中 form-item 数量不对等，高度不齐

**布局结构**:

| 列 | 包含的 form-item | 数量 |
|----|-----------------|------|
| 列一（基础信息） | name, company_id, email, account_type, industry_type_id, is_real_estate, sales_manager_id | **7 项** |
| 列二（结算与业务） | settlement_type, settlement_cycle, price_policy, erp_system, cooperation_status, is_settlement_enabled, manager_id | **7 项** |
| 列三（等级与消费） | scale_level, consume_level, is_key_customer, first_payment_date, onboarding_date, is_disabled | **6 项** |

列三比列一、列二少 1 个 form-item，导致初始高度就不齐。当列一或列二中某个字段因校验产生错误消息时，该列高度增加，而列三不变，视觉上产生跳动。

### 根因 2：`validate-trigger="['blur', 'change']"` 导致清空即触发校验

表单设置了 `validate-trigger="['blur', 'change']"`，这意味着：

1. 用户清空一个带 `allow-clear` 的 `a-select`（如 `settlement_cycle`）
2. `v-model` 值从 `"monthly"` 变为 `undefined`
3. Arco Design 触发 `change` 事件
4. Form 立即执行该字段的校验规则
5. 如果有校验规则（如 `required`），错误消息出现 → form-item 高度增加
6. 如果无校验规则，不产生错误消息，但 Arco Design 仍可能短暂触发布局重算

**关键问题**: `settlement_type` 是 required 字段且**没有** `allow-clear`，如果用户手动将其选中再清空（通过选择另一个值再删除），校验错误消息会立即出现在列二中，导致列二高度突增。

### 根因 3：`allow-clear` 的 `a-select` 清空时值变为 `undefined`，触发响应式重渲染

表单中有 **14 个带 `allow-clear` 的控件**。当用户清空其中一个时：

1. `editForm.xxx` 从有值变为 `undefined`
2. Vue 响应式系统触发组件重渲染
3. `a-select` 组件从「已选中」状态切换到「placeholder 显示」状态
4. 如果该字段在 `editFormRules` 中有校验规则，错误消息区域从 0 高度变为有内容高度
5. 整个 `a-form-item` 的高度增加约 20-24px（Arco Design 默认错误消息行高）
6. 该 `a-col` 内的后续 form-item 全部下移

### 根因 4：`a-spin` 的 loading 状态切换导致内容区域闪烁

```vue
<a-spin :loading="fetchLoading" tip="加载客户数据中...">
  <a-form ...>
```

当弹框打开时，`fetchLoading` 从 `true` 变为 `false`（数据加载完成后），`a-spin` 从加载占位切换到实际表单内容，这个切换过程会产生一次明显的布局变化。

### 根因 5：字典数据异步加载导致 select 选项动态变化

```typescript
const loadDictData = async () => {
  // 1. 加载行业类型
  // 2. 加载 managers
  // 3. 加载合作状态
  // 4. 加载 ERP 系统字典
}
```

这些数据在弹框打开后异步加载。当数据返回时，`a-select` 的选项列表从空变为有值，可能导致下拉面板尺寸变化（虽然不影响主表单布局，但如果 select 有默认值且选项未就绪，选中状态会在选项到达后更新，引起一次微小的重渲染）。

### 根因 6：`price_policy` 的中文→英文映射逻辑可能导致值与选项不匹配

```typescript
price_policy: c.price_policy
  ? ({ 定价: 'pricing', 阶梯: 'tiered', 包年: 'yearly' } as Record<string, string>)[
      c.price_policy
    ] || c.price_policy
  : undefined,
```

如果后端返回的 `price_policy` 值不在映射表中（如后端返回了 `pricing` 而非 `定价`），映射结果为 `undefined`（fallback 到原值 `pricing`），此时 `a-select` 的选项列表中 `pricing` 对应的是 `定价` 标签。但如果后端返回了不在前端选项中的值（如 `monthly`），select 会显示空值，用户清空时不会触发额外变化，但初始渲染可能有一帧的闪烁。

---

## 三、具体表现场景

### 场景 1：清空「结算周期」
1. 用户点击 `settlement_cycle` 的 clear 按钮
2. 值从 `"monthly"` 变为 `undefined`
3. `settlement_cycle` 没有 required 校验规则，所以无错误消息
4. 但 `a-select` 从「显示选中值」切换到「显示 placeholder」，高度不变
5. 由于 `validate-trigger` 包含 `change`，Form 组件仍执行一次校验逻辑
6. 整个表单触发一次响应式更新，可能引起微小的重排

### 场景 2：清空「结算方式」（settlement_type）
1. `settlement_type` 是 required 字段
2. 但它**没有 `allow-clear`**，用户无法通过 clear 按钮清空
3. 如果用户通过选择新值再取消来间接清空，required 校验立即触发
4. 错误消息「请选择结算方式」出现在列二中
5. 列二高度增加 ~24px，列一和列三不变
6. **可见的布局抖动**

### 场景 3：弹框首次打开
1. `fetchLoading = true` → spin 显示加载占位
2. 异步加载字典数据 + 客户详情
3. `fetchLoading = false` → 表单内容出现
4. 各 `a-select` 选项从空变为有值
5. 有值的字段从 placeholder 切换到选中值
6. **一次完整的布局重排**

---

## 四、优化建议

### 建议 1：固定三列高度（推荐 P0）

给三列设置 `min-height` 或使用 CSS Grid 等高列布局：

```css
/* 方案 A：使用 align-items: stretch（默认行为）+ min-height */
.a-row {
  align-items: flex-start; /* 改为 stretch 可让列等高 */
}

/* 方案 B：给每个 a-col 设置 min-height */
.a-col {
  min-height: 480px; /* 根据最大列内容高度设定 */
}
```

或在 `a-row` 上使用 CSS Grid：

```vue
<a-form ...>
  <div class="form-grid">
    <div class="form-col">列一内容</div>
    <div class="form-col">列二内容</div>
    <div class="form-col">列三内容</div>
  </div>
</a-form>
```

```css
.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  align-items: start; /* 各列顶部对齐，不强制等高 */
}
```

### 建议 2：禁用实时校验，改为提交时校验（推荐 P1）

将 `validate-trigger` 改为仅在 blur 时触发，或完全移除实时校验：

```vue
<!-- 方案 A：仅 blur 时校验 -->
<a-form ... validate-trigger="['blur']">

<!-- 方案 B：不设置 validate-trigger，使用默认行为（change）-->
<!-- 但默认行为也会实时校验，所以方案 A 更好 -->

<!-- 方案 C：完全移除 validate-trigger，在提交时手动调用 validate() -->
<a-form ... >
```

### 建议 3：为所有 `a-form-item` 预留错误消息空间（推荐 P0）

给每个 `a-form-item` 添加固定的 `help` slot 或 CSS `min-height`，确保校验消息出现时不改变高度：

```css
:deep(.arco-form-item-message) {
  min-height: 22px; /* 预留错误消息空间 */
}
```

或使用 Arco Design 的 `help` prop 预先占位：

```vue
<a-form-item field="settlement_type" label="结算方式" required help=" ">
  <!-- help=" " 会让 form-item 始终预留消息空间 -->
</a-form-item>
```

### 建议 4：字典数据预加载，消除弹框打开后的异步闪烁（推荐 P1）

将字典数据加载提前到父组件 `Detail.vue` 中，在弹框打开前就完成加载：

```typescript
// Detail.vue
const industryTypes = ref<IndustryType[]>([])
const managers = ref([])
const cooperationStatuses = ref([])

onMounted(async () => {
  // 并行预加载所有字典数据
  const [indRes, mgrRes, coopRes, erpRes] = await Promise.allSettled([
    getIndustryTypes(),
    getManagers(),
    getCooperationStatusesList(),
    getErpSystemsList(),
  ])
  // 赋值...
})

// 传递给 EditCustomerDialog 作为 props
```

### 建议 5：`settlement_type` 添加 `allow-clear` 或移除 `required`（推荐 P2）

当前 `settlement_type` 是 required 但没有 `allow-clear`，用户无法清空它。这是一个 UX 矛盾：
- 如果该字段必填，应允许用户清空后重新选择 → 添加 `allow-clear`
- 如果该字段不应被清空 → 保持现状，但需确保有默认值

建议添加 `allow-clear` 并在 `editFormRules` 中保留 required 规则。

### 建议 6：使用 `v-show` 替代 `v-if`/loading 切换（推荐 P2）

当前 `a-spin` 包裹整个表单，loading 状态切换会导致内容区域从 DOM 中移除/恢复。可以改为：

```vue
<a-spin :loading="fetchLoading" tip="加载客户数据中...">
  <div v-show="!fetchLoading">
    <a-form ...>
  </div>
</a-spin>
```

这样表单 DOM 始终存在，仅通过 CSS 控制可见性，避免 DOM 重建引起的布局抖动。

---

## 五、优先级排序

| 优先级 | 建议 | 预计工时 | 效果 | 状态 |
|--------|------|---------|------|------|
| P0 | 建议 3：CSS 预留错误消息空间 | 5min | 消除校验消息引起的布局抖动 | ✅ 已实施 |
| P0 | 建议 1：Grid 布局或固定列高度 | 15min | 消除列间高度不齐 | ✅ 已实施 |
| P1 | 建议 2：改为 blur-only 校验 | 5min | 减少不必要实时校验 | ✅ 已实施 |
| P1 | 建议 4：字典预加载 | 20min | 消除弹框打开后的异步闪烁 | ✅ 已实施 |
| P2 | 建议 5：settlement_type 添加 allow-clear | 2min | UX 一致性 | ✅ 已实施 |
| P2 | 建议 6：v-show 替代 loading 切换 | 10min | 减少 DOM 重建 | ✅ 已实施 |

---

## 六、实施详情

### 实施日期: 2026-09-11

### 修改文件

| 文件 | 修改内容 |
|------|--------|
| `frontend/src/views/customers/detail/EditCustomerDialog.vue` | 全部 6 项优化：CSS min-height、Grid 布局、blur-only 校验、v-show loading 切换、settlement_type allow-clear、字典 props 接收 |
| `frontend/src/views/customers/Detail.vue` | 传递 managers/cooperationStatuses/erpSystems props 给 EditCustomerDialog |
| `frontend/src/composables/useCustomerDetail.ts` | 添加 cooperationStatuses 和 erpSystems 的预加载逻辑 |
| `.trellis/spec/frontend/component-guidelines.md` | 新增「布局稳定性」章节（R1-R6 规则） |

### 验证结果

- ✅ 前端 lint 检查通过（0 errors）
- ✅ TypeScript 类型检查通过（本次修改文件无新错误）
- ✅ 后端测试无回归

## 七、宽高优化（第二轮）

### 问题
首轮优化后布局不再抖动，但弹框宽度 960px 过宽，三列 Grid 在此宽度下每列约 304px，而表单控件实际只需 ~220px，导致右侧大量留白。

### 调整方案

| 调整项 | 调整前 | 调整后 | 原因 |
|--------|--------|--------|------|
| 弹框宽度 (≥1024px) | 960px | **800px** | 减少右侧空白，每列 ~250px 足够容纳所有控件 |
| 列一字段数 | 7 | 7 (不变) | — |
| 列二字段数 | 7 | **8** | 将「是否停用」从列三移入，平衡高度 |
| 列三字段数 | 6 | **5** | 移出「是否停用」后更紧凑 |

### 字段分布（调整后）

| 列 | 分区标题 | 包含字段 | 数量 |
|----|---------|---------|------|
| 列一 | 基础信息 | name, company_id, email, account_type, industry_type_id, is_real_estate, sales_manager_id | 7 |
| 列二 | 结算与业务 | settlement_type, settlement_cycle, price_policy, erp_system, cooperation_status, is_settlement_enabled, manager_id, **is_disabled** | 8 |
| 列三 | 等级与消费 | scale_level, consume_level, is_key_customer, first_payment_date, onboarding_date | 5 |
| 全宽 | 备注 | notes | 1 |

### Commit
`abc236f` - fix: EditCustomerDialog 宽度优化 960px→800px + 列字段数平衡(7/8/5)

## 八、变更记录

| 日期 | 内容 | 操作人 |
|------|------|--------|
| 2026-09-11 | 初始排查，发现 6 个根因，提出 6 条优化建议 | CatPaw Agent |
| 2026-09-11 | **全部 6 项优化已实施完成**。P0-P2 全部落地，spec 已更新「布局稳定性」章节 | CatPaw Agent |
