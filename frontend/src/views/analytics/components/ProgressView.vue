<template>
  <div class="progress-view">
    <a-progress
      :percent="Math.round(progress.percentage * 100)"
      :status="progressStatus"
      :stroke-width="20"
      style="width: 100%"
    />
    <div class="progress-info">
      <div class="status-text">
        <template v-if="progress.status === 'running'">
          <span>正在同步 {{ progress.current_date }} 的数据...</span>
          <span>已完成 {{ progress.completed_days }}/{{ progress.total_days }} 天</span>
          <span v-if="progress.skipped_days > 0">（跳过 {{ progress.skipped_days }} 天）</span>
        </template>
        <template v-else-if="progress.status === 'completed'">
          <span>同步完成</span>
        </template>
        <template v-else-if="progress.status === 'cancelled'">
          <span>同步已取消</span>
        </template>
        <template v-else-if="progress.status === 'failed'">
          <span>同步失败：{{ progress.error_message || '未知错误' }}</span>
        </template>
      </div>
      <div v-if="progress.status === 'completed' || progress.status === 'failed'" class="stats">
        <a-space>
          <a-tag color="green">成功 {{ progress.success_count }} 条</a-tag>
          <a-tag color="red">失败 {{ progress.failed_count }} 条</a-tag>
          <a-tag v-if="progress.skipped_days > 0" color="orange">
            跳过 {{ progress.skipped_days }} 天
          </a-tag>
        </a-space>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SyncTask } from '@/api/syncTasks'

const props = defineProps<{
  progress: SyncTask
}>()

const progressStatus = computed(() => {
  if (props.progress.status === 'completed') return 'success'
  if (props.progress.status === 'failed') return 'danger'
  if (props.progress.status === 'cancelled') return 'warning'
  return 'normal'
})
</script>

<style scoped>
.progress-view {
  padding: 16px;
}

.progress-info {
  margin-top: 16px;
}

.status-text {
  font-size: 14px;
  color: var(--color-text-2);
  margin-bottom: 12px;
}

.status-text span {
  display: block;
  margin-bottom: 4px;
}

.stats {
  margin-top: 12px;
}
</style>
