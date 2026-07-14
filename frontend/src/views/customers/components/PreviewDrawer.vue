<template>
  <a-drawer
    :visible="visible"
    width="420"
    placement="right"
    :closable="true"
    :footer="null"
    popup-container="#app-root"
    @cancel="emit('close')"
  >
    <div v-if="customer" class="preview-container">
      <!-- 客户头部信息 -->
      <div class="preview-header">
        <div class="customer-logo lg">{{ getInitials(customer.name) }}</div>
        <div class="preview-header-info">
          <div class="preview-name-line">
            <span class="preview-name">{{ customer.name }}</span>
            <Tag v-if="customer.is_key_customer" variant="blue" size="sm">重点客户</Tag>
          </div>
          <div class="preview-meta">
            <span v-if="customer.industry">{{ customer.industry }}</span>
            <span>规模: {{ customer.scale_level || '-' }}</span>
            <span>余额: ¥{{ formatNumber(customer.balance) }}</span>
          </div>
        </div>
      </div>

      <!-- KPI 四宫格 -->
      <div class="preview-kpi-grid">
        <div class="preview-kpi-item">
          <span class="preview-kpi-label">30天消耗</span>
          <span class="preview-kpi-value">
            ¥{{ formatNumber(customer.usage_30d_amount || 0) }}
          </span>
          <ProgressBar
            :value="Math.min(100, customer.usage_30d || 0)"
            :color="getUsageColor(customer.usage_30d || 0)"
          />
        </div>
        <div class="preview-kpi-item">
          <span class="preview-kpi-label">健康度</span>
          <span class="preview-kpi-value">
            <Tag :variant="getHealthVariant(customer.health)" size="md">
              {{ getHealthLabel(customer.health) }}
            </Tag>
          </span>
        </div>
        <div class="preview-kpi-item">
          <span class="preview-kpi-label">余额</span>
          <span class="preview-kpi-value">¥{{ formatNumber(customer.balance) }}</span>
        </div>
        <div class="preview-kpi-item">
          <span class="preview-kpi-label">消费等级</span>
          <span class="preview-kpi-value">{{ customer.consume_level || '-' }}</span>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div class="preview-quick-actions">
        <button class="quick-action" @click="emit('viewDetail', customer.id)">
          <span class="qa-icon">�</span>
          <span>查看详情</span>
        </button>
        <button class="quick-action" @click="emit('edit', customer)">
          <span class="qa-icon">✎</span>
          <span>编辑信息</span>
        </button>
        <button class="quick-action" @click="emit('addTag', customer)">
          <span class="qa-icon">🏷</span>
          <span>打标签</span>
        </button>
      </div>

      <!-- 最近消费历程 -->
      <div class="preview-timeline-section">
        <h4 class="section-title">最近消费历程</h4>
        <div class="timeline">
          <div v-for="item in customer.consumption_history" :key="item.id" class="timeline-item">
            <div class="timeline-dot" />
            <div class="timeline-content">
              <span class="timeline-description">{{ item.description }}</span>
              <span class="timeline-time">{{ formatDate(item.created_at) }}</span>
            </div>
            <span class="timeline-amount" :class="{ negative: item.amount < 0 }">
              ¥{{ formatNumber(Math.abs(item.amount)) }}
            </span>
          </div>
          <div
            v-if="!customer.consumption_history || customer.consumption_history.length === 0"
            class="empty-timeline"
          >
            暂无消费记录
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import type { Customer } from '@/types'
import Tag from '@/components/ui/Tag.vue'
import ProgressBar from '@/components/ui/ProgressBar.vue'

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
  if (n == null || isNaN(n)) return '0.00'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatDate = (date: string | null) => {
  if (!date) return ''
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const getUsageColor = (value: number) => {
  if (value >= 80) return '#059669'
  if (value >= 50) return '#3B82F6'
  return '#94A3B8'
}

const getHealthVariant = (health: string): 'green' | 'amber' | 'red' | 'gray' => {
  const map: Record<string, 'green' | 'amber' | 'red' | 'gray'> = {
    healthy: 'green',
    attention: 'amber',
    high_risk: 'red',
  }
  return map[health] || 'gray'
}

const getHealthLabel = (health: string) => {
  const map: Record<string, string> = {
    healthy: '健康',
    attention: '关注',
    high_risk: '高风险',
  }
  return map[health] || health
}
</script>

<style scoped>
.preview-container {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  margin-top: 20px;
}

/* 头部 */
.preview-header {
  display: flex;
  gap: 16px;
  align-items: center;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
}

.customer-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}
.customer-logo.lg {
  width: 48px;
  height: 48px;
  font-size: 20px;
}

.preview-header-info {
  min-width: 0;
}

.preview-name-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
}

.preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: var(--muted);
  margin-top: 4px;
}

/* KPI 四宫格 */
.preview-kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin: 20px 0;
}

.preview-kpi-item {
  background: #f8fafc;
  border: 1px solid #edf2f7;
  border-radius: 12px;
  padding: 12px;
}

.preview-kpi-label {
  font-size: 12px;
  color: var(--muted);
  display: block;
  margin-bottom: 4px;
}

.preview-kpi-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
}

/* 快捷操作 */
.preview-quick-actions {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}

.quick-action {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  flex: 1;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: white;
  cursor: pointer;
  font-size: 12px;
  color: var(--ink);
  transition: all 0.2s;
}
.quick-action:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: #f8fbff;
}

.qa-icon {
  font-size: 18px;
}

/* 时间轴 */
.preview-timeline-section {
  margin-top: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  margin: 0 0 12px 0;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.timeline-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}

.timeline-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
  flex-shrink: 0;
}

.timeline-content {
  flex: 1;
  min-width: 0;
}

.timeline-description {
  display: block;
  font-size: 13px;
  color: var(--ink);
}

.timeline-time {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.timeline-amount {
  font-size: 13px;
  font-weight: 600;
  color: #059669;
}
.timeline-amount.negative {
  color: var(--red);
}

.empty-timeline {
  text-align: center;
  padding: 24px;
  color: var(--muted);
  font-size: 13px;
}
</style>
