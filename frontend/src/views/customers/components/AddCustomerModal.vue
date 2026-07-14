<template>
  <a-modal
    v-model:visible="localVisible"
    title="新增客户"
    width="600px"
    :confirm-loading="loading"
    @confirm="handleConfirm"
    @cancel="emit('update:visible', false)"
  >
    <a-form :model="form" layout="vertical">
      <a-row :gutter="16">
        <a-col :span="24">
          <a-form-item label="客户名称" required>
            <a-input v-model="form.name" placeholder="请输入客户名称" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="行业">
            <a-select
              v-model="form.industry"
              placeholder="请选择行业"
              allow-clear
            >
              <a-option v-for="it in industryTypes" :key="it.name" :value="it.name">
                {{ it.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="规模等级">
            <a-select v-model="form.scale_level" placeholder="请选择" allow-clear>
              <a-option value="S">S（超大型）</a-option>
              <a-option value="A">A（大型）</a-option>
              <a-option value="B">B（中型）</a-option>
              <a-option value="C">C（小型）</a-option>
              <a-option value="D">D（微型）</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="运营经理">
            <a-select
              v-model="form.manager_id"
              placeholder="请选择"
              allow-clear
            >
              <a-option v-for="m in managers" :key="m.id" :value="m.id">
                {{ m.real_name || `#${m.id}` }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="销售经理">
            <a-select
              v-model="form.sales_manager_id"
              placeholder="请选择"
              allow-clear
            >
              <a-option v-for="m in managers" :key="m.id" :value="m.id">
                {{ m.real_name || `#${m.id}` }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="结算方式">
            <a-select v-model="form.settlement_type" placeholder="请选择" allow-clear>
              <a-option value="prepaid">预付费</a-option>
              <a-option value="postpaid">后付费</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="初始余额">
            <a-input-number
              v-model="form.initial_balance"
              mode="button"
              :min="0"
              :precision="2"
              placeholder="0.00"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import type { IndustryType } from '@/types'
import type { CustomerCreate } from '@/api/customers'

const props = defineProps<{
  visible: boolean
  loading: boolean
  industryTypes: IndustryType[]
  managers: Array<{ id: number; real_name: string | null }>
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: CustomerCreate]
}>()

const localVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const form = reactive<CustomerCreate>({
  name: '',
  industry: '',
  scale_level: '',
  consume_level: '',
  manager_id: null,
  sales_manager_id: null,
  settlement_type: '',
  initial_balance: 0,
  is_key_customer: false,
  contact_person: '',
  contact_phone: '',
  contact_email: '',
  account_type: '',
})

const handleConfirm = () => {
  if (!form.name.trim()) return
  emit('submit', { ...form })
}

const reset = () => {
  form.name = ''
  form.industry = ''
  form.scale_level = ''
  form.consume_level = ''
  form.manager_id = null
  form.sales_manager_id = null
  form.settlement_type = ''
  form.initial_balance = 0
  form.is_key_customer = false
  form.contact_person = ''
  form.contact_phone = ''
  form.contact_email = ''
  form.account_type = ''
}

defineExpose({ reset })
</script>
