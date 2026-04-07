<template>
  <div class="dashboard-layout">
    <!-- 侧边栏 -->
    <aside :class="['sidebar', { collapsed: sidebarCollapsed, 'mobile-open': mobileMenuOpen }]">
      <div class="sidebar-logo">
        <div class="logo-icon">
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
              d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
            />
          </svg>
        </div>
        <span class="logo-text">Customer Platform VK</span>
      </div>

      <nav class="sidebar-nav">
        <!-- 核心功能 -->
        <div class="nav-section">
          <div class="nav-section-title">核心功能</div>

           <a class="nav-item" :class="{ active: $route.path === '/' }" @click="$router.push('/')">
            <div class="nav-item-icon">
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
                  d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
                />
              </svg>
            </div>
            <span class="nav-item-label">仪表盘</span>
          </a>

          <a
            v-if="can('customers:manage')"
            class="nav-item"
            :class="{ active: $route.path.startsWith('/customers') }"
            @click="$router.push('/customers')"
          >
            <div class="nav-item-icon">
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
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
            </div>
            <span class="nav-item-label">客户管理</span>
          </a>

          <div
            class="nav-item nav-item-wrapper"
            :class="{ 
              expanded: expandedSubmenu === 'billing',
              'parent-active': isParentMenuActive('billing')
            }"
            @click="toggleSubmenu('billing')"
            @mouseenter="handleSubmenuHover('billing')"
            @mouseleave="handleSubmenuHover(null)"
          >
            <div class="nav-item-icon">
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
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <span class="nav-item-label">结算管理</span>
            <span v-if="false" class="nav-item-badge">5</span>
            <svg
              class="nav-item-arrow"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
            
            <!-- 收起模式下的子菜单悬浮预览 -->
            <div v-if="sidebarCollapsed" class="submenu-popup">
              <a
                class="nav-subitem"
                :class="{ active: $route.name === 'Balance' }"
                @click="$router.push('/billing/balances')"
                >余额管理</a
              >
              <a
                class="nav-subitem"
                :class="{ active: $route.name === 'PricingRules' }"
                @click="$router.push('/billing/pricing-rules')"
                >计费规则</a
              >
            </div>
          </div>
          <div v-show="expandedSubmenu === 'billing' && !sidebarCollapsed" class="nav-submenu">
            <a
              class="nav-subitem"
              :class="{ active: $route.name === 'Balance' }"
              @click="$router.push('/billing/balances')"
              >余额管理</a
            >
            <a
              class="nav-subitem"
              :class="{ active: $route.name === 'PricingRules' }"
              @click="$router.push('/billing/pricing-rules')"
              >计费规则</a
            >
          </div>

          <a
            v-if="can('profiles:manage')"
            class="nav-item"
            :class="{ active: $route.path.startsWith('/profiles') }"
            @click="$router.push('/profiles')"
          >
            <div class="nav-item-icon">
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
                  d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                />
              </svg>
            </div>
            <span class="nav-item-label">画像管理</span>
          </a>

          <div
            class="nav-item nav-item-wrapper"
            :class="{ 
              expanded: expandedSubmenu === 'analytics',
              'parent-active': isParentMenuActive('analytics')
            }"
            @click="toggleSubmenu('analytics')"
            @mouseenter="handleSubmenuHover('analytics')"
            @mouseleave="handleSubmenuHover(null)"
          >
            <div class="nav-item-icon">
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
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <span class="nav-item-label">客户分析</span>
            <svg
              class="nav-item-arrow"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
          <div v-if="expandedSubmenu === 'analytics' || isParentMenuActive('analytics')" class="nav-submenu">
            <a
              class="nav-subitem"
              :class="{ active: $route.path === '/analytics/consumption' }"
              @click="$router.push('/analytics/consumption')"
            >
              消耗分析
            </a>
            <a
              class="nav-subitem"
              :class="{ active: $route.path === '/analytics/payment' }"
              @click="$router.push('/analytics/payment')"
            >
              回款分析
            </a>
            <a
              class="nav-subitem"
              :class="{ active: $route.path === '/analytics/health' }"
              @click="$router.push('/analytics/health')"
            >
              健康度分析
            </a>
            <a
              class="nav-subitem"
              :class="{ active: $route.path === '/analytics/profile' }"
              @click="$router.push('/analytics/profile')"
            >
              画像分析
            </a>
            <a
              class="nav-subitem"
              :class="{ active: $route.path === '/analytics/forecast' }"
              @click="$router.push('/analytics/forecast')"
            >
              预测回款
            </a>
          </div>
        </div>

        <!-- 系统管理 -->
        <div class="nav-section">
          <div class="nav-section-title">系统管理</div>

          <a
            v-if="can('users:manage')"
            class="nav-item"
            :class="{ active: $route.path.startsWith('/users') }"
            @click="$router.push('/users')"
          >
            <div class="nav-item-icon">
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
                  d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                />
              </svg>
            </div>
            <span class="nav-item-label">用户管理</span>
          </a>

          <a
            v-if="can('roles:manage')"
            class="nav-item"
            :class="{ active: $route.path.startsWith('/roles') }"
            @click="$router.push('/roles')"
          >
            <div class="nav-item-icon">
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
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
            </div>
            <span class="nav-item-label">角色权限</span>
          </a>

          <a
            v-if="can('tags:manage')"
            class="nav-item"
            :class="{ active: $route.path.startsWith('/tags') }"
            @click="$router.push('/tags')"
          >
            <div class="nav-item-icon">
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
                  d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                />
              </svg>
            </div>
            <span class="nav-item-label">标签管理</span>
          </a>

          <div
            class="nav-item nav-item-wrapper"
            :class="{ 
              expanded: expandedSubmenu === 'system',
              'parent-active': isParentMenuActive('system')
            }"
            @click="toggleSubmenu('system')"
            @mouseenter="handleSubmenuHover('system')"
            @mouseleave="handleSubmenuHover(null)"
          >
            <div class="nav-item-icon">
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
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </div>
            <span class="nav-item-label">系统设置</span>
            <svg
              class="nav-item-arrow"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
            
            <!-- 收起模式下的子菜单悬浮预览 -->
            <div v-if="sidebarCollapsed" class="submenu-popup">
              <a
                v-if="can('system:view')"
                class="nav-subitem"
                :class="{ active: $route.name === 'SyncLogs' }"
                @click="$router.push('/system/sync-logs')"
                >同步日志</a
              >
              <a
                v-if="can('system:view')"
                class="nav-subitem"
                :class="{ active: $route.name === 'AuditLogs' }"
                @click="$router.push('/system/audit-logs')"
                >审计日志</a
              >
            </div>
          </div>
          <div v-show="expandedSubmenu === 'system' && !sidebarCollapsed" class="nav-submenu">
            <a
              v-if="can('system:view')"
              class="nav-subitem"
              :class="{ active: $route.name === 'SyncLogs' }"
              @click="$router.push('/system/sync-logs')"
              >同步日志</a
            >
            <a
              v-if="can('system:view')"
              class="nav-subitem"
              :class="{ active: $route.name === 'AuditLogs' }"
              @click="$router.push('/system/audit-logs')"
              >审计日志</a
            >
          </div>
        </div>
      </nav>

      <!-- 用户信息 -->
      <div class="sidebar-user">
        <div class="sidebar-user-info">
          <div class="user-avatar">
            {{ userStore.userInfo?.username?.charAt(0)?.toUpperCase() || 'U' }}
          </div>
          <div class="user-info">
            <div class="user-name">{{ userStore.userInfo?.username || '用户' }}</div>
            <div class="user-role">{{ userStore.userInfo?.roles?.[0] || '运营经理' }}</div>
          </div>
        </div>
        <div class="sidebar-toggle" @click="toggleSidebar">
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
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </div>
      </div>
    </aside>

    <!-- 移动端遮罩层 -->
    <div v-if="mobileMenuOpen" class="mobile-overlay" @click="mobileMenuOpen = false" />

    <!-- 主内容区 -->
    <main :class="['main-content', { 'sidebar-collapsed': sidebarCollapsed }]">
      <!-- 顶部栏 -->
      <header class="header">
        <div class="header-left">
          <button class="mobile-menu-btn" aria-label="打开菜单" @click="toggleMobileMenu">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 class="header-title">{{ pageTitle }}</h1>
          <div class="header-breadcrumb">
            <a @click="$router.push('/')">首页</a>
            <span>/</span>
            <span class="current">{{ pageTitle }}</span>
          </div>
        </div>

        <div class="header-right">
          <!-- 搜索 -->
          <ActionButton label="搜索" @click="$message.info('搜索功能开发中')">
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
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </ActionButton>

          <!-- 通知 -->
          <ActionButton label="消息通知" :badge="3" @click="$message.info('通知功能开发中')">
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

          <!-- 设置 -->
          <ActionButton label="系统设置" @click="$message.info('设置功能开发中')">
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
                d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
              />
            </svg>
          </ActionButton>

          <div class="header-divider"></div>

          <!-- 退出 -->
          <ActionButton label="退出登录" @click="handleLogout">
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
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
          </ActionButton>
        </div>
      </header>

      <!-- 页面内容 -->
      <div class="page-content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import ActionButton from '@/components/ActionButton.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const sidebarCollapsed = ref(false)
