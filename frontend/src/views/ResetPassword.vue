<template>
  <div class="reset-password-container">
    <!-- 背景效果 -->
    <div class="bg-gradient-orb bg-gradient-orb-1"></div>
    <div class="bg-gradient-orb bg-gradient-orb-2"></div>
    <div class="bg-gradient-orb bg-gradient-orb-3"></div>
    <div class="bg-grid-pattern"></div>

    <!-- 重置密码框 -->
    <div class="reset-box">
      <div class="reset-header">
        <div class="brand-logo">
          <div class="brand-logo-icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
              />
            </svg>
          </div>
          <span class="brand-logo-text">重置密码</span>
        </div>
        <p class="reset-subtitle">请输入您的新密码</p>
      </div>

      <a-form ref="formRef" layout="vertical" :model="formData" @submit="handleSubmit">
        <a-form-item
          field="new_password"
          label="新密码"
          :rules="[
            { required: true, message: '请输入新密码' },
            { min: 6, message: '密码长度不能少于 6 位' },
          ]"
        >
          <a-input-password
            v-model="formData.new_password"
            placeholder="请输入新密码"
            size="large"
            :disabled="loading"
          />
        </a-form-item>

        <a-form-item
          field="confirm_password"
          label="确认密码"
          :rules="[
            { required: true, message: '请确认新密码' },
            { validator: validatePasswordMatch, message: '两次输入的密码不一致' },
          ]"
        >
          <a-input-password
            v-model="formData.confirm_password"
            placeholder="请再次输入新密码"
            size="large"
            :disabled="loading"
          />
        </a-form-item>

        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            long
            :loading="loading"
            class="reset-submit-btn"
          >
            重置密码
          </a-button>
        </a-form-item>
      </a-form>

      <div class="reset-footer">
        <router-link to="/login" class="back-to-login">返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import api from '@/api'

const router = useRouter()
const route = useRoute()

const formRef = ref<FormInstance>()
const formData = reactive({
  new_password: '',
  confirm_password: '',
})

const loading = ref(false)

const validatePasswordMatch = (value: string | undefined) => {
  return value === formData.new_password
}

const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch (error) {
    return
  }

  // 获取 URL 中的 token
  const token = route.query.token as string

  if (!token) {
    Message.error('重置链接无效，缺少 Token 参数')
    return
  }

  loading.value = true

  try {
    await api.post('/auth/reset-password', {
      token,
      new_password: formData.new_password,
    })

    Message.success('密码重置成功，即将跳转到登录页')

    // 2 秒后跳转到登录页
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '重置失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* CSS 变量 */
.reset-password-container {
  --primary-1: #e8f3ff;
  --primary-5: #3296f7;
  --primary-6: #0369a1;
  --primary-7: #035a8a;
  --neutral-1: #f7f8fa;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-9: #2f3645;
  --neutral-10: #1d2330;
  --bg-deep: #0f172a;
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

.reset-password-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, var(--bg-deep) 0%, #1e293b 50%, #0f172a 100%);
  overflow: hidden;
}

/* 背景动画效果 */
.bg-gradient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.3;
  animation: float 20s ease-in-out infinite;
}

.bg-gradient-orb-1 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(3, 105, 161, 0.4) 0%, transparent 70%);
  top: -200px;
  right: -200px;
}

.bg-gradient-orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(3, 105, 161, 0.3) 0%, transparent 70%);
  bottom: -150px;
  left: -150px;
  animation-delay: -5s;
}

.bg-gradient-orb-3 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(3, 105, 161, 0.25) 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation-delay: -10s;
}

@keyframes float {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(30px, -30px) scale(1.05);
  }
  66% {
    transform: translate(-20px, 20px) scale(0.95);
  }
}

.bg-grid-pattern {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
}

.reset-box {
  position: relative;
  z-index: 10;
  width: 100%;
  max-width: 480px;
  background: rgba(255, 255, 255, 0.98);
  border-radius: 24px;
  padding: 48px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.reset-header {
  text-align: center;
  margin-bottom: 32px;
}

.brand-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 20px;
}

.brand-logo-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--primary-6), var(--primary-7));
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.3);
}

.brand-logo-icon svg {
  width: 28px;
  height: 28px;
}

.brand-logo-text {
  font-size: 20px;
  font-weight: 600;
  color: var(--neutral-9);
}

.reset-subtitle {
  color: var(--neutral-6);
  font-size: 14px;
}

.reset-submit-btn {
  background: linear-gradient(135deg, var(--primary-6), var(--primary-7));
  border: none;
  font-weight: 500;
  font-size: 16px;
  transition: all var(--transition-base);
}

.reset-submit-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(3, 105, 161, 0.3);
}

.reset-footer {
  margin-top: 24px;
  text-align: center;
}

.back-to-login {
  color: var(--primary-6);
  text-decoration: none;
  font-size: 14px;
  transition: color var(--transition-fast);
}

.back-to-login:hover {
  color: var(--primary-7);
}
</style>
