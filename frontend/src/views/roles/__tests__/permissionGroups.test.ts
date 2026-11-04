import { describe, it, expect } from 'vitest'
import {
  buildBillingSubGroups,
  buildPermissionGroups,
  filterPermissionsByKeyword,
  MODULE_NAME_MAP,
  MODULE_ORDER,
  type PermissionLike,
} from '../permissionGroups'

describe('buildPermissionGroups', () => {
  it('groups permissions by module and returns groups in MODULE_ORDER', () => {
    const permissions: PermissionLike[] = [
      { id: 2, module: 'billing', code: 'billing:edit', name: '编辑结算' },
      { id: 1, module: 'billing', code: 'billing:view', name: '查看结算' },
      { id: 3, module: 'analytics', code: 'analytics:view', name: '查看分析' },
    ]

    const groups = buildPermissionGroups(permissions)

    expect(groups).toHaveLength(2)

    const billingGroup = groups.find((g) => g.key === 'billing')
    expect(billingGroup).toBeDefined()
    expect(billingGroup!.title).toBe('结算管理')
    expect(billingGroup!.permissions.map((p) => p.id)).toEqual([1, 2])

    const analyticsGroup = groups.find((g) => g.key === 'analytics')
    expect(analyticsGroup).toBeDefined()
    expect(analyticsGroup!.title).toBe('客户分析')
  })

  it('places permissions with no module under "other" group', () => {
    const permissions: PermissionLike[] = [{ id: 9, code: 'misc:view', name: '查看其他' }]

    const groups = buildPermissionGroups(permissions)
    const otherGroup = groups.find((g) => g.key === 'other')

    expect(otherGroup).toBeDefined()
    expect(otherGroup!.title).toBe('其他权限')
    expect(otherGroup!.permissions).toHaveLength(1)
    expect(otherGroup!.permissions[0].id).toBe(9)
  })

  it('orders groups by MODULE_ORDER and sorts unknown modules by title', () => {
    const permissions: PermissionLike[] = [
      { id: 1, module: 'roles', code: 'roles:view', name: '查看角色' },
      { id: 2, module: 'customers', code: 'customers:view', name: '查看客户' },
      { id: 3, module: 'billing', code: 'billing:view', name: '查看结算' },
    ]

    const groups = buildPermissionGroups(permissions)
    const keys = groups.map((g) => g.key)

    // customers (index 0), billing (index 1), roles (index 5) in MODULE_ORDER
    expect(keys.indexOf('customers')).toBeLessThan(keys.indexOf('billing'))
    expect(keys.indexOf('billing')).toBeLessThan(keys.indexOf('roles'))
  })

  it('sorts permissions within a group by ascending id', () => {
    const permissions: PermissionLike[] = [
      { id: 10, module: 'billing', code: 'billing:refund', name: '退款操作' },
      { id: 2, module: 'billing', code: 'billing:view', name: '查看结算' },
      { id: 5, module: 'billing', code: 'billing:recharge', name: '充值操作' },
    ]

    const groups = buildPermissionGroups(permissions)
    const billingGroup = groups.find((g) => g.key === 'billing')!

    expect(billingGroup.permissions.map((p) => p.id)).toEqual([2, 5, 10])
  })

  it('returns an empty array for empty input', () => {
    const groups = buildPermissionGroups([])
    expect(groups).toEqual([])
  })

  it('uses MODULE_NAME_MAP for group titles', () => {
    // Verify that every key in MODULE_ORDER (except 'other') has a title in MODULE_NAME_MAP
    for (const key of MODULE_ORDER) {
      if (key === 'other') continue // 'other' has "其他权限" in the map
      expect(MODULE_NAME_MAP[key]).toBeDefined()
    }
  })
})