const expandedSubmenu = ref<string | null>(null)
const hoveredSubmenu = ref<string | null>(null) // 收起时 hover 显示子菜单
const mobileMenuOpen = ref(false)

const toggleMobileMenu = () => {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

// 判断当前路由是否属于某个父菜单
const isSubmenuActive = (submenu: string): boolean => {
  const currentPath = route.path
  if (submenu === 'billing') {
    return currentPath.startsWith('/billing')
  }
  if (submenu === 'system') {
    return currentPath.startsWith('/system')
  }
  return false
}

// 判断父菜单是否应该高亮（自身选中或子菜单选中）
const isParentMenuActive = (menu: string): boolean => {
  if (menu === 'billing' && isSubmenuActive('billing')) return true
  if (menu === 'system' && isSubmenuActive('system')) return true
  return false
}

// 监听路由变化，自动展开包含当前路由的父菜单，并关闭移动端菜单
watch(
  () => route.path,
  (newPath) => {
    if (newPath.startsWith('/billing')) {
      expandedSubmenu.value = 'billing'
    } else if (newPath.startsWith('/system')) {
      expandedSubmenu.value = 'system'
    }
    mobileMenuOpen.value = false
  },
  { immediate: true }
)

// 监听侧边栏收起状态，收起时自动折叠子菜单
watch(sidebarCollapsed, (collapsed) => {
  if (collapsed) {
    expandedSubmenu.value = null
  }
})

// 初始化时从 localStorage 读取侧边栏状态
onMounted(() => {
  const saved = localStorage.getItem('sidebar_collapsed')
  if (saved !== null) {
    sidebarCollapsed.value = saved === 'true'
  }
})

const pageTitle = computed(() => {
  const routeMap: Record<string, string> = {
    Home: '仪表盘',
    Customers: '客户管理',
    CustomerDetail: '客户详情',
    Balance: '余额管理',
    PricingRules: '计费规则',
    Tags: '标签管理',
    Users: '用户管理',
    Roles: '角色权限',
    SyncLogs: '同步日志',
    AuditLogs: '审计日志',
  }
  return routeMap[route.name as string] || '仪表盘'
})

const can = (permission: string) => userStore.hasPermission(permission)

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('sidebar_collapsed', String(sidebarCollapsed.value))
}

