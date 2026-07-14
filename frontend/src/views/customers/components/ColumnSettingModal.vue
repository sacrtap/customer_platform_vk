<template>
  <a-modal
    v-model:visible="localVisible"
    title="自定义列"
    @confirm="handleConfirm"
    @cancel="emit('update:visible', false)"
  >
    <p class="hint">选择要在表格中显示的列</p>
    <CheckboxArray v-model="selectedColumns" :options="columnOptions" :columns="3" />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import CheckboxArray from '@/components/ui/CheckboxArray.vue'

const props = defineProps<{
  visible: boolean
  columns: Array<{ key: string; title: string }>
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'update:modelValue': [value: string[]]
}>()

const localVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const columnOptions = computed(() => props.columns.map((c) => ({ label: c.title, value: c.key })))

const selectedColumns = ref([...props.modelValue])

const handleConfirm = () => {
  emit('update:modelValue', selectedColumns.value)
  emit('update:visible', false)
}
</script>

<style scoped>
.hint {
  font-size: 13px;
  color: var(--muted);
  margin-top: 0;
  margin-bottom: 16px;
}
</style>
