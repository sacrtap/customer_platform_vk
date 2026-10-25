import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import BatchDownloadDetailModal from '@/views/billing/components/BatchDownloadDetailModal.vue'
import { getBatchDownloadDetailMeta, downloadInvoiceDetail } from '@/api/billing'

vi.mock('@/api/billing', () => ({
  getBatchDownloadDetailMeta: vi.fn(),
  downloadInvoiceDetail: vi.fn(),
}))

const metaList = [
  {
    id: 1,
    invoice_no: 'INV001',
    customer_id: 5,
    customer_name: '景发',
    detail_file_status: 'completed',
  },
  {
    id: 2,
    invoice_no: 'INV002',
    customer_id: 6,
    customer_name: '景/发:*?',
    detail_file_status: 'completed',
  },
  {
    id: 3,
    invoice_no: 'INV003',
    customer_id: 7,
    customer_name: null,
    detail_file_status: 'completed',
  },
  {
    id: 4,
    invoice_no: 'INV004',
    customer_id: 8,
    customer_name: '未完成客户',
    detail_file_status: 'pending',
  },
]

function mountModal() {
  return mount(BatchDownloadDetailModal, {
    props: { visible: false, ids: [1, 2, 3, 4] },
    global: {
      stubs: {
        'a-modal': { template: '<div><slot /></div>' },
        'a-alert': { template: '<div><slot /></div>' },
        'a-button': { template: '<button><slot /></button>' },
        'a-progress': true,
        'a-spin': true,
      },
    },
  })
}

/** 等待组件内串行下载循环推进（watch/异步回调全部落定） */
async function settle(rounds = 20) {
  for (let i = 0; i < rounds; i++) {
    await nextTick()
    await flushPromises()
  }
}

async function openReady() {
  const w = mountModal()
  vi.mocked(getBatchDownloadDetailMeta).mockResolvedValue({
    data: { list: metaList },
  } as never)
  await w.setProps({ visible: true })
  await settle()
  return w
}

function findButton(
  w: { findAll: (sel: string) => { text(): string; trigger(e: string): Promise<void> }[] },
  text: string
) {
  return w.findAll('button').find((b) => b.text().includes(text))
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(downloadInvoiceDetail).mockResolvedValue({ data: new Blob(['x']) } as never)
})

afterEach(() => {
  // 清理测试注入的 File System Access API
  delete (window as unknown as Record<string, unknown>).showDirectoryPicker
})

