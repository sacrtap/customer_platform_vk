<template>
  <div class="home-page">
    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-title">客户总数</span>
          <div class="stat-icon primary">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.totalCustomers.toLocaleString() }}</div>
        <div class="stat-change positive">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fill-rule="evenodd" d="M8 12a.5.5 0 0 0 .5-.5V5.707l2.146 2.147a.5.5 0 0 0 .708-.708l-3-3a.5.5 0 0 0-.708 0l-3 3a.5.5 0 1 0 .708.708L7.5 5.707V11.5a.5.5 0 0 0 .5.5z"/>
          </svg>
          +{{ stats.customerGrowth }}% 较上月
        </div>
      </div>
      
      <div class="stat-card success">
        <div class="stat-header">
          <span class="stat-title">本月回款</span>
          <div class="stat-icon success">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        </div>
        <div class="stat-value">¥{{ (stats.monthlyRevenue / 10000).toFixed(1) }}万</div>
        <div class="stat-change positive">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fill-rule="evenodd" d="M8 12a.5.5 0 0 0 .5-.5V5.707l2.146 2.147a.5.5 0 0 0 .708-.708l-3-3a.5.5 0 0 0-.708 0l-3 3a.5.5 0 1 0 .708.708L7.5 5.707V11.5a.5.5 0 0 0 .5.5z"/>
          </svg>
          +{{ stats.revenueGrowth }}% 较上月
        </div>
      </div>
      
      <div class="stat-card warning">
        <div class="stat-header">
          <span class="stat-title">待确认账单</span>
          <div class="stat-icon warning">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.pendingInvoices }}</div>
        <div class="stat-change negative">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fill-rule="evenodd" d="M8 4a.5.5 0 0 1 .5.5v5.793l2.146-2.147a.5.5 0 0 1 .708.708l-3 3a.5.5 0 0 1-.708 0l-3-3a.5.5 0 1 1 .708-.708L7.5 10.293V4.5A.5.5 0 0 1 8 4z"/>
          </svg>
          +{{ stats.pendingGrowth }} 待处理
        </div>
      </div>
      
      <div class="stat-card danger">
        <div class="stat-header">
          <span class="stat-title">余额预警</span>
          <div class="stat-icon danger">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
        </div>
        <div class="stat-value">{{ stats.warningCustomers }}</div>
        <div class="stat-change negative">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fill-rule="evenodd" d="M8 4a.5.5 0 0 1 .5.5v5.793l2.146-2.147a.5.5 0 0 1 .708.708l-3 3a.5.5 0 0 1-.708 0l-3-3a.5.5 0 1 1 .708-.708L7.5 10.293V4.5A.5.5 0 0 1 8 4z"/>
          </svg>
          需跟进
        </div>
      </div>
    </div>
    
    <!-- 内容网格 -->
    <div class="dashboard-grid">
      <!-- 月度回款趋势 -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">月度回款趋势</h3>
          <div class="card-actions">
            <a-button size="small" @click="$message.info('导出功能开发中')">导出</a-button>
            <a-button type="primary" size="small" @click="$message.info('详情功能开发中')">查看详情</a-button>
          </div>
        </div>
        <div class="card-body">
          <div class="chart-placeholder">
            <div style="text-align: center;">
              <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="currentColor" viewBox="0 0 16 16" style="margin-bottom: 12px; opacity: 0.5; color: var(--primary-6);">
                <path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V4Zm2-1a1 1 0 0 0-1 1v.217l7 4.2 7-4.2V4a1 1 0 0 0-1-1H2Zm13 2.383-4.708 2.825L15 11.105V5.383Zm-.034 6.876-5.64-3.471L8 9.583l-1.326-.795-5.64 3.47A1 1 0 0 0 2 13h12a1 1 0 0 0 .966-.741ZM1 11.105l4.708-2.897L1 5.383v5.722Z"/>
              </svg>
              <div>ECharts 图表区域</div>
              <div style="color: var(--neutral-5); font-size: 12px; margin-top: 4px;">
                显示 12 个月回款趋势折线图
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 待办事项 -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">待办事项</h3>
          <a href="#" class="btn-text" @click.prevent="$message.info('查看全部开发中')">查看全部</a>
        </div>
        <div class="card-body">
          <div class="todo-list">
            <div class="todo-item" v-for="(todo, index) in todos" :key="index">
              <label class="todo-checkbox-wrapper">
                <input type="checkbox" v-model="todo.checked">
                <div class="todo-checkbox">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              </label>
              <div class="todo-content">
                <div class="todo-title">{{ todo.title }}</div>
                <div class="todo-meta">
                  <span :class="['todo-priority', todo.priority]">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 16 16">
                      <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                    </svg>
                    {{ todo.priorityText }}
                  </span>
                  <span class="todo-due">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 16 16">
                      <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14Zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                    </svg>
                    {{ todo.due }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 最近结算单 -->
      <div class="card full-width">
        <div class="card-header">
          <h3 class="card-title">最近结算单</h3>
          <a-button type="primary" size="small" @click="$message.info('查看全部开发中')">查看全部</a-button>
        </div>
        <div class="card-body" style="padding: 0;">
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>结算单号</th>
                  <th>客户名称</th>
                  <th>周期</th>
                  <th>金额</th>
                  <th>状态</th>
                  <th>创建时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="invoice in invoices" :key="invoice.id">
                  <td><strong>{{ invoice.no }}</strong></td>
                  <td>{{ invoice.customer }}</td>
                  <td>{{ invoice.period }}</td>
                  <td>¥{{ invoice.amount.toLocaleString() }}</td>
                  <td>
                    <span :class="['status-badge', invoice.status]">
                      <span class="status-dot"></span>
                      {{ invoice.statusText }}
                    </span>
                  </td>
                  <td>{{ invoice.createdAt }}</td>
                  <td>
                    <a-button type="text" size="small" @click="$message.info('查看开发中')">查看</a-button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Message } from '@arco-design/web-vue'

