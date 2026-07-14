<template>
  <a-modal
    v-model:visible="localVisible"
    title="批量设置等级"
    width="480px"
    :confirm-loading="loading"
    @confirm="handleConfirm"
    @cancel="emit('update:visible', false)"
  >
    <a-form layout="vertical">
      <a-form-item label="设置规模等级">
        <a-select v-model="scaleLevel" placeholder="请选择等级" allow-clear>
          <a-option value="S">S（超大型）</a-option>
          <a-option value="A">A（大型）</a-option>
          <a-option value="B">B（中型）</a-option>
          <a-option value="C">C（小型）</a-option>
          <a-option value="D">D（微型）</a-option>
        </a-select>
      </a-form-item>
      <a-form-item label="设置消费等级">
        <a-select v-model="consumeLevel" placeholder="请选择等级" allow-clear>
          <a-option value="S">S（高价值）</a-option>
          <a-option value="A">A（高消费）</a-option>
          <a-option value="B">B（中消费）</a-option>
          <a-option value="C">C（低消费）</a-option>
          <a-option value="none">未消费</a-option>
        </a-select>
      </a-form-item>
      <a-form-item>
        <p class="hint-info">将应用到已选中的 {{ selectedCount }} 个客户</p>
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
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [data: { scale_level: string; consume_level: string }]
}>()

const localVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const scaleLevel = ref('')
const consumeLevel = ref('')

watch(
  () => props.visible,
  (v) => {
    if (v) {
      scaleLevel.value = ''
      consumeLevel.value = ''
    }
  }
)

const handleConfirm = () => {
  emit('confirm', { scale_level: scaleLevel.value, consume_level: consumeLevel.value })
}
</script>

<style scoped>
.hint-info {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
}
</style>
