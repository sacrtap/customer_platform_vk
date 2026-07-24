<template>
  <div class="sync-status-bar" :class="status">
    <span class="pulse-dot" />
    <span class="sync-text">
      <template v-if="status === 'ok'">数据同步正常</template>
      <template v-else-if="status === 'warning'">数据同步异常 · {{ warningText }}</template>
      <template v-else>同步中…</template>
      · 最近同步 {{ lastSync }}<template v-if="nextSync"> · 下次同步 {{ nextSync }}</template>
    </span>
    <slot name="action" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  status: 'ok' | 'warning' | 'syncing'
  lastSync: string
  nextSync?: string
  warningText?: string
}>()
</script>

<style scoped>
.sync-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 14px;
}
.sync-status-bar.ok {
  background: linear-gradient(90deg, #ecfdf5, #f0fdf4);
  border: 1px solid #bbf7d0;
  color: #059669;
}
.sync-status-bar.warning {
  background: linear-gradient(90deg, #fffbeb, #fef3c7);
  border: 1px solid #fde68a;
  color: #d97706;
}
.sync-status-bar.syncing {
  background: linear-gradient(90deg, #eff6ff, #dbeafe);
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
}
.pulse-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: currentColor;
  position: relative;
  flex-shrink: 0;
}
.pulse-dot::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.3;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.3;
  }
  70% {
    transform: scale(2);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 0;
  }
}
</style>
