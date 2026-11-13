/** CRM 充值管理 API：只读回款镜像查询、客户绑定、手动同步与原子导入 */

import api from './index'

export type CrmPaymentStatus = 'pending' | 'imported' | 'blocked'

export interface CrmPaymentItem {
  id: number
  external_id: number
  crm_customer_id: number | null
  crm_customer_name: string | null
  contract_external_id: number | null
  contract_title: string | null
  /** 源回款金额（字符串十进制，避免浮点误差） */
  amount: string | null
  receive_date: string | null
  approve_status: string | null
  industry_path: string | null
  industry_label: string | null
  eligible: boolean
  blocked_reason: string | null
  source_changed: boolean
  status: CrmPaymentStatus
  bound_customer_id: number | null
  bound_customer_name: string | null
  bound_company_id: string | null
  last_seen_at: string | null
  recharge_record_id: number | null
  real_amount: string | null
  bonus_amount: string | null
  total_amount: string | null
  /** 入账业务归期（CRM 回款日） */
  recharge_date: string | null
  /** 入账操作时刻 */
  recharge_created_at: string | null
}

export interface CrmPaymentListData {
  list: CrmPaymentItem[]
  total: number
  page: number
  page_size: number
  /** CRM 凭据是否已配置；未启用时同步/导入/绑定均不可用 */
  crm_enabled: boolean
}

export interface CrmSyncRunItem {
  id: number
  month: string
  trigger: 'manual' | 'scheduled'
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  phase: string | null
  started_at: string | null
  finished_at: string | null
  heartbeat_at: string | null
  customer_count: number | null
  contract_count: number | null
  scanned_contract_count: number | null
  scanned_payment_count: number | null
  payment_count: number | null
  eligible_count: number | null
  error_message: string | null
}

export interface CrmSyncRunListData {
  list: CrmSyncRunItem[]
  total: number
  page: number
  page_size: number
  latest_success_at: string | null
}

export interface CrmCustomerCandidate {
  id: number
  external_id: number
  name: string
  owner_name: string | null
  score: number
  bound_to_current: boolean
  unavailable: boolean
}

export interface CrmCustomerCandidateData {
  list: CrmCustomerCandidate[]
  total: number
  page: number
  page_size: number
  directory_updated_at: string | null
  directory_synced: boolean
}

export interface CrmBindingResult {
  crm_customer_id: number | null
  crm_customer_external_id: number | null
  crm_customer_name: string | null
}

export interface CrmImportPayload {
  customer_id: number
  real_amount: string
  bonus_amount?: string
}

export interface CrmImportResult {
  recharge_record_id: number
  customer_id: number
  real_amount: string
  bonus_amount: string
  total_amount: string
  recharge_date: string | null
  created_at: string | null
  already_imported: boolean
  balance: {
    real_amount: string
    bonus_amount: string
    total_amount: string
  }
}

// ==================== 回款查询 ====================

export function getCrmPayments(params?: {
  month?: string
  status?: CrmPaymentStatus | 'all'
  keyword?: string
  page?: number
  page_size?: number
}) {
  return api.get('/crm-recharge/payments', { params })
}

export function getCrmPayment(id: number) {
  return api.get(`/crm-recharge/payments/${id}`)
}

// ==================== 客户绑定 ====================

export function getCrmCustomerCandidates(
  customerId: number,
  params?: { query?: string; page?: number; page_size?: number }
) {
  return api.get('/crm-recharge/customers/candidates', {
    params: { customer_id: customerId, ...params },
  })
}

export function updateCrmCustomerBinding(customerId: number, crmCustomerId: number | null) {
  return api.put(`/crm-recharge/customers/${customerId}/binding`, {
    crm_customer_id: crmCustomerId,
  })
}

// ==================== 同步 ====================

export function createCrmSyncRun(month: string) {
  return api.post('/crm-recharge/sync-runs', { month })
}

export interface CrmRevokeImportPayload {
  customer_id: number
  /** 撤销原因（审计必填） */
  reason: string
  /** 余额不足时由超级管理员确认强制撤销（线下核对） */
  force?: boolean
}

export interface CrmRevokeImportResult {
  payment_id: number
  payment_external_id: number
  customer_id: number
  recharge_record_id: number
  real_amount: string
  bonus_amount: string
  recharge_date: string | null
  needs_manual_reconciliation: boolean
  shortfall_real: string
  shortfall_bonus: string
  balance: { real_amount: string; bonus_amount: string; total_amount: string }
}

/** 撤销一笔 CRM 充值导入：余额回退并释放该回款，可重新导入 */
export function revokeCrmImport(paymentId: number, payload: CrmRevokeImportPayload) {
  return api.post(`/crm-recharge/payments/${paymentId}/import/revoke`, payload)
}

export function getCrmSyncRuns(params?: { month?: string; page?: number; page_size?: number }) {
  return api.get('/crm-recharge/sync-runs', { params })
}

// ==================== 导入 ====================

export function importCrmPayment(paymentId: number, payload: CrmImportPayload) {
  return api.post(`/crm-recharge/payments/${paymentId}/import`, payload)
}

// ==================== 配置（开关 + 凭据，支持更换） ====================

export interface CrmSettings {
  enabled: boolean
  base_url: string
  corp_id: string
  /** 手机号打码展示，例如 138****0000 */
  phone_masked: string
  password_set: boolean
  credentials_complete: boolean
  /** 开关打开且凭据完整，同步/导入才可用 */
  active: boolean
  /** database=页面保存过；environment=回退部署环境变量 */
  source: 'database' | 'environment'
  /** 服务端是否已注入加密密钥 CRM_CREDENTIAL_KEY（否则无法保存密码） */
  credential_key_configured: boolean
  crm_enabled_for_requests: boolean
  verified_customer_total?: number | null
  /** 保存时验证降级的说明（凭据有效、列表不可读） */
  verification_warning?: string | null
}

export interface CrmSettingsPayload {
  enabled?: boolean
  base_url?: string
  corp_id?: string
  phone?: string
  /** 留空表示保留已保存的密码 */
  password?: string
  clear_password?: boolean
  /** 保存前是否验证账号密码，默认 true */
  verify?: boolean
  /** 跳过验证强制保存（上游临时不可用时二次确认后使用） */
  force?: boolean
}

export interface CrmVerifyResult {
  ok: boolean
  corp_id: string
  customer_total: number | null
  /** 登录凭据有效但客户列表读不出来时的降级提示 */
  warning?: string | null
}

export function getCrmSettings() {
  return api.get('/crm-recharge/settings')
}

export function testCrmCredentials(payload: CrmSettingsPayload) {
  return api.post('/crm-recharge/settings/test', payload)
}

export function updateCrmSettings(payload: CrmSettingsPayload) {
  return api.put('/crm-recharge/settings', payload)
}
