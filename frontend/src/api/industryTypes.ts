import api from './index'
import { IndustryType } from '@/types'

/** 获取行业类型列表 */
export function getIndustryTypesList() {
  return api.get<{ data: IndustryType[] }>('/industry-types')
}

/** 新增行业类型（id 可选，缺省自增；已被占用时后端返回 409） */
export function createIndustryType(data: { id?: number; name: string; sort_order: number }) {
  return api.post<{ data: IndustryType }>('/industry-types', data)
}

/** 更新行业类型（id 可选，缺省保持不变；可借此修改主键 ID） */
export function updateIndustryType(
  id: number,
  data: { id?: number; name: string; sort_order: number }
) {
  return api.put<{ data: IndustryType }>(`/industry-types/${id}`, data)
}

/** 删除行业类型 */
export function deleteIndustryType(id: number) {
  return api.delete(`/industry-types/${id}`)
}
