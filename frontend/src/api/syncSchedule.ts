import request from './index'

export interface SyncSchedule {
  task_name: string
  enabled: boolean
  sync_time: string
  sync_mode: 'skip_existing' | 'force_overwrite'
  next_run_time: string | null
  updated_at: string | null
}

export async function getSyncSchedule(): Promise<SyncSchedule> {
  const res = await request.get('/sync-schedule')
  return res.data
}

export async function updateSyncSchedule(
  params: Partial<Pick<SyncSchedule, 'enabled' | 'sync_time' | 'sync_mode'>>
): Promise<SyncSchedule> {
  const res = await request.put('/sync-schedule', params)
  return res.data
}
