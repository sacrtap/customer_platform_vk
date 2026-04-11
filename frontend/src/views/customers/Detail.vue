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
            <div class="info-table-container">
              <table class="info-table">
                <tbody>
                  <tr>
                    <td class="label-cell">客户名称</td>
                    <td class="value-cell">{{ customer.name }}</td>
                  </tr>
                  <tr>
                    <td class="label-cell">公司 ID</td>
                    <td class="value-cell">{{ customer.company_id }}</td>
                  </tr>
                  <tr>
                    <td class="label-cell">账号类型</td>
                    <td class="value-cell">
                      <a-tag>{{ customer.account_type || '-' }}</a-tag>
                    </td>
                  </tr>
                  <tr>
                    <td class="label-cell">业务类型</td>
                    <td class="value-cell">
                      <a-tag>{{ customer.business_type || '-' }}</a-tag>
                    </td>
                  </tr>
                  <tr>
                    <td class="label-cell">客户等级</td>
                    <td class="value-cell">
                      <a-tag>{{ customer.customer_level || '-' }}</a-tag>
                    </td>
                  </tr>
                  <tr>
                    <td class="label-cell">重点客户</td>
                    <td class="value-cell">
                      <a-tag :color="customer.is_key_customer ? 'red' : 'gray'">
                        {{ customer.is_key_customer ? '是' : '否' }}
                      </a-tag>
                    </td>
                  </tr>
                  <tr>
                    <td class="label-cell">结算方式</td>
                    <td class="value-cell">
                      <a-tag :color="customer.settlement_type === 'prepaid' ? 'green' : 'blue'">
                        {{ customer.settlement_type === 'prepaid' ? '预付费' : '后付费' }}
                      </a-tag>
                    </td>
                  </tr>
                  <tr>
                    <td class="label-cell">结算周期</td>
                    <td class="value-cell">{{ customer.settlement_cycle || '-' }}</td>
                  </tr>
                  <tr>
                    <td class="label-cell">邮箱</td>
                    <td class="value-cell">{{ customer.email || '-' }}</td>
                  </tr>
                  <tr>
                    <td class="label-cell">创建时间</td>
                    <td class="value-cell">{{ formatDateTime(customer.created_at) }}</td>
                  </tr>
                  <tr>
                    <td class="label-cell">客户标签</td>
                    <td class="value-cell">
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
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </a-tab-pane>

          <a-tab-pane key="profile" title="画像信息">
            <div v-if="profileLoading" class="info-grid profile-grid">
              <SkeletonCard v-for="i in 4" :key="i" height="90px" />
            </div>
            <div v-else class="info-grid profile-grid">
              <div class="info-item">
                <label>规模等级</label>
                <a-tag color="blue" size="large">{{ profile.scale_level || '-' }}</a-tag>
              </div>
              <div class="info-item">
                <label>消费等级</label>
                <a-tag color="green" size="large">{{ profile.consume_level || '-' }}</a-tag>
              </div>
              <div class="info-item">
                <label>所属行业</label>
                <span>{{ profile.industry || '-' }}</span>
              </div>
              <div class="info-item">
                <label>房地产行业</label>
                <a-tag :color="profile.is_real_estate ? 'orange' : 'gray'" size="large">
                  {{ profile.is_real_estate ? '是' : '否' }}
                </a-tag>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="balance" title="余额信息">
            <div v-if="balanceLoading" class="balance-cards">
              <SkeletonCard v-for="i in 4" :key="i" height="110px" />
            </div>
            <div v-else class="balance-cards">
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
              <template #empty>
                <EmptyState title="暂无结算单数据" description="当前客户暂无结算单" />
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
              <template #empty>
                <EmptyState title="暂无用量数据" description="当前客户暂无用量记录" />
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
          <a-form-item field="is_key_customer" label="重点客户">
            <a-switch v-model="editForm.is_key_customer" />
          </a-form-item>
          <a-form-item field="manager_id" label="运营经理">
            <a-select
              v-model="editForm.manager_id"
              placeholder="请选择运营经理"
              allow-clear
              :loading="managersLoading"
            >
              <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
                {{ manager.real_name || manager.username }}
              </a-option>
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
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getCustomer, updateCustomer, getProfile } from '@/api/customers'
import { getCustomerBalance, getInvoices, type Invoice } from '@/api/billing'
import { getTags, getCustomerTags, addCustomerTag, removeCustomerTag } from '@/api/tags'
import { getDailyUsage } from '@/api/usage'
import { getManagers } from '@/api/users'
import type { Customer, CustomerProfile, Balance } from '@/types'
import { formatCurrency, formatDateTime, formatNumber } from '@/utils/formatters'
import EmptyState from '@/components/EmptyState.vue'
import SkeletonCard from '@/components/SkeletonCard.vue'

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
  is_key_customer?: boolean
  manager_id?: number
}

