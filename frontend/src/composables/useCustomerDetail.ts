import { ref, reactive, computed, onMounted, onUnmounted, onUpdated, watch } from 'vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getCustomer, updateCustomer, getProfile, updateProfile, getIndustryTypes } from '@/api/customers'
import { getCustomerBalance, getInvoices, getBalanceTrend } from '@/api/billing'
import type { Invoice, BalanceTrendItem } from '@/api/billing'
import { getTags, getCustomerTags, addCustomerTag, removeCustomerTag } from '@/api/tags'
import { getDailyUsage } from '@/api/usage'
import type { DailyUsage } from '@/api/usage'
import { getManagers } from '@/api/users'
import { getCustomerHealthScore } from '@/api/analytics'
import type { CustomerHealthScore } from '@/api/analytics'
import type { Customer, CustomerProfile, Balance, Tag, User, IndustryType } from '@/types'
import { useCustomerStore } from '@/stores/customer'

export interface EditForm {
  name: string
  company_id: number
  email: string
  account_type?: string
  industry_type_id: number | null
  price_policy?: string
  settlement_type?: string
  settlement_cycle?: string
  is_key_customer: boolean
  manager_id?: number
  erp_system?: string
  first_payment_date?: string
  onboarding_date?: string
  sales_manager_id?: number
  cooperation_status?: string
  is_settlement_enabled: boolean
  is_disabled: boolean
  notes?: string
  is_real_estate: boolean | null
  scale_level?: string
  consume_level?: string
}

