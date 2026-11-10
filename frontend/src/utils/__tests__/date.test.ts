import { describe, expect, it } from 'vitest'
import { toLocalDateStr } from '../date'

/**
 * toLocalDateStr（2026-11-10 新增）：本地日期分量格式化。
 *
 * 修复前用 `d.toISOString().split('T')[0]`——toISOString 返回 UTC 渲染串，
 * 本地 00:00 的 Date 渲染成前一天 16:00Z，取到的日期比用户选的少一天；
 * 后端按 CST 语义解释该串，快捷范围整体偏移（余额「本月」实测错 3 天）。
 * 这些用例钉住「本地 00:00 / UTC 边界」两个易错场景。
 */
describe('toLocalDateStr', () => {
  it('本地零点渲染当天（toISOString 会返回前一天）', () => {
    // CST 2026-11-01 00:00 = UTC 2026-10-31 16:00
    const d = new Date(2026, 10, 1, 0, 0, 0)
    expect(toLocalDateStr(d)).toBe('2026-11-01')
    // 对照：bug 版行为
    expect(d.toISOString().split('T')[0]).toBe('2026-10-31')
  })

  it('月末 23:59 附近渲染当天', () => {
    const d = new Date(2026, 10, 30, 23, 59, 59)
    expect(toLocalDateStr(d)).toBe('2026-11-30')
  })

  it('UTC 跨日后不久的本地时刻仍属当天', () => {
    // CST 00:30 = UTC 前一天 16:30；ISO 串日期是前一天，本地分量仍是当天
    const d = new Date('2026-11-09T16:30:00Z')
    expect(toLocalDateStr(d)).toBe('2026-11-10')
    expect(d.toISOString().split('T')[0]).toBe('2026-11-09')
  })

  it('补零：单位数月/日', () => {
    expect(toLocalDateStr(new Date(2026, 0, 5, 12, 0, 0))).toBe('2026-01-05')
  })
})
