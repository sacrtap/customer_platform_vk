<template>
  <div class="discount-history">
    <div class="section-header"><h3>减免修改历史</h3></div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th style="width: 160px">时间</th>
            <th style="width: 110px">金额</th>
            <th>原因</th>
            <th style="width: 100px">操作人</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="dh in histories" :key="dh.id">
            <td>{{ dh.applied_at }}</td>
            <td>
              <span :class="dh.discount_amount > 0 ? 'text-danger' : 'text-success'">
                {{ dh.discount_amount > 0 ? '-' : '+'
                }}{{ formatCurrency(Math.abs(dh.discount_amount)) }}
              </span>
            </td>
            <td>{{ dh.discount_reason || '—' }}</td>
            <td>{{ dh.applied_by_name || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { formatCurrency } from '@/utils/formatters'

/**
 * 减免修改历史区块：VR 结算单详情与结算单管理详情共用，保证两处视觉一致。
 * 两个后端详情接口的 discount_history 元素字段同构，统一用本行类型接收。
 *
 * 外观（标题 + 表格外框 + 单元格）全部由本组件自带，根元素用专属类名
 * `.discount-history`：Vue 3 scoped 会把父组件的 scope id 加到子组件根元素上，
 * 若根元素复用 `.table-wrap` 等父组件同名类，父组件的边框/圆角规则会穿透进来，
 * 造成两处渲染不一致（历史缺陷：发票侧有边框圆角、VR 侧没有）。
 * 空列表由调用方 v-if 守卫，本组件不处理空态。
 */
export interface DiscountHistoryRow {
  id: number
  discount_amount: number
  discount_reason?: string | null
  discount_attachment?: string | null
  applied_at: string
  applied_by?: number | null
  applied_by_name?: string | null
}

defineProps<{
  histories: DiscountHistoryRow[]
}>()
</script>

<style scoped>
.discount-history {
  display: flex;
  flex-direction: column;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
}

.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 15px;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.table th,
.table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border, #e5e7eb);
  text-align: left;
}

.table th {
  color: #64748b;
  font-weight: 600;
}

.text-danger {
  color: var(--red);
  white-space: nowrap;
}

.text-success {
  color: var(--green, #10b981);
  white-space: nowrap;
}
</style>
