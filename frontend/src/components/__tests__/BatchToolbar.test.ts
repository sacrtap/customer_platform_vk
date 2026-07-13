import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchToolbar from '@/components/BatchToolbar.vue'

describe('BatchToolbar', () => {
  it('displays selected count', () => {
    const wrapper = mount(BatchToolbar, {
      props: { count: 5 },
    })
    expect(wrapper.text()).toContain('5')
  })

  it('renders action slot', () => {
    const wrapper = mount(BatchToolbar, {
      props: { count: 3 },
      slots: { default: '<button>批量编辑</button>' },
    })
    expect(wrapper.find('button').exists()).toBe(true)
  })
})
