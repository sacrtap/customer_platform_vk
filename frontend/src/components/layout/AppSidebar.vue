<template>
  <aside :class="['sidebar', { collapsed: sidebarCollapsed, 'mobile-open': mobileMenuOpen }]">
    <div class="sidebar-logo">
      <div class="logo-icon">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
      </div>
      <span v-if="!sidebarCollapsed" class="logo-text">Customer Platform VK</span>
    </div>

    <nav class="sidebar-nav">
      <div class="nav-section">
        <div v-if="!sidebarCollapsed" class="nav-section-title">核心功能</div>
        <a class="nav-item" :class="{ active: $route.path === '/' }" @click="goTo('/')">
          <div class="nav-item-icon"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg></div>
          <span class="nav-item-label">仪表盘</span>
        </a>
        <a v-if="can('customers:view')" class="nav-item" :class="{ active: $route.path.startsWith('/customers') }" @click="goTo('/customers')">
          <div class="nav-item-icon"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg></div>
          <span class="nav-item-label">客户管理</span>
        </a>
        <div class="nav-item nav-item-wrapper" :class="{ expanded: expandedSubmenu === 'billing', 'parent-active': isParentMenuActive('billing') }" @click="toggleSubmenu('billing')" @mouseenter="handleSubmenuHover('billing')" @mouseleave="handleSubmenuHover(null)">
          <div class="nav-item-icon"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg></div>
          <span class="nav-item-label">结算管理</span>
          <svg class="nav-item-arrow" style="margin-left:auto;width:16px;height:16px;transition:transform .2s" :style="{ transform: expandedSubmenu === 'billing' ? 'rotate(180deg)' : 'rotate(0deg)' }" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </div>
        <div v-show="expandedSubmenu === 'billing' && !sidebarCollapsed" class="nav-submenu">
          <a class="nav-subitem" :class="{ active: $route.name === 'Balance' }" @click="goTo('/billing/balances')">余额管理</a>
          <a class="nav-subitem" :class="{ active: $route.name === 'PricingRules' }" @click="goTo('/billing/pricing-rules')">计费规则</a>
          <a class="nav-subitem" :class="{ active: $route.name === 'Invoices' }" @click="goTo('/billing/invoices')">结算单管理</a>
        </div>
      </div>

      <div class="nav-section">
        <div v-if="!sidebarCollapsed" class="nav-section-title">分析</div>
        <div class="nav-item nav-item-wrapper" :class="{ expanded: expandedSubmenu === 'analytics', 'parent-active': isParentMenuActive('analytics') }" @click="toggleSubmenu('analytics')" @mouseenter="handleSubmenuHover('analytics')" @mouseleave="handleSubmenuHover(null)">
          <div class="nav-item-icon"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg></div>
          <span class="nav-item-label">客户分析</span>
          <svg class="nav-item-arrow" style="margin-left:auto;width:16px;height:16px;transition:transform .2s" :style="{ transform: expandedSubmenu === 'analytics' ? 'rotate(180deg)' : 'rotate(0deg)' }" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </div>
        <div v-show="expandedSubmenu === 'analytics' && !sidebarCollapsed" class="nav-submenu">
          <a class="nav-subitem" :class="{ active: $route.path === '/analytics/consumption' }" @click="goTo('/analytics/consumption')">消耗分析</a>
          <a class="nav-subitem" :class="{ active: $route.path === '/analytics/payment' }" @click="goTo('/analytics/payment')">回款分析</a>
          <a class="nav-subitem" :class="{ active: $route.path === '/analytics/health' }" @click="goTo('/analytics/health')">健康度分析</a>
          <a class="nav-subitem" :class="{ active: $route.path === '/analytics/profile' }" @click="goTo('/analytics/profile')">画像分析</a>
          <a class="nav-subitem" :class="{ active: $route.path === '/analytics/forecast' }" @click="goTo('/analytics/forecast')">预测回款</a>
        </div>
      </div>

      <div class="nav-section">
        <div v-if="!sidebarCollapsed" class="nav-section-title">系统管理</div>
        <a v-if="can('tags:view')" class="nav-item" :class="{ active: $route.path === '/tags' }" @click="goTo('/tags')">
          <div class="nav-item-icon"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" /></svg></div>
          <span class="nav-item-label">标签管理</span>
        </a>
        <div class="nav-item nav-item-wrapper" :class="{ expanded: expandedSubmenu === 'system', 'parent-active': isParentMenuActive('system') }" @click="toggleSubmenu('system')" @mouseenter="handleSubmenuHover('system')" @mouseleave="handleSubmenuHover(null)">
          <div class="nav-item-icon"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg></div>
          <span class="nav-item-label">系统设置</span>
          <svg class="nav-item-arrow" style="margin-left:auto;width:16px;height:16px;transition:transform .2s" :style="{ transform: expandedSubmenu === 'system' ? 'rotate(180deg)' : 'rotate(0deg)' }" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </div>
        <div v-show="expandedSubmenu === 'system' && !sidebarCollapsed" class="nav-submenu">
          <a class="nav-subitem" :class="{ active: $route.path === '/system/users' }" @click="goTo('/system/users')">用户管理</a>
          <a class="nav-subitem" :class="{ active: $route.path === '/system/roles' }" @click="goTo('/system/roles')">角色权限</a>
        </div>
      </div>

      <div class="nav-section">
        <div v-if="!sidebarCollapsed" class="nav-section-title">系统工具</div>
        <a v-if="can('sync:view')" class="nav-item" :class="{ active: $route.path === '/system/sync-logs' }" @click="goTo('/system/sync-logs')">
          <div class="nav-item-icon"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg></div>
          <span class="nav-item-label">同步日志</span>
        </a>
        <a v-if="can('audit:view')" class="nav-item" :class="{ active: $route.path === '/system/audit-logs' }" @click="goTo('/system/audit-logs')">
          <div class="nav-item-icon"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" /></svg></div>
          <span class="nav-item-label">审计日志</span>
        </a>
      </div>
    </nav>

    <div class="sidebar-user">
      <div class="sidebar-user-info">
        <div class="user-name">{{ currentUser?.username || '用户' }}</div>
        <div class="user-role">{{ currentUser?.roles?.[0] || '运营经理' }}</div>
      </div>
      <div class="sidebar-toggle" :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'" @click="toggleSidebar">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="sidebarCollapsed ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'" /></svg>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAppLayout } from '@/composables/useAppLayout'

