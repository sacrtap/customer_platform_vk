<template>
  <div class="info-grid">
    <!-- 第 1 行 -->
    <div class="info-item">
      <span class="label">客户名称</span>
      <span class="value">{{ customer.name }}</span>
    </div>
    <div class="info-item">
      <span class="label">公司 ID</span>
      <span class="value">{{ customer.company_id }}</span>
    </div>
    <!-- 第 2 行 -->
    <div class="info-item">
      <span class="label">账号类型</span>
      <span class="value">
        <a-tag>{{ customer.account_type || '-' }}</a-tag>
      </span>
    </div>
    <div class="info-item">
      <span class="label">行业类型</span>
      <span class="value">
        <a-tag>{{ customer.industry || '-' }}</a-tag>
      </span>
    </div>
    <!-- 第 3 行 -->
    <div class="info-item">
      <span class="label">重点客户</span>
      <span class="value">
        <a-tag :color="customer.is_key_customer ? 'red' : 'gray'">
          {{ customer.is_key_customer ? '是' : '否' }}
        </a-tag>
      </span>
    </div>
    <div class="info-item">
      <span class="label">是否房产客户</span>
      <span class="value">
        <a-tag v-if="customer.is_real_estate === true" color="green">是</a-tag>
        <a-tag v-else-if="customer.is_real_estate === false" color="gray">否</a-tag>
        <span v-else>-</span>
      </span>
    </div>
    <!-- 第 4 行 -->
    <div class="info-item">
      <span class="label">结算方式</span>
      <span class="value">
        <a-tag :color="customer.settlement_type === 'prepaid' ? 'green' : 'blue'">
          {{ customer.settlement_type === 'prepaid' ? '预付费' : '后付费' }}
        </a-tag>
      </span>
    </div>
    <div class="info-item">
      <span class="label">结算周期</span>
      <span class="value">{{ settlementCycleText }}</span>
    </div>
    <!-- 第 5 行 -->
    <div class="info-item">
      <span class="label">邮箱</span>
      <span class="value">{{ customer.email || '-' }}</span>
    </div>
    <div class="info-item">
      <span class="label">所属 ERP</span>
      <span class="value">
        <a-tag v-if="customer.erp_system">{{ customer.erp_system }}</a-tag>
        <span v-else>-</span>
      </span>
    </div>
    <!-- 第 6 行 -->
    <div class="info-item">
      <span class="label">合作状态</span>
      <span class="value">
        <a-tag :color="cooperationStatusColor">
          {{ cooperationStatusText }}
        </a-tag>
      </span>
    </div>
    <div class="info-item">
      <span class="label">商务经理</span>
      <span class="value">
        {{ salesManagerName || '-' }}
      </span>
    </div>
    <!-- 第 7 行 -->
    <div class="info-item">
      <span class="label">是否结算</span>
      <span class="value">
        <a-tag :color="customer.is_settlement_enabled ? 'green' : 'gray'">
          {{ customer.is_settlement_enabled ? '是' : '否' }}
        </a-tag>
      </span>
    </div>
    <div class="info-item">
      <span class="label">是否停用</span>
      <span class="value">
        <a-tag :color="customer.is_disabled ? 'red' : 'gray'">
          {{ customer.is_disabled ? '是' : '否' }}
        </a-tag>
      </span>
    </div>
    <!-- 第 8 行 -->
    <div class="info-item">
      <span class="label">首次回款时间</span>
      <span class="value">{{ customer.first_payment_date || '-' }}</span>
    </div>
    <div class="info-item">
      <span class="label">接入时间</span>
      <span class="value">{{ customer.onboarding_date || '-' }}</span>
    </div>
    <!-- 第 9 行 -->
    <div class="info-item">
      <span class="label">备注</span>
      <span class="value">
        <span v-if="customer.notes" class="notes-text">{{ customer.notes }}</span>
        <span v-else>-</span>
      </span>
    </div>
    <div class="info-item">
      <span class="label">创建时间</span>
      <span class="value">{{ formatDateTime(customer.created_at) }}</span>
    </div>
    <!-- 第 10 行 - 占满整行 -->
    <div class="info-item full-width">
      <span class="label">客户标签</span>
      <span class="value">
        <div class="tags-container">
          <a-tag
            v-for="tag in customerTags"
            :key="tag.id"
            color="arcoblue"
            closable
            @close="emit('removeTag', tag.id)"
          >
            {{ tag.name }}
          </a-tag>
          <a-button type="text" size="small" @click="emit('openTagSelector')">
            <template #icon>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                fill="currentColor"
                viewBox="0 0 16 16"
              >
                <path
                  d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
                />
              </svg>
            </template>
            添加标签
          </a-button>
        </div>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Customer, Tag, User } from '@/types'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  customer: Customer
  managers: User[]
  customerTags: Tag[]
}>()

const emit = defineEmits<{
  openTagSelector: []
  removeTag: [tagId: number]
}>()

// 合作状态展示
const cooperationStatusColor = computed(() => {
  const status = props.customer.cooperation_status
  if (status === 'active') return 'green'
  if (status === 'suspended') return 'orange'
  if (status === 'terminated') return 'red'
  if (status === 'noused') return 'gray'
  return 'gray'
})

const cooperationStatusText = computed(() => {
  const status = props.customer.cooperation_status
  const map: Record<string, string> = {
    active: '合作中',
    suspended: '暂停',
    terminated: '终止',
    noused: '近一年未使用',
  }
  return map[status || ''] || '-'
})

// 结算周期展示映射
const settlementCycleText = computed(() => {
  const cycle = props.customer.settlement_cycle
  const map: Record<string, string> = {
    daily: '日结',
    weekly: '周结',
    monthly: '月结',
    quarterly: '季结',
    yearly: '年结',
  }
  return map[cycle || ''] || cycle || '-'
})

// 商务经理名称（从 managers 列表中查找）
const salesManagerName = computed(() => {
  if (!props.customer.sales_manager_id) return null
  const manager = props.managers.find((m) => m.id === props.customer.sales_manager_id)
  return manager ? manager.real_name || manager.username : null
})
</script>

<style scoped>
/* 双列信息网格 - 基础信息面板 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0;
  padding: 8px 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.info-item {
  display: flex;
  flex-direction: column;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
  transition: background-color var(--transition-fast);
}

.info-item:hover {
  background-color: var(--bg);
}

.info-item .label {
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}

.info-item .value {
  font-size: 14px;
  color: var(--ink);
  font-weight: 500;
  line-height: 1.5;
}

/* 客户标签占满整行 */
.info-item.full-width {
  grid-column: 1 / -1;
}

/* 客户标签区域 */
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tags-container :deep(.arco-btn-text) {
  height: 28px;
  padding: 0 12px;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  border: 1px dashed var(--muted);
  background: transparent;
  color: var(--muted);
  font-size: 13px;
}

.tags-container :deep(.arco-btn-text:hover) {
  border-color: #1d4ed8;
  background: #dbeafe;
  color: #1d4ed8;
}

/* 备注文字样式 - 支持换行 */
.notes-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

/* 响应式适配 - 平板及中等屏幕 */
@media (min-width: 375px) and (max-width: 768px) {
  .info-grid {
    grid-template-columns: 1fr;
  }

  .info-item .label {
    font-size: 12px;
  }

  .info-item .value {
    font-size: 14px;
  }
}
</style>
