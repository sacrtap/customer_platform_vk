import api from './index'
import { ErpSystem } from '@/types'

/** 获取 ERP 系统列表 */
export function getErpSystemsList() {
  return api.get<{ data: ErpSystem[] }>('/erp-systems')
}

/** 新增 ERP 系统 */
export function createErpSystem(data: { name: string; value: string; sort_order: number }) {
  return api.post<{ data: ErpSystem }>('/erp-systems', data)
}

/** 更新 ERP 系统 */
export function updateErpSystem(
  id: number,
  data: { name: string; value: string; sort_order: number }
) {
  return api.put<{ data: ErpSystem }>(`/erp-systems/${id}`, data)
}

/** 删除 ERP 系统 */
export function deleteErpSystem(id: number) {
  return api.delete(`/erp-systems/${id}`)
}
