/**
 * 权限分组辅助函数
 *
 * 将扁平的权限列表按照后端 module 字段分组，并按侧边栏菜单顺序排序。
 * 纯逻辑，无 UI 依赖，可独立单元测试。
 */

export interface PermissionLike {
  id: number
  code: string
  name: string
  description?: string
  module?: string
}

export interface PermissionGroup<T extends PermissionLike = PermissionLike> {
  key: string
  title: string
  permissions: T[]
}

/** 模块标识 → 中文标题（与侧边栏菜单名对齐） */
export const MODULE_NAME_MAP: Record<string, string> = {
  customers: '客户管理',
  billing: '结算管理',
  analytics: '客户分析',
  tags: '标签管理',
  users: '用户管理',
  roles: '角色权限',
  industry_types: '行业类型',
  system: '系统管理',
  groups: '客户分组',
  files: '文件管理',
  webhooks: 'Webhook 管理',
  profiles: '客户画像',
  other: '其他权限',
}

/** 模块显示顺序（按侧边栏一级菜单顺序排列） */
export const MODULE_ORDER: string[] = [
  'customers',
  'billing',
  'analytics',
  'tags',
  'users',
  'roles',
  'industry_types',
  'system',
  'files',
  'webhooks',
  'profiles',
  'groups',
  'other',
]

/**
 * 将权限列表按 module 分组为卡片数据。
 * 未指定 module 的权限归入 "其他权限" 分组。
 * 分组顺序按 MODULE_ORDER 排列；未知模块按标题字母序排在已知模块之后。
 * 每组内的权限按 id 升序排列以确保稳定顺序。
 */
export function buildPermissionGroups<T extends PermissionLike>(
  permissions: T[]
): PermissionGroup<T>[] {
  const groups: Record<string, T[]> = {}

  for (const perm of permissions) {
    const key = perm.module || 'other'
    if (!groups[key]) {
      groups[key] = []
    }
    groups[key].push(perm)
  }

  const sortedKeys = Object.keys(groups).sort((a, b) => {
    const ia = MODULE_ORDER.indexOf(a)
    const ib = MODULE_ORDER.indexOf(b)
    if (ia !== -1 && ib !== -1) return ia - ib
    if (ia !== -1) return -1
    if (ib !== -1) return 1
    return (MODULE_NAME_MAP[a] ?? a).localeCompare(MODULE_NAME_MAP[b] ?? b, 'zh-CN')
  })

  return sortedKeys.map((key) => ({
    key,
    title: MODULE_NAME_MAP[key] || key,
    permissions: [...(groups[key] ?? [])].sort((a, b) => a.id - b.id),
  }))
}
