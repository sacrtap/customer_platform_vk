<template>
  <div class="reset-container">
    <div class="reset-box">
      <div class="reset-header">
        <div class="reset-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
        </div>
        <h1 class="reset-title">重置密码</h1>
        <p class="reset-desc">请输入您的新密码，完成后即可使用新密码登录系统</p>
      </div>

      <a-form ref="formRef" layout="vertical" :model="formData" @submit="handleSubmit">
        <a-form-item
          field="new_password"
          label="新密码"
          :rules="[
            { required: true, message: '请输入新密码' },
            { minLength: 6, message: '密码长度不能少于 6 位' },
          ]"
        >
          <a-input-password
            v-model="formData.new_password"
            placeholder="请输入新密码（至少 6 位）"
            size="large"
            :disabled="loading"
            allow-clear
          />
          <!-- 密码强度指示器 -->
          <div v-if="formData.new_password" class="password-strength">
            <div class="strength-bar">
              <div class="strength-fill" :class="passwordStrength.level" :style="{ width: passwordStrength.percent + '%' }" />
            </div>
            <span class="strength-label" :class="passwordStrength.level">{{ passwordStrength.text }}</span>
          </div>
          <!-- 密码要求清单 -->
          <div v-if="formData.new_password" class="password-requirements">
            <div class="req-item" :class="{ met: reqs.length }">
              <span class="req-icon">{{ reqs.length ? '✓' : '○' }}</span> 至少 6 位
            </div>
            <div class="req-item" :class="{ met: reqs.uppercase }">
              <span class="req-icon">{{ reqs.uppercase ? '✓' : '○' }}</span> 含大写字母
            </div>
            <div class="req-item" :class="{ met: reqs.number }">
              <span class="req-icon">{{ reqs.number ? '✓' : '○' }}</span> 含数字
            </div>
            <div class="req-item" :class="{ met: reqs.special }">
              <span class="req-icon">{{ reqs.special ? '✓' : '○' }}</span> 含特殊字符
            </div>
          </div>
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
            class="btn-primary"
          >
            重置密码
          </a-button>
        </a-form-item>
      </a-form>

      <div class="reset-footer">
        <router-link to="/login" class="link">← 返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
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

// 密码强度计算
const passwordStrength = computed(() => {
  const pwd = formData.new_password
  if (!pwd) return { level: '', percent: 0, text: '' }
  let score = 0
  if (pwd.length >= 6) score++
  if (pwd.length >= 10) score++
  if (/[A-Z]/.test(pwd)) score++
  if (/[0-9]/.test(pwd)) score++
  if (/[^A-Za-z0-9]/.test(pwd)) score++
  if (score <= 2) return { level: 'weak', percent: 33, text: '弱' }
  if (score <= 3) return { level: 'medium', percent: 66, text: '中' }
  return { level: 'strong', percent: 100, text: '强' }
})

// 密码要求实时校验
const reqs = computed(() => ({
  length: formData.new_password.length >= 6,
  uppercase: /[A-Z]/.test(formData.new_password),
  number: /[0-9]/.test(formData.new_password),
  special: /[^A-Za-z0-9]/.test(formData.new_password),
}))

const validatePasswordMatch = (value: string | undefined) => {
  return value === formData.new_password
}

const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

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

    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err: unknown) {
    const errorMessage = (err as Error)?.message
    Message.error(errorMessage || '重置失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.reset-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  padding: 20px;
}

.reset-box {
  width: 100%;
  max-width: 480px;
  background: var(--panel);
  border-radius: var(--radius);
  padding: 48px 40px;
  box-shadow: var(--shadow);
}

.reset-header {
  text-align: center;
  margin-bottom: 32px;
}

.reset-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: rgba(29, 78, 216, .10);
  display: grid;
  place-items: center;
  color: var(--primary);
  margin: 0 auto 20px;
}

.reset-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 8px;
}

.reset-desc {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 24px;
}

/* ─── 表单样式 ─── */
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

:deep(.arco-input-inner-wrapper) {
  border-radius: var(--radius-sm);
  border: 1px solid var(--line);
  height: 46px;
  transition: all .2s ease;
}

:deep(.arco-input-inner-wrapper:hover) {
  border-color: var(--primary);
}

:deep(.arco-input-inner-wrapper:focus-within) {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, .1);
}

/* ─── 主按钮 ─── */
.btn-primary {
  width: 100%;
  height: 46px;
  border: none !important;
  border-radius: var(--radius-sm) !important;
  font-size: 14px;
  font-weight: 600;
  background: linear-gradient(135deg, #1D4ED8, #2563EB) !important;
  color: white !important;
  box-shadow: 0 8px 20px rgba(29, 78, 216, .25) !important;
  transition: all .2s ease;
  cursor: pointer;
}

.btn-primary:hover {
  border: none !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 12px 28px rgba(29, 78, 216, .35) !important;
  background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
  color: white !important;
}

.btn-primary:active {
  transform: translateY(0) !important;
}

/* ─── 底部 ─── */
.reset-footer {
  margin-top: 24px;
  text-align: center;
}

.link {
  color: var(--primary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color .2s ease;
}

.link:hover {
  color: #2563EB;
}

@media (max-width: 640px) {
  .reset-container {
    padding: 0;
  }

  .reset-box {
    border-radius: 0;
    min-height: 100vh;
    padding: 32px 24px;
  }
}
/* 密码强度指示器 */
.password-strength {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.strength-bar {
  flex: 1;
  height: 4px;
  background: #E2E8F0;
  border-radius: 2px;
  overflow: hidden;
}
.strength-fill {
  height: 100%;
  border-radius: 2px;
  transition: width .3s ease, background .3s ease;
}
.strength-fill.weak { background: #DC2626; }
.strength-fill.medium { background: #D97706; }
.strength-fill.strong { background: #059669; }
.strength-label { font-size: 12px; font-weight: 600; }
.strength-label.weak { color: #DC2626; }
.strength-label.medium { color: #D97706; }
.strength-label.strong { color: #059669; }

/* 密码要求清单 */
.password-requirements {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}
.req-item {
  display: flex;
  align-items: center;
  gap: 2px;
}
.req-item.met {
  color: #059669;
}
.req-icon {
  font-weight: 700;
  margin-right: 4px;
}
.req-item.met .req-icon {
  color: #059669;
}
</style>
