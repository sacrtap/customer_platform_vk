<template>
  <a-modal
    v-model:visible="isVisible"
    title="余额记录"
    :footer="false"
    width="850px"
    @cancel="emit('update:visible', false)"
  >
    <a-tabs v-model:active-key="activeTab" @change="handleTabChange">
      <!-- 充值记录 -->
      <a-tab-pane key="recharge" title="充值记录">
        <a-table
          :columns="rechargeColumns"
          :data="rechargeRecords"
          :loading="rechargeLoading"
          row-key="id"
          :pagination="rechargePagination"
          @page-change="handleRechargePageChange"
        >
          <template #amount="{ record }">
            <div>{{ formatCurrency(record.total_amount) }}</div>
            <div class="amount-detail">
              <span class="real">实：{{ formatCurrency(record.real_amount) }}</span>
              <span class="bonus">赠：{{ formatCurrency(record.bonus_amount) }}</span>
            </div>
          </template>
          <template #created_at="{ record }">{{ formatDateTime(record.created_at) }}</template>
        </a-table>
      </a-tab-pane>

      <!-- 消耗记录 -->
      <a-tab-pane key="consumption" title="消耗记录">
        <a-table
          :columns="consumptionColumns"
          :data="consumptionRecords"
          :loading="consumptionLoading"
          row-key="id"
          :pagination="consumptionPagination"
          @page-change="handleConsumptionPageChange"
        >
          <template #amount="{ record }">
            <div class="consumption-amount">{{ formatCurrency(record.amount) }}</div>
            <div class="amount-detail">
              <span class="real">实：{{ formatCurrency(record.real_used) }}</span>
              <span class="bonus">赠：{{ formatCurrency(record.bonus_used) }}</span>
            </div>
          </template>
          <template #balance_after="{ record }">
            <span class="balance-after">{{ formatCurrency(record.balance_after) }}</span>
          </template>
          <template #invoice_no="{ record }">
            <a
              v-if="record.invoice_no"
              :href="`/billing/invoices?highlight=${record.invoice_id}`"
              target="_blank"
              class="invoice-link"
              >{{ record.invoice_no }}</a
            >
            <span v-else>-</span>
          </template>
          <template #consumed_at="{ record }">{{ formatDateTime(record.consumed_at) }}</template>
        </a-table>
      </a-tab-pane>
    </a-tabs>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import { getRechargeRecords, getConsumptionRecords } from '@/api/billing'
import type { RechargeRecord, ConsumptionRecord } from '@/api/billing'
import { formatCurrency, formatDateTime } from '@/utils/formatters'

const props = defineProps<{ visible: boolean; customerId?: number }>()
const emit = defineEmits<{ 'update:visible': [value: boolean] }>()
const isVisible = computed({ get: () => props.visible, set: (val) => emit('update:visible', val) })

const activeTab = ref<'recharge' | 'consumption'>('recharge')

// ===== 充值记录 =====
const rechargeLoading = ref(false)
const rechargeRecords = ref<RechargeRecord[]>([])
const rechargePagination = reactive({ current: 1, pageSize: 10, showTotal: true })

const rechargeColumns = [
  { title: '客户', dataIndex: 'customer_name', width: 160 },
  { title: '充值金额', slotName: 'amount', width: 200 },
  { title: '备注', dataIndex: 'remark', width: 200 },
  { title: '充值时间', slotName: 'created_at', width: 180 },
]

const loadRechargeRecords = async () => {
  if (!props.customerId) return
  rechargeLoading.value = true
  try {
    const res = await getRechargeRecords({
      customer_id: props.customerId,
      page: rechargePagination.current,
      page_size: rechargePagination.pageSize,
    })
    rechargeRecords.value = res.data?.list || []
  } catch {
    rechargeRecords.value = []
  } finally {
    rechargeLoading.value = false
  }
}

const handleRechargePageChange = (page: number) => {
  rechargePagination.current = page
  loadRechargeRecords()
}

// ===== 消耗记录 =====
const consumptionLoading = ref(false)
const consumptionRecords = ref<ConsumptionRecord[]>([])
const consumptionPagination = reactive({ current: 1, pageSize: 10, showTotal: true })

const consumptionColumns = [
  { title: '消耗金额', slotName: 'amount', width: 200 },
  { title: '扣款后余额', slotName: 'balance_after', width: 150 },
  { title: '关联结算单', slotName: 'invoice_no', width: 180 },
  { title: '消耗时间', slotName: 'consumed_at', width: 180 },
]

const loadConsumptionRecords = async () => {
  if (!props.customerId) return
  consumptionLoading.value = true
  try {
    const res = await getConsumptionRecords({
      customer_id: props.customerId,
      page: consumptionPagination.current,
      page_size: consumptionPagination.pageSize,
    })
    consumptionRecords.value = res.data?.list || []
  } catch {
    consumptionRecords.value = []
  } finally {
    consumptionLoading.value = false
  }
}

const handleConsumptionPageChange = (page: number) => {
  consumptionPagination.current = page
  loadConsumptionRecords()
}

// ===== Tab 切换 =====
const handleTabChange = (key: string | number) => {
  if (key === 'consumption' && consumptionRecords.value.length === 0) {
    loadConsumptionRecords()
  }
}

// ===== 弹窗打开时加载 =====
watch(
  () => props.visible,
  (val) => {
    if (val) {
      activeTab.value = 'recharge'
      rechargePagination.current = 1
      consumptionPagination.current = 1
      consumptionRecords.value = []
      loadRechargeRecords()
    }
  }
)
</script>

<style scoped>
.amount-detail {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
  display: flex;
  gap: 12px;
}
.amount-detail .real {
  color: var(--primary);
}
.amount-detail .bonus {
  color: var(--green);
}

.consumption-amount {
  color: var(--red, #dc2626);
  font-weight: 600;
}

.balance-after {
  color: var(--primary);
  font-weight: 500;
}

.invoice-link {
  color: var(--primary);
  text-decoration: underline;
  cursor: pointer;
}

.invoice-link:hover {
  opacity: 0.8;
}
</style>
