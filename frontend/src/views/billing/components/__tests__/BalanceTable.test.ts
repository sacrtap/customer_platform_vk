import { describe, it, expect, afterEach } from 'vitest'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import BalanceTable from '@/views/billing/components/BalanceTable.vue'
import type { Balance } from '@/api/billing'

// 避免挂载的 Arco 组件（Tooltip 等）在测试环境销毁后仍残留 requestAnimationFrame，
// 触发 jsdom「Cannot read properties of null (reading '_location')」未处理异常
enableAutoUnmount(afterEach)

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

// a-table 排序入口：点击表头单元格（.arco-table-cell）而非 th 本身
const sortableTh = (wrapper: VueWrapper, title: string) =>
  wrapper.findAll('.arco-table-th').find((h) => h.text().includes(title))

// 统一挂载：a-table 需要 Arco 插件注册（原裸 <table> 实现不需要）
const mountTable = (props: {
  balances: Balance[]
  loading: boolean
  pagination: { current: number; pageSize: number; total: number }
  can: (permission: string) => boolean
}) => mount(BalanceTable, { props, global: { plugins: [ArcoVue] } })

describe('BalanceTable - 排序', () => {
  it('渲染所有可排序列头', () => {
    const wrapper = mountTable(defaultProps)
    const ths = wrapper.findAll('.arco-table-th')
    const titles = ths.map((h) => h.text())
    // company_id, customer_name, total_amount, burn_down, used_total, last_recharge_at
    expect(titles).toContain('客户ID')
    expect(titles).toContain('客户名称')
    expect(titles).toContain('余额')
    expect(titles).toContain('余额燃尽')
    expect(titles).toContain('已消耗')
    expect(titles).toContain('最新充值')
  })

  it('不可排序的列头没有 sorter 图标', () => {
    const wrapper = mountTable(defaultProps)
    const industryTh = sortableTh(wrapper, '行业')!
    // 行业列未配 sortable → 无 sorter 交互元素
    expect(industryTh.find('.arco-table-sorter').exists()).toBe(false)
  })

  it('可排序列头有 sorter 图标', () => {
    const wrapper = mountTable(defaultProps)
    expect(sortableTh(wrapper, '余额')!.find('.arco-table-sorter').exists()).toBe(true)
  })

  it('第一次点击排序列头时，emit sortChange 事件并设置为升序', async () => {
    const wrapper = mountTable(defaultProps)
    await sortableTh(wrapper, '余额')!.find('.arco-table-cell').trigger('click')

    const sortEvents = wrapper.emitted('sortChange')
    expect(sortEvents).toBeTruthy()
    expect(sortEvents![0]).toEqual(['total_amount', 'ascend'])
  })

  it('第二次点击同一列头时，切换为降序', async () => {
    const wrapper = mountTable(defaultProps)
    const cell = sortableTh(wrapper, '余额')!.find('.arco-table-cell')

    await cell.trigger('click')
    expect(wrapper.emitted('sortChange')![0]).toEqual(['total_amount', 'ascend'])

    await cell.trigger('click')
    expect(wrapper.emitted('sortChange')![1]).toEqual(['total_amount', 'descend'])
  })

  it('第三次点击同一列头时，清除排序（emit 空字符串）', async () => {
    const wrapper = mountTable(defaultProps)
    const cell = sortableTh(wrapper, '余额')!.find('.arco-table-cell')

    await cell.trigger('click')
    await cell.trigger('click')
    await cell.trigger('click')

    const sortEvents = wrapper.emitted('sortChange')
    expect(sortEvents).toBeTruthy()
    // 关键：清除排序时 emit ('', '') 而不是 ('total_amount', '')
    expect(sortEvents![2]).toEqual(['', ''])
  })

  it('切换到不同列时，新列设为升序', async () => {
    const wrapper = mountTable(defaultProps)

    await sortableTh(wrapper, '余额')!.find('.arco-table-cell').trigger('click')
    expect(wrapper.emitted('sortChange')![0]).toEqual(['total_amount', 'ascend'])

    await sortableTh(wrapper, '已消耗')!.find('.arco-table-cell').trigger('click')
    expect(wrapper.emitted('sortChange')![1]).toEqual(['used_total', 'ascend'])
  })

  it('所有可排序列都能正确 emit 排序事件', async () => {
    const wrapper = mountTable(defaultProps)

    const expectedColumns = [
      { title: '客户ID', key: 'company_id' },
      { title: '客户名称', key: 'customer_name' },
      { title: '余额', key: 'total_amount' },
      { title: '余额燃尽', key: 'days_remaining' },
      { title: '已消耗', key: 'used_total' },
      { title: '最新充值', key: 'last_recharge_at' },
    ]

    for (const col of expectedColumns) {
      await sortableTh(wrapper, col.title)!.find('.arco-table-cell').trigger('click')
      const events = wrapper.emitted('sortChange')
      const lastEvent = events![events!.length - 1]
      expect(lastEvent[0]).toBe(col.key)
      expect(lastEvent[1]).toBe('ascend')
    }
  })
})

