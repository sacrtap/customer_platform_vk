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
  }
})
