import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import QuickFilterTags from '@/components/QuickFilterTags.vue'

describe('QuickFilterTags', () => {
  const tags = [
    { label: '待确认', value: 'pending', count: 8 },
    { label: '逾期', value: 'overdue', count: 3 },
    { label: '本月新增', value: 'new', count: 12 },
  ]

  it('renders all tags with counts', () => {
    const wrapper = mount(QuickFilterTags, {
      props: { tags, modelValue: '' },
    })
    expect(wrapper.findAll('.quick-tag')).toHaveLength(3)
    expect(wrapper.text()).toContain('待确认')
    expect(wrapper.text()).toContain('8')
  })

  it('highlights active tag', () => {
    const wrapper = mount(QuickFilterTags, {
      props: { tags, modelValue: 'pending' },
    })
    expect(wrapper.find('.quick-tag.active').exists()).toBe(true)
  })

  it('emits update:modelValue on click', async () => {
    const wrapper = mount(QuickFilterTags, {
      props: { tags, modelValue: '' },
    })
    await wrapper.findAll('.quick-tag')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['overdue'])
  })
})
