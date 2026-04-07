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

export const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

export const formatDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
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
