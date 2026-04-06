import api from './index'

// ==================== 余额管理 ====================

export interface Balance {
  id: number
  customer_id: number
  customer_name?: string
  total_amount: number
  real_amount: number
  bonus_amount: number
  used_total: number
  used_real: number
  used_bonus: number
}

export function getBalances(params?: {
  customer_id?: number
  keyword?: string
  page?: number
  page_size?: number
}) {
  return api.get('/billing/balances', { params })
}

export function getCustomerBalance(customerId: number) {
  return api.get(`/billing/customers/${customerId}/balance`)
}

export interface RechargeParams {
  customer_id: number
  real_amount: number
  bonus_amount?: number
  payment_proof?: string
  remark?: string
}

export function recharge(data: RechargeParams) {
  return api.post('/billing/recharge', data)
}

export interface RechargeRecord {
  id: number
  customer_id: number
  real_amount: number
  bonus_amount: number
  total_amount: number
  operator_id: number
  payment_proof?: string
  remark?: string
  created_at: string
}

export function getRechargeRecords(params?: {
  customer_id?: number
  page?: number
  page_size?: number
}) {
  return api.get('/billing/recharge-records', { params })
}

// ==================== 消费记录 ====================

export interface ConsumptionRecord {
  id: number
  customer_id: number
  invoice_id?: number
  amount: number
  bonus_used: number
  real_used: number
  balance_after: number
  consumed_at: string
}

export function getConsumptionRecords(params?: {
  customer_id?: number
  page?: number
  page_size?: number
}) {
  return api.get('/billing/consumption-records', { params })
}

// ==================== 定价规则 ====================

export interface PricingRule {
  id: number
  customer_id?: number
  device_type: string
  pricing_type: 'fixed' | 'tiered' | 'package'
  unit_price?: number
  tiers?: Record<string, unknown>
  package_type?: string
  package_limits?: Record<string, unknown>
  effective_date?: string
  expiry_date?: string
}

export function getPricingRules(params?: {
  customer_id?: number
  device_type?: string
  pricing_type?: string
  page?: number
  page_size?: number
}) {
  return api.get('/billing/pricing-rules', { params })
}

export function createPricingRule(data: Partial<PricingRule>) {
  return api.post('/billing/pricing-rules', data)
}

export function updatePricingRule(id: number, data: Partial<PricingRule>) {
  return api.put(`/billing/pricing-rules/${id}`, data)
}

export function deletePricingRule(id: number) {
  return api.delete(`/billing/pricing-rules/${id}`)
}

// ==================== 结算单管理 ====================

export interface InvoiceItem {
  device_type: string
  layer_type: string
  quantity: number
  unit_price: number
}

export interface Invoice {
  id: number
  invoice_no: string
  customer_id: number
  customer_name?: string
  period_start: string
  period_end: string
  total_amount: number
  discount_amount?: number
  discount_reason?: string
  discount_attachment?: string
  final_amount: number
  status: 'draft' | 'submitted' | 'confirmed' | 'paid' | 'completed'
  is_auto_generated: boolean
  items?: InvoiceItem[]
  approver_id?: number
  approved_at?: string
  customer_confirmed_at?: string
  paid_at?: string
  completed_at?: string
  created_at: string
}

export function getInvoices(params?: {
  customer_id?: number
  status?: string
  page?: number
  page_size?: number
}) {
  return api.get('/billing/invoices', { params })
}

export function getInvoice(id: number) {
  return api.get(`/billing/invoices/${id}`)
}

export interface GenerateInvoiceParams {
  customer_id: number
  period_start: string
  period_end: string
  items: InvoiceItem[]
}

export function generateInvoice(data: GenerateInvoiceParams) {
  return api.post('/billing/invoices/generate', data)
}

export interface ApplyDiscountParams {
  discount_amount: number
  discount_reason?: string
  discount_attachment?: string
}

export function applyDiscount(invoiceId: number, data: ApplyDiscountParams) {
  return api.put(`/billing/invoices/${invoiceId}/discount`, data)
}

export function submitInvoice(invoiceId: number) {
  return api.post(`/billing/invoices/${invoiceId}/submit`)
}

export function confirmInvoice(invoiceId: number) {
  return api.post(`/billing/invoices/${invoiceId}/confirm`)
}

export function payInvoice(invoiceId: number, data: { payment_proof?: string }) {
  return api.post(`/billing/invoices/${invoiceId}/pay`, data)
}

export function completeInvoice(invoiceId: number) {
  return api.post(`/billing/invoices/${invoiceId}/complete`)
}

export function deleteInvoice(id: number) {
  return api.delete(`/billing/invoices/${id}`)
}

// 获取最近结算单（简化接口）
export function getRecentInvoices(limit: number = 10) {
  return getInvoices({ page: 1, page_size: limit })
}
