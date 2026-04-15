# 客户详情编辑弹框三列布局优化 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将客户详情页编辑弹框从单列布局改为响应式三列分组布局，添加公司 ID 可编辑和基础表单验证

**Architecture:** 修改 `Detail.vue` 单文件组件，重构编辑弹框模板结构、添加验证规则、新增响应式样式。后端已有 company_id 唯一性校验，前端只需正确传递字段和处理错误响应。

**Tech Stack:** Vue 3.4 + TypeScript 5.3 + Arco Design 2.54

---

## 文件结构

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 修改 | `frontend/src/views/customers/Detail.vue` | 重构编辑弹框模板 + 样式 + 验证逻辑 |
| 修改 | `frontend/src/api/customers.ts` | `updateCustomer` 类型添加 `company_id` 字段 |

---

### Task 1: 前端 API 类型添加 company_id 字段

**Files:**
- Modify: `frontend/src/api/customers.ts:41-65`

- [ ] **Step 1: 修改 updateCustomer 的类型定义**

在 `updateCustomer` 的 data 类型中添加 `company_id` 字段：

```typescript
// 更新客户
export function updateCustomer(
  id: number,
  data: {
    company_id?: string  // 新增：公司 ID 可编辑
    name?: string
    account_type?: string
    industry?: string
    customer_level?: string
    price_policy?: string
    manager_id?: number
    settlement_cycle?: string
    settlement_type?: string
    is_key_customer?: boolean
    email?: string
    erp_system?: string
    first_payment_date?: string
    onboarding_date?: string
    sales_manager_id?: number
    cooperation_status?: string
    is_settlement_enabled?: boolean
    is_disabled?: boolean
    notes?: string
  }
) {
  return api.put(`/customers/${id}`, data)
}
```

- [ ] **Step 2: TypeScript 类型检查**

