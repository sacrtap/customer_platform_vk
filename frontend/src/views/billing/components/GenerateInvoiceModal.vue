<template>
  <a-modal
    v-model:visible="isVisible"
    title="生成结算单"
    width="860px"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form layout="vertical">
      <!-- 生成方式选择 -->
      <a-form-item label="生成方式" required>
        <a-radio-group v-model="mode" @change="handleModeChange">
          <a-radio value="customer">按指定客户</a-radio>
          <a-radio value="batch">按计费类型</a-radio>
        </a-radio-group>
      </a-form-item>

      <!-- ============ 按指定客户 ============ -->
      <template v-if="mode === 'customer'">
        <a-form-item label="客户" required>
          <CustomerAutoComplete
            :key="customerPickerKey"
            v-model="form.customer_id"
            placeholder="请选择客户"
            width="100%"
          />
        </a-form-item>
        <a-form-item label="结算周期" required>
          <a-range-picker v-model="periodRange" style="width: 100%" @change="handlePeriodChange" />
        </a-form-item>
        <a-form-item v-if="calculatedItems.length" label="计费明细预览">
          <a-table
            :columns="itemColumns"
            :data="calculatedItems"
            :pagination="false"
            size="small"
            row-key="pricing_rule_id"
          >
            <template #pricingType="{ record }">
              <span :class="['pricing-tag', `pricing-${record.pricing_type}`]">
                {{ pricingTypeText(record.pricing_type) }}
              </span>
            </template>
            <template #deviceType="{ record }">
              {{ record.device_type || '—' }}
            </template>
            <template #layerType="{ record }">
              {{
                record.layer_type === 'multi'
                  ? '多层'
                  : record.layer_type === 'single'
                    ? '单层'
                    : '—'
              }}
            </template>
            <template #quantity="{ record }">
              <div class="rule-detail">
                <div v-for="(line, idx) in formatQuantity(record)" :key="idx">{{ line }}</div>
              </div>
            </template>
            <template #ruleDetail="{ record }">
              <div class="rule-detail">
                <div v-for="(line, idx) in formatRuleDetail(record)" :key="idx">{{ line }}</div>
              </div>
            </template>
            <template #subtotal="{ record }">
              <span>{{ formatCurrency(record.subtotal) }}</span>
            </template>
          </a-table>
          <div class="total-preview">预计总金额：{{ formatCurrency(totalPreview) }}</div>
        </a-form-item>
      </template>

      <!-- ============ 按计费类型（批量） ============ -->
      <template v-else>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="计费类型" required>
              <a-select v-model="batchForm.pricing_type" placeholder="请选择">
                <a-option value="fixed">定价结算</a-option>
                <a-option value="tiered">阶梯结算</a-option>
                <a-option value="package">包年结算</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="是否房产客户">
              <a-select v-model="batchForm.is_real_estate" placeholder="请选择">
                <a-option :value="true">是</a-option>
                <a-option :value="false">否</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="行业（可多选）">
              <a-select
                v-model="batchForm.industry_type_ids"
                multiple
                allow-create
                placeholder="默认房产经纪/ERP/平台"
                :options="industryOptions"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="规模等级（可多选）">
              <a-select
                v-model="batchForm.scale_levels"
                multiple
                allow-create
                placeholder="默认全部"
              >
                <a-option v-for="lv in scaleLevelOptions" :key="lv" :value="lv">{{ lv }}</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="消费等级（可多选）">
              <a-select
                v-model="batchForm.consume_levels"
                multiple
                allow-create
                placeholder="默认全部"
              >
                <a-option v-for="lv in consumeLevelOptions" :key="lv" :value="lv">{{
                  lv
                }}</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="结算周期" required>
              <a-range-picker v-model="batchPeriodRange" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 匹配客户预览 -->
        <a-form-item v-if="previewCustomers.length" label="匹配客户预览">
          <div class="preview-summary">
            共匹配 <strong>{{ previewCustomers.length }}</strong> 个客户，其中
            <strong class="text-warn">{{
              previewCustomers.filter((c) => !c.has_manager || !c.has_sales_manager).length
            }}</strong>
            个未指定运营/销售经理（将跳过）
          </div>
          <a-table
            :columns="previewColumns"
            :data="previewCustomers"
            :pagination="{ pageSize: 5 }"
            size="small"
            row-key="id"
          >
            <template #manager="{ record }">
              <span :class="record.has_manager ? '' : 'text-danger'">
                {{ record.has_manager ? '已指定' : '未指定' }}
              </span>
            </template>
            <template #sales="{ record }">
              <span :class="record.has_sales_manager ? '' : 'text-danger'">
                {{ record.has_sales_manager ? '已指定' : '未指定' }}
              </span>
            </template>
          </a-table>
        </a-form-item>
      </template>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  calculateInvoiceItems,
  generateInvoice,
  previewBatchCustomers,
  generateInvoicesBatch,
} from '@/api/billing'
import { getIndustryTypesList } from '@/api/industryTypes'
import { formatCurrency } from '@/utils/formatters'
import { pricingTypeText, formatQuantity, formatRuleDetail } from '@/utils/invoiceFormatters'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
import type { IndustryType } from '@/types'
import type { InvoiceItem } from '@/api/billing'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [value: boolean]; success: [] }>()

