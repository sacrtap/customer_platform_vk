export interface UpdateCustomerData {
  company_id?: number
  name?: string
  account_type?: string
  industry_type_id?: number | null
  price_policy?: string
  manager_id?: number
  settlement_cycle?: string
  settlement_type?: string
  is_key_customer?: boolean
  is_real_estate?: boolean | null
  email?: string
  erp_system?: string
  first_payment_date?: string
  onboarding_date?: string
  sales_manager_id?: number
  cooperation_status?: string
  is_settlement_enabled?: boolean
  is_disabled?: boolean
  notes?: string
}
