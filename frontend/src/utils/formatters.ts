export const formatCurrency = (
  amount: number | null | undefined,
  options?: Intl.NumberFormatOptions
): string => {
  if (amount == null) return '-'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    ...options,
  }).format(amount)
}

export const formatCurrencyWan = (amount: number | null | undefined): string => {
  if (amount == null) return '-'
  const wan = amount / 10000
  return `¥${wan.toFixed(1)}万`
}

/**
 * 将后端返回的时间字符串转换为 Date 对象。
 *
 * 后端时间字段有两种来源：
 * 1. 数据库 func.now() 生成的 DateTime 列（如 created_at）—— naive local datetime
 * 2. Python datetime.now().isoformat() 写入的 String 列（如 ops_confirmed_at）—— naive local datetime
 *
 * 两者都是服务器本地时间（UTC+8）且不带时区后缀。
 * new Date(dateStr) 会将不带时区后缀的字符串当作本地时间解析，这恰好是正确的。
 *
 * 如果后端将来改为返回 UTC 时间（带 'Z' 或 '±HH:MM' 后缀），
 * new Date() 也能正确解析并自动转换为浏览器本地时区。
 *
 * 因此这里直接交给 new Date() 解析，不做额外处理。
 */
export const toDate = (dateStr: string | null | undefined): Date | null => {
  if (!dateStr) return null
  return new Date(dateStr)
}

export const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-'
  const date = toDate(dateStr)
  if (!date) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

export const formatDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-'
  const date = toDate(dateStr)
  if (!date) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}

export const formatNumber = (num: number | null | undefined): string => {
  if (num == null) return '-'
  return new Intl.NumberFormat('zh-CN').format(num)
}

export const formatPercent = (value: number | null | undefined, decimals = 0): string => {
  if (value == null) return '-'
  return new Intl.NumberFormat('zh-CN', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value / 100)
}
