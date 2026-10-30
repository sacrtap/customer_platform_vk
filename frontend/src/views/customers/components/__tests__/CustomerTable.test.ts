import { describe, it, expect, afterEach } from 'vitest'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import CustomerTable from '../CustomerTable.vue'
import type { Customer } from '@/types'

// 避免挂载的 Arco 组件（Tooltip 等）在测试环境销毁后仍残留 requestAnimationFrame，
// 触发 jsdom「Cannot read properties of null (reading '_location')」未处理异常
enableAutoUnmount(afterEach)

// 测试数据：覆盖模板渲染所需字段（company_id/name/balance/industry 等）
const mockCustomers: Customer[] = [
  {
    id: 1,
    company_id: 1001,
    name: '客户A',
    account_type: '正式账号',
    industry: '房产经纪',
    price_policy: null,
    manager_id: null,
    settlement_cycle: null,
    settlement_type: 'prepaid',
    is_key_customer: false,
    email: null,
    created_at: '2026-07-01T10:00:00',
    updated_at: '2026-07-01T10:00:00',
    erp_system: null,
    first_payment_date: null,
    onboarding_date: null,
    sales_manager_id: null,
    cooperation_status: null,
    is_settlement_enabled: true,
    require_reconciliation: false,
    is_disabled: false,
    notes: null,
    is_real_estate: false,
    industry_type_id: 1,
    scale_level: 'A',
    consume_level: '高',
    balance: 50000,
    usage_30d: 60,
    usage_30d_amount: 12000,
    health: 'healthy',
  },
  {
    id: 2,
    company_id: 1002,
    name: '客户B',
    account_type: '正式账号',
    industry: '房产ERP',
    price_policy: null,
    manager_id: null,
    settlement_cycle: null,
    settlement_type: 'postpaid',
    is_key_customer: true,
    email: null,
    created_at: '2026-07-02T10:00:00',
    updated_at: '2026-07-02T10:00:00',
    erp_system: null,
    first_payment_date: null,
    onboarding_date: null,
    sales_manager_id: null,
    cooperation_status: null,
    is_settlement_enabled: true,
    require_reconciliation: false,
    is_disabled: false,
    notes: null,
    is_real_estate: false,
    industry_type_id: 2,
    scale_level: 'B',
    consume_level: '中',
    balance: 20000,
    usage_30d: 30,
    usage_30d_amount: 6000,
    health: 'warning',
  },
]

const defaultProps = {
  customers: mockCustomers,
  loading: false,
  pagination: { current: 1, pageSize: 20, total: 2 },
  managers: [],
  managersLoading: false,
  selectedCustomerIds: [],
  can: () => true,
}

// a-table 排序入口：点击表头单元格（.arco-table-cell）而非 th 本身
const sortableTh = (wrapper: VueWrapper, title: string) =>
  wrapper.findAll('.arco-table-th').find((h) => h.text().includes(title))

// 统一挂载：a-table 需要 Arco 插件注册
const mountTable = (props: typeof defaultProps = defaultProps) =>
  mount(CustomerTable, { props, global: { plugins: [ArcoVue] } })

describe('CustomerTable - 排序', () => {
  it('可排序列头（客户ID）有 sorter 图标', () => {
    const wrapper = mountTable()
    expect(sortableTh(wrapper, '客户ID')!.find('.arco-table-sorter').exists()).toBe(true)
  })

  it('第一次点击表头 emit 升序 asc（而非 Arco 原始词 ascend）', async () => {
    const wrapper = mountTable()
    await sortableTh(wrapper, '客户ID')!.find('.arco-table-cell').trigger('click')

    const sortEvents = wrapper.emitted('sortChange')
    expect(sortEvents).toBeTruthy()
    // 关键回归点：必须映射为后端词表 'asc'，而非 Arco 的 'ascend'
    expect(sortEvents![0]).toEqual(['company_id', 'asc'])
  })

  it('第二次点击同一列表头切换为降序 desc', async () => {
    const wrapper = mountTable()
    const cell = sortableTh(wrapper, '客户ID')!.find('.arco-table-cell')

    await cell.trigger('click')
    await cell.trigger('click')

    const events = wrapper.emitted('sortChange')
    expect(events![0]).toEqual(['company_id', 'asc'])
    expect(events![1]).toEqual(['company_id', 'desc'])
  })

  it('第三次点击同一列表头清除排序，emit 空方向恢复默认', async () => {
    const wrapper = mountTable()
    const cell = sortableTh(wrapper, '客户ID')!.find('.arco-table-cell')

    await cell.trigger('click')
    await cell.trigger('click')
    await cell.trigger('click')

    const events = wrapper.emitted('sortChange')
    expect(events).toBeTruthy()
    // 清除排序：emit ('', '')，触发 handleSort 恢复默认排序
    expect(events![2]).toEqual(['', ''])
  })

  it('切换到不同列时，新列 emit 升序 asc', async () => {
    const wrapper = mountTable()

    await sortableTh(wrapper, '客户ID')!.find('.arco-table-cell').trigger('click')
    expect(wrapper.emitted('sortChange')![0]).toEqual(['company_id', 'asc'])

    await sortableTh(wrapper, '余额')!.find('.arco-table-cell').trigger('click')
    expect(wrapper.emitted('sortChange')![1]).toEqual(['balance', 'asc'])
  })
})
