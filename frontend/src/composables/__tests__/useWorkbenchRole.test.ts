import { describe, expect, it } from 'vitest'
import { deriveRoleProfile } from '@/composables/useWorkbenchRole'

describe('deriveRoleProfile', () => {
  it('超管（view_all 权限 + 超级管理员角色）→ admin 档', () => {
    const profile = deriveRoleProfile(
      new Set([
        'customers:view_all',
        'billing:ops_approve',
        'billing:sales_approve',
        'system:view',
      ]),
      ['超级管理员']
    )
    expect(profile.tier).toBe('admin')
    expect(profile.canViewAll).toBe(true)
    expect(profile.canOpsConfirm).toBe(true)
    expect(profile.canSalesApprove).toBe(true)
    expect(profile.canManageSystem).toBe(true)
  })

  it('运营经理（billing:ops_approve）→ ops 档', () => {
    const profile = deriveRoleProfile(
      new Set(['customers:view', 'billing:confirm', 'billing:ops_approve', 'analytics:view']),
      ['运营经理']
    )
    expect(profile.tier).toBe('ops')
    expect(profile.canViewAll).toBe(false)
    expect(profile.canOpsConfirm).toBe(true)
    expect(profile.canSalesApprove).toBe(false)
    expect(profile.canManageSystem).toBe(false)
  })

  it('销售经理（billing:sales_approve）→ sales 档', () => {
    const profile = deriveRoleProfile(
      new Set(['customers:view', 'billing:sales_approve', 'analytics:view']),
      ['销售经理']
    )
    expect(profile.tier).toBe('sales')
    expect(profile.canOpsConfirm).toBe(false)
    expect(profile.canSalesApprove).toBe(true)
  })

  it('未知只读角色（无审批权限）→ 降级 sales 档（最小权限视角）', () => {
    const profile = deriveRoleProfile(new Set(['customers:view', 'analytics:view']), ['数据分析师'])
    expect(profile.tier).toBe('sales')
    expect(profile.canOpsConfirm).toBe(false)
    expect(profile.canSalesApprove).toBe(false)
  })

  it('admin 优先级高于 ops/sales（三者互斥）', () => {
    const profile = deriveRoleProfile(new Set(['customers:view_all']), [])
    expect(profile.tier).toBe('admin')
  })
})
