import { computed, onUnmounted, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  getInvoices,
  getInvoice,
  getInvoiceFileStatus,
  generateInvoice,
  applyDiscount,
  submitInvoice,
  confirmInvoice,
  cancelInvoice,
  deleteInvoice,
  confirmOps,
  confirmSales,
  retryDeduction,
  updateInvoiceSettlementAccount,
  batchSubmitInvoices,
  batchCancelInvoices,
  batchDeleteInvoices,
} from '@/api/billing'
import type { Invoice, InvoiceItem } from '@/api/billing'

const defaultFilters = () => ({
  keyword: '',
  status: '',
  industry_type: '',
  erp_system: '',
  manager_id: '',
  sales_manager_id: '',
  invoice_date: [] as string[],
  due_date: [] as string[],
})

export interface SortState {
  sort_by: string
  sort_order: 'asc' | 'desc' | ''
}

/** 从拦截器 reject 的未知错误中提取用户可读消息（拦截器约定 reject { code, message }） */
function errorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === 'object' && 'message' in err && typeof err.message === 'string') {
    return err.message || fallback
  }
  return fallback
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

  /** 轮询列表中文件生成中/待生成的结算单状态 */
  const pollFileStatus = async () => {
    const pollingIds = invoices.value
      .filter(
        (inv) => inv.detail_file_status === 'generating' || inv.detail_file_status === 'pending'
      )
      .map((inv) => inv.id)
    // 也检查当前详情抽屉中的结算单
    if (
      currentDetail.value &&
      (currentDetail.value.detail_file_status === 'generating' ||
        currentDetail.value.detail_file_status === 'pending') &&
      !pollingIds.includes(currentDetail.value.id)
    ) {
      pollingIds.push(currentDetail.value.id)
    }
    if (pollingIds.length === 0) return

    try {
      const res = await getInvoiceFileStatus(pollingIds)
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

      // 如果所有生成中/待生成的都已完成/失败，停止轮询
      const stillPolling =
        invoices.value.some(
          (inv) => inv.detail_file_status === 'generating' || inv.detail_file_status === 'pending'
        ) ||
        currentDetail.value?.detail_file_status === 'generating' ||
        currentDetail.value?.detail_file_status === 'pending'
      if (!stillPolling && pollTimer) {
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
      // 页面恢复可见时，检查是否还有生成中/待生成的文件
      const hasPolling =
        invoices.value.some(
          (inv) => inv.detail_file_status === 'generating' || inv.detail_file_status === 'pending'
        ) ||
        currentDetail.value?.detail_file_status === 'generating' ||
        currentDetail.value?.detail_file_status === 'pending'
      if (hasPolling) {
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
      if (filters.industry_type) params.industry_type = filters.industry_type
      if (filters.erp_system) params.erp_system = filters.erp_system
      if (filters.manager_id) params.manager_id = filters.manager_id
      if (filters.sales_manager_id) params.sales_manager_id = filters.sales_manager_id
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
      // 生成中或刚触发（pending）的结算单启动轮询：pending 会在任务开跑后
      // 转为 generating，再转为 completed/failed；只轮 generating 会漏掉
      // 手动重试后 pending→generating 的这段窗口
      const needsPolling = invoices.value.some(
        (inv) => inv.detail_file_status === 'generating' || inv.detail_file_status === 'pending'
      )
      if (needsPolling) {
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
    try {
      await generateInvoice(data)
      Message.success('结算单生成成功')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '结算单生成失败'))
      throw err
    }
  }

  const doApplyDiscount = async (invoiceId: number, discountAmount: number, reason: string) => {
    try {
      await applyDiscount(invoiceId, { discount_amount: discountAmount, discount_reason: reason })
      Message.success('减免申请提交成功')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '减免申请提交失败'))
      throw err
    }
  }

  const doUpdateSettlementAccount = async (invoiceId: number, accountId: number | null) => {
    try {
      await updateInvoiceSettlementAccount(invoiceId, { settlement_account_id: accountId })
      Message.success('结算账户已更新')
      await fetchDetail(invoiceId)
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '结算账户更新失败'))
      throw err
    }
  }

  const doSubmit = async (invoiceId: number) => {
    try {
      await submitInvoice(invoiceId)
      Message.success('提交成功')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '提交失败'))
      throw err
    }
  }

  const doConfirm = async (invoiceId: number) => {
    try {
      await confirmInvoice(invoiceId)
      Message.success('确认成功')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '确认失败'))
      throw err
    }
  }

  const doCancel = async (invoiceId: number) => {
    try {
      await cancelInvoice(invoiceId)
      Message.success('已取消')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '取消失败'))
      throw err
    }
  }

  const doConfirmOps = async (invoiceId: number) => {
    try {
      await confirmOps(invoiceId)
      Message.success('运营经理确认成功')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '运营经理确认失败'))
      throw err
    }
  }

  const doConfirmSales = async (invoiceId: number) => {
    try {
      await confirmSales(invoiceId)
      Message.success('销售经理确认成功')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '销售经理确认失败'))
      throw err
    }
  }

  const doRetryDeduction = async (invoiceId: number) => {
    try {
      const res = await retryDeduction(invoiceId)
      Message.success(res.data?.message || '重试扣款成功')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '重试扣款失败'))
      throw err
    }
  }

  const doDelete = async (invoiceId: number) => {
    try {
      await deleteInvoice(invoiceId)
      Message.success('已删除')
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '删除失败'))
      throw err
    }
  }

  // ===== 批量操作 =====
  const selectedInvoiceIds = ref<number[]>([])
  const hasSelected = computed(() => selectedInvoiceIds.value.length > 0)

  const handleBatchSelect = (checked: boolean, id: number) => {
    if (checked) {
      if (!selectedInvoiceIds.value.includes(id)) {
        selectedInvoiceIds.value.push(id)
      }
    } else {
      const idx = selectedInvoiceIds.value.indexOf(id)
      if (idx > -1) {
        selectedInvoiceIds.value.splice(idx, 1)
      }
    }
  }

  // 全选仅当前页（与客户管理一致）；取消全选清空整个选择
  const handleBatchSelectAll = (checked: boolean, invoices: Invoice[]) => {
    if (checked) {
      selectedInvoiceIds.value = invoices.map((i) => i.id)
    } else {
      selectedInvoiceIds.value = []
    }
  }

  const clearSelection = () => {
    selectedInvoiceIds.value = []
  }

  const doBatchSubmit = async () => {
    try {
      const res = await batchSubmitInvoices(selectedInvoiceIds.value)
      const data = res.data
      Message.success(
        `批量提交完成：成功 ${data?.success_count ?? 0} 个，跳过 ${data?.skipped?.length ?? 0} 个`
      )
      clearSelection()
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '批量提交失败'))
      throw err
    }
  }

  const doBatchCancel = async () => {
    try {
      const res = await batchCancelInvoices(selectedInvoiceIds.value)
      const data = res.data
      Message.success(
        `批量取消完成：成功 ${data?.success_count ?? 0} 个，跳过 ${data?.skipped?.length ?? 0} 个`
      )
      clearSelection()
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '批量取消失败'))
      throw err
    }
  }

  const doBatchDelete = async () => {
    try {
      const res = await batchDeleteInvoices(selectedInvoiceIds.value)
      const data = res.data
      Message.success(
        `批量删除完成：成功 ${data?.success_count ?? 0} 个，跳过 ${data?.skipped?.length ?? 0} 个`
      )
      clearSelection()
      loadInvoices()
    } catch (err) {
      Message.error(errorMessage(err, '批量删除失败'))
      throw err
    }
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
    doUpdateSettlementAccount,
    doSubmit,
    doConfirm,
    doConfirmOps,
    doConfirmSales,
    doRetryDeduction,
    doCancel,
    doDelete,
    selectedInvoiceIds,
    hasSelected,
    handleBatchSelect,
    handleBatchSelectAll,
    clearSelection,
    doBatchSubmit,
    doBatchCancel,
    doBatchDelete,
  }
}