const stats = reactive({
  totalCustomers: 2847,
  customerGrowth: 12.5,
  monthlyRevenue: 1284500,
  revenueGrowth: 8.2,
  pendingInvoices: 23,
  pendingGrowth: 3,
  warningCustomers: 8,
})

const todos = ref([
  { title: '确认 XX 科技账单', priority: 'high', priorityText: '高', due: '今天 18:00 截止', checked: false },
  { title: '跟进余额不足客户', priority: 'high', priorityText: '高', due: '3 个客户', checked: false },
  { title: '审核减免申请 - YY 公司', priority: 'medium', priorityText: '中', due: '明天截止', checked: false },
  { title: '导出月度分析报告', priority: 'low', priorityText: '低', due: '本周五', checked: false },
])

const invoices = ref([
  { id: 1, no: 'INV-2026-0089', customer: 'XX 科技有限公司', period: '2026-03', amount: 128500, status: 'warning', statusText: '待确认', createdAt: '2026-04-01' },
  { id: 2, no: 'INV-2026-0088', customer: 'YY 集团有限公司', period: '2026-03', amount: 85200, status: 'info', statusText: '待付款', createdAt: '2026-04-01' },
  { id: 3, no: 'INV-2026-0087', customer: 'ZZ 创新股份', period: '2026-03', amount: 256800, status: 'success', statusText: '已完成', createdAt: '2026-03-31' },
  { id: 4, no: 'INV-2026-0086', customer: 'AA 数字科技', period: '2026-03', amount: 42300, status: 'success', statusText: '已完成', createdAt: '2026-03-30' },
])
</script>

<style scoped>
.home-page {
  --primary-1: #e8f3ff;
  --primary-5: #3296f7;
  --primary-6: #0369A1;
  --primary-7: #035a8a;
  --success-1: #e8ffea;
  --success-5: #4ade80;
  --success-6: #22c55e;
  --warning-1: #fff7e8;
  --warning-5: #fbbf24;
  --warning-6: #f59e0b;
  --danger-1: #ffe8e8;
  --danger-5: #f87171;
  --danger-6: #ef4444;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-9: #2f3645;
  --neutral-10: #1d2330;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-bottom: 32px;
}

