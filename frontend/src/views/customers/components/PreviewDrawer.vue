<template>
  <Teleport to="body">
    <div v-if="visible" class="preview-drawer-overlay" @click="emit('close')"></div>
    <div class="preview-drawer" :class="{ open: visible }">
      <div class="drawer-header">
        <h3>客户 360 预览</h3>
        <button class="drawer-close" @click="emit('close')">✕</button>
      </div>
      <div v-if="customer" class="drawer-body">
        <!-- 客户信息 -->
        <div class="drawer-customer-info">
          <span class="logo lg">{{ getInitials(customer.name) }}</span>
          <div>
            <h4>{{ customer.name }}</h4>
            <span class="subtle">
              {{ customer.industry || '-' }}
              <template v-if="customer.scale_level"> · 规模 {{ customer.scale_level }}</template>
              <template v-if="customer.consume_level">
                · 消费 {{ customer.consume_level }}</template
              >
            </span>
          </div>
        </div>

        <!-- KPI 四宫格 -->
        <div class="drawer-kpi-grid">
          <div class="drawer-kpi">
            <span>{{ customer.is_package ? '套餐剩余额度' : '当前余额' }}</span>
            <b>{{ formatCurrency(customer.balance) }}</b>
          </div>
          <div class="drawer-kpi">
            <span>30天消耗</span>
            <b>{{ formatCurrency(customer.usage_30d_amount || 0) }}</b>
          </div>
          <div class="drawer-kpi">
            <span>健康度</span>
            <b :class="getHealthClass(customer.health)">{{ getHealthLabel(customer.health) }}</b>
          </div>
          <div class="drawer-kpi">
            <span>预计耗尽</span>
            <b
              :class="{
                danger:
                  getDaysUntilDepleted(customer) !== null && getDaysUntilDepleted(customer)! <= 5,
              }"
              >{{
                getDaysUntilDepleted(customer) !== null
                  ? `${getDaysUntilDepleted(customer)} 天`
                  : '—'
              }}</b
            >
          </div>
        </div>

        <!-- 基础信息 -->
        <div class="drawer-section">
          <h5>基础信息</h5>
          <div class="drawer-info-grid">
            <div class="drawer-info">
              <span>客户编号</span>
              <b>{{ customer.company_id }}</b>
            </div>
            <div class="drawer-info">
              <span>账号类型</span>
              <b>{{ text(customer.account_type) }}</b>
            </div>
            <div class="drawer-info">
              <span>运营经理</span>
              <b>{{ managerName(customer.manager_id) }}</b>
            </div>
            <div class="drawer-info">
              <span>销售经理</span>
              <b>{{ managerName(customer.sales_manager_id) }}</b>
            </div>
            <div class="drawer-info">
              <span>结算方式</span>
              <b>{{ settlementTypeText(customer.settlement_type) }}</b>
            </div>
            <div class="drawer-info">
              <span>结算周期</span>
              <b>{{ settlementCycleText(customer.settlement_cycle) }}</b>
            </div>
            <div class="drawer-info">
              <span>结算账户</span>
              <b>{{ text(customer.settlement_account_name) || '自身' }}</b>
            </div>
            <div class="drawer-info">
              <span>合作状态</span>
              <b>{{ cooperationStatusText(customer.cooperation_status) }}</b>
            </div>
            <div class="drawer-info">
              <span>重点客户</span>
              <b>{{ yesNo(customer.is_key_customer) }}</b>
            </div>
            <div class="drawer-info">
              <span>房产客户</span>
              <b>{{ yesNo(customer.is_real_estate) }}</b>
            </div>
            <div class="drawer-info">
              <span>是否结算</span>
              <b>{{ yesNo(customer.is_settlement_enabled) }}</b>
            </div>
            <div class="drawer-info">
              <span>是否对账</span>
              <b>{{ yesNo(customer.require_reconciliation) }}</b>
            </div>
            <div class="drawer-info">
              <span>是否停用</span>
              <b>{{ yesNo(customer.is_disabled) }}</b>
            </div>
            <div class="drawer-info">
              <span>所属 ERP</span>
              <b>{{ erpName(customer.erp_system) }}</b>
            </div>
            <div class="drawer-info">
              <span>接入时间</span>
              <b>{{ formatDateOnly(customer.onboarding_date) }}</b>
            </div>
            <div class="drawer-info">
              <span>首次回款</span>
              <b>{{ formatDateOnly(customer.first_payment_date) }}</b>
            </div>
            <div class="drawer-info">
              <span>创建时间</span>
              <b>{{ formatDateTime(customer.created_at) }}</b>
            </div>
            <div class="drawer-info wide">
              <span>邮箱</span>
              <b>{{ text(customer.email) }}</b>
            </div>
            <div v-if="customer.notes" class="drawer-info wide">
              <span>备注</span>
              <b>{{ customer.notes }}</b>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="drawer-actions">
          <button class="btn primary" @click="emit('viewDetail', customer.id)">查看详情</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { CooperationStatus, Customer, ErpSystem } from '@/types'
import { formatCurrency, formatDate as formatDateOnly, formatDateTime } from '@/utils/formatters'

interface ManagerOption {
  id: number
  real_name: string | null
}

