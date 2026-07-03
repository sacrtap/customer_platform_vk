# 客户详情页功能优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化客户详情页的 5 项功能：基础信息双列显示、编辑框新增规模/消费等级、删除房地产行业字段、消费等级显示格式化。

**Architecture:** 所有改动集中在单个 Vue 组件 `Detail.vue` 中，涉及模板结构、表单字段、计算属性和样式的修改。编辑提交时需并行调用 `updateCustomer` 和 `updateProfile` 两个 API。

**Tech Stack:** Vue 3.4 + TypeScript 5.3 + Arco Design 2.54 + Vite 5.0

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/views/customers/Detail.vue` | 修改 | 核心改动文件：模板布局、编辑表单、计算属性、样式 |
| `frontend/src/api/customers.ts` | 无 | 已包含 `updateProfile` API，无需修改 |
| `frontend/src/types/index.ts` | 无 | 已包含 `scale_level` 和 `consume_level` 类型定义 |

---

## 实现任务

### Task 1: 基础信息列表改为双列显示

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue:1-176` (模板部分)
- Modify: `frontend/src/views/customers/Detail.vue:1256-1349` (样式部分)

- [ ] **Step 1: 修改基础信息模板为双列布局**

将现有的单列 `<table>` 结构改为双列布局。使用 CSS Grid 实现，保持 `<table>` 结构但修改其渲染方式：

修改 `<template>` 部分的基础信息表格 (约第 34-176 行)，将 `<table>` 改为使用 div + CSS Grid：

```vue
<div class="info-grid">
  <!-- 第 1 行 -->
  <div class="info-item">
    <span class="label">客户名称</span>
    <span class="value">{{ customer.name }}</span>
  </div>
  <div class="info-item">
    <span class="label">公司 ID</span>
    <span class="value">{{ customer.company_id }}</span>
  </div>
  <!-- 第 2 行 -->
  <div class="info-item">
    <span class="label">账号类型</span>
    <span class="value">
      <a-tag>{{ customer.account_type || '-' }}</a-tag>
    </span>
  </div>
  <div class="info-item">
    <span class="label">行业类型</span>
    <span class="value">
      <a-tag>{{ customer.industry || '-' }}</a-tag>
    </span>
  </div>
  <!-- 继续所有字段... -->
</div>
```

需要保留的所有字段（按原顺序，每行 2 个）：
1. 客户名称 | 公司 ID
2. 账号类型 | 行业类型
3. 客户等级 | 重点客户
4. 结算方式 | 结算周期
5. 邮箱 | 所属 ERP
6. 合作状态 | 销售负责人
7. 是否结算 | 是否停用
8. 首次回款时间 | 接入时间
9. 备注 | 创建时间
10. 客户标签 (占满整行)

- [ ] **Step 2: 添加双列布局样式**

在 `<style scoped>` 部分添加/修改样式：

```css
/* 双列信息网格 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0;
  padding: 8px 0;
}

.info-item {
  display: flex;
  flex-direction: column;
  padding: 14px 16px;
  border-bottom: 1px solid var(--neutral-2);
  transition: background-color var(--transition-fast, 150ms);
}

.info-item:hover {
  background-color: var(--neutral-1);
}

.info-item .label {
  font-size: 12px;
  font-weight: 600;
  color: var(--neutral-6);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}

.info-item .value {
  font-size: 14px;
  color: var(--neutral-10);
  font-weight: 500;
  line-height: 1.5;
}

/* 客户标签占满整行 */
.info-item.full-width {
  grid-column: 1 / -1;
}

/* 响应式适配 */
@media (max-width: 768px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .info-item .label {
    font-size: 11px;
  }
  
  .info-item .value {
    font-size: 13px;
  }
}
```

- [ ] **Step 3: 移除旧的表格样式**

删除或注释掉以下旧样式类：
- `.info-table-container`
- `.info-table`
- `.info-table tbody tr`
- `.info-table .label-cell`
- `.info-table .value-cell`

- [ ] **Step 4: 验证页面渲染**

运行前端开发服务器，访问客户详情页，确认：
- 基础信息以双列显示
- 字段对齐正确
- 响应式布局在小屏幕下变为单列
- 所有字段数据正常显示

---

