<template>
  <a-modal
    v-model:visible="localVisible"
    title="分配运营经理"
    width="480px"
    :confirm-loading="loading"
    @confirm="handleConfirm"
    @cancel="emit('update:visible', false)"
  >
    <a-form layout="vertical">
      <a-form-item label="选择运营经理" required>
        <a-select v-model="selectedManager" placeholder="请选择运营经理" allow-clear>
          <a-option v-for="m in managers" :key="m.id" :value="m.id">
            {{ m.real_name || `#${m.id}` }}
          </a-option>
        </a-select>
      </a-form-item>
      <a-form-item>
        <p class="hint-info">将分配 {{ selectedCount }} 个客户给所选运营经理</p>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  loading: boolean
  selectedCount: number
  managers: Array<{ id: number; real_name: string | null }>
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [managerId: number]
}>()

const localVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const selectedManager = ref<number | null>(null)

watch(
  () => props.visible,
  (v) => {
    if (v) selectedManager.value = null
  }
)

const handleConfirm = () => {
  if (selectedManager.value == null) return
  emit('confirm', selectedManager.value)
}
</script>

<style scoped>
.hint-info {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
}
</style>
