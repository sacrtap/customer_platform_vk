<template>
  <aside :class="['side', { collapsed: sidebarCollapsed, 'mobile-open': mobileMenuOpen }]">
    <!-- 折叠/展开浮动按钮 -->
    <button
      class="toggle-btn desktop-only"
      :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
      :aria-expanded="!sidebarCollapsed"
      @click="toggleSidebar"
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path :d="sidebarCollapsed ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'" />
      </svg>
    </button>

    <!-- 品牌区 -->
    <div class="brand">
      <div class="mark">VK</div>
      <div class="brand-text">
        <div class="brand-name">客户运营中台</div>
        <div class="brand-sub">Customer Platform</div>
      </div>
    </div>

    <!-- 导航区 -->
    <nav class="nav" aria-label="主导航">
      <!-- 总览组 -->
      <div class="nav-group">
        <div class="nav-title">总览</div>
        <button
          class="nav-btn"
          :class="{ active: $route.path === '/' }"
          :aria-current="$route.path === '/' ? 'page' : undefined"
          @click="goTo('/')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
              /></svg
          ></span>
          <span class="nav-text">运营工作台</span>
        </button>
      </div>

      <!-- 核心功能组 -->
      <div class="nav-group">
        <div class="nav-title">核心功能</div>
        <button
          v-if="can('customers:view')"
          class="nav-btn"
          :class="{ active: $route.path.startsWith('/customers') }"
          :aria-current="$route.path.startsWith('/customers') ? 'page' : undefined"
          @click="goTo('/customers')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
              /></svg
          ></span>
          <span class="nav-text">客户管理</span>
        </button>

        <div
          class="nav-parent"
          :class="{ active: isParentMenuActive('billing') }"
          :aria-expanded="expandedSubmenu === 'billing'"
          @click="toggleSubmenu('billing')"
        >
          <div class="nav-main">
            <span class="nav-icon"
              ><svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                /></svg
            ></span>
            <span class="nav-text">结算管理</span>
          </div>
          <span class="chev">▼</span>
        </div>
        <div v-show="expandedSubmenu === 'billing' && !sidebarCollapsed" class="subnav">
          <button
            class="nav-btn sub"
            :class="{ active: $route.name === 'Balance' }"
            @click="goTo('/billing/balances')"
          >
            余额管理
          </button>
          <button
            class="nav-btn sub"
            :class="{ active: $route.name === 'PricingRules' }"
            @click="goTo('/billing/pricing-rules')"
          >
            计费规则
          </button>
          <button
            class="nav-btn sub"
            :class="{ active: $route.name === 'PackagePlans' }"
            @click="goTo('/billing/package-plans')"
          >
            包年套餐
          </button>
          <button
            class="nav-btn sub"
            :class="{ active: $route.name === 'Invoices' }"
            @click="goTo('/billing/invoices')"
          >
            结算单管理
          </button>
        </div>
      </div>

      <!-- 运营分析组 -->
      <div class="nav-group">
        <div class="nav-title">运营分析</div>
        <div
          class="nav-parent"
          :class="{ active: isParentMenuActive('analytics') }"
          :aria-expanded="expandedSubmenu === 'analytics'"
          @click="toggleSubmenu('analytics')"
        >
          <div class="nav-main">
            <span class="nav-icon"
              ><svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                /></svg
            ></span>
            <span class="nav-text">客户分析</span>
          </div>
          <span class="chev">▼</span>
        </div>
        <div v-show="expandedSubmenu === 'analytics' && !sidebarCollapsed" class="subnav">
          <button
            class="nav-btn sub"
            :class="{ active: $route.path === '/analytics/consumption' }"
            @click="goTo('/analytics/consumption')"
          >
            消耗分析
          </button>
          <button
            class="nav-btn sub"
            :class="{ active: $route.path === '/analytics/payment' }"
            @click="goTo('/analytics/payment')"
          >
            回款分析
          </button>
          <button
            class="nav-btn sub"
            :class="{ active: $route.path === '/analytics/health' }"
            @click="goTo('/analytics/health')"
          >
            健康度分析
          </button>
          <button
            class="nav-btn sub"
            :class="{ active: $route.path === '/analytics/profile' }"
            @click="goTo('/analytics/profile')"
          >
            画像分析
          </button>
          <button
            class="nav-btn sub"
            :class="{ active: $route.path === '/analytics/forecast' }"
            @click="goTo('/analytics/forecast')"
          >
            预测回款
          </button>
        </div>
      </div>

      <!-- 系统管理组 -->
      <div class="nav-group">
        <div class="nav-title">系统管理</div>
        <button
          v-if="can('tags:view')"
          class="nav-btn"
          :class="{ active: $route.path === '/tags' }"
          :aria-current="$route.path === '/tags' ? 'page' : undefined"
          @click="goTo('/tags')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
              /></svg
          ></span>
          <span class="nav-text">标签管理</span>
        </button>
        <button
          v-if="can('users:view')"
          class="nav-btn"
          :class="{ active: $route.path === '/users' }"
          :aria-current="$route.path === '/users' ? 'page' : undefined"
          @click="goTo('/users')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg
          ></span>
          <span class="nav-text">用户管理</span>
        </button>
        <button
          v-if="can('roles:view')"
          class="nav-btn"
          :class="{ active: $route.path === '/roles' }"
          :aria-current="$route.path === '/roles' ? 'page' : undefined"
          @click="goTo('/roles')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              /></svg
          ></span>
          <span class="nav-text">角色权限</span>
        </button>
        <button
          v-if="can('industry_types:manage')"
          class="nav-btn"
          :class="{ active: $route.path === '/system/industry-types' }"
          :aria-current="$route.path === '/system/industry-types' ? 'page' : undefined"
          @click="goTo('/system/industry-types')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
              /></svg
          ></span>
          <span class="nav-text">行业类型</span>
        </button>
        <button
          v-if="can('system:database_clear')"
          class="nav-btn"
          :class="{ active: $route.path === '/system/database-management' }"
          :aria-current="$route.path === '/system/database-management' ? 'page' : undefined"
          @click="goTo('/system/database-management')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3"
              /></svg
          ></span>
          <span class="nav-text">数据清空</span>
        </button>
      </div>

      <!-- 系统工具组 -->
      <div class="nav-group">
        <div class="nav-title">系统工具</div>
        <button
          v-if="can('system:view')"
          class="nav-btn"
          :class="{ active: $route.path === '/system/sync-logs' }"
          :aria-current="$route.path === '/system/sync-logs' ? 'page' : undefined"
          @click="goTo('/system/sync-logs')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              /></svg
          ></span>
          <span class="nav-text">同步日志</span>
        </button>
        <button
          v-if="can('system:view')"
          class="nav-btn"
          :class="{ active: $route.path === '/system/audit-logs' }"
          :aria-current="$route.path === '/system/audit-logs' ? 'page' : undefined"
          @click="goTo('/system/audit-logs')"
        >
          <span class="nav-icon"
            ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
              /></svg
          ></span>
          <span class="nav-text">审计日志</span>
        </button>
      </div>
    </nav>
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
  toggleSidebar,
  toggleSubmenu,
  isParentMenuActive,
} = useAppLayout()

