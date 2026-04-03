import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
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
        meta: { requiresPermission: 'users:manage' },
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('@/views/roles/Index.vue'),
        meta: { requiresPermission: 'roles:manage' },
      },
      {
        path: 'customers',
        name: 'Customers',
        component: () => import('@/views/customers/Index.vue'),
        meta: { requiresPermission: 'customers:manage' },
      },
      {
        path: 'customers/:id',
        name: 'CustomerDetail',
        component: () => import('@/views/customers/Detail.vue'),
        meta: { requiresPermission: 'customers:manage' },
      },
      {
        path: 'tags',
        name: 'Tags',
        component: () => import('@/views/tags/Index.vue'),
        meta: { requiresPermission: 'tags:manage' },
      },
      {
        path: 'billing',
        name: 'Billing',
        children: [
          {
            path: 'balances',
            name: 'Balance',
            component: () => import('@/views/billing/Balance.vue'),
            meta: { requiresPermission: 'billing:manage' },
          },
          {
            path: 'pricing-rules',
            name: 'PricingRules',
            component: () => import('@/views/billing/PricingRules.vue'),
            meta: { requiresPermission: 'billing:manage' },
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
  userStore.initFromStorage()

  if (to.meta.requiresAuth && !userStore.token) {
    next('/login')
  } else if (to.path === '/login' && userStore.token) {
    next('/')
  } else {
    next()
  }
})

export default router
