<template>
  <div class="invoice-page">
    <AppPageHeader
      title="结算单管理"
      description="结算单列表、详情查看与状态流转"
      eyebrow="BILLING"
    >
      <template #actions>
        <a-button v-if="can('billing:edit')" type="primary" @click="generateModalVisible = true">
          <template #icon><icon-plus /></template>生成结算单
        </a-button>
        <a-button v-if="can('billing:view')" @click="handleExport">
          <template #icon><icon-download /></template>导出
        </a-button>
      </template>
    </AppPageHeader>

    <FilterPanel>
      <InvoiceFilters v-model:filters="filters" @search="handleSearch" @reset="handleReset" />
    </FilterPanel>

    <MetricGrid>
      <MetricCard label="本月应收" :value="formatCurrency(thisMonthReceivable)" />
      <MetricCard label="待确认" :value="pendingConfirmCount" trend="需跟进" trend-type="warn" />
      <MetricCard label="已取消" :value="failedCount" />
      <MetricCard label="临期回款" :value="urgentCollectionCount" />
    </MetricGrid>

    <CompactTableShell>
      <a-table
        :columns="columns"
        :data="invoices"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        :scroll="{ x: 'max-content' }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sorter-change="handleSortChange"
      >
        <template #period="{ record }"><span class="cell-nowrap">{{ formatDate(record.period_start) }} ~ {{ formatDate(record.period_end) }}</span></template>
        <template #totalAmount="{ record }"><span class="amount">{{ formatCurrency(record.total_amount) }}</span></template>
        <template #discount="{ record }">
          <span v-if="record.discount_amount && record.discount_amount > 0" class="amount text-danger">-{{ formatCurrency(record.discount_amount) }}</span>
          <span v-else class="text-muted">-</span>
        </template>
        <template #finalAmount="{ record }"><span class="amount-final">{{ formatCurrency(record.final_amount) }}</span></template>
        <template #status="{ record }"><InvoiceStatusBadge :status="record.status" /></template>
        <template #createdAt="{ record }"><span class="cell-nowrap">{{ formatDateTime(record.created_at) }}</span></template>
        <template #action="{ record }">
          <a-dropdown>
            <template #trigger>
              <a-button size="small" ghost>操作</a-button>
            </template>
            <template #overlay>
              <a-menu
                :options="getActionOptions(record)"
                @select="key => handleSingleAction(record, key)"
              />
            </template>
          </a-dropdown>
        </template>
      </a-table>
    </CompactTableShell>

    <InvoiceDetailDrawer v-model:visible="drawerVisible" :detail="currentDetail" @close="drawerVisible = false" />
    <GenerateInvoiceModal v-model:visible="generateModalVisible" @success="handleGenerateSuccess" />
    <DiscountModal v-model:visible="discountModalVisible" :invoice-id="selectedInvoiceId" @success="handleDiscountSuccess" />
    <PayModal v-model:visible="payModalVisible" :invoice-id="selectedInvoiceId" @success="handlePaySuccess" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Modal } from '@arco-design/web-vue'
import { IconPlus, IconDownload } from '@arco-design/web-vue/es/icon'
import { useUserStore } from '@/stores/user'
import { useInvoice } from '@/composables/useInvoice'
import { formatCurrency, formatDate, formatDateTime } from '@/utils/formatters'
import type { Invoice } from '@/api/billing'
import InvoiceFilters from './components/InvoiceFilters.vue'
import InvoiceDetailDrawer from './components/InvoiceDetailDrawer.vue'
import GenerateInvoiceModal from './components/GenerateInvoiceModal.vue'
import DiscountModal from './components/DiscountModal.vue'
import PayModal from './components/PayModal.vue'
import InvoiceStatusBadge from '@/components/invoice/InvoiceStatusBadge.vue'

import {
  AppPageHeader,
  FilterPanel,
  MetricCard,
  MetricGrid,
  CompactTableShell,
} from '@/components/dashboard'

const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)

const {
  loading, invoices, currentDetail, filters, pagination,
  loadInvoices, handlePageChange, handlePageSizeChange, handleSortChange, handleSearch, handleReset,
  fetchDetail, doSubmit, doConfirm, doCancel, doDelete,
} = useInvoice()

const drawerVisible = ref(false)
const generateModalVisible = ref(false)
const discountModalVisible = ref(false)
const payModalVisible = ref(false)
const selectedInvoiceId = ref<number>(0)