// 状态
const loading = ref(false)
const keyCustomerLoading = ref(false)
const editLoading = ref(false)
const editModalVisible = ref(false)
const activeTab = ref('basic')
const profileLoading = ref(true)
const balanceLoading = ref(true)

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

const managersLoading = ref(false)
const managers = ref<any[]>([])

const loadManagers = async () => {
  managersLoading.value = true
  try {
    const res = await getManagers()
    managers.value = res.data?.list || res.data || []
  } catch (error: any) {
    console.error('加载运营经理失败:', error)
  } finally {
    managersLoading.value = false
  }
}

// 用量数据
const usageLoading = ref(false)
const usageData = ref<any[]>([])
const usagePagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})

const usageColumns = [
  { title: '日期', dataIndex: 'usage_date' },
  { title: '设备类型', slotName: 'deviceType' },
  { title: '层级类型', dataIndex: 'layer_type' },
  { title: '用量', slotName: 'quantity' },
  { title: '同步时间', dataIndex: 'synced_at' },
]

const invoiceColumns = [
  { title: '结算单号', dataIndex: 'invoice_no' },
  { title: '周期开始', dataIndex: 'period_start' },
  { title: '周期结束', dataIndex: 'period_end' },
  { title: '金额', slotName: 'amount' },
  { title: '状态', slotName: 'status' },
  { title: '创建时间', dataIndex: 'created_at' },
  { title: '操作', slotName: 'action' },
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
  is_key_customer: false,
  manager_id: undefined,
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
    // 处理 profile 为 null 的情况
    profile.value = profileRes.data || {
      id: 0,
      customer_id: id,
      scale_level: null,
      consume_level: null,
      industry: null,
      is_real_estate: false,
      description: null,
      created_at: '',
      updated_at: '',
    }
    // 为 balance 添加缺失的 id 和 customer_id 字段（后端返回的数据不包含这些字段）
    balance.value = {
      ...balanceRes.data,
      id: 0,
      customer_id: id,
    }
    invoices.value = invoicesRes.data?.list || invoicesRes.data?.items || []
  } catch (error) {
    Message.error('加载客户数据失败')
    console.error('加载客户数据失败:', error)
  } finally {
    loading.value = false
    profileLoading.value = false
    balanceLoading.value = false
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
    is_key_customer: customer.value.is_key_customer || false,
    manager_id: customer.value.manager_id || undefined,
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
      is_key_customer: editForm.value.is_key_customer,
      manager_id: editForm.value.manager_id || undefined,
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
  loadManagers()
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
  --success-bg: #e8ffea;
  --success-color: #22c55e;
  --warning-bg: #fff7e8;
  --warning-color: #f59e0b;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
  
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 12px;
  
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
  
  /* 修复容器宽度溢出问题 - 允许横向滚动 */
  width: 100%;
  overflow-x: auto;
  box-sizing: border-box;
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
  padding: 32px;
  width: 100%;
  box-sizing: border-box;
  overflow-x: auto;
}

/* 纵向表格样式 - 基础信息面板 */
.info-table-container {
  padding: 8px 0;
}

.info-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.info-table tbody tr {
  border-bottom: 1px solid var(--neutral-2);
  transition: background-color var(--transition-fast, 150ms);
}

.info-table tbody tr:last-child {
  border-bottom: none;
}

.info-table tbody tr:hover {
  background-color: var(--neutral-1);
}

.info-table .label-cell {
  width: 140px;
  padding: 14px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--neutral-6);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  vertical-align: top;
  background: var(--neutral-1);
}

.info-table .value-cell {
  padding: 14px 16px;
  font-size: 14px;
  color: var(--neutral-10);
  font-weight: 500;
  line-height: 1.5;
  vertical-align: top;
}

.info-table .value-cell .arco-tag {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 客户标签区域 */
.info-table .tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.info-table .tags-container .arco-btn-text {
  height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  transition: all var(--transition-fast, 150ms);
  border: 1px dashed var(--neutral-6);
  background: transparent;
  color: var(--neutral-6);
  font-size: 13px;
}

.info-table .tags-container .arco-btn-text:hover {
  border-color: var(--primary-6);
  background: var(--primary-1);
  color: var(--primary-6);
}

/* 响应式适配 */
@media (max-width: 768px) {
  .info-table .label-cell {
    width: 100px;
    font-size: 12px;
  }
  
  .info-table .value-cell {
    font-size: 13px;
  }
}

/* 画像信息和余额信息 - 自适应 Grid 布局 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-lg, 24px);
  padding: var(--space-lg, 24px) var(--space-md, 16px);
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

/* 响应式适配 */
@media (max-width: 1199px) and (min-width: 768px) {
  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm, 8px);
  padding: var(--space-md, 16px);
  background: var(--neutral-1);
  border-radius: var(--radius-md, 10px);
  transition: all var(--transition-base, 250ms);
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid var(--neutral-2);
  min-height: 90px;
}

