import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FilterSection from '@/components/FilterSection.vue'

describe('FilterSection', () => {
  it('renders slot content', () => {
    const wrapper = mount(FilterSection, {
      slots: { default: '<div class="filter-content">筛选内容</div>' },
    })
    expect(wrapper.find('.filter-content').exists()).toBe(true)
  })
})