describe('BalanceTable - 余额展示', () => {
  const rowOf = (wrapper: VueWrapper, index: number) =>
    wrapper.findAll('tbody .arco-table-tr')[index]

  it('客户ID 列只展示 company_id，与客户管理页取值一致（不回退 customer_id）', () => {
    const wrapper = mountTable(defaultProps)

    // company_id 有值的行显示 company_id
    expect(rowOf(wrapper, 0).find('.cust-id').text()).toBe('1001')
    // company_id 为空的行显示空（而非回退显示 customer_id 105）
    expect(rowOf(wrapper, 4).find('.cust-id').text()).toBe('')
  })

  it('负余额标记为欠费，零余额保持中性', () => {
    const wrapper = mountTable(defaultProps)

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
    const wrapper = mountTable(defaultProps)

    expect(rowOf(wrapper, 2).find('.never-recharge').text()).toBe('从未充值')
    expect(rowOf(wrapper, 0).find('.never-recharge').exists()).toBe(false)
  })

  it('余额燃尽列 Hover tooltip 使用 Arco a-tooltip 承载多行明细，而非原生 title', () => {
    const wrapper = mountTable(defaultProps)
    // 第 1 行 days_remaining=15，预付费且有消费数据 → 渲染油表单元格
    const cell = rowOf(wrapper, 0).find('.burn-cell')

    expect(cell.exists()).toBe(true)
    // 不应再使用浏览器原生 title 提示
    expect(cell.attributes('title')).toBeUndefined()
    expect(cell.attributes('data-tooltip')).toBeUndefined()

    // tooltip 内容为多段明细，用换行分隔（a-tooltip content 由 getBurnTooltip 生成）
    const tip = wrapper
      .findAllComponents({ name: 'Tooltip' })
      .find((t) => String(t.props('content') ?? '').includes('预计可支撑 15 天'))
    expect(tip).toBeTruthy()
    const content = String(tip!.props('content'))
    expect(content).toContain('日均消耗')
    expect(content).toContain('30 天内有 18 天消费记录')
    expect(content).toContain('当前余额')
    expect(content).toContain('预计可支撑 15 天')
    expect(content).toContain('\n')
  })

  it('包年客户「已消耗」列展示套餐内累计消耗（实时口径），非包年仍展示 used_total', () => {
    const packageRow: Balance = {
      id: 9,
      customer_id: 109,
      company_id: 1009,
      customer_name: '包年客户',
      industry_type: '房产经纪',
      total_amount: 90000,
      real_amount: 0,
      bonus_amount: 0,
      used_total: 0, // 包年 used_total 通常为 0（不走结算单累计）
      used_real: 0,
      used_bonus: 0,
      last_recharge_at: undefined,
      daily_avg_cost: null,
      consumption_days: 0,
      days_remaining: 45,
      is_package: true,
      package_expired: false,
      package_remaining_amount: 90000,
      package_consumed_amount: 30000, // 套餐内累计消耗（实时）
    }
    const wrapper = mountTable({ ...defaultProps, balances: [...mockBalances, packageRow] })
    const row = rowOf(wrapper, mockBalances.length)

    // 已消耗列展示 package_consumed_amount（30000）而非 used_total（0）
    expect(row.find('td').exists()).toBe(true)
    expect(row.text()).toContain('30,000')
    expect(row.find('.used-package').text()).toContain('套餐内累计消耗')
    // 包年不展示「实/赠」消耗拆分
    expect(row.find('.used-real').exists()).toBe(false)

    // tooltip 说明为实时口径、不依赖结算单
    const tip = wrapper
      .findAllComponents({ name: 'Tooltip' })
      .find((t) => String(t.props('content') ?? '').includes('套餐内累计消耗'))
    expect(tip).toBeTruthy()
    expect(String(tip!.props('content'))).toContain('不依赖结算单')
  })

  it('过期包年客户「已消耗」回退展示 used_total（package_consumed_amount 为 null）', () => {
    const expiredRow: Balance = {
      id: 10,
      customer_id: 110,
      company_id: 1010,
      customer_name: '过期包年客户',
      industry_type: '房产经纪',
      total_amount: 0,
      real_amount: 0,
      bonus_amount: 0,
      used_total: 12345,
      used_real: 12345,
      used_bonus: 0,
      last_recharge_at: undefined,
      daily_avg_cost: null,
      consumption_days: 0,
      days_remaining: 0,
      is_package: true,
      package_expired: true,
      package_remaining_amount: 0,
      package_consumed_amount: null,
    }
    const wrapper = mountTable({ ...defaultProps, balances: [expiredRow] })
    const row = rowOf(wrapper, 0)

    // 回退展示 CustomerBalance.used_total，且保留「实/赠」拆分
    expect(row.text()).toContain('12,345')
    expect(row.find('.used-real').exists()).toBe(true)
    expect(row.find('.used-package').exists()).toBe(false)
  })

  it('操作列按钮为充值/记录/重算', () => {
    const wrapper = mountTable(defaultProps)
    // 操作列为固定右侧列，按钮在 #action slot 内
    const actionCell = rowOf(wrapper, 0).findAll('.arco-table-td').at(-1)!
    const labels = actionCell.findAll('button').map((b) => b.text())

    expect(labels).toEqual(['充值', '记录', '重算'])
  })

  it('操作列固定右侧（fixed-right 类 + 位于最后一列）', () => {
    const wrapper = mountTable(defaultProps)
    const ths = wrapper.findAll('.arco-table-th')
    const lastTh = ths[ths.length - 1]
    expect(lastTh.text()).toContain('操作')
    expect(lastTh.classes()).toContain('arco-table-col-fixed-right')
  })

  it('即将耗尽（≤7天）行加 row-warning，8-30 天加 row-warn', () => {
    const wrapper = mountTable(defaultProps)
    // 第 2 行 days_remaining=6 → 红色高亮
    expect(rowOf(wrapper, 1).classes()).toContain('row-warning')
    // 第 1 行 days_remaining=15 → 黄色高亮
    expect(rowOf(wrapper, 0).classes()).toContain('row-warn')
    // 第 3 行无消耗数据 → 无高亮
    const plain = rowOf(wrapper, 2).classes()
    expect(plain).not.toContain('row-warning')
    expect(plain).not.toContain('row-warn')
  })

  it('操作列按钮点击 emit 对应事件', async () => {
    const wrapper = mountTable(defaultProps)
    const actionCell = rowOf(wrapper, 0).findAll('.arco-table-td').at(-1)!
    const buttons = actionCell.findAll('button')

    await buttons[0].trigger('click')
    expect(wrapper.emitted('recharge')).toBeTruthy()

    await buttons[1].trigger('click')
    expect(wrapper.emitted('viewRecords')).toBeTruthy()

    await buttons[2].trigger('click')
    expect(wrapper.emitted('recalculate')).toBeTruthy()
  })
})
