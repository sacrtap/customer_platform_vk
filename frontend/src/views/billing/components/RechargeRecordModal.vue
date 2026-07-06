<template>
  <a-modal v-model:visible="isVisible" title="充值记录" :footer="false" width="800px" @cancel="emit('update:visible', false)">
    <a-table :columns="columns" :data="records" :loading="loading" row-key="id" :pagination="pagination" @page-change="handlePageChange">
      <template #amount="{ record }">
        <div>{{ formatCurrency(record.total_amount) }}</div>
        <div class="amount-detail"><span class="real">实：{{ formatCurrency(record.real_amount) }}</span><span class="bonus">赠：{{ formatCurrency(record.bonus_amount) }}</span></div>
      </template>
      <template #created_at="{ record }">{{ formatDate(record.created_at) }}</template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import { getRechargeRecords } from '@/api/billing'
import type { RechargeRecord } from '@/api/billing'
import { formatCurrency } from '@/utils/formatters'

const props = defineProps<{ visible: boolean; customerId?: number }>()
const emit = defineEmits<{ 'update:visible': [value: boolean] }>()
const isVisible = computed({ get: () => props.visible, set: (val) => emit('update:visible', val) })

const loading = ref(false)
const records = ref<RechargeRecord[]>([])
const total = ref(0)

const pagination = reactive({ current: 1, pageSize: 10, showTotal: true })

const columns = [
  { title: '客户', dataIndex: 'customer_name', width: 160 },
  { title: '充值金额', slotName: 'amount', width: 200 },
  { title: '备注', dataIndex: 'remark', width: 200 },
  { title: '充值时间', slotName: 'created_at', width: 180 },
]

const formatDate = (d: string) => { if (!d) return ''; return new Date(d).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) }

const loadRecords = async () => {
  if (!props.customerId) return
  loading.value = true
  try {
    const res = await getRechargeRecords({ customer_id: props.customerId, page: pagination.current, page_size: pagination.pageSize })
    records.value = res.data?.list || []
    total.value = res.data?.total || 0
  } catch { records.value = [] }
  finally { loading.value = false }
}

const handlePageChange = (page: number) => { pagination.current = page; loadRecords() }

watch(() => props.visible, (val) => { if (val) { pagination.current = 1; loadRecords() } })
</script>

<style scoped>
.amount-detail { font-size: 12px; color: #8f959e; margin-top: 2px; display: flex; gap: 12px; }
.amount-detail .real { color: #0369a1; }
.amount-detail .bonus { color: #22c55e; }
</style>