### Task 2: 编辑对话框增加规模等级和消费等级

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue:374-494` (编辑对话框模板)
- Modify: `frontend/src/views/customers/Detail.vue:602-622` (EditForm 接口)
- Modify: `frontend/src/views/customers/Detail.vue:762-782` (editForm 初始化)
- Modify: `frontend/src/views/customers/Detail.vue:914-937` (openEditModal 函数)
- Modify: `frontend/src/views/customers/Detail.vue:939-974` (handleEditSubmit 函数)

- [ ] **Step 1: 更新 EditForm 接口定义**

在 `<script setup>` 中的 `EditForm` 接口添加新字段：

```typescript
interface EditForm {
  name: string
  email: string
  account_type?: string
  industry?: string
  customer_level?: string
  settlement_type?: string
  settlement_cycle?: string
  is_key_customer?: boolean
  manager_id?: number
  erp_system?: string
  first_payment_date?: string
  onboarding_date?: string
  sales_manager_id?: number
  cooperation_status?: string
  is_settlement_enabled?: boolean
  is_disabled?: boolean
  notes?: string
  // 新增字段
  scale_level?: string
  consume_level?: string
}
```

- [ ] **Step 2: 在编辑表单中添加规模等级下拉选择器**

在编辑对话框的 `<a-form>` 中，在"客户等级"字段之后添加：

```vue
<a-form-item field="scale_level" label="规模等级">
  <a-select v-model="editForm.scale_level" placeholder="请选择规模等级" allow-clear>
    <a-option value="100">100人</a-option>
    <a-option value="500">500人</a-option>
    <a-option value="1000">1000人</a-option>
    <a-option value="2000">2000人</a-option>
    <a-option value="5000">5000人</a-option>
  </a-select>
</a-form-item>
```

- [ ] **Step 3: 在编辑表单中添加消费等级下拉选择器**

在"规模等级"字段之后添加：

```vue
<a-form-item field="consume_level" label="消费等级">
  <a-select v-model="editForm.consume_level" placeholder="请选择消费等级" allow-clear>
    <a-option value="S">S - 100万</a-option>
    <a-option value="A">A - 50万</a-option>
    <a-option value="B">B - 25万</a-option>
    <a-option value="C">C - 12万</a-option>
    <a-option value="D">D - 6万</a-option>
  </a-select>
</a-form-item>
```

- [ ] **Step 4: 更新 editForm 初始化**

在 `editForm` 的 `ref` 初始化中添加新字段默认值：

```typescript
const editForm = ref<EditForm>({
  // ... 现有字段
  notes: undefined,
  // 新增字段
  scale_level: undefined,
  consume_level: undefined,
})
```

- [ ] **Step 5: 更新 openEditModal 函数**

在打开编辑对话框时，从 profile 数据中读取规模等级和消费等级：

```typescript
const openEditModal = () => {
  editForm.value = {
    // ... 现有字段
    notes: customer.value.notes || undefined,
    // 新增字段
    scale_level: profile.value.scale_level || undefined,
    consume_level: profile.value.consume_level || undefined,
  }
  editModalVisible.value = true
}
```

- [ ] **Step 6: 更新 handleEditSubmit 函数**

修改提交逻辑，并行调用两个 API：

```typescript
const handleEditSubmit = async () => {
  editLoading.value = true
  try {
    // 并行更新 Customer 和 CustomerProfile
    const [customerRes, profileRes] = await Promise.all([
      updateCustomer(customerId.value, {
        name: editForm.value.name,
        email: editForm.value.email || undefined,
        account_type: editForm.value.account_type || undefined,
        industry: editForm.value.industry || undefined,
        customer_level: editForm.value.customer_level || undefined,
        settlement_type: editForm.value.settlement_type,
        settlement_cycle: editForm.value.settlement_cycle || undefined,
        is_key_customer: editForm.value.is_key_customer,
        manager_id: editForm.value.manager_id || undefined,
        erp_system: editForm.value.erp_system || undefined,
        first_payment_date: editForm.value.first_payment_date || undefined,
        onboarding_date: editForm.value.onboarding_date || undefined,
        sales_manager_id: editForm.value.sales_manager_id || undefined,
        cooperation_status: editForm.value.cooperation_status || undefined,
        is_settlement_enabled: editForm.value.is_settlement_enabled,
        is_disabled: editForm.value.is_disabled,
        notes: editForm.value.notes || undefined,
      }),
      updateProfile(customerId.value, {
        scale_level: editForm.value.scale_level || undefined,
        consume_level: editForm.value.consume_level || undefined,
      }),
    ])
    
    Message.success('更新成功')
    editModalVisible.value = false
    customerStore.invalidateCustomerCache(customerId.value)
    await loadCustomerData()
  } catch (error) {
    Message.error('更新失败')
    console.error('更新失败:', error)
  } finally {
    editLoading.value = false
  }
}
```

- [ ] **Step 7: 导入 updateProfile API**

确保在文件顶部导入 `updateProfile`：

```typescript
import { getCustomer, updateCustomer, getProfile, updateProfile } from '@/api/customers'
```

---

### Task 3: 删除画像信息中的"房地产行业"字段

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue:179-216` (画像信息模板)

- [ ] **Step 1: 移除房地产行业卡片**

在画像信息 tab 的 `metrics-grid` 中，删除第 4 个指标卡片（约第 207-215 行）：

