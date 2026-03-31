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
            <a-menu-item key="customers">客户管理</a-menu-item>
            <a-menu-item key="billing">结算管理</a-menu-item>
            <a-menu-item key="profiles">画像管理</a-menu-item>
            <a-menu-item key="analytics">客户分析</a-menu-item>
            <a-menu-item key="settings">系统设置</a-menu-item>
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

const handleMenuClick = (key: string) => {
  router.push(`/${key}`)
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
