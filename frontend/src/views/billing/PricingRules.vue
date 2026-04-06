<template>
  <div class="pricing-rules">
    <a-card>
      <template #title>
        <a-space>
          <span>定价规则</span>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><icon-plus /></template>
            新建规则
          </a-button>
        </a-space>
      </template>

      <!-- 筛选区域 -->
      <a-form :model="filters" layout="inline" class="filter-form">
        <a-form-item label="客户">
          <a-select
            v-model="filters.customer_id"
            placeholder="请选择客户"
            style="width: 200px"
            allow-clear
            :loading="customersLoading"
          >
            <a-option
              v-for="customer in customers"
              :key="customer.id"
              :value="customer.id"
              :label="customer.name"
            />
          </a-select>
        </a-form-item>
        <a-form-item label="设备类型">
          <a-select
            v-model="filters.device_type"
            placeholder="请选择"
            style="width: 150px"
            allow-clear
          >
            <a-option value="X">X 系列</a-option>
            <a-option value="N">N 系列</a-option>
            <a-option value="L">L 系列</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="计费类型">
          <a-select
            v-model="filters.pricing_type"
            placeholder="请选择"
            style="width: 150px"
            allow-clear
          >
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

      <!-- 表格 -->
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
          <span>{{ record.customer_name || `客户${record.customer_id}` }}</span>
        </template>
        <template #device_type="{ record }">
          <a-tag
            :color="
              record.device_type === 'X'
                ? 'arcoblue'
                : record.device_type === 'N'
                  ? 'green'
                  : 'orange'
            "
          >
            {{ record.device_type }}系列
          </a-tag>
        </template>
        <template #pricing_type="{ record }">
          <a-tag
            :color="
              record.pricing_type === 'fixed'
                ? 'blue'
                : record.pricing_type === 'tiered'
                  ? 'green'
                  : 'orange'
            "
          >
            {{ getPricingTypeText(record.pricing_type) }}
          </a-tag>
        </template>
        <template #unit_price="{ record }">
          <span v-if="record.unit_price">¥{{ record.unit_price.toFixed(2) }}</span>
          <span v-else>-</span>
        </template>
        <template #valid_period="{ record }">
          <span v-if="record.effective_date && record.expiry_date">
            {{ record.effective_date }} 至 {{ record.expiry_date }}
          </span>
          <span v-else-if="record.effective_date"> {{ record.effective_date }} 起 </span>
          <span v-else>-</span>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="showEditModal(record)">编辑</a-button>
            <a-popconfirm content="确定要删除此定价规则吗？" @ok="handleDelete(record)">
              <a-button type="text" size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 创建/编辑规则弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :confirm-loading="modalLoading"
      width="600px"
      @ok="handleSubmit"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item label="客户" :rules="[{ required: true, message: '请选择客户' }]">
          <a-select
            v-model="formData.customer_id"
            placeholder="请选择客户"
            :loading="customersLoading"
          >
            <a-option
              v-for="customer in customers"
              :key="customer.id"
              :value="customer.id"
              :label="customer.name"
            />
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
        <a-form-item v-if="formData.pricing_type === 'tiered'" label="阶梯配置">
          <a-alert type="info" style="margin-bottom: 12px">
            阶梯配置需要通过 JSON
            格式输入，例如：[{"min":0,"max":100,"price":10},{"min":101,"max":500,"price":8}]
          </a-alert>
          <a-textarea
            v-model="formData.tiersJson"
            placeholder='例如：[{"min":0,"max":100,"price":10},{"min":101,"max":500,"price":8}]'
            :rows="4"
          />
        </a-form-item>

        <!-- 包年结算 -->
        <a-form-item
          v-if="formData.pricing_type === 'package'"
          label="套餐类型"
          :rules="[{ required: true, message: '请选择套餐类型' }]"
        >
          <a-select v-model="formData.package_type" placeholder="请选择">
            <a-option value="A">A 套餐</a-option>
            <a-option value="B">B 套餐</a-option>
            <a-option value="C">C 套餐</a-option>
            <a-option value="D">D 套餐</a-option>
          </a-select>
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="生效日期" :rules="[{ required: true, message: '请选择生效日期' }]">
              <a-date-picker v-model="formData.effective_date" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="失效日期">
              <a-date-picker v-model="formData.expiry_date" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus } from '@arco-design/web-vue/es/icon'
import * as billingApi from '@/api/billing'
import { getCustomers } from '@/api/customers'

interface PricingRule {
  id: number
  customer_id?: number
  customer_name?: string
  device_type: string
  pricing_type: 'fixed' | 'tiered' | 'package'
  unit_price?: number
  tiers?: Record<string, unknown>
  package_type?: string
  package_limits?: Record<string, unknown>
  effective_date?: string
  expiry_date?: string
}