```vue
<!-- 删除以下代码块 -->
<div v-if="profileLoading" class="metric-card loading">
  <SkeletonCard height="72px" />
</div>
<div v-else class="metric-card">
  <span class="metric-label">房地产行业</span>
  <a-tag :color="profile.is_real_estate ? 'orange' : 'gray'" size="large">
    {{ profile.is_real_estate ? '是' : '否' }}
  </a-tag>
</div>
```

删除后，核心指标区从 4 个卡片变为 3 个卡片（规模等级、消费等级、所属行业）。

- [ ] **Step 2: 调整网格布局**

由于卡片从 4 个变为 3 个，修改 `.metrics-grid` 的 CSS 使其适配 3 个卡片：

```css
/* 核心指标网格 - 3 列布局 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
```

---

### Task 4: 画像信息消费等级显示格式化

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue:195-196` (消费等级显示)
- Modify: `frontend/src/views/customers/Detail.vue` (添加计算属性)

- [ ] **Step 1: 创建消费等级显示计算属性**

在 `<script setup>` 中添加计算属性：

```typescript
// 消费等级显示映射
const CONSUME_LEVEL_MAP: Record<string, string> = {
  S: 'S - 100万',
  A: 'A - 50万',
  B: 'B - 25万',
  C: 'C - 12万',
  D: 'D - 6万',
}

// 消费等级显示文本
const consumeLevelDisplay = computed(() => {
  const level = profile.value.consume_level
  if (!level) return '-'
  return CONSUME_LEVEL_MAP[level] || level
})
```

- [ ] **Step 2: 更新模板中的消费等级显示**

将画像信息中的消费等级显示从：

```vue
<span class="metric-value">{{ profile.consume_level || '-' }}</span>
```

改为：

```vue
<span class="metric-value">{{ consumeLevelDisplay }}</span>
```

---

### Task 5: 代码质量检查与验证

**Files:**
- All modified files

- [ ] **Step 1: 运行 TypeScript 类型检查**

```bash
cd frontend && npm run type-check
```

确保无类型错误。

- [ ] **Step 2: 运行 ESLint 检查**

```bash
cd frontend && npm run lint
```

修复所有 lint 错误。

- [ ] **Step 3: 运行 Prettier 格式化**

```bash
cd frontend && npm run format
```

- [ ] **Step 4: 功能验证清单**

在浏览器中手动验证以下功能：

| 功能点 | 验证步骤 | 预期结果 |
|--------|---------|---------|
| 基础信息双列 | 访问客户详情页 → 基础信息 tab | 字段以 2 列显示，对齐正确 |
| 规模等级编辑 | 点击编辑 → 选择规模等级 → 保存 | 保存成功，刷新后显示正确 |
| 消费等级编辑 | 点击编辑 → 选择消费等级 → 保存 | 保存成功，刷新后显示正确 |
| 删除房地产行业 | 访问客户详情页 → 画像信息 tab | 不再显示"房地产行业"卡片 |
| 消费等级显示 | 访问客户详情页 → 画像信息 tab | 显示格式为 "S - 100万" |
| 响应式布局 | 缩小浏览器窗口 | 基础信息变为单列，指标卡片自适应 |

- [ ] **Step 5: 提交代码**

```bash
git add frontend/src/views/customers/Detail.vue
git commit -m "feat: 优化客户详情页 - 双列布局、新增规模/消费等级编辑、删除房地产行业字段"
```

---

## 自审检查

### 1. 规范覆盖检查

| 需求点 | 对应任务 | 状态 |
|--------|---------|------|
| 基础信息双列显示 | Task 1 | ✅ 已覆盖 |
| 编辑框增加规模等级 | Task 2 (Step 2, 4, 5, 6) | ✅ 已覆盖 |
| 删除房地产行业字段 | Task 3 | ✅ 已覆盖 |
| 编辑框增加消费等级 | Task 2 (Step 3, 4, 5, 6) | ✅ 已覆盖 |
| 消费等级显示格式化 | Task 4 | ✅ 已覆盖 |
| price_policy 不处理 | 无 | ✅ 已确认不处理 |

### 2. 占位符扫描

- ✅ 无 "TBD"、"TODO" 或未完成的步骤
- ✅ 所有步骤都有具体代码和命令
- ✅ 无 "类似 Task N" 的引用

### 3. 类型一致性

- ✅ `EditForm` 接口已添加 `scale_level` 和 `consume_level`
- ✅ `updateProfile` API 已在导入中声明
- ✅ `CONSUME_LEVEL_MAP` 映射与后端存储值一致
- ✅ 所有字段类型与 `CustomerProfile` 类型定义匹配

### 4. 边界情况

- ✅ 消费等级映射处理了 null/undefined 情况（返回 '-'）
- ✅ 消费等级映射处理了未知值（返回原值）
- ✅ 编辑提交时两个 API 并行调用，任一失败都会提示错误
- ✅ 编辑成功后清除缓存并重新加载数据
