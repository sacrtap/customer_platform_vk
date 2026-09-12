import { onUnmounted, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  getInvoices,
  getInvoice,
  getInvoiceFileStatus,
  generateInvoice,
  applyDiscount,
  payInvoice,
  submitInvoice,
  confirmInvoice,
  cancelInvoice,
  deleteInvoice,
  confirmOps,
  confirmSales,
  retryDeduction,
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
  sort_order: 'asc' | 'desc' | ''
}

export function useInvoice() {
  const loading = ref(false)
  const detailLoading = ref(false)
  const invoices = ref<Invoice[]>([])
  const total = ref(0)
  const currentDetail = ref<Invoice | null>(null)

  // ===== 文件状态轮询 =====
  let pollTimer: ReturnType<typeof setInterval> | null = null
  const POLL_INTERVAL = 5000 // 5 秒轮询

  /** 轮询列表中文件生成中的结算单状态 */
  const pollFileStatus = async () => {
    const generatingIds = invoices.value
      .filter((inv) => inv.detail_file_status === 'generating')
      .map((inv) => inv.id)
    // 也检查当前详情抽屉中的结算单
    if (
      currentDetail.value &&
      currentDetail.value.detail_file_status === 'generating' &&
      !generatingIds.includes(currentDetail.value.id)
    ) {
      generatingIds.push(currentDetail.value.id)
    }
    if (generatingIds.length === 0) return

    try {
      const res = await getInvoiceFileStatus(generatingIds)
      const list: { id: number; detail_file_status: string; detail_file_path?: string }[] =
        res.data?.list || []

      // 更新列表中的状态
      const statusMap = new Map(list.map((item) => [item.id, item]))
      for (const inv of invoices.value) {
        const update = statusMap.get(inv.id)
        if (update && update.detail_file_status !== inv.detail_file_status) {
          inv.detail_file_status = update.detail_file_status
          if (update.detail_file_path) inv.detail_file_path = update.detail_file_path
        }
      }

      // 更新详情中的状态
      if (currentDetail.value) {
        const update = statusMap.get(currentDetail.value.id)
        if (update && update.detail_file_status !== currentDetail.value.detail_file_status) {
          currentDetail.value.detail_file_status = update.detail_file_status
          if (update.detail_file_path)
            currentDetail.value.detail_file_path = update.detail_file_path
        }
      }

      // 如果所有生成中的都已完成/失败，停止轮询
      const stillGenerating =
        invoices.value.some((inv) => inv.detail_file_status === 'generating') ||
        currentDetail.value?.detail_file_status === 'generating'
      if (!stillGenerating && pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    } catch {
      // 轮询失败静默处理
    }
  }

  /** 启动轮询（如已有定时器则不重复启动） */
  const startPolling = () => {
    if (pollTimer) return
    pollTimer = setInterval(pollFileStatus, POLL_INTERVAL)
    // 使用 Visibility API：页面不可见时暂停轮询，可见时恢复
    document.addEventListener('visibilitychange', onVisibilityChange)
  }

  /** 页面可见性变化处理 */
  const onVisibilityChange = () => {
    if (document.hidden && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    } else if (!document.hidden && !pollTimer) {
      // 页面恢复可见时，检查是否还有生成中的文件
      const hasGenerating =
        invoices.value.some((inv) => inv.detail_file_status === 'generating') ||
        currentDetail.value?.detail_file_status === 'generating'
      if (hasGenerating) {
        pollTimer = setInterval(pollFileStatus, POLL_INTERVAL)
        pollFileStatus() // 立即执行一次
      }
    }
  }

  /** 停止轮询 */
  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    document.removeEventListener('visibilitychange', onVisibilityChange)
  }

  // 组件卸载时清理定时器
  onUnmounted(() => {
    stopPolling()
  })

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
    if (sortState.sort_order === 'asc') return 'asc'
    if (sortState.sort_order === 'desc') return 'desc'
    return 'desc'
  }

  const loadInvoices = async () => {
    loading.value = true
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
        sort_by: sortState.sort_by || undefined,
        sort_order: sortState.sort_by ? backendSortOrder() : undefined,
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
      invoices.value = res.data?.list || []
      total.value = res.data?.total || 0
      // 如果列表中有文件生成中的结算单，启动轮询
      const hasGenerating = invoices.value.some((inv) => inv.detail_file_status === 'generating')
      if (hasGenerating) {
        startPolling()
      } else {
        stopPolling()
      }
    } catch {
      invoices.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  const handlePageChange = (page: number) => {
    pagination.current = page
    loadInvoices()
  }
  const handlePageSizeChange = (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.current = 1
    loadInvoices()
  }
  const handleSortChange = (dataIndex: string, direction: string) => {
    sortState.sort_by = dataIndex
    sortState.sort_order = direction as 'asc' | 'desc' | ''
    loadInvoices()
  }
  const handleSearch = () => {
    pagination.current = 1
    loadInvoices()
  }
  const handleReset = () => {
    Object.assign(filters, defaultFilters())
    pagination.current = 1
    loadInvoices()
  }

  const fetchDetail = async (id: number): Promise<Invoice | null> => {
    detailLoading.value = true
    try {
      const res = await getInvoice(id)
      currentDetail.value = res.data
      return res.data
    } finally {
      detailLoading.value = false
    }
  }

  const doGenerate = async (data: {
    customer_id: number
    period_start: string
    period_end: string
    items: InvoiceItem[]
  }) => {
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

  const doConfirmOps = async (invoiceId: number) => {
    await confirmOps(invoiceId)
    Message.success('运营经理确认成功')
    loadInvoices()
  }

  const doConfirmSales = async (invoiceId: number) => {
    await confirmSales(invoiceId)
    Message.success('销售经理确认成功')
    loadInvoices()
  }

  const doRetryDeduction = async (invoiceId: number) => {
    try {
      const res = await retryDeduction(invoiceId)
      Message.success(res.data?.message || '重试扣款成功')
      loadInvoices()
    } catch (err) {
      const msg = (err as { message?: string })?.message || '重试扣款失败'
      Message.error(msg)
      throw err
    }
  }

  const doDelete = async (invoiceId: number) => {
    await deleteInvoice(invoiceId)
    Message.success('已删除')
    loadInvoices()
  }

  return {
    loading,
    detailLoading,
    invoices,
    total,
    currentDetail,
    filters,
    sortState,
    pagination,
    loadInvoices,
    handlePageChange,
    handlePageSizeChange,
    handleSortChange,
    handleSearch,
    handleReset,
    fetchDetail,
    startPolling,
    stopPolling,
    pollFileStatus,
    doGenerate,
    doApplyDiscount,
    doPay,
    doSubmit,
    doConfirm,
    doConfirmOps,
    doConfirmSales,
    doRetryDeduction,
    doCancel,
    doDelete,
  }
}
