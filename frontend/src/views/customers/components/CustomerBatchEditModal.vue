<template>
    <!-- 批量编辑对话框 -->
    <a-modal
      v-model:visible="isVisible"
      :title="`批量编辑（已选择 ${selectedCustomerIds.length} 个客户）`"
      width="600px"
      :mask-closable="false"
      @cancel="closeBatchEditDialog"
    >
      <a-form :model="batchForm" layout="vertical">
        <div class="batch-form-grid">
          <!-- 1. 运营经理 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.manager_id">运营经理</a-checkbox>
            <a-select
              v-model="batchForm.manager_id"
              :disabled="!batchFieldsSelected.manager_id"
              placeholder="选择运营经理"
              allow-clear
            >
              <a-option v-for="m in managers" :key="m.id" :value="m.id" :label="m.real_name || m.username" />
            </a-select>
          </div>

          <!-- 2. 商务经理 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.sales_manager_id">商务经理</a-checkbox>
            <a-select
              v-model="batchForm.sales_manager_id"
              :disabled="!batchFieldsSelected.sales_manager_id"
              placeholder="选择商务经理"
              allow-clear
            >
              <a-option v-for="m in managers" :key="m.id" :value="m.id" :label="m.real_name || m.username" />
            </a-select>
          </div>

          <!-- 3. 合作状态 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.cooperation_status">合作状态</a-checkbox>
            <a-select
              v-model="batchForm.cooperation_status"
              :disabled="!batchFieldsSelected.cooperation_status"
              placeholder="选择合作状态"
              allow-clear
            >
              <a-option value="active">合作中</a-option>
              <a-option value="inactive">暂停合作</a-option>
              <a-option value="terminated">已终止</a-option>
            </a-select>
          </div>

          <!-- 4. 重点客户 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.is_key_customer">重点客户</a-checkbox>
            <a-switch
              v-model="batchForm.is_key_customer"
              :disabled="!batchFieldsSelected.is_key_customer"
              type="round"
            >
              <template #checked>是</template>
              <template #unchecked>否</template>
            </a-switch>
          </div>

          <!-- 5. 房产客户（三态 select）-->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.is_real_estate">房产客户</a-checkbox>
            <a-select
              v-model="batchForm.is_real_estate"
              :disabled="!batchFieldsSelected.is_real_estate"
              placeholder="选择"
              allow-clear
            >
              <a-option :value="true">是</a-option>
              <a-option :value="false">否</a-option>
            </a-select>
          </div>

          <!-- 6. 结算方式 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.settlement_type">结算方式</a-checkbox>
            <a-select
              v-model="batchForm.settlement_type"
              :disabled="!batchFieldsSelected.settlement_type"
              placeholder="选择结算方式"
              allow-clear
            >
              <a-option value="prepaid">预付费</a-option>
              <a-option value="postpaid">后付费</a-option>
            </a-select>
          </div>

          <!-- 7. 结算周期 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.settlement_cycle">结算周期</a-checkbox>
            <a-select
              v-model="batchForm.settlement_cycle"
              :disabled="!batchFieldsSelected.settlement_cycle"
              placeholder="选择结算周期"
              allow-clear
            >
              <a-option value="monthly">月结</a-option>
              <a-option value="quarterly">季结</a-option>
              <a-option value="yearly">年结</a-option>
            </a-select>
          </div>

          <!-- 8. 是否启用结算 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.is_settlement_enabled">是否启用结算</a-checkbox>
            <a-switch
              v-model="batchForm.is_settlement_enabled"
              :disabled="!batchFieldsSelected.is_settlement_enabled"
              type="round"
            >
              <template #checked>启用</template>
              <template #unchecked>停用</template>
            </a-switch>
          </div>

          <!-- 9. 停用 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.is_disabled">停用</a-checkbox>
            <a-switch
              v-model="batchForm.is_disabled"
              :disabled="!batchFieldsSelected.is_disabled"
              type="round"
            >
              <template #checked>已停用</template>
              <template #unchecked>正常</template>
            </a-switch>
          </div>

          <!-- 10. 账号类型 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.account_type">账号类型</a-checkbox>
            <a-select
              v-model="batchForm.account_type"
              :disabled="!batchFieldsSelected.account_type"
              placeholder="选择账号类型"
              allow-clear
            >
              <a-option value="正式账号">正式账号</a-option>
              <a-option value="测试账号">测试账号</a-option>
              <a-option value="客户测试账号">客户测试账号</a-option>
              <a-option value="内部账号">内部账号</a-option>
            </a-select>
          </div>

          <!-- 11. 计费策略 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.price_policy">计费策略</a-checkbox>
            <a-select
              v-model="batchForm.price_policy"
              :disabled="!batchFieldsSelected.price_policy"
              placeholder="选择计费策略"
              allow-clear
            >
              <a-option value="pricing">定价</a-option>
              <a-option value="tiered">阶梯</a-option>
              <a-option value="yearly">包年</a-option>
            </a-select>
          </div>

          <!-- 12. 规模等级 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.scale_level">规模等级</a-checkbox>
            <a-select
              v-model="batchForm.scale_level"
              :disabled="!batchFieldsSelected.scale_level"
              placeholder="选择规模等级"
              allow-clear
            >
              <a-option value="S">S - 超大规模 (5000 人)</a-option>
              <a-option value="A">A - 大规模 (2000 人)</a-option>
              <a-option value="B">B - 中大规模 (1000 人)</a-option>
              <a-option value="C">C - 中等规模 (500 人)</a-option>
              <a-option value="D">D - 小规模 (100 人)</a-option>
              <a-option value="E">E - 微型 (&lt;100 人)</a-option>
            </a-select>
          </div>

          <!-- 13. 消费等级 -->
          <div class="batch-field-item">
            <a-checkbox v-model="batchFieldsSelected.consume_level">消费等级</a-checkbox>
            <a-select
              v-model="batchForm.consume_level"
              :disabled="!batchFieldsSelected.consume_level"
              placeholder="选择消费等级"
              allow-clear
            >
              <a-option value="C1">C1 - 100 万</a-option>
              <a-option value="C2">C2 - 50 万</a-option>
              <a-option value="C3">C3 - 25 万</a-option>
              <a-option value="C4">C4 - 12 万</a-option>
              <a-option value="C5">C5 - 6 万</a-option>
              <a-option value="C6">C6 - 6 万以下</a-option>
            </a-select>
          </div>
        </div>
      </a-form>

      <template #footer>
        <a-space>
          <a-button @click="closeBatchEditDialog">取消</a-button>
          <a-button @click="showPreviewDialog">预览</a-button>
          <a-button type="primary" @click="handleBatchSubmit">提交</a-button>
        </a-space>
      </template>
    </a-modal>

    <!-- 预览确认对话框 -->
    <a-modal
      v-model:visible="batchPreviewVisible"
      title="确认批量修改"
      width="500px"
      @ok="confirmBatchSubmit"
      @cancel="batchPreviewVisible = false"
    >
      <p>即将修改 <strong>{{ selectedCustomerIds.length }}</strong> 个客户的以下字段：</p>
      <a-table :columns="previewColumns" :data="previewRows" :pagination="false" size="small" />
    </a-modal>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'
