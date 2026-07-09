<template>
  <div class="action-toolbar">
    <slot />
  </div>
</template>

<style scoped>
.action-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
</style>