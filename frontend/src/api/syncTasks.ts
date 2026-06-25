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
  operator_id?: number
  created_at?: string
  completed_at?: string
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
