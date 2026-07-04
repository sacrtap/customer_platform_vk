<template>
  <div class="dashboard-layout">
    <AppSidebar @close-mobile="mobileMenuOpen = false" />

    <div v-if="mobileMenuOpen" class="mobile-overlay" @click="closeMobileMenu" />

    <main :class="['main-content', { 'sidebar-collapsed': sidebarCollapsed }]">
      <AppHeader
        @toggle-mobile="toggleMobileMenu"
        @profile="goToProfile"
        @change-password="showChangePasswordModal"
      />

      <div class="page-content">
        <router-view />
      </div>

      <!-- 修改密码对话框 -->
      <a-modal
        v-model:visible="changePasswordVisible"
        title="修改密码"
        :mask-closable="false"
        @ok="handleChangePassword"
        @cancel="changePasswordVisible = false"
      >
        <a-form ref="changePasswordFormRef" :model="changePasswordForm" layout="vertical">
          <a-form-item label="当前密码" field="current_password" :rules="[{ required: true, message: '请输入当前密码' }]">
            <a-input-password v-model="changePasswordForm.current_password" placeholder="请输入当前密码" size="large" />
          </a-form-item>
          <a-form-item
            label="新密码"
            field="new_password"
            :rules="[
              { required: true, message: '请输入新密码' },
              { minLength: 6, message: '密码长度不能少于 6 位' },
            ]"
          >
            <a-input-password v-model="changePasswordForm.new_password" placeholder="请输入新密码（至少 6 位）" size="large" />
          </a-form-item>
          <a-form-item
            label="确认新密码"
            field="confirm_password"
            :rules="[
              { required: true, message: '请再次输入新密码' },
              { validator: validateConfirmPassword, message: '两次输入的密码不一致' },
            ]"
          >
            <a-input-password v-model="changePasswordForm.confirm_password" placeholder="请再次输入新密码" size="large" />
          </a-form-item>
        </a-form>
        <template #footer>
          <a-button @click="changePasswordVisible = false">取消</a-button>
          <a-button type="primary" :loading="changePasswordLoading" @click="handleChangePassword">确认修改</a-button>
        </template>
      </a-modal>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'
import { changePassword } from '@/api/users'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import { useAppLayout } from '@/composables/useAppLayout'

const router = useRouter()
const { sidebarCollapsed, mobileMenuOpen, toggleMobileMenu, closeMobileMenu } = useAppLayout()

// ─── 修改密码 ───────────────────────────────────────────────────
const changePasswordVisible = ref(false)
const changePasswordFormRef = ref<FormInstance>()
const changePasswordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})
const changePasswordLoading = ref(false)

const validateConfirmPassword = (_value: string, callback: (error?: string) => void) => {
  if (changePasswordForm.new_password !== changePasswordForm.confirm_password) {
    callback('两次输入的密码不一致')
  } else {
    callback()
  }
}

const showChangePasswordModal = () => {
  changePasswordVisible.value = true
  changePasswordForm.current_password = ''
  changePasswordForm.new_password = ''
  changePasswordForm.confirm_password = ''
}

const handleChangePassword = async () => {
  if (!changePasswordFormRef.value) return
  try {
    await changePasswordFormRef.value.validate()
  } catch {
    return
  }
  changePasswordLoading.value = true
  try {
    await changePassword({
      current_password: changePasswordForm.current_password,
      new_password: changePasswordForm.new_password,
    })
    Message.success('密码修改成功')
    changePasswordVisible.value = false
  } catch (error) {
    handleError(error)
  } finally {
    changePasswordLoading.value = false
  }
}

const goToProfile = () => router.push('/profile')
</script>

<style scoped>
.dashboard-layout {
  --sidebar-width: 260px;
  --sidebar-collapsed-width: 68px;
  --header-height: 64px;
  --primary-1: #e8f3ff;
  --primary-5: #0369a1;
  --primary-6: #0f172a;
  --primary-7: #020617;
  --success-1: #e8ffea;
  --success-6: #22c55e;
  --warning-1: #fff7e8;
  --warning-6: #f59e0b;
  --danger-1: #ffe8e8;
  --danger-5: #f87171;
  --danger-6: #ef4444;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-9: #2f3645;
  --neutral-10: #1d2330;
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  min-height: 100vh;
  background: var(--neutral-1);
}

.main-content {
  margin-left: var(--sidebar-width);
  min-height: 100vh;
  transition: margin-left var(--transition-base);
  width: calc(100% - var(--sidebar-width));
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}

.main-content.sidebar-collapsed {
  margin-left: var(--sidebar-collapsed-width);
  width: calc(100% - var(--sidebar-collapsed-width));
}

.page-content {
  flex: 1;
  padding: 24px 32px;
  max-width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

.mobile-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}

@media (max-width: 1200px) {
  .mobile-overlay { display: block; }
  .main-content { margin-left: 0; width: 100%; }
  .main-content.sidebar-collapsed { margin-left: 0; width: 100%; }
}
</style>
