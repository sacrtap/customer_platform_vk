import api from './index'
import { CooperationStatus } from '@/types'

/** 获取合作状态列表 */
export function getCooperationStatusesList() {
  return api.get<{ data: CooperationStatus[] }>('/cooperation-statuses')
}

/** 新增合作状态 */
export function createCooperationStatus(data: { name: string; value: string; sort_order: number }) {
  return api.post<{ data: CooperationStatus }>('/cooperation-statuses', data)
}

/** 更新合作状态 */
export function updateCooperationStatus(
  id: number,
  data: { name: string; value: string; sort_order: number }
) {
  return api.put<{ data: CooperationStatus }>(`/cooperation-statuses/${id}`, data)
}

/** 删除合作状态 */
export function deleteCooperationStatus(id: number) {
  return api.delete(`/cooperation-statuses/${id}`)
}
