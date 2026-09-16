/**
 * 阶梯配置（tiers）前端唯一解析实现
 *
 * 契约：tiers 的唯一形态为
 *   [{"min": number, "max": number | null, "price": number}]
 * 后端保证已是该数组形态（或 null），此处仅做容错与类型收敛。
 */

/** 阶梯配置条目 */
export interface Tier {
  min: number
  max: number | null
  price: number
}

/**
 * 解析阶梯配置。
 *
 * - null/undefined/非数组/空数组 → []
 * - 数组项缺字段时用安全默认值（min→0, max→null, price→0）
 * - 兼容历史 {ranges: [...]} 对象形态（后端已归一化，此处仅做防御）
 */
export function parseTiers(raw: unknown): Tier[] {
  if (!raw) return []

  let arr: Array<{ min?: number; max?: number | null; price?: number }> = []

  if (Array.isArray(raw)) {
    arr = raw as typeof arr
  } else if (typeof raw === 'object' && raw !== null) {
    const obj = raw as Record<string, unknown>
    if (Array.isArray(obj.ranges)) {
      arr = obj.ranges as typeof arr
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
