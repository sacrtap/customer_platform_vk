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
const CONSUME_LEVELS = [
  { value: 'C6', label: 'C6级', color: '#7C3AED' },
  { value: 'C5', label: 'C5级', color: '#D97706' },
  { value: 'C4', label: 'C4级', color: '#1D4ED8' },
  { value: 'C3', label: 'C3级', color: '#059669' },
  { value: 'C2', label: 'C2级', color: '#D97706' },
  { value: 'C1', label: 'C1级', color: '#DC2626' },
] as const

const props = defineProps<{
  currentLevel: string
}>()

// 组件内部自动计算进度
const progress = computed(() => {
  const level = props.currentLevel
  const index = CONSUME_LEVELS.findIndex((l) => l.value === level)
  if (index < 0) return 0
  // 游标在每个等级段的中间位置
  return Math.round(((index + 0.5) / CONSUME_LEVELS.length) * 100)
})

const levels = CONSUME_LEVELS

const segments = CONSUME_LEVELS.map((l) => ({ level: l.value }))

const currentLevelIndex = computed(() =>
  CONSUME_LEVELS.findIndex((l) => l.value === props.currentLevel)
)

const nextLevel = computed(() => {
  const index = currentLevelIndex.value
  return index < CONSUME_LEVELS.length - 1 ? CONSUME_LEVELS[index + 1].value : null
})

const getLevelLabel = (level: string) => {
  return CONSUME_LEVELS.find((l) => l.value === level)?.label || level
}
</script>

<style scoped>
.consume-level-progress {
  background: var(--panel);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid var(--line);
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
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
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
  background: #ede9fe;
  color: var(--violet);
}

.level-badge.d {
  background: #fef3c7;
  color: var(--amber);
}

.level-badge.c {
  background: #dbeafe;
  color: var(--primary);
}

.level-badge.b {
  background: #dcfce7;
  color: var(--green);
}

.level-badge.a {
  background: #fef3c7;
  color: var(--amber);
}

.level-badge.s {
  background: #fee2e2;
  color: var(--red);
}

.progress-bar-container {
  position: relative;
  height: 12px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--line);
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
  background: var(--violet);
}

.progress-segment.d {
  background: var(--amber);
}

.progress-segment.c {
  background: var(--primary);
}

.progress-segment.b {
  background: var(--green);
}

.progress-segment.a {
  background: var(--amber);
}

.progress-segment.s {
  background: var(--red);
}

.progress-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(
    90deg,
    var(--violet) 0%,
    var(--amber) 16%,
    var(--primary) 33%,
    var(--green) 50%,
    var(--amber) 66%,
    var(--red) 100%
  );
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
  background: var(--violet);
}

.marker-dot.d {
  background: var(--amber);
}

.marker-dot.c {
  background: var(--primary);
}

.marker-dot.b {
  background: var(--green);
}

.marker-dot.a {
  background: var(--amber);
}

.marker-dot.s {
  background: var(--red);
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
  color: var(--muted);
}

.level-value {
  font-size: 18px;
  font-weight: 700;
}

.level-value.e {
  color: var(--violet);
}

.level-value.d {
  color: var(--amber);
}

.level-value.c {
  color: var(--primary);
}

.level-value.b {
  color: var(--green);
}

.level-value.a {
  color: var(--amber);
}

.level-value.s {
  color: var(--red);
}

.progress-percentage {
  text-align: right;
}

.percentage-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
}
</style>
