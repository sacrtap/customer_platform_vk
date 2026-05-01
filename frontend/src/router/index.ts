import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/views/ResetPassword.vue'),
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/users/Index.vue'),
        meta: { requiresPermission: 'users:view' },
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('@/views/roles/Index.vue'),
        meta: { requiresPermission: 'roles:view' },
      },
      {
        path: 'customers',
        name: 'Customers',
        component: () => import('@/views/customers/Index.vue'),
        meta: { requiresPermission: 'customers:view' },
      },
      {
        path: 'customers/:id',
        name: 'CustomerDetail',
        component: () => import('@/views/customers/Detail.vue'),
        meta: { requiresPermission: 'customers:view' },
      },
      {
        path: 'tags',
        name: 'Tags',
        component: () => import('@/views/tags/Index.vue'),
        meta: { requiresPermission: 'tags:view' },
      },
      {
        path: 'customer-groups',
        name: 'CustomerGroups',
        component: () => import('@/views/customer-groups/Index.vue'),
        meta: { requiresPermission: 'customers:view' },
      },
      {
        path: 'billing',
        name: 'Billing',
        children: [
          {
            path: 'balances',
            name: 'Balance',
            component: () => import('@/views/billing/Balance.vue'),
            meta: { requiresPermission: 'billing:view' },
          },
          {
            path: 'pricing-rules',
            name: 'PricingRules',
            component: () => import('@/views/billing/PricingRules.vue'),
            meta: { requiresPermission: 'billing:view' },
          },
          {
            path: 'invoices',
            name: 'Invoices',
            component: () => import('@/views/billing/Invoices.vue'),
            meta: { requiresPermission: 'billing:view' },
          },
        ],
      },
      {
        path: 'analytics',
        name: 'Analytics',
        children: [
          {
            path: 'consumption',
            name: 'ConsumptionAnalysis',
            component: () => import('@/views/analytics/Consumption.vue'),
            meta: { requiresPermission: 'analytics:view' },
          },
          {
            path: 'payment',
            name: 'PaymentAnalysis',
            component: () => import('@/views/analytics/Payment.vue'),
            meta: { requiresPermission: 'analytics:view' },
          },
          {
            path: 'health',
            name: 'HealthAnalysis',
            component: () => import('@/views/analytics/Health.vue'),
            meta: { requiresPermission: 'analytics:view' },
          },
          {
            path: 'profile',
            name: 'ProfileAnalysis',
            component: () => import('@/views/analytics/Profile.vue'),
            meta: { requiresPermission: 'analytics:view' },
          },
          {
            path: 'forecast',
            name: 'ForecastAnalysis',
            component: () => import('@/views/analytics/Forecast.vue'),
            meta: { requiresPermission: 'analytics:view' },
          },
        ],
      },
      {
        path: 'system',
        name: 'System',
        children: [
          {
            path: 'sync-logs',
            name: 'SyncLogs',
            component: () => import('@/views/system/SyncLogs.vue'),
            meta: { requiresPermission: 'system:view' },
          },
          {
            path: 'audit-logs',
            name: 'AuditLogs',
            component: () => import('@/views/system/AuditLogs.vue'),
            meta: { requiresPermission: 'system:view' },
          },
        ],
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore()
  // 确保从 storage 初始化用户状态
  userStore.initFromStorage()

  // 登录态检查：token 不存在或已过期
  if (to.meta.requiresAuth) {
    if (!userStore.token || userStore.isTokenExpired()) {
      userStore.logout() // 清理所有状态
      next('/login')
      return
    }
  }

  // 已登录访问登录页，重定向到首页
  if (to.path === '/login' && userStore.token && !userStore.isTokenExpired()) {
    next({ path: '/', replace: true, force: true })
    return
  }

  // 权限检查
  const requiredPermission = to.meta.requiresPermission as string | undefined
  if (requiredPermission && userStore.token) {
    if (!userStore.hasPermission(requiredPermission)) {
      // 无权限，跳转到首页
      next({ path: '/', replace: true })
      return
    }
  }

  next()
})

export default router