const columns = [
  { title: '客户', dataIndex: 'customer_name', slotName: 'customer_name', width: 200 },
  { title: '设备类型', dataIndex: 'device_type', slotName: 'device_type', width: 120 },
  { title: '计费类型', dataIndex: 'pricing_type', slotName: 'pricing_type', width: 120 },
  { title: '单价', dataIndex: 'unit_price', slotName: 'unit_price', width: 100 },
  { title: '套餐类型', dataIndex: 'package_type', width: 100 },
  { title: '有效期', slotName: 'valid_period', width: 200 },
  { title: '操作', slotName: 'action', width: 150, fixed: 'right' },
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
  customer_id: undefined as number | undefined,
  device_type: undefined as string | undefined,
  pricing_type: undefined as string | undefined,
})

const modalVisible = ref(false)
const modalTitle = ref('新建规则')
const modalLoading = ref(false)
const isEdit = ref(false)

const formData = reactive({
  id: null as number | null,
  customer_id: null as number | null,
  device_type: 'X',
  pricing_type: 'fixed' as 'fixed' | 'tiered' | 'package',
  unit_price: undefined as number | undefined,
  tiersJson: '',
  package_type: undefined as string | undefined,
  effective_date: undefined as string | undefined,
  expiry_date: undefined as string | undefined,
})

const customers = ref<{ id: number; name: string }[]>([])
const customersLoading = ref(false)

const getPricingTypeText = (type: string) => {
  const map: Record<string, string> = {
    fixed: '定价结算',
    tiered: '阶梯结算',
    package: '包年结算',
  }
  return map[type] || type
}

const loadCustomers = async () => {
  customersLoading.value = true
  try {
    const res = await getCustomers({ page_size: 1000 })
    customers.value = res.data.list || []
  } catch (err: unknown) {
    Message.error('加载客户列表失败')
  } finally {
    customersLoading.value = false
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = {}
    if (filters.customer_id) params.customer_id = filters.customer_id
    if (filters.device_type) params.device_type = filters.device_type
    if (filters.pricing_type) params.pricing_type = filters.pricing_type

    const res = await billingApi.getPricingRules(params)
    data.value = res.data || []
    pagination.total = data.value.length
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  fetchData()
}

const handleReset = () => {
  filters.customer_id = undefined
  filters.device_type = undefined
  filters.pricing_type = undefined
  fetchData()
}

const onPageChange = (page: number) => {
  pagination.current = page
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
}

const showCreateModal = () => {
  isEdit.value = false
  modalTitle.value = '新建规则'
  Object.assign(formData, {
    id: null,
    customer_id: null,
    device_type: 'X',
    pricing_type: 'fixed',
    unit_price: undefined,
    tiersJson: '',
    package_type: undefined,
    effective_date: undefined,
    expiry_date: undefined,
  })
  modalVisible.value = true
  loadCustomers()
}

const showEditModal = (record: PricingRule) => {
  isEdit.value = true
  modalTitle.value = '编辑规则'
  Object.assign(formData, {
    id: record.id,
    customer_id: record.customer_id,
    device_type: record.device_type,
    pricing_type: record.pricing_type,
    unit_price: record.unit_price,
    tiersJson: record.tiers ? JSON.stringify(record.tiers) : '',
    package_type: record.package_type,
    effective_date: record.effective_date,
    expiry_date: record.expiry_date,
  })
  modalVisible.value = true
  loadCustomers()
}

const onPricingTypeChange = () => {
  formData.tiersJson = ''
  formData.package_type = undefined
  formData.unit_price = undefined
}

const handleSubmit = async () => {
  if (!formData.customer_id) {
    Message.warning('请选择客户')
    return
  }
  if (!formData.effective_date) {
    Message.warning('请选择生效日期')
    return
  }

  modalLoading.value = true
  try {
    const data: Partial<PricingRule> = {
      customer_id: formData.customer_id,
      device_type: formData.device_type,
      pricing_type: formData.pricing_type,
      effective_date: formData.effective_date,
      expiry_date: formData.expiry_date,
    }

    if (formData.pricing_type === 'fixed' && formData.unit_price) {
      data.unit_price = formData.unit_price
    } else if (formData.pricing_type === 'tiered') {
      if (formData.tiersJson) {
        try {
          data.tiers = JSON.parse(formData.tiersJson)
        } catch (e) {
          Message.error('阶梯配置 JSON 格式不正确')
          modalLoading.value = false
          return
        }
      }
    } else if (formData.pricing_type === 'package' && formData.package_type) {
      data.package_type = formData.package_type
    }

    if (isEdit.value && formData.id) {
      await billingApi.updatePricingRule(formData.id, data)
      Message.success('更新成功')
    } else {
      await billingApi.createPricingRule(data)
      Message.success('创建成功')
    }
    modalVisible.value = false
    fetchData()
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

const handleDelete = async (record: PricingRule) => {
  try {
    await billingApi.deletePricingRule(record.id)
    Message.success('删除成功')
    fetchData()
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '删除失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.pricing-rules {
  padding: 20px;
}

.filter-form {
  margin-bottom: 16px;
}
</style>
