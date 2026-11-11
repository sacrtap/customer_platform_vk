import { computed, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  getVrSettlements,
  getVrSettlement,
  createVrSettlement,
  submitVrSettlement,
  confirmCsSupervisor,
  confirmSales,
  confirmSalesSupervisor,
  rejectSalesSupervisor,
  applyVrDiscount,
  confirmVrSettlement,
  retryVrDeduction,
  cancelVrSettlement,
  rollbackVrSettlement,
  deleteVrSettlement,
} from '@/api/vrSettlement'
import type { VrSettlement } from '@/api/vrSettlement'

const defaultFilters = () => ({
  keyword: '',
  status: '',
})

export interface SortState {
  sort_by: string
  sort_order: 'asc' | 'desc' | ''
}

// 排序方向归一化：兼容 arco a-table 回调的 ascend/descend 与后端 asc/desc 两种
// 词表。集中在入口归一，避免调用方各自转换时漏掉方向映射导致降序失效
// （与 useInvoice/useBalance 同一处理）。
const normalizeSortOrder = (direction: string): 'asc' | 'desc' | '' => {
  if (direction === 'asc' || direction === 'ascend') return 'asc'
  if (direction === 'desc' || direction === 'descend') return 'desc'
  return ''
}

/** 从拦截器 reject 的未知错误中提取用户可读消息（拦截器约定 reject { code, message }） */
function errorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === 'object' && 'message' in err && typeof err.message === 'string') {
    return err.message || fallback
  }
  return fallback
}

export function useVrSettlement() {
  const loading = ref(false)
  const detailLoading = ref(false)
  const settlements = ref<VrSettlement[]>([])
  const total = ref(0)
  const currentDetail = ref<VrSettlement | null>(null)

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

  const loadVrSettlements = async () => {
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
      const res = await getVrSettlements(params)
      settlements.value = res.data?.list || []
      total.value = res.data?.total || 0
    } catch {
      settlements.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  const handlePageChange = (page: number) => {
    pagination.current = page
    loadVrSettlements()
  }
  const handlePageSizeChange = (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.current = 1
    loadVrSettlements()
  }
  const handleSortChange = (dataIndex: string, direction: string) => {
    sortState.sort_by = dataIndex
    sortState.sort_order = normalizeSortOrder(direction)
    loadVrSettlements()
  }
  const handleSearch = () => {
    pagination.current = 1
    loadVrSettlements()
  }
  const handleReset = () => {
    Object.assign(filters, defaultFilters())
    pagination.current = 1
    loadVrSettlements()
  }

  const fetchVrDetail = async (id: number): Promise<VrSettlement | null> => {
    detailLoading.value = true
    try {
      const res = await getVrSettlement(id)
      currentDetail.value = res.data
      return res.data
    } finally {
      detailLoading.value = false
    }
  }

  const doCreate = async (data: Parameters<typeof createVrSettlement>[0]) => {
    try {
      await createVrSettlement(data)
      Message.success('创建成功')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '创建失败'))
      throw err
    }
  }

  const doSubmit = async (id: number) => {
    try {
      await submitVrSettlement(id)
      Message.success('提交成功')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '提交失败'))
      throw err
    }
  }

  const doConfirmCs = async (id: number) => {
    try {
      await confirmCsSupervisor(id)
      Message.success('客服主管审批成功')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '客服主管审批失败'))
      throw err
    }
  }

  const doConfirmSales = async (id: number) => {
    try {
      await confirmSales(id)
      Message.success('销售审批成功')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '销售审批失败'))
      throw err
    }
  }

  const doConfirmSalesSupervisor = async (id: number, comment?: string) => {
    try {
      await confirmSalesSupervisor(id, comment)
      Message.success('审批通过')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '审批失败'))
      throw err
    }
  }

  const doRejectSalesSupervisor = async (id: number, comment: string) => {
    try {
      await rejectSalesSupervisor(id, comment)
      Message.success('已驳回，退回销售审批')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '驳回失败'))
      throw err
    }
  }

  const doRollback = async (id: number, comment: string) => {
    try {
      await rollbackVrSettlement(id, comment)
      Message.success('已回退至上一步')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '回退失败'))
      throw err
    }
  }

  const doApplyDiscount = async (
    id: number,
    data: { discount_amount: number; discount_reason: string; discount_attachment?: string | null }
  ) => {
    try {
      await applyVrDiscount(id, data)
      Message.success('减免信息已更新')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '减免提交失败'))
      throw err
    }
  }

  const doConfirm = async (id: number) => {
    try {
      await confirmVrSettlement(id)
      Message.success('确认成功')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '确认失败'))
      throw err
    }
  }

  const doRetryDeduction = async (id: number) => {
    try {
      const res = await retryVrDeduction(id)
      Message.success(res.data?.message || '重试扣款成功')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '重试扣款失败'))
      throw err
    }
  }

  const doCancel = async (id: number) => {
    try {
      await cancelVrSettlement(id)
      Message.success('已取消')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '取消失败'))
      throw err
    }
  }

  const doDelete = async (id: number) => {
    try {
      await deleteVrSettlement(id)
      Message.success('已删除')
      loadVrSettlements()
    } catch (err) {
      Message.error(errorMessage(err, '删除失败'))
      throw err
    }
  }

  // ===== 多选（跨页保留选中）=====
  const selectedIds = ref<number[]>([])
  const hasSelected = computed(() => selectedIds.value.length > 0)

  const handleBatchSelect = (checked: boolean, id: number) => {
    if (checked) {
      if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
    } else {
      const idx = selectedIds.value.indexOf(id)
      if (idx >= 0) selectedIds.value.splice(idx, 1)
    }
  }

  const handleBatchSelectAll = (checked: boolean, list: VrSettlement[]) => {
    if (checked) {
      for (const item of list) {
        if (!selectedIds.value.includes(item.id)) selectedIds.value.push(item.id)
      }
    } else {
      const pageIds = new Set(list.map((i) => i.id))
      selectedIds.value = selectedIds.value.filter((id) => !pageIds.has(id))
    }
  }

  const clearSelection = () => {
    selectedIds.value = []
  }

  return {
    loading,
    detailLoading,
    settlements,
    total,
    currentDetail,
    filters,
    sortState,
    pagination,
    selectedIds,
    hasSelected,
    loadVrSettlements,
    fetchVrDetail,
    handlePageChange,
    handlePageSizeChange,
    handleSortChange,
    handleSearch,
    handleReset,
    doCreate,
    doSubmit,
    doConfirmCs,
    doConfirmSales,
    doConfirmSalesSupervisor,
    doRejectSalesSupervisor,
    doRollback,
    doApplyDiscount,
    doConfirm,
    doRetryDeduction,
    doCancel,
    doDelete,
    handleBatchSelect,
    handleBatchSelectAll,
    clearSelection,
  }
}
