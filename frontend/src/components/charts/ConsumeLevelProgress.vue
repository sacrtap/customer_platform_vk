<!-- frontend/src/components/charts/ConsumeLevelProgress.vue -->
<template>
  <div class="consume-level-progress">
    <div class="level-header">
      <span class="level-label">消费等级</span>
      <span class="level-value">{{ currentLevel }}</span>
    </div>
    <div class="progress-container">
      <div class="progress-track">
        <div
          v-for="(level, index) in levels"
          :key="level"
          :class="['level-segment', getSegmentClass(index)]"
        >
          <span class="segment-label">{{ level }}</span>
        </div>
      </div>
      <div class="progress-indicator" :style="{ left: indicatorPosition + '%' }">
        <div class="indicator-arrow"></div>
      </div>
    </div>
    <div class="progress-info">
      <span class="info-text">距离下一等级还需消费 ¥{{ formatNumber(amountToNextLevel) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    currentLevel: string
    currentAmount: number
  }>(),
  {}
)

// 统一的消费等级配置（从低到高）
const levels = ['E', 'D', 'C', 'B', 'A', 'S']

// 消费等级阈值（与详情页显示映射保持一致）
const levelThresholds = {
  E: 0,
  D: 60000,
  C: 120000,
  B: 250000,
  A: 500000,
  S: 1000000,
}

// 根据消费金额自动判断所在等级区间，不依赖 currentLevel
const getCurrentLevelInfo = (amount: number) => {
  let index = 0
  for (let i = levels.length - 1; i >= 0; i--) {
    if (amount >= levelThresholds[levels[i] as keyof typeof levelThresholds]) {
      index = i
      break
    }
  }
  return { index, level: levels[index] }
}

const indicatorPosition = computed(() => {
  const levelInfo = getCurrentLevelInfo(props.currentAmount)
  const levelIndex = levelInfo.index
  
  if (levelIndex < 0) return 0
  if (levelIndex >= levels.length - 1) {
    return 100
  }
  
  // 6 个等级，5 个间隔，每个间隔占 20%（100/5=20）
  const segmentWidth = 100 / (levels.length - 1)
  
  // 当前等级的阈值
  const currentThreshold = levelThresholds[levels[levelIndex] as keyof typeof levelThresholds]
  // 下一等级的阈值
  const nextLevel = levels[levelIndex + 1]
  const nextThreshold = levelThresholds[nextLevel as keyof typeof levelThresholds]
  
  // 在当前等级段内的进度百分比
  const range = nextThreshold - currentThreshold
  const progress = props.currentAmount - currentThreshold
  const segmentProgress = Math.min(Math.max(progress / range, 0), 1)
  
  // 游标位置 = 已完成的段数 + 当前段内的进度
  return (levelIndex + segmentProgress) * segmentWidth
})

const amountToNextLevel = computed(() => {
  const levelInfo = getCurrentLevelInfo(props.currentAmount)
  const levelIndex = levelInfo.index
  
  if (levelIndex >= levels.length - 1) {
    return 0
  }
  const nextLevel = levels[levelIndex + 1]
  const nextThreshold = levelThresholds[nextLevel as keyof typeof levelThresholds]
  return Math.max(0, nextThreshold - props.currentAmount)
})

const getSegmentClass = (index: number) => {
  const currentLevelIndex = getCurrentLevelInfo(props.currentAmount).index
  
  // 当前等级所在的 segment
  if (index === currentLevelIndex) {
    return 'current'
  }
  // 已完成的等级（在当前等级之前）
  if (index < currentLevelIndex) {
    return 'completed'
  }
  return ''
}

const formatNumber = (num: number) => {
  return num.toLocaleString()
}
</script>

<style scoped>
.consume-level-progress {
  width: 100%;
  max-width: 100%;
  height: 100%;
  min-height: 248px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  box-sizing: border-box;
  overflow: hidden;
}

.level-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.level-label {
  font-size: 14px;
  font-weight: 600;
  color: #646a73;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.level-value {
  font-size: 24px;
  font-weight: 700;
  color: #0369a1;
}

.progress-container {
  position: relative;
  margin-bottom: 16px;
  padding: 20px 0;
}

.progress-track {
  display: flex;
  gap: 4px;
  height: 12px;
}

.level-segment {
  flex: 1;
  background: #e5e7eb;
  border-radius: 6px;
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 24px;
  transition: background-color 0.3s ease;
}

.level-segment.completed {
  background: #22c55e;
}

.level-segment.current {
  background: linear-gradient(90deg, #0369a1, #0ea5e9);
}

.segment-label {
  position: absolute;
  bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #646a73;
}

.level-segment.completed .segment-label,
.level-segment.current .segment-label {
  color: #1d2330;
}

.progress-indicator {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  transition: left 0.5s ease;
}

.indicator-arrow {
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 10px solid #0369a1;
}

.progress-info {
  text-align: center;
}

.info-text {
  font-size: 13px;
  color: #646a73;
}
</style>
