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
  /** 组内子分区（当前仅 billing 组有；无则平铺渲染） */
  subGroups?: PermissionSubGroup<T>[]
}

export interface PermissionSubGroup<T extends PermissionLike = PermissionLike> {
  key: string
  title: string
  permissions: T[]
}

/** 模块标识 → 中文标题（与侧边栏菜单名对齐） */
export const MODULE_NAME_MAP: Record<string, string> = {
  customers: '客户管理',
  billing: '结算管理',
  vr_settlement: 'VR编辑费用结算',
  analytics: '客户分析',
  tags: '标签管理',
  users: '用户管理',
  roles: '角色权限',
  system: '系统管理',
  files: '文件管理',
  webhooks: 'Webhook 管理',
  profiles: '客户画像',
  industry_types: '行业类型',
  cooperation_statuses: '合作状态',
  balance_whitelist: '余额白名单',
  api_keys: 'API-Key',
  erp_systems: 'ERP系统',
  other: '其他权限',
}

/** 模块显示顺序（按侧边栏一级菜单顺序排列） */
export const MODULE_ORDER: string[] = [
  'customers',
  'billing',
  'vr_settlement',
  'analytics',
  'tags',
  'users',
  'roles',
  'system',
  'files',
  'industry_types',
  'cooperation_statuses',
  'erp_systems',
  'balance_whitelist',
  'api_keys',
]

/**
 * 按关键词过滤权限（角色权限弹窗搜索用）。
 *
 * 对 name 与 code 做大小写不敏感的子串匹配；keyword 为空/空白时返回原数组。
 * 纯函数，无 UI 依赖，可独立单元测试。
 */
export function filterPermissionsByKeyword<T extends PermissionLike>(
  permissions: T[],
  keyword: string
): T[] {
  const kw = keyword.trim().toLowerCase()
  if (!kw) return permissions
  return permissions.filter(
    (perm) => perm.name.toLowerCase().includes(kw) || perm.code.toLowerCase().includes(kw)
  )
}

/**
 * billing 组内子分区规则：与侧边栏「结算管理」子菜单对应。
 * 按 code 精确映射；未登记的 billing 新码归「其他」子区（兜底防漂移——
 * 新增码忘记登记规则时仍可见、可授权，不会静默消失在平铺列表外）。
 */
const BILLING_SUBGROUP_RULES: { key: string; title: string; codes: string[] }[] = [
  { key: 'general', title: '通用', codes: ['billing:view'] },
  {
    key: 'pricing',
    title: '计费规则',
    codes: ['billing:edit', 'billing:delete', 'billing:pricing_import', 'billing:pricing_export'],
  },
  {
    key: 'package',
    title: '包年套餐',
    codes: [
      'billing:package_edit',
      'billing:package_delete',
      'billing:package_import',
      'billing:package_export',
    ],
  },
  {
    key: 'balance',
    title: '余额管理',
    codes: ['billing:recharge', 'billing:balance_import', 'billing:balance_export'],
  },
  {
    key: 'invoice',
    title: '结算单管理',
    codes: [
      'billing:invoice_import',
      'billing:invoice_export',
      'billing:confirm',
      'billing:detail_status_view',
      'billing:detail_regenerate',
      'billing:invoice_generate',
      'billing:invoice_submit',
    ],
  },
  {
    key: 'approval',
    title: '审批与减免',
    codes: [
      'billing:ops_approve',
      'billing:sales_approve',
      'billing:discount_approve',
      'billing:discount_apply',
    ],
  },
]

/** 将 billing 组权限按业务面拆为子分区；子分区按规则顺序输出，空区过滤，组内按 id 升序。 */
export function buildBillingSubGroups<T extends PermissionLike>(
  permissions: T[]
): PermissionSubGroup<T>[] {
  const codeToRule = new Map<string, string>()
  for (const rule of BILLING_SUBGROUP_RULES) {
    for (const code of rule.codes) {
      codeToRule.set(code, rule.key)
    }
  }
  const ruleByKey = new Map(BILLING_SUBGROUP_RULES.map((rule) => [rule.key, rule]))

  const buckets = new Map<string, T[]>()
  for (const perm of permissions) {
    const key = codeToRule.get(perm.code) ?? 'other'
    if (!buckets.has(key)) buckets.set(key, [])
    buckets.get(key)!.push(perm)
  }

  const orderedKeys = [...BILLING_SUBGROUP_RULES.map((rule) => rule.key), 'other']
  return orderedKeys
    .filter((key) => (buckets.get(key) ?? []).length > 0)
    .map((key) => ({
      key,
      title: ruleByKey.get(key)?.title ?? '其他',
      permissions: [...buckets.get(key)!].sort((a, b) => a.id - b.id),
    }))
}

/**
 * 将权限列表按 module 分组为卡片数据。
 * 未指定 module 的权限归入 "其他权限" 分组。
 * 分组顺序按 MODULE_ORDER 排列；未知模块按标题字母序排在已知模块之后。
 * 每组内的权限按 id 升序排列以确保稳定顺序。
 * billing 组额外填充 subGroups（组内按业务面二级分区）。
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

  return sortedKeys.map((key) => {
    const sorted = [...(groups[key] ?? [])].sort((a, b) => a.id - b.id)
    const group: PermissionGroup<T> = {
      key,
      title: MODULE_NAME_MAP[key] || key,
      permissions: sorted,
    }
    if (key === 'billing') {
      group.subGroups = buildBillingSubGroups(sorted)
    }
    return group
  })
}
