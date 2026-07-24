<template>
  <a-modal
    :visible="visible"
    :title="isEdit ? '编辑规则' : '新建规则'"
    :confirm-loading="modalLoading"
    width="600px"
    @update:visible="$emit('update:visible', $event)"
    @before-ok="handleSubmit"
  >
    <a-form :model="formData" layout="vertical">
      <a-form-item label="客户" :rules="[{ required: true, message: '请选择客户' }]">
        <CustomerAutoComplete
          v-model="formData.customer_id"
          :display-name="formData.customer_name"
          placeholder="请输入客户名称搜索"
          width="100%"
        />
      </a-form-item>
      <a-form-item label="计费类型" :rules="[{ required: true, message: '请选择计费类型' }]">
        <a-select
          v-model="formData.pricing_type"
          placeholder="请选择"
          @change="onPricingTypeChange"
        >
          <a-option value="fixed">定价结算</a-option>
          <a-option value="tiered">阶梯结算</a-option>
          <a-option value="package">包年结算</a-option>
        </a-select>
      </a-form-item>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="设备类型" :rules="[{ required: true, message: '请选择设备类型' }]">
            <a-select v-model="formData.device_type" placeholder="请选择">
              <a-option value="X">X 系列</a-option>
              <a-option value="N">N 系列</a-option>
              <a-option value="L">L 系列</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="楼层类型" :rules="[{ required: true, message: '请选择楼层类型' }]">
            <a-select v-model="formData.layer_type" placeholder="请选择">
              <a-option value="single">单层</a-option>
              <a-option value="multi">多层</a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <!-- 定价结算 -->
      <a-form-item
        v-if="formData.pricing_type === 'fixed'"
        label="单价"
        :rules="[{ required: true, message: '请输入单价' }]"
      >
        <a-input-number
          v-model="formData.unit_price"
          placeholder="请输入单价"
          :min="0"
          :precision="2"
          style="width: 100%"
        >
          <template #prefix>¥</template>
        </a-input-number>
      </a-form-item>

      <!-- 阶梯结算 -->
      <div v-if="formData.pricing_type === 'tiered'" class="tier-editor">
        <div class="tier-editor-header">
          <span class="tier-editor-title">阶梯配置</span>
          <button type="button" class="btn primary tier-add-btn" @click="addTier">
            + 添加阶梯
          </button>
        </div>
        <div v-if="formData.tiers.length === 0" class="tier-empty">
          暂未配置阶梯，点击"添加阶梯"开始设置
        </div>
        <div v-for="(tier, idx) in formData.tiers" :key="idx" class="tier-item">
          <div class="tier-row">
            <div class="tier-field">
              <label class="tier-label">最小用量</label>
              <a-input-number v-model="tier.min" :min="0" :precision="0" style="width: 100%" />
              <button
                v-if="idx > 0"
                type="button"
                class="tier-auto-btn"
                title="自动填充为上一阶梯最大值+1"
                @click="autoFillMin(idx)"
              >
                自动
              </button>
            </div>
            <div class="tier-field">
              <label class="tier-label">最大用量</label>
              <a-input-number
                v-model="tier.max"
                :min="0"
                :precision="0"
                :disabled="tier.unlimited"
                style="width: 100%"
                @change="onTierMaxChange(idx)"
              />
            </div>
            <div class="tier-field tier-price-field">
              <label class="tier-label">单价</label>
              <a-input-number v-model="tier.price" :min="0" :precision="2" style="width: 100%">
                <template #prefix>¥</template>
              </a-input-number>
            </div>
            <div class="tier-field tier-unlimited-field">
              <a-checkbox v-model="tier.unlimited" @change="onTierUnlimitedChange(idx)">
                不限
              </a-checkbox>
            </div>
            <button
              v-if="formData.tiers.length > 1"
              type="button"
              class="tier-remove-btn"
              @click="removeTier(idx)"
            >
              ✕
            </button>
          </div>
          <div v-if="getTierError(idx)" class="tier-error">{{ getTierError(idx) }}</div>
        </div>
      </div>

      <!-- 包年结算 -->
      <a-form-item
        v-if="formData.pricing_type === 'package'"
        label="套餐类型"
        :rules="[{ required: true, message: '请选择套餐类型' }]"
      >
        <a-select v-model="formData.package_type" placeholder="请选择套餐">
          <a-option
            v-for="plan in packagePlanOptions"
            :key="plan.package_type"
            :value="plan.package_type"
          >
            {{ plan.name }} ({{ plan.package_type }})
          </a-option>
        </a-select>
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="生效日期" :rules="[{ required: true, message: '请选择生效日期' }]">
            <a-date-picker v-model="formData.effective_date" style="width: 100%" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="失效日期（可选）">
            <a-date-picker v-model="formData.expiry_date" style="width: 100%" />
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
import * as billingApi from '@/api/billing'

type PricingRule = billingApi.PricingRule

