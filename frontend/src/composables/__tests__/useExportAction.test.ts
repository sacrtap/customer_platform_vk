import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { Message } from '@arco-design/web-vue'
import { useExportAction, type ExportApi, type ExportResponse } from '../useExportAction'

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

// 屏蔽 jsdom 未实现的 navigation（<a download> click 会触发）
const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

// jsdom 的 URL 上没有 createObjectURL/revokeObjectURL
const createObjectURL = vi.fn(() => 'blob:mock')
const revokeObjectURL = vi.fn()
vi.stubGlobal(
  'URL',
  class extends URL {
    static createObjectURL = createObjectURL
    static revokeObjectURL = revokeObjectURL
  }
)

const ok = (headers?: Record<string, string>): ExportResponse => ({
  data: new Blob(['x']),
  headers,
})

// 用宽松签名便于在各用例中按需 as 到具体参数类型
const api = vi.fn(async (_params?: unknown) => ok())

describe('useExportAction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.mockImplementation(async () => ok())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('导出期间 exporting 为 true，结束后复位', async () => {
    const { exporting, run } = useExportAction({
      exportApi: api,
      filename: 'a.xlsx',
    })
    expect(exporting.value).toBe(false)

    const promise = run(undefined)
    expect(exporting.value).toBe(true)

    await promise
    expect(exporting.value).toBe(false)
  })

  it('导出失败后 exporting 仍复位', async () => {
    api.mockImplementation(async () => {
      throw new Error('network')
    })

    const { exporting, run } = useExportAction({ exportApi: api, filename: 'a.xlsx' })
    await run(undefined)

    expect(exporting.value).toBe(false)
  })

  it('默认提示导出成功', async () => {
    const { run } = useExportAction({ exportApi: api, filename: 'a.xlsx' })
    await run(undefined)

    expect(Message.success).toHaveBeenCalledWith('导出成功')
  })

  it('successMessage 为 false 时不提示', async () => {
    const { run } = useExportAction({
      exportApi: api,
      filename: 'a.xlsx',
      successMessage: false,
    })
    await run(undefined)

    expect(Message.success).not.toHaveBeenCalled()
  })

  it('filename 为函数时按调用时求值，并用于 link.download', async () => {
    const downloads: string[] = []
    clickSpy.mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push(this.download)
    })

    const { run } = useExportAction({
      exportApi: api,
      filename: () => `balances_${new Date().toISOString().slice(0, 10)}.xlsx`,
    })
    await run(undefined)

    expect(downloads).toEqual([`balances_${new Date().toISOString().slice(0, 10)}.xlsx`])
  })

  it('onSuccess 收到原始响应，可读取 X-Truncated 响应头', async () => {
    api.mockImplementation(async () => ok({ 'x-truncated': 'true' }))
    const onSuccess = vi.fn()

    const { run } = useExportAction({
      exportApi: api,
      filename: 'a.xlsx',
      onSuccess,
    })
    await run(undefined)

    expect(onSuccess).toHaveBeenCalledWith(ok({ 'x-truncated': 'true' }))
  })

  it('object URL 延迟回收，不在下载前撤销', async () => {
    vi.useFakeTimers()
    const { run } = useExportAction({ exportApi: api, filename: 'a.xlsx' })
    await run(undefined)

    expect(revokeObjectURL).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1000)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })

  it('透传参数给导出接口', async () => {
    const { run } = useExportAction({
      exportApi: api as unknown as ExportApi<{ status: string }>,
      filename: 'a.xlsx',
    })
    await run({ status: 'draft' })

    expect(api).toHaveBeenCalledWith({ status: 'draft' })
  })

  it('失败时走 handleError，不抛给调用方', async () => {
    api.mockImplementation(async () => {
      throw new Error('boom')
    })
    const { run } = useExportAction({ exportApi: api, filename: 'a.xlsx' })

    await expect(run(undefined)).resolves.toBeUndefined()
  })
})
