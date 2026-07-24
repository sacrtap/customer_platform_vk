<template>
  <a-modal
    v-model:visible="isVisible"
    title="付款确认"
    width="500px"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="emit('update:visible', false)"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item field="payment_method" label="付款方式" required>
        <a-select v-model="form.payment_method" placeholder="请选择付款方式" allow-clear>
          <a-option value="bank_transfer">银行转账</a-option>
          <a-option value="check">支票</a-option>
          <a-option value="cash">现金</a-option>
          <a-option value="other">其他</a-option>
        </a-select>
      </a-form-item>
      <a-form-item field="payment_date" label="付款日期" required>
        <a-date-picker
          v-model="form.payment_date"
          placeholder="请选择付款日期"
          style="width: 100%"
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
import { ref, reactive, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'

const props = defineProps<{
  visible: boolean
  invoiceId?: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isVisible = computed({ get: () => props.visible, set: (val) => emit('update:visible', val) })

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  payment_method: '',
  payment_date: '',
  remark: '',
})

const rules = {
  payment_method: [{ required: true, message: '请选择付款方式' }],
  payment_date: [{ required: true, message: '请选择付款日期' }],
}

const handleSubmit = async () => {
  if (!props.invoiceId) return false
  const valid = await formRef.value?.validate()
  if (valid) return false

  loading.value = true
  try {
    emit('success')
    Message.success('付款确认已提交')
    return true
  } catch {
    return false
  } finally {
    loading.value = false
  }
}
</script>
