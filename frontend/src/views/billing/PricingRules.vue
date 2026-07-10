<template>
  <div class="pricing-rules">
    <AppPageHeader
      title="计价规则"
      description="按客户/设备/楼层维度维护计价规则"
      eyebrow="BILLING"
    >
      <template #actions>
        <a-button v-if="can('billing:edit')" type="primary" @click="showCreateModal">
          <template #icon><icon-plus /></template>新建规则
        </a-button>
      </template>
    </AppPageHeader>

    <FilterPanel>
      <a-form :model="filters" layout="inline" class="filter-form">
        <a-form-item label="客户">
          <CustomerAutoComplete v-model="filters.keyword" placeholder="请输入客户名称/ID" style="width: 220px" />
        </a-form-item>
        <a-form-item label="设备类型">
          <a-select v-model="filters.device_type" placeholder="请选择" allow-clear style="width: 160px">
            <a-option value="X">X光机</a-option>
            <a-option value="CT">CT</a-option>
            <a-option value="MR">MR</a-option>
            <a-option value="DR">DR</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="计费类型">
          <a-select v-model="filters.pricing_type" placeholder="请选择" allow-clear style="width: 160px">
            <a-option value="fixed">定价结算</a-option>
            <a-option value="tiered">阶梯结算</a-option>
            <a-option value="package">包年结算</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="handleSearch">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </FilterPanel>

    <DataSection title="计价规则列表" :count="pagination.total">
      <CompactTableShell>
        <a-table
          :columns="columns"
          :data="data"
          :loading="loading"
          row-key="id"
          :pagination="pagination"
          @page-change="onPageChange"
          @page-size-change="onPageSizeChange"
        >
          <template #customer_name="{ record }">
            <span>{{ record.customer_name || '—' }}</span>
          </template>
          <template #device_type="{ record }">
            <span class="device-badge">{{ record.device_type }}</span>
          </template>
          <template #layer_type="{ record }">
            <span>{{ record.layer_type === 'single' ? '单层' : '多层' }}</span>
          </template>
          <template #pricing_type="{ record }">
            <span class="pricing-badge">{{ getPricingTypeText(record.pricing_type) }}</span>
          </template>
          <template #unit_price="{ record }">
            <span v-if="record.unit_price != null" class="amount">¥{{ record.unit_price }}</span>
            <span v-else>—</span>
          </template>
          <template #package_type="{ record }">
            <span v-if="record.package_type">{{ record.package_type }}</span>
            <span v-else>—</span>
          </template>
          <template #valid_period="{ record }">
            <span v-if="record.effective_date || record.expiry_date">
              {{ record.effective_date ? formatDate(record.effective_date) : '—' }}
              ~
              {{ record.expiry_date ? formatDate(record.expiry_date) : '长期' }}
            </span>
            <span v-else>—</span>
          </template>
          <template #action="{ record }">
            <a-dropdown>
              <template #trigger>
                <a-button size="small" ghost>操作</a-button>
              </template>
              <template #overlay>
                <a-menu @select="key => handleAction(record, key as string)">
                  <a-menu-item key="edit">编辑</a-menu-item>
                  <a-menu-item key="delete">删除</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </template>
        </a-table>
      </CompactTableShell>
    </DataSection>

    <a-modal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :confirm-loading="modalLoading"
      width="600px"
      @before-ok="handleSubmit"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item label="客户" required>
          <CustomerAutoComplete v-model="formData.customer_id" placeholder="请选择客户" style="width: 100%" />
        </a-form-item>
        <a-form-item label="设备类型" required>
          <a-select v-model="formData.device_type" placeholder="请选择" style="width: 100%">
            <a-option value="X">X光机</a-option>
            <a-option value="CT">CT</a-option>
            <a-option value="MR">MR</a-option>
            <a-option value="DR">DR</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="楼层类型" required>
          <a-radio-group v-model="formData.layer_type">
            <a-radio value="single">单层</a-radio>
            <a-radio value="multi">多层</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="计费类型" required>
          <a-select v-model="formData.pricing_type" placeholder="请选择" style="width: 100%" @change="onPricingTypeChange">
            <a-option value="fixed">定价结算</a-option>
            <a-option value="tiered">阶梯结算</a-option>
            <a-option value="package">包年结算</a-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="formData.pricing_type === 'fixed'" label="单价" required>
          <a-input-number v-model="formData.unit_price" :min="0" :precision="2" style="width: 100%" />
        </a-form-item>
        <a-form-item v-if="formData.pricing_type === 'tiered'" label="阶梯配置 (JSON)">
          <a-textarea v-model="formData.tiersJson" :rows="4" placeholder='[{"min": 0, "max": 100, "price": 10}, {"min": 101, "max": null, "price": 8}]' style="width: 100%" />
        </a-form-item>
        <a-form-item v-if="formData.pricing_type === 'package'" label="套餐类型">
          <a-select v-model="formData.package_type" placeholder="请选择" style="width: 100%">
            <a-option value="basic">基础套餐</a-option>
            <a-option value="standard">标准套餐</a-option>
            <a-option value="premium">高级套餐</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="生效日期" required>
          <a-date-picker v-model="formData.effective_date" style="width: 100%" />
        </a-form-item>
        <a-form-item label="失效日期">
          <a-date-picker v-model="formData.expiry_date" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconPlus } from '@arco-design/web-vue/es/icon'