import { batchUpdateCustomers } from '@/api/customers'

interface BatchFailedItem {
  customer_id: number
  reason: string
}

const props = defineProps<{
  visible: boolean
  selectedCustomerIds: number[]
  managers: Array<Record<string, unknown>>
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'submitted'): void
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const batchPreviewVisible = ref(false)

const batchForm = reactive({
  manager_id: null as number | null,
  sales_manager_id: null as number | null,
  cooperation_status: '',
  is_key_customer: false,
  is_real_estate: null as boolean | null,
  settlement_type: '',
  settlement_cycle: '',
  is_settlement_enabled: false,
  is_disabled: false,
  account_type: '',
  price_policy: '',
  scale_level: null as string | null,
  consume_level: null as string | null,
})

const batchFieldsSelected = reactive({
  manager_id: false,
  sales_manager_id: false,
  cooperation_status: false,
  is_key_customer: false,
  is_real_estate: false,
  settlement_type: false,
  settlement_cycle: false,
  is_settlement_enabled: false,
  is_disabled: false,
  account_type: false,
  price_policy: false,
  scale_level: false,
  consume_level: false,
})

const fieldNames: Record<string, string> = {
  manager_id: '运营经理',
  sales_manager_id: '商务经理',
  cooperation_status: '合作状态',
  is_key_customer: '重点客户',
  is_real_estate: '房产客户',
  settlement_type: '结算方式',
  settlement_cycle: '结算周期',
  is_settlement_enabled: '是否启用结算',
  is_disabled: '停用',
  account_type: '账号类型',
  price_policy: '计费策略',
  scale_level: '规模等级',
  consume_level: '消费等级',
}

