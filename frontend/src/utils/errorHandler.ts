import { Message } from '@arco-design/web-vue'

/** 错误码分类枚举 */
export enum ErrorCategory {
  SUCCESS = 0,
  CLIENT_ERROR = 400, // 400xx - 参数错误
  AUTH_ERROR = 401, // 401xx - 认证错误
  FORBIDDEN_ERROR = 403, // 403xx - 权限不足
  NOT_FOUND_ERROR = 404, // 404xx - 资源不存在
  BUSINESS_ERROR = 422, // 422xx - 业务逻辑错误
  SERVER_ERROR = 500, // 500xx - 服务器错误
}

/** 扩展错误接口 */
export interface AppError {
  code: number | string
  message: string
  category: ErrorCategory
}

/** 根据错误码获取分类 */
export function getErrorCategory(code: number): ErrorCategory {
  if (code === 0) return ErrorCategory.SUCCESS
  if (code >= 40000 && code < 40100) return ErrorCategory.CLIENT_ERROR
  if (code >= 40100 && code < 40200) return ErrorCategory.AUTH_ERROR
  if (code >= 40300 && code < 40400) return ErrorCategory.FORBIDDEN_ERROR
  if (code >= 40400 && code < 40500) return ErrorCategory.NOT_FOUND_ERROR
  if (code >= 42200 && code < 42300) return ErrorCategory.BUSINESS_ERROR
  if (code >= 50000) return ErrorCategory.SERVER_ERROR
  return ErrorCategory.SERVER_ERROR
}

/** 获取用户友好的错误提示 */
export function getUserFriendlyMessage(code: number, backendMessage: string): string {
  const category = getErrorCategory(code)

  // 对于参数错误和业务错误，优先使用后端返回的具体信息
  if (category === ErrorCategory.CLIENT_ERROR || category === ErrorCategory.BUSINESS_ERROR) {
    return backendMessage || '请求参数有误，请检查后重试'
  }

  // 对于系统级错误，使用统一的友好提示
  switch (category) {
    case ErrorCategory.AUTH_ERROR:
      // 优先使用后端返回的具体信息（如"用户名或密码错误"）
      // 其他情况（如 token 过期）显示通用提示
      return backendMessage || '登录已过期，请重新登录'
    case ErrorCategory.FORBIDDEN_ERROR:
      return '您没有执行此操作的权限'
    case ErrorCategory.NOT_FOUND_ERROR:
      return '请求的资源不存在'
    case ErrorCategory.SERVER_ERROR:
      return '系统繁忙，请稍后重试'
    default:
      return backendMessage || '操作失败'
  }
}

/** 展示错误提示 */
export function showError(message: string, duration = 3000): void {
  Message.error({
    content: message,
    duration,
  })
}

/** 统一错误处理函数 */
export function handleError(error: unknown, fallbackMessage = '操作失败'): void {
  // AppError 对象
  if (error && typeof error === 'object' && 'code' in error) {
    const appError = error as AppError

    if (typeof appError.code === 'number') {
      const friendlyMsg = getUserFriendlyMessage(appError.code, appError.message)
      showError(friendlyMsg)
      return
    }

    // 网络错误
    if (appError.code === 'NETWORK_ERROR' || appError.code === 'ECONNABORTED') {
      showError('网络连接失败，请检查网络设置')
      return
    }
  }

  // 标准 Error 对象
  if (error instanceof Error) {
    showError(error.message || fallbackMessage)
    return
  }

  // 兜底
  showError(fallbackMessage)
}
