/**
 * 结算单状态映射 — 统一管理所有状态文本和样式
 * 所有组件应从此文件导入，避免重复定义
 */

export const INVOICE_STATUS_MAP: Record<string, string> = {
  draft: '草稿',
  pending_ops: '待运营经理确认',
  pending_sales: '待销售经理确认',
  pending_customer: '待客户确认',
  customer_confirmed: '客户已确认',
  paid: '已付款',
  completed: '已完成',
  cancelled: '已取消',
}

export const INVOICE_STATUS_CLASS_MAP: Record<string, string> = {
  draft: 'gray',
  pending_ops: 'amber',
  pending_sales: 'amber',
  pending_customer: 'orange',
  customer_confirmed: 'blue',
  paid: 'green',
  completed: 'green',
  cancelled: 'red',
}

/** 获取状态文本 */
export function getInvoiceStatusLabel(status: string): string {
  return INVOICE_STATUS_MAP[status] || status
}

/** 获取状态样式类名 */
export function getInvoiceStatusColor(status: string): string {
  return INVOICE_STATUS_CLASS_MAP[status] || 'gray'
}

/** 结算单状态选项（用于筛选下拉） */
export const INVOICE_STATUS_OPTIONS = Object.entries(INVOICE_STATUS_MAP).map(([value, label]) => ({
  label,
  value,
}))
