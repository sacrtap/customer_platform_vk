import axios from 'axios'
import type { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import router from '@/router'
import { getErrorCategory, ErrorCategory } from '@/utils/errorHandler'

const service: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 防止并发重复刷新
let isRefreshing = false
// 等待刷新完成的请求队列
let refreshSubscribers: Array<(token: string) => void> = []

// 通知所有等待的请求使用新 token
function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token))
  refreshSubscribers = []
}

// 清除等待队列并跳转登录
function onRefreshFailed() {
  refreshSubscribers = []
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user_permissions')
  router.push('/login')
}

// 将请求加入等待队列
function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 刷新 token 函数
async function doRefreshToken(): Promise<string> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    throw new Error('No refresh token')
  }

  // 使用 axios 直接调用刷新接口，避免触发拦截器的 401 处理
  const response = await axios.post('/api/v1/auth/refresh', {
    refresh_token: refreshToken,
  })

  const res = response.data
  if (res.code === 0 && res.data?.access_token) {
    const { access_token, refresh_token: newRefreshToken } = res.data
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', newRefreshToken)
    return access_token
  }

  throw new Error('Refresh token failed')
}

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    // blob 响应（文件下载等）直接返回完整 response，不做 JSON 校验
    if (response.config.responseType === 'blob') {
      return response
    }
    const res = response.data
    if (res.code !== 0) {
      // 业务错误
      const category = getErrorCategory(res.code)

      // 认证错误：让调用方处理（通常会触发刷新或跳转登录）
      if (category === ErrorCategory.AUTH_ERROR) {
        return Promise.reject({
          code: res.code,
          message: res.message || '认证失败',
          category,
        })
      }

      // 其他业务错误：带上错误分类信息返回
      return Promise.reject({
        code: res.code,
        message: res.message || '操作失败',
        category,
      })
    }
    return res
  },
  async (error) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // HTTP 401 响应
    if (error.response && error.response.status === 401 && !originalRequest._retry) {
      // 登录接口不应该尝试刷新 token
      if (originalRequest.url?.includes('/auth/login')) {
        // 直接返回后端错误信息
        return Promise.reject({
          code: error.response.data?.code || 40101,
          message: error.response.data?.message || '用户名或密码错误',
          category: ErrorCategory.AUTH_ERROR,
        })
      }

      if (isRefreshing) {
        // 正在刷新，将请求加入等待队列
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(service(originalRequest))
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const newToken = await doRefreshToken()
        onRefreshed(newToken)
        // 重试原请求
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return service(originalRequest)
      } catch {
        // 刷新失败，清理状态并跳转登录
        onRefreshFailed()
        return Promise.reject(error)
      } finally {
        isRefreshing = false
      }
    }

    // 网络错误或 HTTP 错误
    if (!error.response) {
      return Promise.reject({
        code: 'NETWORK_ERROR',
        message: '网络连接失败',
        category: ErrorCategory.SERVER_ERROR,
      })
    }

    // 提取后端返回的错误信息
    // 优先使用 response.data.message，其次是 statusText
    const backendMessage = error.response.data?.message || 
                           error.response.statusText || 
                           '请求失败'
    const code = error.response.data?.code || error.response.status * 100

    return Promise.reject({
      code,
      message: backendMessage,
      category: getErrorCategory(typeof code === 'number' ? code : 50000),
    })
  }
)

export default service
