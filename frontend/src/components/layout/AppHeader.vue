<template>
  <header class="header">
    <div class="header-left">
      <button class="mobile-menu-btn" aria-label="打开菜单" @click="emit('toggle-mobile')">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <h1 class="header-title">{{ pageTitle }}</h1>
      <div class="header-breadcrumb">
        <a @click="goHome">首页</a>
        <span>/</span>
        <span class="current">{{ pageTitle }}</span>
      </div>
    </div>
    <div class="header-center">
      <div class="global-search">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" class="search-icon">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input type="search" placeholder="全局搜索..." class="search-input" aria-label="全局搜索" />
      </div>
    </div>
    <div class="header-right">
      <div class="status-pills">
        <span class="status-pill sync">
          <span class="status-dot sync" />
          <span>同步中</span>
        </span>
        <span class="status-pill warning">
          <span class="status-dot warning" />
          <span>3 预警</span>
        </span>
      </div>
      <div class="header-divider"></div>
      <a-popover trigger="click" position="br" :content-style="{ padding: 0, borderRadius: '12px' }" :arrow-style="{ display: 'none' }">
        <div class="user-avatar-btn">
          <div v-if="currentUser?.avatar_url" class="user-avatar-img">
            <img :src="currentUser.avatar_url" :alt="currentUser.username" />
          </div>
          <div v-else class="user-avatar-text">{{ currentUser?.username?.charAt(0)?.toUpperCase() || 'U' }}</div>
        </div>
        <template #content>
          <div class="user-dropdown">
            <div class="dropdown-header">
              <div v-if="currentUser?.avatar_url" class="dropdown-avatar-img">
                <img :src="currentUser.avatar_url" :alt="currentUser.username" />
              </div>
              <div v-else class="dropdown-avatar-text">{{ currentUser?.username?.charAt(0)?.toUpperCase() || 'U' }}</div>
              <div class="dropdown-user-info">
                <div class="dropdown-user-name">{{ currentUser?.username || '用户' }}</div>
                <div class="dropdown-user-role">{{ currentUser?.role_name || '运营专员' }}</div>
              </div>
            </div>
            <div class="dropdown-divider"></div>
            <div class="dropdown-menu">
              <a class="dropdown-item" @click="goProfile">
                <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                个人中心
              </a>
              <a class="dropdown-item" @click="goChangePassword">
                <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                修改密码
              </a>
              <div class="dropdown-divider"></div>
              <button class="dropdown-item logout" @click="handleLogout">
                <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                退出登录
              </button>
            </div>
          </div>
        </template>
      </a-popover>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAppLayout } from '@/composables/useAppLayout'

const emit = defineEmits<{
  'toggle-mobile': []
  'profile': []
  'change-password': []
}>()

const router = useRouter()
const { pageTitle, currentUser, handleLogout: logout } = useAppLayout()

const goHome = () => router.push('/')
const goProfile = () => {
  emit('profile')
  router.push('/profile')
}
const goChangePassword = () => {
  emit('change-password')
}
const handleLogout = () => { logout() }
</script>

<style scoped>
.header {
  height: var(--cop-header-height);
  background: var(--cop-panel);
  border-bottom: 1px solid var(--cop-line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 50;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}
.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
  max-width: 600px;
  margin: 0 32px;
}
.global-search {
  position: relative;
  width: 100%;
  max-width: 480px;
}
.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 18px;
  color: var(--cop-muted);
  pointer-events: none;
}
.search-input {
  width: 100%;
  height: 40px;
  padding: 0 16px 0 44px;
  border: 1px solid var(--cop-line);
  border-radius: var(--cop-radius-sm);
  background: var(--cop-bg);
  color: var(--cop-ink);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.search-input:focus {
  border-color: var(--cop-primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.12);
  background: var(--cop-panel);
}
.search-input::placeholder {
  color: var(--cop-muted);
}
.header-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--cop-ink);
  white-space: nowrap;
}
.header-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.header-breadcrumb a {
  color: var(--cop-muted);
  cursor: pointer;
  text-decoration: none;
}
.header-breadcrumb a:hover {
  color: var(--cop-primary);
}
.header-breadcrumb .current {
  color: var(--cop-muted);
  font-weight: 500;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-divider {
  width: 1px;
  height: 24px;
  background: var(--cop-line);
  margin: 0 4px;
}
.mobile-menu-btn {
  display: none;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  align-items: center;
  justify-content: center;
  color: var(--cop-muted);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s;
  border: none;
  background: transparent;
}
.mobile-menu-btn:hover {
  background: var(--cop-bg);
  color: var(--cop-ink);
}
.mobile-menu-btn svg {
  width: 24px;
  height: 24px;
}
.user-avatar-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  overflow: hidden;
  border: 2px solid transparent;
  transition: border-color 0.15s;
}
.user-avatar-btn:hover {
  border-color: var(--cop-primary);
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
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--cop-primary), var(--cop-cyan));
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}
.status-pills {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.status-pill.sync {
  background: rgba(29, 78, 216, 0.1);
  color: var(--cop-primary);
}
.status-pill.warning {
  background: rgba(217, 119, 6, 0.1);
  color: var(--cop-warning);
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  animation: pulse 2s infinite;
}
.status-dot.sync {
  background: var(--cop-primary);
}
.status-dot.warning {
  background: var(--cop-warning);
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.user-dropdown {
  min-width: 220px;
}
.dropdown-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--cop-bg);
  border-bottom: 1px solid var(--cop-line);
}
.dropdown-avatar-img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
}
.dropdown-avatar-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dropdown-avatar-text {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--cop-primary), var(--cop-cyan));
  color: #fff;
  font-weight: 600;
  font-size: 16px;
}
.dropdown-user-info {
  flex: 1;
  min-width: 0;
}
.dropdown-user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--cop-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dropdown-user-role {
  font-size: 12px;
  color: var(--cop-muted);
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
  color: var(--cop-muted);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s;
  text-decoration: none;
}
.dropdown-item:hover {
  background: var(--cop-bg);
  color: var(--cop-ink);
}
.dropdown-divider {
  height: 1px;
  background: var(--cop-line);
  margin: 8px 0;
}
.dropdown-item.logout {
  color: var(--cop-danger);
}
.dropdown-item.logout:hover {
  background: rgba(220, 38, 38, 0.1);
  color: var(--cop-danger);
}
@media (max-width: 1200px) {
  .mobile-menu-btn { display: flex; }
  .header-breadcrumb { display: none; }
  .header-center { display: none; }
}
</style>