const columns = [
  { title: '结算单号', dataIndex: 'invoice_no', width: 180, sortable: { sortDirections: ['ascend','descend'] } },
  { title: '客户', dataIndex: 'customer_name', width: 200 },
  { title: '周期', slotName: 'period', width: 230 },
  { title: '总金额', slotName: 'totalAmount', width: 130, align: 'right', sortable: { sortDirections: ['ascend','descend'] } },
  { title: '折扣', slotName: 'discount', width: 90, align: 'right' },
  { title: '实付', slotName: 'finalAmount', width: 130, align: 'right', sortable: { sortDirections: ['ascend','descend'] } },
  { title: '状态', slotName: 'status', width: 110 },
  { title: '创建时间', slotName: 'createdAt', width: 160, sortable: { sortDirections: ['ascend','descend'] } },
  { title: '操作', slotName: 'action', width: 200, fixed: 'right' as const },
]

const getActionOptions = (record: Invoice) => {
  const options = [
    { label: '详情', key: 'view' },
  ]

  if (record.status === 'draft' && can('billing:edit')) {
    options.push({ label: '提交', key: 'submit' })
  }
  if (record.status === 'pending_customer' && can('billing:view')) {
    options.push({ label: '确认', key: 'confirm' })
  }
  if (['draft', 'pending_customer'].includes(record.status) && can('billing:edit')) {
    options.push({ label: '取消', key: 'cancel' })
  }
  if (['draft', 'cancelled'].includes(record.status) && can('billing:edit')) {
    options.push({ label: '删除', key: 'delete' })
  }
  if (record.status === 'customer_confirmed' && can('billing:view')) {
    options.push({ label: '折扣', key: 'discount' })
    options.push({ label: '回款', key: 'pay' })
  }

  return options
}

const handleSingleAction = async (record: Invoice, action: string) => {
  const actions: Record<string, () => Promise<void>> = {
    view: async () => { selectedInvoiceId.value = record.id; await fetchDetail(record.id); drawerVisible.value = true },
    submit: async () => { await doSubmit(record.id); loadInvoices() },
    confirm: async () => { await doConfirm(record.id); loadInvoices() },
    cancel: async () => {
      await Modal.confirm({ title: '确认取消', content: '确定要取消该结算单吗？', onOk: async () => { await doCancel(record.id); loadInvoices() } })
    },
    delete: async () => {
      await Modal.confirm({ title: '确认删除', content: '确定要删除该结算单吗？此操作不可恢复。', onOk: async () => { await doDelete(record.id); loadInvoices() } })
    },
    discount: async () => { discountModalVisible.value = true },
    pay: async () => { payModalVisible.value = true },
  }

  if (actions[action]) {
    await actions[action]()
  }
}

const handleExport = () => {
  console.log('导出结算单列表')
}

const handleGenerateSuccess = () => {
  generateModalVisible.value = false
}

const handleDiscountSuccess = () => {
  discountModalVisible.value = false
}

const handlePaySuccess = () => {
  payModalVisible.value = false
}

// Computed metrics
const thisMonthReceivable = computed(() => {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  return invoices.value
    .filter(i => new Date(i.created_at) >= start && i.final_amount > 0 && ['customer_confirmed', 'paid', 'completed'].includes(i.status))
    .reduce((sum, i) => sum + i.final_amount, 0)
})

const pendingConfirmCount = computed(() => {
  return invoices.value.filter(i => i.status === 'pending_customer').length
})

const failedCount = computed(() => {
  return invoices.value.filter(i => i.status === 'cancelled').length
})

const urgentCollectionCount = computed(() => {
  const now = new Date()
  const thirtyDaysLater = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000)
  return invoices.value.filter(i =>
    i.status === 'customer_confirmed' &&
    i.paid_at &&
    new Date(i.paid_at) <= thirtyDaysLater
  ).length
})

loadInvoices()
</script>

<style scoped>
.invoice-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 0;
}

.cell-nowrap { white-space: nowrap; }
.amount { font-weight: 500; color: var(--cop-ink); }
.amount-final { font-size: 14px; font-weight: 600; color: var(--cop-primary); }
.text-danger { color: var(--cop-danger); }
.text-muted { color: var(--cop-muted); }
</style>