<template>
  <div class="quick-filter-tags">
    <button
      v-for="tag in tags"
      :key="tag.value"
      class="quick-tag"
      :class="{ active: modelValue === tag.value }"
      @click="$emit('update:modelValue', modelValue === tag.value ? '' : tag.value)"
    >
      {{ tag.label }}
      <span v-if="tag.count != null" class="tag-count">{{ tag.count }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
interface QuickTag {
  label: string
  value: string
  count?: number
}

defineProps<{
  tags: QuickTag[]
  modelValue: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<style scoped>
.quick-filter-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.quick-tag {
  border: 1px solid var(--line);
  background: white;
  border-radius: 999px;
  padding: 7px 10px;
  color: var(--muted);
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.18s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.quick-tag:hover {
  border-color: #93c5fd;
  background: #eff6ff;
  color: var(--primary);
}

.quick-tag.active {
  background: #dbeafe;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.tag-count {
  font-size: 12px;
  opacity: 0.8;
}
</style>
