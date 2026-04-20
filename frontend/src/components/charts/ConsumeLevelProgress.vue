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

const levels = ['D', 'C', 'B', 'A', 'S']

const levelThresholds = {
  D: 0,
  C: 60000,
  B: 120000,
  A: 250000,
  S: 500000,
}

const currentLevelIndex = computed(() => levels.indexOf(props.currentLevel))

const nextLevelIndex = computed(() => Math.min(currentLevelIndex.value + 1, levels.length - 1))

const currentThreshold = computed(
  () => levelThresholds[props.currentLevel as keyof typeof levelThresholds] || 0
)

const nextThreshold = computed(() => {
  const nextLevel = levels[nextLevelIndex.value]
  return levelThresholds[nextLevel as keyof typeof levelThresholds] || 0
})

const indicatorPosition = computed(() => {
  if (currentLevelIndex.value >= levels.length - 1) {
    return 100
  }
  const range = nextThreshold.value - currentThreshold.value
  const progress = props.currentAmount - currentThreshold.value
  const segmentProgress = Math.min(progress / range, 1)
  return (currentLevelIndex.value + segmentProgress) * 25
})

const amountToNextLevel = computed(() => {
  if (currentLevelIndex.value >= levels.length - 1) {
    return 0
  }
  return Math.max(0, nextThreshold.value - props.currentAmount)
})

const getSegmentClass = (index: number) => {
  if (index < currentLevelIndex.value) {
    return 'completed'
  }
  if (index === currentLevelIndex.value) {
    return 'current'
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
  background: white;
  border-radius: 12px;
  border: 1px solid #eef0f3;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
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
  bottom: 0;
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
