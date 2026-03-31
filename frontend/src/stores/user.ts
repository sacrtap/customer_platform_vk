import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface UserInfo {
  id: number
  username: string
  roles: string[]
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>('')
  const refreshToken = ref<string>('')
  const userInfo = ref<UserInfo | null>(null)

  function setToken(newToken: string, newRefreshToken: string) {
    token.value = newToken
    refreshToken.value = newRefreshToken
    localStorage.setItem('access_token', newToken)
    localStorage.setItem('refresh_token', newRefreshToken)
  }

  function setUserInfo(info: UserInfo) {
    userInfo.value = info
  }

  function logout() {
    token.value = ''
    refreshToken.value = ''
    userInfo.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  function initFromStorage() {
    const storedToken = localStorage.getItem('access_token')
    const storedRefresh = localStorage.getItem('refresh_token')
    if (storedToken) {
      token.value = storedToken
    }
    if (storedRefresh) {
      refreshToken.value = storedRefresh
    }
  }

  return {
    token,
    refreshToken,
    userInfo,
    setToken,
    setUserInfo,
    logout,
    initFromStorage,
  }
})
