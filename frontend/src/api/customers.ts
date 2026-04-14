import api from './index'

// 获取客户列表
export function getCustomers(params?: {
  page?: number
  page_size?: number
  keyword?: string
  account_type?: string
  industry?: string
  customer_level?: string
  manager_id?: number
  settlement_type?: string
  is_key_customer?: boolean
}) {
  return api.get('/customers', { params })
}

// 获取客户详情
export function getCustomer(id: number) {
  return api.get(`/customers/${id}`)
}

// 创建客户
export function createCustomer(data: {
  company_id: string
  name: string
  account_type?: string
  industry?: string
  customer_level?: string
  price_policy?: string
  manager_id?: number
  settlement_cycle?: string
  settlement_type?: string
  is_key_customer?: boolean
  email?: string
}) {
  return api.post('/customers', data)
}

// 更新客户
export function updateCustomer(
  id: number,
  data: {
    name?: string
    account_type?: string
    industry?: string
    customer_level?: string
    price_policy?: string
    manager_id?: number
    settlement_cycle?: string
    settlement_type?: string
    is_key_customer?: boolean
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
) {
  return api.put(`/customers/${id}`, data)
}

// 删除客户
export function deleteCustomer(id: number) {
  return api.delete(`/customers/${id}`)
}

// 获取客户画像
export function getProfile(customerId: number) {
  return api.get(`/customers/${customerId}/profile`)
}

// 更新客户画像
export function updateProfile(
  customerId: number,
  data: {
    scale_level?: string
    consume_level?: string
    industry?: string
    is_real_estate?: boolean
    description?: string
    monthly_avg_shots?: number
    monthly_avg_shots_estimated?: number
    estimated_annual_spend?: number
    actual_annual_spend_2025?: number
  }
) {
  return api.put(`/customers/${customerId}/profile`, data)
}

// Excel 导入
export function importCustomers(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/customers/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

// 下载导入模板
export function downloadImportTemplate() {
  return api.get('/customers/import-template', {
    responseType: 'blob',
  })
}

// Excel 导出
export function exportCustomers(params?: {
  keyword?: string
  account_type?: string
  industry?: string
  customer_level?: string
  manager_id?: number
  settlement_type?: string
  is_key_customer?: boolean
}) {
  return api.get('/customers/export', {
    params,
    responseType: 'blob',
  })
}

// 获取行业类型字典
export function getIndustryTypes() {
  return api.get('/dicts/industry_types')
}
