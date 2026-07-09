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
          <a-button type="primary" :loading="changePasswordLoading" @click="handleChangePassword">确定</a-button>
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
    Message.success('密码修改成功，请重新登录')
    changePasswordVisible.value = false
    // 这里可以触发登出逻辑
  } catch (e) {
    handleError(e)
  } finally {
    changePasswordLoading.value = false
  }
}

const goToProfile = () => {
  router.push('/profile')
}
</script>

<style scoped>
.dashboard-layout {
  min-height: 100vh;
  background: var(--cop-bg);
}

.mobile-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 25;
}

.main-content {
  margin-left: var(--cop-sidebar-width);
  min-height: 100vh;
  transition: margin-left var(--t-base);
  display: flex;
  flex-direction: column;
}

.main-content.sidebar-collapsed {
  margin-left: var(--cop-sidebar-collapsed-width);
}

.page-content {
  flex: 1;
  padding: 22px 24px 44px;
  background: var(--cop-bg);
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 0;
  }
  .main-content.sidebar-collapsed {
    margin-left: 0;
  }
  .page-content {
    padding: 16px;
  }
}
</style>