import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

/**
 * 运营工作台角色画像
 *
 * 依据用户权限码派生首屏展示 tier（超管 > 运营经理 > 销售经理 互斥优先）。
 * 权限码语义（backend/scripts/seed.py）：
 * - customers:view_all —— 仅超级管理员持有（数据全局可见）
 * - billing:ops_approve —— 运营经理确认结算单（第一步，运营经理独有）
 * - billing:sales_approve —— 销售经理确认结算单（第二步，销售经理独有）
 * - system:view —— 系统管理可见（数据同步等）
 */
export interface WorkbenchRoleProfile {
  /** 首屏场景档位：admin=全局经营视图 / ops=我负责的客户 / sales=我跟进的客户 */
  tier: 'admin' | 'ops' | 'sales'
  canViewAll: boolean
  canOpsConfirm: boolean
  canSalesApprove: boolean
  canManageSystem: boolean
}

const SUPER_ADMIN_ROLE = '超级管理员'

export function deriveRoleProfile(
  perms: ReadonlySet<string>,
  roles: readonly string[] = []
): WorkbenchRoleProfile {
  const superAdmin = roles.includes(SUPER_ADMIN_ROLE)
  const canViewAll = superAdmin || perms.has('customers:view_all')
  const canOpsConfirm = superAdmin || perms.has('billing:ops_approve')
  const canSalesApprove = superAdmin || perms.has('billing:sales_approve')
  const canManageSystem = superAdmin || perms.has('system:view')

  let tier: WorkbenchRoleProfile['tier']
  if (canViewAll) {
    tier = 'admin'
  } else if (canOpsConfirm) {
    tier = 'ops'
  } else {
    // 未知/仅查看角色按最小权限视角降级为 sales
    tier = 'sales'
  }

  return { tier, canViewAll, canOpsConfirm, canSalesApprove, canManageSystem }
}

/** 工作台角色画像组合式函数（供 Home.vue 使用） */
export function useWorkbenchRole() {
  const userStore = useUserStore()
  const roleProfile = computed(() =>
    deriveRoleProfile(userStore.permissions, userStore.userInfo?.roles ?? [])
  )
  return { roleProfile }
}
