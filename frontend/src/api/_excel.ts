/**
 * Excel 导入/导出的共享请求助手（内部模块，下划线前缀表不对外公开）。
 *
 * 从 api/billing.ts 提取：billing 的 4 个导入/导出端点最早固化了这套写法，
 * 管理页（用户/标签/角色/行业类型/合作状态/余额白名单/API-Key）的导入导出
 * 复用同一约定。billing.ts 从本模块 re-export，对外签名不变。
 */
import api from './index'

/**
 * 同步重载端点的超时（毫秒）。
 *
 * 导入/导出由后端在请求内同步完成：逐行 DB 写入（或上限 5 万行的查询 + openpyxl 生成），
 * 大文件在 DB 负载高时会明显超过 axios 实例的全局 15s 超时。前端一旦中断，服务端仍会
 * 继续执行并提交数据 —— 用户看到「失败」而数据已落库，重试即产生重复数据，故单独放宽。
 */
export const LONG_RUNNING_REQUEST_TIMEOUT = 120000

/**
 * 上传文件进行导入（后端同步逐行写入，单独放宽超时避免前端先断）。
 * 注意：不要手动设置 Content-Type，让浏览器/axios 自动生成含 boundary 的 multipart 头；
 * 手写 `multipart/form-data`（无 boundary）反而会导致后端无法解析文件边界。
 */
export function importFile(url: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post(url, formData, { timeout: LONG_RUNNING_REQUEST_TIMEOUT })
}

/** 下载导入模板（blob 响应）。 */
export function fetchImportTemplate(url: string) {
  return api.get(url, { responseType: 'blob' })
}

/** 导出（blob 响应，params 为当前筛选条件；后端剔除分页参数，上限 5 万条）。 */
export function fetchExport<P extends object>(url: string, params?: P) {
  return api.get(url, { params, responseType: 'blob', timeout: LONG_RUNNING_REQUEST_TIMEOUT })
}
