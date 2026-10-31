import api from './index'
import { fetchExport, fetchImportTemplate, importFile } from './_excel'
import type { BalanceWhitelistItem, BalanceWhitelistListResult } from '@/types'

/** 获取余额白名单列表（分页 + 关键字） */
export function getBalanceWhitelist(params?: {
  page?: number
  page_size?: number
  keyword?: string
}) {
  return api.get<BalanceWhitelistListResult>('/balance-whitelists', { params })
}

/** 按 ERP 批量导入该 ERP 下所有有效客户（dryRun=true 仅预检不落库） */
export function batchImportBalanceWhitelist(erp_system_value: string, dryRun?: boolean) {
  return api.post<{ dry_run?: boolean; imported: number; skipped: number }>(
    '/balance-whitelists/batch-import',
    { erp_system_value },
    { params: dryRun ? { dry_run: true } : undefined }
  )
}

/** 单独添加单个客户 */
export function addBalanceWhitelist(data: { customer_id: number; static_balance?: number }) {
  return api.post<BalanceWhitelistItem>('/balance-whitelists', data)
}

/** 编辑静态余额（可选更新备注；remark 传 null 表示清空备注） */
export function updateBalanceWhitelist(id: number, static_balance: number, remark?: string | null) {
  return api.put<BalanceWhitelistItem>(`/balance-whitelists/${id}`, { static_balance, remark })
}

/** 移出白名单（软删除） */
export function removeBalanceWhitelist(id: number) {
  return api.delete(`/balance-whitelists/${id}`)
}

// ==================== Excel 批量导入 / 导出 ====================

/** 导入响应（与 ImportModal 的 ImportResult 契约一致） */
export interface BalanceWhitelistImportResult {
  success_count: number
  error_count: number
  dry_run?: boolean
  errors?: string[]
}

/** 批量导入余额白名单（dryRun=true 仅预检查不落库） */
export function importBalanceWhitelist(file: File, dryRun = false) {
  return importFile(`/balance-whitelists/import${dryRun ? '?dry_run=true' : ''}`, file)
}

/** 下载余额白名单导入模板 */
export function fetchBalanceWhitelistTemplate() {
  return fetchImportTemplate('/balance-whitelists/import-template')
}

/** 导出余额白名单（按 keyword 过滤，上限 5 万条） */
export function exportBalanceWhitelist(params?: { keyword?: string }) {
  return fetchExport('/balance-whitelists/export', params)
}
