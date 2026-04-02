<template>
  <div class="balance-list">
    <a-card>
      <template #title>
        <a-space>
          <span>余额管理</span>
          <a-button type="primary" @click="showRechargeModal">
            <template #icon><icon-plus /></template>
            充值
          </a-button>
        </a-space>
      </template>

      <!-- 筛选区域 -->
      <a-form :model="filters" layout="inline" class="filter-form">
        <a-form-item label="客户名称">
          <a-input
            v-model="filters.keyword"
            placeholder="请输入客户名称"
            style="width: 200px"
            @press-enter="handleSearch"
          >
            <template #prefix><icon-search /></template>
          </a-input>
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
          <a-space>
            <a-avatar :size="24">{{ record.customer_name?.charAt(0) || 'C' }}</a-avatar>
            <span>{{ record.customer_name || `客户${record.customer_id}` }}</span>
          </a-space>
        </template>
        <template #total_amount="{ record }">
          <a-typography-text type="success">¥{{ formatAmount(record.total_amount) }}</a-typography-text>
        </template>
        <template #real_amount="{ record }">
          <span>¥{{ formatAmount(record.real_amount) }}</span>
        </template>
        <template #bonus_amount="{ record }">
          <a-tag color="orange">¥{{ formatAmount(record.bonus_amount) }}</a-tag>
        </template>
        <template #used_total="{ record }">
          <a-typography-text type="danger">¥{{ formatAmount(record.used_total) }}</a-typography-text>
        </template>
        <template #balance="{ record }">
          <a-tag :color="record.total_amount - record.used_total > 0 ? 'green' : 'gray'">
            ¥{{ formatAmount(record.total_amount - record.used_total) }}
          </a-tag>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="viewRechargeRecords(record)">充值记录</a-button>
            <a-button type="text" size="small" @click="viewConsumptionRecords(record)">消费记录</a-button>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 充值弹窗 -->
    <a-modal
      v-model:visible="rechargeModalVisible"
      title="客户充值"
      :confirm-loading="rechargeLoading"
      width="500px"
      @ok="handleRecharge"
    >
      <a-form :model="rechargeForm" layout="vertical">
        <a-form-item
          label="选择客户"
          :rules="[{ required: true, message: '请选择客户' }]"
        >
          <a-select
            v-model="rechargeForm.customer_id"
            placeholder="请选择客户"
            :loading="customersLoading"
          >
            <a-option
              v-for="customer in customers"
              :key="customer.id"
              :value="customer.id"
              :label="customer.name"
            >
              <a-space>
                <span>{{ customer.name }}</span>
                <a-tag v-if="customer.is_key_customer" size="small" color="orangered">重点</a-tag>
              </a-space>
            </a-option>
          </a-select>
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item
              label="实充金额"
              :rules="[{ required: true, message: '请输入实充金额' }]"
            >
              <a-input-number
                v-model="rechargeForm.real_amount"
                placeholder="请输入金额"
                :min="0"
                :precision="2"
                style="width: 100%"
              >
                <template #prefix>¥</template>
              </a-input-number>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="赠费金额">
              <a-input-number
                v-model="rechargeForm.bonus_amount"
                placeholder="请输入金额"
                :min="0"
                :precision="2"
                style="width: 100%"
              >
                <template #prefix>¥</template>
              </a-input-number>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="备注">
          <a-textarea
            v-model="rechargeForm.remark"
            placeholder="请输入备注"
            :max-length="200"
            show-word-limit
            :auto-size="{ minRows: 3, maxRows: 5 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 充值记录弹窗 -->
    <a-modal
      v-model:visible="rechargeRecordsModalVisible"
      title="充值记录"
      :footer="false"
      width="800px"
    >
      <a-table
        :columns="rechargeRecordColumns"
        :data="rechargeRecords"
        :loading="rechargeRecordsLoading"
        row-key="id"
        :pagination="rechargeRecordPagination"
        @page-change="onRechargeRecordPageChange"
        @page-size-change="onRechargeRecordPageSizeChange"
      >
        <template #amount="{ record }">
          <a-space>
            <span>实充：¥{{ formatAmount(record.real_amount) }}</span>
            <a-tag v-if="record.bonus_amount > 0" color="orange">赠：¥{{ formatAmount(record.bonus_amount) }}</a-tag>
          </a-space>
        </template>
        <template #created_at="{ record }">
          {{ formatDate(record.created_at) }}
        </template>
      </a-table>
    </a-modal>

    <!-- 消费记录弹窗 -->
    <a-modal
      v-model:visible="consumptionRecordsModalVisible"
      title="消费记录"
      :footer="false"
      width="800px"
    >
      <a-table
        :columns="consumptionRecordColumns"
        :data="consumptionRecords"
        :loading="consumptionRecordsLoading"
        row-key="id"
        :pagination="consumptionRecordPagination"
        @page-change="onConsumptionRecordPageChange"
        @page-size-change="onConsumptionRecordPageSizeChange"
      >
        <template #amount="{ record }">
          <a-space>
            <span>¥{{ formatAmount(record.amount) }}</span>
            <a-tag v-if="record.bonus_used > 0" color="orange">赠费：¥{{ formatAmount(record.bonus_used) }}</a-tag>
            <a-tag v-if="record.real_used > 0" color="blue">实付：¥{{ formatAmount(record.real_used) }}</a-tag>
          </a-space>
        </template>
        <template #consumed_at="{ record }">
          {{ formatDate(record.consumed_at) }}
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconPlus,
  IconSearch,
} from '@arco-design/web-vue/es/icon'
import * as billingApi from '@/api/billing'
import { getCustomers } from '@/api/customers'

