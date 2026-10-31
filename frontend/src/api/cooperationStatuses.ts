import api from './index'
import { fetchExport, fetchImportTemplate, importFile } from './_excel'
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

/** 导出合作状态（全量，返回 blob） */
export function exportCooperationStatuses() {
  return fetchExport('/cooperation-statuses/export')
}

/** 下载合作状态导入模板（返回 blob） */
export function fetchCooperationStatusTemplate() {
  return fetchImportTemplate('/cooperation-statuses/import-template')
}

/** 导入合作状态（file 上传；dryRun=true 预检查不落库） */
export function importCooperationStatuses(file: File, dryRun = false) {
  return importFile(`/cooperation-statuses/import${dryRun ? '?dry_run=true' : ''}`, file)
}
