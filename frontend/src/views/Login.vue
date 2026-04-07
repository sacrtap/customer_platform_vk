<template>
  <div class="login-container">
    <!-- 背景效果 -->
    <div class="bg-gradient-orb bg-gradient-orb-1"></div>
    <div class="bg-gradient-orb bg-gradient-orb-2"></div>
    <div class="bg-gradient-orb bg-gradient-orb-3"></div>
    <div class="bg-grid-pattern"></div>

    <!-- 登录框 -->
    <div class="login-box">
      <!-- 左侧品牌区域 -->
      <div class="login-brand">
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
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
              />
            </svg>
          </div>
          <span class="brand-logo-text">Customer Platform VK</span>
        </div>

        <div class="brand-content">
          <h1 class="brand-title">客户运营中台</h1>
          <p class="brand-subtitle">统一管理客户信息、结算、画像，实现高效运营分析与决策支持</p>

          <div class="brand-features">
            <div v-for="(feature, index) in features" :key="index" class="brand-feature">
              <div class="brand-feature-icon">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2.5"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <span>{{ feature }}</span>
            </div>
          </div>
        </div>

        <div class="brand-footer">
          <div class="brand-stats">
            <div v-for="(stat, index) in stats" :key="index" class="brand-stat">
              <span class="brand-stat-value">{{ stat.value }}</span>
              <span class="brand-stat-label">{{ stat.label }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧登录表单 -->
      <div class="login-form-panel">
        <div class="login-header">
          <h2 class="login-welcome">欢迎回来</h2>
          <p class="login-subtitle">请输入您的账号信息登录系统</p>
        </div>

        <a-form ref="formRef" layout="vertical" :model="formData" @submit="handleSubmit">
          <a-form-item
            field="username"
            label="账号"
            :rules="[{ required: true, message: '请输入用户名' }]"
          >
            <a-input
              v-model="formData.username"
              placeholder="请输入用户名/邮箱"
              size="large"
              :disabled="loading"
              allow-clear
            >
              <template #prefix>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  fill="currentColor"
                  viewBox="0 0 16 16"
                >
                  <path
                    d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4Zm-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.289 10 8 10c-2.29 0-3.516.68-4.168 1.332-.678.678-.83 1.418-.832 1.664h10Z"
                  />
                </svg>
              </template>
            </a-input>
          </a-form-item>

          <a-form-item
            field="password"
            label="密码"
            :rules="[{ required: true, message: '请输入密码' }]"
          >
            <a-input-password
              v-model="formData.password"
              placeholder="请输入密码"
              size="large"
              :disabled="loading"
            >
              <template #prefix>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  fill="currentColor"
                  viewBox="0 0 16 16"
                >
                  <path
                    d="M8 1a2 2 0 0 1 2 2v4H6V3a2 2 0 0 1 2-2Zm3 6V3a3 3 0 0 0-6 0v4a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2ZM5 8v5a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V8H5Z"
                  />
                </svg>
              </template>
            </a-input-password>
          </a-form-item>

          <div class="login-options">
            <a-checkbox v-model="formData.remember">记住我</a-checkbox>
            <a href="#" class="login-forgot" @click.prevent="forgotPasswordVisible = true"
              >忘记密码？</a
            >
          </div>

          <a-form-item>
            <a-button
              type="primary"
              html-type="submit"
              size="large"
              long
              :loading="loading"
              class="login-submit-btn"
            >
              登 录
            </a-button>
          </a-form-item>
        </a-form>

        <div class="login-footer">还没有账号？<a href="#">联系管理员</a></div>
      </div>
    </div>

    <!-- 忘记密码对话框 -->
    <a-modal
      v-model:visible="forgotPasswordVisible"
      title="重置密码"
      :mask-closable="false"
      @ok="handleForgotPassword"
      @cancel="forgotPasswordVisible = false"
    >
      <a-form ref="forgotFormRef" :model="forgotForm" layout="vertical">
        <a-form-item
          label="用户名/邮箱"
          field="username"
          :rules="[{ required: true, message: '请输入用户名或邮箱' }]"
        >
          <a-input v-model="forgotForm.username" placeholder="请输入用户名或邮箱" size="large" />
        </a-form-item>
        <a-form-item
          label="注册邮箱"
          field="email"
          :rules="[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '邮箱格式不正确' },
          ]"
        >
          <a-input v-model="forgotForm.email" placeholder="请输入注册时的邮箱" size="large" />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-button @click="forgotPasswordVisible = false">取消</a-button>
        <a-button type="primary" :loading="forgotLoading" @click="handleForgotPassword">
          发送重置链接
        </a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import api from '@/api'

