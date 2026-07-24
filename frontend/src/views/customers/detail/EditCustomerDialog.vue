<template>
  <a-modal
    :visible="visible"
    title="编辑客户"
    :width="modalWidth"
    :confirm-loading="submitLoading"
    :mask-closable="false"
    @ok="handleSubmit"
    @cancel="handleCancel"
    @close="handleCancel"
  >
    <a-spin :loading="fetchLoading" tip="加载客户数据中...">
      <a-form
        ref="editFormRef"
        :model="editForm"
        :rules="editFormRules"
        layout="vertical"
        validate-trigger="['blur', 'change']"
      >
        <a-row :gutter="24">
          <!-- ===== 列一：基础信息 ===== -->
          <a-col :xs="24" :sm="12" :md="8">
            <div class="section-title">基础信息</div>
            <a-form-item field="name" label="客户名称" required>
              <a-input v-model="editForm.name" placeholder="请输入客户名称" />
            </a-form-item>
            <a-form-item field="company_id" label="公司ID" required>
              <a-input-number
                v-model="editForm.company_id"
                placeholder="请输入公司ID"
                :min="1"
                style="width: 100%"
                hide-button
              />
            </a-form-item>
            <a-form-item field="email" label="邮箱">
              <a-input v-model="editForm.email" placeholder="请输入邮箱" allow-clear />
            </a-form-item>
            <a-form-item field="account_type" label="账号类型">
              <a-select v-model="editForm.account_type" placeholder="请选择" allow-clear>
                <a-option value="正式账号">正式账号</a-option>
                <a-option value="客户测试账号">客户测试账号</a-option>
                <a-option value="内部账号">内部账号</a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="industry_type_id" label="行业类型">
              <a-select v-model="editForm.industry_type_id" placeholder="请选择" allow-clear>
                <a-option v-for="type in industryTypes" :key="type.id" :value="type.id">
                  {{ type.name }}
                </a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="is_real_estate" label="是否房产客户">
              <a-switch v-model="editForm.is_real_estate" />
            </a-form-item>
            <a-form-item field="sales_manager_id" label="销售经理">
              <a-select
                v-model="editForm.sales_manager_id"
                placeholder="请选择"
                allow-clear
                :loading="managersLoading"
              >
                <a-option v-for="m in managers" :key="m.id" :value="m.id">
                  {{ m.real_name || `#${m.id}` }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>

          <!-- ===== 列二：结算与业务 ===== -->
          <a-col :xs="24" :sm="12" :md="8">
            <div class="section-title">结算与业务</div>
            <a-form-item field="settlement_type" label="结算方式" required>
              <a-select v-model="editForm.settlement_type" placeholder="请选择">
                <a-option value="prepaid">预付费</a-option>
                <a-option value="postpaid">后付费</a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="settlement_cycle" label="结算周期">
              <a-select v-model="editForm.settlement_cycle" placeholder="请选择" allow-clear>
                <a-option value="daily">日结</a-option>
                <a-option value="weekly">周结</a-option>
                <a-option value="monthly">月结</a-option>
                <a-option value="quarterly">季结</a-option>
                <a-option value="yearly">年结</a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="price_policy" label="价格策略">
              <a-select v-model="editForm.price_policy" placeholder="请选择" allow-clear>
                <a-option value="pricing">定价</a-option>
                <a-option value="tiered">阶梯</a-option>
                <a-option value="yearly">包年</a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="erp_system" label="ERP 系统">
              <a-select v-model="editForm.erp_system" placeholder="请选择" allow-clear>
                <a-option value="SAP">SAP</a-option>
                <a-option value="Oracle">Oracle</a-option>
                <a-option value="用友">用友</a-option>
                <a-option value="金蝶">金蝶</a-option>
                <a-option value="自研">自研</a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="cooperation_status" label="合作状态">
              <a-select v-model="editForm.cooperation_status" placeholder="请选择" allow-clear>
                <a-option value="active">合作中</a-option>
                <a-option value="suspended">暂停</a-option>
                <a-option value="terminated">终止</a-option>
                <a-option value="noused">近一年未使用</a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="is_settlement_enabled" label="启用结算">
              <a-switch v-model="editForm.is_settlement_enabled" />
            </a-form-item>
            <a-form-item field="manager_id" label="运营经理">
              <a-select
                v-model="editForm.manager_id"
                placeholder="请选择"
                allow-clear
                :loading="managersLoading"
              >
                <a-option v-for="m in managers" :key="m.id" :value="m.id">
                  {{ m.real_name || `#${m.id}` }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>

          <!-- ===== 列三：等级与消费 ===== -->
          <a-col :xs="24" :sm="12" :md="8">
            <div class="section-title">等级与消费</div>
            <a-form-item field="scale_level" label="规模等级">
              <a-select v-model="editForm.scale_level" placeholder="请选择" allow-clear>
                <a-option value="S">S（超大型）</a-option>
                <a-option value="A">A（大型）</a-option>
                <a-option value="B">B（中型）</a-option>
                <a-option value="C">C（小型）</a-option>
                <a-option value="D">D（微型）</a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="consume_level" label="消费等级">
              <a-select v-model="editForm.consume_level" placeholder="请选择" allow-clear>
                <a-option value="C1">C1</a-option>
                <a-option value="C2">C2</a-option>
                <a-option value="C3">C3</a-option>
                <a-option value="C4">C4</a-option>
                <a-option value="C5">C5</a-option>
                <a-option value="C6">C6</a-option>
              </a-select>
            </a-form-item>
            <a-form-item field="is_key_customer" label="是否重点客户">
              <a-switch v-model="editForm.is_key_customer" />
            </a-form-item>
            <a-form-item field="first_payment_date" label="首次回款时间">
              <a-date-picker
                v-model="editForm.first_payment_date"
                placeholder="请选择"
                style="width: 100%"
                allow-clear
                value-format="YYYY-MM-DD"
              />
            </a-form-item>
            <a-form-item field="onboarding_date" label="接入时间">
              <a-date-picker
                v-model="editForm.onboarding_date"
                placeholder="请选择"
                style="width: 100%"
                allow-clear
                value-format="YYYY-MM-DD"
              />
            </a-form-item>
            <a-form-item field="is_disabled" label="是否停用">
              <a-switch v-model="editForm.is_disabled" />
            </a-form-item>
          </a-col>

          <!-- ===== 备注（横跨三列） ===== -->
          <a-col :span="24">
            <a-form-item field="notes" label="备注">
              <a-textarea
                v-model="editForm.notes"
                placeholder="请输入备注"
                :max-length="500"
                show-word-limit
                allow-clear
                :auto-size="{ minRows: 2, maxRows: 4 }"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FieldRule, FormInstance } from '@arco-design/web-vue'
import type { IndustryType } from '@/types'
import { getCustomer, updateCustomer, updateProfile, getIndustryTypes } from '@/api/customers'
import { getManagers } from '@/api/users'
import { handleError } from '@/utils/errorHandler'

const props = defineProps<{
  visible: boolean
  customerId: number | null
  industryTypes?: IndustryType[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  saved: []
}>()

const editFormRef = ref<FormInstance>()
const fetchLoading = ref(false)
const submitLoading = ref(false)

// 字典数据（如果外部未传则自行加载）
const managers = ref<Array<{ id: number; real_name: string | null; username?: string }>>([])
const managersLoading = ref(false)
const innerIndustryTypes = ref<IndustryType[]>([])
const industryTypes = computed(() => props.industryTypes || innerIndustryTypes.value)

const modalWidth = computed(() => {
  if (typeof window === 'undefined') return '960px'
  const w = window.innerWidth
  if (w < 768) return '95vw'
  if (w < 1024) return '90vw'
  return '960px'
})

interface EditForm {
  name: string
  company_id: number
  email: string
  account_type?: string
  industry_type_id: number | null
  price_policy?: string
  settlement_type?: string
  settlement_cycle?: string
  is_key_customer: boolean
  manager_id?: number
  erp_system?: string
  first_payment_date?: string
  onboarding_date?: string
  sales_manager_id?: number
  cooperation_status?: string
  is_settlement_enabled: boolean
  is_disabled: boolean
  notes?: string
  is_real_estate: boolean | null
  scale_level?: string
  consume_level?: string
}

const createDefaultForm = (): EditForm => ({
  name: '',
  company_id: 0,
  email: '',
  account_type: undefined,
  industry_type_id: null,
  price_policy: undefined,
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
  is_real_estate: null,
  scale_level: undefined,
  consume_level: undefined,
})

const editForm = reactive<EditForm>(createDefaultForm())

const editFormRules: Record<string, FieldRule[]> = {
  name: [{ required: true, message: '请输入客户名称' }],
  company_id: [{ required: true, message: '请输入公司 ID' }],
  settlement_type: [{ required: true, message: '请选择结算方式' }],
  email: [
    {
      validator: (value: string, callback: (error?: string) => void) => {
        if (value && !/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(value)) {
          callback('邮箱格式不正确')
        } else {
          callback()
        }
      },
    },
  ],
}

// 加载字典数据
const loadDictData = async () => {
  if (!props.industryTypes) {
    try {
      const res = await getIndustryTypes()
      innerIndustryTypes.value = res.data?.data || res.data || []
    } catch {
      // ignore
    }
  }
  if (managers.value.length === 0) {
    managersLoading.value = true
    try {
      const res = await getManagers()
      managers.value = res.data?.list || res.data || []
    } catch {
      // ignore
    } finally {
      managersLoading.value = false
    }
  }
}

// 获取客户详情并填充表单
const fetchAndInitForm = async () => {
  if (!props.customerId) return
  fetchLoading.value = true
  try {
    await loadDictData()
    const res = await getCustomer(props.customerId)
    const c = res.data?.data || res.data
    if (!c) return

    Object.assign(editForm, {
      name: c.name || '',
      company_id: Number(c.company_id) || 0,
      email: c.email || '',
      account_type: c.account_type || undefined,
      industry_type_id: c.profile?.industry_type_id ?? c.industry_type_id ?? null,
      price_policy: c.price_policy
        ? ({ 定价: 'pricing', 阶梯: 'tiered', 包年: 'yearly' } as Record<string, string>)[
            c.price_policy
          ] || c.price_policy
        : undefined,
      settlement_type: c.settlement_type || undefined,
      settlement_cycle: c.settlement_cycle || undefined,
      is_key_customer: c.is_key_customer || false,
      manager_id: c.manager_id || undefined,
      erp_system: c.erp_system || undefined,
      first_payment_date: c.first_payment_date || undefined,
      onboarding_date: c.onboarding_date || undefined,
      sales_manager_id: c.sales_manager_id || undefined,
      cooperation_status: c.cooperation_status || undefined,
      is_settlement_enabled: c.is_settlement_enabled ?? true,
      is_disabled: c.is_disabled ?? false,
      notes: c.notes || undefined,
      is_real_estate: c.is_real_estate ?? null,
      scale_level: c.profile?.scale_level || c.scale_level || undefined,
      consume_level: c.profile?.consume_level || c.consume_level || undefined,
    })
  } catch (error) {
    handleError(error, '加载客户数据失败')
  } finally {
    fetchLoading.value = false
  }
}

// 弹框打开时加载数据
watch(
  () => props.visible,
  (val) => {
    if (val && props.customerId) {
      Object.assign(editForm, createDefaultForm())
      editFormRef.value?.resetFields()
      fetchAndInitForm()
    }
  }
)

const handleSubmit = async () => {
  const valid = await editFormRef.value?.validate()
  if (valid) return

  submitLoading.value = true
  try {
    const form = { ...editForm }
    // 构建 basic 更新数据
    const basicData: Record<string, unknown> = {
      name: form.name,
      company_id: form.company_id,
      email: form.email || undefined,
      account_type: form.account_type || undefined,
      industry_type_id: form.industry_type_id,
      price_policy: form.price_policy || undefined,
      settlement_type: form.settlement_type,
      settlement_cycle: form.settlement_cycle || undefined,
      is_key_customer: form.is_key_customer,
      manager_id: form.manager_id || undefined,
      sales_manager_id: form.sales_manager_id || undefined,
      erp_system: form.erp_system || undefined,
      first_payment_date: form.first_payment_date || undefined,
      onboarding_date: form.onboarding_date || undefined,
      cooperation_status: form.cooperation_status || undefined,
      is_settlement_enabled: form.is_settlement_enabled,
      is_disabled: form.is_disabled,
      notes: form.notes || undefined,
      is_real_estate: form.is_real_estate,
    }

    // 构建 profile 更新数据
    const profileData: Record<string, unknown> = {
      scale_level: form.scale_level || undefined,
      consume_level: form.consume_level || undefined,
      industry_type_id: form.industry_type_id,
    }

    await Promise.all([
      updateCustomer(props.customerId!, basicData as Parameters<typeof updateCustomer>[1]),
      updateProfile(props.customerId!, profileData as Parameters<typeof updateProfile>[1]),
    ])

    Message.success('客户信息已更新')
    emit('update:visible', false)
    emit('saved')
  } catch (error: unknown) {
    handleError(error, '更新客户信息失败')
  } finally {
    submitLoading.value = false
  }
}

const handleCancel = () => {
  editFormRef.value?.resetFields()
  emit('update:visible', false)
}
</script>

<style scoped>
.section-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--primary, #2563eb);
  padding-bottom: 8px;
  margin-bottom: 16px;
  border-bottom: 2px solid var(--primary, #2563eb);
}
</style>