const props = withDefaults(
  defineProps<{
    visible: boolean
    customer: Customer | null
    managers?: ManagerOption[]
    cooperationStatuses?: CooperationStatus[]
    erpSystems?: ErpSystem[]
  }>(),
  {
    managers: () => [],
    cooperationStatuses: () => [],
    erpSystems: () => [],
  }
)

const emit = defineEmits<{
  close: []
  viewDetail: [id: number]
}>()

const getInitials = (name: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const text = (value: string | number | null | undefined) => {
  if (value === null || value === undefined) return '-'
  const str = String(value).trim()
  return str || '-'
}

const yesNo = (value: boolean | null | undefined) => {
  if (value === true) return '是'
  if (value === false) return '否'
  return '-'
}

const managerName = (id: number | null | undefined) => {
  if (!id) return '-'
  const manager = props.managers.find((m) => m.id === id)
  return manager?.real_name || `#${id}`
}

const settlementTypeText = (type: string | null | undefined) => {
  const map: Record<string, string> = { prepaid: '预付费', postpaid: '后付费' }
  return (type && map[type]) || text(type)
}

const settlementCycleText = (cycle: string | null | undefined) => {
  const map: Record<string, string> = {
    daily: '日结',
    weekly: '周结',
    monthly: '月结',
    quarterly: '季结',
    yearly: '年结',
  }
  return (cycle && map[cycle]) || text(cycle)
}

const cooperationStatusText = (status: string | null | undefined) => {
  if (!status) return '-'
  const found = props.cooperationStatuses.find((s) => s.value === status)
  if (found) return found.name
  const map: Record<string, string> = {
    active: '合作中',
    suspended: '暂停',
    terminated: '终止',
    noused: '近一年未使用',
  }
  return map[status] || status
}

const erpName = (erp: string | null | undefined) => {
  if (!erp) return '-'
  const found = props.erpSystems.find((e) => e.value === erp)
  return found?.name || erp
}

const getHealthLabel = (health: string | null | undefined) => {
  const map: Record<string, string> = {
    healthy: '健康',
    attention: '关注',
    high_risk: '高风险',
    inactive: '不活跃',
  }
  return (health && map[health]) || '-'
}

const getHealthClass = (health: string | null | undefined) => {
  if (health === 'attention') return 'amber'
  if (health === 'high_risk') return 'danger'
  if (health === 'inactive') return 'gray'
  return ''
}

const getDaysUntilDepleted = (customer: Customer) => {
  const usage = customer.usage_30d_amount || 0
  if (usage <= 0) return null // 无消耗数据时返回 null，模板中显示 "—"
  const dailyUsage = usage / 30
  const balance = customer.balance || 0
  if (dailyUsage <= 0) return null
  return Math.max(0, Math.round(balance / dailyUsage))
}
</script>

<style scoped>
/* 遮罩层 */
.preview-drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.25);
  z-index: 89;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 抽屉 */
.preview-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 400px;
  height: 100vh;
  background: #fff;
  box-shadow: -8px 0 32px rgba(15, 23, 42, 0.12);
  z-index: 90;
  transform: translateX(100%);
  transition: transform 0.25s ease;
  display: flex;
  flex-direction: column;
}
.preview-drawer.open {
  transform: translateX(0);
}

/* 头部 */
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 22px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}
.drawer-header h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
}
.drawer-close {
  border: 0;
  background: transparent;
  font-size: 18px;
  color: var(--muted);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.2s;
}
.drawer-close:hover {
  background: #f1f5f9;
}

/* 内容区 */
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
}

/* 客户信息 */
.drawer-customer-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.drawer-customer-info .logo {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  font-size: 18px;
  background: #e0f2fe;
  color: #0369a1;
  display: grid;
  place-items: center;
  font-weight: 850;
  flex-shrink: 0;
}
.drawer-customer-info h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
}
.subtle {
  color: var(--muted);
  font-size: 12px;
}

/* KPI 网格 */
.drawer-kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 18px;
}
.drawer-kpi {
  background: #f8fafc;
  border: 1px solid #edf2f7;
  border-radius: 12px;
  padding: 12px;
}
.drawer-kpi span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.drawer-kpi b {
  font-size: 18px;
  font-weight: 800;
}
.drawer-kpi b.amber {
  color: var(--amber);
}
.drawer-kpi b.danger {
  color: var(--red);
}

/* 基础信息 */
.drawer-section {
  margin-bottom: 18px;
}
.drawer-section h5 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 700;
}
.drawer-info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 14px;
  padding: 14px;
  background: #f8fafc;
  border: 1px solid #edf2f7;
  border-radius: 12px;
}
.drawer-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.drawer-info.wide {
  grid-column: 1 / -1;
}
.drawer-info > span {
  font-size: 12px;
  color: var(--muted);
}
.drawer-info > b {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  overflow-wrap: anywhere;
}

/* 操作按钮 */
.drawer-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 12px;
  cursor: pointer;
  font-weight: 700;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}
.btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}
.btn.primary:hover {
  background: #1e40af;
}

@media (max-width: 1100px) {
  .preview-drawer {
    width: 100%;
  }
}
</style>