const selectedFields = computed(() => {
  return Object.keys(batchFieldsSelected).filter(k => (batchFieldsSelected as Record<string, boolean>)[k])
})

const previewColumns = [
  { title: '字段名', dataIndex: 'fieldName' },
  { title: '修改后值', dataIndex: 'newValue' },
]

const previewRows = computed(() => {
  const rows: { fieldName: string; newValue: string }[] = []
  for (const [key, selected] of Object.entries(batchFieldsSelected)) {
    if (selected) {
      const value = (batchForm as Record<string, unknown>)[key]
      if (value === null || value === '') continue
      let displayValue = String(value)
      if (typeof value === 'boolean') {
        displayValue = value ? '是' : '否'
      }
      rows.push({ fieldName: fieldNames[key] || key, newValue: displayValue })
    }
  }
  return rows
})

const showPreviewDialog = () => {
  if (!selectedFields.value.length) {
    Message.warning('请至少勾选一个字段')
    return
  }
  const fields: Record<string, unknown> = {}
  for (const [key, selected] of Object.entries(batchFieldsSelected)) {
    if (selected) {
      fields[key] = (batchForm as Record<string, unknown>)[key]
    }
  }
  if (Object.keys(fields).length === 0) {
    Message.warning('请至少选择一个已勾选字段的值')
    return
  }
  batchPreviewVisible.value = true
}

const closeBatchEditDialog = () => {
  emit('update:visible', false)
}

const submitBatchUpdate = async (fields: Record<string, unknown>) => {
  try {
    const result = await batchUpdateCustomers(props.selectedCustomerIds, fields)

    const data = result.data

    if (data.failed_count === 0) {
      Message.success(`批量编辑成功，共修改 ${data.success_count} 个客户`)
    } else if (data.success_count > 0) {
      Message.warning(
        `批量编辑完成：成功 ${data.success_count} 个，失败 ${data.failed_count} 个`
      )
      if (data.failed_list && data.failed_list.length > 0) {
        const details = data.failed_list.slice(0, 5).map(
          (item: BatchFailedItem) => `客户 ${item.customer_id}: ${item.reason}`
        ).join('\n')
        Modal.warning({
          title: '部分客户编辑失败',
          content: details + (data.failed_list.length > 5 ? '\n...' : ''),
        })
      }
    } else {
      Message.error(`批量编辑失败，全部 ${data.failed_count} 个客户编辑失败`)
    }

    emit('update:visible', false)
    emit('submitted')
  } catch (error: unknown) {
    handleError(error, '批量编辑失败')
  }
}

const handleBatchSubmit = () => {
  showPreviewDialog()
}

const confirmBatchSubmit = () => {
  const fields: Record<string, unknown> = {}
  for (const [key, selected] of Object.entries(batchFieldsSelected)) {
    if (selected) {
      fields[key] = (batchForm as Record<string, unknown>)[key]
    }
  }
  submitBatchUpdate(fields)
}

// Reset form when dialog opens
const resetForm = () => {
  batchForm.manager_id = null
  batchForm.sales_manager_id = null
  batchForm.cooperation_status = ''
  batchForm.is_key_customer = false
  batchForm.is_real_estate = null
  batchForm.settlement_type = ''
  batchForm.settlement_cycle = ''
  batchForm.is_settlement_enabled = false
  batchForm.is_disabled = false
  batchForm.account_type = ''
  batchForm.price_policy = ''
  batchForm.scale_level = null
  batchForm.consume_level = null

  Object.keys(batchFieldsSelected).forEach(k => {
    (batchFieldsSelected as Record<string, boolean>)[k] = false
  })
}

defineExpose({ resetForm })
</script>