describe('buildBillingSubGroups', () => {
  const billingPermissions: PermissionLike[] = [
    { id: 60, module: 'billing', code: 'billing:view', name: '查看结算' },
    { id: 61, module: 'billing', code: 'billing:edit', name: '编辑计费配置' },
    { id: 62, module: 'billing', code: 'billing:package_edit', name: '编辑包年套餐' },
    { id: 63, module: 'billing', code: 'billing:recharge', name: '充值操作' },
    { id: 64, module: 'billing', code: 'billing:invoice_generate', name: '生成结算单' },
    { id: 65, module: 'billing', code: 'billing:ops_approve', name: '运营经理确认' },
  ]

  it('splits billing permissions into business subgroups in rule order', () => {
    const subGroups = buildBillingSubGroups(billingPermissions)

    expect(subGroups.map((sg) => sg.key)).toEqual([
      'general',
      'pricing',
      'package',
      'balance',
      'invoice',
      'approval',
    ])
    expect(subGroups.map((sg) => sg.title)).toEqual([
      '通用',
      '计费规则',
      '包年套餐',
      '余额管理',
      '结算单管理',
      '审批与减免',
    ])
  })

  it('places each code in its mapped subgroup', () => {
    const subGroups = buildBillingSubGroups(billingPermissions)

    expect(subGroups.find((sg) => sg.key === 'general')!.permissions.map((p) => p.code)).toEqual([
      'billing:view',
    ])
    expect(subGroups.find((sg) => sg.key === 'pricing')!.permissions.map((p) => p.code)).toEqual([
      'billing:edit',
    ])
    expect(subGroups.find((sg) => sg.key === 'invoice')!.permissions.map((p) => p.code)).toEqual([
      'billing:invoice_generate',
    ])
  })

  it('drops empty subgroups', () => {
    const subGroups = buildBillingSubGroups([
      { id: 60, module: 'billing', code: 'billing:view', name: '查看结算' },
    ])

    expect(subGroups).toHaveLength(1)
    expect(subGroups[0].key).toBe('general')
  })

  it('falls unregistered codes into the "other" subgroup (drift guard)', () => {
    const subGroups = buildBillingSubGroups([
      { id: 99, module: 'billing', code: 'billing:brand_new', name: '全新权限' },
      { id: 60, module: 'billing', code: 'billing:view', name: '查看结算' },
    ])

    const other = subGroups.find((sg) => sg.key === 'other')
    expect(other).toBeDefined()
    expect(other!.title).toBe('其他')
    expect(other!.permissions.map((p) => p.code)).toEqual(['billing:brand_new'])
    // 兜底子区排在规则子区之后
    expect(subGroups[subGroups.length - 1].key).toBe('other')
  })

  it('sorts permissions within a subgroup by ascending id', () => {
    const subGroups = buildBillingSubGroups([
      { id: 65, module: 'billing', code: 'billing:invoice_submit', name: '提交结算单' },
      { id: 64, module: 'billing', code: 'billing:invoice_generate', name: '生成结算单' },
    ])

    expect(subGroups[0].permissions.map((p) => p.id)).toEqual([64, 65])
  })

  it('buildPermissionGroups attaches subGroups to the billing group only', () => {
    const groups = buildPermissionGroups(billingPermissions)

    const billingGroup = groups.find((g) => g.key === 'billing')!
    expect(billingGroup.subGroups).toBeDefined()
    expect(billingGroup.subGroups!.length).toBeGreaterThan(0)
  })

  it('buildPermissionGroups leaves non-billing groups without subGroups', () => {
    const groups = buildPermissionGroups([
      { id: 1, module: 'customers', code: 'customers:view', name: '查看客户' },
      { id: 2, module: 'billing', code: 'billing:view', name: '查看结算' },
    ])

    expect(groups.find((g) => g.key === 'customers')!.subGroups).toBeUndefined()
    expect(groups.find((g) => g.key === 'billing')!.subGroups).toBeDefined()
  })
})

describe('filterPermissionsByKeyword', () => {
  const permissions: PermissionLike[] = [
    { id: 1, module: 'customers', code: 'customers:view_all', name: '查看全部客户' },
    { id: 2, module: 'customers', code: 'customers:view', name: '查看客户' },
    { id: 3, module: 'system', code: 'system:database_clear', name: '数据清空' },
  ]

  it('returns all permissions for empty keyword', () => {
    expect(filterPermissionsByKeyword(permissions, '')).toEqual(permissions)
    expect(filterPermissionsByKeyword(permissions, '   ')).toEqual(permissions)
  })

  it('matches code substring', () => {
    const result = filterPermissionsByKeyword(permissions, 'view_all')
    expect(result.map((p) => p.id)).toEqual([1])
  })

  it('matches name', () => {
    const result = filterPermissionsByKeyword(permissions, '清空')
    expect(result.map((p) => p.id)).toEqual([3])
  })

  it('matches case-insensitively', () => {
    const result = filterPermissionsByKeyword(permissions, 'DATABASE_CLEAR')
    expect(result.map((p) => p.id)).toEqual([3])
  })

  it('returns empty array when nothing matches', () => {
    expect(filterPermissionsByKeyword(permissions, 'nonexistent')).toEqual([])
  })
})
