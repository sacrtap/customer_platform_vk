import api from './index'

export interface DailyUsage {
  id: number
  customer_id: number
  usage_date: string
  device_type: string
  layer_type: string | null
  quantity: number
  synced_at: string
}

export function getDailyUsage(params?: {
  customer_id?: number
  page?: number
  page_size?: number
  start_date?: string
  end_date?: string
  device_type?: string
}) {
  return api.get('/usage/daily', { params })
}
