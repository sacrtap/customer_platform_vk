import api from './index'

// ==================== 余额管理 ====================

export interface Balance {
  id: number
  customer_id: number
  company_id?: number
  customer_name?: string
  account_type?: string
  industry_type?: string
  settlement_type?: string
  is_key_customer?: boolean
  total_amount: number
  real_amount: number
  bonus_amount: number
  used_total: number
  used_real: number
  used_bonus: number
  last_recharge_at?: string
  /** 近 30 天日均消耗（无消费记录时 null） */
  daily_avg_cost: number | null
  /** 近 30 天有消费的天数 */
  consumption_days: number
  /** 预计剩余天数（null = 无消耗或后付费） */
  days_remaining: number | null
}

export interface BalanceStats {
  total_balance: number
  total_customers: number
  this_month_count: number
  this_month_amount: number
  this_month_real_amount: number
  this_month_bonus_amount: number
  low_balance_count: number
  zero_balance_count: number
  /** days_remaining ≤ 7 的客户数 */
  burning_soon_count: number
}

export function getBalances(params?: {
  customer_id?: number
  keyword?: string
  account_type?: string
  industry?: string
  manager_id?: number
  sales_manager_id?: number
  recharge_date_from?: string
  recharge_date_to?: string
  tag_ids?: string
  is_key_customer?: string
  is_real_estate?: string
  settlement_type?: string
  balance_min?: number
  balance_max?: number
  sort_by?: string
  sort_order?: string
  page?: number
  page_size?: number
}) {
  return api.get('/billing/balances', { params })
}

export function getBalanceStats(params?: {
  keyword?: string
  industry?: string
  account_type?: string
  manager_id?: number
  sales_manager_id?: number
  is_key_customer?: boolean
  is_real_estate?: boolean
  settlement_type?: string
  tag_ids?: string
}) {
  return api.get<BalanceStats>('/billing/balance-stats', { params })
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
  invoice_no?: string | null
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
  customer_name?: string
  device_type?: string
  layer_type?: string
  pricing_type: 'fixed' | 'tiered' | 'package'
  unit_price?: number
  multi_floor_pricing_type?: 'unified' | 'incremental'
  additional_floor_price?: number
  tiers?: Array<{ min: number; max: number | null; price: number }> | Record<string, unknown>
  package_type?: string
  package_limits?: Record<string, unknown>
  effective_date?: string
  expiry_date?: string | null
}

