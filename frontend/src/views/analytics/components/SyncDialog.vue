<template>
  <a-modal
    :visible="isVisible"
    title="数据同步"
    ok-text="提交同步任务"
    cancel-text="取消"
    :ok-loading="loading"
    :on-before-ok="handleBeforeOk"
    @update:visible="handleVisibleUpdate"
    @cancel="handleCancel"
  >
    <a-form :model="form" layout="vertical">
      <a-form-item label="开始日期" required>
        <a-date-picker
          v-model="form.start_date"
          style="width: 100%"
          :disabled-date="disableStartDate"
        />
      </a-form-item>
      <a-form-item label="结束日期" required>
        <a-date-picker
          v-model="form.end_date"
          style="width: 100%"
          :disabled-date="disableEndDate"
        />
      </a-form-item>
      <a-form-item v-if="dateRangeError" :error="dateRangeError">
        <a-alert type="error">{{ dateRangeError }}</a-alert>
      </a-form-item>
      <a-form-item label="同步模式">
        <a-radio-group v-model="form.sync_mode">
          <a-radio value="skip_existing">仅补充缺失数据</a-radio>
          <a-radio value="force_overwrite">强制覆盖已有数据</a-radio>
        </a-radio-group>
      </a-form-item>
      <a-alert v-if="form.sync_mode === 'force_overwrite'" type="warning" style="margin-top: 12px">
        将删除并重新同步选定周期内的所有数据，此操作不可撤销
      </a-alert>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { createSyncTask } from '@/api/syncTasks'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const router = useRouter()

const isVisible = computed(() => props.visible)

const handleVisibleUpdate = (value: boolean) => {
  emit('update:visible', value)
}

const loading = ref(false)

const form = reactive({
  start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
  end_date: new Date(),
  sync_mode: 'skip_existing' as 'skip_existing' | 'force_overwrite',
})

const dateRangeError = computed(() => {
  if (!form.start_date || !form.end_date) return ''
  const start = new Date(form.start_date)
  const end = new Date(form.end_date)

  if (end < start) {
    return '结束日期不能早于开始日期'
  }

  const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1
  if (days > 31) {
    return '时间跨度不能超过31天'
  }

  return ''
})

const disableStartDate = (date: Date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date > today
}

const disableEndDate = (date: Date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date > today
}

const handleBeforeOk = async () => {
  if (dateRangeError.value) {
    Message.error(dateRangeError.value)
    return false
  }

  loading.value = true
  try {
    const start_date = formatDate(form.start_date)
    const end_date = formatDate(form.end_date)

    await createSyncTask({
      start_date,
      end_date,
      sync_mode: form.sync_mode,
    })

    // 提交成功，弹出提示并关闭对话框
    Modal.success({
      title: '同步任务已提交',
      content: '任务已在后台执行，可在「同步日志」中查看处理进度。',
      okText: '查看同步日志',
      cancelText: '关闭',
      hideCancel: false,
      onOk: () => {
        router.push('/system/sync-logs')
      },
    })

    // 通知父组件刷新数据
    emit('success')
    return true // 关闭对话框
  } catch (error: unknown) {
    const err = error as { message?: string }
    const message = err?.message || '创建任务失败'
    Message.error(message)
    return false
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  emit('update:visible', false)
}

const formatDate = (value: Date | string): string => {
  if (typeof value === 'string') {
    return value.split('T')[0]
  }
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

watch(
  () => props.visible,
  (newVal) => {
    if (!newVal) {
      // 对话框关闭时重置表单状态
      loading.value = false
    }
  }
)
</script>
