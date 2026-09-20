/**
 * 客户管理模块共享选项常量
 *
 * 所有客户表单（新增、编辑、批量编辑）和详情展示页
 * 统一使用这些常量，确保选项值域一致。
 */

/** 账号类型选项 */
export const ACCOUNT_TYPE_OPTIONS = [
  { label: '正式账号', value: '正式账号' },
  { label: '客户测试账号', value: '客户测试账号' },
  { label: '内部账号', value: '内部账号' },
] as const

/** 结算方式选项 */
export const SETTLEMENT_TYPE_OPTIONS = [
  { label: '预付费', value: 'prepaid' },
  { label: '后付费', value: 'postpaid' },
] as const

/** 结算周期选项 */
export const SETTLEMENT_CYCLE_OPTIONS = [
  { label: '日结', value: 'daily' },
  { label: '周结', value: 'weekly' },
  { label: '月结', value: 'monthly' },
  { label: '季结', value: 'quarterly' },
  { label: '年结', value: 'yearly' },
] as const

/** 结算周期值 → 中文显示 映射 */
export const SETTLEMENT_CYCLE_MAP: Record<string, string> = {
  daily: '日结',
  weekly: '周结',
  monthly: '月结',
  quarterly: '季结',
  yearly: '年结',
}

/** 结算方式值 → 中文显示 映射 */
export const SETTLEMENT_TYPE_MAP: Record<string, string> = {
  prepaid: '预付费',
  postpaid: '后付费',
}

/** 价格策略选项 */
export const PRICE_POLICY_OPTIONS = [
  { label: '定价', value: 'pricing' },
  { label: '阶梯', value: 'tiered' },
  { label: '包年', value: 'yearly' },
] as const

/** 规模等级选项 */
export const SCALE_LEVEL_OPTIONS = [
  { label: 'S - 超大规模 (5000人)', value: 'S' },
  { label: 'A - 大规模 (2000人)', value: 'A' },
  { label: 'B - 中大规模 (1000人)', value: 'B' },
  { label: 'C - 中等规模 (500人)', value: 'C' },
  { label: 'D - 小规模 (100人)', value: 'D' },
  { label: 'E - 微型 (<100人)', value: 'E' },
] as const

/** 消费等级选项 */
export const CONSUME_LEVEL_OPTIONS = [
  { label: 'C1 - 100万', value: 'C1' },
  { label: 'C2 - 50万', value: 'C2' },
  { label: 'C3 - 25万', value: 'C3' },
  { label: 'C4 - 12万', value: 'C4' },
  { label: 'C5 - 6万', value: 'C5' },
  { label: 'C6 - 6万以下', value: 'C6' },
] as const

/** 结算单状态选项（含多角色协作流程） */
export const INVOICE_STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '待运营经理确认', value: 'pending_ops' },
  { label: '待销售经理确认', value: 'pending_sales' },
  { label: '待客户确认', value: 'pending_customer' },
  { label: '客户已确认', value: 'customer_confirmed' },
  { label: '已付款', value: 'paid' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'cancelled' },
] as const

/** 结算单状态值 → 中文显示 映射 */
export const INVOICE_STATUS_MAP: Record<string, string> = {
  draft: '草稿',
  pending_ops: '待运营经理确认',
  pending_sales: '待销售经理确认',
  pending_customer: '待客户确认',
  customer_confirmed: '客户已确认',
  paid: '已付款',
  completed: '已完成',
  cancelled: '已取消',
}

/** 结算单状态值 → 标签 CSS 类 映射 */
export const INVOICE_STATUS_CLASS_MAP: Record<string, string> = {
  draft: 'gray',
  pending_ops: 'amber',
  pending_sales: 'amber',
  pending_customer: 'orange',
  customer_confirmed: 'blue',
  paid: 'green',
  completed: 'green',
  cancelled: 'red',
}

/** 布尔筛选项（是/否，供 FilterDropdown 使用，值为 string） */
export const BOOLEAN_FILTER_OPTIONS = [
  { label: '是', value: 'true' },
  { label: '否', value: 'false' },
] as const
