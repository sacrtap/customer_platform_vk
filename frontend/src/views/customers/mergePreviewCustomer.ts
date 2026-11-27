import type { Customer, CustomerDetail } from '@/types'

/**
 * 合并「客户列表行」与「客户详情接口」数据，生成 360 预览抽屉使用的客户对象。
 *
 * 两个接口同名字段形状不同：详情接口的 `balance` 是余额明细对象，
 * 列表接口的 `balance` 是数值。预览 KPI「当前余额」必须用数值，
 * 若直接让详情对象覆盖列表数值，`formatCurrency` 会输出「¥NaN」。
 */
export function mergePreviewCustomer(row: Customer | null, detail: CustomerDetail): Customer {
  const { balance: detailBalance, ...detailFields } = detail
  return {
    // 列表行提供余额/30天消耗/健康度等列表口径字段
    ...row,
    // 详情接口提供 ERP/合作状态/关键日期/停用/备注等完整基础字段
    ...detailFields,
    balance: detailBalance?.total_amount ?? row?.balance ?? null,
  } as Customer
}