const goTo = (path: string) => {
  router.push(path)
  emit('close-mobile')
}
</script>

<style scoped>
.side {
  position: sticky;
  top: 0;
  height: 100vh;
  background:
    radial-gradient(circle at 20% 0%, rgba(37, 99, 235, 0.28), transparent 32%),
    linear-gradient(180deg, #111c33 0%, #0b1220 100%);
  color: #cbd5e1;
  padding: 16px 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: visible;
  border-right: 1px solid rgba(148, 163, 184, 0.16);
  z-index: 30;
}

/* ─── 折叠/展开按钮 ─── */
.toggle-btn {
  position: absolute;
  top: 22px;
  right: -17px;
  width: 34px;
  height: 34px;
  z-index: 80;
  border: 1px solid rgba(147, 197, 253, 0.24);
  background: linear-gradient(135deg, #1d4ed8, #0891b2);
  color: white;
  border-radius: 999px;
  padding: 0;
  cursor: pointer;
  display: grid;
  place-items: center;
  font-weight: 900;
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.3);
  transition:
    background 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.toggle-btn:hover {
  transform: translateX(2px);
  box-shadow: 0 12px 30px rgba(37, 99, 235, 0.38);
}

/* ─── 品牌区 ─── */
.brand {
  height: 42px;
  display: flex;
  gap: 10px;
  align-items: center;
  color: white;
  font-weight: 850;
  font-size: 16px;
  line-height: 1.2;
  transition: gap 0.25s ease;
}

.mark {
  width: 36px;
  height: 36px;
  border-radius: 13px;
  background: linear-gradient(135deg, #3b82f6, #06b6d4);
  display: grid;
  place-items: center;
  color: white;
  font-weight: 900;
  font-size: 14px;
  box-shadow: 0 10px 28px rgba(37, 99, 235, 0.34);
  flex-shrink: 0;
}

.brand-text {
  min-width: 0;
  overflow: hidden;
}

.brand-name {
  font-size: 14px;
  font-weight: 850;
  color: white;
  white-space: nowrap;
}

.brand-sub {
  font-size: 10px;
  font-weight: 600;
  color: #93a4b8;
  letter-spacing: 0.04em;
}

/* ─── 导航区 ─── */
.nav {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
  overflow-y: auto;
  overflow-x: visible;
}

.nav::-webkit-scrollbar {
  width: 4px;
}

.nav::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.nav-group {
  display: grid;
  gap: 4px;
  overflow: visible;
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 16px;
  padding: 6px;
  background: rgba(15, 23, 42, 0.2);
}

.nav-title {
  padding: 2px 9px 1px;
  color: #93a4b8;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
}

.nav-btn {
  border: 0;
  background: transparent;
  color: #cbd5e1;
  text-align: left;
  padding: 8px 10px;
  border-radius: 12px;
  cursor: pointer;
  font: inherit;
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 34px;
  transition:
    background 0.18s ease,
    color 0.18s ease,
    box-shadow 0.18s ease;
  white-space: nowrap;
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.09);
  color: white;
}

.nav-btn.active {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.24), rgba(6, 182, 212, 0.12));
  color: white;
  box-shadow: inset 0 0 0 1px rgba(125, 211, 252, 0.12);
}

