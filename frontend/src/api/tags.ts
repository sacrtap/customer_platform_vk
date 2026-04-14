import api from './index'
import type { Tag } from '@/types'

export type { Tag }

// 获取标签列表
export function getTags(params?: {
  page?: number
  page_size?: number
  type?: 'customer' | 'profile'
  category?: string
}) {
  return api.get('/tags', { params })
}

// 获取标签详情
export function getTag(id: number) {
  return api.get(`/tags/${id}`)
}

// 创建标签
export function createTag(data: { name: string; type: 'customer' | 'profile'; category?: string }) {
  return api.post('/tags', data)
}

// 更新标签
export function updateTag(
  id: number,
  data: {
    name?: string
    category?: string
  }
) {
  return api.put(`/tags/${id}`, data)
}

// 删除标签
export function deleteTag(id: number) {
  return api.delete(`/tags/${id}`)
}

// 获取标签使用次数
export function getTagUsage(id: number) {
  return api.get(`/tags/usage/${id}`)
}

// ========== 客户标签管理 ==========

// 获取客户的所有标签
export function getCustomerTags(customerId: number) {
  return api.get(`/customers/${customerId}/tags`)
}

// 给客户添加标签
export function addCustomerTag(customerId: number, tagId: number) {
  return api.post(`/customers/${customerId}/tags/${tagId}`)
}

// 移除客户标签
export function removeCustomerTag(customerId: number, tagId: number) {
  return api.delete(`/customers/${customerId}/tags/${tagId}`)
}

// 批量给客户添加标签
export function batchAddCustomerTags(data: { customer_ids: number[]; tag_ids: number[] }) {
  return api.post('/customers/tags/batch-add', data)
}

// 批量移除客户标签
export function batchRemoveCustomerTags(data: { customer_ids: number[]; tag_ids: number[] }) {
  return api.post('/customers/tags/batch-remove', data)
}

// ========== 画像标签管理 ==========

// 获取画像的所有标签
export function getProfileTags(profileId: number) {
  return api.get(`/profiles/${profileId}/tags`)
}

// 给画像添加标签
export function addProfileTag(profileId: number, tagId: number) {
  return api.post(`/profiles/${profileId}/tags/${tagId}`)
}

// 移除画像标签
export function removeProfileTag(profileId: number, tagId: number) {
  return api.delete(`/profiles/${profileId}/tags/${tagId}`)
}
