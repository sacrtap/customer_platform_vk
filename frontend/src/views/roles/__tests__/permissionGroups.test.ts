import { describe, it, expect } from 'vitest'
import {
  buildPermissionGroups,
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
    const permissions: PermissionLike[] = [
      { id: 9, code: 'misc:view', name: '查看其他' },
    ]

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
