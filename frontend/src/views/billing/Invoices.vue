<template>
  <div class="invoice-page">
    <div class="page-header">
      <div class="header-title">
        <h1>结算单管理</h1>
        <p class="header-subtitle">结算单列表、详情查看与状态流转</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('billing:edit')" type="primary" @click="generateModalVisible = true">
          <template #icon><icon-plus /></template>生成结算单
        </a-button>
        <a-button v-if="can('billing:view')" @click="handleExport">
          <template #icon><icon-download /></template>导出
        </a-button>
      </div>
    </div>

    <InvoiceFilters v-model:filters="filters" @search="handleSearch" @reset="handleReset" />

    <div class="table-section">
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
          <a-space>
            <a-button type="primary" size="small" @click="viewInvoice(record)">查看</a-button>
            <a-button v-if="record.status === 'draft'" type="primary" size="small" @click="handleSingleAction(record, 'submit')">提交</a-button>
            <a-dropdown>
              <a-button size="small">更多<icon-down /></a-button>
              <template #content>
                <a-doption v-if="record.status === 'pending_customer'" @click="handleSingleAction(record, 'confirm')">确认</a-doption>
                <a-doption v-if="['draft', 'pending_customer'].includes(record.status)" @click="handleSingleAction(record, 'cancel')">取消</a-doption>
                <a-doption v-if="can('billing:edit') && record.status === 'draft'" @click="handleSingleAction(record, 'delete')">删除</a-doption>
              </template>
            </a-dropdown>
          </a-space>
        </template>
      </a-table>
    </div>

    <InvoiceDetailDrawer
      v-model:visible="drawerVisible"
      :invoice="currentDetail"
      @go-customer="goToCustomer"
      @submit="handleSingleAction(currentDetail!, 'submit')"
      @confirm="handleSingleAction(currentDetail!, 'confirm')"
      @cancel="handleSingleAction(currentDetail!, 'cancel')"
    />

    <GenerateInvoiceModal v-model:visible="generateModalVisible" @success="handleGenerateSuccess" />
    <DiscountModal v-model:visible="discountModalVisible" :invoice-id="selectedInvoiceId" @success="handleDiscountSuccess" />
    <PayModal v-model:visible="payModalVisible" :invoice-id="selectedInvoiceId" @success="handlePaySuccess" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Modal } from '@arco-design/web-vue'
import { IconPlus, IconDownload, IconDown } from '@arco-design/web-vue/es/icon'
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

const router = useRouter()
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

const viewInvoice = async (record: Invoice) => {
  selectedInvoiceId.value = record.id
  await fetchDetail(record.id)
  drawerVisible.value = true
}

const goToCustomer = (id: number) => router.push(`/customers/${id}`)

const handleExport = () => {
  // 导出逻辑占位
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

const handleSingleAction = (record: Invoice, action: 'submit' | 'confirm' | 'cancel' | 'delete') => {
  const actions = {
    submit: () => doSubmit(record.id),
    confirm: () => doConfirm(record.id),
    cancel: () => {
      Modal.confirm({ title: '确认取消', content: '确定要取消该结算单吗？', onOk: () => doCancel(record.id) })
    },
    delete: () => {
      Modal.confirm({ title: '确认删除', content: '确定要删除该结算单吗？此操作不可恢复。', onOk: () => doDelete(record.id) })
    },
  }
  actions[action]()
}

// 初始化
loadInvoices()
</script>

<style scoped>
.invoice-page { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.header-title h1 { font-size: 24px; font-weight: 700; color: #2f3645; margin-bottom: 8px; }
.header-subtitle { font-size: 14px; color: #8f959e; margin-top: 4px; }
.header-actions { display: flex; gap: 12px; }
.table-section { background: #fff; border-radius: 12px; padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,.06); overflow-x: auto; }
.amount { font-weight: 500; color: #2f3645; white-space: nowrap; }
.amount-final { font-size: 14px; font-weight: 600; color: #0369a1; white-space: nowrap; }
.text-danger { color: #ef4444; white-space: nowrap; }
.cell-nowrap { white-space: nowrap; }
.text-muted { color: #8f959e; white-space: nowrap; }
::deep(.arco-table-td),
::deep(.arco-table-th) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