interface Tier {
  min: number
  max: number | null
  price: number
  unlimited: boolean
}

const props = defineProps<{
  visible: boolean
  editData: PricingRule | null
  packagePlanOptions: billingApi.PackagePlan[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  saved: []
}>()

const isEdit = ref(false)
const modalLoading = ref(false)

const formData = reactive({
  id: null as number | null,
  customer_id: undefined as number | undefined,
  customer_name: '' as string,
  device_type: 'X',
  layer_type: 'single' as 'single' | 'multi',
  pricing_type: 'fixed' as 'fixed' | 'tiered' | 'package',
  unit_price: undefined as number | undefined,
  tiers: [] as Tier[],
  package_type: undefined as string | undefined,
  effective_date: undefined as string | undefined,
  expiry_date: undefined as string | undefined,
})

// 监听 visible 变化，初始化表单数据
watch(
  () => props.visible,
  (val) => {
    if (val) {
      if (props.editData) {
        isEdit.value = true
        const record = props.editData
        Object.assign(formData, {
          id: record.id,
          customer_id: record.customer_id,
          customer_name: record.customer_name || '',
          device_type: record.device_type,
          layer_type: record.layer_type || 'single',
          pricing_type: record.pricing_type,
          unit_price: record.unit_price,
          tiers: parseTiers(record.tiers),
          package_type: record.package_type,
          effective_date: record.effective_date,
          expiry_date: record.expiry_date,
        })
      } else {
        isEdit.value = false
        Object.assign(formData, {
          id: null,
          customer_id: undefined,
          customer_name: '',
          device_type: 'X',
          layer_type: 'single',
          pricing_type: 'fixed',
          unit_price: undefined,
          tiers: [],
          package_type: undefined,
          effective_date: undefined,
          expiry_date: undefined,
        })
      }
    }
  }
)

// 解析后端返回的 tiers 数据为编辑器可用的数组
const parseTiers = (raw: unknown): Tier[] => {
  if (!raw) return []
  let arr: Array<{ min?: number; max?: number | null; price?: number }> = []
  if (Array.isArray(raw)) {
    arr = raw as typeof arr
  } else if (typeof raw === 'object' && raw !== null && 'ranges' in raw) {
    arr = (raw as { ranges: typeof arr }).ranges
  }
  return arr.map((t) => ({
    min: Number(t.min) || 0,
    max: t.max == null ? null : Number(t.max),
    price: Number(t.price) || 0,
    unlimited: t.max == null,
  }))
}

// 阶梯编辑器操作
const addTier = () => {
  if (formData.tiers.length > 0) {
    const lastTier = formData.tiers[formData.tiers.length - 1]
    if (lastTier.unlimited) {
      Message.warning('上一阶梯的最大用量为"不限"，无法继续添加阶梯')
      return
    }
    if (lastTier.max == null) {
      Message.warning('请先完善上一阶梯的最大用量')
      return
    }
    const newMin = lastTier.max + 1
    formData.tiers.push({ min: newMin, max: null, price: 0, unlimited: true })
  } else {
    formData.tiers.push({ min: 0, max: null, price: 0, unlimited: true })
  }
}

const removeTier = (idx: number) => {
  formData.tiers.splice(idx, 1)
}

const onTierMaxChange = (idx: number) => {
  if (idx < formData.tiers.length - 1) {
    const currentMax = formData.tiers[idx].max
    if (currentMax != null) {
      formData.tiers[idx + 1].min = currentMax + 1
    }
  }
}

const autoFillMin = (idx: number) => {
  if (idx === 0) return
  const prevMax = formData.tiers[idx - 1].max
  if (prevMax != null) {
    formData.tiers[idx].min = prevMax + 1
  } else {
    Message.warning('上一阶梯尚未设置最大用量')
  }
}

const onTierUnlimitedChange = (idx: number) => {
  if (formData.tiers[idx].unlimited) {
    formData.tiers[idx].max = null
    if (idx < formData.tiers.length - 1) {
      Message.warning('"不限"为最高档，已自动删除后续阶梯')
      formData.tiers.splice(idx + 1)
    }
  } else if (formData.tiers[idx].max === null) {
    formData.tiers[idx].max = 0
  }
}

const getTierError = (idx: number): string => {
  const tier = formData.tiers[idx]
  if (!tier) return ''
  if (idx === 0 && tier.min !== 0) return '首阶梯最小用量必须为 0'
  if (idx > 0) {
    const prevTier = formData.tiers[idx - 1]
    if (prevTier) {
      const prevMax = prevTier.max
      if (prevMax != null && tier.min <= prevMax)
        return `最小用量必须大于上一阶梯最大用量（${prevMax}）`
      if (prevMax != null && tier.min > prevMax + 1)
        return `与上一阶梯存在间隙（${prevMax + 1} ~ ${tier.min - 1} 未覆盖），建议点击「自动」`
    }
  }
  if (!tier.unlimited && tier.max != null && tier.max === tier.min)
    return '最小用量与最大用量不能一致'
  if (!tier.unlimited && tier.max != null && tier.max < tier.min) return '最大用量必须大于最小用量'
  if (tier.unlimited && idx < formData.tiers.length - 1) return '只有最后一阶梯可设为「不限」'
  return ''
}

const onPricingTypeChange = () => {
  formData.tiers = []
  formData.package_type = undefined
  formData.unit_price = undefined
}

const handleSubmit = async () => {
  if (!formData.customer_id) {
    Message.warning('请选择客户')
    return false
  }
  if (!formData.effective_date) {
    Message.warning('请选择生效日期')
    return false
  }

  modalLoading.value = true
  try {
    const conflictRes = await billingApi.checkPricingRuleConflict({
      customer_id: formData.customer_id,
      device_type: formData.device_type,
      layer_type: formData.layer_type,
      effective_date: formData.effective_date,
      expiry_date: formData.expiry_date,
      exclude_id: isEdit.value && formData.id ? formData.id : undefined,
    })

    if (conflictRes.data.has_conflict) {
      const conflictRules = conflictRes.data.conflicting_rules
      const conflictMsg = conflictRules
        .map(
          (r: billingApi.ConflictRule) =>
            `规则ID ${r.id}（${r.pricing_type}）：${r.effective_date} ~ ${r.expiry_date || '永久'}`
        )
        .join('\n')
      Message.error({ content: `有效期冲突，已存在以下规则：\n${conflictMsg}`, duration: 5000 })
      return false
    }

    const submitData: Partial<PricingRule> = {
      customer_id: formData.customer_id,
      device_type: formData.device_type,
      layer_type: formData.layer_type,
      pricing_type: formData.pricing_type,
      effective_date: formData.effective_date,
      expiry_date: formData.expiry_date || null,
    }

    if (formData.pricing_type === 'fixed' && formData.unit_price) {
      submitData.unit_price = formData.unit_price
    } else if (formData.pricing_type === 'tiered') {
      if (formData.tiers.length === 0) {
        Message.warning('请至少添加一条阶梯配置')
        modalLoading.value = false
        return false
      }
      for (let i = 0; i < formData.tiers.length; i++) {
        const t = formData.tiers[i]
        if (t.min == null || t.price == null) {
          Message.warning(`第 ${i + 1} 条阶梯配置不完整`)
          modalLoading.value = false
          return false
        }
        const err = getTierError(i)
        if (err) {
          Message.warning(`第 ${i + 1} 条阶梯：${err}`)
          modalLoading.value = false
          return false
        }
      }
      submitData.tiers = formData.tiers.map((t) => ({
        min: t.min,
        max: t.unlimited ? null : t.max,
        price: t.price,
      }))
    } else if (formData.pricing_type === 'package' && formData.package_type) {
      submitData.package_type = formData.package_type
    }

    if (isEdit.value && formData.id) {
      await billingApi.updatePricingRule(formData.id, submitData)
      Message.success('更新成功')
    } else {
      await billingApi.createPricingRule(submitData)
      Message.success('创建成功')
    }
    emit('saved')
    return true
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '操作失败')
    return false
  } finally {
    modalLoading.value = false
  }
}
</script>