export function getPricingRules(params?: {
  customer_id?: number
  keyword?: string
  device_type?: string
  layer_type?: string
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

// ==================== 定价规则冲突检查 ====================

export interface ConflictCheckParams {
  customer_id: number
  pricing_type: 'fixed' | 'tiered' | 'package'
  device_type?: string
  layer_type?: string
  effective_date: string
  expiry_date?: string
  exclude_id?: number
}

export interface ConflictRule {
  id: number
  pricing_type: string
  effective_date: string | null
  expiry_date: string | null
}

export interface ConflictCheckResult {
  has_conflict: boolean
  conflicting_rules: ConflictRule[]
}

export function checkPricingRuleConflict(params: ConflictCheckParams) {
  return api.get<ConflictCheckResult>('/billing/pricing-rules/check-conflict', { params })
}

// ==================== 结算单管理 ====================

export interface InvoiceItem {
  id?: number
  device_type?: string
  layer_type?: string
  quantity: number
  unit_price: number
  subtotal?: number
  additional_floor_price?: number
  multi_floor_pricing_type?: 'unified' | 'incremental'
  order_count?: number
  pricing_rule_id?: number
}

export interface Invoice {
  id: number
  invoice_no: string
  customer_id: number
  customer_name?: string
  /** 客户指定的运营经理 ID（用于前端判断确认按钮是否可点击） */
  customer_manager_id?: number | null
  /** 客户指定的销售经理 ID（用于前端判断确认按钮是否可点击） */
  customer_sales_manager_id?: number | null
  period_start: string
  period_end: string
  total_amount: number
  discount_amount?: number
  discount_reason?: string
  discount_attachment?: string
  final_amount: number
  status:
    | 'draft'
    | 'pending_ops'
    | 'pending_sales'
    | 'pending_customer'
    | 'customer_confirmed'
    | 'paid'
    | 'completed'
    | 'cancelled'
  is_auto_generated: boolean
  items?: InvoiceItem[]
  approver_id?: number
  approver_name?: string | null
  approved_at?: string
  discount_applied_at?: string
  ops_confirmed_by?: number | null
  ops_confirmed_name?: string | null
  ops_confirmed_at?: string
  sales_confirmed_by?: number | null
  sales_confirmed_name?: string | null
  sales_confirmed_at?: string
  customer_confirmed_at?: string
  customer_confirmed_by?: number | null
  customer_confirmed_name?: string | null
  paid_at?: string
  completed_at?: string
  completed_by?: number | null
  completed_name?: string | null
  cancelled_at?: string
  cancelled_by?: number | null
  cancelled_name?: string | null
  created_by?: number | null
  created_by_name?: string | null
  created_at: string
  /** 明细文件生成状态 */
  detail_file_path?: string | null
  detail_file_status?: string
  /** 减免修改历史（按时间倒序） */
  discount_history?: DiscountHistory[]
}

/** 减免修改历史记录 */
export interface DiscountHistory {
  id: number
  discount_amount: number
  discount_reason?: string
  discount_attachment?: string
  applied_at: string
  applied_by?: number | null
  applied_by_name?: string | null
}

/** 明细文件生成状态类型 */
export type DetailFileStatus = 'pending' | 'generating' | 'completed' | 'failed'

export function getInvoices(params?: {
  customer_id?: number
  keyword?: string
  status?: string
  page?: number
  page_size?: number
}) {
  return api.get('/billing/invoices', { params })
}

export function getInvoice(id: number) {
  return api.get(`/billing/invoices/${id}`)
}

/** 批量查询结算单文件状态（轻量轮询接口） */
export function getInvoiceFileStatus(ids: number[]) {
  return api.get('/billing/invoices/file-status', { params: { ids: ids.join(',') } })
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

export interface CalculateInvoiceItemsParams {
  customer_id: number
  period_start: string
  period_end: string
}

export function calculateInvoiceItems(data: CalculateInvoiceItemsParams) {
  return api.post('/billing/invoices/calculate-items', data)
}

// ==================== 批量生成结算单 ====================

export interface BatchGenerateParams {
  pricing_type?: 'fixed' | 'tiered' | 'package'
  industry_type_ids?: number[]
  scale_levels?: string[]
  consume_levels?: string[]
  is_real_estate?: boolean
}

export interface PreviewBatchCustomer {
  id: number
  name: string
  manager_id: number | null
  sales_manager_id: number | null
  has_manager: boolean
  has_sales_manager: boolean
}

export interface PreviewBatchResult {
  total: number
  customers: PreviewBatchCustomer[]
}

export function previewBatchCustomers(data: BatchGenerateParams) {
  return api.post<PreviewBatchResult>('/billing/invoices/preview-batch', data)
}

export interface GenerateBatchParams extends BatchGenerateParams {
  period_start: string
  period_end: string
}

export interface BatchGenerateResult {
  success_count: number
  generated: Array<{
    customer_id: number
    name: string
    invoice_id: number
    invoice_no: string
    total_amount: number
  }>
  skipped: Array<{
    customer_id: number
    name: string
    reason: string
  }>
}

export function generateInvoicesBatch(data: GenerateBatchParams) {
  return api.post<BatchGenerateResult>('/billing/invoices/generate-batch', data)
}

// ==================== 多角色确认流程 ====================

export function confirmOps(invoiceId: number) {
  return api.post(`/billing/invoices/${invoiceId}/confirm-ops`)
}

export function confirmSales(invoiceId: number) {
  return api.post(`/billing/invoices/${invoiceId}/confirm-sales`)
}

export function retryDeduction(invoiceId: number) {
  return api.post(`/billing/invoices/${invoiceId}/retry-deduction`)
}

export interface ApplyDiscountParams {
  discount_amount: number
  discount_reason?: string
  discount_attachment?: string
}

export function applyDiscount(invoiceId: number, data: ApplyDiscountParams) {
  return api.put(`/billing/invoices/${invoiceId}/discount`, data)
}

/**
 * 上传减免附件文件
 * 注意：不要手动设置 Content-Type，让浏览器自动生成包含 boundary 的 multipart 头
 */
export function uploadDiscountAttachment(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/files/upload', formData)
}

export function submitInvoice(
  invoiceId: number,
  discount?: { discount_amount?: number; discount_reason?: string; discount_attachment?: string }
) {
  return api.post(`/billing/invoices/${invoiceId}/submit`, discount || {})
}

export function downloadInvoiceDetail(id: number) {
  return api.get(`/billing/invoices/${id}/download-detail`, { responseType: 'blob' })
}

export function regenerateInvoiceDetail(id: number) {
  return api.post(`/billing/invoices/${id}/regenerate-detail`)
}

export function getInvoiceDetailLogs(params?: {
  status?: string
  customer_id?: number
  page?: number
  page_size?: number
}) {
  return api.get('/billing/invoices/detail-logs', { params })
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

export function cancelInvoice(id: number) {
  return api.post(`/billing/invoices/${id}/cancel`)
}

// 获取最近结算单（简化接口）
export function getRecentInvoices(limit: number = 10) {
  return getInvoices({ page: 1, page_size: limit })
}

// ==================== 余额趋势 ====================

export interface BalanceTrendItem {
  month: string
  total_amount: number
  real_amount: number
  bonus_amount: number
}

export function getBalanceTrend(customerId: number, months: number = 6) {
  return api.get(`/billing/customers/${customerId}/balance-trend`, { params: { months } })
}

// ==================== 余额导入 ====================

export function importBalances(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/billing/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export function downloadBalanceImportTemplate() {
  return api.get('/billing/import-template', {
    responseType: 'blob',
  })
}

// ==================== 包年套餐管理 ====================

export interface PackagePlan {
  id: number
  name: string
  package_type: string
  device_type?: string
  layer_type?: string
  is_unlimited: boolean
  limit_count?: number | null
  base_fee: number
  /** 超额单价（限量套餐超出 limit_count 后的每单位用量价格） */
  over_limit_unit_price?: number | null
  description?: string
  status: 'active' | 'inactive'
  created_at?: string
  updated_at?: string
}

export function getPackagePlans(params?: {
  keyword?: string
  status?: string
  is_unlimited?: string
  page?: number
  page_size?: number
}) {
  return api.get('/billing/package-plans', { params })
}

export function getPackagePlan(id: number) {
  return api.get(`/billing/package-plans/${id}`)
}

export function createPackagePlan(data: Partial<PackagePlan>) {
  return api.post('/billing/package-plans', data)
}

export function updatePackagePlan(id: number, data: Partial<PackagePlan>) {
  return api.put(`/billing/package-plans/${id}`, data)
}

export function deletePackagePlan(id: number) {
  return api.delete(`/billing/package-plans/${id}`)
}
