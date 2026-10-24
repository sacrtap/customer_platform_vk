import api from './index'

/** 单条提交摘要（取 commit message 首行 + 短 sha） */
export interface DeployCommit {
  sha: string
  message: string
  author: string
  date: string
}

/** 一次成功部署的更新摘要 */
export interface DeployUpdate {
  /** 部署触发时间（ISO UTC） */
  deployed_at: string
  /** 部署提交短 sha（7 位） */
  head_sha: string
  status: string
  /** GitHub 上该次 workflow 运行链接 */
  html_url: string
  /** 本次部署相对上一次部署的新增提交 */
  commits: DeployCommit[]
}

/** 获取最近部署更新摘要（后端已做 Redis 缓存与失败降级） */
export function getSystemUpdates() {
  return api.get('/system/updates')
}
