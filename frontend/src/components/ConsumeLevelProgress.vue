<template>
  <div class="consume-level-progress">
    <div class="level-labels">
      <div
        v-for="(level, index) in levels"
        :key="level.value"
        class="level-label"
        :class="{ active: currentLevelIndex >= index, current: currentLevel === level.value }"
      >
        <span class="level-badge" :class="level.value.toLowerCase()">
          {{ level.label }}
        </span>
      </div>
    </div>
    <div class="progress-bar-container">
      <div class="progress-segments">
        <div
          v-for="(segment, index) in segments"
          :key="index"
          class="progress-segment"
          :class="segment.level.toLowerCase()"
        />
      </div>
      <div class="progress-fill" :style="{ width: `${progress}%` }" />
      <div class="progress-marker" :style="{ left: `${progress}%` }">
        <div class="marker-dot" :class="currentLevel.toLowerCase()"></div>
      </div>
    </div>
    <div class="level-info">
      <div class="current-level">
        <span class="info-label">当前等级</span>
        <span class="level-value" :class="currentLevel.toLowerCase()">
          {{ getLevelLabel(currentLevel) }}
        </span>
      </div>
      <div v-if="nextLevel" class="next-level">
        <span class="info-label">下一等级</span>
        <span class="level-value" :class="nextLevel.toLowerCase()">
          {{ getLevelLabel(nextLevel) }}
        </span>
      </div>
      <div class="progress-percentage">
        <span class="percentage-value">{{ progress }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// 统一的消费等级配置（从低到高）
export const CONSUME_LEVELS = [
  { value: 'E', label: 'E级', color: '#a855f7' },
  { value: 'D', label: 'D级', color: '#f59e0b' },
  { value: 'C', label: 'C级', color: '#3296f7' },
  { value: 'B', label: 'B级', color: '#22c55e' },
  { value: 'A', label: 'A级', color: '#d97706' },
  { value: 'S', label: 'S级', color: '#ef4444' },
] as const

export type ConsumeLevel = typeof CONSUME_LEVELS[number]['value']

const props = defineProps<{
  currentLevel: string
}>()

// 组件内部自动计算进度
const progress = computed(() => {
  const level = props.currentLevel
  const index = CONSUME_LEVELS.findIndex(l => l.value === level)
  if (index < 0) return 0
  // 游标在每个等级段的中间位置
  return Math.round(((index + 0.5) / CONSUME_LEVELS.length) * 100)
})

const levels = CONSUME_LEVELS

const segments = CONSUME_LEVELS.map(l => ({ level: l.value }))

const currentLevelIndex = computed(() => 
  CONSUME_LEVELS.findIndex(l => l.value === props.currentLevel)
)

const nextLevel = computed(() => {
  const index = currentLevelIndex.value
  return index < CONSUME_LEVELS.length - 1 ? CONSUME_LEVELS[index + 1].value : null
})

const getLevelLabel = (level: string) => {
  return CONSUME_LEVELS.find(l => l.value === level)?.label || level
}
</script>

<style scoped>
.consume-level-progress {
  background: white;
  border-radius: 16px;
  padding: 24px;
  border: 1px solid var(--neutral-2, #eef0f3);
}

.level-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.level-label {
  opacity: 0.4;
  transition: opacity 200ms ease;
}

.level-label.active {
  opacity: 1;
}

.level-label.current .level-badge {
  transform: scale(1.1);
  box-shadow: 0 0 0 3px rgba(3, 105, 161, 0.1);
}

.level-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  transition: all 200ms ease;
}

/* 等级颜色 - 从低到高 */
.level-badge.e {
  background: #f3e8ff;
  color: #a855f7;
}

.level-badge.d {
  background: #fff7e8;
  color: #f59e0b;
}

.level-badge.c {
  background: #e8f3ff;
  color: #3296f7;
}

.level-badge.b {
  background: #e8ffea;
  color: #22c55e;
}

.level-badge.a {
  background: #fef3c7;
  color: #d97706;
}

.level-badge.s {
  background: #fee2e2;
  color: #ef4444;
}

.progress-bar-container {
  position: relative;
  height: 12px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--neutral-2, #eef0f3);
}

.progress-segments {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
}

.progress-segment {
  flex: 1;
  opacity: 0.3;
}

.progress-segment.e {
  background: #a855f7;
}

.progress-segment.d {
  background: #f59e0b;
}

.progress-segment.c {
  background: #3296f7;
}

.progress-segment.b {
  background: #22c55e;
}

.progress-segment.a {
  background: #d97706;
}

.progress-segment.s {
  background: #ef4444;
}

.progress-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, #a855f7 0%, #f59e0b 16%, #3296f7 33%, #22c55e 50%, #d97706 66%, #ef4444 100%);
  transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: 6px;
}

.progress-marker {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  transition: left 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.marker-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 3px solid white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: all 200ms ease;
}

.marker-dot.e {
  background: #a855f7;
}

.marker-dot.d {
  background: #f59e0b;
}

.marker-dot.c {
  background: #3296f7;
}

.marker-dot.b {
  background: #22c55e;
}

.marker-dot.a {
  background: #d97706;
}

.marker-dot.s {
  background: #ef4444;
}

.level-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
}

.current-level,
.next-level {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--neutral-5, #8f959e);
}

.level-value {
  font-size: 18px;
  font-weight: 700;
}

.level-value.e {
  color: #a855f7;
}

.level-value.d {
  color: #f59e0b;
}

.level-value.c {
  color: #3296f7;
}

.level-value.b {
  color: #22c55e;
}

.level-value.a {
  color: #d97706;
}

.level-value.s {
  color: #ef4444;
}

.progress-percentage {
  text-align: right;
}

.percentage-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10, #1d2330);
}
</style>
