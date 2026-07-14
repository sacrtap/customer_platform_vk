<template>
  <div ref="dropdownRef" class="filter-dropdown">
    <button type="button" class="filter-trigger" @click="toggle">
      <span class="filter-label">{{ label }}</span>
      <span class="filter-value">{{ displayValue }}</span>
      <span class="filter-arrow" :class="{ open: isOpen }">▾</span>
    </button>
    <div v-if="isOpen" class="filter-panel">
      <div
        v-for="opt in options"
        :key="opt.value"
        class="filter-option"
        :class="{ active: isSelected(opt.value) }"
        @click="selectOption(opt.value)"
      >
        {{ opt.label }}
      </div>
      <div v-if="multiple" class="filter-actions">
        <button type="button" class="btn-confirm" @click="confirmApply">确认</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface Option {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    label: string
    modelValue: string | string[]
    options: Option[]
    multiple?: boolean
  }>(),
  {
    multiple: false,
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string | string[]]
  apply: []
}>()

const isOpen = ref(false)
const dropdownRef = ref<HTMLElement>()

const displayValue = computed(() => {
  if (props.multiple) {
    const arr = props.modelValue as string[]
    if (arr.length === 0) return '全部'
    if (arr.length === 1) {
      return props.options.find((o) => o.value === arr[0])?.label ?? '全部'
    }
    return `已选 ${arr.length} 项`
  }
  if (!props.modelValue) return '全部'
  return props.options.find((o) => o.value === props.modelValue)?.label ?? '全部'
})

const isSelected = (val: string) => {
  if (props.multiple) return (props.modelValue as string[]).includes(val)
  return props.modelValue === val
}

const toggle = () => {
  isOpen.value = !isOpen.value
}

const selectOption = (val: string) => {
  if (props.multiple) {
    const arr = [...(props.modelValue as string[])]
    const idx = arr.indexOf(val)
    if (idx >= 0) arr.splice(idx, 1)
    else arr.push(val)
    emit('update:modelValue', arr)
  } else {
    emit('update:modelValue', val)
    isOpen.value = false
    emit('apply')
  }
}

const confirmApply = () => {
  isOpen.value = false
  emit('apply')
}

const handleClickOutside = (e: MouseEvent) => {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
.filter-dropdown {
  position: relative;
  display: inline-block;
}
.filter-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: white;
  cursor: pointer;
  font-size: 13px;
  transition: border-color 0.2s;
}
.filter-trigger:hover {
  border-color: var(--primary);
}
.filter-label {
  color: var(--muted);
}
.filter-value {
  color: var(--ink);
  font-weight: 500;
}
.filter-arrow {
  transition: transform 0.2s;
  font-size: 10px;
}
.filter-arrow.open {
  transform: rotate(180deg);
}
.filter-panel {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  min-width: 180px;
  background: white;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  z-index: 100;
  padding: 4px;
}
.filter-option {
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}
.filter-option:hover {
  background: var(--bg);
}
.filter-option.active {
  background: #eff6ff;
  color: var(--primary);
  font-weight: 600;
}
.filter-actions {
  padding: 8px 12px;
  border-top: 1px solid var(--line);
  margin-top: 4px;
}
.btn-confirm {
  width: 100%;
  padding: 6px;
  border: none;
  border-radius: 6px;
  background: var(--primary);
  color: white;
  font-size: 13px;
  cursor: pointer;
}
</style>
