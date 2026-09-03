<template>
  <div class="page-container">
    <div class="page-header">
      <h1>结算单日志</h1>
      <p class="page-desc">监控结算单明细文件生成状态</p>
    </div>

    <div class="filter-bar">
      <a-select
        v-model="filters.status"
        placeholder="文件状态"
        allow-clear
        style="width: 160px"
        @change="loadLogs"
      >
        <a-option value="generating">生成中</a-option>
        <a-option value="completed">已完成</a-option>
        <a-option value="failed">失败</a-option>
      </a-select>
      <a-button @click="loadLogs">刷新</a-button>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th style="width: 160px">结算单号</th>
            <th>客户</th>
            <th style="width: 200px">结算周期</th>
            <th style="width: 100px; text-align: right">总金额</th>
            <th style="width: 100px">文件状态</th>
            <th style="width: 160px">更新时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td>{{ log.invoice_no }}</td>
            <td>{{ log.customer_name || '-' }}</td>
            <td>{{ log.period_start }} ~ {{ log.period_end }}</td>
            <td style="text-align: right">{{ formatCurrency(log.total_amount) }}</td>
            <td>
              <span v-if="log.detail_file_status === 'completed'" class="badge green">已完成</span>
              <span v-else-if="log.detail_file_status === 'generating'" class="badge blue"
                >生成中</span
              >
              <span v-else-if="log.detail_file_status === 'failed'" class="badge red">失败</span>
              <span v-else class="badge grey">待生成</span>
            </td>
            <td>{{ formatDateTime(log.updated_at) }}</td>
          </tr>
          <tr v-if="logs.length === 0">
            <td :colspan="6" class="empty-state">暂无日志</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pagination">
      <a-pagination
        v-model:current="pagination.page"
        :total="pagination.total"
        :page-size="pagination.pageSize"
        show-total
        @change="loadLogs"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { getInvoiceDetailLogs } from '@/api/billing'
import { formatCurrency, formatDateTime } from '@/utils/formatters'
import { handleError } from '@/utils/errorHandler'

interface DetailLog {
  id: number
  invoice_no: string
  customer_id: number
  customer_name: string | null
  period_start: string | null
  period_end: string | null
  detail_file_status: string
  detail_file_path: string | null
  total_amount: number
  created_at: string | null
  updated_at: string | null
}

const logs = reactive<DetailLog[]>([])
const filters = reactive({
  status: undefined as string | undefined,
})
const pagination = reactive({
  page: 1,
  total: 0,
  pageSize: 20,
})

const loadLogs = async () => {
  try {
    const res = await getInvoiceDetailLogs({
      status: filters.status,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    logs.splice(0, logs.length, ...res.data.data.list)
    pagination.total = res.data.data.total
  } catch (error) {
    handleError(error)
  }
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.page-container {
  padding: 24px;
}
.page-header {
  margin-bottom: 20px;
}
.page-header h1 {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  margin: 0 0 4px 0;
}
.page-desc {
  color: var(--muted);
  font-size: 14px;
  margin: 0;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 12px;
}
.table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}
.table th,
.table td {
  padding: 10px 12px;
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  white-space: nowrap;
}
.table th {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}
.badge.green {
  background: #d1fae5;
  color: #065f46;
}
.badge.blue {
  background: #dbeafe;
  color: #1e40af;
}
.badge.red {
  background: #fee2e2;
  color: #991b1b;
}
.badge.grey {
  background: #f3f4f6;
  color: #6b7280;
}
.empty-state {
  text-align: center;
  padding: 32px 20px;
  color: var(--muted);
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