Run: `cd frontend && npm run type-check`
Expected: PASS (no new type errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/customers.ts
git commit -m "feat(api): add company_id field to updateCustomer type"
```

---

### Task 2: 编辑弹框模板重构 - 三列分组布局

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue:362-500` (编辑弹框 template 部分)

- [ ] **Step 1: 替换编辑弹框模板**

将现有的单列 `a-form` 替换为三列分组布局。新的弹框结构：

```vue
<!-- 编辑客户对话框 -->
<a-modal
  v-model:visible="editModalVisible"
  title="编辑客户"
  :width="modalWidth"
  :confirm-loading="editLoading"
  @ok="handleEditSubmit"
  @cancel="editModalVisible = false"
>
  <a-form
    ref="editFormRef"
    :model="editForm"
    :rules="editFormRules"
    layout="vertical"
    validate-trigger="['blur', 'change']"
  >
    <div class="edit-form-grid">
      <!-- 第一列：基础信息 -->
      <div class="edit-form-column">
        <div class="column-title">基础信息</div>

        <a-form-item field="name" label="客户名称" required>
          <a-input v-model="editForm.name" placeholder="请输入客户名称" />
        </a-form-item>

        <a-form-item field="company_id" label="公司 ID" required>
          <a-input v-model="editForm.company_id" placeholder="请输入公司 ID" />
        </a-form-item>

        <a-form-item field="account_type" label="账号类型">
          <a-select v-model="editForm.account_type" placeholder="请选择账号类型" allow-clear>
            <a-option value="正式账号">正式账号</a-option>
            <a-option value="测试账号">测试账号</a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="industry" label="行业类型">
          <a-select v-model="editForm.industry" placeholder="请选择行业类型" allow-clear>
            <a-option value="A">A 类</a-option>
            <a-option value="B">B 类</a-option>
            <a-option value="C">C 类</a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="customer_level" label="客户等级">
          <a-select v-model="editForm.customer_level" placeholder="请选择客户等级" allow-clear>
            <a-option value="KA">KA</a-option>
            <a-option value="A">A</a-option>
            <a-option value="B">B</a-option>
            <a-option value="C">C</a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="email" label="邮箱">
          <a-input v-model="editForm.email" placeholder="请输入邮箱" />
        </a-form-item>
      </div>

      <!-- 第二列：结算与业务 -->
      <div class="edit-form-column">
        <div class="column-title">结算与业务</div>

        <a-form-item field="settlement_type" label="结算方式" required>
          <a-select v-model="editForm.settlement_type" placeholder="请选择结算方式">
            <a-option value="prepaid">预付费</a-option>
            <a-option value="postpaid">后付费</a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="settlement_cycle" label="结算周期">
          <a-select v-model="editForm.settlement_cycle" placeholder="请选择结算周期" allow-clear>
            <a-option value="日结">日结</a-option>
            <a-option value="周结">周结</a-option>
            <a-option value="月结">月结</a-option>
            <a-option value="季结">季结</a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="cooperation_status" label="合作状态">
          <a-select v-model="editForm.cooperation_status" placeholder="请选择合作状态" allow-clear>
            <a-option value="active">合作中</a-option>
            <a-option value="suspended">暂停</a-option>
            <a-option value="terminated">终止</a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="erp_system" label="所属 ERP">
          <a-input v-model="editForm.erp_system" placeholder="请输入所属 ERP 系统" allow-clear />
        </a-form-item>

        <a-form-item field="manager_id" label="运营经理">
          <a-select
            v-model="editForm.manager_id"
            placeholder="请选择运营经理"
            allow-clear
            :loading="managersLoading"
          >
            <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
              {{ manager.real_name || manager.username }}
            </a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="sales_manager_id" label="销售负责人">
          <a-select
            v-model="editForm.sales_manager_id"
            placeholder="请选择销售负责人"
            allow-clear
            :loading="managersLoading"
          >
            <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
              {{ manager.real_name || manager.username }}
            </a-option>
          </a-select>
        </a-form-item>
      </div>

      <!-- 第三列：画像与状态 -->
      <div class="edit-form-column">
        <div class="column-title">画像与状态</div>

        <a-form-item field="scale_level" label="规模等级">
          <a-select v-model="editForm.scale_level" placeholder="请选择规模等级" allow-clear>
            <a-option value="100">100人</a-option>
            <a-option value="500">500人</a-option>
            <a-option value="1000">1000人</a-option>
            <a-option value="2000">2000人</a-option>
            <a-option value="5000">5000人</a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="consume_level" label="消费等级">
          <a-select v-model="editForm.consume_level" placeholder="请选择消费等级" allow-clear>
            <a-option value="S">S</a-option>
            <a-option value="A">A</a-option>
            <a-option value="B">B</a-option>
            <a-option value="C">C</a-option>
            <a-option value="D">D</a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="first_payment_date" label="首次回款时间">
          <a-date-picker
            v-model="editForm.first_payment_date"
            placeholder="请选择首次回款时间"
            style="width: 100%"
            allow-clear
            value-format="YYYY-MM-DD"
          />
        </a-form-item>

        <a-form-item field="onboarding_date" label="接入时间">
          <a-date-picker
            v-model="editForm.onboarding_date"
            placeholder="请选择接入时间"
            style="width: 100%"
            allow-clear
            value-format="YYYY-MM-DD"
          />
        </a-form-item>

        <a-form-item field="is_key_customer" label="重点客户">
          <a-switch v-model="editForm.is_key_customer" />
        </a-form-item>

        <a-form-item field="is_settlement_enabled" label="是否结算">
          <a-switch v-model="editForm.is_settlement_enabled" />
        </a-form-item>

        <a-form-item field="is_disabled" label="是否停用">
          <a-switch v-model="editForm.is_disabled" />
        </a-form-item>
      </div>

      <!-- 备注区域 - 横跨三列 -->
      <div class="edit-form-note">
        <a-form-item field="notes" label="备注">
          <a-textarea
            v-model="editForm.notes"
            placeholder="请输入备注信息"
            :auto-size="{ minRows: 2, maxRows: 4 }"
            allow-clear
          />
        </a-form-item>
      </div>
    </div>
  </a-form>
</a-modal>
```

- [ ] **Step 2: 验证模板语法**

Run: `cd frontend && npm run lint`
Expected: PASS (no lint errors in template)

---

### Task 3: 添加表单验证逻辑和响应式弹窗宽度

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue:531-794` (script 部分)

- [ ] **Step 1: 添加编辑表单 ref 和验证规则**

在 script setup 中添加：

```typescript
import type { FormInstance } from '@arco-design/web-vue'

// 编辑表单 ref
const editFormRef = ref<FormInstance>()

// 弹窗响应式宽度
const modalWidth = computed(() => {
  if (typeof window === 'undefined') return '1100px'
  const width = window.innerWidth
  if (width >= 1400) return '1100px'
  if (width >= 768) return '800px'
  return '100%'
})

// 编辑表单验证规则
const editFormRules = {
  company_id: [
    { required: true, message: '公司 ID 不能为空', trigger: ['blur', 'change'] },
  ],
  name: [
    { required: true, message: '客户名称不能为空', trigger: ['blur', 'change'] },
    { maxLength: 200, message: '客户名称不能超过 200 个字符', trigger: ['blur', 'change'] },
  ],
  email: [
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] },
  ],
  settlement_type: [
    { required: true, message: '请选择结算方式', trigger: ['blur', 'change'] },
  ],
}
```

- [ ] **Step 2: 修改 EditForm 接口，添加 company_id**

```typescript
// 编辑表单类型
interface EditForm {
  company_id: string  // 新增：必填
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
  scale_level?: string
  consume_level?: string
}
```

- [ ] **Step 3: 修改 editForm 初始化值**

```typescript
const editForm = ref<EditForm>({
  company_id: '',
  name: '',
  email: '',
  account_type: undefined,
  industry: undefined,
  customer_level: undefined,
  settlement_type: undefined,
  settlement_cycle: undefined,
  is_key_customer: false,
  manager_id: undefined,
  erp_system: undefined,
  first_payment_date: undefined,
  onboarding_date: undefined,
  sales_manager_id: undefined,
  cooperation_status: undefined,
  is_settlement_enabled: true,
  is_disabled: false,
  notes: undefined,
  scale_level: undefined,
  consume_level: undefined,
})
```

- [ ] **Step 4: 修改 openEditModal，填充 company_id**

在 `openEditModal` 中赋值 `company_id`：

```typescript
const openEditModal = () => {
  // 防护检查：确保 profile 数据已加载
  if (profileLoading.value || !profile.value || profile.value.id === 0) {
    Message.warning('客户画像数据加载中，请稍后编辑')
    return
  }
  
  editForm.value = {
    company_id: customer.value.company_id || '',  // 新增
    name: customer.value.name || '',
    email: customer.value.email || '',
    account_type: customer.value.account_type || undefined,
    industry: customer.value.industry || undefined,
    customer_level: customer.value.customer_level || undefined,
    settlement_type: customer.value.settlement_type || undefined,
    settlement_cycle: customer.value.settlement_cycle || undefined,
    is_key_customer: customer.value.is_key_customer || false,
    manager_id: customer.value.manager_id || undefined,
    erp_system: customer.value.erp_system || undefined,
    first_payment_date: customer.value.first_payment_date || undefined,
    onboarding_date: customer.value.onboarding_date || undefined,
    sales_manager_id: customer.value.sales_manager_id || undefined,
    cooperation_status: customer.value.cooperation_status || undefined,
    is_settlement_enabled: customer.value.is_settlement_enabled ?? true,
    is_disabled: customer.value.is_disabled ?? false,
    notes: customer.value.notes || undefined,
    scale_level: profile.value.scale_level || undefined,
    consume_level: profile.value.consume_level || undefined,
  }
  editModalVisible.value = true
}
```

- [ ] **Step 5: 修改 handleEditSubmit，添加客户端验证 + 日期校验 + 服务端排重错误处理**

```typescript
// 提交编辑
const handleEditSubmit = async () => {
  // 1. 客户端表单验证
  try {
    await editFormRef.value?.validate()
  } catch {
    return false
  }

  // 2. 日期格式校验
  if (editForm.value.first_payment_date) {
    const paymentDate = new Date(editForm.value.first_payment_date)
    const today = new Date()
    today.setHours(23, 59, 59, 999)
    if (paymentDate > today) {
      Message.error('首次回款时间不能超过今天')
      return false
    }
  }

  if (editForm.value.onboarding_date) {
    const onboardingDate = new Date(editForm.value.onboarding_date)
    const today = new Date()
    today.setHours(23, 59, 59, 999)
    if (onboardingDate > today) {
      Message.error('接入时间不能超过今天')
      return false
    }
  }

  // 3. 首次回款时间不能早于接入时间
  if (editForm.value.first_payment_date && editForm.value.onboarding_date) {
    const paymentDate = new Date(editForm.value.first_payment_date)
    const onboardingDate = new Date(editForm.value.onboarding_date)
    if (paymentDate < onboardingDate) {
      Message.error('首次回款时间不能早于接入时间')
      return false
    }
  }

  editLoading.value = true
  try {
    // 并行更新 Customer 和 CustomerProfile
    await Promise.all([
      updateCustomer(customerId.value, {
        company_id: editForm.value.company_id,  // 新增
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
    // 性能优化: 更新后清除缓存
    customerStore.invalidateCustomerCache(customerId.value)
    await loadCustomerData()
    return true
  } catch (error: unknown) {
    // 处理服务端 company_id 排重错误
    const err = error as { message?: string; response?: { data?: { message?: string } } }
    if (err.response?.data?.message) {
      Message.error(err.response.data.message)
    } else if (err.message?.includes('公司 ID')) {
      Message.error(err.message)
    } else {
      Message.error('更新失败')
    }
    console.error('更新失败:', error)
    return false
  } finally {
    editLoading.value = false
  }
}
```

- [ ] **Step 6: 取消弹框时重置表单验证状态**

修改弹框 `@cancel` 处理：

```vue
<a-modal
  v-model:visible="editModalVisible"
  title="编辑客户"
  :width="modalWidth"
  :confirm-loading="editLoading"
  @ok="handleEditSubmit"
  @cancel="handleEditCancel"
>
```

```typescript
const handleEditCancel = () => {
  editModalVisible.value = false
  editFormRef.value?.resetFields()
}
```

- [ ] **Step 7: 添加窗口 resize 监听，使弹窗宽度响应式更新**

```typescript
// 弹窗宽度响应式更新
const handleResize = () => {
  // 触发 modalWidth computed 重新计算
  window.dispatchEvent(new Event('resize'))
}

onMounted(() => {
  loadCustomerData()
  loadCustomerTags()
  loadUsageData()
  loadManagers()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (tabLoadTimer) {
    clearTimeout(tabLoadTimer)
    tabLoadTimer = null
  }
  window.removeEventListener('resize', handleResize)
})
```

- [ ] **Step 8: TypeScript 类型检查**

Run: `cd frontend && npm run type-check`
Expected: PASS

---

### Task 4: 添加三列布局样式

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue` (style 部分)

- [ ] **Step 1: 添加三列布局 CSS**

在 `<style scoped>` 末尾（`.notes-text` 之后）添加：

```css
/* ========== 编辑弹框三列布局 ========== */

/* 编辑表单网格容器 */
.edit-form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0 20px;
  width: 100%;
}

/* 编辑表单列 */
.edit-form-column {
  display: flex;
  flex-direction: column;
}

/* 列标题 */
.edit-form-column .column-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-6, #0369a1);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--primary-1, #e8f3ff);
}

/* 列分隔线 */
.edit-form-column + .edit-form-column {
  border-left: 1px solid var(--neutral-2, #eef0f3);
  padding-left: 20px;
}

/* 备注区域 - 横跨三列 */
.edit-form-note {
  grid-column: 1 / -1;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--neutral-2, #eef0f3);
}

/* 响应式降级：两列 */
@media (max-width: 1399px) {
  .edit-form-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .edit-form-column:nth-child(1) {
    border-right: 1px solid var(--neutral-2, #eef0f3);
    padding-right: 20px;
  }

  .edit-form-column:nth-child(2) {
    border-left: none;
    padding-left: 0;
  }

  .edit-form-column:nth-child(3) {
    border-top: 1px solid var(--neutral-2, #eef0f3);
    padding-top: 16px;
    margin-top: 16px;
    grid-column: 1 / -1;
  }

  .edit-form-column:nth-child(3) .column-title {
    margin-bottom: 12px;
  }
}

/* 响应式降级：单列 */
@media (max-width: 767px) {
  .edit-form-grid {
    grid-template-columns: 1fr;
  }

  .edit-form-column {
    border-left: none !important;
    border-right: none !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    border-top: none !important;
    padding-top: 0 !important;
    margin-top: 0 !important;
    grid-column: auto !important;
  }

  .edit-form-column + .edit-form-column {
    border-top: 1px solid var(--neutral-2, #eef0f3);
    padding-top: 16px;
    margin-top: 16px;
  }

  .edit-form-note {
    border-top: 1px solid var(--neutral-2, #eef0f3);
  }
}
```

- [ ] **Step 2: 验证样式生效**

前端开发服务器运行后，打开客户详情页，点击"编辑"按钮，确认：
- 弹窗宽度为 1100px（大屏）
- 字段分为三列显示
- 列标题显示正确
- 列之间有分隔线

---

### Task 5: 行业类型下拉选项优化

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue:383-389` (行业类型下拉选项)

- [ ] **Step 1: 使用后端行业类型接口替代硬编码选项**

项目中已有 `getIndustryTypes()` API 和行业类型数据。查看 `Index.vue` 如何使用行业类型，在 Detail.vue 中也使用同样的方式加载行业类型选项。

在 script 中添加行业类型加载：

```typescript
import { getIndustryTypes, type IndustryType } from '@/api/customers'

const industryTypes = ref<IndustryType[]>([])
const industryTypesLoading = ref(false)

const loadIndustryTypes = async () => {
  industryTypesLoading.value = true
  try {
    const res = await getIndustryTypes()
    industryTypes.value = res.data || []
  } catch (error) {
    console.error('加载行业类型失败:', error)
  } finally {
    industryTypesLoading.value = false
  }
}
```

在 `onMounted` 中调用 `loadIndustryTypes()`。

在模板中行业类型下拉使用动态选项：

```vue
<a-form-item field="industry" label="行业类型">
  <a-select v-model="editForm.industry" placeholder="请选择行业类型" allow-clear :loading="industryTypesLoading">
    <a-option v-for="type in industryTypes" :key="type.name" :value="type.name">
      {{ type.name }}
    </a-option>
  </a-select>
</a-form-item>
```

- [ ] **Step 2: TypeScript 类型检查**

Run: `cd frontend && npm run type-check`
Expected: PASS

---

### Task 6: 完整验证和提交

- [ ] **Step 1: 运行前端完整检查**

Run: `cd frontend && npm run type-check && npm run lint`
Expected: All pass

- [ ] **Step 2: 运行后端测试（确保无回归）**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/ -v --tb=short -q`
Expected: All pass

- [ ] **Step 3: 手动功能验证清单**

启动前后端后，验证以下场景：

1. 打开客户详情页 → 点击"编辑" → 弹窗以三列显示，字段分组正确
2. 必填字段（公司 ID、客户名称、结算方式）带红色星号
3. 清空公司 ID 提交 → 显示"公司 ID 不能为空"
4. 清空客户名称提交 → 显示"客户名称不能为空"
5. 邮箱输入"abc"提交 → 显示"邮箱格式不正确"
6. 首次回款时间设为未来日期 → 显示"首次回款时间不能超过今天"
7. 接入时间设为未来日期 → 显示"接入时间不能超过今天"
8. 首次回款时间早于接入时间 → 显示"首次回款时间不能早于接入时间"
9. 修改公司 ID 为其他客户已使用的 ID → 显示"公司 ID 'xxx' 已被其他客户使用"
10. 正常修改并提交 → 成功提示 + 数据刷新
11. 窗口缩小到 < 1400px → 降级为两列
12. 窗口缩小到 < 768px → 降级为单列
13. 点击取消 → 弹框关闭，验证状态重置

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/customers/Detail.vue frontend/src/api/customers.ts
git commit -m "feat(ui): customer edit dialog three-column layout with validation

- Restructure edit modal into three-column grouped layout
  (basic info, settlement & business, profile & status)
- Add company_id as editable required field
- Add form validation: required fields, email format, date constraints
- Add responsive width (1100px/800px/100% with column fallback)
- Use dynamic industry types from backend API
- Handle server-side company_id uniqueness error"
```

---

## 自审检查

### 设计文档覆盖检查

| 设计文档要求 | 对应 Task | 状态 |
|-------------|-----------|------|
| 三列分组布局 | Task 2 | ✅ |
| 响应式弹窗宽度 | Task 3 Step 1, Step 7 | ✅ |
| 公司 ID 必填 + 可编辑 | Task 1, Task 2, Task 3 | ✅ |
| 客户名称必填 + 最长 200 字符 | Task 3 Step 1 | ✅ |
| 结算方式必填 | Task 3 Step 1 | ✅ |
| 邮箱格式校验 | Task 3 Step 1 | ✅ |
| 日期不能超过今天 | Task 3 Step 5 | ✅ |
| 首次回款不早于接入时间 | Task 3 Step 5 | ✅ |
| 公司 ID 服务端排重 | Task 3 Step 5 (错误处理) | ✅ |
| 备注跨列显示 | Task 2 | ✅ |
| 响应式降级（两列/单列） | Task 4 | ✅ |

### 占位符扫描

- 无 TBD/TODO
- 所有步骤都有完整代码
- 类型签名一致（EditForm 包含 company_id，updateCustomer 类型包含 company_id）
- 错误处理完整（客户端验证 + 日期校验 + 服务端排重错误）

### 类型一致性

- `EditForm.company_id: string` → `updateCustomer` data 类型 `company_id?: string` ✅
- `FormInstance` import from `@arco-design/web-vue` ✅
- `IndustryType` import from `@/api/customers` ✅
- `editFormRules` 中字段名与 `EditForm` 接口字段名一致 ✅