const isVisible = computed({ get: () => props.visible, set: (val) => emit('update:visible', val) })

const loading = ref(false)
const mode = ref<'customer' | 'batch'>('customer')

// ===== 按指定客户模式 =====
const calculatedItems = ref<InvoiceItem[]>([])

const form = reactive({
  customer_id: undefined as number | undefined,
  period_start: '',
  period_end: '',
})

const periodRange = ref<string[]>([])

// 弹窗每次打开时递增：CustomerAutoComplete 的显示文本由组件内部 displayText 维护，
// 不随 modelValue 变化，需重建组件才能清空输入框（不改动该组件本身）
const customerPickerKey = ref(0)

const itemColumns = [
  { title: '计费类型', slotName: 'pricingType', width: 90 },
  { title: '设备类型', slotName: 'deviceType', width: 80 },
  { title: '楼层', slotName: 'layerType', width: 70 },
  { title: '用量', slotName: 'quantity', width: 90 },
  { title: '计费规则', slotName: 'ruleDetail' },
  { title: '小计', slotName: 'subtotal', width: 120 },
]

const totalPreview = computed(() =>
  calculatedItems.value.reduce(
    (sum, item) =>
      sum + (item.subtotal !== undefined ? item.subtotal : item.quantity * item.unit_price),
    0
  )
)

// 获取计费明细预览
const fetchCalculatedItems = async () => {
  if (form.customer_id && form.period_start && form.period_end) {
    try {
      const res = await calculateInvoiceItems({
        customer_id: form.customer_id,
        period_start: form.period_start,
        period_end: form.period_end,
      })
      // 将后端可能返回的 null 值转为 undefined，以兼容 InvoiceItem 类型
      const rawItems = (res.data?.items || []) as Array<Record<string, unknown>>
      calculatedItems.value = rawItems.map((item) => {
        const cleaned: Record<string, unknown> = {}
        for (const [key, value] of Object.entries(item)) {
          cleaned[key] = value === null ? undefined : value
        }
        return cleaned as unknown as InvoiceItem
      })
    } catch {
      calculatedItems.value = []
    }
  } else {
    calculatedItems.value = []
  }
}

const handlePeriodChange = async (dates: string[]) => {
  if (dates.length === 2) {
    form.period_start = dates[0]
    form.period_end = dates[1]
    await fetchCalculatedItems()
  } else {
    form.period_start = ''
    form.period_end = ''
    calculatedItems.value = []
  }
}

// 客户变化时自动刷新预览
watch(
  () => form.customer_id,
  () => {
    if (mode.value === 'customer') {
      fetchCalculatedItems()
    }
  }
)

// ===== 按计费类型（批量）模式 =====
const scaleLevelOptions = ['S', 'A', 'B', 'C', 'D', 'E']
const consumeLevelOptions = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6']

const industryOptions = ref<{ label: string; value: number }[]>([])

const batchForm = reactive({
  pricing_type: 'fixed' as 'fixed' | 'tiered' | 'package',
  industry_type_ids: [] as number[],
  scale_levels: [] as string[],
  consume_levels: [] as string[],
  is_real_estate: true as boolean,
})

const batchPeriodRange = ref<string[]>([])

const previewCustomers = ref<
  {
    id: number
    name: string
    has_manager: boolean
    has_sales_manager: boolean
  }[]
>([])

const previewColumns = [
  { title: '客户名称', dataIndex: 'name' },
  { title: '运营经理', slotName: 'manager', width: 100 },
  { title: '销售经理', slotName: 'sales', width: 100 },
]

// 加载行业类型选项
const loadIndustryOptions = async () => {
  try {
    const res = await getIndustryTypesList()
    const list: IndustryType[] = res.data?.data || res.data || []
    industryOptions.value = list.map((item) => ({ label: item.name, value: item.id }))
    // 默认选中房产经纪/房产ERP/房产平台
    const defaults = list.filter(
      (item) =>
        item.name.includes('房产经纪') ||
        item.name.includes('房产ERP') ||
        item.name.includes('房产平台')
    )
    if (defaults.length > 0) {
      batchForm.industry_type_ids = defaults.map((d) => d.id)
    }
  } catch {
    industryOptions.value = []
  }
}

