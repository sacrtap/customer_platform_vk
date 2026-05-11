import api from './index'
import { IndustryType } from '@/types'

/** 获取行业类型列表 */
export function getIndustryTypesList() {
  return api.get<{ data: IndustryType[] }>('/industry-types')
}

/** 新增行业类型 */
export function createIndustryType(data: { name: string; sort_order: number }) {
  return api.post<{ data: IndustryType }>('/industry-types', data)
}

/** 更新行业类型 */
export function updateIndustryType(id: number, data: { name: string; sort_order: number }) {
  return api.put<{ data: IndustryType }>(`/industry-types/${id}`, data)
}

/** 删除行业类型 */
export function deleteIndustryType(id: number) {
  return api.delete(`/industry-types/${id}`)
}
