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
            <a-radio value="force_overwrite">强制覆盖已有数据</a-radio>
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
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { createSyncTask, type SyncTask } from '@/api/syncTasks'
import ProgressView from './ProgressView.vue'

const router = useRouter()

const props = defineProps<{
  visible: boolean
  minimized?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'update:minimized', value: boolean): void
  (e: 'success'): void
  (e: 'progress', progress: SyncTask): void
}>()

// 内部 visible 状态管理
const isVisible = computed(() => props.visible)

const handleVisibleUpdate = (value: boolean) => {
  emit('update:visible', value)
}

const state = ref<'input' | 'polling' | 'result'>('input')
const loading = ref(false)
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
    if (progress.value.status === 'completed') return '同步完成'
    if (progress.value.status === 'cancelled') return '同步已取消'
    return '同步失败'
  }
  return '数据同步'
})

const okText = computed(() => {
  if (state.value === 'input') return '提交同步任务'
  if (state.value === 'polling') return '取消'
  if (state.value === 'result') {
    return progress.value.status === 'failed' ? '重试' : '关闭'
  }
  return '确定'
})

const cancelText = computed(() => {
  return state.value === 'input' ? '取消' : '关闭'
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
  if (state.value === 'input') {
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

      // 关闭当前对话框
      emit('update:visible', false)
      state.value = 'input'

      // 显示成功提示框，提供跳转至同步日志页面的入口
      Modal.success({
        title: '任务创建成功',
        content: '同步任务已创建，是否立即查看任务进度？',
        okText: '查看任务',
        cancelText: '关闭',
        onOk: () => {
          router.push('/system/sync-logs')
        },
      })

      return false
    } catch (error: unknown) {
      const err = error as { message?: string }
      const message = err?.message || '创建任务失败'
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
  if (state.value === 'polling') {
    // 隐藏模式：关闭 modal 但继续轮询
    emit('update:minimized', true)
    emit('update:visible', false)
  } else {
    // 输入或结果状态：真正关闭
    state.value = 'input'
    emit('update:visible', false)
  }
}

const formatDate = (value: Date | string): string => {
  if (typeof value === 'string') {
    // 处理 ISO 格式字符串，提取日期部分
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
    if (!newVal && !props.minimized) {
      state.value = 'input'
    }
  }
)
</script>