interface Balance {
  id: number
  customer_id: number
  customer_name?: string
  total_amount: number
  real_amount: number
  bonus_amount: number
  used_total: number
  used_real: number
  used_bonus: number
}

const columns = [
  { title: '客户名称', dataIndex: 'customer_name', slotName: 'customer_name', width: 200 },
  { title: '总余额', dataIndex: 'total_amount', slotName: 'total_amount', width: 120 },
  { title: '实充余额', dataIndex: 'real_amount', slotName: 'real_amount', width: 120 },
  { title: '赠费余额', dataIndex: 'bonus_amount', slotName: 'bonus_amount', width: 120 },
  { title: '已用总额', dataIndex: 'used_total', slotName: 'used_total', width: 120 },
  { title: '剩余余额', dataIndex: 'balance', slotName: 'balance', width: 120 },
  { title: '操作', slotName: 'action', width: 200, fixed: 'right' },
]

const data = ref<Balance[]>([])
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
})

const rechargeModalVisible = ref(false)
const rechargeLoading = ref(false)
const rechargeForm = reactive({
  customer_id: null as number | null,
  real_amount: 0,
  bonus_amount: 0,
  remark: '',
})

const customers = ref<{ id: number; name: string; is_key_customer?: boolean }[]>([])
const customersLoading = ref(false)

const rechargeRecordsModalVisible = ref(false)
const rechargeRecords = ref<any[]>([])
const rechargeRecordsLoading = ref(false)
const rechargeRecordPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
})
const currentCustomerId = ref<number | null>(null)

const rechargeRecordColumns = [
  { title: '实充/赠费', slotName: 'amount', width: 200 },
  { title: '备注', dataIndex: 'remark', width: 200 },
  { title: '操作人', dataIndex: 'operator_id', width: 100 },
  { title: '充值时间', slotName: 'created_at', width: 180 },
]

const consumptionRecordsModalVisible = ref(false)
const consumptionRecords = ref<any[]>([])
const consumptionRecordsLoading = ref(false)
const consumptionRecordPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const consumptionRecordColumns = [
  { title: '消费金额', slotName: 'amount', width: 250 },
  { title: '余额变动后', dataIndex: 'balance_after', width: 120 },
  { title: '消费时间', slotName: 'consumed_at', width: 180 },
]

