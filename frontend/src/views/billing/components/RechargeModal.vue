<template>
  <a-modal
    v-model:visible="isVisible"
    title="客户充值"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="form" layout="vertical">
      <a-form-item field="customer_id" label="客户" required>
        <CustomerAutoComplete
          v-model="form.customer_id"
          :display-name="currentDisplayName"
          placeholder="请输入客户名称搜索"
          width="100%"
        />
      </a-form-item>
      <a-form-item field="real_amount" label="充值金额" required>
        <a-input-number
          v-model="form.real_amount"
          placeholder="请输入充值金额（负数表示扣减）"
          style="width: 100%"
          :precision="2"
          :step="100"
        />
      </a-form-item>
      <a-form-item field="bonus_amount" label="赠送金额">
        <a-input-number
          v-model="form.bonus_amount"
          placeholder="请输入赠送金额（负数表示扣减）"
          style="width: 100%"
          :precision="2"
          :step="100"
        />
      </a-form-item>
      <a-form-item field="remark" label="备注">
        <a-textarea
          v-model="form.remark"
          placeholder="请输入备注"
          :max-length="200"
          show-word-limit
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { recharge as rechargeApi } from '@/api/billing'
import { formatCurrency } from '@/utils/formatters'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'

const props = defineProps<{
  visible: boolean
  customerId?: number
  customerName?: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const formRef = ref<FormInstance>()
const loading = ref(false)

const currentDisplayName = ref('')

const form = reactive({
  customer_id: undefined as number | undefined,
  real_amount: null as number | null,
  bonus_amount: null as number | null,
  remark: '',
})

// 当弹窗打开时，预设客户信息
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      if (props.customerId) {
        form.customer_id = props.customerId
        currentDisplayName.value = props.customerName || ''
      } else {
        form.customer_id = undefined
        currentDisplayName.value = ''
      }
    }
  }
)

const handleSubmit = async () => {
  if (!form.customer_id) {
    Message.error('请选择客户')
    return false
  }
  if (form.real_amount === null || form.real_amount === undefined) {
    Message.error('请输入充值金额')
    return false
  }
  if (form.real_amount === 0) {
    Message.error('充值金额不能为 0')
    return false
  }

  if (form.real_amount < 0) {
    const totalDeduction = form.real_amount + (form.bonus_amount || 0)
    const confirmed = await new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: '确认扣减金额',
        content: `本次操作将从客户账户扣除 ${formatCurrency(Math.abs(totalDeduction))}，其中实充扣减 ${formatCurrency(Math.abs(form.real_amount!))}，赠送扣减 ${formatCurrency(Math.abs(form.bonus_amount || 0))}，是否确认？`,
        okText: '确认扣减',
        cancelText: '取消',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    })
    if (!confirmed) return false
  }

  loading.value = true
  try {
    await rechargeApi({
      customer_id: form.customer_id!,
      real_amount: form.real_amount!,
      bonus_amount: form.bonus_amount || undefined,
      remark: form.remark,
    })
    Message.success('充值成功')
    emit('success')
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '充值失败')
    return false
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  formRef.value?.resetFields()
  emit('update:visible', false)
}
</script>
