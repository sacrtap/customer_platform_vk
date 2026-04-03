import api from './index'

export interface CustomerGroup {
  id: number
  name: string
  description?: string
  group_type: 'dynamic' | 'static'
  filter_conditions?: any
  created_at?: string
}

export interface CreateGroupParams {
  name: string
  description?: string
  group_type: 'dynamic' | 'static'
  filter_conditions?: any
}

/**
 * 获取群组列表
 */
export function getCustomerGroups() {
  return api.get('/customer-groups')
}

/**
 * 创建群组
 */
export function createCustomerGroup(data: CreateGroupParams) {
  return api.post('/customer-groups', data)
}

/**
 * 获取群组详情
 */
export function getGroupDetail(id: number) {
  return api.get(`/customer-groups/${id}`)
}

/**
 * 更新群组
 */
export function updateCustomerGroup(id: number, data: Partial<CreateGroupParams>) {
  return api.put(`/customer-groups/${id}`, data)
}

/**
 * 删除群组
 */
export function deleteCustomerGroup(id: number) {
  return api.delete(`/customer-groups/${id}`)
}

/**
 * 获取群组成员列表
 */
export function getGroupMembers(id: number, params?: { page?: number; page_size?: number }) {
  return api.get(`/customer-groups/${id}/members`, { params })
}

/**
 * 添加成员
 */
export function addGroupMember(id: number, customer_id: number) {
  return api.post(`/customer-groups/${id}/members`, { customer_id })
}

/**
 * 移除成员
 */
export function removeGroupMember(id: number, customer_id: number) {
  return api.delete(`/customer-groups/${id}/members/${customer_id}`)
}

/**
 * 应用群组筛选
 */
export function applyGroupFilter(id: number, params?: { page?: number; page_size?: number }) {
  return api.post(`/customer-groups/${id}/apply`, undefined, { params })
}

/**
 * 获取群组统计
 */
export function getGroupStats(id: number) {
  return api.get(`/customer-groups/${id}/stats`)
}
