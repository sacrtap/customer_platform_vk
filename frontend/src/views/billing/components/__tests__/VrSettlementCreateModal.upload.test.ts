import { describe, it, expect, beforeAll, afterEach, vi } from 'vitest'
import { mount, enableAutoUnmount, flushPromises, type VueWrapper } from '@vue/test-utils'
import ArcoVue, { Message } from '@arco-design/web-vue'
import VrSettlementCreateModal from '@/views/billing/components/VrSettlementCreateModal.vue'
import { uploadDiscountAttachment, createVrSettlement } from '@/api/vrSettlement'

vi.mock('@/api/vrSettlement', () => ({
  uploadDiscountAttachment: vi.fn(),
  createVrSettlement: vi.fn(),
}))

// 同 BalanceTable：Arco 组件销毁后残留 rAF 会触发 jsdom 未处理异常
enableAutoUnmount(afterEach)

// Arco responsive-observe 依赖 matchMedia，jsdom 不提供
beforeAll(() => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as never
})

/**
 * <script setup> 编译后 VTU 的 vm 类型不含 setup 暴露成员，
 * 测试需按名访问内部状态/方法，故一次性断言到该命名形状（仅测试接线用）。
 */
interface CreateModalVm {
  form: Record<string, unknown>
  fileList: { file?: File; name?: string }[]
  handleFileChange: (list: { file?: File; name?: string }[]) => void
  handleSubmit: () => Promise<boolean>
}

function vmOf(wrapper: VueWrapper): CreateModalVm {
  return (wrapper.vm as unknown as { $: { setupState: CreateModalVm } }).$.setupState
}

function mountModal(): VueWrapper {
  return mount(VrSettlementCreateModal, {
    props: { visible: true },
    global: { plugins: [ArcoVue] },
  })
}

/**
 * 回归守护（2026-11-03 修复）：
 * 1. 移除已选文件后 file-list 必须同步为空（旧实现 length>0 守卫导致移除无效）
 * 2. 上传失败必须展示后端真实错误 message（旧实现吞成统一「文件上传失败」）
 */
describe('VrSettlementCreateModal 明细文件上传', () => {
  it('移除文件（空列表回调）后 file-list 同步清空', async () => {
    const wrapper = mountModal()
    const vm = vmOf(wrapper)

    // 选中一个文件
    const fakeFile = new File(['x'], '明细.xlsx')
    vm.handleFileChange([{ file: fakeFile, name: '明细.xlsx' }])
    await flushPromises()
    expect(vm.fileList).toHaveLength(1)

    // 点移除：Arco 回传空数组——旧实现在此不清空（length>0 守卫）
    vm.handleFileChange([])
    await flushPromises()
    expect(vm.fileList).toHaveLength(0)
  })

  it('上传失败时展示后端真实错误 message', async () => {
    const errorSpy = vi.spyOn(Message, 'error').mockImplementation(() => '' as never)
    // 400 类（参数/业务错误）走后端 message 透传分支；拦截器 reject 形状同此
    vi.mocked(uploadDiscountAttachment).mockRejectedValue({
      code: 40001,
      message: '文件大小超过限制 (10MB)',
      category: 'client',
    })

    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    // reactive 代理引用不可整体替换，按属性合并
    Object.assign(vm.form, {
      customer_id: 1,
      period_start: '2026-11-01',
      period_end: '2026-11-30',
      total_amount: 100,
    })
    vm.fileList = [{ file: new File(['x'], '明细.xlsx') }]
    await flushPromises()

    const ok = await vm.handleSubmit()

    expect(ok).toBe(false)
    // 真实后端文案必须透出，而非统一「文件上传失败」（showError 走对象形式）
    expect(errorSpy).toHaveBeenCalledWith(
      expect.objectContaining({ content: '文件大小超过限制 (10MB)' })
    )
    // 上传失败不得继续创建
    expect(createVrSettlement).not.toHaveBeenCalled()
  })

  it('上传成功且创建成功时emit success', async () => {
    vi.mocked(uploadDiscountAttachment).mockResolvedValue({
      code: 0,
      data: { file_path: '/uploads/2026/11/abc.xlsx' },
    } as never)
    vi.mocked(createVrSettlement).mockResolvedValue({ code: 0, data: { id: 1 } } as never)

    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    Object.assign(vm.form, {
      customer_id: 1,
      period_start: '2026-11-01',
      period_end: '2026-11-30',
      total_amount: 100,
    })
    vm.fileList = [{ file: new File(['x'], '明细.xlsx'), name: '明细.xlsx' }]
    await flushPromises()

    const ok = await vm.handleSubmit()

    expect(ok).toBe(true)
    expect(uploadDiscountAttachment).toHaveBeenCalled()
    expect(createVrSettlement).toHaveBeenCalledWith(
      expect.objectContaining({
        customer_id: 1,
        total_amount: 100,
        detail_file_path: '/uploads/2026/11/abc.xlsx',
        detail_file_name: '明细.xlsx',
      })
    )
    expect(wrapper.emitted('success')).toBeTruthy()
  })
})
