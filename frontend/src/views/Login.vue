<template>
  <div class="login-container">
    <!-- 登录框 -->
    <div class="login-box">
      <!-- 左侧品牌展示区 -->
      <div class="login-brand">
        <div class="brand-header">
          <div class="brand-logo">
            <div class="brand-mark">VK</div>
            <div class="brand-identity">
              <div class="brand-title">客户运营中台</div>
              <div class="brand-subtitle">Customer Operations Platform</div>
            </div>
          </div>
        </div>

        <div class="brand-content">
          <div class="feature-item">
            <div class="feature-icon">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <path d="M3 3v18h18" />
                <path d="M18.7 8l-5.1 5.2-2.8-2.8L7 14.3" />
              </svg>
            </div>
            <div class="feature-text">
              <h3>数据驱动决策</h3>
              <p>实时监控客户消耗、回款、健康度等核心指标，快速识别异常与机会</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feature-icon">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
            </div>
            <div class="feature-text">
              <h3>高效运营管理</h3>
              <p>统一的客户管理、结算管理、画像分析工作台，提升运营效率</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feature-icon">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div class="feature-text">
              <h3>安全可控</h3>
              <p>RBAC 权限模型、完整审计日志、并发安全保障</p>
            </div>
          </div>
        </div>

        <div class="brand-footer">© 2026 客户运营中台 · 企业内部系统</div>
      </div>

      <!-- 右侧登录表单区 -->
      <div class="login-form-panel">
        <div class="login-header">
          <h1 class="login-welcome">欢迎回来</h1>
          <p class="login-subtitle">请登录您的账号以继续使用系统</p>
        </div>

        <a-form ref="formRef" layout="vertical" :model="formData" @submit="handleSubmit">
          <a-form-item
            field="username"
            label="账号"
            :rules="[{ required: true, message: '请输入用户名或邮箱' }]"
          >
            <a-input
              v-model="formData.username"
              placeholder="请输入用户名或邮箱"
              size="large"
              :disabled="loading"
              allow-clear
              @keydown.enter="handleEnter"
            />
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
              @keydown.enter="handleEnter"
            />
          </a-form-item>

          <div class="login-options">
            <a-checkbox v-model="formData.remember">记住我</a-checkbox>
            <a href="#" class="login-forgot" @click.prevent="forgotPasswordVisible = true"
              >忘记密码？</a
            >
          </div>

          <button type="submit" class="login-submit-btn" :disabled="loading">
            <a-spin v-if="loading" size="small" style="margin-right: 8px" />
            <span>{{ loading ? '登录中...' : '登录' }}</span>
            <svg
              v-if="!loading"
              class="btn-arrow"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </a-form>

        <div class="divider"><span>或</span></div>

        <button type="button" class="btn-sso" @click="handleSSO">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>使用企业 SSO 登录</span>
        </button>

        <div class="login-footer">
          还没有账号？<a href="#" @click.prevent="contactAdmin">联系管理员开通</a>
        </div>
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
import { handleError } from '@/utils/errorHandler'

const router = useRouter()
const userStore = useUserStore()

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

const handleEnter = (e: KeyboardEvent) => {
  // 输入法组合输入过程中不触发登录
  if (e.isComposing) return
  handleSubmit()
}

const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true

  try {
    const res = await api.post('/auth/login', formData)

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
  } catch (error) {
    handleError(error, '账号或密码错误')
  } finally {
    loading.value = false
  }
}

const handleSSO = () => {
  Message.info('企业 SSO 登录功能开发中')
}

const contactAdmin = () => {
  Message.info('请联系系统管理员开通账号')
}

onMounted(() => {
  const rememberedUsername = localStorage.getItem('remembered_username')
  if (rememberedUsername) {
    formData.username = rememberedUsername
    formData.remember = true
  }
})

const handleForgotPassword = async () => {
  if (!forgotFormRef.value) return

  try {
    await forgotFormRef.value.validate()
  } catch {
    return
  }

  forgotLoading.value = true

  try {
    await api.post('/auth/forgot-password', forgotForm)
    Message.success('密码重置链接已发送到您的邮箱，请查收')
    forgotPasswordVisible.value = false
    forgotForm.username = ''
    forgotForm.email = ''
  } catch (error) {
    handleError(error, '发送失败，请稍后重试')
  } finally {
    forgotLoading.value = false
  }
}
</script>

<style scoped>
/* ==========================================
   设计令牌 — 对齐 prototype/css/login.css
   ========================================== */
.login-container {
  --bg: #f6f8fb;
  --panel: #ffffff;
  --ink: #0f172a;
  --muted: #475569;
  --line: #dbe3ef;
  --primary: #1d4ed8;
  --primary-hover: #2563eb;
  --shadow: 0 14px 40px rgba(15, 23, 42, 0.08), 0 2px 6px rgba(15, 23, 42, 0.04);
  --radius: 18px;
  --radius-sm: 12px;
}

.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--bg);
  padding: 20px;
}

/* ─── 登录框 ─── */
.login-box {
  display: grid;
  grid-template-columns: 480px 520px;
  max-width: 1000px;
  width: 100%;
  min-height: 600px;
  background: var(--panel);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  position: relative;
  z-index: 10;
}

