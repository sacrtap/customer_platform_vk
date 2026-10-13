import api from './index'
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
