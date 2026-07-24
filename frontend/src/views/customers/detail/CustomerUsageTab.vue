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
        <template #layerType="{ record }">
          <a-tag>{{ formatLayerType(record.layer_type) }}</a-tag>
        </template>
        <template #quantity="{ record }">
          {{ formatNumber(record.quantity || 0) }}
        </template>
        <template #syncedAt="{ record }">
          {{ (record.synced_at || '').replace('T', ' ').split('.')[0] }}
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

// 楼层类型映射
const LAYER_TYPE_MAP: Record<string, string> = {
  single: '单层',
  multi: '多层',
}

const formatLayerType = (layerType: string | null | undefined): string => {
  if (!layerType) return '-'
  return LAYER_TYPE_MAP[layerType] || layerType
}

const usageColumns = [
  { title: '日期', dataIndex: 'usage_date', width: 120 },
  { title: '设备类型', slotName: 'deviceType', width: 120 },
  { title: '楼层类型', slotName: 'layerType', width: 100 },
  { title: '用量', slotName: 'quantity', width: 100, align: 'right' },
  { title: '同步时间', slotName: 'syncedAt', width: 170 },
]
</script>

<style scoped>
.usage-distribution-section {
  margin-bottom: 24px;
}

.usage-table-section {
  margin-bottom: 24px;
}

.data-table-card :deep(.arco-table-th) {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

.data-table-card :deep(.arco-table-tr:hover .arco-table-td) {
  background: #f8fbff;
}

.data-table-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 0;
  overflow: hidden;
}
</style>
