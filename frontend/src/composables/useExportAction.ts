import { ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'

/** Excel MIME 类型（xlsx） */
const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/**
 * 延迟回收 object URL 的等待时间（ms）。
 * Safari/Firefox 可能在下载启动前就撤销 object URL 导致下载失败，
 * 故不能 click() 后立即 revoke。
 */
const REVOKE_DELAY_MS = 1000

/**
 * 导出接口响应（仅声明本模块用到的字段）。
 * headers 用宽松索引类型以兼容 AxiosResponseHeaders——其值为
 * `string | number | string[] | undefined`，不适合收窄成 string。
 */
export interface ExportResponse {
  data: Blob | ArrayBuffer
  headers?: Record<string, unknown>
}

/** 导出接口签名 */
export type ExportApi<P> = (params: P) => Promise<ExportResponse>

export interface UseExportActionOptions<P> {
  /** 导出接口 */
  exportApi: ExportApi<P>
  /** 下载文件名，可传函数以依赖当前筛选条件 */
  filename: string | (() => string)
  /**
   * 成功提示文案。默认 `'导出成功'`；
   * 传 `false` 表示不提示（调用方自行通过 onSuccess 反馈）。
   */
  successMessage?: string | false
  /** 成功回调，收到原始响应，便于读取 X-Truncated 等响应头 */
  onSuccess?: (res: ExportResponse) => void
  /** 失败时的兜底提示文案 */
  errorMessage?: string
}

/**
 * 页面级导出动作契约：统一「进行中」状态 + Blob 下载 + 错误处理。
 *
 * 用于消除各页面手抄 `exporting` ref + try/finally + 下载代码的重复，
 * 并保证状态在异常路径必然复位（否则按钮会永久卡在「导出中」）。
 *
 * @example
 * const { exporting, run } = useExportAction({
 *   exportApi: exportBalances,
 *   filename: () => `balances_${new Date().toISOString().slice(0, 10)}.xlsx`,
 *   onSuccess: (res) => {
 *     if (res.headers?.['x-truncated'] === 'true') {
 *       Message.warning('数据超过 5 万条，仅导出了前 5 万条，请缩小筛选范围后再导出')
 *     }
 *   },
 * })
 */
export function useExportAction<P = void>(options: UseExportActionOptions<P>) {
  const {
    exportApi,
    filename,
    successMessage = '导出成功',
    onSuccess,
    errorMessage = '导出失败',
  } = options

  const exporting = ref(false)

  const run = async (params: P) => {
    exporting.value = true
    try {
      const res = await exportApi(params)
      const blob = new Blob([res.data], { type: XLSX_MIME })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = typeof filename === 'function' ? filename() : filename
      document.body.appendChild(link)
      link.click()
      // 延迟回收：见 REVOKE_DELAY_MS 注释
      setTimeout(() => {
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
      }, REVOKE_DELAY_MS)

      onSuccess?.(res)
      if (successMessage !== false) {
        Message.success(successMessage)
      }
    } catch (error: unknown) {
      handleError(error, errorMessage)
    } finally {
      exporting.value = false
    }
  }

  return { exporting, run }
}
