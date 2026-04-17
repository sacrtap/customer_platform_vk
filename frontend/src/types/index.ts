/**
 * 通用类型定义
 */

/** API 响应格式 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  meta?: {
    page: number
    page_size: number
    total: number
  }
}

/** 分页参数 */
export interface PaginationParams {
  page?: number
  page_size?: number
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  list: T[]
  total: number
}

/** 审计日志 */
export interface AuditLog {
  id: number
  user_id: number | null
  username: string | null
  action: string
  module: string
  record_id: number | null
  record_type: string | null
  changes: { before?: Record<string, unknown>; after?: Record<string, unknown> } | null
  ip_address: string | null
  created_at: string | null
}

/** 标签 */
export interface Tag {
  id: number
  name: string
  type: string
  category: string | null
  customer_count?: number
  profile_count?: number
  created_at: string
}

/** 用户 */
export interface User {
  id: number
  username: string
  email: string | null
  real_name: string | null
  is_active: boolean
  is_system: boolean
  roles: string[]
  created_at: string
}

/** 角色 */
export interface Role {
  id: number
  name: string
  description: string | null
  is_system: boolean
  permissions: string[]
  created_at: string
}

/** 计费模式枚举 */
export enum PricePolicy {
  PRICING = 'pricing',   // 定价
  TIERED = 'tiered',     // 阶梯
  YEARLY = 'yearly',     // 包年
}

/** 计费模式展示映射 */
export const PRICE_POLICY_DISPLAY_MAP: Record<string, string> = {
  pricing: '定价',
  tiered: '阶梯',
  yearly: '包年',
}

/** 客户 */
export interface Customer {
  id: number
  company_id: number
  name: string
  account_type: string | null
  industry: string | null
  customer_level: string | null
  price_policy: PricePolicy | string | null
  manager_id: number | null
  settlement_cycle: string | null
  settlement_type: string | null
  is_key_customer: boolean
  email: string | null
  created_at: string
  updated_at: string
  // 新增字段
  erp_system: string | null
  first_payment_date: string | null
  onboarding_date: string | null
  sales_manager_id: number | null
  cooperation_status: string | null
  is_settlement_enabled: boolean | null
  is_disabled: boolean | null
  notes: string | null
}

/** 客户画像 */
export interface CustomerProfile {
  id: number
  customer_id: number
  scale_level: string | null
  consume_level: string | null
  industry: string | null
  is_real_estate: boolean
  description: string | null
  created_at: string
  updated_at: string
  // 新增字段
  monthly_avg_shots: number | null
  monthly_avg_shots_estimated: number | null
  estimated_annual_spend: number | null
  actual_annual_spend_2025: number | null
}

/** 行业类型字典 */
export interface IndustryType {
  id: number
  name: string
  sort_order: number
}

/** 计费规则 */
export interface PricingRule {
  id: number
  customer_id: number | null
  device_type: string
  pricing_type: string
  unit_price: number | null
  tiers: Record<string, unknown> | null
  package_type: string | null
  package_limits: Record<string, unknown> | null
  effective_date: string
  expiry_date: string | null
  created_at: string
}

/** 结算单 */
export interface Invoice {
  id: number
  invoice_no: string
  customer_id: number
  period_start: string
  period_end: string
  total_amount: number
  discount_amount: number
  discount_reason: string | null
  discount_attachment: string | null
  final_amount: number
  status: string
  approver_id: number | null
  approved_at: string | null
  customer_confirmed_at: string | null
  payment_proof: string | null
  paid_at: string | null
  completed_at: string | null
  is_auto_generated: boolean
  created_at: string
}

/** 余额 */
export interface Balance {
  id: number
  customer_id: number
  total_amount: number
  real_amount: number
  bonus_amount: number
  used_total: number
  used_real: number
  used_bonus: number
  created_at: string
  updated_at: string
}

/** 充值记录 */
export interface RechargeRecord {
  id: number
  customer_id: number
  real_amount: number
  bonus_amount: number
  total_amount: number
  operator_id: number | null
  payment_proof: string | null
  remark: string | null
  created_at: string
}

/** 群组 */
export interface CustomerGroup {
  id: number
  name: string
  description: string | null
  group_type: 'dynamic' | 'static'
  filter_conditions: Record<string, unknown> | null
  member_count: number
  created_by: number
  created_at: string
}

/** 导入结果 */
export interface ImportResult {
  success_count: number
  error_count: number
  errors: string[]
}