const emit = defineEmits<{
  'close-mobile': []
}>()

const router = useRouter()
const {
  sidebarCollapsed,
  mobileMenuOpen,
  expandedSubmenu,
  can,
  currentUser,
  toggleSidebar,
  toggleSubmenu,
  handleSubmenuHover,
  isParentMenuActive,
} = useAppLayout()

const goTo = (path: string) => {
  router.push(path)
  emit('close-mobile')
}
</script>

<style scoped>
.sidebar { --sidebar-width: 260px; --sidebar-collapsed-width: 68px; --header-height: 64px; --primary-5: #0369a1; --danger-5: #f87171; --t-fast: 150ms cubic-bezier(0.4,0,0.2,1); --t-base: 250ms cubic-bezier(0.4,0,0.2,1); position: fixed; left: 0; top: 0; bottom: 0; width: var(--sidebar-width); background: linear-gradient(180deg,#1d2330 0%,#0f172a 100%); z-index: 100; display: flex; flex-direction: column; transition: width var(--t-base); overflow: hidden; }
.sidebar.collapsed { width: var(--sidebar-collapsed-width); }
.sidebar-nav { flex: 1; padding: 20px 12px; overflow-y: auto; overflow-x: hidden; min-height: 0; }
.sidebar-nav::-webkit-scrollbar { width: 4px; }
.sidebar-nav::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 2px; }
.sidebar-logo { height: var(--header-height); display: flex; align-items: center; gap: 12px; padding: 0 20px; border-bottom: 1px solid rgba(255,255,255,.1); flex-shrink: 0; }
.sidebar.collapsed .sidebar-logo { padding: 0 16px; justify-content: center; }
.logo-icon { width: 36px; height: 36px; background: linear-gradient(135deg,#0369a1,#0284c7); border-radius: 10px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(3,105,161,.4); flex-shrink: 0; }
.logo-icon svg { width: 22px; height: 22px; color: #fff; }
.logo-text { font-size: 16px; font-weight: 700; color: #fff; letter-spacing: -.3px; white-space: nowrap; }
.nav-section { margin-bottom: 24px; }
.sidebar.collapsed .nav-section { margin-bottom: 12px; width: 100%; display: flex; flex-direction: column; align-items: center; }
.nav-section-title { font-size: 11px; font-weight: 600; color: rgba(255,255,255,.6); text-transform: uppercase; letter-spacing: .5px; padding: 0 12px; margin-bottom: 8px; white-space: nowrap; }
.sidebar.collapsed .nav-section-title { opacity: 0; width: 0; padding: 0; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 12px; border-radius: 10px; color: #fff; text-decoration: none; transition: background-color var(--t-fast), color var(--t-fast); cursor: pointer; margin-bottom: 4px; position: relative; white-space: nowrap; }
.nav-item-wrapper { position: relative; }
.sidebar.collapsed .nav-item { padding: 0; justify-content: center; align-items: center; aspect-ratio: 1; width: 100%; min-height: 48px; border-radius: 12px; }
.nav-item:hover { background: rgba(3,105,161,.15); color: #fff; }
.nav-item.active { background: linear-gradient(135deg,#0369a1,#0284c7); color: #fff; box-shadow: 0 4px 12px rgba(3,105,161,.4); }
.sidebar.collapsed .nav-item.active { box-shadow: 0 6px 20px rgba(3,105,161,.5); transform: scale(1.02); }
.nav-item-icon { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; color: #fff; transition: transform var(--t-fast); }
.nav-item-icon svg { width: 22px; height: 22px; }
.sidebar.collapsed .nav-item-icon { margin: 0; }
.nav-item-label { font-size: 14px; font-weight: 500; color: #fff; transition: opacity var(--t-fast), width var(--t-fast); }
.sidebar.collapsed .nav-item-label, .sidebar.collapsed .nav-item-arrow { display: none; opacity: 0; width: 0; overflow: hidden; }
.nav-item-arrow { transition: transform var(--t-fast); }
.nav-submenu { padding-left: 24px; }
.nav-subitem { display: block; padding: 10px 12px; font-size: 13px; color: rgba(255,255,255,.7); text-decoration: none; border-radius: 8px; transition: background-color var(--t-fast); cursor: pointer; margin-bottom: 2px; }
.nav-subitem:hover { background: rgba(3,105,161,.15); color: #fff; }
.nav-subitem.active { background: rgba(3,105,161,.2); color: #fff; font-weight: 500; }
.sidebar.collapsed .nav-submenu { display: none; }
.sidebar-user { display: flex; align-items: center; gap: 8px; padding: 16px 12px; border-top: 1px solid rgba(255,255,255,.1); flex-shrink: 0; }
.sidebar.collapsed .sidebar-user { justify-content: center; padding: 16px 8px; }
.sidebar-user-info { flex: 1; min-width: 0; }
.sidebar.collapsed .sidebar-user-info { display: none; }
.user-name { font-size: 13px; font-weight: 500; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.user-role { font-size: 11px; color: rgba(255,255,255,.5); margin-top: 2px; }
.sidebar-toggle { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.15); border-radius: 8px; cursor: pointer; color: #fff; transition: background-color var(--t-fast); flex-shrink: 0; }
.sidebar-toggle:hover { background: rgba(255,255,255,.2); }
.sidebar-toggle svg { width: 16px; height: 16px; }
@media (max-width:768px) { .sidebar { transform: translateX(-100%); width: var(--sidebar-width)!important; } .sidebar.mobile-open { transform: translateX(0); box-shadow: 0 0 20px rgba(0,0,0,.3); } .sidebar.collapsed { width: var(--sidebar-width)!important; } }
</style>
