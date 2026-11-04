<template>
  <a-modal
    v-model:visible="isVisible"
    :title="title"
    width="480px"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item field="comment" label="回退理由（必填）">
        <a-textarea
          v-model="form.comment"
          placeholder="请填写回退理由"
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

const props = withDefaults(
  defineProps<{
    visible: boolean
    title?: string
    loading?: boolean
  }>(),
  {
    title: '回退',
    loading: false,
  }
)

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [comment: string]
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const formRef = ref<FormInstance>()

const form = reactive({
  comment: '',
})

const rules = {
  comment: [
    {
      required: true,
      message: '回退必须填写理由',
    },
  ],
}

// 打开弹窗时重置表单
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
  try {
    const errors = await formRef.value?.validate()
    if (errors) return false
  } catch {
    return false
  }

  emit('submit', form.comment.trim())
  // 不在此处关闭弹窗：由调用方在提交成功后关闭（失败时保持打开供修改）
  return false
}
</script>
