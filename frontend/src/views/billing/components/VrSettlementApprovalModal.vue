<template>
  <a-modal
    v-model:visible="isVisible"
    :title="mode === 'approve' ? '销售主管审批通过' : '销售主管审批驳回'"
    width="480px"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <!-- 有待一并审批的减免时，顶部只读展示 -->
    <a-alert v-if="discountAmount" type="warning" style="margin-bottom: 12px">
      <template #title>待一并审批的减免</template>
      {{ formatCurrency(discountAmount) }}{{ discountReason ? `（${discountReason}）` : '' }}
    </a-alert>
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item
        field="comment"
        :label="mode === 'approve' ? '审批意见（选填）' : '驳回理由（必填）'"
      >
        <a-textarea
          v-model="form.comment"
          :placeholder="
            mode === 'approve' ? '可填写审批意见' : '请填写驳回理由，退回后销售需重新确认'
          "
          :max-length="500"
          show-word-limit
          :auto-size="{ minRows: 3, maxRows: 6 }"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from 'vue'
import type { FormInstance } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'
import { formatCurrency } from '@/utils/formatters'
import { confirmSalesSupervisor, rejectSalesSupervisor } from '@/api/vrSettlement'

const props = defineProps<{
  visible: boolean
  settlementId?: number
  mode: 'approve' | 'reject'
  discountAmount?: number
  discountReason?: string
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
  comment: '',
})

// 驳回模式理由必填；通过模式可选
const rules = computed(() => ({
  comment:
    props.mode === 'reject'
      ? [
          {
            required: true,
            message: '驳回必须填写理由',
          },
        ]
      : [],
}))

// 打开弹窗时重置表单（审批通过/驳回切换时同样重置）
watch(
  () => props.visible,
  (val) => {
    if (val) {
      form.comment = ''
      nextTick(() => {
        formRef.value?.clearValidate()
      })
    }
  }
)

const handleCancel = () => {
  emit('update:visible', false)
}

const handleSubmit = async () => {
  if (!props.settlementId) return false

  try {
    const errors = await formRef.value?.validate()
    if (errors) return false
  } catch {
    return false
  }

  loading.value = true
  try {
    if (props.mode === 'approve') {
      await confirmSalesSupervisor(props.settlementId, form.comment || undefined)
    } else {
      await rejectSalesSupervisor(props.settlementId, form.comment)
    }
    emit('success')
    return true
  } catch (error) {
    handleError(error)
    return false
  } finally {
    loading.value = false
  }
}
</script>
