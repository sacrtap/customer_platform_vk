<template>
  <div class="customer-detail-page">
    <a-spin :loading="loading" size="large">
      <div class="page-header">
        <div class="header-title">
          <a-button type="text" @click="goBack">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                fill-rule="evenodd"
                d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z"
              />
            </svg>
          </a-button>
          <h1>{{ customer.name || '客户详情' }}</h1>
        </div>
        <div class="header-actions">
          <a-button @click="openEditModal">编辑</a-button>
          <a-button type="primary" :loading="keyCustomerLoading" @click="toggleKeyCustomer">
            {{ customer.is_key_customer ? '取消重点' : '设为重点' }}
          </a-button>
        </div>
      </div>

      <div class="tabs-section">
        <a-tabs v-model="activeTab">
          <a-tab-pane key="basic" title="基础信息">
            <div class="info-grid">
              <div class="info-item">
                <label>客户名称</label>
                <span>{{ customer.name }}</span>
              </div>
              <div class="info-item">
                <label>公司 ID</label>
                <span>{{ customer.company_id }}</span>
              </div>
              <div class="info-item">
                <label>账号类型</label>
                <a-tag>{{ customer.account_type || '-' }}</a-tag>
              </div>
              <div class="info-item">
                <label>业务类型</label>
                <a-tag>{{ customer.business_type || '-' }}</a-tag>
              </div>
              <div class="info-item">
                <label>客户等级</label>
                <a-tag>{{ customer.customer_level || '-' }}</a-tag>
              </div>
              <div class="info-item">
                <label>重点客户</label>
                <a-tag :color="customer.is_key_customer ? 'red' : 'gray'">
                  {{ customer.is_key_customer ? '是' : '否' }}
                </a-tag>
              </div>
              <div class="info-item">
                <label>结算方式</label>
                <a-tag :color="customer.settlement_type === 'prepaid' ? 'green' : 'blue'">
                  {{ customer.settlement_type === 'prepaid' ? '预付费' : '后付费' }}
                </a-tag>
              </div>
              <div class="info-item">
                <label>结算周期</label>
                <span>{{ customer.settlement_cycle || '-' }}</span>
              </div>
              <div class="info-item">
                <label>邮箱</label>
                <span>{{ customer.email || '-' }}</span>
              </div>
              <div class="info-item">
                <label>创建时间</label>
                <span>{{ formatDateTime(customer.created_at) }}</span>
              </div>
              <div class="info-item-full">
                <label>客户标签</label>
                <div class="tags-container">
                  <a-tag
                    v-for="tag in customerTags"
                    :key="tag.id"
                    color="arcoblue"
                    closable
                    @close="removeTag(tag.id)"
                  >
                    {{ tag.name }}
                  </a-tag>
                  <a-button type="text" size="small" @click="openTagSelector">
                    <template #icon>
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="16"
                        height="16"
                        fill="currentColor"
                        viewBox="0 0 16 16"
                      >
                        <path
                          d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
                        />
                      </svg>
                    </template>
                    添加标签
                  </a-button>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="profile" title="画像信息">
            <div class="info-grid">
              <div class="info-item">
                <label>规模等级</label>
                <a-tag color="blue">{{ profile.scale_level || '-' }}</a-tag>
              </div>
              <div class="info-item">
                <label>消费等级</label>
                <a-tag color="green">{{ profile.consume_level || '-' }}</a-tag>
              </div>
              <div class="info-item">
                <label>所属行业</label>
                <span>{{ profile.industry || '-' }}</span>
              </div>
              <div class="info-item">
                <label>房地产行业</label>
                <a-tag :color="profile.is_real_estate ? 'orange' : 'gray'">
                  {{ profile.is_real_estate ? '是' : '否' }}
                </a-tag>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="balance" title="余额信息">
            <div class="balance-cards">
              <div class="balance-card">
                <div class="balance-label">总余额</div>
                <div class="balance-value">{{ formatCurrency(balance.total_amount) }}</div>
              </div>
              <div class="balance-card">
                <div class="balance-label">实充余额</div>
                <div class="balance-value real">{{ formatCurrency(balance.real_amount) }}</div>
              </div>
              <div class="balance-card">
                <div class="balance-label">赠送余额</div>
                <div class="balance-value bonus">{{ formatCurrency(balance.bonus_amount) }}</div>
              </div>
              <div class="balance-card">
                <div class="balance-label">已消耗</div>
                <div class="balance-value">{{ formatCurrency(balance.used_total) }}</div>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="invoices" title="结算单">
            <a-table :columns="invoiceColumns" :data="invoices" :pagination="false" row-key="id">
              <template #status="{ record }">
                <span :class="['status-badge', getStatusClass(record.status)]">
                  <span class="status-dot"></span>
                  {{ getStatusText(record.status) }}
                </span>
              </template>
              <template #amount="{ record }">
                {{ formatCurrency(record.final_amount || record.total_amount) }}
              </template>
              <template #action="{ record }">
                <a-button type="primary" size="small" @click="viewInvoice(record)">查看</a-button>
              </template>
            </a-table>
          </a-tab-pane>

          <a-tab-pane key="usage" title="用量数据">
            <a-table
              :columns="usageColumns"
              :data="usageData"
              :loading="usageLoading"
              :pagination="usagePagination"
              row-key="id"
              @page-change="handleUsagePageChange"
            >
              <template #deviceType="{ record }">
                <a-tag>{{ record.device_type }}</a-tag>
              </template>
              <template #quantity="{ record }">
                {{ formatNumber(record.quantity || 0) }}
              </template>
            </a-table>
          </a-tab-pane>
        </a-tabs>
      </div>

      <!-- 编辑客户对话框 -->
      <a-modal
        v-model:visible="editModalVisible"
        title="编辑客户"
        :confirm-loading="editLoading"
        @ok="handleEditSubmit"
        @cancel="editModalVisible = false"
      >
        <a-form :model="editForm" layout="vertical">
          <a-form-item field="name" label="客户名称">
            <a-input v-model="editForm.name" placeholder="请输入客户名称" />
          </a-form-item>
          <a-form-item field="email" label="邮箱">
            <a-input v-model="editForm.email" placeholder="请输入邮箱" />
          </a-form-item>
          <a-form-item field="account_type" label="账号类型">
            <a-select v-model="editForm.account_type" placeholder="请选择账号类型" allow-clear>
              <a-option value="正式账号">正式账号</a-option>
              <a-option value="测试账号">测试账号</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="business_type" label="业务类型">
            <a-select v-model="editForm.business_type" placeholder="请选择业务类型" allow-clear>
              <a-option value="A">A 类</a-option>
              <a-option value="B">B 类</a-option>
              <a-option value="C">C 类</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="customer_level" label="客户等级">
            <a-select v-model="editForm.customer_level" placeholder="请选择客户等级" allow-clear>
              <a-option value="KA">KA</a-option>
              <a-option value="A">A</a-option>
              <a-option value="B">B</a-option>
              <a-option value="C">C</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="settlement_type" label="结算方式">
            <a-select v-model="editForm.settlement_type" placeholder="请选择结算方式">
              <a-option value="prepaid">预付费</a-option>
              <a-option value="postpaid">后付费</a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="settlement_cycle" label="结算周期">
            <a-select v-model="editForm.settlement_cycle" placeholder="请选择结算周期" allow-clear>
              <a-option value="日结">日结</a-option>
              <a-option value="周结">周结</a-option>
              <a-option value="月结">月结</a-option>
              <a-option value="季结">季结</a-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>

      <!-- 标签选择器对话框 -->
      <a-modal
        v-model:visible="tagSelectorVisible"
        title="添加标签"
        :confirm-loading="tagSelectorLoading"
        width="500px"
        @ok="handleAddTag"
        @cancel="tagSelectorVisible = false"
      >
        <a-form layout="vertical">
          <a-form-item label="选择标签" required>
            <a-select
              v-model="selectedTagIds"
              placeholder="请选择标签"
              multiple
              allow-clear
              :loading="allTagsLoading"
            >
              <a-option v-for="tag in availableTags" :key="tag.id" :value="tag.id">
                {{ tag.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getCustomer, updateCustomer, getProfile } from '@/api/customers'
import { getCustomerBalance, getInvoices, type Invoice } from '@/api/billing'
import { getTags, getCustomerTags, addCustomerTag, removeCustomerTag } from '@/api/tags'
import { getDailyUsage } from '@/api/usage'
import type { Customer, CustomerProfile, Balance } from '@/types'
import { formatCurrency, formatDate, formatDateTime, formatNumber } from '@/utils/formatters'

const route = useRoute()
const router = useRouter()

// 返回上一页
const goBack = () => {
  router.back()
}

// 编辑表单类型
interface EditForm {
  name: string
  email: string
  account_type?: string
  business_type?: string
  customer_level?: string
  settlement_type?: string
  settlement_cycle?: string
}

// 状态
const loading = ref(false)
const keyCustomerLoading = ref(false)
const editLoading = ref(false)
const editModalVisible = ref(false)
const activeTab = ref('basic')

// 数据
const customerId = ref<number>(0)
const customer = ref<Customer>({
  id: 0,
  company_id: '',
  name: '',
  account_type: null,
  business_type: null,
  customer_level: null,
  price_policy: null,
  manager_id: null,
  settlement_cycle: null,
  settlement_type: null,
  is_key_customer: false,
  email: null,
  created_at: '',
  updated_at: '',
})

const profile = ref<CustomerProfile>({
  id: 0,
  customer_id: 0,
  scale_level: null,
  consume_level: null,
  industry: null,
  is_real_estate: false,
  description: null,
  created_at: '',
  updated_at: '',
})

const balance = ref<Balance>({
  id: 0,
  customer_id: 0,
  total_amount: 0,
  real_amount: 0,
  bonus_amount: 0,
  used_total: 0,
  used_real: 0,
  used_bonus: 0,
  created_at: '',
  updated_at: '',
})

const invoices = ref<Invoice[]>([])
const customerTags = ref<any[]>([])
const allTags = ref<any[]>([])
const allTagsLoading = ref(false)
const tagSelectorVisible = ref(false)
const tagSelectorLoading = ref(false)
const selectedTagIds = ref<number[]>([])

// 用量数据
const usageLoading = ref(false)
const usageData = ref<any[]>([])
const usagePagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})

