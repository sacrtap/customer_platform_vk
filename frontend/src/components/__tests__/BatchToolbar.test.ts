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
    expect(wrapper.text()).toContain('批量编辑')
    expect(wrapper.text()).toContain('分配负责人')
  })

  it('emits batch-action event', async () => {
    const wrapper = mount(BatchToolbar, {
      props: { selectedCount: 2 },
    })
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    expect(wrapper.emitted('batchAction')).toBeTruthy()
  })

  it('导出中时批量导出按钮禁用且文案切换', () => {
    const idle = mount(BatchToolbar, { props: { selectedCount: 2 } })
    const idleExportBtn = idle.findAll('button').find((b) => b.text() === '批量导出')
    expect(idleExportBtn?.attributes('disabled')).toBeUndefined()

    const busy = mount(BatchToolbar, { props: { selectedCount: 2, exporting: true } })
    const busyExportBtn = busy.findAll('button').find((b) => b.text() === '导出中...')
    expect(busyExportBtn?.attributes('disabled')).toBeDefined()
    // 其他按钮不受影响
    const editBtn = busy.findAll('button').find((b) => b.text() === '批量编辑')
    expect(editBtn?.attributes('disabled')).toBeUndefined()
  })
})
