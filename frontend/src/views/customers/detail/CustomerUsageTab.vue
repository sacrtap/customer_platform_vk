<template>
  <div class="usage-distribution-section">
    <slot name="chart" />
  </div>

  <div class="usage-table-section">
    <div class="data-table-card">
      <a-table
        :columns="usageColumns"
        :data="usageData"
        :loading="usageLoading"
        :pagination="usagePagination"
        row-key="id"
        @page-change="emit('pageChange', $event)"
      >
        <template #deviceType="{ record }">
          <a-tag>{{ record.device_type }}</a-tag>
        </template>
        <template #quantity="{ record }">
          {{ formatNumber(record.quantity || 0) }}
        </template>
        <template #empty>
          <EmptyState title="暂无用量数据" description="当前客户暂无用量记录" />
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DailyUsage } from '@/api/usage'
import { formatNumber } from '@/utils/formatters'
import EmptyState from '@/components/EmptyState.vue'

defineProps<{
  usageData: DailyUsage[]
  usageLoading: boolean
  usagePagination: { current: number; pageSize: number; total: number }
}>()

const emit = defineEmits<{
  pageChange: [page: number]
}>()

const usageColumns = [
  { title: '日期', dataIndex: 'usage_date', width: 120 },
  { title: '设备类型', slotName: 'deviceType', width: 120 },
  { title: '图层类型', dataIndex: 'layer_type', width: 100 },
  { title: '用量', slotName: 'quantity', width: 100, align: 'right' },
  { title: '同步时间', dataIndex: 'synced_at', width: 170 },
]
</script>

<style scoped>
.usage-distribution-section {
  margin-bottom: 24px;
}

.usage-table-section {
  margin-bottom: 24px;
}

.data-table-card {
  background: var(--color-bg-2);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 16px;
}
</style>