const toggleSubmenu = (menu: string) => {
  if (sidebarCollapsed.value) return // 收起时不允许点击展开
  expandedSubmenu.value = expandedSubmenu.value === menu ? null : menu
}

const handleSubmenuHover = (menu: string | null) => {
  if (sidebarCollapsed.value) {
    hoveredSubmenu.value = menu
  }
}

const handleLogout = () => {
  userStore.logout()
  Message.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
/* CSS 变量 */
.dashboard-layout {
  --sidebar-width: 260px;
  --sidebar-collapsed-width: 68px;
  --header-height: 64px;
  --primary-1: #e8f3ff;
  --primary-5: #3296f7;
  --primary-6: #0369a1;
  --primary-7: #035a8a;
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
}

.dashboard-layout {
  display: flex;
  min-height: 100vh;
  background: var(--neutral-1);
}

/* 侧边栏 */
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background: linear-gradient(180deg, var(--neutral-10) 0%, var(--neutral-9) 100%);
  z-index: 100;
  display: flex;
  flex-direction: column;
  transition: width var(--transition-base);
  overflow: hidden; /* 移除滚动，由 sidebar-nav 处理 */
}

/* 确保收起时宽度精确为 64px */
.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

/* 侧边栏滚动条美化 - 默认隐藏，hover 时显示 */
.sidebar-nav::-webkit-scrollbar {
  width: 6px;
}

