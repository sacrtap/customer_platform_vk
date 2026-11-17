import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import SyncLogDetailDrawer from '@/views/system/components/SyncLogDetailDrawer.vue'

// Arco 响应式组件依赖 matchMedia，jsdom 不实现
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

enableAutoUnmount(afterEach)

// 覆盖四类明细形态：费用计算（内部客户）/ 订单未匹配（外部）/ 订单保存失败（仅外部公司名）/ 任务级（无客户）
const detailRows = [
  {
    id: 1,
    sync_date: '2026-11-17',
    level: 'info',
    category: 'cost_calc',
    message: '费用计算完成',
    customer_id: 507,
    customer_name: '广州某某装饰',
    external_customer_id: null,
    company_name: null,
    order_code: null,
    record_count: 1,
    is_settlement_enabled: true,
    account_type: '正式账号',
    company_id: 507,
    created_at: '2026-11-17T10:00:00',
  },
  {
    id: 2,
    sync_date: '2026-11-17',
    level: 'warning',
    category: 'order_match',
    message: '订单未匹配到内部客户',
    customer_id: null,
    customer_name: null,
    external_customer_id: '999888',
    company_name: '外部未匹配公司',
    order_code: 'ORD-1',
    record_count: 1,
    is_settlement_enabled: null,
    account_type: null,
    company_id: null,
    created_at: '2026-11-17T10:01:00',
  },
  {
    id: 3,
    sync_date: '2026-11-17',
    level: 'error',
    category: 'order_save',
    message: '订单处理失败',
    customer_id: null,
    customer_name: null,
    external_customer_id: null,
    company_name: '保存失败公司',
    order_code: 'ORD-2',
    record_count: 1,
    is_settlement_enabled: null,
    account_type: null,
    company_id: null,
    created_at: '2026-11-17T10:02:00',
  },
  {
    id: 4,
    sync_date: '2026-11-17',
    level: 'info',
    category: 'system',
    message: '任务完成',
    customer_id: null,
    customer_name: null,
    external_customer_id: null,
    company_name: null,
    order_code: null,
    record_count: 1,
    is_settlement_enabled: null,
    account_type: null,
    company_id: null,
    created_at: '2026-11-17T10:03:00',
  },
]

vi.mock('@/api/syncTasks', () => ({
  getSyncTaskDetails: vi.fn(async () => ({
    summary: { info_count: 2, warning_count: 1, error_count: 1, total_count: 4 },
    list: detailRows,
    pagination: { page: 1, page_size: 20, total: 4 },
  })),
}))

function mountDrawer() {
  return mount(SyncLogDetailDrawer, {
    props: {
      visible: false,
      task: {
        task_id: 'abcdef12-0000-0000-0000-000000000000',
        status: 'completed',
        sync_mode: 'force_overwrite',
        start_date: '2026-11-17',
        end_date: '2026-11-17',
        operator_name: '测试',
      } as never,
    },
    global: {
      plugins: [ArcoVue],
      stubs: { 'a-drawer': { template: '<div><slot /></div>' } },
    },
  })
}

describe('执行信息抽屉 内部/外部分列', () => {
  it('公司ID列展示内部ID+内部客户名，外部列展示外部ID+外部公司名', async () => {
    const wrapper = mountDrawer()
    await wrapper.setProps({ visible: true })
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(4)

    // 列序：级别/日期/类别/公司ID(3)/外部(4)
    const cells = rows.map((r) => r.findAll('td').map((td) => td.text().trim()))

    // 费用计算：内部客户 ID 与名称同格；无外部信息
    expect(cells[0][3]).toBe('507 · 广州某某装饰')
    expect(cells[0][4]).toBe('-')
    // 未匹配订单：内部列为 -，外部 ID 与外部公司名同格
    expect(cells[1][3]).toBe('-')
    expect(cells[1][4]).toBe('999888 · 外部未匹配公司')
    // 保存失败：无外部 ID，外部列只显示外部公司名
    expect(cells[2][3]).toBe('-')
    expect(cells[2][4]).toBe('保存失败公司')
    // 任务级：两列均无值
    expect(cells[3][3]).toBe('-')
    expect(cells[3][4]).toBe('-')

    // 内部名称不得落到外部列，外部名称不得落到公司ID列
    for (const cell of cells) {
      expect(cell[3]).not.toContain('外部未匹配公司')
      expect(cell[4]).not.toContain('广州某某装饰')
    }
  })
})