const usageColumns = [
  { title: '日期', dataIndex: 'usage_date', width: 120 },
  { title: '设备类型', slotName: 'deviceType', width: 100 },
  { title: '层级类型', dataIndex: 'layer_type', width: 100 },
  { title: '用量', slotName: 'quantity', width: 120 },
  { title: '同步时间', dataIndex: 'synced_at', width: 160 },
]

const invoiceColumns = [
  { title: '结算单号', dataIndex: 'invoice_no', width: 180 },
  { title: '周期开始', dataIndex: 'period_start', width: 120 },
  { title: '周期结束', dataIndex: 'period_end', width: 120 },
  { title: '金额', slotName: 'amount', width: 140 },
  { title: '状态', slotName: 'status', width: 120 },
  { title: '创建时间', dataIndex: 'created_at', width: 180 },
  { title: '操作', slotName: 'action', width: 80 },
]

// 编辑表单
const editForm = ref<EditForm>({
  name: '',
  email: '',
  account_type: undefined,
  business_type: undefined,
  customer_level: undefined,
  settlement_type: undefined,
  settlement_cycle: undefined,
})

// 加载数据
const loadCustomerData = async () => {
  loading.value = true
  try {
    const id = Number(route.params.id)
    customerId.value = id

    // 并行加载所有数据
    const [customerRes, profileRes, balanceRes, invoicesRes] = await Promise.all([
      getCustomer(id),
      getProfile(id),
      getCustomerBalance(id),
      getInvoices({ customer_id: id, page_size: 100 }),
    ])

    customer.value = customerRes.data
    profile.value = profileRes.data
    balance.value = balanceRes.data
    invoices.value = invoicesRes.data?.list || invoicesRes.data?.items || []
  } catch (error) {
    Message.error('加载客户数据失败')
    console.error('加载客户数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取状态样式类
const getStatusClass = (status: string) => {
  const statusMap: Record<string, string> = {
    draft: 'warning',
    submitted: 'warning',
    confirmed: 'success',
    paid: 'success',
    completed: 'success',
  }
  return statusMap[status] || 'warning'
}

// 获取状态文本
const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    draft: '草稿',
    submitted: '已提交',
    confirmed: '已确认',
    paid: '已付款',
    completed: '已完成',
  }
  return statusMap[status] || status
}

// 打开编辑对话框
const openEditModal = () => {
  editForm.value = {
    name: customer.value.name || '',
    email: customer.value.email || '',
    account_type: customer.value.account_type || undefined,
    business_type: customer.value.business_type || undefined,
    customer_level: customer.value.customer_level || undefined,
    settlement_type: customer.value.settlement_type || undefined,
    settlement_cycle: customer.value.settlement_cycle || undefined,
  }
  editModalVisible.value = true
}

// 提交编辑
const handleEditSubmit = async () => {
  editLoading.value = true
  try {
    await updateCustomer(customerId.value, {
      name: editForm.value.name,
      email: editForm.value.email || undefined,
      account_type: editForm.value.account_type || undefined,
      business_type: editForm.value.business_type || undefined,
      customer_level: editForm.value.customer_level || undefined,
      settlement_type: editForm.value.settlement_type,
      settlement_cycle: editForm.value.settlement_cycle || undefined,
    })
    Message.success('更新成功')
    editModalVisible.value = false
    await loadCustomerData()
  } catch (error) {
    Message.error('更新失败')
    console.error('更新失败:', error)
  } finally {
    editLoading.value = false
  }
}

// 切换重点客户
const toggleKeyCustomer = async () => {
  keyCustomerLoading.value = true
  try {
    await updateCustomer(customerId.value, {
      is_key_customer: !customer.value.is_key_customer,
    })
    Message.success(customer.value.is_key_customer ? '已取消重点客户' : '已设为重点客户')
    customer.value.is_key_customer = !customer.value.is_key_customer
  } catch (error) {
    Message.error('操作失败')
    console.error('切换重点客户失败:', error)
  } finally {
    keyCustomerLoading.value = false
  }
}

// 查看结算单
const viewInvoice = (record: Invoice) => {
  Message.info(`查看结算单：${record.invoice_no}`)
}

// ========== 标签管理 ==========

// 加载客户标签
const loadCustomerTags = async () => {
  try {
    const res = await getCustomerTags(customerId.value)
    customerTags.value = res.data || []
  } catch (error: any) {
    console.error('加载客户标签失败:', error)
  }
}

// 加载所有可用的客户标签
const loadAllTags = async () => {
  allTagsLoading.value = true
  try {
    const res = await getTags({ type: 'customer', page_size: 100 })
    allTags.value = res.data?.list || []
  } catch (error: any) {
    console.error('加载标签列表失败:', error)
  } finally {
    allTagsLoading.value = false
  }
}

// 计算可用标签（已添加的标签不显示）
const availableTags = computed(() => {
  const addedIds = new Set(customerTags.value.map((t) => t.id))
  return allTags.value.filter((t) => !addedIds.has(t.id))
})

// 打开标签选择器
const openTagSelector = async () => {
  selectedTagIds.value = []
  await loadAllTags()
  tagSelectorVisible.value = true
}

// 添加标签
const handleAddTag = async () => {
  if (selectedTagIds.value.length === 0) {
    Message.warning('请选择要添加的标签')
    return
  }

  tagSelectorLoading.value = true
  try {
    for (const tagId of selectedTagIds.value) {
      await addCustomerTag(customerId.value, tagId)
    }
    Message.success('标签添加成功')
    tagSelectorVisible.value = false
    await loadCustomerTags()
  } catch (error: any) {
    Message.error(error.message || '添加标签失败')
  } finally {
    tagSelectorLoading.value = false
  }
}

// 移除标签
const removeTag = async (tagId: number) => {
  try {
    await removeCustomerTag(customerId.value, tagId)
    Message.success('标签移除成功')
    await loadCustomerTags()
  } catch (error: any) {
    Message.error(error.message || '移除标签失败')
  }
}

// 加载用量数据
const loadUsageData = async () => {
  usageLoading.value = true
  try {
    const res = await getDailyUsage({
      customer_id: customerId.value,
      page: usagePagination.current,
      page_size: usagePagination.pageSize,
    })
    usageData.value = res.data?.list || []
    usagePagination.total = res.data?.total || 0
  } catch (error: any) {
    console.error('加载用量数据失败:', error)
  } finally {
    usageLoading.value = false
  }
}

const handleUsagePageChange = (page: number) => {
  usagePagination.current = page
  loadUsageData()
}

onMounted(() => {
  loadCustomerData()
  loadCustomerTags()
  loadUsageData()
})
</script>

<style scoped>
.customer-detail-page {
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-6: #646a73;
  --neutral-10: #1d2330;
  --primary-1: #e8f3ff;
  --primary-6: #0369a1;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.tabs-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  padding: 24px;
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  padding: 16px 0;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.info-item-full {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.info-item label {
  font-size: 13px;
  color: var(--neutral-6);
  font-weight: 500;
}
.info-item span {
  font-size: 14px;
  color: var(--neutral-10);
}
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.balance-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  padding: 24px 0;
}
.balance-card {
  background: var(--neutral-1);
  padding: 24px;
  border-radius: 12px;
  text-align: center;
}
.balance-label {
  font-size: 13px;
  color: var(--neutral-6);
  margin-bottom: 8px;
}
.balance-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--neutral-10);
}
.balance-value.real {
  color: var(--primary-6);
}
.balance-value.bonus {
  color: #22c55e;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge.success {
  background: #e8ffea;
  color: #22c55e;
}
.status-badge.warning {
  background: #fff7e8;
  color: #f59e0b;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
</style>
