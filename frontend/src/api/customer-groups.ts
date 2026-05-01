import api from './index'
import type { CustomerGroup, CreateGroupParams, GroupMember, GroupStats } from '@/types/customer-groups'

export type { CustomerGroup, CreateGroupParams, GroupMember, GroupStats }

/**
 * 获取群组列表
 */
export function getCustomerGroups() {
  return api.get<{ list: CustomerGroup[] }>('/customer-groups')
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
  return api.get<CustomerGroup>(`/customer-groups/${id}`)
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
  return api.get<{ list: GroupMember[]; total: number }>(`/customer-groups/${id}/members`, { params })
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
  return api.post<{ list: GroupMember[]; total: number }>(`/customer-groups/${id}/apply`, undefined, { params })
}

/**
 * 获取群组统计
 */
export function getGroupStats(id: number) {
  return api.get<GroupStats>(`/customer-groups/${id}/stats`)
}