import { useUserStore } from '@/stores/user'
import * as billingApi from '@/api/billing'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
import { formatDate } from '@/utils/formatters'

import {
  AppPageHeader,
  FilterPanel,
  DataSection,
  CompactTableShell,
} from '@/components/dashboard'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

interface PricingRule {
  id: number
  customer_id?: number
  customer_name?: string
  device_type: string
  layer_type?: string
  pricing_type: 'fixed' | 'tiered' | 'package'
  unit_price?: number
  tiers?: Record<string, unknown>
  package_type?: string
  effective_date?: string
  expiry_date?: string
}

const columns = [
  { title: '客户', dataIndex: 'customer_name', slotName: 'customer_name', width: 200 },
  { title: '设备类型', dataIndex: 'device_type', slotName: 'device_type', width: 100 },
  { title: '楼层类型', dataIndex: 'layer_type', slotName: 'layer_type', width: 100 },
  { title: '计费类型', dataIndex: 'pricing_type', slotName: 'pricing_type', width: 120 },
  { title: '单价', dataIndex: 'unit_price', slotName: 'unit_price', width: 100 },
  { title: '套餐类型', dataIndex: 'package_type', slotName: 'package_type', width: 100 },
  { title: '有效期', slotName: 'valid_period', width: 200 },
  { title: '操作', slotName: 'action', width: 150, fixed: 'right' as const },
]

const data = ref<PricingRule[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const filters = reactive({
  keyword: '',
  device_type: undefined as string | undefined,
  pricing_type: undefined as string | undefined,
})

const modalVisible = ref(false)
const modalTitle = ref('新建规则')
const modalLoading = ref(false)
const isEdit = ref(false)

const formData = reactive({
  id: null as number | null,
  customer_id: undefined as number | undefined,
  device_type: 'X',
  layer_type: 'single' as 'single' | 'multi',
  pricing_type: 'fixed' as 'fixed' | 'tiered' | 'package',
  unit_price: undefined as number | undefined,
  tiersJson: '',
  package_type: undefined as string | undefined,
  effective_date: undefined as string | undefined,
  expiry_date: undefined as string | undefined,
})

const getPricingTypeText = (type: string) => {
  const map: Record<string, string> = {
    fixed: '定价结算',
    tiered: '阶梯结算',
    package: '包年结算',
  }
  return map[type] || type
}

const fetchData = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.device_type) params.device_type = filters.device_type
    if (filters.pricing_type) params.pricing_type = filters.pricing_type

    const res = await billingApi.getPricingRules(params)
    data.value = res.data.list || []
    pagination.total = res.data.total || data.value.length
    pagination.pageSize = res.data.page_size || pagination.pageSize
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchData()
}

