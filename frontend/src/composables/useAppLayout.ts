import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'

// ─── Module-level singleton state ────────────────────────────────
const sidebarCollapsed = ref(false)
const expandedSubmenu = ref<string | null>(null)
const hoveredSubmenu = ref<string | null>(null)
const mobileMenuOpen = ref(false)
let initialized = false

export interface NavItem {
  key: string
  label: string
  icon?: string
  to?: string
  children?: NavItem[]
  badge?: number
  permission?: string
}

export interface NavSection {
  key: string
  title: string
  items: NavItem[]
}

export function useAppLayout() {
  const router = useRouter()
  const route = useRoute()
  const userStore = useUserStore()

  // ─── 导航菜单数据（按分组） ─────────────────────────────────────
  const navSections = computed<NavSection[]>(() => {
    const sections: NavSection[] = [
      {
        key: 'core',
        title: '核心功能',
        items: [
          { key: 'dashboard', label: '仪表盘', to: '/' },
          { key: 'customers', label: '客户管理', to: '/customers', permission: 'customers:view' },
          {
            key: 'billing',
            label: '结算管理',
            children: [
              { key: 'balance', label: '余额管理', to: '/billing/balance' },
              { key: 'pricing-rules', label: '计费规则', to: '/billing/pricing-rules' },
              { key: 'invoices', label: '结算单管理', to: '/billing/invoices' },
            ],
          },
        ],
      },
      {
        key: 'analytics',
        title: '分析',
        items: [
          {
            key: 'analytics',
            label: '客户分析',
            children: [
              { key: 'consumption', label: '消耗分析', to: '/analytics/consumption' },
              { key: 'payment', label: '回款分析', to: '/analytics/payment' },
              { key: 'health', label: '健康度分析', to: '/analytics/health' },
              { key: 'profile', label: '画像分析', to: '/analytics/profile' },
              { key: 'forecast', label: '预测回款', to: '/analytics/forecast' },
            ],
          },
        ],
      },
      {
        key: 'system',
        title: '系统管理',
        items: [
          { key: 'tags', label: '标签管理', to: '/tags', permission: 'tags:view' },
          { key: 'users', label: '用户管理', to: '/users', permission: 'users:view' },
          { key: 'roles', label: '角色权限', to: '/roles', permission: 'roles:view' },
          {
            key: 'industry-types',
            label: '行业类型',
            to: '/system/industry-types',
            permission: 'industry_types:manage',
          },
        ],
      },
      {
        key: 'tools',
        title: '系统工具',
        items: [
          { key: 'sync-logs', label: '同步日志', to: '/system/sync-logs', permission: 'sync:view' },
          {
            key: 'audit-logs',
            label: '审计日志',
            to: '/system/audit-logs',
            permission: 'audit:view',
          },
        ],
      },
    ]

    const filterItems = (items: NavItem[]): NavItem[] =>
      items
        .filter((item) => !item.permission || userStore.hasPermission(item.permission))
        .map((item) => (item.children ? { ...item, children: filterItems(item.children) } : item))
        .filter((item) => !item.children || item.children.length > 0)

    return sections
      .map((s) => ({ ...s, items: filterItems(s.items) }))
      .filter((s) => s.items.length > 0)
  })

  // ─── 当前页面标题（保留原 route.name 映射） ─────────────────────
  const pageTitle = computed(() => {
    const routeMap: Record<string, string> = {
      Home: '仪表盘',
      Profile: '个人信息',
      Customers: '客户管理',
      CustomerDetail: '客户详情',
      Balance: '余额管理',
      PricingRules: '计费规则',
      Tags: '标签管理',
      Users: '用户管理',
      Roles: '角色权限',
      SyncLogs: '同步日志',
      IndustryTypes: '行业类型',
      AuditLogs: '审计日志',
    }
    return routeMap[route.name as string] || '仪表盘'
  })

  const can = (permission: string) => userStore.hasPermission(permission)
  const currentUser = computed(() => userStore.userInfo)
  const userPermissions = computed(() => userStore.permissions)

  // ─── 方法 ──────────────────────────────────────────────────────
  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem('prototype-sidebar-collapsed', String(sidebarCollapsed.value))
  }
  const toggleMobileMenu = () => {
    mobileMenuOpen.value = !mobileMenuOpen.value
  }
  const closeMobileMenu = () => {
    mobileMenuOpen.value = false
  }
  const toggleSubmenu = (menu: string) => {
    if (sidebarCollapsed.value) return
    expandedSubmenu.value = expandedSubmenu.value === menu ? null : menu
  }
  const handleSubmenuHover = (menu: string | null) => {
    if (sidebarCollapsed.value) hoveredSubmenu.value = menu
  }
  const isSubmenuActive = (submenu: string): boolean => {
    const p = route.path
    if (submenu === 'billing') return p.startsWith('/billing')
    if (submenu === 'analytics') return p.startsWith('/analytics')
    if (submenu === 'system')
      return p === '/tags' || p === '/users' || p === '/roles' || p === '/system/industry-types'
    return false
  }
  const isParentMenuActive = (menu: string): boolean =>
    (menu === 'billing' && isSubmenuActive('billing')) ||
    (menu === 'analytics' && isSubmenuActive('analytics')) ||
    (menu === 'system' && isSubmenuActive('system'))

  const handleLogout = () => {
    userStore.logout()
    Message.success('已退出登录')
    router.push('/login')
  }

  // ─── 监听（仅注册一次） ─────────────────────────────────────────
  if (!initialized) {
    initialized = true
    watch(
      () => route.path,
      (newPath) => {
        if (newPath.startsWith('/billing')) expandedSubmenu.value = 'billing'
        else if (newPath.startsWith('/analytics')) expandedSubmenu.value = 'analytics'
        else if (
          newPath === '/tags' ||
          newPath === '/users' ||
          newPath === '/roles' ||
          newPath === '/system/industry-types' ||
          newPath === '/system/database-management'
        )
          expandedSubmenu.value = 'system'
        else expandedSubmenu.value = null
        mobileMenuOpen.value = false
      },
      { immediate: true }
    )

    watch(sidebarCollapsed, (c) => {
      if (c) expandedSubmenu.value = null
    })

    onMounted(() => {
      const saved = localStorage.getItem('prototype-sidebar-collapsed')
      if (saved !== null) sidebarCollapsed.value = saved === 'true'
      if (userStore.isTokenExpired()) {
        userStore.logout()
        Message.warning('登录已过期，请重新登录')
        router.push('/login')
      }
    })
  }

  return {
    sidebarCollapsed,
    expandedSubmenu,
    hoveredSubmenu,
    mobileMenuOpen,
    navSections,
    pageTitle,
    currentUser,
    userPermissions,
    can,
    toggleSidebar,
    toggleMobileMenu,
    closeMobileMenu,
    toggleSubmenu,
    handleSubmenuHover,
    isSubmenuActive,
    isParentMenuActive,
    handleLogout,
  }
}
