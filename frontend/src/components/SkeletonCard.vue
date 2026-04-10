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
  border: 1px solid var(--neutral-2);
  overflow: hidden;
}

.skeleton-placeholder {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-line {
  height: 16px;
  background: linear-gradient(90deg, #f0f0f0 25%, #f7f7f7 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  animation: shimmer 1.5s infinite;
}

.skeleton-line--short {
  width: 60%;
  height: 14px;
}

.skeleton-line--long {
  width: 100%;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