const formatAmount = (amount: number) => {
  return amount.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await billingApi.getBalances({
      keyword: filters.keyword || undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    data.value = res.data.list || []
    pagination.total = res.data.total || 0
  } catch (err: any) {
    Message.error(err.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  customersLoading.value = true
  try {
    const res = await getCustomers({ page_size: 1000 })
    customers.value = res.data.list || []
  } catch (err: any) {
    Message.error('加载客户列表失败')
  } finally {
    customersLoading.value = false
  }
}

const handleSearch = () => {
  fetchData()
}

const handleReset = () => {
  filters.keyword = ''
  fetchData()
}

const onPageChange = (page: number) => {
  pagination.current = page
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
}

const showRechargeModal = () => {
  rechargeModalVisible.value = true
  rechargeForm.customer_id = null
  rechargeForm.real_amount = 0
  rechargeForm.bonus_amount = 0
  rechargeForm.remark = ''
  loadCustomers()
}

const handleRecharge = async () => {
  if (!rechargeForm.customer_id) {
    Message.warning('请选择客户')
    return
  }
  if (rechargeForm.real_amount <= 0) {
    Message.warning('实充金额必须大于 0')
    return
  }
  
  rechargeLoading.value = true
  try {
    await billingApi.recharge({
      customer_id: rechargeForm.customer_id,
      real_amount: rechargeForm.real_amount,
      bonus_amount: rechargeForm.bonus_amount,
      remark: rechargeForm.remark,
    })
    Message.success('充值成功')
    rechargeModalVisible.value = false
    fetchData()
  } catch (err: any) {
    Message.error(err.message || '充值失败')
  } finally {
    rechargeLoading.value = false
  }
}

const viewRechargeRecords = async (record: Balance) => {
  currentCustomerId.value = record.customer_id
  rechargeRecordsModalVisible.value = true
  rechargeRecordsLoading.value = true
  try {
    const res = await billingApi.getRechargeRecords({
      customer_id: record.customer_id,
      page: rechargeRecordPagination.current,
      page_size: rechargeRecordPagination.pageSize,
    })
    rechargeRecords.value = res.data.list || []
    rechargeRecordPagination.total = res.data.total || 0
  } catch (err: any) {
    Message.error(err.message || '加载失败')
  } finally {
    rechargeRecordsLoading.value = false
  }
}

const onRechargeRecordPageChange = (page: number) => {
  rechargeRecordPagination.current = page
  if (currentCustomerId.value) {
    viewRechargeRecords({ customer_id: currentCustomerId.value } as Balance)
  }
}

const onRechargeRecordPageSizeChange = (pageSize: number) => {
  rechargeRecordPagination.pageSize = pageSize
  rechargeRecordPagination.current = 1
  if (currentCustomerId.value) {
    viewRechargeRecords({ customer_id: currentCustomerId.value } as Balance)
  }
}

const viewConsumptionRecords = async (record: Balance) => {
  currentCustomerId.value = record.customer_id
  consumptionRecordsModalVisible.value = true
  consumptionRecordsLoading.value = true
  try {
    const res = await billingApi.getConsumptionRecords({
      customer_id: record.customer_id,
      page: consumptionRecordPagination.current,
      page_size: consumptionRecordPagination.pageSize,
    })
    consumptionRecords.value = res.data.list || []
    consumptionRecordPagination.total = res.data.total || 0
  } catch (err: any) {
    Message.error(err.message || '加载失败')
  } finally {
    consumptionRecordsLoading.value = false
  }
}

const onConsumptionRecordPageChange = (page: number) => {
  consumptionRecordPagination.current = page
  if (currentCustomerId.value) {
    viewConsumptionRecords({ customer_id: currentCustomerId.value } as Balance)
  }
}

const onConsumptionRecordPageSizeChange = (pageSize: number) => {
  consumptionRecordPagination.pageSize = pageSize
  consumptionRecordPagination.current = 1
  if (currentCustomerId.value) {
    viewConsumptionRecords({ customer_id: currentCustomerId.value } as Balance)
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.balance-list {
  padding: 20px;
}

.filter-form {
  margin-bottom: 16px;
}
</style>
