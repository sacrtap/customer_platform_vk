<template>
  <header class="header">
    <div class="header-left">
      <button class="mobile-menu-btn" aria-label="打开菜单" @click="emit('toggle-mobile')">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
      </button>
      <h1 class="header-title">{{ pageTitle }}</h1>
      <div class="header-breadcrumb">
        <a @click="goHome">首页</a>
        <span>/</span>
        <span class="current">{{ pageTitle }}</span>
      </div>
    </div>
    <div class="header-right">
      <ActionButton label="消息通知" :badge="3" @click="handleNotification">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
      </ActionButton>
      <div class="header-divider"></div>
      <a-popover trigger="click" position="br" :content-style="{ padding: 0, borderRadius: '12px' }" :arrow-style="{ display: 'none' }">
        <div class="user-avatar-btn">
          <div v-if="currentUser?.avatar_url" class="user-avatar-img"><img :src="currentUser.avatar_url" :alt="currentUser.username" /></div>
          <div v-else class="user-avatar-text">{{ currentUser?.username?.charAt(0)?.toUpperCase() || 'U' }}</div>
        </div>
        <template #content>
          <div class="user-dropdown">
            <div class="dropdown-header">
              <div v-if="currentUser?.avatar_url" class="dropdown-avatar-img"><img :src="currentUser.avatar_url" :alt="currentUser.username" /></div>
              <div v-else class="dropdown-avatar">{{ currentUser?.username?.charAt(0)?.toUpperCase() || 'U' }}</div>
              <div class="dropdown-user-info">
                <div class="dropdown-user-name">{{ currentUser?.username || '用户' }}</div>
                <div class="dropdown-user-role">{{ currentUser?.roles?.[0] || '运营经理' }}</div>
              </div>
            </div>
            <div class="dropdown-menu">
              <div class="dropdown-item" @click="emit('profile')"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>个人信息</div>
              <div class="dropdown-item" @click="emit('change-password')"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>修改密码</div>
              <div class="dropdown-divider"></div>
              <div class="dropdown-item" @click="handleLogout"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>退出登录</div>
            </div>
          </div>
        </template>
      </a-popover>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useAppLayout } from '@/composables/useAppLayout'
import ActionButton from '@/components/ActionButton.vue'

const emit = defineEmits<{
  'toggle-mobile': []
  'profile': []
  'change-password': []
}>()
const router = useRouter()
const { pageTitle, currentUser, handleLogout: logout } = useAppLayout()
const goHome = () => router.push('/')
const handleNotification = () => Message.info('通知功能开发中')
const handleLogout = () => { logout() }
</script>

<style scoped>
.header { height: var(--header-height); background: #fff; border-bottom: 1px solid var(--neutral-2); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; position: sticky; top: 0; z-index: 50; }
.header-left { display: flex; align-items: center; gap: 20px; }
.header-title { font-size: 20px; font-weight: 700; color: var(--neutral-10); white-space: nowrap; }
.header-breadcrumb { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.header-breadcrumb a { color: var(--neutral-5); cursor: pointer; text-decoration: none; }
.header-breadcrumb a:hover { color: var(--primary-6); }
.header-breadcrumb .current { color: var(--neutral-7); font-weight: 500; }
.header-right { display: flex; align-items: center; gap: 12px; }
.header-divider { width: 1px; height: 24px; background: var(--neutral-2); margin: 0 4px; }
.mobile-menu-btn { display: none; width: 40px; height: 40px; border-radius: 10px; align-items: center; justify-content: center; color: var(--neutral-6); cursor: pointer; transition: background-color var(--t-fast), color var(--t-fast); border: none; background: transparent; }
.mobile-menu-btn:hover { background: var(--neutral-1); color: var(--neutral-9); }
.mobile-menu-btn svg { width: 24px; height: 24px; }
.user-avatar-btn { width: 40px; height: 40px; border-radius: 50%; cursor: pointer; transition: all var(--t-fast); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.user-avatar-btn:hover { box-shadow: 0 0 0 3px rgba(3,105,161,.2); }
.user-avatar-img { width: 100%; height: 100%; }
.user-avatar-img img { width: 100%; height: 100%; object-fit: cover; }
.user-avatar-text { width: 100%; height: 100%; background: linear-gradient(135deg,#0369a1,#0284c7); display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 600; font-size: 16px; border-radius: 50%; }
.user-dropdown { width: 240px; }
.dropdown-header { padding: 16px; display: flex; align-items: center; gap: 12px; background: var(--neutral-1); border-bottom: 1px solid var(--neutral-2); }
.dropdown-avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg,#0369a1,#0284c7); display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 600; font-size: 16px; flex-shrink: 0; }
.dropdown-avatar-img { width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0; overflow: hidden; }
.dropdown-avatar-img img { width: 100%; height: 100%; object-fit: cover; }
.dropdown-user-info { flex: 1; overflow: hidden; }
.dropdown-user-name { font-size: 14px; font-weight: 600; color: var(--neutral-10); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dropdown-user-role { font-size: 12px; color: var(--neutral-5); margin-top: 2px; }
.dropdown-menu { padding: 8px; }
.dropdown-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 8px; font-size: 13px; color: var(--neutral-7); cursor: pointer; transition: background-color var(--t-fast); }
.dropdown-item:hover { background: var(--neutral-1); color: var(--neutral-10); }
.dropdown-divider { height: 1px; background: var(--neutral-2); margin: 8px 0; }
@media (max-width:1200px) { .mobile-menu-btn { display: flex; } .header-breadcrumb { display: none; } }
</style>
