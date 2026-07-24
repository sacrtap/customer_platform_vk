import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '@/components/PageHeader.vue'

describe('PageHeader', () => {
  it('renders eyebrow, title, and subtitle', () => {
    const wrapper = mount(PageHeader, {
      props: {
        eyebrow: '客户管理',
        title: '客户列表',
        subtitle: '统一客户基础信息与画像数据管理',
      },
    })
    expect(wrapper.find('.eyebrow').text()).toBe('客户管理')
    expect(wrapper.find('h1').text()).toBe('客户列表')
    expect(wrapper.find('.desc').text()).toBe('统一客户基础信息与画像数据管理')
  })

  it('renders actions slot', () => {
    const wrapper = mount(PageHeader, {
      props: { eyebrow: '测试', title: '标题' },
      slots: { actions: '<button>操作</button>' },
    })
    expect(wrapper.find('.actions button').exists()).toBe(true)
  })

  it('hides subtitle when not provided', () => {
    const wrapper = mount(PageHeader, {
      props: { eyebrow: '测试', title: '标题' },
    })
    expect(wrapper.find('.desc').exists()).toBe(false)
  })
})
