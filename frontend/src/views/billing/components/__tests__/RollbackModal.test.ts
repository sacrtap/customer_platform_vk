import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'
import ArcoVue from '@arco-design/web-vue'
import RollbackModal from '@/views/billing/components/RollbackModal.vue'

// Arco 组件销毁后可能残留 requestAnimationFrame，触发 jsdom 未处理异常
enableAutoUnmount(afterEach)

// jsdom 不实现 window.matchMedia，Arco 响应式组件挂载时需要
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

// a-modal 真实渲染 Teleport 到 body 且依赖 rAF，测试环境不稳定；stub 掉并透传
// before-ok（= 点击确定）与 title，弹窗主体（表单/textarea/校验）保持真实组件
function mountModal(overrides: Record<string, unknown> = {}) {
  return mount(RollbackModal, {
    props: { visible: true, ...overrides } as never,
    global: {
      plugins: [ArcoVue],
      stubs: {
        'a-modal': {
          props: ['title'],
          template:
            '<div class="modal-stub"><span class="modal-stub-title">{{ title }}</span>' +
            '<slot /><button class="modal-stub-ok" @click="$emit(\'before-ok\')">确定</button>' +
            '<button class="modal-stub-cancel" @click="$emit(\'cancel\')">取消</button></div>',
        },
      },
    },
  })
}

describe('RollbackModal - 回退理由弹窗', () => {
  it('标题默认「回退」，可被 props 覆盖', () => {
    expect(mountModal().find('.modal-stub-title').text()).toBe('回退')
    expect(mountModal({ title: '回退至上一步审核' }).find('.modal-stub-title').text()).toBe(
      '回退至上一步审核'
    )
  })

  it('空理由点击确定：校验失败，不 emit submit', async () => {
    const wrapper = mountModal()
    await wrapper.find('textarea').setValue('')
    await wrapper.find('.modal-stub-ok').trigger('click')
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('填写理由点击确定：emit submit 且 trim 首尾空白', async () => {
    const wrapper = mountModal()
    await wrapper.find('textarea').setValue('  信息有误  ')
    await wrapper.find('.modal-stub-ok').trigger('click')
    expect(wrapper.emitted('submit')?.[0]).toEqual(['信息有误'])
  })

  it('提交后不自动关闭弹窗（由调用方成功后关闭）', async () => {
    const wrapper = mountModal()
    await wrapper.find('textarea').setValue('信息有误')
    await wrapper.find('.modal-stub-ok').trigger('click')
    expect(wrapper.emitted('update:visible')).toBeUndefined()
  })

  it('点击取消 emit update:visible false', async () => {
    const wrapper = mountModal()
    await wrapper.find('.modal-stub-cancel').trigger('click')
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('重新打开时清空上次输入', async () => {
    const wrapper = mountModal()
    await wrapper.find('textarea').setValue('上次的理由')
    // VTU 对 script-setup 泛型 props 推断丢失，仓库既有模式为 as never
    await wrapper.setProps({ visible: false } as never)
    await wrapper.setProps({ visible: true } as never)
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('')
  })
})
