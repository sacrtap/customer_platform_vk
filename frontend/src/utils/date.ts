/**
 * 将 Date 对象格式化为本地时区（CST）日期串 'YYYY-MM-DD'。
 *
 * 背景（2026-11-10 修复）：`date.toISOString()` 返回 UTC 渲染串——
 * 本地 00:00 的 Date 会渲染成前一天 16:00Z，split('T')[0] 取到前一天；
 * 而后端一律按 CST 语义解释日期串（local_date_range_to_utc 等）。
 * 凡用 toISOString 拼日期串传给后端的快捷筛选，区间整体偏移 1 天
 * （余额「本月」实测错 3 天）。本函数改用本地日期分量，无时区换算。
 *
 * 注意：不要"优化"回 toISOString——那是 bug，不是简写。
 */
export const toLocalDateStr = (d: Date): string => {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
