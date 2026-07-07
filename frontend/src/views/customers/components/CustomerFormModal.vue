<template>
    <!-- 新建/编辑客户对话框 -->
    <a-modal
      v-model:visible="isVisible"
      :title="isEditMode ? '编辑客户' : '新建客户'"
      :confirm-loading="customerModalLoading"
      width="600px"
      @before-ok="handleCustomerSubmit"
      @cancel="handleCustomerModalCancel"
    >
      <a-form
        ref="customerFormRef"
        :model="customerForm"
        :rules="customerFormRules"
        layout="vertical"
        validate-trigger="['blur', 'change']"
      >
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="company_id" label="公司 ID" required>
              <a-input v-model="customerForm.company_id" placeholder="请输入公司 ID" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="name" label="客户名称" required>
              <a-input v-model="customerForm.name" placeholder="请输入客户名称" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item field="email" label="邮箱">
          <a-input v-model="customerForm.email" placeholder="请输入邮箱" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="account_type" label="账号类型">
              <a-select
                v-model="customerForm.account_type"
                placeholder="请选择账号类型"
                allow-clear
              >
                <a-option value="正式账号">正式账号</a-option>
                <a-option value="测试账号">测试账号</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="industry_type_id" label="行业类型">
              <a-select
                v-model="customerForm.industry_type_id"
                placeholder="请选择行业类型"
                allow-clear
              >
                <a-option v-for="item in industryTypes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="settlement_type" label="结算方式">
              <a-select
                v-model="customerForm.settlement_type"
                placeholder="请选择结算方式"
                allow-clear
              >
                <a-option value="prepaid">预付费</a-option>
                <a-option value="postpaid">后付费</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="is_real_estate" label="是否房产客户">
              <a-select v-model="customerForm.is_real_estate" placeholder="请选择" allow-clear>
                <a-option :value="true">是</a-option>
                <a-option :value="false">否</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="settlement_cycle" label="结算周期">
              <a-select
                v-model="customerForm.settlement_cycle"
                placeholder="请选择结算周期"
                allow-clear
              >
                <a-option value="daily">日结</a-option>
                <a-option value="weekly">周结</a-option>
                <a-option value="monthly">月结</a-option>
                <a-option value="quarterly">季结</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="is_key_customer" label="重点客户">
              <a-switch v-model="customerForm.is_key_customer" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item field="manager_id" label="运营经理">
          <a-select
            v-model="customerForm.manager_id"
            placeholder="请选择运营经理"
            allow-clear
            :loading="managersLoading"
          >
            <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
              {{ manager.real_name || manager.username }}
            </a-option>
          </a-select>
        </a-form-item>

        <a-form-item field="sales_manager_id" label="商务经理">
          <a-select
            v-model="customerForm.sales_manager_id"
            placeholder="请选择商务经理"
            allow-clear
            :loading="managersLoading"
          >
            <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
              {{ manager.real_name || manager.username }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import type { IndustryType, Customer } from '@/types'
import { handleError } from '@/utils/errorHandler'
import { createCustomer, updateCustomer } from '@/api/customers'

interface CustomerForm {
  company_id: number | undefined
  name: string
  email: string
  account_type: string | null | undefined
  industry_type_id: number | null
  settlement_type: string | null | undefined
  settlement_cycle: string | null | undefined
  is_key_customer: boolean
  is_real_estate: boolean | null
  manager_id: number | null
  sales_manager_id: number | null
}

const props = defineProps<{
  visible: boolean
  isEditMode: boolean
  customerRecord: Customer | null
  industryTypes: IndustryType[]
  managers: Array<Record<string, unknown>>
  managersLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'saved'): void
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const customerModalLoading = ref(false)
const customerFormRef = ref<FormInstance>()

const customerForm = reactive<CustomerForm>({
  company_id: undefined,
  name: '',
  email: '',
  account_type: undefined,
  industry_type_id: null,
  settlement_type: undefined,
  settlement_cycle: undefined,
  is_key_customer: false,
  is_real_estate: null,
  manager_id: null,
  sales_manager_id: null,
})

const customerFormRules = {
  company_id: [{ required: true, message: '请输入公司 ID', trigger: ['blur', 'change'] as const }],
  name: [{ required: true, message: '请输入客户名称', trigger: ['blur', 'change'] as const }],
  email: [{ type: 'email' as const, message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] as const }],
}

// Watch for modal opening to initialize form
const initFormForCreate = () => {
  customerForm.company_id = undefined
  customerForm.name = ''
  customerForm.email = ''
  customerForm.account_type = undefined
  customerForm.industry_type_id = null
  customerForm.settlement_type = undefined
  customerForm.settlement_cycle = undefined
  customerForm.is_key_customer = false
  customerForm.is_real_estate = null
  customerForm.manager_id = null
  customerForm.sales_manager_id = null
}

const initFormForEdit = (record: Customer) => {
  customerForm.company_id = record.company_id
  customerForm.name = record.name
  customerForm.email = record.email || ''
  customerForm.account_type = record.account_type
  customerForm.industry_type_id = record.industry_type_id ?? null
  customerForm.settlement_type = record.settlement_type
  customerForm.settlement_cycle = record.settlement_cycle
  customerForm.is_key_customer = record.is_key_customer
  customerForm.is_real_estate = record.is_real_estate ?? null
  customerForm.manager_id = record.manager_id || null
  customerForm.sales_manager_id = record.sales_manager_id || null
}

// Auto-initialize form when modal opens
watch(() => props.visible, (val) => {
  if (val && props.isEditMode && props.customerRecord) {
    initFormForEdit(props.customerRecord)
  } else if (val && !props.isEditMode) {
    initFormForCreate()
  }
})

const handleCustomerModalCancel = () => {
  emit('update:visible', false)
  customerFormRef.value?.resetFields()
}

const handleCustomerSubmit = async () => {
  try {
    await customerFormRef.value?.validate()
  } catch {
    return false
  }

  customerModalLoading.value = true
  try {
    const data = {
      company_id: customerForm.company_id ?? 0,
      name: customerForm.name,
      email: customerForm.email || undefined,
      account_type: customerForm.account_type || undefined,
      industry_type_id: customerForm.industry_type_id,
      settlement_type: customerForm.settlement_type || undefined,
      settlement_cycle: customerForm.settlement_cycle || undefined,
      is_key_customer: customerForm.is_key_customer,
      is_real_estate: customerForm.is_real_estate ?? undefined,
      manager_id: customerForm.manager_id || undefined,
      sales_manager_id: customerForm.sales_manager_id || undefined,
    }

    if (props.isEditMode && props.customerRecord?.id) {
      await updateCustomer(props.customerRecord.id, data)
      Message.success('更新成功')
    } else {
      await createCustomer(data)
      Message.success('创建成功')
    }
    emit('saved')
    emit('update:visible', false)
    return true
  } catch (error: unknown) {
    handleError(error, '操作失败')
    return false
  } finally {
    customerModalLoading.value = false
  }
}

// Expose for parent
defineExpose({
  initFormForCreate,
  initFormForEdit,
})
</script>
