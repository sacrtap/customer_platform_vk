import api from './index'

// ==================== 消耗分析 ====================

export interface ConsumptionTrendItem {
  date: string
  order_count: number
  cost: number
  year?: number
  month?: number
  period?: string
  total_amount?: number
}

export function getConsumptionTrend(params?: {
  start_date?: string
  end_date?: string
  customer_id?: number
  keyword?: string
  metric?: 'cost' | 'order_count'
  force_refresh?: boolean
}) {
  return api.get('/analytics/consumption/trend', { params })
}

export interface TopCustomer {
  customer_id: number
  customer_name: string
  order_count: number
  cost: number
  company_id?: number
  total_amount?: number
}

export function getTopCustomers(params?: {
  start_date?: string
  end_date?: string
  limit?: number
  metric?: 'cost' | 'order_count'
  force_refresh?: boolean
}) {
  return api.get('/analytics/consumption/top', { params })
}

export interface DeviceDistributionItem {
  device_type: string
  order_count: number
  cost: number
  order_count_percentage: number
  cost_percentage: number
  total_quantity?: number
  total_amount?: number
}

export function getDeviceDistribution(params?: {
  start_date?: string
  end_date?: string
  customer_id?: number
  keyword?: string
  metric?: 'cost' | 'order_count'
  force_refresh?: boolean
}) {
  return api.get('/analytics/consumption/device-distribution', { params })
}

export function manualSyncConsumption() {
  return api.post('/analytics/consumption/sync')
}

// ==================== 回款分析 ====================

export interface PaymentAnalysis {
  total_invoiced: number
  total_discount: number
  total_final: number
  total_received: number
  pending_amount: number
  collection_rate: number
}

export function getPaymentAnalysis(params?: {
  start_date?: string
  end_date?: string
  keyword?: string
}) {
  return api.get('/analytics/payment/analysis', { params })
}

export interface InvoiceStatusStats {
  total: number
  paid: number
  unpaid: number
  overdue: number
}

export function getInvoiceStatusStats(params?: { start_date?: string; end_date?: string }) {
  return api.get('/analytics/payment/invoice-status', { params })
}

// ==================== 健康度分析 ====================

export interface HealthStats {
  total_customers: number
  healthy_count: number
  warning_count: number
  danger_count: number
  health_rate: number
}

export function getHealthStats() {
  return api.get('/analytics/health/stats')
}

export interface WarningCustomer {
  customer_id: number
  company_id: string
  customer_name: string
  total_amount: number
  real_amount: number
  bonus_amount: number
  manager_name: string
}

export function getWarningList(params?: { threshold?: number }) {
  return api.get('/analytics/health/warning-list', { params })
}

export interface InactiveCustomer {
  customer_id: number
  company_id: string
  customer_name: string
  manager_name: string
  days: number
  days_inactive?: number
}

export function getInactiveList(params?: { days?: number }) {
  return api.get('/analytics/health/inactive-list', { params })
}

// ==================== 画像分析 ====================

export interface IndustryDistributionItem {
  industry_type: string
  customer_count: number
  percentage: number
}

export function getIndustryDistribution(params?: { force_refresh?: boolean }) {
  return api.get('/analytics/profile/industry', { params })
}

export interface ScaleLevelStatsItem {
  scale_level: string
  customer_count: number
  percentage: number
}

export function getScaleStats(params?: { force_refresh?: boolean }) {
  return api.get('/analytics/profile/scale', { params })
}

export interface ConsumeLevelStatsItem {
  consume_level: string
  customer_count: number
  percentage: number
}

export function getConsumeLevelStats(params?: { force_refresh?: boolean }) {
  return api.get('/analytics/profile/consume-level', { params })
}

export interface RealEstateStats {
  is_real_estate: boolean
  customer_count: number
  percentage: number
}

export function getRealEstateStats(params?: { force_refresh?: boolean }) {
  return api.get('/analytics/profile/real-estate', { params })
}

export interface RealEstateIndustryItem {
  industry_type: string
  customer_count: number
  percentage: number
}

export function getRealEstateIndustryStats(params?: { force_refresh?: boolean }) {
  return api.get('/analytics/profile/real-estate-industry', { params })
}

// ==================== 预测回款 ====================

export interface PaymentPrediction {
  customer_id: number
  customer_name: string
  company_id: string
  month: string
  predicted_amount: number
  confidence: number
}

export function getMonthlyPrediction(params?: {
  year?: number
  month?: number
  keyword?: string
}) {
  return api.get('/analytics/prediction/monthly', { params })
}

// ==================== 首页仪表盘 ====================

export interface DashboardStats {
  total_customers: number
  active_customers: number
  total_revenue: number
  monthly_growth: number
}

export function getDashboardStats() {
  return api.get('/analytics/dashboard/stats')
}

export interface ChartTrendItem {
  month: string
  value: number
}

export interface DashboardChartData {
  revenue_trend: ChartTrendItem[]
  customer_growth: ChartTrendItem[]
}

export function getDashboardChartData(params?: { chart_type?: string; months?: number }) {
  return api.get('/analytics/dashboard/chart-data', { params })
}

// ==================== 首页仪表盘扩展 ====================

// 模拟待办事项接口（后端暂未实现）
export interface PendingTask {
  id: number
  title: string
  type: 'warning' | 'info' | 'success'
  created_at: string
  status: 'pending' | 'completed'
}

export interface PendingTasksResponse {
  tasks: PendingTask[]
  total: number
}

export function getPendingTasks() {
  // 模拟数据，后端接口暂未实现
  return Promise.resolve({
    tasks: [
      {
        id: 1,
        title: '3 个客户余额不足',
        type: 'warning',
        created_at: new Date().toISOString(),
        status: 'pending',
      },
      {
        id: 2,
        title: '5 个客户即将到期',
        type: 'info',
        created_at: new Date().toISOString(),
        status: 'pending',
      },
      {
        id: 3,
        title: '2 个结算单待确认',
        type: 'info',
        created_at: new Date().toISOString(),
        status: 'pending',
      },
    ],
    total: 3,
  })
}

// ==================== 客户健康度 ====================

export interface CustomerHealthScore {
  customer_id: number
  customer_name: string
  score: number
  health_score: number
  health_level: string
  level: string
  risk_factors: string[]
  suggestions: string[]
}

export function getCustomerHealthScore(customerId: number) {
  return api.get(`/analytics/health/customers/${customerId}/score`)
}