.sidebar-nav::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-nav::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  transition: background var(--transition-fast);
}

.sidebar-nav:hover::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.3);
}

.sidebar-nav::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.4);
}

.sidebar-logo {
  height: var(--header-height);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.sidebar.collapsed .sidebar-logo {
  padding: 0 16px;
  justify-content: center;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--primary-5) 0%, var(--primary-6) 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.4);
  flex-shrink: 0;
}

.logo-icon svg {
  width: 22px;
  height: 22px;
  color: white;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: white;
  letter-spacing: -0.3px;
  white-space: nowrap;
  transition: opacity var(--transition-fast);
}

.sidebar.collapsed .logo-text {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

/* 导航 */
.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar.collapsed .sidebar-nav {
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.nav-section {
  margin-bottom: 24px;
}

.sidebar.collapsed .nav-section {
  margin-bottom: 12px;
}

.nav-section-title {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 0 12px;
  margin-bottom: 8px;
  white-space: nowrap;
  transition: opacity var(--transition-fast);
}

.sidebar.collapsed .nav-section-title {
  opacity: 0;
  width: 0;
  padding: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  transition: background-color var(--transition-fast), color var(--transition-fast);
  cursor: pointer;
  margin-bottom: 4px;
  position: relative;
  white-space: nowrap;
}

.sidebar.collapsed .nav-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* 有子菜单的父项需要 relative 定位 */
.nav-item-wrapper {
  position: relative;
}

.sidebar.collapsed .nav-item {
  padding: 0;
  justify-content: center;
  align-items: center;
  aspect-ratio: 1;
  width: 100%;
  min-height: 48px;
  border-radius: 12px;
  display: flex;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

.nav-item.active {
  background: linear-gradient(135deg, var(--primary-6) 0%, var(--primary-7) 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.3);
  transition: background-color var(--transition-fast), color var(--transition-fast), box-shadow var(--transition-fast);
}

/* 收起模式下的选中图标状态 - 更明显的视觉效果 */
.sidebar.collapsed .nav-item.active {
  background: linear-gradient(135deg, var(--primary-6) 0%, var(--primary-7) 100%);
  box-shadow: 0 6px 20px rgba(3, 105, 161, 0.4);
  transform: scale(1.02);
}

.sidebar.collapsed .nav-item.active .nav-item-icon {
  color: white;
  transform: scale(1.1);
}

.nav-item-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.nav-item-icon svg {
  width: 22px;
  height: 22px;
}

/* 收起模式下确保图标完美居中 */
.sidebar.collapsed .nav-item-icon {
  width: 24px;
  height: 24px;
  margin: 0;
}

.sidebar.collapsed .nav-item-icon svg {
  width: 22px;
  height: 22px;
}

.nav-item-label {
  font-size: 14px;
  font-weight: 500;
  transition: opacity var(--transition-fast), width var(--transition-fast);
}

.sidebar.collapsed .nav-item-label,
.sidebar.collapsed .nav-item-badge,
.sidebar.collapsed .nav-item-arrow,
.sidebar.collapsed .nav-section-title {
  display: none;
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.sidebar.collapsed .nav-item-icon {
  margin: 0;
}

.nav-item-badge {
  margin-left: auto;
  padding: 2px 8px;
  background: var(--danger-5);
  color: white;
  font-size: 11px;
  font-weight: 600;
  border-radius: 10px;
  flex-shrink: 0;
}

.nav-item-arrow {
  margin-left: auto;
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.5);
  transition: transform var(--transition-fast);
  flex-shrink: 0;
}

.nav-item.expanded .nav-item-arrow {
  transform: rotate(90deg);
}

/* 子菜单 */
.nav-submenu {
  margin-top: 4px;
  padding-left: 32px;
  overflow: hidden;
  transition: opacity var(--transition-base), transform var(--transition-base);
}

.nav-subitem {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.5);
  text-decoration: none;
  font-size: 13px;
  transition: background-color var(--transition-fast), color var(--transition-fast);
  margin-bottom: 2px;
  position: relative;
  cursor: pointer;
}

.nav-subitem::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.nav-subitem:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

/* 二级菜单选中效果优化 */
.nav-subitem.active {
  color: #ffffff;
  background: linear-gradient(90deg, rgba(3, 105, 161, 0.5), rgba(3, 105, 161, 0.15));
  font-weight: 600;
}

.nav-subitem.active::before {
  background: #0369a1;
}

/* 父级菜单联动高亮 - 当子菜单选中时 */
.nav-item.parent-active {
  background: rgba(255, 255, 255, 0.12);
  color: white;
}

/* 收起模式下的子菜单悬浮预览 */
.submenu-popup {
  position: absolute;
  left: calc(100% + 12px);
  top: 4px;
  min-width: 160px;
  background: var(--neutral-10);
  border-radius: 12px;
  padding: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 1002;
  display: none;
  opacity: 0;
  transform: translateX(-10px);
  transition: opacity var(--transition-base), transform var(--transition-base);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.sidebar.collapsed .nav-item-wrapper:hover .submenu-popup {
  display: block;
  opacity: 1;
  transform: translateX(0);
}

/* 子菜单项 popup 中的样式 */
.sidebar.collapsed .submenu-popup .nav-subitem {
  padding: 10px 12px;
  margin-bottom: 2px;
  cursor: pointer;
}

.sidebar.collapsed .submenu-popup .nav-subitem:hover {
  background: rgba(255, 255, 255, 0.08);
}

.sidebar.collapsed .submenu-popup .nav-subitem.active {
  background: linear-gradient(90deg, rgba(3, 105, 161, 0.5), rgba(3, 105, 161, 0.15));
  color: #ffffff;
  font-weight: 600;
}

/* 用户信息 */
.sidebar-user {
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0;
  min-height: 72px;
  position: relative;
}

.sidebar.collapsed .sidebar-user {
  padding: 16px 12px;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
}

.sidebar-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  overflow: hidden;
}

.sidebar.collapsed .sidebar-user-info {
  display: none;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--primary-5) 0%, var(--primary-6) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 16px;
  flex-shrink: 0;
}

.user-info {
  flex: 1;
  overflow: hidden;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: white;
  white-space: nowrap;
}

.user-role {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 2px;
  white-space: nowrap;
}

/* 侧边栏切换按钮 */
.sidebar-toggle {
  width: 32px;
  height: 32px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.sidebar-toggle:hover {
  background: rgba(255, 255, 255, 0.18);
  border-color: rgba(255, 255, 255, 0.3);
  transform: scale(1.05);
}

/* 侧边栏收起时的切换按钮定位 - 优化为内联 */
.sidebar.collapsed .sidebar-toggle {
  position: relative;
  right: auto;
  left: auto;
  bottom: auto;
  transform: none;
  z-index: 1001;
  background: linear-gradient(135deg, var(--primary-6) 0%, var(--primary-7) 100%);
  border-color: rgba(255, 255, 255, 0.2);
  box-shadow: 0 4px 16px rgba(3, 105, 161, 0.4);
  width: 40px;
  height: 40px;
  margin: 0 auto;
}

.sidebar.collapsed .sidebar-toggle:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(3, 105, 161, 0.5);
  border-color: rgba(255, 255, 255, 0.4);
}

.sidebar-toggle svg {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.8);
  transition: transform var(--transition-fast), color var(--transition-fast);
}

