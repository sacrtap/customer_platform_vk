import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'

// ─── Module-level singleton state ────────────────────────────────
const SIDEBAR_STORAGE_KEY = 'customer-platform-sidebar-collapsed'
const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true')
const expandedSubmenu = ref<string | null>(null)
const hoveredSubmenu = ref<string | null>(null)
const mobileMenuOpen = ref(false)
let initialized = false

export interface SidebarItem {
  key: string
  label: string
  route: string
  icon: string
  children?: Array<{ key: string; label: string; route: string; hint?: string; icon: string }>
  permission?: string
}

export interface NavSection {
  key: string
  title: string
  items: SidebarItem[]
}

export function useAppLayout() {
  const router = useRouter()
  const route = useRoute()
  const userStore = useUserStore()

  // ─── 导航菜单数据（按分组，按 brief 要求的分组） ─────────────────────
  const navSections = computed<NavSection[]>(() => [
    {
      key: 'overview',
      title: '总览',
      items: [
        {
          key: 'dashboard',
          label: '运营工作台',
          route: '/',
          icon: 'LayoutDashboard',
        },
      ],
    },
    {
      key: 'core',
      title: '核心功能',
      items: [
        {
          key: 'customers',
          label: '客户管理',
          route: '/customers',
          icon: 'Users',
          permission: 'customers:view',
        },
        {
          key: 'billing',
          label: '结算管理',
          route: '/billing',
          icon: 'CreditCard',
          children: [
            { key: 'settlement', label: '结算单', route: '/billing/settlement', hint: '列表', icon: 'FileText' },
            { key: 'reconciliation', label: '对账单', route: '/billing/reconciliation', hint: '列表', icon: 'CheckCheck' },
          ],
        },
      ],
    },
    {
      key: 'analytics',
      title: '运营分析',
      items: [
        {
          key: 'analytics',
          label: '客户分析',
          route: '/analytics',
          icon: 'BarChart2',
        },
      ],
    },
    {
      key: 'system',
      title: '系统管理',
      items: [
        {
          key: 'governance',
          label: '系统治理',
          route: '/governance',
          icon: 'Settings',
        },
      ],
    },
  ])

  // ─── 当前页面标题（保留原 route.name 映射） ─────────────────────
  const pageTitle = computed(() => {
    const titleMap: Record<string, string> = {
      Dashboard: '运营工作台',
      Customers: '客户管理',
      CustomerDetail: '客户详情',
      Billing: '结算管理',
      SettlementList: '结算单列表',
      ReconciliationList: '对账单列表',
      Analytics: '客户分析',
      Governance: '系统治理',
      Settings: '设置',
      Profile: '个人中心',
    }
    return titleMap[route.name as string] || '客户运营中台'
  })

  const can = (permission: string) => userStore.hasPermission(permission)
  const currentUser = computed(() => userStore.userInfo)
  const userPermissions = computed(() => userStore.permissions)

  // ─── 方法 ──────────────────────────────────────────────────────
  const setCollapsed = (value: boolean) => {
    sidebarCollapsed.value = value
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(value))
  }

  const toggleSidebar = () => {
    setCollapsed(!sidebarCollapsed.value)
  }

  const toggleMobileMenu = () => { mobileMenuOpen.value = !mobileMenuOpen.value }
  const closeMobileMenu = () => { mobileMenuOpen.value = false }

  const toggleSubmenu = (menu: string) => {
    if (sidebarCollapsed.value) return
    expandedSubmenu.value = expandedSubmenu.value === menu ? null : menu
  }

  const handleSubmenuHover = (menu: string | null) => {
    if (sidebarCollapsed.value) hoveredSubmenu.value = menu
  }

  const isParentMenuActive = (menu: string): boolean => {
    if (menu === 'billing') return route.path.startsWith('/billing')
    if (menu === 'customers') return route.path.startsWith('/customers')
    if (menu === 'analytics') return route.path.startsWith('/analytics')
    if (menu === 'governance') return route.path.startsWith('/governance')
    return false
  }

  const handleLogout = () => {
    userStore.logout()
    Message.success('已退出登录')
    router.push('/login')
  }

  // ─── 监听路由变化（仅注册一次） ─────────────────────────────────────────
  if (!initialized) {
    initialized = true
    watch(() => route.path, (newPath) => {
      if (newPath.startsWith('/billing')) expandedSubmenu.value = 'billing'
      else if (newPath.startsWith('/analytics')) expandedSubmenu.value = 'analytics'
      else if (newPath.startsWith('/tags') || newPath.startsWith('/users') || newPath.startsWith('/roles') || newPath.startsWith('/system')) expandedSubmenu.value = 'system'
      else expandedSubmenu.value = null
      mobileMenuOpen.value = false
    }, { immediate: true })
  }

  // ─── 返回 ───────────────────────────────────────────────────────
  return {
    sidebarCollapsed,
    expandedSubmenu,
    hoveredSubmenu,
    mobileMenuOpen,
    navSections,
    pageTitle,
    can,
    currentUser,
    userPermissions,
    setCollapsed,
    toggleSidebar,
    toggleMobileMenu,
    closeMobileMenu,
    toggleSubmenu,
    handleSubmenuHover,
    isParentMenuActive,
    handleLogout,
  }
}