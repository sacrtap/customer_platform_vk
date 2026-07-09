<template>
  <aside
    class="app-sidebar"
    :class="{ 'is-collapsed': sidebarCollapsed, 'mobile-open': mobileMenuOpen }"
    @mouseenter="handleSubmenuHover(null)"
    @mouseleave="handleSubmenuHover(null)"
  >
    <div class="sidebar-header">
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
      <span v-if="!sidebarCollapsed" class="sidebar-title">Customer Platform VK</span>
    </div>

    <nav class="sidebar-nav" aria-label="主导航">
      <div
        v-for="section in navSections"
        :key="section.key"
        class="sidebar-section"
      >
        <div
          v-if="!sidebarCollapsed"
          class="sidebar-group-title"
          :aria-label="section.title"
        >
          {{ section.title }}
        </div>

        <div
          v-for="item in section.items"
          :key="item.key"
          class="sidebar-parent"
          :aria-expanded="expandedSubmenu === item.key"
          @click="can(item.permission ?? '') && toggleSubmenu(item.key)"
          @mouseenter="handleSubmenuHover(item.key)"
          @mouseleave="handleSubmenuHover(null)"
        >
          <a
            v-if="!item.children"
            :href="item.route"
            class="sidebar-item"
            :class="{ active: isParentMenuActive(item.key) }"
            :aria-current="isParentMenuActive(item.key) ? 'page' : undefined"
            @click.prevent="can(item.permission ?? '') && goTo(item.route)"
          >
            <span class="sidebar-icon" :aria-hidden="true">
              <component :is="getIconComponent(item.icon)" />
            </span>
            <span v-if="!sidebarCollapsed" class="sidebar-label">{{ item.label }}</span>
          </a>

          <div
            v-else
            class="sidebar-parent-trigger"
            :class="{ active: isParentMenuActive(item.key) }"
          >
            <span class="sidebar-icon" :aria-hidden="true">
              <component :is="getIconComponent(item.icon)" />
            </span>
            <span v-if="!sidebarCollapsed" class="sidebar-label">{{ item.label }}</span>
            <span
              v-if="!sidebarCollapsed"
              class="sidebar-chev"
              :class="{ expanded: expandedSubmenu === item.key }"
            >
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
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </span>
          </div>

          <div
            v-if="item.children"
            class="sidebar-subnav"
            :style="{ display: expandedSubmenu === item.key ? 'block' : 'none' }"
            role="group"
            :aria-label="item.label"
          >
            <a
              v-for="child in item.children"
              :key="child.key"
              :href="child.route"
              class="sidebar-child"
              :aria-current="route.path === child.route ? 'page' : undefined"
              @click.prevent="goTo(child.route)"
            >
              <span class="sidebar-icon" :aria-hidden="true">
                <component :is="getIconComponent(child.icon)" />
              </span>
              <span v-if="!sidebarCollapsed" class="sidebar-label">
                {{ child.label }}
              </span>
              <span
                v-if="!sidebarCollapsed && child.hint"
                class="sidebar-hint"
              >
                {{ child.hint }}
              </span>
            </a>
          </div>
        </div>
      </div>
    </nav>

    <div v-if="!sidebarCollapsed" class="sidebar-footer">
      <button
        class="collapse-toggle"
        aria-label="折叠侧边栏"
        title="折叠侧边栏"
        @click="toggleSidebar"
      >
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
            d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
          />
        </svg>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useAppLayout } from '@/composables/useAppLayout'

const emit = defineEmits<{
  'close-mobile': []
}>()

const router = useRouter()
const route = useRoute()

const {
  sidebarCollapsed,
  mobileMenuOpen,
  expandedSubmenu,
  navSections,
  can,
  toggleSidebar,
  toggleSubmenu,
  handleSubmenuHover,
  isParentMenuActive,
} = useAppLayout()

const iconMap = {
  LayoutDashboard: {
    template: `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>`,
  },
  Users: {
    template: `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87" /><path d="M16 3.13a4 4 0 010 7.75" /></svg>`,
  },
  CreditCard: {
    template: `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2" /><line x1="1" y1="10" x2="23" y2="10" /></svg>`,
  },
  BarChart2: {
    template: `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>`,
  },
  Settings: {
    template: `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" /></svg>`,
  },
  FileText: {
    template: `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>`,
  },
  CheckCheck: {
    template: `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 6 12 12 6 9" /><polyline points="22 10 18 14 14 10" /></svg>`,
  },
}

