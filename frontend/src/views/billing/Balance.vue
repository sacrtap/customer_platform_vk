<template>
  <div class="balance-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>余额管理</h1>
        <p class="header-subtitle">客户余额充值与管理</p>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="$message.info('新建充值开发中')">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
            </svg>
          </template>
          新建充值
        </a-button>
      </div>
    </div>
    
    <div class="table-section">
      <a-table :columns="columns" :data="data" :loading="loading" row-key="id" :pagination="pagination">
        <template #balance>
          <div class="balance-info">
            <div>总额：¥500,000</div>
            <div class="balance-detail">
              <span class="real">实充：¥400,000</span>
              <span class="bonus">赠送：¥100,000</span>
            </div>
          </div>
        </template>
        <template #action>
          <a-space>
            <a-button type="text" size="small" @click="$message.info('充值记录开发中')">充值记录</a-button>
            <a-button type="text" size="small" @click="$message.info('调整开发中')">调整</a-button>
          </a-space>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const loading = ref(false)
const pagination = { current: 1, pageSize: 20, total: 50, showTotal: true, showPageSize: true }

const columns = [
  { title: '客户名称', dataIndex: 'customer_name', width: 200 },
  { title: '余额', slotName: 'balance', width: 250 },
  { title: '已消耗', dataIndex: 'used_total', width: 120 },
  { title: '最后充值', dataIndex: 'last_recharge_at', width: 180 },
  { title: '操作', slotName: 'action', width: 180, fixed: 'right' as const },
]

const data = ref([
  { id: 1, customer_name: 'XX 科技有限公司', total_amount: 500000, real_amount: 400000, bonus_amount: 100000, used_total: 128500, last_recharge_at: '2026-04-01' },
  { id: 2, customer_name: 'YY 集团有限公司', total_amount: 300000, real_amount: 250000, bonus_amount: 50000, used_total: 85200, last_recharge_at: '2026-03-28' },
  { id: 3, customer_name: 'ZZ 创新股份', total_amount: 800000, real_amount: 700000, bonus_amount: 100000, used_total: 256800, last_recharge_at: '2026-03-25' },
])
</script>

<style scoped>
.balance-management-page {
  --neutral-1: #f7f8fa; --neutral-2: #eef0f3; --neutral-6: #646a73; --neutral-10: #1d2330;
  --primary-6: #0369A1; --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.header-title h1 { font-size: 24px; font-weight: 700; color: var(--neutral-10); margin-bottom: 8px; }
.header-subtitle { font-size: 14px; color: var(--neutral-6); }
.header-actions { display: flex; gap: 12px; }
.table-section { background: white; border-radius: 16px; border: 1px solid var(--neutral-2); box-shadow: var(--shadow-sm); overflow: hidden; }
.balance-info { font-size: 14px; }
.balance-detail { display: flex; gap: 16px; margin-top: 4px; font-size: 12px; }
.balance-detail .real { color: var(--primary-6); }
.balance-detail .bonus { color: #22c55e; }
</style>
