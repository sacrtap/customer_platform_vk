import api from './index'

// ==================== 消耗分析 ====================

export interface ConsumptionTrendItem {
  year: number
  month: number
  period: string
  total_amount: number
}

export function getConsumptionTrend(params?: {
  start_date?: string
  end_date?: string
  customer_id?: number
}) {
  return api.get('/analytics/consumption/trend', { params })
}

export interface TopCustomer {
  customer_id: number
  company_id: string
  customer_name: string
  total_amount: number
}

export function getTopCustomers(params?: {
  start_date?: string
  end_date?: string
  limit?: number
}) {
  return api.get('/analytics/consumption/top', { params })
}

export interface DeviceDistributionItem {
  device_type: string
  total_quantity: number
  total_amount: number
}

export function getDeviceDistribution(params?: {
  start_date?: string
  end_date?: string
  customer_id?: number
}) {
  return api.get('/analytics/consumption/device-distribution', { params })
}

// ==================== 回款分析 ====================

export interface PaymentAnalysis {
  total_invoiced: number
  total_discount: number
  total_final: number
  total_paid: number
  completion_rate: number
  difference: number
}

export function getPaymentAnalysis(params?: {
  start_date?: string
  end_date?: string
  customer_id?: number
}) {
  return api.get('/analytics/payment/analysis', { params })
}

export interface InvoiceStatusStats {
  status: string
  count: number
  total_amount: number
}

export function getInvoiceStatusStats(params?: { start_date?: string; end_date?: string }) {
  return api.get('/analytics/payment/invoice-status', { params })
}

// ==================== 健康度分析 ====================

export interface HealthStats {
  total_customers: number
  active_customers: number
  inactive_customers: number
  warning_customers: number
  churn_risk_customers: number
  active_rate: number
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
}

export function getWarningList(params?: { threshold?: number }) {
  return api.get('/analytics/health/warning-list', { params })
}

export interface InactiveCustomer {
  customer_id: number
  company_id: string
  customer_name: string
  manager_id?: number
  manager_name: string
  days?: number
  days_inactive?: number
}

export function getInactiveList(params?: { days?: number }) {
  return api.get('/analytics/health/inactive-list', { params })
}

// ==================== 画像分析 ====================

export interface IndustryDistributionItem {
  industry: string
  count: number
  percentage: number
}

export function getIndustryDistribution() {
  return api.get('/analytics/profile/industry')
}

export interface LevelStatsItem {
  level: string
  count: number
  percentage: number
}

export function getLevelStats() {
  return api.get('/analytics/profile/level')
}

export interface ScaleLevelStatsItem {
  scale_level: string
  count: number
  percentage: number
}

export function getScaleStats() {
  return api.get('/analytics/profile/scale')
}

export interface ConsumeLevelStatsItem {
  consume_level: string
  count: number
  percentage: number
}

export function getConsumeLevelStats() {
  return api.get('/analytics/profile/consume-level')
}

export interface RealEstateStats {
  total_customers: number
  real_estate_customers: number
  non_real_estate_customers: number
  real_estate_percentage: number
}

export function getRealEstateStats() {
  return api.get('/analytics/profile/real-estate')
}

// ==================== 预测回款 ====================

export interface PaymentPrediction {
  customer_id: number
  company_id: string
  customer_name: string
  device_type: string
  quantity: number
  pricing_type: string
  predicted_amount: number
}

export function getMonthlyPrediction(params?: {
  year?: number
  month?: number
  customer_id?: number
}) {
  return api.get('/analytics/prediction/monthly', { params })
}

// ==================== 首页仪表盘 ====================

export interface DashboardStats {
  total_customers: number
  key_customers: number
  total_balance: number
  real_balance: number
  bonus_balance: number
  month_invoice_count: number
  pending_confirmation: number
  month_consumption: number
}

export function getDashboardStats() {
  return api.get('/analytics/dashboard/stats')
}

export interface ChartTrendItem {
  period: string
  invoiced: number
  paid: number
  completion_rate: number
}

export interface DashboardChartData {
  consumption_trend: ConsumptionTrendItem[]
  payment_trend: ChartTrendItem[]
}

export function getDashboardChartData(params?: { chart_type?: string; months?: number }) {
  // 使用模拟数据作为降级方案
  return new Promise((resolve) => {
    api
      .get('/analytics/dashboard/chart-data', { params })
      .then(resolve)
      .catch(() => {
        // 生成模拟数据
        const months = params?.months || 12
        const now = new Date()
        const consumption_trend: Array<{
          year: number
          month: number
          period: string
          total_amount: number
        }> = []

        for (let i = months - 1; i >= 0; i--) {
          const date = new Date(now.getFullYear(), now.getMonth() - i, 1)
          const baseAmount = 500000 + Math.random() * 500000
          consumption_trend.push({
            year: date.getFullYear(),
            month: date.getMonth() + 1,
            period: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`,
            total_amount: Math.round(baseAmount),
          })
        }

        const payment_trend = consumption_trend.map((item) => ({
          period: item.period,
          invoiced: Math.round(item.total_amount * 0.95),
          paid: Math.round(item.total_amount * 0.85),
          completion_rate: 0.89,
        }))

        resolve({
          data: { consumption_trend, payment_trend },
        })
      })
  })
}

// ==================== 首页仪表盘扩展 ====================

// 模拟待办事项接口（后端暂未实现）
export interface PendingTask {
  id: number
  title: string
  priority: 'high' | 'medium' | 'low'
  priority_text: string
  due_date: string
  created_at: string
}

export interface PendingTasksResponse {
  items: PendingTask[]
  total: number
}

export function getPendingTasks() {
  // 后端暂未实现，返回模拟数据
  return Promise.resolve({
    data: {
      items: [
        {
          id: 1,
          title: '确认待处理账单',
          priority: 'high',
          priority_text: '高',
          due_date: '今天 18:00 截止',
          created_at: '2026-04-06',
        },
        {
          id: 2,
          title: '跟进余额不足客户',
          priority: 'high',
          priority_text: '高',
          due_date: '3 个客户',
          created_at: '2026-04-05',
        },
        {
          id: 3,
          title: '审核减免申请',
          priority: 'medium',
          priority_text: '中',
          due_date: '明天截止',
          created_at: '2026-04-04',
        },
        {
          id: 4,
          title: '导出月度分析报告',
          priority: 'low',
          priority_text: '低',
          due_date: '本周五',
          created_at: '2026-04-03',
        },
      ],
      total: 4,
    },
  })
}
