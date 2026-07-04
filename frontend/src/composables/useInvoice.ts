import { reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  getInvoices,
  getInvoice,
  generateInvoice,
  applyDiscount,
  payInvoice,
  submitInvoice,
  confirmInvoice,
  cancelInvoice,
  deleteInvoice,
} from '@/api/billing'
import type { Invoice, InvoiceItem } from '@/api/billing'

const defaultFilters = () => ({
  keyword: '',
  status: '',
  invoice_date: [] as string[],
  due_date: [] as string[],
})

export interface SortState {
  sort_by: string
  sort_order: 'ascend' | 'descend' | ''
}

export function useInvoice() {
  const loading = ref(false)
  const invoices = ref<Invoice[]>([])
  const total = ref(0)
  const currentDetail = ref<Invoice | null>(null)

  const filters = reactive(defaultFilters())
  const sortState = reactive<SortState>({ sort_by: '', sort_order: '' })

  const pagination = reactive({
    current: 1,
    pageSize: 20,
    showTotal: true,
    showPageSize: true,
    pageSizeOptions: [10, 20, 50, 100],
  })

  const backendSortOrder = (): 'asc' | 'desc' => {
    if (sortState.sort_order === 'ascend') return 'asc'
    if (sortState.sort_order === 'descend') return 'desc'
    return 'asc'
  }

  const loadInvoices = async () => {
    loading.value = true
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
        sort_by: sortState.sort_by || undefined,
        sort_order: backendSortOrder(),
      }
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.status) params.status = filters.status
      if (filters.invoice_date?.length === 2) {
        params.invoice_date_from = filters.invoice_date[0]
        params.invoice_date_to = filters.invoice_date[1]
      }
      if (filters.due_date?.length === 2) {
        params.due_date_from = filters.due_date[0]
        params.due_date_to = filters.due_date[1]
      }
      const res = await getInvoices(params)
      invoices.value = res.data?.items || []
      total.value = res.data?.total || 0
    } catch {
      invoices.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  const handlePageChange = (page: number) => { pagination.current = page; loadInvoices() }
  const handlePageSizeChange = (pageSize: number) => { pagination.pageSize = pageSize; pagination.current = 1; loadInvoices() }
  const handleSortChange = (dataIndex: string, direction: string) => { sortState.sort_by = dataIndex; sortState.sort_order = direction as 'ascend' | 'descend' | ''; loadInvoices() }
  const handleSearch = () => { pagination.current = 1; loadInvoices() }
  const handleReset = () => { Object.assign(filters, defaultFilters()); pagination.current = 1; loadInvoices() }

  const fetchDetail = async (id: number): Promise<Invoice | null> => {
    loading.value = true
    try {
      const res = await getInvoice(id)
      currentDetail.value = res.data
      return res.data
    } finally {
      loading.value = false
    }
  }

  const doGenerate = async (data: { customer_id: number; period_start: string; period_end: string; items: InvoiceItem[] }) => {
    await generateInvoice(data)
    Message.success('结算单生成成功')
    loadInvoices()
  }

  const doApplyDiscount = async (invoiceId: number, discountAmount: number, reason: string) => {
    await applyDiscount(invoiceId, { discount_amount: discountAmount, discount_reason: reason })
    Message.success('折扣申请提交成功')
    loadInvoices()
  }

  const doPay = async (invoiceId: number, paymentMethod: string) => {
    await payInvoice(invoiceId, { payment_proof: paymentMethod })
    Message.success('付款确认成功')
    loadInvoices()
  }

  const doSubmit = async (invoiceId: number) => {
    await submitInvoice(invoiceId)
    Message.success('提交成功')
    loadInvoices()
  }

  const doConfirm = async (invoiceId: number) => {
    await confirmInvoice(invoiceId)
    Message.success('确认成功')
    loadInvoices()
  }

  const doCancel = async (invoiceId: number) => {
    await cancelInvoice(invoiceId)
    Message.success('已取消')
    loadInvoices()
  }

  const doDelete = async (invoiceId: number) => {
    await deleteInvoice(invoiceId)
    Message.success('已删除')
    loadInvoices()
  }

  return {
    loading, invoices, total, currentDetail,
    filters, sortState, pagination,
    loadInvoices, handlePageChange, handlePageSizeChange, handleSortChange, handleSearch, handleReset,
    fetchDetail, doGenerate, doApplyDiscount, doPay, doSubmit, doConfirm, doCancel, doDelete,
  }
}