const handleReset = () => {
  filters.keyword = ''
  filters.device_type = undefined
  filters.pricing_type = undefined
  pagination.current = 1
  fetchData()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchData()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchData()
}

const showCreateModal = () => {
  isEdit.value = false
  modalTitle.value = '新建规则'
  Object.assign(formData, {
    id: null,
    customer_id: undefined,
    device_type: 'X',
    layer_type: 'single',
    pricing_type: 'fixed',
    unit_price: undefined,
    tiersJson: '',
    package_type: undefined,
    effective_date: undefined,
    expiry_date: undefined,
  })
  modalVisible.value = true
}

const showEditModal = (record: PricingRule) => {
  isEdit.value = true
  modalTitle.value = '编辑规则'
  Object.assign(formData, {
    id: record.id,
    customer_id: record.customer_id,
    device_type: record.device_type,
    layer_type: record.layer_type || 'single',
    pricing_type: record.pricing_type,
    unit_price: record.unit_price,
    tiersJson: record.tiers ? JSON.stringify(record.tiers) : '',
    package_type: record.package_type,
    effective_date: record.effective_date,
    expiry_date: record.expiry_date,
  })
  modalVisible.value = true
}

const onPricingTypeChange = () => {
  formData.tiersJson = ''
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
  if (formData.pricing_type === 'fixed' && formData.unit_price == null) {
    Message.warning('请输入单价')
    return false
  }
  if (formData.pricing_type === 'tiered' && !formData.tiersJson.trim()) {
    Message.warning('请输入阶梯配置')
    return false
  }
  if (formData.pricing_type === 'package' && !formData.package_type) {
    Message.warning('请选择套餐类型')
    return false
  }

  modalLoading.value = true
  try {
    let tiers: Record<string, unknown> | undefined
    if (formData.pricing_type === 'tiered') {
      try {
        tiers = JSON.parse(formData.tiersJson)
      } catch {
        Message.warning('阶梯配置 JSON 格式错误')
        return false
      }
    }

    const payload = {
      customer_id: formData.customer_id,
      device_type: formData.device_type,
      layer_type: formData.layer_type,
      pricing_type: formData.pricing_type,
      unit_price: formData.unit_price,
      tiers,
      package_type: formData.package_type,
      effective_date: formData.effective_date,
      expiry_date: formData.expiry_date,
    }

    if (isEdit.value && formData.id) {
      await billingApi.updatePricingRule(formData.id, payload)
      Message.success('更新成功')
    } else {
      await billingApi.createPricingRule(payload)
      Message.success('创建成功')
    }
    modalVisible.value = false
    fetchData()
  } catch (err: unknown) {
    Message.error((err as Error)?.message || (isEdit.value ? '更新失败' : '创建失败'))
    return false
  } finally {
    modalLoading.value = false
  }
}

const handleAction = (record: PricingRule, action: string) => {
  if (action === 'edit') {
    showEditModal(record)
  } else if (action === 'delete') {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该计价规则吗？此操作不可恢复。',
      onOk: async () => {
        try {
          await billingApi.deletePricingRule(record.id)
          Message.success('删除成功')
          fetchData()
        } catch (err: unknown) {
          Message.error((err as Error)?.message || '删除失败')
        }
      },
    })
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.pricing-rules {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-form {
  margin-bottom: 0;
}

.device-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: var(--cop-primary-bg);
  color: var(--cop-primary);
}

.pricing-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: var(--cop-bg);
  color: var(--cop-ink);
}

.amount {
  font-weight: 600;
  color: var(--cop-ink);
}
</style>