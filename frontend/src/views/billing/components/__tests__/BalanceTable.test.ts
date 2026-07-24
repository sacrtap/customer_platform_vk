import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BalanceTable from '@/views/billing/components/BalanceTable.vue'
import type { Balance } from '@/api/billing'

// 测试数据
const mockBalances: Balance[] = [
  {
    id: 1,
    customer_id: 101,
    company_id: 1001,
    customer_name: '客户A',
    industry_type: '房产经纪',
    total_amount: 50000,
    real_amount: 40000,
    bonus_amount: 10000,
    used_total: 20000,
    used_real: 15000,
    used_bonus: 5000,
    last_recharge_at: '2026-07-15T10:00:00',
  },
  {
    id: 2,
    customer_id: 102,
    company_id: 1002,
    customer_name: '客户B',
    industry_type: '房产ERP',
    total_amount: 5000,
    real_amount: 4000,
    bonus_amount: 1000,
    used_total: 30000,
    used_real: 25000,
    used_bonus: 5000,
    last_recharge_at: '2026-07-10T10:00:00',
  },
  {
    id: 3,
    customer_id: 103,
    company_id: 1003,
    customer_name: '客户C',
    industry_type: '房产平台',
    total_amount: 0,
    real_amount: 0,
    bonus_amount: 0,
    used_total: 50000,
    used_real: 45000,
    used_bonus: 5000,
    last_recharge_at: undefined,
  },
]

const defaultProps = {
  balances: mockBalances,
  loading: false,
  pagination: {
    current: 1,
    pageSize: 20,
    total: 3,
  },
  selectedIds: [] as number[],
  can: (_p: string) => true,
}

describe('BalanceTable - 排序', () => {
  it('渲染所有可排序列头', () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const sortableHeaders = wrapper.findAll('.th-sortable')
    // company_id, customer_name, total_amount, used_total, last_recharge_at
    expect(sortableHeaders).toHaveLength(5)
    const titles = sortableHeaders.map((h) => h.text())
    expect(titles).toContain('客户ID')
    expect(titles).toContain('客户名称')
    expect(titles).toContain('余额')
    expect(titles).toContain('已消耗')
    expect(titles).toContain('最新充值')
  })

  it('不可排序的列头没有 th-sortable 类', () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const allHeaders = wrapper.findAll('thead th')
    // 行业、趋势、预计耗尽 不可排序
    const nonSortableTexts = allHeaders
      .filter((h) => !h.classes().includes('th-sortable'))
      .map((h) => h.text())
    expect(nonSortableTexts).toContain('行业')
    expect(nonSortableTexts).toContain('趋势')
    expect(nonSortableTexts).toContain('预计耗尽')
  })

  it('第一次点击排序列头时，emit sortChange 事件并设置为升序', async () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    // 点击"余额"列头
    const balanceHeader = wrapper.findAll('.th-sortable').find((h) => h.text().includes('余额'))
    expect(balanceHeader).toBeTruthy()
    await balanceHeader!.trigger('click')

    const sortEvents = wrapper.emitted('sortChange')
    expect(sortEvents).toBeTruthy()
    expect(sortEvents![0]).toEqual(['total_amount', 'asc'])
  })

  it('第二次点击同一列头时，切换为降序', async () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const balanceHeader = wrapper.findAll('.th-sortable').find((h) => h.text().includes('余额'))!

    // 第一次点击：升序
    await balanceHeader.trigger('click')
    expect(wrapper.emitted('sortChange')![0]).toEqual(['total_amount', 'asc'])

    // 第二次点击：降序
    await balanceHeader.trigger('click')
    expect(wrapper.emitted('sortChange')![1]).toEqual(['total_amount', 'desc'])
  })

  it('第三次点击同一列头时，清除排序（emit 空字符串）', async () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const balanceHeader = wrapper.findAll('.th-sortable').find((h) => h.text().includes('余额'))!

    // 第一次：升序
    await balanceHeader.trigger('click')
    // 第二次：降序
    await balanceHeader.trigger('click')
    // 第三次：清除
    await balanceHeader.trigger('click')

    const sortEvents = wrapper.emitted('sortChange')
    expect(sortEvents).toBeTruthy()
    // 关键：清除排序时 emit ('', '') 而不是 ('total_amount', '')
    expect(sortEvents![2]).toEqual(['', ''])
  })

  it('切换到不同列时，新列设为升序', async () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const headers = wrapper.findAll('.th-sortable')
    const balanceHeader = headers.find((h) => h.text().includes('余额'))!
    const usedHeader = headers.find((h) => h.text().includes('已消耗'))!

    // 先点击余额列：升序
    await balanceHeader.trigger('click')
    expect(wrapper.emitted('sortChange')![0]).toEqual(['total_amount', 'asc'])

    // 再点击已消耗列：升序
    await usedHeader.trigger('click')
    expect(wrapper.emitted('sortChange')![1]).toEqual(['used_total', 'asc'])
  })

  it('排序时表头显示正确的 CSS 类（sort-asc / sort-desc）', async () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const balanceHeader = wrapper.findAll('.th-sortable').find((h) => h.text().includes('余额'))!

    // 初始：无排序类
    expect(balanceHeader.classes()).not.toContain('sort-asc')
    expect(balanceHeader.classes()).not.toContain('sort-desc')

    // 第一次点击：升序
    await balanceHeader.trigger('click')
    expect(balanceHeader.classes()).toContain('sort-asc')

    // 第二次点击：降序
    await balanceHeader.trigger('click')
    expect(balanceHeader.classes()).toContain('sort-desc')
    expect(balanceHeader.classes()).not.toContain('sort-asc')

    // 第三次点击：清除
    await balanceHeader.trigger('click')
    expect(balanceHeader.classes()).not.toContain('sort-asc')
    expect(balanceHeader.classes()).not.toContain('sort-desc')
  })

  it('所有可排序列都能正确 emit 排序事件', async () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const headers = wrapper.findAll('.th-sortable')

    const expectedColumns = [
      { title: '客户ID', key: 'company_id' },
      { title: '客户名称', key: 'customer_name' },
      { title: '余额', key: 'total_amount' },
      { title: '已消耗', key: 'used_total' },
      { title: '最新充值', key: 'last_recharge_at' },
    ]

    for (const col of expectedColumns) {
      const header = headers.find((h) => h.text().includes(col.title))
      expect(header).toBeTruthy()
      await header!.trigger('click')
      const events = wrapper.emitted('sortChange')
      const lastEvent = events![events!.length - 1]
      expect(lastEvent[0]).toBe(col.key)
      expect(lastEvent[1]).toBe('asc')
    }
  })
})