describe('BatchDownloadDetailModal', () => {
  it('ready 阶段显示统计与跳过提示', async () => {
    const w = await openReady()
    expect(w.text()).toContain('共 4 项 · 可下载 3 项')
    expect(w.text()).toContain('1 个明细文件未生成完成，将跳过')
    // 未完成项不出现在下载计划中
    expect(getBatchDownloadDetailMeta).toHaveBeenCalledWith([1, 2, 3, 4])
  })

  it('meta 请求失败时提示后端文案并关闭弹窗', async () => {
    const errorSpy = vi.spyOn(Message, 'error').mockImplementation(() => '' as never)
    const w = mountModal()
    vi.mocked(getBatchDownloadDetailMeta).mockRejectedValue(new Error('boom'))
    await w.setProps({ visible: true })
    await settle()
    // 拦截器 reject 的对象带 message 时优先展示
    expect(errorSpy).toHaveBeenCalledWith('boom')
    expect(w.emitted('update:visible')).toBeTruthy()
    errorSpy.mockRestore()
  })

  it('meta 请求失败且无 message 时回退兜底文案', async () => {
    const errorSpy = vi.spyOn(Message, 'error').mockImplementation(() => '' as never)
    const w = mountModal()
    vi.mocked(getBatchDownloadDetailMeta).mockRejectedValue(null)
    await w.setProps({ visible: true })
    await settle()
    expect(errorSpy).toHaveBeenCalledWith('获取下载信息失败')
    errorSpy.mockRestore()
  })

  it('showDirectoryPicker 存在时走目录写入分支，文件名合法且清洗非法字符', async () => {
    const write = vi.fn().mockResolvedValue(undefined)
    const close = vi.fn().mockResolvedValue(undefined)
    const createWritable = vi.fn().mockResolvedValue({ write, close })
    const getFileHandle = vi.fn().mockResolvedValue({ createWritable })
    const showDirectoryPicker = vi.fn().mockResolvedValue({ getFileHandle })
    ;(window as unknown as Record<string, unknown>).showDirectoryPicker = showDirectoryPicker

    const w = await openReady()
    await findButton(w, '开始下载')!.trigger('click')
    await settle()

    expect(showDirectoryPicker).toHaveBeenCalled()
    // 3 个 completed 项全部通过目录写入，名称分别为正常名 / 清洗名 / #id 回退
    expect(getFileHandle).toHaveBeenCalledTimes(3)
    expect(getFileHandle.mock.calls.map((c) => c[0])).toEqual([
      '景发-INV001.xlsx',
      '景发-INV002.xlsx',
      '#7-INV003.xlsx',
    ])
    for (const call of getFileHandle.mock.calls) {
      expect(call[1]).toEqual({ create: true })
    }
    expect(createWritable).toHaveBeenCalledTimes(3)
    expect(write).toHaveBeenCalledTimes(3)
    expect(close).toHaveBeenCalledTimes(3)

    // 完成汇总：成功 3 · 失败 0 · 跳过 1
    expect(w.text()).toContain('下载完成 · 成功 3 · 失败 0 · 跳过 1')
  })

  it('showDirectoryPicker 不存在时降级为浏览器逐个下载（<a download> click）', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const createObjectURL = vi.fn().mockReturnValue('blob:mock')
    const revokeObjectURL = vi.fn()
    window.URL.createObjectURL = createObjectURL as never
    window.URL.revokeObjectURL = revokeObjectURL as never

    const w = await openReady()
    await findButton(w, '开始下载')!.trigger('click')
    await settle()

    expect(clickSpy).toHaveBeenCalledTimes(3)
    expect(createObjectURL).toHaveBeenCalledTimes(3)
    expect(downloadInvoiceDetail).toHaveBeenCalledTimes(3)
    expect(w.text()).toContain('下载完成 · 成功 3 · 失败 0 · 跳过 1')
    clickSpy.mockRestore()
  })

  it('用户取消选目录（AbortError）时回到 ready 阶段，不发起下载', async () => {
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    ;(window as unknown as Record<string, unknown>).showDirectoryPicker = vi
      .fn()
      .mockRejectedValue(abort)

    const w = await openReady()
    await findButton(w, '开始下载')!.trigger('click')
    await settle()

    expect(w.text()).toContain('共 4 项 · 可下载 3 项')
    expect(downloadInvoiceDetail).not.toHaveBeenCalled()
  })

  it('取消按钮中断下载循环（cancelled 后不再发起后续下载）', async () => {
    // 首个下载用受控 promise 挂起：循环停在 await 处，此时点取消，
    // 循环恢复后进入下一轮前读到 cancelled → break。无真实定时器。
    let releaseFirst: (v: { data: Blob }) => void = () => {}
    const firstPromise = new Promise<{ data: Blob }>((resolve) => {
      releaseFirst = resolve
    })
    let calls = 0
    vi.mocked(downloadInvoiceDetail).mockImplementation(async () => {
      calls++
      if (calls === 1) return firstPromise as never
      return { data: new Blob(['x']) } as never
    })

    const w = await openReady()
    await findButton(w, '开始下载')!.trigger('click')
    await settle(5)
    expect(calls).toBe(1)

    await findButton(w, '取消下载')!.trigger('click')
    // 放开挂起的首个下载，循环恢复后应在 break 处停下
    releaseFirst({ data: new Blob(['x']) })
    await settle(20)

    expect(calls).toBe(1)
    expect(w.text()).toContain('已取消')
  })

  it('单个下载失败计入失败列表，不阻塞其余项', async () => {
    vi.mocked(downloadInvoiceDetail).mockImplementation(async () => {
      throw { message: '明细文件不存在' }
    })

    const w = await openReady()
    await findButton(w, '开始下载')!.trigger('click')
    await settle(30)

    expect(w.text()).toContain('下载完成 · 成功 0 · 失败 3 · 跳过 1')
    expect(w.text()).toContain('INV001：明细文件不存在')
  })
})
