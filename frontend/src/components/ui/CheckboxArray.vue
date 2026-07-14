<template>
  <div class="checkbox-grid" :style="{ gridTemplateColumns: `repeat(${columns}, 1fr)` }">
    <label v-for="opt in options" :key="opt.value" class="checkbox-item">
      <input
        type="checkbox"
        :checked="modelValue.includes(opt.value)"
        @change="toggle(opt.value)"
      />
      {{ opt.label }}
    </label>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: string[]
    options: Array<{ label: string; value: string }>
    columns?: number
  }>(),
  {
    columns: 4,
  }
)

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const toggle = (val: string) => {
  const arr = [...props.modelValue]
  const idx = arr.indexOf(val)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(val)
  emit('update:modelValue', arr)
}
</script>

<style scoped>
.checkbox-grid {
  display: grid;
  gap: 8px;
}
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 0;
}
.checkbox-item input[type='checkbox'] {
  width: 14px;
  height: 14px;
  cursor: pointer;
}
</style>
