import { describe, it, expect } from 'vitest'
import { mergePreviewCustomer } from '../mergePreviewCustomer'
import type { Customer, CustomerDetail } from '@/types'
import { formatCurrency } from '@/utils/formatters'

const listRow = {
  id: 7,
  company_id: 1007,
  name: '乐有家',
  balance: 888.8,
  usage_30d_amount: 120,
  health: 'healthy',
  erp_system: null,
} as unknown as Customer

const detail = {
  ...listRow,
  erp_system: 'kingdee',
  // 详情接口 balance 是余额明细对象，与列表的数值形状不同
  balance: {
    total_amount: 1234.56,
    real_amount: 1000,
    bonus_amount: 234.56,
    used_total: 0,
    used_real: 0,
    used_bonus: 0,
  },
} as unknown as CustomerDetail

describe('mergePreviewCustomer', () => {
  it('用详情余额明细的 total_amount 生成数值型余额，避免 ¥NaN', () => {
    const merged = mergePreviewCustomer(listRow, detail)
    expect(typeof merged.balance).toBe('number')
    expect(merged.balance).toBe(1234.56)
    expect(formatCurrency(merged.balance)).toBe('¥1,234.56')
  })

  it('详情基础字段覆盖列表，列表独有指标保留', () => {
    const merged = mergePreviewCustomer(listRow, detail)
    expect(merged.erp_system).toBe('kingdee')
    expect(merged.usage_30d_amount).toBe(120)
    expect(merged.health).toBe('healthy')
  })

  it('详情无余额明细时回退列表余额；两者都无则为 null', () => {
    const merged = mergePreviewCustomer(listRow, { ...detail, balance: null })
    expect(merged.balance).toBe(888.8)
    expect(mergePreviewCustomer(null, { ...detail, balance: null }).balance).toBeNull()
  })
})
