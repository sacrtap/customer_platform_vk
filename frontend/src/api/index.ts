import axios from 'axios'
import type { AxiosInstance, AxiosResponse } from 'axios'
import router from '@/router'

const service: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    // 直接从 localStorage 读取 token，避免在拦截器中使用 useUserStore() 的问题
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

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    // blob 响应（文件下载等）直接返回完整 response，不做 JSON 校验
    if (response.config.responseType === 'blob') {
      return response
    }
    const res = response.data
    if (res.code !== 0) {
      if (res.code === 40101 || res.code === 40102) {
        // 清除 localStorage 中的 token
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user_permissions')
        router.push('/login')
      }
      return Promise.reject(new Error(res.message || 'Error'))
    }
    return res
  },
  (error) => {
    if (error.response && error.response.status === 401) {
      // 清除 localStorage 中的 token
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user_permissions')
      router.push('/login')
    }
    // 提取后端返回的错误信息
    if (error.response && error.response.data && error.response.data.message) {
      return Promise.reject(new Error(error.response.data.message))
    }
    return Promise.reject(error)
  }
)

export default service
