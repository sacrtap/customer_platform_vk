/**
 * 结算单计费明细格式化工具
 *
 * 共享给 GenerateInvoiceModal（预览）和 InvoiceDetailDrawer（详情）使用，
 * 确保两处展示的计费明细结构一致。
 */

import { formatCurrency } from './formatters'
import type { InvoiceItem } from '@/api/billing'

/** 阶梯配置条目 */
interface TierRange {
  min: number
  max: number | null
  price: number
}

/** 计费类型文本 — 兼容后端 pricing/tiered/yearly 和前端 fixed/tiered/package */
export function pricingTypeText(type?: string): string {
  const map: Record<string, string> = {
    fixed: '定价',
    pricing: '定价',
    tiered: '阶梯',
    package: '包年',
    yearly: '包年',
  }
  return type ? map[type] || type : '—'
}

/** 格式化数字（去除浮点精度问题） */
export function formatItemNumber(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/\.?0+$/, '')
}

/** 格式化用量显示（返回多行，多层递增模式分两行） */
export function formatQuantity(record: InvoiceItem): string[] {
  if (record.pricing_type === 'package' && record.package_type === 'unlimited') {
    return [`${formatItemNumber(record.quantity)} 层`]
  }
  if (record.order_count != null && record.order_count !== record.quantity) {
    // 多层递增：首行订单数，第二行层数
    return [`${formatItemNumber(record.order_count)} 单`, `${formatItemNumber(record.quantity)} 层`]
  }
  return [`${formatItemNumber(record.quantity)}`]
}

/** 格式化计费规则详情（返回多行文本数组） */
export function formatRuleDetail(record: InvoiceItem): string[] {
  if (!record.pricing_type) return ['—']

  // formatCurrency 已含 ¥ 前缀（style: currency），不再额外添加
  const fmtPrice = (v: number | null | undefined) => formatCurrency(v ?? 0)
  const fmtNum = (v: number | null | undefined) => formatItemNumber(v ?? 0)

  if (record.pricing_type === 'fixed') {
    if (
      record.multi_floor_pricing_type === 'incremental' &&
      record.additional_floor_price != null
    ) {
      const orderCount = record.order_count ?? 0
      const extraFloors = Math.max(0, record.quantity - orderCount)
      return [
        `基础单价 ${fmtPrice(record.unit_price)}/单 × ${fmtNum(orderCount)} 单`,
        `附加楼层 ${fmtPrice(record.additional_floor_price)}/层 × ${fmtNum(extraFloors)} 层`,
      ]
    }
    return [`单价 ${fmtPrice(record.unit_price)}/单`]
  }

  if (record.pricing_type === 'tiered') {
    const tiers = parseTiers(record.tiers)
    if (tiers.length === 0) return [`平均单价 ${fmtPrice(record.unit_price)}`]

    const lines = tiers.map((t) => {
      const range = t.max == null ? `${t.min}+` : `${t.min}~${t.max}`
      return `${range} @ ${fmtPrice(t.price)}`
    })
    lines.push(`平均单价 ${fmtPrice(record.unit_price)}`)
    return lines
  }

  if (record.pricing_type === 'package') {
    if (record.package_type === 'unlimited') {
      const days = record.period_days ?? 0
      return [
        '不限量套餐',
        `年费 ${fmtPrice(record.base_fee)} → 日费 ${fmtPrice(record.unit_price)}`,
        `周期 ${days} 天 × ${fmtPrice(record.unit_price)}/天`,
      ]
    }
    if (record.package_type === 'limited') {
      const lines: string[] = ['限量套餐']
      if (record.base_fee != null) {
        lines.push(`年费 ${fmtPrice(record.base_fee)}`)
      }
      const limit = record.limit_count ?? 0
      lines.push(`套餐内 ${fmtNum(limit)} 单 @ ${fmtPrice(record.unit_price)}/单`)
      if (record.usage_cost != null) {
        lines.push(`套餐内费用 ${fmtPrice(record.usage_cost)}`)
      }
      const overQty = record.over_limit_quantity ?? 0
      if (overQty > 0) {
        lines.push(
          `超量 ${fmtNum(overQty)} 单 @ ${fmtPrice(record.over_limit_unit_price)}/单 = ${fmtPrice(record.over_limit_cost)}`
        )
      }
      return lines
    }
  }

  return ['—']
}

/** 解析阶梯配置 */
export function parseTiers(raw: unknown): TierRange[] {
  if (!raw) return []
  let arr: Array<{ min?: number; max?: number | null; price?: number }> = []
  if (Array.isArray(raw)) {
    arr = raw as Array<{ min?: number; max?: number | null; price?: number }>
  } else if (typeof raw === 'object' && raw !== null) {
    const obj = raw as Record<string, unknown>
    if (Array.isArray(obj.ranges)) {
      arr = obj.ranges as Array<{ min?: number; max?: number | null; price?: number }>
    }
  }
  return arr
    .filter((t) => t.min != null && t.price != null)
    .map((t) => ({
      min: t.min ?? 0,
      max: t.max ?? null,
      price: t.price ?? 0,
    }))
    .sort((a, b) => a.min - b.min)
}
