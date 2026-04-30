import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface UserInfo {
  id: number
  username: string
  roles: string[]
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>('')
  const refreshToken = ref<string>('')
  const userInfo = ref<UserInfo | null>(null)
  const permissions = ref<Set<string>>(new Set())

  function setToken(newToken: string, newRefreshToken: string) {
    token.value = newToken
    refreshToken.value = newRefreshToken
    localStorage.setItem('access_token', newToken)
    localStorage.setItem('refresh_token', newRefreshToken)
  }

  function setUserInfo(info: UserInfo) {
    userInfo.value = info
    localStorage.setItem('user_info', JSON.stringify(info))
  }

  function setPermissions(perms: string[]) {
    permissions.value = new Set(perms)
    localStorage.setItem('user_permissions', JSON.stringify(perms))
  }

  function hasPermission(code: string): boolean {
    // 超级管理员拥有所有权限
    if (userInfo.value?.roles.includes('超级管理员')) {
      return true
    }
    return permissions.value.has(code)
  }

  function logout() {
    token.value = ''
    refreshToken.value = ''
    userInfo.value = null
    permissions.value = new Set()
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_permissions')
    localStorage.removeItem('user_info')
  }

  function initFromStorage() {
    const storedToken = localStorage.getItem('access_token')
    const storedRefresh = localStorage.getItem('refresh_token')
    const storedPerms = localStorage.getItem('user_permissions')
    const storedUserInfo = localStorage.getItem('user_info')
    if (storedToken) {
      token.value = storedToken
    }
    if (storedRefresh) {
      refreshToken.value = storedRefresh
    }
    if (storedPerms) {
      try {
        permissions.value = new Set(JSON.parse(storedPerms))
      } catch {
        permissions.value = new Set()
      }
    }
    if (storedUserInfo) {
      try {
        userInfo.value = JSON.parse(storedUserInfo)
      } catch {
        userInfo.value = null
      }
    }
  }

  /**
   * 解析 JWT token payload（不验证签名，仅读取内容）
   */
  function decodeJwtPayload(token: string): Record<string, unknown> | null {
    try {
      const parts = token.split('.')
      if (parts.length !== 3) return null
      const payload = JSON.parse(atob(parts[1]))
      return payload
    } catch {
      return null
    }
  }

  /**
   * 检查 access_token 是否已过期
   */
  function isTokenExpired(): boolean {
    if (!token.value) return true
    const payload = decodeJwtPayload(token.value)
    if (!payload) return true
    const exp = payload.exp as number | undefined
    if (!exp) return true
    // JWT exp 是秒级时间戳，Date.now() 是毫秒级
    return Date.now() >= exp * 1000
  }

  /**
   * 获取 access_token 剩余有效时间（毫秒）
   * 返回负数表示已过期
   */
  function getTokenRemainingTime(): number {
    if (!token.value) return 0
    const payload = decodeJwtPayload(token.value)
    if (!payload) return 0
    const exp = payload.exp as number | undefined
    if (!exp) return 0
    return exp * 1000 - Date.now()
  }

  /**
   * 获取 access_token 剩余有效时间（人类可读格式）
   */
  function getTokenRemainingTimeFormatted(): string {
    const ms = getTokenRemainingTime()
    if (ms <= 0) return '已过期'

    const totalSeconds = Math.floor(ms / 1000)
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)

    if (hours > 0) {
      return `${hours}小时${minutes}分钟`
    }
    if (minutes > 0) {
      return `${minutes}分钟`
    }
    return `${totalSeconds}秒`
  }

  const isSuperAdmin = computed(() => {
    return userInfo.value?.roles.includes('超级管理员') ?? false
  })

  return {
    token,
    refreshToken,
    userInfo,
    permissions,
    setToken,
    setUserInfo,
    setPermissions,
    hasPermission,
    logout,
    initFromStorage,
    isSuperAdmin,
    isTokenExpired,
    getTokenRemainingTime,
    getTokenRemainingTimeFormatted,
  }
})
