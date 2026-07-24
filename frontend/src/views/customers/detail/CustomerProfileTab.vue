<template>
  <div class="profile-tab-content">
    <!-- 核心指标区 -->
    <div class="metrics-grid">
      <div v-if="profileLoading" class="metric-card loading">
        <SkeletonCard height="72px" />
      </div>
      <div v-else class="metric-card primary">
        <span class="metric-label">规模等级</span>
        <span class="metric-value">{{ profile.scale_level || '-' }}</span>
      </div>

      <div v-if="profileLoading" class="metric-card loading">
        <SkeletonCard height="72px" />
      </div>
      <div v-else class="metric-card success">
        <span class="metric-label">消费等级</span>
        <span class="metric-value">{{ consumeLevelDisplay }}</span>
      </div>

      <div v-if="profileLoading" class="metric-card loading">
        <SkeletonCard height="72px" />
      </div>
      <div v-else class="metric-card warning">
        <span class="metric-label">预估年消费</span>
        <span class="metric-value">{{
          profile.estimated_annual_spend
            ? formatCurrency(Number(profile.estimated_annual_spend))
            : '-'
        }}</span>
      </div>
    </div>

    <!-- 扩展指标区 -->
    <div class="metrics-grid metrics-grid-extended">
      <div v-if="profileLoading" class="metric-card loading">
        <SkeletonCard height="72px" />
      </div>
      <div v-else class="metric-card">
        <span class="metric-label">月均拍摄量（实际）</span>
        <span class="metric-value">{{ profile.monthly_avg_shots ?? '-' }}</span>
      </div>

      <div v-if="profileLoading" class="metric-card loading">
        <SkeletonCard height="72px" />
      </div>
      <div v-else class="metric-card">
        <span class="metric-label">月均拍摄量（测算）</span>
        <span class="metric-value">{{ profile.monthly_avg_shots_estimated ?? '-' }}</span>
      </div>

      <div v-if="profileLoading" class="metric-card loading">
        <SkeletonCard height="72px" />
      </div>
      <div v-else class="metric-card">
        <span class="metric-label">25年实际消费</span>
        <span class="metric-value">{{
          profile.actual_annual_spend_2025
            ? formatCurrency(Number(profile.actual_annual_spend_2025))
            : '-'
        }}</span>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-grid">
      <div class="chart-panel">
        <h4 class="chart-title">健康度评分</h4>
        <p class="chart-description">综合评估客户健康状况</p>
        <div v-if="healthScoreLoading" class="chart-loading">
          <a-spin size="large" />
        </div>
        <div v-else class="chart-content">
          <HealthGauge v-if="healthScore" :score="healthScore.score" :level="healthScore.level" />
        </div>
      </div>

      <div class="chart-panel">
        <h4 class="chart-title">消费等级进度</h4>
        <p class="chart-description">当前消费等级升级进度</p>
        <div class="chart-content">
          <ConsumeLevelProgress
            v-if="profile.consume_level"
            :current-level="profile.consume_level"
            :current-amount="profile.actual_annual_spend_2025 || 0"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CustomerProfile } from '@/types'
import type { CustomerHealthScore } from '@/api/analytics'
import { formatCurrency } from '@/utils/formatters'
import SkeletonCard from '@/components/SkeletonCard.vue'
import HealthGauge from '@/components/charts/HealthGauge.vue'
import ConsumeLevelProgress from '@/components/charts/ConsumeLevelProgress.vue'

const props = defineProps<{
  profile: CustomerProfile
  profileLoading: boolean
  healthScore?: CustomerHealthScore | null
  healthScoreLoading?: boolean
}>()

const CONSUME_LEVEL_MAP: Record<string, string> = {
  C1: 'C1 - 100 万',
  C2: 'C2 - 50 万',
  C3: 'C3 - 25 万',
  C4: 'C4 - 12 万',
  C5: 'C5 - 6 万',
  C6: 'C6 - 6 万以下',
}