<style scoped>
.tier-editor {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.tier-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.tier-editor-title {
  font-weight: 600;
  font-size: 14px;
  color: #334155;
}

.tier-add-btn {
  font-size: 12px;
  padding: 4px 10px;
}

.tier-empty {
  text-align: center;
  color: #94a3b8;
  padding: 20px;
  font-size: 13px;
}

.tier-item {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px 0;
}

.tier-item:last-child {
  border-bottom: none;
}

.tier-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.tier-field {
  flex: 1;
  position: relative;
}

.tier-label {
  display: block;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.tier-auto-btn {
  position: absolute;
  right: -32px;
  bottom: 0;
  font-size: 11px;
  padding: 2px 6px;
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  color: #64748b;
  cursor: pointer;
  white-space: nowrap;
}

.tier-auto-btn:hover {
  background: #e2e8f0;
}

.tier-price-field {
  flex: 0.8;
}

.tier-unlimited-field {
  flex: 0.5;
  padding-bottom: 6px;
}

.tier-remove-btn {
  flex: 0;
  background: none;
  border: none;
  color: #ef4444;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 8px;
}

.tier-error {
  color: #ef4444;
  font-size: 12px;
  margin-top: 4px;
}

.btn {
  display: inline-block;
  padding: 6px 14px;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 6px;
  background: var(--panel, #fff);
  color: var(--ink, #0f172a);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.btn:hover {
  border-color: var(--primary, #1d4ed8);
  color: var(--primary, #1d4ed8);
}

.btn.primary {
  background: var(--primary, #1d4ed8);
  border-color: var(--primary, #1d4ed8);
  color: #fff;
}

.btn.primary:hover {
  opacity: 0.9;
}
</style>
