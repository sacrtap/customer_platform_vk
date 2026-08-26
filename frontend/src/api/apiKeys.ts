import api from './index'
import type { ApiKey } from '@/types'

/** 获取 API-Key 列表 */
export function getApiKeysList(params?: { page?: number; page_size?: number }) {
  return api.get<{ data: ApiKey[]; meta: { page: number; page_size: number; total: number } }>(
    '/api-keys',
    { params }
  )
}

/** 创建 API-Key */
export function createApiKey(data: { name: string; description?: string; expires_at?: string }) {
  return api.post<{ data: ApiKey }>('/api-keys', data)
}

/** 切换 API-Key 状态 */
export function toggleApiKeyStatus(id: number) {
  return api.patch<{ data: ApiKey }>(`/api-keys/${id}/toggle-status`)
}

/** 删除 API-Key */
export function deleteApiKey(id: number) {
  return api.delete(`/api-keys/${id}`)
}
