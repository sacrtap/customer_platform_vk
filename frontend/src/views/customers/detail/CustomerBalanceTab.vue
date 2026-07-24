<template>
  <div>
    <div v-if="balanceLoading" class="balance-cards">
      <SkeletonCard v-for="i in 4" :key="i" height="110px" />
    </div>
    <div v-else class="balance-cards">
      <div class="balance-card">
        <div class="balance-label">总余额</div>
        <div class="balance-value">{{ formatCurrency(balance.total_amount) }}</div>
      </div>
      <div class="balance-card">
        <div class="balance-label">实充余额</div>
        <div class="balance-value real">{{ formatCurrency(balance.real_amount) }}</div>
      </div>
      <div class="balance-card">
        <div class="balance-label">赠送余额</div>
        <div class="balance-value bonus">{{ formatCurrency(balance.bonus_amount) }}</div>
      </div>
      <div class="balance-card">
        <div class="balance-label">已消耗</div>
        <div class="balance-value">{{ formatCurrency(balance.used_total) }}</div>
      </div>
    </div>

    <!-- 余额趋势图 - 性能优化: 延迟加载 -->
    <div class="balance-trend-section">
      <BalanceTrendChart
        v-if="shouldRenderBalanceTrend"
        :trend="balanceTrend"
        :loading="balanceTrendLoading"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Balance } from '@/types'
import type { BalanceTrendItem } from '@/api/billing'
import { formatCurrency } from '@/utils/formatters'
import SkeletonCard from '@/components/SkeletonCard.vue'
import BalanceTrendChart from '@/components/charts/BalanceTrendChart.vue'

defineProps<{
  balance: Balance
  balanceLoading: boolean
  balanceTrend: BalanceTrendItem[]
  balanceTrendLoading: boolean
  shouldRenderBalanceTrend: boolean
}>()
</script>

<style scoped>
/* 余额卡片 - 自适应 Grid 布局 */
.balance-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-lg, 24px);
  padding: var(--space-lg, 24px) var(--space-md, 16px);
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

/* 4 张卡片最佳布局 */
@media (min-width: 1400px) {
  .balance-cards {
    grid-template-columns: repeat(4, 1fr);
  }
}

/* 响应式适配 */
@media (max-width: 1199px) and (min-width: 768px) {
  .balance-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .balance-cards {
    grid-template-columns: 1fr;
  }
}

.balance-card {
  background: linear-gradient(135deg, #ffffff 0%, var(--bg) 100%);
  padding: var(--spacing-xl, 20px) var(--spacing-lg, 16px);
  border-radius: var(--radius-lg);
  text-align: center;
  border: 1px solid var(--line);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base);
  min-height: 110px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.balance-card::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(29, 78, 216, 0.1) 0%, transparent 70%);
  opacity: 0;
  transition: opacity var(--transition-base);
  pointer-events: none;
}

.balance-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--primary), var(--cyan), var(--primary));
  transform: scaleX(0);
  transition: transform var(--transition-base);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

.balance-card:hover {
  transform: translateY(-6px) scale(1.02);
  box-shadow:
    0 20px 40px rgba(29, 78, 216, 0.2),
    0 8px 16px rgba(0, 0, 0, 0.1);
  border-color: var(--primary);
  background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%);
}

.balance-card:hover::before {
  opacity: 1;
}

.balance-card:hover::after {
  transform: scaleX(1);
}

.balance-label {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.balance-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.2;
}

.balance-value.real {
  color: var(--primary);
}

.balance-value.bonus {
  color: var(--green);
}

/* 余额趋势区域 */
.balance-trend-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--line);
  width: 100%;
  box-sizing: border-box;
  min-height: 400px;
}

/* 空数据最小高度，防止布局塌陷 */
.balance-cards {
  min-height: 200px;
}

/* XS Mobile - 374px and below */
@media (max-width: 374px) {
  .balance-cards {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 16px 12px;
  }

  .balance-card {
    padding: 16px 12px;
    min-height: 100px;
  }

  .balance-value {
    font-size: 26px;
  }
}
</style>
