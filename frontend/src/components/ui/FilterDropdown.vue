<template>
  <div ref="dropdownRef" class="filter-dropdown" :class="{ 'open-trigger': isOpen }">
    <button type="button" class="filter-trigger" @click="toggle">
      <span class="filter-label">{{ label }}</span>
      <span class="filter-value">{{ displayValue }}</span>
      <span class="filter-arrow" :class="{ open: isOpen }">▾</span>
    </button>
    <div v-if="isOpen" class="filter-panel">
      <!-- "全部"选项 -->
      <div
        v-if="!hideAll"
        class="filter-option"
        :class="{ active: isAllSelected }"
        @click="selectAll"
      >
        全部
      </div>
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
    hideAll?: boolean
  }>(),
  {
    multiple: false,
    hideAll: false,
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string | string[]]
  apply: []
}>()

const isOpen = ref(false)
const dropdownRef = ref<HTMLElement>()

const isAllSelected = computed(() => {
  if (props.multiple) {
    return (props.modelValue as string[]).length === 0
  }
  return !props.modelValue
})

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

// 点击“全部”：单选清空值，多选清空数组
const selectAll = () => {
  if (props.multiple) {
    emit('update:modelValue', [])
  } else {
    emit('update:modelValue', '')
    isOpen.value = false
    emit('apply')
  }
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
  min-width: 132px;
}
.filter-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  font: inherit;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}
.filter-trigger:hover {
  border-color: #93c5fd;
}
.filter-dropdown.open-trigger .filter-trigger {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
}
.filter-label {
  font-size: 12px;
  color: var(--muted);
  font-weight: 600;
  white-space: nowrap;
}
.filter-value {
  font-size: 13px;
  color: var(--ink);
  font-weight: 700;
  flex: 1;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.filter-arrow {
  font-size: 10px;
  color: var(--muted);
  transition: transform 0.2s;
}
.filter-arrow.open {
  transform: rotate(180deg);
}
.filter-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 100%;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  z-index: 30;
  padding: 4px;
  max-height: 280px;
  overflow-y: auto;
}
.filter-option {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--ink);
  cursor: pointer;
  transition: background 0.15s;
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-option:hover {
  background: #eff6ff;
  color: var(--primary);
}
.filter-option.active {
  background: #dbeafe;
  color: var(--primary);
  font-weight: 700;
}
.filter-option.active::before {
  content: '✓';
  font-size: 12px;
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
  border-radius: 8px;
  background: var(--primary);
  color: white;
  font-size: 13px;
  cursor: pointer;
}
</style>
