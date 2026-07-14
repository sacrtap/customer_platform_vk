<template>
  <a-modal
    v-model:visible="localVisible"
    title="群发邮件"
    width="560px"
    :confirm-loading="loading"
    @confirm="handleConfirm"
    @cancel="emit('update:visible', false)"
  >
    <a-form :model="form" layout="vertical">
      <a-form-item label="收件人">
        <a-input :model-value="`${selectedCount} 个客户`" disabled />
      </a-form-item>
      <a-form-item label="邮件主题" required>
        <a-input v-model="form.subject" placeholder="请输入邮件主题" />
      </a-form-item>
      <a-form-item label="邮件内容" required>
        <a-textarea
          v-model="form.content"
          :auto-size="{ minRows: 6, maxRows: 12 }"
          placeholder="请输入邮件内容"
        />
      </a-form-item>
      <a-form-item>
        <p class="hint-info">将向 {{ selectedCount }} 个客户发送邮件</p>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  loading: boolean
  selectedCount: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [data: { subject: string; content: string }]
}>()

const localVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const form = reactive({ subject: '', content: '' })

watch(
  () => props.visible,
  (v) => {
    if (v) {
      form.subject = ''
      form.content = ''
    }
  }
)

const handleConfirm = () => {
  if (!form.subject.trim() || !form.content.trim()) return
  emit('confirm', { ...form })
}
</script>

<style scoped>
.hint-info {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
}
</style>