const router = useRouter()
const userStore = useUserStore()

const features = ['RBAC 权限模型 + 自定义角色', '客户信息与画像统一管理', '多维度数据分析与洞察']

const stats = [
  { value: '99.9%', label: '系统可用性' },
  { value: '500+', label: '企业客户' },
  { value: '24/7', label: '技术支持' },
]

const formRef = ref<FormInstance>()
const formData = reactive({
  username: '',
  password: '',
  remember: false,
})

const loading = ref(false)

// 忘记密码相关
const forgotPasswordVisible = ref(false)
const forgotFormRef = ref<FormInstance>()
const forgotForm = reactive({
  username: '',
  email: '',
})
const forgotLoading = ref(false)

const handleSubmit = async () => {
  // 先进行表单验证
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch (error) {
    // 验证失败，不继续提交
    return
  }

  loading.value = true

  try {
    const res = await api.post('/auth/login', formData)

    // 记住我功能：保存或移除用户名
    if (formData.remember) {
      localStorage.setItem('remembered_username', formData.username)
    } else {
      localStorage.removeItem('remembered_username')
    }

    userStore.setToken(res.data.access_token, res.data.refresh_token)
    userStore.setUserInfo(res.data.user)
    userStore.setPermissions(res.data.permissions || [])
    Message.success('登录成功')
    router.push('/')
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '登录失败')
  } finally {
    loading.value = false
  }
}

// 页面加载时恢复记住的用户名
onMounted(() => {
  const rememberedUsername = localStorage.getItem('remembered_username')
  if (rememberedUsername) {
    formData.username = rememberedUsername
    formData.remember = true
  }
})

// 忘记密码处理
const handleForgotPassword = async () => {
  if (!forgotFormRef.value) return

  try {
    await forgotFormRef.value.validate()
  } catch (error) {
    return
  }

  forgotLoading.value = true

  try {
    await api.post('/auth/forgot-password', forgotForm)

    Message.success('密码重置链接已发送到您的邮箱，请查收')
    forgotPasswordVisible.value = false

    // 重置表单
    forgotForm.username = ''
    forgotForm.email = ''
  } catch (error) {
    Message.error((error as Error).message || '发送失败，请稍后重试')
  } finally {
    forgotLoading.value = false
  }
}
</script>

<style scoped>
/* CSS 变量 */
.login-container {
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

.login-container {
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
  background: radial-gradient(circle, rgba(59, 130, 246, 0.3) 0%, transparent 70%);
  bottom: -150px;
  left: -150px;
  animation-delay: -7s;
}

.bg-gradient-orb-3 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation-delay: -14s;
}

@keyframes float {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  25% {
    transform: translate(30px, -30px) scale(1.05);
  }
  50% {
    transform: translate(-20px, 20px) scale(0.95);
  }
  75% {
    transform: translate(20px, 30px) scale(1.02);
  }
}

.bg-grid-pattern {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 60px 60px;
  pointer-events: none;
}

