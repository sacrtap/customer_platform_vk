<template>
  <a-timeline>
    <a-timeline-item v-for="(event, index) in events" :key="index" :color="event.dotColor">
      <div :class="['timeline-content', event.textClass]">
        <strong>{{ event.label }}</strong>
        <p v-if="event.operator" class="timeline-operator">操作人：{{ event.operator }}</p>
        <p v-if="event.time" class="timeline-time">{{ event.time }}</p>
        <p v-if="event.detailParts" class="timeline-detail">
          <span v-for="(part, i) in event.detailParts" :key="i">
            <template v-if="part.type === 'link'">
              {{ part.prefix
              }}<a :href="part.url" target="_blank" download class="timeline-attachment-link">{{
                part.label
              }}</a>
            </template>
            <template v-else>
              {{ part.text }}
            </template>
            <span v-if="i < event.detailParts.length - 1"> | </span>
          </span>
        </p>
      </div>
    </a-timeline-item>
  </a-timeline>
</template>

<script setup lang="ts">
/**
 * 状态机时间线哑渲染层：invoice / VR 结算单详情共用。
 * 节点推导逻辑（哪些节点、什么颜色）由 `common/timelineStatus.ts` 与各业务 wrapper 负责，本组件只渲染。
 */

import type { TimelineDetailPart } from './timelineStatus'

export interface TimelineEvent {
  label: string
  time?: string
  operator?: string
  detailParts?: TimelineDetailPart[]
  /** a-timeline-item 的 dot 颜色：blue=当前 / green=已完成 / gray=未到达 / red=取消 */
  dotColor: string
  /** 节点文案样式类：current-event / completed-event / pending-event / cancelled-event */
  textClass: string
}

defineProps<{
  events: TimelineEvent[]
}>()
</script>

<style scoped>
.timeline-content {
  line-height: 1.6;
}

/* 当前节点：蓝色加粗 */
.current-event {
  color: var(--primary);
  font-weight: 600;
}

/* 已完成节点：绿色 */
.completed-event {
  color: var(--green);
}

/* 未到达节点：灰色 */
.pending-event {
  color: var(--muted);
}

/* 取消节点：红色 */
.cancelled-event {
  color: var(--red);
  font-weight: 600;
}

.timeline-time {
  font-size: 12px;
  color: var(--muted);
  margin: 4px 0 0 0;
}

.timeline-operator {
  font-size: 12px;
  color: var(--ink);
  margin: 2px 0 0 0;
  font-weight: 500;
}

.timeline-detail {
  font-size: 12px;
  color: var(--muted);
  margin: 4px 0 0 0;
}

.timeline-attachment-link {
  color: var(--primary);
  text-decoration: underline;
  cursor: pointer;
}

.timeline-attachment-link:hover {
  opacity: 0.8;
}
</style>
