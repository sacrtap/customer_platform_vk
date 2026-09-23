import { describe, it, expect } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
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
    daily_avg_cost: 3200.0,
    consumption_days: 18,
    days_remaining: 15,
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
    daily_avg_cost: 800.0,
    consumption_days: 25,
    days_remaining: 6,
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
    daily_avg_cost: null,
    consumption_days: 0,
    days_remaining: null,
  },
  {
    id: 4,
    customer_id: 104,
    company_id: 1004,
    customer_name: '客户D',
    industry_type: '房产经纪',
    total_amount: -1500,
    real_amount: -1500,
    bonus_amount: 0,
    used_total: 1500,
    used_real: 1500,
    used_bonus: 0,
    last_recharge_at: undefined,
    daily_avg_cost: null,
    consumption_days: 0,
    days_remaining: null,
  },
  {
    id: 5,
    customer_id: 105,
    company_id: undefined,
    customer_name: '客户E',
    industry_type: '房产经纪',
    total_amount: 0,
    real_amount: 0,
    bonus_amount: 0,
    used_total: 0,
    used_real: 0,
    used_bonus: 0,
    last_recharge_at: undefined,
    daily_avg_cost: null,
    consumption_days: 0,
    days_remaining: null,
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
  can: (_p: string) => true,
}

describe('BalanceTable - 排序', () => {
  it('渲染所有可排序列头', () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const sortableHeaders = wrapper.findAll('.th-sortable')
    // company_id, customer_name, total_amount, burn_down, used_total, last_recharge_at
    expect(sortableHeaders).toHaveLength(6)
    const titles = sortableHeaders.map((h) => h.text())
    expect(titles).toContain('客户ID')
    expect(titles).toContain('客户名称')
    expect(titles).toContain('余额')
    expect(titles).toContain('余额燃尽')
    expect(titles).toContain('已消耗')
    expect(titles).toContain('最新充值')
  })

  it('不可排序的列头没有 th-sortable 类', () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const allHeaders = wrapper.findAll('thead th')
    // 行业 不可排序
    const nonSortableTexts = allHeaders
      .filter((h) => !h.classes().includes('th-sortable'))
      .map((h) => h.text())
    expect(nonSortableTexts).toContain('行业')
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
      { title: '余额燃尽', key: 'days_remaining' },
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

describe('BalanceTable - 余额展示', () => {
  const rowOf = (wrapper: VueWrapper, index: number) => wrapper.findAll('tbody tr')[index]

  it('客户ID 列只展示 company_id，与客户管理页取值一致（不回退 customer_id）', () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })

    // company_id 有值的行显示 company_id
    expect(rowOf(wrapper, 0).find('.cust-id').text()).toBe('1001')
    // company_id 为空的行显示空（而非回退显示 customer_id 105）
    expect(rowOf(wrapper, 4).find('.cust-id').text()).toBe('')
  })

  it('负余额标记为欠费，零余额保持中性', () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })

    // 第 4 行余额 -1500（欠费）
    const debtRow = rowOf(wrapper, 3)
    expect(debtRow.find('.balance-amount b').classes()).toContain('danger')
    expect(debtRow.find('.tag.red').text()).toBe('欠费')

    // 第 3 行余额为 0，不标红也不加欠费标签
    const zeroRow = rowOf(wrapper, 2)
    expect(zeroRow.find('.balance-amount b').classes()).not.toContain('danger')
    expect(zeroRow.find('.tag.red').exists()).toBe(false)
  })

  it('未充值的客户显示「从未充值」', () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })

    expect(rowOf(wrapper, 2).find('.never-recharge').text()).toBe('从未充值')
    expect(rowOf(wrapper, 0).find('.never-recharge').exists()).toBe(false)
  })

  it('操作列按钮为充值/记录/重算', () => {
    const wrapper = mount(BalanceTable, { props: defaultProps })
    const labels = rowOf(wrapper, 0)
      .findAll('.td-actions button')
      .map((b) => b.text())

    expect(labels).toEqual(['充值', '记录', '重算'])
  })
})
