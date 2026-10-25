<template>
  <div :class="['shell', { collapsed: sidebarCollapsed }]">
    <AppSidebar @close-mobile="mobileMenuOpen = false" />

    <div v-if="mobileMenuOpen" class="mobile-overlay" @click="closeMobileMenu" />

    <div class="main">
      <AppHeader
        @toggle-mobile="toggleMobileMenu"
        @profile="goToProfile"
        @change-password="showChangePasswordModal"
      />

      <div class="page">
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
          <a-form-item
            label="当前密码"
            field="current_password"
            :rules="[{ required: true, message: '请输入当前密码' }]"
          >
            <a-input-password
              v-model="changePasswordForm.current_password"
              placeholder="请输入当前密码"
              size="large"
            />
          </a-form-item>
          <a-form-item
            label="新密码"
            field="new_password"
            :rules="[
              { required: true, message: '请输入新密码' },
              { minLength: 6, message: '密码长度不能少于 6 位' },
            ]"
          >
            <a-input-password
              v-model="changePasswordForm.new_password"
              placeholder="请输入新密码（至少 6 位）"
              size="large"
            />
          </a-form-item>
          <a-form-item
            label="确认新密码"
            field="confirm_password"
            :rules="[
              { required: true, message: '请再次输入新密码' },
              { validator: validateConfirmPassword, message: '两次输入的密码不一致' },
            ]"
          >
            <a-input-password
              v-model="changePasswordForm.confirm_password"
              placeholder="请再次输入新密码"
              size="large"
            />
          </a-form-item>
        </a-form>
        <template #footer>
          <a-button @click="changePasswordVisible = false">取消</a-button>
          <a-button type="primary" :loading="changePasswordLoading" @click="handleChangePassword"
            >确认修改</a-button
          >
        </template>
      </a-modal>

      <!-- 系统升级公告弹窗（存在未读部署时自动弹出） -->
      <UpgradeAnnouncementModal
        v-model:visible="upgradeVisible"
        :updates="upgradeUpdates"
        @close="handleUpgradeClose"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'
import { changePassword } from '@/api/users'
import { getSystemUpdates, type DeployUpdate } from '@/api/system'
import { useUserStore } from '@/stores/user'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import UpgradeAnnouncementModal from '@/components/system/UpgradeAnnouncementModal.vue'
import { useAppLayout } from '@/composables/useAppLayout'

const router = useRouter()
const { sidebarCollapsed, mobileMenuOpen, toggleMobileMenu, closeMobileMenu } = useAppLayout()
const userStore = useUserStore()

// ─── 系统升级公告 ─────────────────────────────────────────────────
// 已读按「用户 × 浏览器」维度记录最近一次展示的部署时间（ISO UTC 词法可比较），
// 避免每次登录重复打扰；关闭弹框即写入。
const upgradeReadKey = () => `upgrade_announcement_last_read_${userStore.userInfo?.id}`
const upgradeVisible = ref(false)
const upgradeUpdates = ref<DeployUpdate[]>([])
// 组件卸载后 onMounted 的出站请求可能才返回：此时再置 visible 会打开一个已随
// Dashboard 卸载的弹窗（Arco modal Teleport 到 body，不随路由切换销毁），
// 其全屏遮罩会拦截目标页面的全部指针事件。故用标记在回调里守住。
let upgradeUnmounted = false
let upgradeLoadHandler: (() => void) | null = null
onBeforeUnmount(() => {
  upgradeUnmounted = true
  if (upgradeLoadHandler) {
    window.removeEventListener('load', upgradeLoadHandler)
    upgradeLoadHandler = null
  }
})

onMounted(() => {
  const uid = userStore.userInfo?.id
  if (!uid) return
  // 公告是增强信息，不得拖慢首屏：等到浏览器 load 事件后再发起出站请求。
  // 在 onMounted 里直接 await 会占用首屏加载期，使首页 load 事件被外部 API
  // 往返（GitHub 匿名请求可达数秒）拖住，连带所有以 load 为等待条件的流程。
  const start = () => {
    void (async () => {
      try {
        const res = await getSystemUpdates()
        if (upgradeUnmounted) return
        const updates: DeployUpdate[] = res.data?.updates || []
        if (!updates.length) return
        const lastRead = localStorage.getItem(upgradeReadKey())
        const latest = updates[0].deployed_at
        if (!lastRead || latest > lastRead) {
          upgradeUpdates.value = updates
          upgradeVisible.value = true
        }
      } catch {
        // 接口失败静默降级：不打扰用户
      }
    })()
  }
  if (document.readyState === 'complete') {
    start()
  } else {
    upgradeLoadHandler = start
    window.addEventListener('load', start, { once: true })
  }
})

const handleUpgradeClose = () => {
  if (userStore.userInfo?.id && upgradeUpdates.value.length) {
    localStorage.setItem(upgradeReadKey(), upgradeUpdates.value[0].deployed_at)
  }
  upgradeVisible.value = false
}

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
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 189px 1fr;
  transition: grid-template-columns 0.25s ease;
  background: var(--bg);
}

.shell.collapsed {
  grid-template-columns: 72px 1fr;
}

.main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.page {
  flex: 1;
  padding: 22px 24px 44px;
  max-width: 1440px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
  overflow-x: hidden;
}

.mobile-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}

@media (max-width: 1100px) {
  .shell,
  .shell.collapsed {
    grid-template-columns: 1fr;
  }

  .mobile-overlay {
    display: block;
  }
}

@media (max-width: 640px) {
  .page {
    padding: 16px;
  }
}
</style>