const consumeLevelDisplay = computed(() => {
  const level = props.profile.consume_level
  if (!level) return '-'
  return CONSUME_LEVEL_MAP[level] || level
})
</script>

<style scoped>
/* ========== 画像信息页面优化样式 ========== */

/* 画像信息整体包装器 */
.profile-tab-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 核心指标网格 - 3 列布局 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

/* 核心指标卡片 */
.metric-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-radius: 12px;
  min-height: 72px;
  background: #ffffff;
  border: 1px solid var(--soft);
  transition: all 200ms ease;
  position: relative;
  overflow: hidden;
}

/* 加载状态 */
.metric-card.loading {
  background: var(--bg);
  border-color: transparent;
  pointer-events: none;
}

.metric-card.loading :deep(.skeleton-card) {
  opacity: 0.6;
}

/* 主色指标卡片 - 规模等级 */
.metric-card.primary {
  background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
  border-color: transparent;
  color: #ffffff;
}

.metric-card.primary .metric-label {
  color: rgba(255, 255, 255, 0.85);
}

.metric-card.primary .metric-value {
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
}

.metric-card.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(29, 78, 216, 0.25);
}

/* 成功色指标卡片 - 消费等级 */
.metric-card.success {
  background: linear-gradient(135deg, #059669 0%, #10b981 100%);
  border-color: transparent;
  color: #ffffff;
}

.metric-card.success .metric-label {
  color: rgba(255, 255, 255, 0.85);
}

.metric-card.success .metric-value {
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
}

.metric-card.success:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(5, 150, 105, 0.25);
}

/* 警告色指标卡片 - 预估年消费 */
.metric-card.warning {
  background: linear-gradient(135deg, var(--amber) 0%, #fbbf24 100%);
  border-color: transparent;
  color: #ffffff;
}

.metric-card.warning .metric-label {
  color: rgba(255, 255, 255, 0.85);
}

.metric-card.warning .metric-value {
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
}

.metric-card.warning:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(217, 119, 6, 0.25);
}

/* 普通指标卡片 */
.metric-card .metric-label {
  font-size: 12px;
  font-weight: 500;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.metric-card .metric-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.2;
}

/* 指标卡片 Hover 效果 - 简化版 */
.metric-card:not(.primary):not(.success):not(.warning):not(.loading):hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: #bfdbfe;
  background: #fafbfc;
}

/* 图表网格 - 2列布局 */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

/* 图表面板 - 透明容器，由外层.tabs-section统一提供卡片效果 */
.chart-panel {
  padding: 20px 28px;
}

/* 图表标题 */
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 4px 0;
  line-height: 1.4;
}

.chart-description {
  font-size: 12px;
  color: #94a3b8;
  margin: 0 0 16px 0;
  line-height: 1.5;
}

/* 图表内容区 */
.chart-content {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-content :deep(.health-gauge),
.chart-content :deep(.consume-level-progress) {
  width: 100%;
  max-width: 100%;
}

/* 加载状态 */
.chart-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  width: 100%;
}

/* 响应式布局 */
@media (max-width: 1199px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .metrics-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .metric-card {
    padding: 14px 16px;
    min-height: 64px;
  }

  .metric-card .metric-value {
    font-size: 16px;
  }

  .metric-card.primary .metric-value,
  .metric-card.success .metric-value {
    font-size: 18px;
  }

  .charts-grid {
    gap: 16px;
  }

  .chart-panel {
    padding: 16px;
  }

  .chart-content {
    min-height: 200px;
  }
}

@media (max-width: 480px) {
  .metric-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .metric-card .metric-value {
    font-size: 18px;
  }
}

/* 减少运动偏好支持 */
@media (prefers-reduced-motion: reduce) {
  .metric-card,
  .chart-panel {
    transition: none;
  }

  .metric-card:hover {
    transform: none;
  }
}
</style>
