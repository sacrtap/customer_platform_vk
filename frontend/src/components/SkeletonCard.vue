<template>
  <div class="skeleton-card" :style="{ height: height }">
    <div class="skeleton-placeholder">
      <div class="skeleton-line skeleton-line--short" />
      <div class="skeleton-line" />
      <div class="skeleton-line skeleton-line--long" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    height?: string
  }>(),
  {
    height: '110px',
  }
)
</script>

<style scoped>
.skeleton-card {
  background: white;
  border-radius: 12px;
  padding: 20px 16px;
  border: 1px solid var(--soft);
  overflow: hidden;
}

.skeleton-placeholder {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-line {
  height: 16px;
  background: linear-gradient(
    90deg,
    var(--bg) 0%,
    var(--soft) 25%,
    var(--bg) 50%,
    var(--soft) 75%,
    var(--bg) 100%
  );
  background-size: 400% 100%;
  border-radius: 4px;
  animation: shimmer 2s ease-in-out infinite;
}

.skeleton-line--short {
  width: 60%;
  height: 14px;
  animation-delay: 0.1s;
}

.skeleton-line--long {
  width: 100%;
  animation-delay: 0.2s;
}

@keyframes shimmer {
  0% {
    background-position: 400% 0;
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
  100% {
    background-position: -400% 0;
    opacity: 0.5;
  }
}

/* 减少运动偏好支持 */
@media (prefers-reduced-motion: reduce) {
  .skeleton-line {
    animation: none;
    background: var(--soft);
  }
}
</style>
