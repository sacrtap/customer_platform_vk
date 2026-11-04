import api from './index'
import { uploadDiscountAttachment } from './billing'

// 明细 Excel 上传复用 billing 的通用上传包装（POST /files/upload），不新建上传函数
export { uploadDiscountAttachment }

// ==================== 类型定义 ====================

export type VrSettlementStatus =
  | 'draft'
  | 'pending_cs_supervisor'
  | 'pending_sales'
  | 'pending_sales_supervisor'
  | 'pending_customer'
  | 'customer_confirmed'
  | 'completed'
  | 'cancelled'

export interface VrSettlementDiscountHistory {
  id: number
  discount_amount: number
  discount_reason?: string | null
  discount_attachment?: string | null
  applied_at: string
  applied_by?: number | null
  applied_by_name?: string | null
}

export interface VrSettlement {
  id: number
  settlement_no: string
  customer_id: number | null
  customer_name?: string | null
  /** 客户指定的运营经理 ID（用于前端判断按钮是否可点击） */
  customer_manager_id?: number | null
  /** 客户指定的销售 ID（用于前端判断按钮是否可点击） */
  customer_sales_manager_id?: number | null
  period_start: string
  period_end: string
  total_amount: number
  discount_amount?: number
  discount_reason?: string | null
  discount_attachment?: string | null
  discount_applied_at?: string | null
  discount_approver_id?: number | null
  discount_approver_name?: string | null
  discount_approved_at?: string | null
  discount_approval_comment?: string | null
  final_amount: number
  status: VrSettlementStatus
  /**
   * 有减免且系统存在持「减免审批」权限的用户时为 true：
   * 销售主管审批通过必须由持 billing:discount_approve 的用户执行（后端同源门禁）
   */
  discount_approval_required?: boolean
  cs_supervisor_confirmed_by?: number | null
  cs_supervisor_confirmed_name?: string | null
  cs_supervisor_confirmed_at?: string | null
  sales_confirmed_by?: number | null
  sales_confirmed_name?: string | null
  sales_confirmed_at?: string | null
  sales_supervisor_confirmed_by?: number | null
  sales_supervisor_confirmed_name?: string | null
  sales_supervisor_confirmed_at?: string | null
  customer_confirmed_at?: string | null
  customer_confirmed_by?: number | null
  customer_confirmed_name?: string | null
  completed_at?: string | null
  completed_by?: number | null
  completed_name?: string | null
  cancelled_at?: string | null
  cancelled_by?: number | null
  cancelled_name?: string | null
  detail_file_path: string | null
  detail_file_name: string | null
  /** 备注说明（创建时填写的多行文本，只读展示） */
  remark?: string | null
  is_auto_generated?: boolean
  created_by?: number | null
  created_by_name?: string | null
  created_at: string
  /** 减免修改历史（按时间倒序） */
  discount_history?: VrSettlementDiscountHistory[]
}

export interface CreateVrSettlementParams {
  customer_id: number
  period_start: string
  period_end: string
  total_amount: number
  detail_file_path: string
  detail_file_name: string
  remark?: string
}

// ==================== API 函数 ====================

export function getVrSettlements(params?: {
  keyword?: string
  status?: string
  customer_id?: number
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: string
}) {
  return api.get('/billing/vr-settlements', { params })
}

export function getVrSettlement(id: number) {
  return api.get(`/billing/vr-settlements/${id}`)
}

export function createVrSettlement(data: CreateVrSettlementParams) {
  return api.post('/billing/vr-settlements', data)
}

export function submitVrSettlement(id: number) {
  return api.post(`/billing/vr-settlements/${id}/submit`)
}

export function confirmCsSupervisor(id: number) {
  return api.post(`/billing/vr-settlements/${id}/confirm-cs`)
}

export function confirmSales(id: number) {
  return api.post(`/billing/vr-settlements/${id}/confirm-sales`)
}

export function confirmSalesSupervisor(id: number, comment?: string) {
  return api.post(`/billing/vr-settlements/${id}/confirm-sales-supervisor`, { comment })
}

export function rejectSalesSupervisor(id: number, comment: string) {
  return api.post(`/billing/vr-settlements/${id}/reject-sales-supervisor`, { comment })
}

export function applyVrDiscount(
  id: number,
  data: { discount_amount: number; discount_reason: string; discount_attachment?: string | null }
) {
  return api.put(`/billing/vr-settlements/${id}/discount`, data)
}

export function confirmVrSettlement(id: number) {
  return api.post(`/billing/vr-settlements/${id}/confirm`)
}

export function retryVrDeduction(id: number) {
  return api.post(`/billing/vr-settlements/${id}/retry-deduction`)
}

export function cancelVrSettlement(id: number) {
  return api.post(`/billing/vr-settlements/${id}/cancel`)
}

/** 回退至上一步审核（回退理由必填）：pending_cs_supervisor→draft / pending_sales→pending_cs_supervisor */
export function rollbackVrSettlement(id: number, comment: string) {
  return api.post(`/billing/vr-settlements/${id}/rollback`, { comment })
}

export function deleteVrSettlement(id: number) {
  return api.delete(`/billing/vr-settlements/${id}`)
}
