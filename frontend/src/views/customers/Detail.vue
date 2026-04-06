<template>
  <div class="customer-detail-page">
    <div class="page-header">
      <div class="header-title">
        <a-button type="text" @click="$router.back()">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 16 16">
            <path fill-rule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z"/>
          </svg>
        </a-button>
        <h1>客户详情</h1>
      </div>
      <div class="header-actions">
        <a-button @click="$message.info('编辑开发中')">编辑</a-button>
        <a-button type="primary" @click="$message.info('重点客户切换开发中')">
          {{ customer.is_key_customer ? '取消重点' : '设为重点' }}
        </a-button>
      </div>
    </div>
    
    <div class="tabs-section">
      <a-tabs v-model="activeTab">
        <a-tab-pane key="basic" title="基础信息">
          <div class="info-grid">
            <div class="info-item">
              <label>客户名称</label>
              <span>{{ customer.name }}</span>
            </div>
            <div class="info-item">
              <label>公司 ID</label>
              <span>{{ customer.company_id }}</span>
            </div>
            <div class="info-item">
              <label>账号类型</label>
              <a-tag>{{ customer.account_type || '-' }}</a-tag>
            </div>
            <div class="info-item">
              <label>业务类型</label>
              <a-tag>{{ customer.business_type || '-' }}</a-tag>
            </div>
            <div class="info-item">
              <label>客户等级</label>
              <a-tag>{{ customer.customer_level || '-' }}</a-tag>
            </div>
            <div class="info-item">
              <label>重点客户</label>
              <a-tag :color="customer.is_key_customer ? 'red' : 'gray'">
                {{ customer.is_key_customer ? '是' : '否' }}
              </a-tag>
            </div>
            <div class="info-item">
              <label>结算方式</label>
              <a-tag :color="customer.settlement_type === 'prepaid' ? 'green' : 'blue'">
                {{ customer.settlement_type === 'prepaid' ? '预付费' : '后付费' }}
              </a-tag>
            </div>
            <div class="info-item">
              <label>结算周期</label>
              <span>{{ customer.settlement_cycle || '-' }}</span>
            </div>
            <div class="info-item">
              <label>邮箱</label>
              <span>{{ customer.email || '-' }}</span>
            </div>
            <div class="info-item">
              <label>创建时间</label>
              <span>{{ customer.created_at }}</span>
            </div>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="profile" title="画像信息">
          <div class="info-grid">
            <div class="info-item">
              <label>规模等级</label>
              <a-tag color="blue">{{ profile.scale_level || '-' }}</a-tag>
            </div>
            <div class="info-item">
              <label>消费等级</label>
              <a-tag color="green">{{ profile.consume_level || '-' }}</a-tag>
            </div>
            <div class="info-item">
              <label>所属行业</label>
              <span>{{ profile.industry || '-' }}</span>
            </div>
            <div class="info-item">
              <label>房地产行业</label>
              <a-tag :color="profile.is_real_estate ? 'orange' : 'gray'">
                {{ profile.is_real_estate ? '是' : '否' }}
              </a-tag>
            </div>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="balance" title="余额信息">
          <div class="balance-cards">
            <div class="balance-card">
              <div class="balance-label">总余额</div>
              <div class="balance-value">¥500,000</div>
            </div>
            <div class="balance-card">
              <div class="balance-label">实充余额</div>
              <div class="balance-value real">¥400,000</div>
            </div>
            <div class="balance-card">
              <div class="balance-label">赠送余额</div>
              <div class="balance-value bonus">¥100,000</div>
            </div>
            <div class="balance-card">
              <div class="balance-label">已消耗</div>
              <div class="balance-value">¥128,500</div>
            </div>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="invoices" title="结算单">
          <a-table :columns="invoiceColumns" :data="invoices" :pagination="false" row-key="id">
            <template #status="{ record }">
              <span :class="['status-badge', record.status]">
                <span class="status-dot"></span>
                {{ record.statusText }}
              </span>
            </template>
            <template #action>
              <a-button type="text" size="small" @click="$message.info('查看开发中')">查看</a-button>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const activeTab = ref('basic')

const customer = ref({
  name: 'XX 科技有限公司',
  company_id: 'COMP001',
  account_type: '正式账号',
  business_type: 'A',
  customer_level: 'KA',
  is_key_customer: true,
  settlement_type: 'prepaid',
  settlement_cycle: '月结',
  email: 'contact@xxtech.com',
  created_at: '2026-01-15',
})

const profile = ref({
  scale_level: '大型企业',
  consume_level: '高消费',
  industry: '互联网',
  is_real_estate: false,
})

const invoiceColumns = [
  { title: '结算单号', dataIndex: 'no', width: 150 },
  { title: '周期', dataIndex: 'period', width: 100 },
  { title: '金额', dataIndex: 'amount', width: 120 },
  { title: '状态', slotName: 'status', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', width: 150 },
  { title: '操作', slotName: 'action', width: 80 },
]

const invoices = ref([
  { id: 1, no: 'INV-2026-0089', period: '2026-03', amount: 128500, status: 'warning', statusText: '待确认', created_at: '2026-04-01' },
  { id: 2, no: 'INV-2026-0078', period: '2026-02', amount: 115200, status: 'success', statusText: '已完成', created_at: '2026-03-01' },
  { id: 3, no: 'INV-2026-0065', period: '2026-01', amount: 98600, status: 'success', statusText: '已完成', created_at: '2026-02-01' },
])
</script>

<style scoped>
.customer-detail-page {
  --neutral-1: #f7f8fa; --neutral-2: #eef0f3; --neutral-6: #646a73; --neutral-10: #1d2330;
  --primary-1: #e8f3ff; --primary-6: #0369A1; --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.header-title { display: flex; align-items: center; gap: 12px; }
.header-title h1 { font-size: 24px; font-weight: 700; color: var(--neutral-10); margin: 0; }
.header-actions { display: flex; gap: 12px; }
.tabs-section { background: white; border-radius: 16px; border: 1px solid var(--neutral-2); box-shadow: var(--shadow-sm); padding: 24px; }
.info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; padding: 16px 0; }
.info-item { display: flex; flex-direction: column; gap: 8px; }
.info-item label { font-size: 13px; color: var(--neutral-6); font-weight: 500; }
.info-item span { font-size: 14px; color: var(--neutral-10); }
.balance-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; padding: 24px 0; }
.balance-card { background: var(--neutral-1); padding: 24px; border-radius: 12px; text-align: center; }
.balance-label { font-size: 13px; color: var(--neutral-6); margin-bottom: 8px; }
.balance-value { font-size: 28px; font-weight: 700; color: var(--neutral-10); }
.balance-value.real { color: var(--primary-6); }
.balance-value.bonus { color: #22c55e; }
.status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }
.status-badge.success { background: #e8ffea; color: #22c55e; }
.status-badge.warning { background: #fff7e8; color: #f59e0b; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
</style>
