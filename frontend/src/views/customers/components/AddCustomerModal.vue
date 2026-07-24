<template>
  <a-modal
    v-model:visible="localVisible"
    title="新增客户"
    width="640px"
    :confirm-loading="loading"
    :mask-closable="false"
    @ok="handleConfirm"
    @cancel="handleCancel"
    @close="reset"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-row :gutter="16">
        <!-- 客户ID（必填） -->
        <a-col :span="12">
          <a-form-item field="company_id" label="客户ID">
            <a-input-number
              v-model="form.company_id"
              placeholder="请输入客户ID"
              :min="1"
              style="width: 100%"
              hide-button
            />
          </a-form-item>
        </a-col>
        <!-- 客户名称（必填） -->
        <a-col :span="12">
          <a-form-item field="name" label="客户名称">
            <a-input v-model="form.name" placeholder="请输入客户名称" allow-clear />
          </a-form-item>
        </a-col>
        <!-- 邮箱 -->
        <a-col :span="12">
          <a-form-item field="email" label="邮箱">
            <a-input v-model="form.email" placeholder="请输入邮箱" allow-clear />
          </a-form-item>
        </a-col>
        <!-- 账号类型 -->
        <a-col :span="12">
          <a-form-item field="account_type" label="账号类型">
            <a-select v-model="form.account_type" placeholder="请选择" allow-clear>
              <a-option value="正式账号">正式账号</a-option>
              <a-option value="客户测试账号">客户测试账号</a-option>
              <a-option value="内部账号">内部账号</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <!-- 行业类型 -->
        <a-col :span="12">
          <a-form-item field="industry_type_id" label="行业类型">
            <a-select v-model="form.industry_type_id" placeholder="请选择行业类型" allow-clear>
              <a-option v-for="it in industryTypes" :key="it.id" :value="it.id">
                {{ it.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <!-- 结算方式 -->
        <a-col :span="12">
          <a-form-item field="settlement_type" label="结算方式">
            <a-select v-model="form.settlement_type" placeholder="请选择" allow-clear>
              <a-option value="prepaid">预付费</a-option>
              <a-option value="postpaid">后付费</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <!-- 是否房产客户 -->
        <a-col :span="12">
          <a-form-item field="is_real_estate" label="是否房产客户">
            <a-switch v-model="form.is_real_estate" />
          </a-form-item>
        </a-col>
        <!-- 结算周期 -->
        <a-col :span="12">
          <a-form-item field="settlement_cycle" label="结算周期">
            <a-select v-model="form.settlement_cycle" placeholder="请选择" allow-clear>
              <a-option value="monthly">月结</a-option>
              <a-option value="quarterly">季结</a-option>
              <a-option value="yearly">年结</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <!-- 是否重点客户（开关按钮样式） -->
        <a-col :span="12">
          <a-form-item field="is_key_customer" label="是否重点客户">
            <a-switch v-model="form.is_key_customer" />
          </a-form-item>
        </a-col>
        <!-- 运营经理 -->
        <a-col :span="12">
          <a-form-item field="manager_id" label="运营经理">
            <a-select
              v-model="form.manager_id"
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
        <!-- 销售经理 -->
        <a-col :span="12">
          <a-form-item field="sales_manager_id" label="销售经理">
            <a-select
              v-model="form.sales_manager_id"
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
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FieldRule, FormInstance } from '@arco-design/web-vue'
import type { IndustryType } from '@/types'
import { createCustomer } from '@/api/customers'
import { handleError } from '@/utils/errorHandler'

const props = defineProps<{
  visible: boolean
  industryTypes: IndustryType[]
  managers: Array<{ id: number; real_name: string | null }>
  managersLoading?: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  saved: []
}>()

const localVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const formRef = ref<FormInstance>()
const loading = ref(false)

interface CreateForm {
  company_id: number | undefined
  name: string
  email: string
  account_type: string
  industry_type_id: number | undefined
  settlement_type: string
  is_real_estate: boolean
  settlement_cycle: string
  is_key_customer: boolean
  manager_id: number | undefined
  sales_manager_id: number | undefined
}

const createDefaultForm = (): CreateForm => ({
  company_id: undefined,
  name: '',
  email: '',
  account_type: '',
  industry_type_id: undefined,
  settlement_type: '',
  is_real_estate: false,
  settlement_cycle: '',
  is_key_customer: false,
  manager_id: undefined,
  sales_manager_id: undefined,
})

const form = reactive<CreateForm>(createDefaultForm())

const rules: Record<string, FieldRule[]> = {
  company_id: [{ required: true, message: '请输入客户ID' }],
  name: [{ required: true, message: '请输入客户名称' }],
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

// 弹框打开时重置表单
watch(
  () => props.visible,
  (val) => {
    if (val) {
      Object.assign(form, createDefaultForm())
      formRef.value?.resetFields()
    }
  }
)

const handleConfirm = async () => {
  const valid = await formRef.value?.validate()
  if (valid) return // 有校验错误

  loading.value = true
  try {
    // 构建提交数据，过滤空值
    const payload: Record<string, unknown> = {
      company_id: form.company_id,
      name: form.name,
    }
    if (form.email) payload.email = form.email
    if (form.account_type) payload.account_type = form.account_type
    if (form.industry_type_id) payload.industry_type_id = form.industry_type_id
    if (form.settlement_type) payload.settlement_type = form.settlement_type
    payload.is_real_estate = form.is_real_estate
    if (form.settlement_cycle) payload.settlement_cycle = form.settlement_cycle
    payload.is_key_customer = form.is_key_customer
    if (form.manager_id) payload.manager_id = form.manager_id
    if (form.sales_manager_id) payload.sales_manager_id = form.sales_manager_id

    await createCustomer(payload as Parameters<typeof createCustomer>[0])
    Message.success('创建成功')
    localVisible.value = false
    emit('saved')
  } catch (error: unknown) {
    handleError(error, '创建客户失败')
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  localVisible.value = false
}

const reset = () => {
  Object.assign(form, createDefaultForm())
  formRef.value?.resetFields()
}
</script>
