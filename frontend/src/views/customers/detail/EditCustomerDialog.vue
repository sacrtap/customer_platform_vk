<template>
  <a-modal
    :visible="visible"
    title="编辑客户"
    :width="modalWidth"
    :confirm-loading="editLoading"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="editFormRef"
      :model="editForm"
      :rules="editFormRules"
      layout="vertical"
      validate-trigger="['blur', 'change']"
    >
      <div class="edit-form-grid">
        <!-- 第一列：基础信息 -->
        <div class="edit-form-column">
          <div class="column-title">基础信息</div>
          <a-form-item field="name" label="客户名称" required>
            <a-input v-model="editForm.name" placeholder="请输入客户名称" />
          </a-form-item>
          <a-form-item field="company_id" label="公司 ID" required>
            <a-input v-model="editForm.company_id" placeholder="请输入公司 ID" />
          </a-form-item>
          <a-form-item field="account_type" label="账号类型">
            <a-select v-model="editForm.account_type" placeholder="请选择账号类型" allow-clear>
              <a-option value="正式账号">正式账号</a-option>
              <a-option value="测试账号">测试账号</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="industry_type_id" label="行业类型">
            <a-select
              v-model="editForm.industry_type_id"
              placeholder="请选择行业类型"
              allow-clear
              :loading="industryTypesLoading"
            >
              <a-option v-for="type in industryTypes" :key="type.id" :value="type.id">
                {{ type.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="manager_id" label="客户经理">
            <a-select v-model="editForm.manager_id" placeholder="请选择客户经理" allow-clear>
              <a-option v-for="m in managers" :key="m.id" :value="m.id">
                {{ m.real_name || m.username }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="sales_manager_id" label="销售">
            <a-select v-model="editForm.sales_manager_id" placeholder="请选择销售" allow-clear>
              <a-option v-for="m in managers" :key="m.id" :value="m.id">
                {{ m.real_name || m.username }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="is_real_estate" label="是否房产客户">
            <a-select v-model="editForm.is_real_estate" placeholder="请选择" allow-clear>
              <a-option :value="true">是</a-option>
              <a-option :value="false">否</a-option>
            </a-select>
          </a-form-item>
        </div>
        <!-- 第二列：结算与业务 -->
        <div class="edit-form-column">
          <div class="column-title">结算与业务</div>
          <a-form-item field="settlement_type" label="结算方式" required>
            <a-select v-model="editForm.settlement_type" placeholder="请选择结算方式">
              <a-option value="prepaid">预付费</a-option>
              <a-option value="postpaid">后付费</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="settlement_cycle" label="结算周期">
            <a-select v-model="editForm.settlement_cycle" placeholder="请选择结算周期" allow-clear>
              <a-option value="daily">日结</a-option>
              <a-option value="weekly">周结</a-option>
              <a-option value="monthly">月结</a-option>
              <a-option value="quarterly">季结</a-option>
              <a-option value="yearly">年结</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="cooperation_status" label="合作状态">
            <a-select v-model="editForm.cooperation_status" placeholder="请选择合作状态" allow-clear>
              <a-option value="active">合作中</a-option>
              <a-option value="suspended">暂停</a-option>
              <a-option value="terminated">终止</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="price_policy" label="价格策略">
            <a-select v-model="editForm.price_policy" placeholder="请选择价格策略" allow-clear>
              <a-option v-for="opt in pricePolicyOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="erp_system" label="ERP 系统">
            <a-select v-model="editForm.erp_system" placeholder="请选择 ERP 系统" allow-clear>
              <a-option value="SAP">SAP</a-option>
              <a-option value="Oracle">Oracle</a-option>
              <a-option value="用友">用友</a-option>
              <a-option value="金蝶">金蝶</a-option>
              <a-option value="自研">自研</a-option>
            </a-select>
          </a-form-item>
        </div>
        <!-- 第三列：等级与消费 -->
        <div class="edit-form-column">
          <div class="column-title">等级与消费</div>
          <a-form-item field="scale_level" label="规模等级">
            <a-select v-model="editForm.scale_level" placeholder="请选择规模等级" allow-clear>
              <a-option value="S1">S1</a-option>
              <a-option value="S2">S2</a-option>
              <a-option value="S3">S3</a-option>
              <a-option value="S4">S4</a-option>
              <a-option value="S5">S5</a-option>
              <a-option value="S6">S6</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="consume_level" label="消费等级">
            <a-select v-model="editForm.consume_level" placeholder="请选择消费等级" allow-clear>
              <a-option value="C1">C1</a-option>
              <a-option value="C2">C2</a-option>
              <a-option value="C3">C3</a-option>
              <a-option value="C4">C4</a-option>
              <a-option value="C5">C5</a-option>
              <a-option value="C6">C6</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="first_payment_date" label="首次回款时间">
            <a-date-picker
              v-model="editForm.first_payment_date"
              placeholder="请选择首次回款时间"
              style="width: 100%"
              allow-clear
              value-format="YYYY-MM-DD"
            />
          </a-form-item>
          <a-form-item field="onboarding_date" label="接入时间">
            <a-date-picker
              v-model="editForm.onboarding_date"
              placeholder="请选择接入时间"
              style="width: 100%"
              allow-clear
              value-format="YYYY-MM-DD"
            />
          </a-form-item>
          <a-form-item field="is_key_customer" label="重点客户">
            <a-switch v-model="editForm.is_key_customer" />
          </a-form-item>
          <a-form-item field="is_settlement_enabled" label="是否结算">
            <a-switch v-model="editForm.is_settlement_enabled" />
          </a-form-item>
          <a-form-item field="is_disabled" label="是否停用">
            <a-switch v-model="editForm.is_disabled" />
          </a-form-item>
        </div>
        <div class="edit-form-note">
          <a-form-item field="notes" label="备注">
            <a-textarea
              v-model="editForm.notes"
              placeholder="请输入备注"
              :max-length="500"
              show-word-limit
              allow-clear
            />
          </a-form-item>
        </div>
      </div>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { FormInstance } from '@arco-design/web-vue'
import type { Customer, IndustryType, User } from '@/types'
import type { EditForm } from '@/composables/useCustomerDetail'

const props = defineProps<{
  visible: boolean
  customer: Customer
  editLoading: boolean
  modalWidth: string
  industryTypes: IndustryType[]
  industryTypesLoading: boolean
  managers: User[]
  pricePolicyOptions: { label: string; value: string }[]
}>()

const emit = defineEmits<{
  submit: [form: EditForm]
  close: []
}>()

const editFormRef = ref<FormInstance>()

const editForm = reactive<EditForm>({
  name: '',
  company_id: 0,
  email: '',
  account_type: undefined,
  industry_type_id: null,
  price_policy: undefined,
  settlement_type: undefined,
  settlement_cycle: undefined,
  is_key_customer: false,
  manager_id: undefined,
  erp_system: undefined,
  first_payment_date: undefined,
  onboarding_date: undefined,
  sales_manager_id: undefined,
  cooperation_status: undefined,
  is_settlement_enabled: true,
  is_disabled: false,
  notes: undefined,
  is_real_estate: null,
  scale_level: undefined,
  consume_level: undefined,
})

const editFormRules = {
  name: [{ required: true, message: '请输入客户名称' }],
  company_id: [{ required: true, message: '请输入公司 ID' }],
  settlement_type: [{ required: true, message: '请选择结算方式' }],
}

const initForm = () => {
  Object.assign(editForm, {
    name: props.customer?.name || '',
    company_id: Number(props.customer?.company_id) || 0,
    email: props.customer?.email || '',
    account_type: props.customer?.account_type || undefined,
    industry_type_id: props.customer?.industry_type_id ?? null,
    price_policy: props.customer?.price_policy || undefined,
    settlement_type: props.customer?.settlement_type || undefined,
    settlement_cycle: props.customer?.settlement_cycle || undefined,
    is_key_customer: props.customer?.is_key_customer || false,
    manager_id: props.customer?.manager_id || undefined,
    erp_system: props.customer?.erp_system || undefined,
    first_payment_date: props.customer?.first_payment_date || undefined,
    onboarding_date: props.customer?.onboarding_date || undefined,
    sales_manager_id: props.customer?.sales_manager_id || undefined,
    cooperation_status: props.customer?.cooperation_status || undefined,
    is_settlement_enabled: props.customer?.is_settlement_enabled ?? true,
    is_disabled: props.customer?.is_disabled ?? false,
    notes: props.customer?.notes || undefined,
    is_real_estate: props.customer?.is_real_estate ?? null,
    scale_level: props.customer?.scale_level || undefined,
    consume_level: props.customer?.consume_level || undefined,
  })
}

const handleSubmit = async () => {
  try {
    await editFormRef.value?.validate()
    emit('submit', { ...editForm })
  } catch {
    // validation failed
  }
}

const handleCancel = () => {
  editFormRef.value?.resetFields()
  emit('close')
}

if (props.customer) {
  initForm()
}
</script>

<style scoped>
.edit-form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.edit-form-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.column-title {
  font-weight: 600;
  color: var(--color-text-1);
  margin-bottom: 8px;
  font-size: 14px;
}

.edit-form-note {
  grid-column: 1 / -1;
}

@media (max-width: 1200px) {
  .edit-form-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .edit-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
