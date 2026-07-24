<template>
  <header class="top">
    <button class="mobile-menu-btn" aria-label="打开菜单" @click="emit('toggle-mobile')">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M4 6h16M4 12h16M4 18h16"
        />
      </svg>
    </button>

    <div class="search" role="search" aria-label="全局搜索">
      <svg
        aria-hidden="true"
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
      <input
        ref="searchInputRef"
        v-model="searchQuery"
        placeholder="搜索客户、结算单、报表…（按 / 聚焦）"
        @keydown.enter="handleSearch"
      />
    </div>

    <div class="header-right">
      <ActionButton label="消息通知" :badge="3" @click="handleNotification">
        <svg
          aria-hidden="true"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
      </ActionButton>
      <div class="header-divider"></div>
      <a-popover
        trigger="click"
        position="br"
        :content-style="{ padding: 0, borderRadius: '12px' }"
        :arrow-style="{ display: 'none' }"
      >
        <div class="user-avatar-btn">
          <div v-if="currentUser?.avatar_url" class="user-avatar-img">
            <img :src="currentUser.avatar_url" :alt="currentUser.username" />
          </div>
          <div v-else class="user-avatar-text">
            {{ currentUser?.username?.charAt(0)?.toUpperCase() || 'U' }}
          </div>
        </div>
        <template #content>
          <div class="user-dropdown">
            <div class="dropdown-header">
              <div v-if="currentUser?.avatar_url" class="dropdown-avatar-img">
                <img :src="currentUser.avatar_url" :alt="currentUser.username" />
              </div>
              <div v-else class="dropdown-avatar">
                {{ currentUser?.username?.charAt(0)?.toUpperCase() || 'U' }}
              </div>
              <div class="dropdown-user-info">
                <div class="dropdown-user-name">{{ currentUser?.username || '用户' }}</div>
                <div class="dropdown-user-role">{{ currentUser?.roles?.[0] || '运营经理' }}</div>
              </div>
            </div>
            <div class="dropdown-menu">
              <div class="dropdown-item" @click="emit('profile')">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  /></svg
                >个人信息
              </div>
              <div class="dropdown-item" @click="emit('change-password')">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                  /></svg
                >修改密码
              </div>
              <div class="dropdown-divider"></div>
              <div class="dropdown-item" @click="handleLogout">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  /></svg
                >退出登录
              </div>
            </div>
          </div>
        </template>
      </a-popover>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useAppLayout } from '@/composables/useAppLayout'
import ActionButton from '@/components/ActionButton.vue'

const emit = defineEmits<{
  'toggle-mobile': []
  profile: []
  'change-password': []
}>()

const { currentUser, handleLogout: logout } = useAppLayout()
const handleNotification = () => Message.info('通知功能开发中')
const handleLogout = () => {
  logout()
}

// ─── 搜索框 ───────────────────────────────────────────────────
const searchQuery = ref('')
const searchInputRef = ref<HTMLInputElement>()

const handleSearch = () => {
  if (searchQuery.value.trim()) {
    Message.info(`搜索「${searchQuery.value}」功能开发中`)
  }
}

// 键盘快捷键 "/" 聚焦搜索框
const handleKeydown = (e: KeyboardEvent) => {
  if (
    e.key === '/' &&
    document.activeElement?.tagName !== 'INPUT' &&
    document.activeElement?.tagName !== 'TEXTAREA'
  ) {
    e.preventDefault()
    searchInputRef.value?.focus()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.top {
  position: sticky;
  top: 0;
  z-index: 5;
  background: rgba(246, 248, 251, 0.86);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(219, 227, 239, 0.8);
  padding: 14px 24px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  background: white;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 10px 12px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  color: var(--muted);
  max-width: 480px;
}

.search:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
}

.search input {
  border: 0;
  outline: 0;
  width: 100%;
  font: inherit;
  color: var(--ink);
  background: transparent;
}

.search input::placeholder {
  color: var(--muted);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.header-divider {
  width: 1px;
  height: 24px;
  background: var(--line);
  margin: 0 4px;
}

.mobile-menu-btn {
  display: none;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  cursor: pointer;
  transition:
    background-color var(--transition-fast),
    color var(--transition-fast);
  border: none;
  background: transparent;
}

.mobile-menu-btn:hover {
  background: var(--bg);
  color: var(--ink);
}

.mobile-menu-btn svg {
  width: 24px;
  height: 24px;
}

.user-avatar-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

.user-avatar-btn:hover {
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.2);
}

.user-avatar-img {
  width: 100%;
  height: 100%;
}

.user-avatar-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar-text {
  width: 100%;
  height: 100%;
  background: #dbeafe;
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 14px;
  border-radius: 50%;
}

.user-dropdown {
  width: 240px;
}

.dropdown-header {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg);
  border-bottom: 1px solid var(--line);
}

.dropdown-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #dbeafe;
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 16px;
  flex-shrink: 0;
}

.dropdown-avatar-img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
  overflow: hidden;
}

.dropdown-avatar-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dropdown-user-info {
  flex: 1;
  overflow: hidden;
}

.dropdown-user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-user-role {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.dropdown-menu {
  padding: 8px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.dropdown-item:hover {
  background: var(--bg);
  color: var(--ink);
}

.dropdown-divider {
  height: 1px;
  background: var(--line);
  margin: 8px 0;
}

@media (max-width: 1100px) {
  .mobile-menu-btn {
    display: flex;
  }
}

@media (max-width: 640px) {
  .top {
    padding: 12px;
    flex-wrap: wrap;
  }

  .search {
    order: 3;
    flex-basis: 100%;
    max-width: none;
  }
}
</style>