/* ==========================================
   左侧品牌展示区
   ========================================== */
.login-brand {
  background:
    radial-gradient(circle at 20% 0%, rgba(37, 99, 235, 0.28), transparent 32%),
    linear-gradient(180deg, #111c33 0%, #0b1220 100%);
  color: #cbd5e1;
  padding: 48px 40px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.login-brand::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.15) 0%, transparent 60%);
  animation: brand-pulse 8s ease-in-out infinite;
  pointer-events: none;
}

@keyframes brand-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.5;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.8;
  }
}

.brand-header {
  position: relative;
  z-index: 1;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: linear-gradient(135deg, #3b82f6, #06b6d4);
  display: grid;
  place-items: center;
  color: white;
  font-weight: 900;
  font-size: 20px;
  box-shadow: 0 10px 28px rgba(37, 99, 235, 0.34);
  flex-shrink: 0;
}

.brand-identity {
  display: flex;
  flex-direction: column;
}

.brand-title {
  color: white;
  font-size: 24px;
  font-weight: 850;
  line-height: 1.2;
}

.brand-subtitle {
  color: #94a3b8;
  font-size: 13px;
  margin-top: 4px;
}

/* ─── 品牌内容（特性卡片）─── */
.brand-content {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 32px;
}

.feature-item {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.feature-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.15);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.feature-icon svg {
  width: 20px;
  height: 20px;
  stroke: #3b82f6;
  fill: none;
  stroke-width: 2;
}

.feature-text h3 {
  color: white;
  font-size: 15px;
  font-weight: 700;
  margin: 0 0 4px;
}

.feature-text p {
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
}

.brand-footer {
  position: relative;
  z-index: 1;
  color: #64748b;
  font-size: 12px;
  text-align: center;
}

/* ==========================================
   右侧登录表单区
   ========================================== */
.login-form-panel {
  padding: 48px 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: var(--panel);
}

.login-header {
  margin-bottom: 36px;
}

.login-welcome {
  font-size: 28px;
  font-weight: 800;
  color: var(--ink);
  margin: 0 0 8px;
}

.login-subtitle {
  color: var(--muted);
  font-size: 14px;
  margin: 0;
}

/* ─── Arco 表单覆盖 ─── */
:deep(.arco-form) {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

:deep(.arco-form-item) {
  margin-bottom: 0;
}

:deep(.arco-form-item-label) {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
}

:deep(.arco-input-wrapper),
:deep(.arco-input-inner-wrapper) {
  border-radius: var(--radius-sm);
  border: 1px solid var(--line);
  height: 46px;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

:deep(.arco-input-wrapper:hover),
:deep(.arco-input-inner-wrapper:hover) {
  border-color: var(--primary);
}

:deep(.arco-input-focus .arco-input-wrapper),
:deep(.arco-input-inner-wrapper:focus-within) {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
}

:deep(.arco-input) {
  font-size: 14px;
}

/* ─── 表单选项（记住我 / 忘记密码）─── */
.login-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  margin-top: -4px;
}

:deep(.arco-checkbox) {
  font-size: 13px;
  color: var(--muted);
}

.login-forgot {
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
}

.login-forgot:hover {
  color: var(--primary-hover);
}

/* ─── 主登录按钮 ─── */
.login-submit-btn {
  width: 100%;
  padding: 13px 20px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-stack);
  color: white;
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  box-shadow: 0 8px 20px rgba(29, 78, 216, 0.25);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  line-height: 1.45;
  height: 46px;
}

.login-submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 28px rgba(29, 78, 216, 0.35);
}

.login-submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.login-submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* 箭头图标：hover 位移效果 */
.btn-arrow {
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.login-submit-btn:hover:not(:disabled) .btn-arrow {
  transform: translateX(3px);
}

/* ─── 分隔线 ─── */
.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  font-size: 12px;
  margin: 12px 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--line);
}

/* ─── SSO 按钮 ─── */
.btn-sso {
  width: 100%;
  padding: 13px 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-stack);
  color: var(--ink);
  background: var(--bg);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  line-height: 1.45;
}

.btn-sso:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-sso:active {
  transform: scale(0.98);
}

/* ─── 登录底部 ─── */
.login-footer {
  margin-top: 32px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
}

.login-footer a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
  cursor: pointer;
}

.login-footer a:hover {
  color: var(--primary-hover);
}

/* ==========================================
   响应式
   ========================================== */
@media (max-width: 960px) {
  .login-box {
    grid-template-columns: 1fr;
    max-width: 520px;
  }

  .login-brand {
    padding: 32px 28px;
    min-height: 240px;
  }

  .brand-content {
    gap: 20px;
  }

  .feature-item:nth-child(n + 3) {
    display: none;
  }

  .brand-header .brand-logo {
    margin-bottom: 24px;
  }
}

@media (max-width: 640px) {
  .login-container {
    padding: 0;
  }

  .login-box {
    border-radius: 0;
    min-height: 100vh;
    max-width: 100%;
  }

  .login-form-panel {
    padding: 32px 24px;
  }

  .login-brand {
    padding: 28px 24px;
    min-height: 200px;
  }
}
</style>
