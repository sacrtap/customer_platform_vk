import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChartCard from '@/components/ChartCard.vue'

describe('ChartCard', () => {
  it('renders title', () => {
    const wrapper = mount(ChartCard, {
      props: { title: '经营趋势' },
    })
    expect(wrapper.find('.section-title h2').text()).toBe('经营趋势')
  })

  it('renders actions slot', () => {
    const wrapper = mount(ChartCard, {
      props: { title: '测试' },
      slots: { actions: '<button>导出</button>' },
    })
    expect(wrapper.find('.section-title .actions button').exists()).toBe(true)
  })

  it('renders default slot content', () => {
    const wrapper = mount(ChartCard, {
      props: { title: '测试' },
      slots: { default: '<div class="chart-body">图表内容</div>' },
    })
    expect(wrapper.find('.chart-body').exists()).toBe(true)
  })
})
