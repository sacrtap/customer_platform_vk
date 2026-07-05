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
        <a-tabs v-model="activeTab" @change="handleTabChange">
          <a-tab-pane key="basic" title="基础信息">
            <CustomerBasicTab :customer="customer!" :managers="managers" :customer-tags="customerTags" @open-tag-selector="openTagSelector" @remove-tag="removeTag" />
          </a-tab-pane>
          <a-tab-pane key="profile" title="画像信息">
            <CustomerProfileTab
              :profile="profile!"
              :profile-loading="profileLoading"
              :health-score="healthScore"
              :health-score-loading="healthScoreLoading"
            />
          </a-tab-pane>

          <a-tab-pane key="balance" title="余额信息">
            <CustomerBalanceTab
              :balance="balance"
              :balance-loading="balanceLoading"
              :balance-trend="balanceTrend"
              :balance-trend-loading="balanceTrendLoading"
              :should-render-balance-trend="shouldRenderChart('balanceTrend')"
            />
          </a-tab-pane>

          <a-tab-pane key="invoices" title="结算单">
            <CustomerInvoicesTab :invoices="invoices" @view-invoice="viewInvoice" />
          </a-tab-pane>

          <a-tab-pane key="usage" title="用量数据">
            <CustomerUsageTab
              :usage-data="usageData"
              :usage-loading="usageLoading"
              :usage-pagination="usagePagination"
            >
              <template #chart>
                <UsageDistributionChart
                  v-if="shouldRenderChart('usageDistribution')"
                  :distribution="usageDistribution"
                  :total-quantity="totalUsageQuantity"
                  :loading="usageLoading"
                />
              </template>
            </CustomerUsageTab>
          </a-tab-pane>
        </a-tabs>
      </div>

      <!-- 编辑客户对话框 -->
      <EditCustomerDialog
        :visible="editModalVisible"
        :customer="customer"
        :edit-loading="editLoading"
        :modal-width="modalWidth"
        :industry-types="industryTypes"
        :industry-types-loading="industryTypesLoading"
        :managers="managers"
        :price-policy-options="pricePolicyOptions"
        @submit="handleEditSubmit"
        @close="editModalVisible = false"
      />

      <!-- 标签选择器对话框 -->
      <TagSelectorDialog
        :visible="tagSelectorVisible"
        :loading="tagSelectorLoading"
        :all-tags="allTags"
        :all-tags-loading="allTagsLoading"
        :customer-tags="customerTags"
        @add="handleAddTag"
        @close="closeTagSelector"
      />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import {
  getCustomer,
  updateCustomer,
  getProfile,
  updateProfile,
  getIndustryTypes,
} from '@/api/customers'
import {
  getCustomerBalance,
  getInvoices,
  type Invoice,
  getBalanceTrend,
  type BalanceTrendItem,
} from '@/api/billing'
import { getTags, getCustomerTags, addCustomerTag, removeCustomerTag } from '@/api/tags'
import { getDailyUsage, type DailyUsage } from '@/api/usage'
import { getManagers } from '@/api/users'
import { getCustomerHealthScore, type CustomerHealthScore } from '@/api/analytics'
import type { Customer, CustomerProfile, Balance, Tag, User, IndustryType } from '@/types'
import UsageDistributionChart from '@/components/charts/UsageDistributionChart.vue'
import { useCustomerStore } from '@/stores/customer'

import EditCustomerDialog from './detail/EditCustomerDialog.vue'
import TagSelectorDialog from './detail/TagSelectorDialog.vue'
import CustomerBasicTab from './detail/CustomerBasicTab.vue'
import CustomerProfileTab from './detail/CustomerProfileTab.vue'
import CustomerBalanceTab from './detail/CustomerBalanceTab.vue'
import CustomerInvoicesTab from './detail/CustomerInvoicesTab.vue'
import CustomerUsageTab from './detail/CustomerUsageTab.vue'
const route = useRoute()
const router = useRouter()
const customerStore = useCustomerStore()

// 价格策略选项
const pricePolicyOptions = [
  { label: '定价', value: 'pricing' },
  { label: '阶梯', value: 'tiered' },
  { label: '包年', value: 'yearly' },
]


// 弹窗响应式宽度
const modalWidth = computed(() => {
  if (typeof window === 'undefined') return '1100px'
  const width = window.innerWidth
  if (width >= 1400) return '1100px'
  if (width >= 768) return '800px'
  return '100%'
})