.sidebar-toggle:hover svg {
  color: white;
}

/* 展开时箭头朝右，收起时箭头朝左 */
.sidebar:not(.collapsed) .sidebar-toggle svg {
  transform: rotate(0deg);
}

.sidebar.collapsed .sidebar-toggle svg {
  transform: rotate(180deg);
  color: white;
}

/* 主内容区 */
.main-content {
  margin-left: var(--sidebar-width);
  min-height: 100vh;
  transition: margin-left var(--transition-base);
  width: calc(100% - var(--sidebar-width));
  overflow-x: hidden; /* 防止横向滚动条 */
}

/* 侧边栏收起时的主内容区 - 使用类名而不是:has() 提高兼容性 */
.main-content.sidebar-collapsed {
  margin-left: var(--sidebar-collapsed-width);
  width: calc(100% - var(--sidebar-collapsed-width));
}

/* 页面内容区域 - 统一布局 */
.page-content {
  padding: 24px 32px;
  max-width: 100%;
  overflow-x: hidden; /* 防止内容溢出 */
  box-sizing: border-box;
}

/* 顶部栏 */
.header {
  height: var(--header-height);
  background: white;
  border-bottom: 1px solid var(--neutral-2);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  flex: 1;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.header-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--neutral-10);
}

.header-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--neutral-5);
}