// 批量预览
const doPreviewBatch = async () => {
  if (!batchForm.pricing_type) {
    previewCustomers.value = []
    return
  }
  try {
    const res = await previewBatchCustomers({
      pricing_type: batchForm.pricing_type,
      industry_type_ids: batchForm.industry_type_ids.length
        ? batchForm.industry_type_ids
        : undefined,
      scale_levels: batchForm.scale_levels.length ? batchForm.scale_levels : undefined,
      consume_levels: batchForm.consume_levels.length ? batchForm.consume_levels : undefined,
      is_real_estate: batchForm.is_real_estate,
    })
    previewCustomers.value = res.data?.customers || []
  } catch {
    previewCustomers.value = []
  }
}

// 批量条件变化时自动预览
watch(
  () => [
    batchForm.pricing_type,
    batchForm.industry_type_ids,
    batchForm.scale_levels,
    batchForm.consume_levels,
    batchForm.is_real_estate,
  ],
  () => {
    if (mode.value === 'batch') {
      doPreviewBatch()
    }
  },
  { deep: true }
)

// 切换模式时初始化
const handleModeChange = (val: string | number | boolean) => {
  if (val === 'batch' && industryOptions.value.length === 0) {
    loadIndustryOptions()
  }
  if (val === 'batch') {
    doPreviewBatch()
  }
}

// 弹窗打开时：保留结算周期，仅清空客户和预览数据
watch(
  () => props.visible,
  (val) => {
    if (val) {
      mode.value = 'customer'
      // 清空客户和预览
      customerPickerKey.value += 1
      calculatedItems.value = []
      form.customer_id = undefined
      form.period_start = periodRange.value.length === 2 ? periodRange.value[0] : ''
      form.period_end = periodRange.value.length === 2 ? periodRange.value[1] : ''
      // 保留 batchPeriodRange，仅清空预览
      previewCustomers.value = []
      batchForm.pricing_type = 'fixed'
      batchForm.industry_type_ids = []
      batchForm.scale_levels = []
      batchForm.consume_levels = []
      batchForm.is_real_estate = true
    }
  }
)

// ===== 提交 =====
const handleSubmit = async () => {
  if (mode.value === 'customer') {
    return await handleSubmitSingle()
  } else {
    return await handleSubmitBatch()
  }
}

const handleSubmitSingle = async () => {
  if (!form.customer_id || !form.period_start || !form.period_end) {
    Message.error('请完善客户和结算周期信息')
    return false
  }
  if (calculatedItems.value.length === 0) {
    Message.error('暂无计费明细，请先选择客户和结算周期生成预览')
    return false
  }
  loading.value = true
  try {
    await generateInvoice({
      customer_id: form.customer_id,
      period_start: form.period_start,
      period_end: form.period_end,
      items: calculatedItems.value,
    })
    Message.success('生成成功')
    emit('success')
    return true
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '生成失败')
    return false
  } finally {
    loading.value = false
  }
}

const handleSubmitBatch = async () => {
  if (!batchPeriodRange.value || batchPeriodRange.value.length !== 2) {
    Message.error('请选择结算周期')
    return false
  }
  if (previewCustomers.value.length === 0) {
    Message.error('未匹配到任何客户，请调整筛选条件')
    return false
  }
  const eligibleCount = previewCustomers.value.filter(
    (c) => c.has_manager && c.has_sales_manager
  ).length
  if (eligibleCount === 0) {
    Message.error('匹配到的客户均未指定运营/销售经理，无法生成')
    return false
  }
  loading.value = true
  try {
    const res = await generateInvoicesBatch({
      pricing_type: batchForm.pricing_type,
      industry_type_ids: batchForm.industry_type_ids.length
        ? batchForm.industry_type_ids
        : undefined,
      scale_levels: batchForm.scale_levels.length ? batchForm.scale_levels : undefined,
      consume_levels: batchForm.consume_levels.length ? batchForm.consume_levels : undefined,
      is_real_estate: batchForm.is_real_estate,
      period_start: batchPeriodRange.value[0],
      period_end: batchPeriodRange.value[1],
    })
    const result = res.data
    if (result.success_count > 0) {
      Message.success(
        `批量生成完成：成功 ${result.success_count} 个，跳过 ${result.skipped.length} 个`
      )
      emit('success')
      return true
    } else {
      Message.warning('所有客户均被跳过，未生成任何结算单')
      return false
    }
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '批量生成失败')
    return false
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>

<style scoped>
.total-preview {
  text-align: right;
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
  margin-top: 8px;
}
.preview-summary {
  margin-bottom: 8px;
  font-size: 13px;
  color: #64748b;
}
.text-warn {
  color: #f59e0b;
  font-weight: 600;
}
.text-danger {
  color: var(--red, #ef4444);
}

/* 计费类型标签 */
.pricing-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}
.pricing-fixed {
  background: #e0f2fe;
  color: #0284c7;
}
.pricing-tiered {
  background: #dcfce7;
  color: #16a34a;
}
.pricing-package {
  background: #fef3c7;
  color: #d97706;
}

/* 计费规则详情 */
.rule-detail {
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
}
</style>
