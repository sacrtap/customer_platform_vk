/**
 * VR编辑费用结算状态映射 — 统一管理所有状态文本和样式
 * 所有组件应从此文件导入，避免重复定义
 */

export const VR_SETTLEMENT_STATUS_MAP: Record<string, string> = {
  draft: '草稿',
  pending_cs_supervisor: '待客服主管审批',
  pending_sales: '待销售审批',
  pending_sales_supervisor: '待销售主管审批',
  pending_customer: '待客户确认',
  customer_confirmed: '客户已确认',
  completed: '已完成',
  cancelled: '已取消',
}

export const VR_SETTLEMENT_STATUS_CLASS_MAP: Record<string, string> = {
  draft: 'gray',
  pending_cs_supervisor: 'amber',
  pending_sales: 'amber',
  pending_sales_supervisor: 'amber',
  pending_customer: 'orange',
  customer_confirmed: 'blue',
  completed: 'green',
  cancelled: 'red',
}

/** 获取状态文本 */
export function getVrSettlementStatusLabel(status: string): string {
  return VR_SETTLEMENT_STATUS_MAP[status] || status
}

/** 获取状态样式类名 */
export function getVrSettlementStatusColor(status: string): string {
  return VR_SETTLEMENT_STATUS_CLASS_MAP[status] || 'gray'
}

/** VR结算单状态选项（用于筛选下拉） */
export const VR_SETTLEMENT_STATUS_OPTIONS = Object.entries(VR_SETTLEMENT_STATUS_MAP).map(
  ([value, label]) => ({ label, value })
)
