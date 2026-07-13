import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TableSection from '@/components/TableSection.vue'

describe('TableSection', () => {
  it('renders slot content', () => {
    const wrapper = mount(TableSection, {
      slots: { default: '<table><tbody><tr><td>测试</td></tr></tbody></table>' },
    })
    expect(wrapper.find('table').exists()).toBe(true)
  })
})
