<template>
  <a-modal v-model:visible="isVisible" title="生成结算单" width="700px" :confirm-loading="loading" @before-ok="handleSubmit" @cancel="emit('update:visible', false)">
    <a-form :model="form" :rules="rules" layout="vertical">
      <a-form-item field="customer_id" label="客户" required>
        <CustomerAutoComplete v-model="form.customer_id" placeholder="请选择客户" width="100%" />
      </a-form-item>
      <a-form-item field="period_start" label="结算周期" required>
        <a-range-picker v-model="periodRange" style="width: 100%" @change="handlePeriodChange" />
      </a-form-item>
      <a-form-item v-if="calculatedItems.length" label="结算明细预览">
        <a-table :columns="itemColumns" :data="calculatedItems" :pagination="false" size="small" row-key="id">
          <template #subtotal="{ record }">
            <span>{{ formatCurrency(record.quantity * record.unit_price) }}</span>
          </template>
        </a-table>
        <div class="total-preview">预计总金额：{{ formatCurrency(totalPreview) }}</div>
      </a-form-item>
      <a-form-item field="remark" label="备注">
        <a-textarea v-model="form.remark" placeholder="请输入备注" :max-length="200" show-word-limit />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { calculateInvoiceItems } from '@/api/billing'
import { formatCurrency } from '@/utils/formatters'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [value: boolean]; success: [data: unknown] }>()

const isVisible = computed({ get: () => props.visible, set: (val) => emit('update:visible', val) })

const loading = ref(false)
const calculatedItems = ref<{ id?: number; device_type: string; quantity: number; unit_price: number }[]>([])

const form = reactive({
  customer_id: undefined as number | undefined,
  period_start: '',
  period_end: '',
  remark: '',
})

const periodRange = ref<string[]>([])

const rules = {
  customer_id: [{ required: true, message: '请选择客户' }],
  period_start: [{ required: true, message: '请选择结算周期' }],
}

const itemColumns = [
  { title: '设备类型', dataIndex: 'device_type', width: 140 },
  { title: '图层', dataIndex: 'layer_type', width: 80 },
  { title: '数量', dataIndex: 'quantity', width: 80 },
  { title: '单价', dataIndex: 'unit_price', width: 100 },
  { title: '小计', slotName: 'subtotal', width: 120 },
]

const totalPreview = computed(() => calculatedItems.value.reduce((sum, item) => sum + item.quantity * item.unit_price, 0))

const handlePeriodChange = async (dates: string[]) => {
  if (dates.length === 2 && form.customer_id) {
    form.period_start = dates[0]
    form.period_end = dates[1]
    try {
      const res = await calculateInvoiceItems({
        customer_id: form.customer_id,
        period_start: dates[0],
        period_end: dates[1],
      })
      calculatedItems.value = res.data?.items || []
    } catch {
      calculatedItems.value = []
    }
  }
}

const handleSubmit = async () => {
  if (!form.customer_id || !form.period_start) {
    Message.error('请完善信息')
    return false
  }
  loading.value = true
  try {
    emit('success', { ...form, items: calculatedItems.value })
    Message.success('生成请求已提交')
    return true
  } catch {
    return false
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.total-preview { text-align: right; font-size: 14px; font-weight: 600; color: #0369a1; margin-top: 8px; }
</style>
