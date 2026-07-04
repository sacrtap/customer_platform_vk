<template>
  <a-modal v-model:visible="isVisible" title="申请折扣" width="500px" :confirm-loading="loading" @before-ok="handleSubmit" @cancel="emit('update:visible', false)">
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item field="discount_amount" label="折扣金额" required>
        <a-input-number v-model="form.discount_amount" placeholder="请输入折扣金额" :min="0" :precision="2" style="width: 100%" />
      </a-form-item>
      <a-form-item field="reason" label="申请原因" required>
        <a-textarea v-model="form.reason" placeholder="请输入申请原因" :max-length="500" show-word-limit />
      </a-form-item>
      <a-form-item field="attachment" label="附件（选填）">
        <a-upload
          :limit="1"
          :auto-upload="false"
          accept=".pdf,.jpg,.png"
          @change="handleFileChange"
        >
          <template #upload-button>
            <a-button>选择文件</a-button>
          </template>
        </a-upload>
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
  discount_amount: null as number | null,
  reason: '',
  attachment: undefined as File | undefined,
})

const rules = {
  discount_amount: [
    { required: true, message: '请输入折扣金额' },
    { validator: (v: number, cb: (e?: string) => void) => { if (v <= 0) cb('折扣金额必须大于 0'); else cb() } },
  ],
  reason: [{ required: true, message: '请输入申请原因' }],
}

const handleFileChange = (files: File[]) => {
  form.attachment = files[0]
}

const handleSubmit = async () => {
  if (!props.invoiceId) return false
  const valid = await formRef.value?.validate()
  if (valid) return false

  loading.value = true
  try {
    emit('success')
    Message.success('折扣申请已提交')
    return true
  } catch {
    return false
  } finally {
    loading.value = false
  }
}
</script>