.stat-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--neutral-2);
  transition: all var(--transition-base);
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary-5) 0%, var(--primary-6) 100%);
}

.stat-card.success::before {
  background: linear-gradient(90deg, var(--success-5) 0%, var(--success-6) 100%);
}

.stat-card.warning::before {
  background: linear-gradient(90deg, var(--warning-5) 0%, var(--warning-6) 100%);
}

.stat-card.danger::before {
  background: linear-gradient(90deg, var(--danger-5) 0%, var(--danger-6) 100%);
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.stat-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-6);
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.primary {
  background: var(--primary-1);
  color: var(--primary-6);
}

.stat-icon.success {
  background: var(--success-1);
  color: var(--success-6);
}

.stat-icon.warning {
  background: var(--warning-1);
  color: var(--warning-6);
}

.stat-icon.danger {
  background: var(--danger-1);
  color: var(--danger-6);
}

.stat-icon svg {
  width: 22px;
  height: 22px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.stat-change {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}

.stat-change.positive {
  color: var(--success-6);
}

.stat-change.negative {
  color: var(--danger-6);
}

/* 内容网格 */
.dashboard-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
}

/* 卡片 */
.card {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.card.full-width {
  grid-column: 1 / -1;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--neutral-2);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--neutral-10);
}

.card-actions {
  display: flex;
  gap: 8px;
}

.card-body {
  padding: 24px;
}

.chart-placeholder {
  height: 300px;
  background: linear-gradient(180deg, var(--primary-1) 0%, white 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 待办事项 */
.todo-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px;
  background: var(--neutral-1);
  border-radius: 12px;
  transition: all var(--transition-base);
  border: 1px solid transparent;
}

.todo-item:hover {
  background: white;
  border-color: var(--neutral-2);
  box-shadow: var(--shadow-sm);
  transform: translateX(4px);
}

.todo-checkbox-wrapper {
  position: relative;
  flex-shrink: 0;
}

.todo-checkbox-wrapper input[type="checkbox"] {
  display: none;
}

.todo-checkbox {
  width: 20px;
  height: 20px;
  border: 2px solid var(--neutral-3);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast);
  background: white;
}

.todo-checkbox svg {
  width: 14px;
  height: 14px;
  color: white;
  opacity: 0;
  transform: scale(0);
  transition: all var(--transition-fast);
}

.todo-checkbox-wrapper input[type="checkbox"]:checked + .todo-checkbox {
  background: var(--primary-6);
  border-color: var(--primary-6);
}

.todo-checkbox-wrapper input[type="checkbox"]:checked + .todo-checkbox svg {
  opacity: 1;
  transform: scale(1);
}

.todo-content {
  flex: 1;
  min-width: 0;
}

.todo-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-9);
  margin-bottom: 8px;
  line-height: 1.4;
}

.todo-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.todo-priority {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.todo-priority.high {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #dc2626;
}

.todo-priority.medium {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #d97706;
}

.todo-priority.low {
  background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
  color: #4338ca;
}

.todo-due {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--neutral-5);
}

/* 表格 */
.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th {
  text-align: left;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--neutral-6);
  background: var(--neutral-1);
  border-bottom: 1px solid var(--neutral-2);
}

td {
  padding: 16px;
  font-size: 14px;
  color: var(--neutral-7);
  border-bottom: 1px solid var(--neutral-2);
}

tr:last-child td {
  border-bottom: none;
}

tr:hover td {
  background: var(--neutral-1);
}

/* 状态徽章 */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.success {
  background: var(--success-1);
  color: var(--success-6);
}

.status-badge.warning {
  background: var(--warning-1);
  color: var(--warning-6);
}

.status-badge.danger {
  background: var(--danger-1);
  color: var(--danger-6);
}

.status-badge.info {
  background: var(--primary-1);
  color: var(--primary-6);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* 文字按钮 */
.btn-text {
  background: transparent;
  color: var(--primary-6);
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-decoration: none;
  border: none;
}

.btn-text:hover {
  background: var(--primary-1);
  color: var(--primary-7);
}

/* 响应式 */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