.nav-btn.active .nav-icon {
  color: #67e8f9;
}

.nav-icon {
  width: 18px;
  height: 18px;
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  color: #93c5fd;
}

.nav-icon svg {
  width: 18px;
  height: 18px;
  stroke: currentColor;
  stroke-width: 2;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.nav-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}

/* ─── 父菜单 ─── */
.nav-parent {
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 12px;
  color: #cbd5e1;
  font-size: 13px;
  font-weight: 600;
  transition:
    background 0.18s ease,
    color 0.18s ease;
  user-select: none;
}

.nav-parent:hover {
  background: rgba(255, 255, 255, 0.09);
  color: white;
}

.nav-parent.active {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.24), rgba(6, 182, 212, 0.12));
  color: white;
  box-shadow: inset 0 0 0 1px rgba(125, 211, 252, 0.12);
}

.nav-parent.active .nav-icon {
  color: #67e8f9;
}

.nav-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chev {
  color: #8aa0b8;
  font-size: 10px;
  transition: transform 0.18s ease;
}

.nav-parent[aria-expanded='true'] .chev {
  transform: rotate(180deg);
}

/* ─── 子菜单 ─── */
.subnav {
  display: grid;
  gap: 1px;
  margin: 0 0 2px 17px;
  padding-left: 8px;
  border-left: 1px solid rgba(148, 163, 184, 0.22);
}

.nav-btn.sub {
  padding: 5px 8px;
  min-height: 28px;
  font-size: 12px;
  color: #b6c3d1;
  border-radius: 8px;
}

.nav-btn.sub:hover {
  background: rgba(255, 255, 255, 0.09);
  color: white;
}

.nav-btn.sub.active {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.24), rgba(6, 182, 212, 0.12));
  color: white;
  box-shadow: inset 0 0 0 1px rgba(125, 211, 252, 0.12);
}

/* ─── 折叠态 ───
   使用 .side.collapsed 而非 .shell.collapsed
   原因：.shell 是 Dashboard.vue 的元素，在 scoped CSS 中使用 .shell.collapsed
   会导致 Vue 编译异常，display:none 直接作用于 .shell 元素本身，引发白屏
   .side 是本组件的根元素 <aside>，自身已绑定 { collapsed: sidebarCollapsed } 类
*/

.side.collapsed .brand {
  justify-content: center;
  gap: 0;
}

.side.collapsed .nav {
  align-items: center;
  gap: 6px;
}

.side.collapsed .nav-group {
  width: 44px;
  padding: 0;
  border-color: transparent;
  background: transparent;
  border-radius: 14px;
  gap: 6px;
}

.side.collapsed .nav-btn {
  width: 40px;
  height: 40px;
  min-height: 40px;
  padding: 0;
  justify-content: center;
  border-radius: 14px;
}

.side.collapsed .nav-parent {
  width: 40px;
  height: 40px;
  padding: 0;
  justify-content: center;
  border-radius: 14px;
}

.side.collapsed .nav-main {
  gap: 0;
}

.side.collapsed .nav-icon {
  width: 20px;
  height: 20px;
}

.side.collapsed .nav-icon svg {
  width: 20px;
  height: 20px;
}

.side.collapsed .brand-text,
.side.collapsed .nav-title,
.side.collapsed .nav-text,
.side.collapsed .chev,
.side.collapsed .subnav {
  opacity: 0;
  visibility: hidden;
  display: none !important;
}

/* ─── 响应式 ─── */
@media (max-width: 1100px) {
  .side {
    position: fixed;
    left: 0;
    top: 0;
    width: 252px !important;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
  }

  .side.mobile-open {
    transform: translateX(0);
    box-shadow: 0 0 20px rgba(0, 0, 0, 0.3);
  }

  .toggle-btn {
    display: none;
  }
}
</style>