export function useCustomerDetail() {
  const route = useRoute()
  console.log('[useCustomerDetail] called, route.params.id =', route.params.id)
  const router = useRouter()
  const customerStore = useCustomerStore()

  const customerId = ref(Number(route.params.id))

  const customer = ref<Customer | null>(null)
  const loading = ref(true)
  const activeTab = ref('basic')

  const balance = ref<Balance | undefined>(undefined)
  const balanceLoading = ref(false)

  const profile = ref<CustomerProfile | null>(null)
  const profileLoading = ref(false)

  const invoices = ref<Invoice[]>([])

  const usageData = ref<DailyUsage[]>([])
  const usageLoading = ref(false)
  const usagePagination = ref({ current: 1, pageSize: 20, total: 0 })

  const healthScore = ref<CustomerHealthScore | null>(null)
  const healthScoreLoading = ref(false)
  const balanceTrend = ref<BalanceTrendItem[]>([])
  const balanceTrendLoading = ref(false)
  const usageDistribution = ref<{ device_type: string; quantity: number; percentage: number }[]>([])
  const totalUsageQuantity = ref(0)

  const editModalVisible = ref(false)
  const editFormRef = ref<FormInstance>()
  const editLoading = ref(false)
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

  const tagSelectorVisible = ref(false)
  const tagSelectorLoading = ref(false)
  const customerTags = ref<Tag[]>([])
  const allTags = ref<Tag[]>([])
  const selectedTags = ref<Tag[]>([])
  const managers = ref<User[]>([])
  const industryTypes = ref<IndustryType[]>([])
  const pricePolicyOptions = [
    { label: '定价', value: 'pricing' },
    { label: '阶梯', value: 'tiered' },
    { label: '包年', value: 'yearly' },
  ]

  const keyCustomerLoading = ref(false)
  const industryTypesLoading = ref(false)
  const allTagsLoading = ref(false)

  const modalWidth = computed(() => {
    if (typeof window === 'undefined') return '1100px'
    const width = window.innerWidth
    if (width >= 1400) return '1100px'
    if (width >= 768) return '800px'
    return '100%'
  })

  const consumeLevelDisplay = computed(() => {
    if (!profile.value?.consume_level) return '-'
    const levelMap: Record<string, string> = { high: '高', medium: '中', low: '低' }
    return levelMap[profile.value.consume_level] || profile.value.consume_level
  })

  const profileExtensionList = computed(() => [
    { label: '月均拍摄量（实际）', value: profile.value?.monthly_avg_shots ?? '-' },
    { label: '月均拍摄量（预估）', value: profile.value?.monthly_avg_shots_estimated ?? '-' },
    { label: '预估年消费', value: profile.value?.estimated_annual_spend ?? '-' },
    { label: '2025年实际消费', value: profile.value?.actual_annual_spend_2025 ?? '-' },
  ])

  const loadedTabs = ref<Set<string>>(new Set(['basic']))
  const chartRenderState = ref<Record<string, boolean>>({})
  const shouldRenderBalanceTrend = computed(() => chartRenderState.value.balanceTrend ?? false)
  let tabLoadTimer: ReturnType<typeof setTimeout> | null = null

  const markChartForRender = (chartId: string): void => {
    chartRenderState.value[chartId] = true
  }

  const loadDetail = async () => {
    // 防御: 防止无效 customerId 导致 API 挂起
    if (!customerId.value || isNaN(customerId.value) || customerId.value <= 0) {
      console.error('[loadDetail] Invalid customerId:', customerId.value)
      Message.error('无效的客户 ID，请检查路由参数')
      loading.value = false
      return
    }
    loading.value = true
    console.log('[loadDetail] started, loading =', loading.value)
    try {
      const [customerRes, profileRes, balanceRes, invoicesRes] = await Promise.all([
        getCustomer(customerId.value),
        getProfile(customerId.value).catch(() => null),
        getCustomerBalance(customerId.value).catch(() => null),
        getInvoices({ customer_id: customerId.value, page_size: 100 }).catch(() => null),
      ])
      console.log('[loadDetail] API all resolved')
      customer.value = customerRes.data
      profile.value = profileRes?.data || null
      balance.value = balanceRes?.data
      invoices.value = invoicesRes?.data?.list || []
    } catch (error) {
      console.error('[loadDetail] API error:', error)
      Message.error('加载客户数据失败')
    } finally {
      loading.value = false
      console.log('[loadDetail] finally block, loading =', loading.value)
    }
  }

  const loadBalance = async () => {
    balanceLoading.value = true
    try {
      const [balanceRes, trendRes] = await Promise.all([
        getCustomerBalance(customerId.value),
        getBalanceTrend(customerId.value).catch(() => null),
      ])
      balance.value = balanceRes.data
      balanceTrend.value = trendRes?.data || []
      balanceTrendLoading.value = false
    } catch (error) {
      Message.error('加载余额数据失败')
      console.error('加载余额数据失败:', error)
    } finally {
      balanceLoading.value = false
    }
  }

  const loadProfile = async () => {
    profileLoading.value = true
    try {
      const [profileRes, healthRes] = await Promise.all([
        getProfile(customerId.value),
        getCustomerHealthScore(customerId.value).catch(() => null),
      ])
      profile.value = profileRes.data
      healthScore.value = healthRes?.data || null
      healthScoreLoading.value = false
    } catch (error) {
      Message.error('加载画像数据失败')
      console.error('加载画像数据失败:', error)
    } finally {
      profileLoading.value = false
    }
  }

  const loadInvoices = async () => {
    try {
      const res = await getInvoices({ customer_id: customerId.value, page_size: 100 })
      invoices.value = res.data?.list || []
    } catch (error) {
      Message.error('加载结算单失败')
      console.error('加载结算单失败:', error)
    }
  }

  const loadUsage = async (page?: number) => {
    usageLoading.value = true
    try {
      const currentPage = page || usagePagination.value.current
      const res = await getDailyUsage({
        customer_id: customerId.value,
        page: currentPage,
        page_size: usagePagination.value.pageSize,
      })
      usageData.value = res.data?.list || []
      usagePagination.value.total = res.data?.total || 0
    } catch (error: unknown) {
      // 后端未实现用量 API 时优雅降级，显示空状态而非错误提示
      usageData.value = []
      usagePagination.value.total = 0
      console.warn('[loadUsage] API error (showing empty state):', error)
    } finally {
      usageLoading.value = false
    }
  }

  const handleTabChange = (tabKey: string): void => {
    activeTab.value = tabKey
    if (!loadedTabs.value.has(tabKey)) {
      loadedTabs.value.add(tabKey)
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
    if (tabKey === 'profile' && !profile.value?.scale_level) loadProfile()
    if (tabKey === 'balance' && !balance.value?.total_amount) loadBalance()
    if (tabKey === 'invoices' && !invoices.value.length) loadInvoices()
    if (tabKey === 'usage' && !usageData.value.length) loadUsage()
  }

  const goBack = () => { router.back() }

  const getStatusClass = (status: string) => {
    const map: Record<string, string> = {
      draft: 'warning', pending_customer: 'warning', customer_confirmed: 'success',
      paid: 'success', completed: 'success', cancelled: 'danger',
    }
    return map[status] || 'warning'
  }

  const getStatusText = (status: string) => {
    const map: Record<string, string> = {
      draft: '草稿', pending_customer: '待客户确认', customer_confirmed: '客户已确认',
      paid: '已付款', completed: '已完成', cancelled: '已取消',
    }
    return map[status] || status
  }

  const openEdit = () => {
    if (profileLoading.value || !profile.value) {
      Message.warning('客户画像数据加载中，请稍后编辑')
      return
    }
    Object.assign(editForm, {
      name: customer.value?.name || '',
      company_id: Number(customer.value?.company_id) || 0,
      email: customer.value?.email as string ?? '',
      account_type: customer.value?.account_type || undefined,
      industry_type_id: profile.value?.industry_type_id as number | null ?? null,
      price_policy: customer.value?.price_policy || undefined,
      settlement_type: customer.value?.settlement_type || undefined,
      settlement_cycle: customer.value?.settlement_cycle || undefined,
      is_key_customer: customer.value?.is_key_customer || false,
      manager_id: customer.value?.manager_id || undefined,
      erp_system: customer.value?.erp_system || undefined,
      first_payment_date: customer.value?.first_payment_date || undefined,
      onboarding_date: customer.value?.onboarding_date || undefined,
      sales_manager_id: customer.value?.sales_manager_id || undefined,
      cooperation_status: customer.value?.cooperation_status || undefined,
      is_settlement_enabled: customer.value?.is_settlement_enabled ?? true,
      is_disabled: customer.value?.is_disabled ?? false,
      notes: customer.value?.notes || undefined,
      is_real_estate: customer.value?.is_real_estate as boolean | null ?? null,
      scale_level: profile.value?.scale_level || undefined,
      consume_level: profile.value?.consume_level || undefined,
    })
    editModalVisible.value = true
  }

  const closeEdit = () => {
    editModalVisible.value = false
    editFormRef.value?.resetFields()
  }

  const submitEdit = async (form: EditForm) => {
    editLoading.value = true
    try {
      await editFormRef.value?.validate()
      const editForm = form
      const [basicRes, profileRes] = await Promise.all([
        updateCustomer(customerId.value, form),
        editForm.scale_level || editForm.consume_level
          ? updateProfile(customerId.value, {
              scale_level: editForm.scale_level,
              consume_level: editForm.consume_level,
              industry_type_id: editForm.industry_type_id,
            })
          : Promise.resolve(null),
      ])
      customer.value = basicRes.data
      if (profileRes?.data) profile.value = profileRes.data
      if (basicRes.data) {
        customerStore.updateCachedCustomerPart(customerId.value, 'customer', basicRes.data as Customer)
      }
      closeEdit()
      Message.success('客户信息已更新')
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

  const toggleKeyCustomer = async () => {
    keyCustomerLoading.value = true
    try {
      const wasKeyCustomer = customer.value?.is_key_customer
      await updateCustomer(customerId.value, {
        is_key_customer: !wasKeyCustomer,
      })
      Message.success(wasKeyCustomer ? '已取消重点客户' : '已设为重点客户')
      if (customer.value) {
        customer.value.is_key_customer = !wasKeyCustomer
        customerStore.updateCachedCustomerPart(customerId.value, 'customer', customer.value)
      }
    } catch (error) {
      Message.error('操作失败')
      console.error('切换重点客户失败:', error)
    } finally {
      keyCustomerLoading.value = false
    }
  }

  const viewInvoice = (record: Invoice) => {
    Message.info(`查看结算单：${record.invoice_no}`)
  }

  const loadCustomerTags = async () => {
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
      allTags.value = allTagsRes.data || []
      customerStore.cacheTagsData(customerId.value, {
        customerTags: customerTags.value,
        allTags: allTags.value,
      })
    } catch (error) {
      Message.error('加载标签失败')
      console.error('加载标签失败:', error)
    }
  }

  const openTagSelector = async () => {
    tagSelectorVisible.value = true
    await loadCustomerTags()
    selectedTags.value = []
  }

  const closeTagSelector = () => {
    tagSelectorVisible.value = false
    selectedTags.value = []
  }

  const addTags = async (tagIds: number[]) => {
    tagSelectorLoading.value = true
    try {
      await Promise.all(tagIds.map((tagId) => addCustomerTag(customerId.value, tagId)))
      Message.success('标签已添加')
      await loadCustomerTags()
      closeTagSelector()
    } catch (error) {
      Message.error('添加标签失败')
      console.error('添加标签失败:', error)
    } finally {
      tagSelectorLoading.value = false
    }
  }

  const removeTag = async (tagId: number) => {
    try {
      await removeCustomerTag(customerId.value, tagId)
      Message.success('标签已移除')
      await loadCustomerTags()
    } catch (error) {
      Message.error('移除标签失败')
      console.error('移除标签失败:', error)
    }
  }

  const loadManagers = async () => {
    try {
      const res = await getManagers()
      managers.value = res.data || []
    } catch (error) {
      console.error('加载客户经理失败:', error)
    }
  }

  const loadIndustryTypes = async () => {
    try {
      const res = await getIndustryTypes()
      industryTypes.value = res.data || []
    } catch (error) {
      console.error('加载行业类型失败:', error)
    }
  }

  // 诊断: 追踪 loading 状态变化
  watch(loading, (val) => {
    console.log('[watch] loading changed to:', val)
  }, { immediate: true })

  onMounted(() => {
    console.log('[useCustomerDetail] onMounted fired')
    loadDetail()
    loadManagers()
    loadIndustryTypes()
  })

  onUpdated(() => {
    console.log('[onUpdated] loading =', loading.value)
  })

  onUnmounted(() => {
    if (tabLoadTimer) clearTimeout(tabLoadTimer)
  })

  return {
    customer, loading, activeTab,
    balance, balanceLoading,
    profile, profileLoading,
    invoices,
    usageData, usageLoading, usagePagination,
    healthScore, healthScoreLoading, balanceTrend, balanceTrendLoading, shouldRenderBalanceTrend,
    usageDistribution, totalUsageQuantity,
    editModalVisible, editForm, editFormRef, editLoading, modalWidth,
    tagSelectorVisible, tagSelectorLoading, selectedTags,
    customerTags, allTags, allTagsLoading,
    managers, industryTypes, industryTypesLoading, pricePolicyOptions,
    keyCustomerLoading,
    consumeLevelDisplay, profileExtensionList,
    loadDetail, loadBalance, loadProfile, loadInvoices, loadUsage,
    handleTabChange, getStatusClass, getStatusText,
    goBack, openEdit, closeEdit, submitEdit, toggleKeyCustomer, viewInvoice,
    openTagSelector, closeTagSelector, addTags, removeTag,
    loadManagers, loadIndustryTypes,
  }
}
