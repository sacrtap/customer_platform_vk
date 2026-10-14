import { describe, it, expect, afterEach } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'
import CustomerBalanceTab from '@/views/customers/detail/CustomerBalanceTab.vue'
import type { Balance } from '@/types'

// 避免挂载的 Arco 组件在测试环境销毁后仍残留 requestAnimationFrame，
// 触发 jsdom「Cannot read properties of null (reading '_location')」未处理异常
enableAutoUnmount(afterEach)

const baseProps = {
  balanceTrend: [],
  balanceTrendLoading: false,
  shouldRenderBalanceTrend: false,
  balanceLoading: false,
}

const prepaidBalance: Balance = {
  id: 1,
  customer_id: 101,
  total_amount: 50000,
  real_amount: 40000,
  bonus_amount: 10000,
  used_total: 20000,
  used_real: 15000,
  used_bonus: 5000,
  created_at: '2026-07-01T00:00:00',
  updated_at: '2026-07-01T00:00:00',
  is_package: false,
}

const packageBalance: Balance = {
  id: 2,
  customer_id: 102,
  total_amount: 90000, // 后端已按套餐剩余额度覆盖
  real_amount: 0,
  bonus_amount: 0,
  used_total: 0,
  used_real: 0,
  used_bonus: 0,
  created_at: '2026-07-01T00:00:00',
  updated_at: '2026-07-01T00:00:00',
  is_package: true,
  package_expired: false,
  package_remaining_amount: 90000,
  package_remaining_count: 1000,
  package_is_unlimited: false,
  package_consumed_amount: 30000,
}

describe('CustomerBalanceTab - 余额口径', () => {
  it('非包年客户：展示总/实充/赠送/已消耗四卡片', () => {
    const wrapper = mount(CustomerBalanceTab, {
      props: { ...baseProps, balance: prepaidBalance },
    })
    const labels = wrapper.findAll('.balance-label').map((n) => n.text())
    expect(labels).toEqual(['总余额', '实充余额', '赠送余额', '已消耗'])
  })

  it('包年客户：展示套餐剩余额度/次数/套餐内累计消耗，不显示实充赠送', () => {
    const wrapper = mount(CustomerBalanceTab, {
      props: { ...baseProps, balance: packageBalance },
    })
    const labels = wrapper.findAll('.balance-label').map((n) => n.text())
    expect(labels).toEqual(['套餐剩余额度', '套餐剩余次数', '套餐内累计消耗', '已结算消耗'])
    const text = wrapper.text()
    // 90000 剩余额度、1000 次数、30000 累计消耗
    expect(text).toContain('90,000')
    expect(text).toContain('1,000')
    expect(text).toContain('30,000')
    // 包年不展示实充/赠送余额卡片
    expect(text).not.toContain('实充余额')
    expect(text).not.toContain('赠送余额')
  })

  it('不限量包年客户：剩余次数显示「不限量」', () => {
    const wrapper = mount(CustomerBalanceTab, {
      props: {
        ...baseProps,
        balance: {
          ...packageBalance,
          package_is_unlimited: true,
          package_remaining_count: null,
        },
      },
    })
    expect(wrapper.text()).toContain('不限量')
  })

  it('过期包年客户：显示「套餐已过期」标签', () => {
    const wrapper = mount(CustomerBalanceTab, {
      props: {
        ...baseProps,
        balance: { ...packageBalance, package_expired: true },
      },
    })
    expect(wrapper.find('.pkg-tag').exists()).toBe(true)
    expect(wrapper.find('.pkg-tag').text()).toBe('套餐已过期')
  })
})
