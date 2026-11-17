import request from './index'

export interface CreateSyncTaskParams {
  start_date: string
  end_date: string
  sync_mode: 'skip_existing' | 'force_overwrite'
}

export interface SyncTask {
  task_id: string
  status: string
  sync_mode: string
  total_days: number
  completed_days: number
  skipped_days: number
  current_date: string | null
  success_count: number
  failed_count: number
  percentage: number
  error_message: string | null
  start_date?: string
  end_date?: string
  operator_id?: number | null
  operator_name?: string
  created_at?: string
  completed_at?: string
  /** 执行信息三态（由后端按明细级别计算，历史任务按 status 回退） */
  execution_status?: 'normal' | 'warning' | 'error'
  info_count?: number
  warning_count?: number
  error_count?: number
}

export interface SyncLogDetail {
  id: number
  sync_date: string
  level: 'info' | 'warning' | 'error'
  category: string
  message: string
  /** 内部客户 DB 主键（customers.id，非对外编号） */
  customer_id: number | null
  /** 内部客户名称（Customer.name；费用计算/订单保存明细，喂「公司名」列） */
  customer_name: string | null
  /** 外部客户ID（MySQL group_type；仅订单未匹配明细，无内部客户时喂「公司ID」列） */
  external_customer_id: string | null
  /** 外部公司名（MySQL company_name；仅订单未匹配/保存失败明细，customer_name 为空时兜底「公司名」列） */
  company_name: string | null
  order_code: string | null
  record_count: number
  is_settlement_enabled: boolean | null
  account_type: string | null
  /** 内部客户公司编号（customers.company_id，对外可读编号，随 customer_id 左连带入，喂「公司ID」列） */
  company_id: number | null
  created_at: string | null
}

export interface SyncLogDetailResponse {
  summary: {
    info_count: number
    warning_count: number
    error_count: number
    total_count: number
  }
  list: SyncLogDetail[]
  pagination: {
    page: number
    page_size: number
    total: number
  }
}

export async function createSyncTask(params: CreateSyncTaskParams): Promise<SyncTask> {
  const res = await request.post('/sync-tasks', params)
  return res.data
}

export async function getSyncTaskProgress(taskId: string): Promise<SyncTask> {
  const res = await request.get(`/sync-tasks/${taskId}/progress`)
  return res.data
}

export async function getSyncTask(taskId: string): Promise<SyncTask> {
  const res = await request.get(`/sync-tasks/${taskId}`)
  return res.data
}
export async function cancelSyncTask(taskId: string): Promise<void> {
  await request.post(`/sync-tasks/${taskId}/cancel`)
}

export interface SyncTaskListParams {
  page?: number
  page_size?: number
  status?: string
}

export interface SyncTaskListResponse {
  list: SyncTask[]
  pagination: {
    total: number
    page: number
    page_size: number
  }
}

export interface SyncTaskStats {
  total_tasks: number
  success_rate: number
  last_24h: {
    total: number
    failed: number
  }
}

export async function getSyncTaskList(params?: SyncTaskListParams): Promise<SyncTaskListResponse> {
  const res = await request.get('/sync-tasks', { params })
  return res.data
}

export async function getSyncTaskStats(): Promise<SyncTaskStats> {
  const res = await request.get('/sync-tasks/stats')
  return res.data
}

export async function getSyncTaskDetails(
  taskId: string,
  params?: {
    level?: string
    type?: string
    is_settled?: string
    keyword?: string
    account_type?: string
    page?: number
    page_size?: number
  }
): Promise<SyncLogDetailResponse> {
  const res = await request.get(`/sync-tasks/${taskId}/details`, { params })
  return res.data
}
