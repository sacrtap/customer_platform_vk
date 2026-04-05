import request from './index'

/**
 * 获取审计日志列表
 */
export function getAuditLogs(params: {
  page?: number
  page_size?: number
  user_id?: number
  action?: string
  module?: string
  start_date?: string
  end_date?: string
}) {
  return request.get('/audit-logs', { params })
}

/**
 * 获取所有操作类型
 */
export function getAuditActions() {
  return request.get('/audit-logs/actions')
}

/**
 * 获取所有模块
 */
export function getAuditModules() {
  return request.get('/audit-logs/modules')
}
