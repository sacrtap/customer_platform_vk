<template>
  <div class="login-container">
    <div class="login-box">
      <h1 class="login-title">客户运营中台</h1>
      <a-form :model="form" style="max-width: 300px" @submit="handleSubmit">
        <a-form-item
          field="username"
          label="用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
        >
          <a-input
            v-model="form.username"
            placeholder="请输入用户名"
            :disabled="loading"
          />
        </a-form-item>
        <a-form-item
          field="password"
          label="密码"
          :rules="[{ required: true, message: '请输入密码' }]"
        >
          <a-input-password
            v-model="form.password"
            placeholder="请输入密码"
            :disabled="loading"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" long :loading="loading">
            登录
          </a-button>
        </a-form-item>
      </a-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import api from '@/api'

const router = useRouter()
const userStore = useUserStore()

const form = reactive({
  username: '',
  password: '',
})

const loading = ref(false)

const handleSubmit = async () => {
  loading.value = true
  
  try {
    const res = await api.post('/auth/login', form)
    userStore.setToken(res.data.access_token, res.data.refresh_token)
    userStore.setUserInfo(res.data.user)
    userStore.setPermissions(res.data.permissions || [])
    Message.success('登录成功')
    router.push('/')
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #165dff 0%, #0e42d2 100%);
}

.login-box {
  background: white;
  padding: 40px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  width: 100%;
  max-width: 400px;
}

.login-title {
  text-align: center;
  margin-bottom: 30px;
  color: #165dff;
  font-size: 24px;
}
</style>