/* 登录框 */
.login-box {
  display: grid;
  grid-template-columns: 1fr 1fr;
  max-width: 1100px;
  width: 90%;
  background: rgba(255, 255, 255, 0.98);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.16);
  position: relative;
  z-index: 10;
  animation: slideUp 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(40px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 左侧品牌区域 */
.login-brand {
  background: linear-gradient(135deg, var(--bg-deep) 0%, #1e293b 100%);
  padding: 64px 56px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.login-brand::before {
  content: '';
  position: absolute;
  inset: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  opacity: 0.5;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
  z-index: 1;
}

.brand-logo-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--primary-5) 0%, var(--primary-6) 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(3, 105, 161, 0.4);
}

.brand-logo-icon svg {
  width: 28px;
  height: 28px;
  color: white;
}

.brand-logo-text {
  font-size: 24px;
  font-weight: 700;
  color: white;
  letter-spacing: -0.5px;
}

.brand-content {
  position: relative;
  z-index: 1;
}

.brand-title {
  font-size: 36px;
  font-weight: 700;
  color: white;
  line-height: 1.2;
  margin-bottom: 16px;
}

.brand-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  margin-bottom: 32px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.brand-feature {
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
}

.brand-feature-icon {
  width: 20px;
  height: 20px;
  background: rgba(3, 105, 161, 0.3);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-feature-icon svg {
  width: 12px;
  height: 12px;
  color: var(--primary-1);
}

.brand-footer {
  position: relative;
  z-index: 1;
}

.brand-stats {
  display: flex;
  gap: 32px;
}

.brand-stat {
  text-align: left;
}

.brand-stat-value {
  font-size: 28px;
  font-weight: 700;
  color: white;
  display: block;
}

.brand-stat-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
  display: block;
}

/* 右侧表单区域 */
.login-form-panel {
  padding: 64px 56px;
  background: white;
}

.login-header {
  margin-bottom: 40px;
}

.login-welcome {
  font-size: 28px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.login-subtitle {
  font-size: 15px;
  color: var(--neutral-6);
}

/* 表单样式 */
:deep(.arco-form) {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

:deep(.arco-form-item) {
  margin-bottom: 0;
}

:deep(.arco-form-item-label) {
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-9);
  margin-bottom: 8px;
}

:deep(.arco-input-inner-wrapper) {
  border-radius: 12px;
  border: 1.5px solid var(--neutral-3);
  height: 48px;
  transition: all var(--transition-base);
}

:deep(.arco-input-inner-wrapper:hover) {
  border-color: var(--primary-5);
}

:deep(.arco-input-inner-wrapper:focus-within) {
  border-color: var(--primary-6);
  box-shadow: 0 0 0 3px rgba(3, 105, 161, 0.1);
}

:deep(.arco-input) {
  font-size: 15px;
}

:deep(.arco-input-prefix) {
  color: var(--neutral-5);
  margin-right: 12px;
}

.login-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
  margin-bottom: 20px;
}

:deep(.arco-checkbox) {
  font-size: 14px;
  color: var(--neutral-7);
}

.login-forgot {
  font-size: 14px;
  color: var(--primary-6);
  text-decoration: none;
  font-weight: 500;
  transition: color var(--transition-fast);
}

.login-forgot:hover {
  color: var(--primary-7);
}

.login-submit-btn {
  height: 48px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--primary-5) 0%, var(--primary-6) 100%);
  color: white;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.3);
  transition: all var(--transition-base);
}

.login-submit-btn:hover {
  background: linear-gradient(135deg, var(--primary-6) 0%, var(--primary-7) 100%);
  box-shadow: 0 6px 20px rgba(3, 105, 161, 0.4);
  transform: translateY(-1px);
}

.login-submit-btn:active {
  transform: translateY(0);
}

.login-footer {
  margin-top: 32px;
  text-align: center;
  font-size: 14px;
  color: var(--neutral-6);
}

.login-footer a {
  color: var(--primary-6);
  text-decoration: none;
  font-weight: 500;
}

.login-footer a:hover {
  text-decoration: underline;
}

/* 响应式 */
@media (max-width: 900px) {
  .login-box {
    grid-template-columns: 1fr;
    max-width: 500px;
  }

  .login-brand {
    display: none;
  }

  .login-form-panel {
    padding: 48px 32px;
  }
}
</style>
