<template>
  <a-modal
    v-model:visible="isVisible"
    title="提交结算单"
    width="520px"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <div class="submit-modal-hint">
      请确认结算单信息。如需减免，请填写以下字段；无减免可直接提交。
    </div>
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item
        field="discount_amount"
        label="减免金额"
        help="正值为减免，负值为加价；不填则无减免"
      >
        <a-input-number
          v-model="form.discount_amount"
          placeholder="请输入减免金额（可为负值）"
          :precision="2"
          style="width: 100%"
        >
          <template #prefix>¥</template>
        </a-input-number>
      </a-form-item>
      <a-form-item field="reason" label="减免说明">
        <a-textarea
          v-model="form.reason"
          placeholder="填写了减免金额时必填"
          :max-length="500"
          show-word-limit
          :auto-size="{ minRows: 2, maxRows: 4 }"
        />
      </a-form-item>
      <a-form-item field="attachment" label="附件（选填）">
        <a-upload
          v-model:file-list="fileList"
          :limit="1"
          :auto-upload="false"
          accept=".pdf,.jpg,.png,.xlsx,.xls"
          @change="handleFileChange"
        >
          <template #upload-button>
            <a-button>
              <template #icon>+</template>
              选择文件
            </a-button>
          </template>
        </a-upload>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'
import { submitInvoice, uploadDiscountAttachment } from '@/api/billing'

const props = defineProps<{
  visible: boolean
  invoiceId?: number
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

const form = reactive({
  discount_amount: undefined as number | undefined,
  reason: '',
  attachment: undefined as File | undefined,
})

// a-upload 文件列表（受控）
const fileList = ref<{ file?: File; [key: string]: unknown }[]>([])

// 每次打开弹窗时重置表单
watch(
  () => props.visible,
  (val) => {
    if (val) {
      form.discount_amount = undefined
      form.reason = ''
      form.attachment = undefined
      fileList.value = []
      nextTick(() => {
        formRef.value?.clearValidate()
      })
    }
  }
)

const rules = {
  discount_amount: [
    {
      validator: (v: number | undefined, cb: (e?: string) => void) => {
        if (v === undefined || v === null) cb()
        else if (v === 0) cb('减免金额不能为 0')
        else cb()
      },
    },
  ],
  reason: [
    {
      validator: (v: string, cb: (e?: string) => void) => {
        if (form.discount_amount !== undefined && form.discount_amount !== 0 && !v) {
          cb('填写了减免金额时，减免说明为必填')
        } else cb()
      },
    },
  ],
}

const handleFileChange = (fileList: { file?: File; [key: string]: unknown }[]) => {
  if (fileList && fileList.length > 0) {
    const item = fileList[0]
    form.attachment = item.file || item
  }
}

const handleCancel = () => {
  emit('update:visible', false)
}

const handleSubmit = async () => {
  if (!props.invoiceId) return false

  // 表单验证（validate 失败时会 throw）
  try {
    const errors = await formRef.value?.validate()
    if (errors) return false
  } catch {
    return false
  }

  loading.value = true
  try {
    // 如果选择了附件文件，先上传
    let attachmentPath: string | undefined
    if (form.attachment) {
      try {
        const uploadRes = await uploadDiscountAttachment(form.attachment)
        attachmentPath = (uploadRes.data as { file_path?: string })?.file_path
      } catch {
        Message.error('附件上传失败')
        return false
      }
    }

    await submitInvoice(props.invoiceId, {
      discount_amount: form.discount_amount,
      discount_reason: form.reason || undefined,
      discount_attachment: attachmentPath,
    })
    emit('success')
    Message.success('结算单已提交')
    return true
  } catch (error) {
    handleError(error)
    return false
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.submit-modal-hint {
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #f0f5ff;
  border-radius: 8px;
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
}
</style>