// 性能优化: 已加载的标签页数据
const loadedTabs = ref<Set<string>>(new Set(['basic']))

// 性能优化: 图表渲染状态（延迟加载）
const chartRenderState = ref<Record<string, boolean>>({})

// 延迟加载定时器
let tabLoadTimer: ReturnType<typeof setTimeout> | null = null

// 性能优化: 检查是否应该渲染图表
const shouldRenderChart = (chartId: string): boolean => {
  return chartRenderState.value[chartId] ?? false
}

// 性能优化: 标记图表为可渲染
const markChartForRender = (chartId: string): void => {
  chartRenderState.value[chartId] = true
}

// 性能优化: Tab 切换处理 - 按需加载数据
const handleTabChange = (tabKey: string): void => {
  if (!loadedTabs.value.has(tabKey)) {
    loadedTabs.value.add(tabKey)

    // 延迟加载图表，避免标签页切换卡顿
    if (tabLoadTimer) {
      clearTimeout(tabLoadTimer)
    }

    tabLoadTimer = setTimeout(() => {
      if (tabKey === 'profile') {
        markChartForRender('health')
        markChartForRender('consume')
      } else if (tabKey === 'balance') {
        markChartForRender('balanceTrend')
      } else if (tabKey === 'usage') {
        markChartForRender('usageDistribution')
      }
    }, 100)
  }
}

// 返回上一页
const goBack = () => {
  router.back()
}

// 编辑表单类型
interface EditForm {
  name: string
  company_id: number
  email: string
  account_type?: string
  industry_type_id?: number | null
  price_policy?: string
  settlement_type?: string
  settlement_cycle?: string
  is_key_customer?: boolean
  manager_id?: number
  // 新增字段
  erp_system?: string
  first_payment_date?: string
  onboarding_date?: string
  sales_manager_id?: number
  cooperation_status?: string
  is_settlement_enabled?: boolean
  is_disabled?: boolean
  notes?: string
  is_real_estate?: boolean | null
  // 规模等级和消费等级（来自 CustomerProfile）
  scale_level?: string
  consume_level?: string
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
  company_id: 0,
  name: '',
  account_type: null,
  industry: null,
  price_policy: null,
  manager_id: null,
  settlement_cycle: null,
  settlement_type: null,
  is_key_customer: false,
  email: null,
  created_at: '',
  updated_at: '',
  erp_system: null,
  first_payment_date: null,
  onboarding_date: null,
  sales_manager_id: null,
  cooperation_status: null,
  is_settlement_enabled: null,
  is_disabled: null,
  notes: null,
  is_real_estate: null,
  industry_type_id: null,
  scale_level: null,
  consume_level: null,
})

const profile = ref<CustomerProfile>({
  id: 0,
  customer_id: 0,
  scale_level: null,
  consume_level: null,
  industry_type_id: null,
  is_real_estate: false,
  description: null,
  created_at: '',
  updated_at: '',
  monthly_avg_shots: null,
  monthly_avg_shots_estimated: null,
  estimated_annual_spend: null,
  actual_annual_spend_2025: null,
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

// 健康度数据
const healthScoreLoading = ref(true)
const healthScore = ref<CustomerHealthScore | null>(null)

// 余额趋势数据
const balanceTrendLoading = ref(true)
const balanceTrend = ref<BalanceTrendItem[]>([])

// 用量分布数据（模拟）
const usageDistribution = ref<Array<{ device_type: string; quantity: number; percentage: number }>>(
  []
)
const totalUsageQuantity = ref(0)

const invoices = ref<Invoice[]>([])
const customerTags = ref<Tag[]>([])
const allTags = ref<Tag[]>([])
const allTagsLoading = ref(false)
const tagSelectorVisible = ref(false)
const tagSelectorLoading = ref(false)
const selectedTagIds = ref<number[]>([])

const managersLoading = ref(false)
const managers = ref<User[]>([])

const industryTypes = ref<IndustryType[]>([])
const industryTypesLoading = ref(false)

const loadIndustryTypes = async () => {
  industryTypesLoading.value = true
  try {
    const res = await getIndustryTypes()
    industryTypes.value = res.data || []
  } catch (error) {
    console.error('加载行业类型失败:', error)
  } finally {
    industryTypesLoading.value = false
  }
}

const loadManagers = async () => {
  // 性能优化: 检查缓存
  if (customerStore.hasCachedManagers()) {
    managers.value = customerStore.getCachedManagers() || []
    return
  }

  managersLoading.value = true
  try {
    const res = await getManagers()
    const managersList = res.data?.list || res.data || []
    managers.value = managersList
    // 性能优化: 缓存数据
    customerStore.cacheManagersData(managersList)
  } catch (error) {
    console.error('加载运营经理失败:', error)
  } finally {
    managersLoading.value = false
  }
}

// 用量数据
const usageLoading = ref(false)
const usageData = ref<DailyUsage[]>([])
const usagePagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})