.header-breadcrumb a {
  color: var(--neutral-5);
  cursor: pointer;
  text-decoration: none;
}

.header-breadcrumb a:hover {
  color: var(--primary-6);
}

.header-breadcrumb .current {
  color: var(--neutral-7);
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
  background: var(--neutral-2);
  margin: 0 4px;
}

/* 页面内容 */
.page-content {
  padding: 32px;
}

/* 移动端菜单按钮样式 */
.mobile-menu-btn {
  display: none;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  align-items: center;
  justify-content: center;
  color: var(--neutral-6);
  cursor: pointer;
  transition: background-color var(--transition-fast), color var(--transition-fast);
  border: none;
  background: transparent;
}

.mobile-menu-btn:hover {
  background: var(--neutral-1);
  color: var(--neutral-9);
}

.mobile-menu-btn svg {
  width: 24px;
  height: 24px;
}

/* 移动端遮罩层 */
.mobile-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}

/* 响应式 */
@media (max-width: 1200px) {
  .mobile-menu-btn {
    display: flex;
  }

  .mobile-overlay {
    display: block;
  }

  .sidebar {
    transform: translateX(-100%);
    z-index: 100;
  }

  .sidebar.mobile-open {
    transform: translateX(0);
  }

  .main-content {
    margin-left: 0;
    width: 100%;
  }
  
  .main-content.sidebar-collapsed {
    margin-left: 0;
    width: 100%;
  }
}
</style>
