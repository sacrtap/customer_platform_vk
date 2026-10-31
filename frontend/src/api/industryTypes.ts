import api from './index'
import { fetchExport, fetchImportTemplate, importFile } from './_excel'
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

// ==================== 行业类型导入导出 ====================

/** 导出行业类型为 Excel（全量，无筛选参数） */
export function exportIndustryTypes() {
  return fetchExport('/industry-types/export')
}

/** 下载行业类型导入模板（blob 响应） */
export function fetchIndustryTypeTemplate() {
  return fetchImportTemplate('/industry-types/import-template')
}

/** 批量导入行业类型（后端同步逐行写入，dryRun 为预检查不落库） */
export function importIndustryTypes(file: File, dryRun = false) {
  return importFile(`/industry-types/import${dryRun ? '?dry_run=true' : ''}`, file)
}