.info-item:hover {
  background: #ffffff;
  transform: translateY(-2px);
  box-shadow: var(--shadow-md, 0 4px 12px rgba(0, 0, 0, 0.08));
  border-color: var(--primary-1);
}

.info-item-full {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--neutral-1);
  border-radius: 10px;
  transition: all var(--transition-fast, 150ms);
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid var(--neutral-2);
}

.info-item-full:hover {
  background: #ffffff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: var(--primary-1);
}
.info-item label,
.info-item-full label {
  font-size: 12px;
  color: var(--neutral-6);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  word-break: break-word;
  flex-shrink: 0;
}

.info-item span,
.info-item-full span {
  font-size: 14px;
  color: var(--neutral-10);
  font-weight: 500;
  line-height: 1.4;
  word-break: break-word;
  overflow-wrap: break-word;
  display: block;
  max-width: 100%;
}

.info-item span {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* 修复标签组件溢出问题 */
.info-item :deep(.arco-tag),
.info-item-full :deep(.arco-tag) {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding-top: 4px;
}

.tags-container .arco-btn-text {
  height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  transition: all var(--transition-fast, 150ms);
  border: 1px dashed var(--neutral-6);
  background: transparent;
  color: var(--neutral-6);
  font-size: 13px;
}

.tags-container .arco-btn-text:hover {
  border-color: var(--primary-6);
  background: var(--primary-1);
  color: var(--primary-6);
}

/* 余额卡片 - 自适应 Grid 布局 */
.balance-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-lg, 24px);
  padding: var(--space-lg, 24px) var(--space-md, 16px);
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

/* 4 张卡片最佳布局 */
@media (min-width: 1400px) {
  .balance-cards {
    grid-template-columns: repeat(4, 1fr);
  }
}

/* 响应式适配 */
@media (max-width: 1199px) and (min-width: 768px) {
  .balance-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .balance-cards {
    grid-template-columns: 1fr;
  }
}

.balance-card {
  background: linear-gradient(135deg, #ffffff 0%, var(--neutral-1) 100%);
  padding: var(--space-lg, 20px) var(--space-md, 16px);
  border-radius: var(--radius-lg, 12px);
  text-align: center;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm, 0 2px 4px rgba(0, 0, 0, 0.04));
  transition: all var(--transition-base, 250ms);
  min-height: 110px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.balance-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(0, 0, 0, 0.12));
  border-color: var(--primary-1);
}
.balance-label {
  font-size: 13px;
  color: var(--neutral-6);
  margin-bottom: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.balance-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--neutral-10);
  line-height: 1.2;
}

.balance-value.real {
  color: var(--primary-6);
}

.balance-value.bonus {
  color: var(--success-color);
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
  background: var(--success-bg);
  color: var(--success-color);
}
.status-badge.warning {
  background: var(--warning-bg);
  color: var(--warning-color);
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* 画像区域专属样式 */
.profile-grid {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-lg, 24px);
  padding: var(--space-lg, 24px) var(--space-md, 16px);
}

/* Tabs 容器 - 允许横向滚动 */
:deep(.arco-tabs-pane) {
  width: 100%;
  overflow-x: visible;
}

:deep(.arco-tabs-content) {
  width: 100%;
  overflow-x: visible;
}

/* 表格自动布局，支持横向滚动 */
:deep(.arco-table) {
  min-width: 700px;
  table-layout: auto;
}

/* 表格容器 - 支持横向滚动 */
.table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--neutral-2);
  border-radius: var(--radius-md);
}

/* 表格空状态居中样式 */
:deep(.arco-table-empty) {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 48px 24px;
  min-height: 300px;
}

:deep(.arco-table-empty .empty-state) {
  margin: 0 auto;
}

/* 空数据最小高度，防止布局塌陷 */
.info-grid,
.balance-cards {
  min-height: 200px;
}

/* 响应式断点 */
/* Mobile - 375px */
@media (max-width: 374px) {
  .info-grid,
  .balance-cards {
    grid-template-columns: 1fr;
  }
  
  .info-item {
    padding: 12px;
  }
  
  .balance-card {
    padding: 16px 12px;
  }
}

/* Mobile Large - 767px */
@media (max-width: 767px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .balance-cards {
    grid-template-columns: 1fr;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .header-actions {
    width: 100%;
  }
  
  .header-actions .arco-btn {
    flex: 1;
  }
  
  .tabs-section {
    padding: 16px;
  }
}

/* Tablet - 768px to 1199px */
@media (min-width: 768px) and (max-width: 1199px) {
  .info-grid,
  .balance-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Desktop - 1200px+ */
@media (min-width: 1200px) {
  .balance-cards {
    grid-template-columns: repeat(4, 1fr);
  }
}

/* 减少运动偏好支持 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
