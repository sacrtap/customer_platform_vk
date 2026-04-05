<template>
  <div class="dashboard">
    <a-layout>
      <a-layout-header class="header">
        <div class="logo">客户运营中台</div>
        <div class="user-info">
          <a-dropdown>
            <a-avatar :size="32">{{ userStore.userInfo?.username?.charAt(0)?.toUpperCase() }}</a-avatar>
            <template #content>
              <a-doption @click="handleLogout">退出登录</a-doption>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>
      <a-layout>
        <a-layout-sider :width="200" class="sider">
          <a-menu :default-selected-keys="['dashboard']" @menu-item-click="handleMenuClick">
            <a-menu-item key="dashboard">首页</a-menu-item>
            <a-menu-item v-if="can('customers:manage')" key="customers">客户管理</a-menu-item>
            <a-menu-item v-if="can('tags:manage')" key="tags">标签管理</a-menu-item>
            <a-sub-menu v-if="can('billing:manage')" key="billing" title="结算管理">
              <a-menu-item key="billing/balances">余额管理</a-menu-item>
              <a-menu-item key="billing/pricing-rules">定价规则</a-menu-item>
            </a-sub-menu>
            <a-sub-menu v-if="can('users:manage') || can('roles:manage')" key="admin" title="系统设置">
              <a-menu-item v-if="can('users:manage')" key="users">平台账号管理</a-menu-item>
              <a-menu-item v-if="can('roles:manage')" key="roles">角色权限管理</a-menu-item>
            </a-sub-menu>
            <a-sub-menu v-if="can('system:view')" key="system" title="系统管理">
              <a-menu-item key="system/sync-logs">同步任务日志</a-menu-item>
              <a-menu-item key="system/audit-logs">审计日志</a-menu-item>
            </a-sub-menu>
          </a-menu>
        </a-layout-sider>
        <a-layout-content class="content">
          <router-view />
        </a-layout-content>
      </a-layout>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const can = (permission: string) => userStore.hasPermission(permission)

const handleMenuClick = (key: string) => {
  if (key === 'dashboard') {
    router.push('/')
  } else {
    router.push(`/${key}`)
  }
}

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.dashboard {
  height: 100vh;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #165dff;
  color: white;
  padding: 0 20px;
}

.logo {
  font-size: 18px;
  font-weight: bold;
}

.user-info {
  cursor: pointer;
}

.sider {
  background: white;
}

.content {
  margin: 16px;
  padding: 20px;
  background: white;
  border-radius: 4px;
}
</style>
