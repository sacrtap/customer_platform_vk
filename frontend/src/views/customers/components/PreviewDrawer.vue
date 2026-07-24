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
            <span>当前余额</span>
            <b>¥{{ formatNumber(customer.balance) }}</b>
          </div>
          <div class="drawer-kpi">
            <span>30天消耗</span>
            <b>¥{{ formatNumber(customer.usage_30d_amount || 0) }}</b>
          </div>
          <div class="drawer-kpi">
            <span>健康度</span>
            <b :class="getHealthClass(customer.health)">{{ getHealthLabel(customer.health) }}</b>
          </div>
          <div class="drawer-kpi">
            <span>预计耗尽</span>
            <b :class="{ danger: getDaysUntilDepleted(customer) <= 5 }"
              >{{ getDaysUntilDepleted(customer) }} 天</b
            >
          </div>
        </div>

        <!-- 最近操作时间轴 -->
        <div class="drawer-section">
          <h5>最近操作</h5>
          <div class="drawer-timeline">
            <div
              v-for="item in (customer.consumption_history || []).slice(0, 5)"
              :key="item.id"
              class="drawer-event"
            >
              <span>{{ formatDate(item.created_at) }}</span>
              <b>{{ item.description }}</b>
            </div>
            <div
              v-if="!customer.consumption_history || customer.consumption_history.length === 0"
              class="drawer-empty"
            >
              暂无操作记录
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="drawer-actions">
          <button class="btn primary" @click="emit('viewDetail', customer.id)">查看详情</button>
          <button class="btn">生成结算单</button>
          <button class="btn">提醒充值</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { Customer } from '@/types'

defineProps<{
  visible: boolean
  customer: Customer | null
}>()

const emit = defineEmits<{
  close: []
  viewDetail: [id: number]
  edit: [record: Customer]
  addTag: [record: Customer]
}>()

const getInitials = (name: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const formatNumber = (num: number | string | null) => {
  const n = typeof num === 'string' ? parseFloat(num) : num
  if (n == null || isNaN(n)) return '0'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

const formatDate = (date: string | null) => {
  if (!date) return ''
  const d = new Date(date)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffDay = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  if (diffDay === 0) {
    return `今天 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  if (diffDay === 1) {
    return `昨天 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`
}

const getHealthLabel = (health: string | null | undefined) => {
  const map: Record<string, string> = {
    healthy: '健康',
    attention: '关注',
    high_risk: '高风险',
  }
  return (health && map[health]) || '-'
}

const getHealthClass = (health: string | null | undefined) => {
  if (health === 'attention') return 'amber'
  if (health === 'high_risk') return 'danger'
  return ''
}

const getDaysUntilDepleted = (customer: Customer) => {
  const usage = customer.usage_30d_amount || 0
  if (usage <= 0) return 0
  const dailyUsage = usage / 30
  const balance = customer.balance || 0
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

/* 时间轴 */
.drawer-section {
  margin-bottom: 18px;
}
.drawer-section h5 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 700;
}
.drawer-timeline {
  display: grid;
  gap: 8px;
}
.drawer-event {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #edf2f7;
  font-size: 13px;
}
.drawer-event > span {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
  min-width: 80px;
}
.drawer-event > b {
  font-weight: 600;
  color: var(--ink);
}
.drawer-empty {
  text-align: center;
  padding: 20px;
  color: var(--muted);
  font-size: 13px;
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