const getIconComponent = (iconName: string) => iconMap[iconName as keyof typeof iconMap] || iconMap.LayoutDashboard

const goTo = (path: string) => {
  router.push(path)
  emit('close-mobile')
}
</script>

<style scoped>
.app-sidebar {
  width: var(--cop-sidebar-width);
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  background: linear-gradient(180deg, #1d2330 0%, #0f172a 100%);
  z-index: 30;
  display: flex;
  flex-direction: column;
  transition: width var(--t-base);
  overflow: visible;
}

.app-sidebar.is-collapsed {
  width: var(--cop-sidebar-collapsed-width);
}

.sidebar-header {
  height: var(--cop-header-height);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.app-sidebar.is-collapsed .sidebar-header {
  justify-content: center;
  padding: 0 12px;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--cop-primary), #0284c7);
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
  color: #fff;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  letter-spacing: -0.3px;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-nav {
  flex: 1;
  padding: 16px 8px;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

.sidebar-nav::-webkit-scrollbar {
  width: 4px;
}

.sidebar-nav::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.sidebar-section {
  margin-bottom: 20px;
}

.sidebar-group-title {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 0 12px;
  margin-bottom: 8px;
  white-space: nowrap;
}

.app-sidebar.is-collapsed .sidebar-group-title {
  display: none;
}

.sidebar-parent {
  position: relative;
  width: 100%;
}

.sidebar-item,
.sidebar-parent-trigger {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--cop-radius-sm);
  color: rgba(255, 255, 255, 0.85);
  text-decoration: none;
  transition: background var(--t-fast), color var(--t-fast);
  background: none;
  border: none;
  cursor: pointer;
  width: 100%;
  text-align: left;
  font-size: 14px;
  font-weight: 500;
}

.sidebar-item:hover,
.sidebar-parent-trigger:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.sidebar-item.active,
.sidebar-parent-trigger.active {
  background: linear-gradient(90deg, rgba(3, 105, 161, 0.2), transparent);
  color: #fff;
  border-left: 3px solid var(--cop-primary);
  padding-left: 9px;
}

.sidebar-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  color: currentColor;
}

.sidebar-icon svg {
  width: 20px;
  height: 20px;
}

.sidebar-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-chev {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
  transition: transform var(--t-fast);
}

.sidebar-chev.expanded {
  transform: rotate(180deg);
}

.sidebar-chev svg {
  width: 16px;
  height: 16px;
}

.sidebar-subnav {
  margin-top: 4px;
  padding-left: 8px;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
}

.app-sidebar.is-collapsed .sidebar-subnav,
.app-sidebar.is-collapsed .sidebar-parent[aria-expanded="true"] + .sidebar-subnav {
  display: none !important;
}

.sidebar-child {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--cop-radius-sm);
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  transition: background var(--t-fast), color var(--t-fast);
  font-size: 13px;
  font-weight: 500;
}

.sidebar-child:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.sidebar-child[aria-current="page"] {
  background: rgba(3, 105, 161, 0.15);
  color: #fff;
}

.sidebar-child .sidebar-icon {
  width: 16px;
  height: 16px;
}

.sidebar-child .sidebar-icon svg {
  width: 16px;
  height: 16px;
}

.sidebar-hint {
  margin-left: auto;
  font-size: 11px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.4);
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  white-space: nowrap;
}

.app-sidebar.is-collapsed .sidebar-label,
.app-sidebar.is-collapsed .sidebar-group-title,
.app-sidebar.is-collapsed .sidebar-hint,
.app-sidebar.is-collapsed .sidebar-chev {
  display: none;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.collapse-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 8px;
  border-radius: var(--cop-radius-sm);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: background var(--t-fast), color var(--t-fast), border-color var(--t-fast);
}

.collapse-toggle:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.2);
}

.collapse-toggle svg {
  width: 20px;
  height: 20px;
}

.app-sidebar.is-collapsed .collapse-toggle {
  padding: 8px;
}
</style>