// 编辑表单
const editForm = ref<EditForm>({
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
  // 新增字段
  erp_system: undefined,
  first_payment_date: undefined,
  onboarding_date: undefined,
  sales_manager_id: undefined,
  cooperation_status: undefined,
  is_settlement_enabled: true,
  is_disabled: false,
  notes: undefined,
  is_real_estate: null,
  // 规模等级和消费等级（来自 CustomerProfile）
  scale_level: undefined,
  consume_level: undefined,
})


// 加载数据 - 优化版：支持 Pinia 缓存和并行加载
const loadCustomerData = async () => {
  const id = Number(route.params.id)
  customerId.value = id

  // 性能优化: 检查是否有缓存数据
  if (customerStore.hasCachedCustomer(id)) {
    const cached = customerStore.getCachedCustomer(id)!
    customer.value = cached.customer
    profile.value = cached.profile
    balance.value = cached.balance
    invoices.value = cached.invoices
    healthScore.value = cached.healthScore
    balanceTrend.value = cached.balanceTrend

    loading.value = false
    profileLoading.value = false
    balanceLoading.value = false
    healthScoreLoading.value = false
    balanceTrendLoading.value = false

    // 模拟用量分布数据
    usageDistribution.value = [
      { device_type: 'iOS', quantity: 45000, percentage: 45 },
      { device_type: 'Android', quantity: 35000, percentage: 35 },
      { device_type: 'Web', quantity: 15000, percentage: 15 },
      { device_type: 'H5', quantity: 5000, percentage: 5 },
    ]
    totalUsageQuantity.value = 100000
    return
  }

  loading.value = true

  // 性能优化: 分阶段加载数据 - 先加载关键数据
  try {
    // 第一阶段: 加载基础信息（快速显示）
    const [customerRes, profileRes, balanceRes] = await Promise.all([
      getCustomer(id),
      getProfile(id),
      getCustomerBalance(id),
    ])

    customer.value = customerRes.data
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
    balance.value = {
      ...balanceRes.data,
      id: 0,
      customer_id: id,
    }

    // 第一阶段数据加载完成，立即更新加载状态
    profileLoading.value = false
    balanceLoading.value = false

    // 第二阶段: 加载其他数据（后台加载）
    const [invoicesRes, healthRes, balanceTrendRes] = await Promise.all([
      getInvoices({ customer_id: id, page_size: 100 }),
      getCustomerHealthScore(id).catch(() => ({
        data: { customer_id: id, score: 75, level: '健康', factors: [] },
      })),
      getBalanceTrend(id, 6).catch(() => ({ data: [] })),
    ])

    invoices.value = invoicesRes.data?.list || invoicesRes.data?.items || []
    healthScore.value = healthRes.data
    balanceTrend.value = balanceTrendRes.data || []
    healthScoreLoading.value = false
    balanceTrendLoading.value = false

    // 模拟用量分布数据
    usageDistribution.value = [
      { device_type: 'iOS', quantity: 45000, percentage: 45 },
      { device_type: 'Android', quantity: 35000, percentage: 35 },
      { device_type: 'Web', quantity: 15000, percentage: 15 },
      { device_type: 'H5', quantity: 5000, percentage: 5 },
    ]
    totalUsageQuantity.value = 100000

    // 性能优化: 缓存所有数据
    customerStore.cacheCustomerData(id, {
      customer: customer.value,
      profile: profile.value,
      balance: balance.value,
      invoices: invoices.value,
      healthScore: healthScore.value,
      balanceTrend: balanceTrend.value,
    })
  } catch (error) {
    Message.error('加载客户数据失败')
    console.error('加载客户数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取状态样式类

// 获取状态文本

// 打开编辑对话框
const openEditModal = () => {
  // 防护检查：确保 profile 数据已加载
  if (profileLoading.value || !profile.value) {
    Message.warning('客户画像数据加载中，请稍后编辑')
    return
  }

  editForm.value = {
    name: customer.value.name || '',
    company_id: Number(customer.value.company_id) || 0,
    email: customer.value.email || '',
    account_type: customer.value.account_type || undefined,
    industry_type_id: profile.value.industry_type_id ?? null,
    price_policy: customer.value.price_policy || undefined,
    settlement_type: customer.value.settlement_type || undefined,
    settlement_cycle: customer.value.settlement_cycle || undefined,
    is_key_customer: customer.value.is_key_customer || false,
    manager_id: customer.value.manager_id || undefined,
    // 新增字段
    erp_system: customer.value.erp_system || undefined,
    first_payment_date: customer.value.first_payment_date || undefined,
    onboarding_date: customer.value.onboarding_date || undefined,
    sales_manager_id: customer.value.sales_manager_id || undefined,
    cooperation_status: customer.value.cooperation_status || undefined,
    is_settlement_enabled: customer.value.is_settlement_enabled ?? true,
    is_disabled: customer.value.is_disabled ?? false,
    notes: customer.value.notes || undefined,
    is_real_estate: customer.value.is_real_estate ?? null,
    // 规模等级和消费等级（来自 CustomerProfile）
    scale_level: profile.value.scale_level || undefined,
    consume_level: profile.value.consume_level || undefined,
  }
  editModalVisible.value = true
}

// 提交编辑
const handleEditSubmit = async (form: EditForm) => {
  // 1. 日期格式校验
  if (form.first_payment_date) {
    const paymentDate = new Date(form.first_payment_date)
    const today = new Date()
    today.setHours(23, 59, 59, 999)
    if (paymentDate > today) {
      Message.error('首次回款时间不能超过今天')
      return false
    }
  }

  if (form.onboarding_date) {
    const onboardingDate = new Date(form.onboarding_date)
    const today = new Date()
    today.setHours(23, 59, 59, 999)
    if (onboardingDate > today) {
      Message.error('接入时间不能超过今天')
      return false
    }
  }

  // 2. 首次回款时间不能早于接入时间
  if (form.first_payment_date && form.onboarding_date) {
    const paymentDate = new Date(form.first_payment_date)
    const onboardingDate = new Date(form.onboarding_date)
    if (paymentDate < onboardingDate) {
      Message.error('首次回款时间不能早于接入时间')
      return false
    }
  }

  editLoading.value = true
  try {
    await Promise.all([
      updateCustomer(customerId.value, {
        company_id: form.company_id,
        name: form.name,
        email: form.email || undefined,
        account_type: form.account_type || undefined,
        industry_type_id: form.industry_type_id ?? undefined,
        price_policy: form.price_policy || undefined,
        settlement_type: form.settlement_type,
        settlement_cycle: form.settlement_cycle || undefined,
        is_key_customer: form.is_key_customer,
        manager_id: form.manager_id || undefined,
        erp_system: form.erp_system || undefined,
        first_payment_date: form.first_payment_date || undefined,
        onboarding_date: form.onboarding_date || undefined,
        sales_manager_id: form.sales_manager_id || undefined,
        cooperation_status: form.cooperation_status || undefined,
        is_settlement_enabled: form.is_settlement_enabled,
        is_disabled: form.is_disabled,
        notes: form.notes || undefined,
        is_real_estate: form.is_real_estate ?? null,
      }),
      updateProfile(customerId.value, {
        scale_level: form.scale_level || undefined,
        consume_level: form.consume_level || undefined,
        industry_type_id: form.industry_type_id ?? undefined,
      }),
    ])
    Message.success('更新成功')
    editModalVisible.value = false
    customerStore.invalidateCustomerCache(customerId.value)
    await loadCustomerData()
    return true
  } catch (error: unknown) {
    const err = error as Error
    if (err.message && err.message !== 'Error') {
      Message.error(err.message)
    } else {
      Message.error('更新失败，请查看浏览器控制台获取详细信息')
    }
    console.error('更新失败:', error)
    return false
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
    // 性能优化: 更新 store 缓存
    customerStore.updateCachedCustomerPart(customerId.value, 'customer', customer.value)
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
  // 性能优化: 检查缓存
  const cachedTags = customerStore.getCachedTags(customerId.value)
  if (cachedTags && customerStore.hasCachedTags(customerId.value)) {
    customerTags.value = cachedTags.customerTags
    allTags.value = cachedTags.allTags
    return
  }

  try {
    const [customerTagsRes, allTagsRes] = await Promise.all([
      getCustomerTags(customerId.value),
      getTags({ type: 'customer', page_size: 100 }),
    ])
    customerTags.value = customerTagsRes.data || []
    allTags.value = allTagsRes.data?.list || []
    // 性能优化: 缓存数据
    customerStore.cacheTagsData(customerId.value, {
      customerTags: customerTags.value,
      allTags: allTags.value,
    })
  } catch (error) {
    console.error('加载客户标签失败:', error)
  }
}

// 加载所有可用的客户标签（保留用于标签选择器打开时刷新）
const loadAllTags = async () => {
  allTagsLoading.value = true
  try {
    const res = await getTags({ type: 'customer', page_size: 100 })
    allTags.value = res.data?.list || []
  } catch (error) {
    console.error('加载标签列表失败:', error)
  } finally {
    allTagsLoading.value = false
  }
}




// 打开标签选择器
const openTagSelector = async () => {
  selectedTagIds.value = []
  await loadAllTags()
  tagSelectorVisible.value = true
}

const closeTagSelector = () => { tagSelectorVisible.value = false }
// 添加标签
const handleAddTag = async (tagIds: number[]) => {

  tagSelectorLoading.value = true
  try {
    for (const tagId of tagIds) {
      await addCustomerTag(customerId.value, tagId)
    }
    Message.success('标签添加成功')
    tagSelectorVisible.value = false
    // 性能优化: 更新后清除缓存并重新加载
    customerStore.invalidateTagsCache(customerId.value)
    await loadCustomerTags()
  } catch (error) {
    Message.error((error as Error).message || '添加标签失败')
  } finally {
    tagSelectorLoading.value = false
  }
}

// 移除标签
const removeTag = async (tagId: number) => {
  try {
    await removeCustomerTag(customerId.value, tagId)
    Message.success('标签移除成功')
    // 性能优化：更新后清除缓存并重新加载
    customerStore.invalidateTagsCache(customerId.value)
    await loadCustomerTags()
  } catch (error) {
    Message.error((error as Error).message || '移除标签失败')
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
  } catch (error) {
    console.error('加载用量数据失败:', error)
  } finally {
    usageLoading.value = false
  }
}


onMounted(() => {
  loadCustomerData()
  loadCustomerTags()
  loadUsageData()
  loadManagers()
  loadIndustryTypes()
  window.addEventListener('resize', handleResize)
})

// 弹窗宽度响应式更新
const handleResize = () => {
  // 触发 modalWidth computed 重新计算
  window.dispatchEvent(new Event('resize'))
}

// 性能优化: 路由变化时重置状态（防止复用组件时状态残留）
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId !== oldId) {
      activeTab.value = 'basic'
      loadedTabs.value = new Set(['basic'])
      chartRenderState.value = {}
      if (tabLoadTimer) {
        clearTimeout(tabLoadTimer)
        tabLoadTimer = null
      }
      loadCustomerData()
      loadCustomerTags()
      loadUsageData()
    }
  }
)

// 性能优化: 组件卸载时清理定时器和事件监听器，防止内存泄漏
onUnmounted(() => {
  if (tabLoadTimer) {
    clearTimeout(tabLoadTimer)
    tabLoadTimer = null
  }
  window.removeEventListener('resize', handleResize)
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

  /* 修复容器宽度溢出问题 - 不允许横向滚动 */
  width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* Arco Spin 组件宽度约束 */
:deep(.arco-spin) {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

:deep(.arco-spin-nested-loading) {
  width: 100%;
  max-width: 100%;
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
  margin: 0 0 8px 0;
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
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: auto;
}

/* 双列信息网格 - 基础信息面板 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0;
  padding: 8px 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.info-item {
  display: flex;
  flex-direction: column;
  padding: 14px 16px;
  border-bottom: 1px solid var(--neutral-2);
  transition: background-color var(--transition-fast);
}

.info-item:hover {
  background-color: var(--neutral-1);
}

.info-item .label {
  font-size: 13px;
  font-weight: 600;
  color: var(--neutral-6);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}

.info-item .value {
  font-size: 14px;
  color: var(--neutral-10);
  font-weight: 500;
  line-height: 1.5;
}

/* 客户标签占满整行 */
.info-item.full-width {
  grid-column: 1 / -1;
}

/* 客户标签区域 */
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tags-container :deep(.arco-btn-text) {
  height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  transition: all var(--transition-fast);
  border: 1px dashed var(--neutral-6);
  background: transparent;
  color: var(--neutral-6);
  font-size: 13px;
}

.tags-container :deep(.arco-btn-text:hover) {
  border-color: var(--primary-6);
  background: var(--primary-1);
  color: var(--primary-6);
}

/* 响应式适配 - 平板及中等屏幕 */
@media (min-width: 375px) and (max-width: 768px) {
  .info-grid {
    grid-template-columns: 1fr;
  }

  .info-item .label {
    font-size: 12px;
  }

  .info-item .value {
    font-size: 14px;
  }
}


/* 表格自动布局 - 使用 auto 自适应，不强制固定宽度 */
:deep(.arco-table) {
  table-layout: auto;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box; /* 修复：Arco 默认 content-box + padding 导致溢出 */
}

/* 表格单元格内容不换行时截断显示 */
:deep(.arco-table-td),
:deep(.arco-table-th) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

:deep(.arco-table-wrapper) {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
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
.info-grid {
  min-height: 200px;
}

/* 响应式断点 */
/* XS Mobile - 374px and below */
@media (max-width: 374px) {
  .info-grid {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 16px 12px;
  }

  .info-item {
    padding: 12px;
    min-height: 80px;
  }

  .tabs-section {
    padding: 12px;
    border-radius: 12px;
  }

  .header-title h1 {
    font-size: 20px;
  }
}

/* Mobile - 375px to 767px */
@media (min-width: 375px) and (max-width: 767px) {

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
    padding: 20px 16px;
  }

  .header-title h1 {
    font-size: 22px;
  }

}

/* Tablet - 768px to 1199px */
@media (min-width: 768px) and (max-width: 1199px) {

  .tabs-section {
    padding: 28px;
  }
}



/* Ultra-wide screens - 1600px+ */
@media (min-width: 1600px) {
  .tabs-section {
    max-width: 1600px;
    margin: 0 auto;
  }
}


/* 用量分布区域 */
.usage-distribution-section {
  margin-bottom: 24px;
  width: 100%;
  box-sizing: border-box;
  min-height: 350px;
}

.usage-table-section {
  margin-top: 24px;
  width: 100%;
  box-sizing: border-box;
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

/* 扩展指标网格间距 */
.metrics-grid-extended {
  margin-top: 4px;
}

/* 备注文字样式 - 支持换行 */
.notes-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

/* ========== 编辑弹框三列布局 ========== */

/* 编辑表单网格容器 */
.edit-form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0 20px;
  width: 100%;
}

/* 编辑表单列 */
.edit-form-column {
  display: flex;
  flex-direction: column;
}

/* 列标题 */
.edit-form-column .column-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-6, #0369a1);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--primary-1, #e8f3ff);
}

/* 列分隔线 */
.edit-form-column + .edit-form-column {
  border-left: 1px solid var(--neutral-2, #eef0f3);
  padding-left: 20px;
}

/* 备注区域 - 横跨三列 */
.edit-form-note {
  grid-column: 1 / -1;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--neutral-2, #eef0f3);
}

/* 响应式降级：两列 */
@media (max-width: 1399px) {
  .edit-form-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .edit-form-column:nth-child(1) {
    border-right: 1px solid var(--neutral-2, #eef0f3);
    padding-right: 20px;
  }

  .edit-form-column:nth-child(2) {
    border-left: none;
    padding-left: 0;
  }

  .edit-form-column:nth-child(3) {
    border-top: 1px solid var(--neutral-2, #eef0f3);
    padding-top: 16px;
    margin-top: 16px;
    grid-column: 1 / -1;
  }

  .edit-form-column:nth-child(3) .column-title {
    margin-bottom: 12px;
  }
}

/* 响应式降级：单列 */
@media (max-width: 767px) {
  .edit-form-grid {
    grid-template-columns: 1fr;
  }

  .edit-form-column {
    border-left: none !important;
    border-right: none !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    border-top: none !important;
    padding-top: 0 !important;
    margin-top: 0 !important;
    grid-column: auto !important;
  }

  .edit-form-column + .edit-form-column {
    border-top: 1px solid var(--neutral-2, #eef0f3);
    padding-top: 16px;
    margin-top: 16px;
  }

  .edit-form-note {
    border-top: 1px solid var(--neutral-2, #eef0f3);
  }
}
</style>
