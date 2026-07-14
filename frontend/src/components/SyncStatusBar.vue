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
  background: rgba(16, 185, 129, .08);
  color: #059669;
}
.sync-status-bar.warning {
  background: rgba(245, 158, 11, .08);
  color: #D97706;
}
.sync-status-bar.syncing {
  background: rgba(29, 78, 216, .08);
  color: #1D4ED8;
}
.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 2s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.sync-text { flex: 1; }
</style>
