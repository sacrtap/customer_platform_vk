<template>
  <a-modal
    :visible="isVisible"
    :title="title"
    :ok-text="okText"
    :cancel-text="cancelText"
    :ok-loading="loading"
    :on-before-ok="handleBeforeOk"
    @update:visible="handleVisibleUpdate"
    @cancel="handleCancel"
  >
    <!-- 输入阶段 -->
    <div v-if="state === 'input'">
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
            <a-radio value="force_overwrite">强制重新同步</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-alert
          v-if="form.sync_mode === 'force_overwrite'"
          type="warning"
          style="margin-top: 12px"
        >
          将删除并重新同步选定周期内的所有数据，此操作不可撤销
        </a-alert>
      </a-form>
    </div>

    <!-- 进度阶段 -->
    <div v-else-if="state === 'polling' || state === 'result'">
      <ProgressView :progress="progress" />
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { createSyncTask, getSyncTaskProgress, type SyncTask } from '@/api/syncTasks'
import ProgressView from './ProgressView.vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

// 内部 visible 状态管理
const isVisible = computed(() => props.visible)

const handleVisibleUpdate = (value: boolean) => {
  emit('update:visible', value)
}

const state = ref<'input' | 'creating' | 'polling' | 'result'>('input')
const loading = ref(false)
const taskId = ref<string>('')
const progress = ref<SyncTask>({
  task_id: '',
  status: '',
  sync_mode: '',
  total_days: 0,
  completed_days: 0,
  skipped_days: 0,
  current_date: null,
  success_count: 0,
  failed_count: 0,
  percentage: 0,
  error_message: null,
})

const form = reactive({
  start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), // 7天前
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

const title = computed(() => {
  if (state.value === 'input') return '数据同步'
  if (state.value === 'polling') return '同步中...'
  if (state.value === 'result') {
    return progress.value.status === 'completed' ? '同步完成' : '同步失败'
  }
  return '数据同步'
})

const okText = computed(() => {
  if (state.value === 'input') return '开始同步'
  if (state.value === 'polling') return '取消'
  if (state.value === 'result') {
    return progress.value.status === 'failed' ? '重试' : '关闭'
  }
  return '确定'
})

const cancelText = computed(() => {
  return state.value === 'input' ? '取消' : '关闭'
})

let pollInterval: number | null = null

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
  if (state.value === 'input') {
    if (dateRangeError.value) {
      Message.error(dateRangeError.value)
      return false
    }

    loading.value = true
    try {
      const start_date = formatDate(form.start_date)
      const end_date = formatDate(form.end_date)

      const result = await createSyncTask({
        start_date,
        end_date,
        sync_mode: form.sync_mode,
      })

      taskId.value = result.task_id
      state.value = 'polling'
      startPolling()
      return false // 不关闭对话框
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '创建任务失败'
      Message.error(message)
      return false
    } finally {
      loading.value = false
    }
  } else if (state.value === 'result') {
    if (progress.value.status === 'failed') {
      // 重试
      state.value = 'input'
      return false
    }
    return true // 关闭对话框
  }
  return false
}

const handleCancel = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
  state.value = 'input'
  emit('update:visible', false)
}

const startPolling = () => {
  pollInterval = window.setInterval(async () => {
    try {
      const result = await getSyncTaskProgress(taskId.value)
      progress.value = result

      if (result.status === 'completed' || result.status === 'failed') {
        if (pollInterval) {
          clearInterval(pollInterval)
          pollInterval = null
        }
        state.value = 'result'
        if (result.status === 'completed') {
          emit('success')
        }
      }
    } catch (error) {
      console.error('轮询进度失败:', error)
    }
  }, 2000)
}

const formatDate = (date: Date): string => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

watch(
  () => props.visible,
  (newVal) => {
    if (!newVal) {
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
      state.value = 'input'
    }
  }
)

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})
</script>
