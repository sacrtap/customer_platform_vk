import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchToolbar from '@/views/customers/components/BatchToolbar.vue'

describe('BatchToolbar', () => {
  it('displays selected count', () => {
    const wrapper = mount(BatchToolbar, {
      props: { selectedCount: 5 },
    })
    expect(wrapper.text()).toContain('5')
  })

  it('renders batch action buttons', () => {
    const wrapper = mount(BatchToolbar, {
      props: { selectedCount: 3 },
    })
    expect(wrapper.text()).toContain('分配运营经理')
    expect(wrapper.text()).toContain('设置等级')
  })

  it('emits batch-action event', async () => {
    const wrapper = mount(BatchToolbar, {
      props: { selectedCount: 2 },
    })
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    expect(wrapper.emitted('batch-action')).toBeTruthy()
  })
})
