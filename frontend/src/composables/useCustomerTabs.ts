/**
 * Tab 懒加载 + 图表渲染状态管理 composable
 */
import { ref, computed, onUnmounted } from 'vue'

export function useCustomerTabs() {
  const activeTab = ref('basic')
  const loadedTabs = ref<Set<string>>(new Set(['basic']))
  const chartRenderState = ref<Record<string, boolean>>({})
  const shouldRenderBalanceTrend = computed(() => chartRenderState.value.balanceTrend ?? false)

  let tabLoadTimer: ReturnType<typeof setTimeout> | null = null

  const markChartForRender = (chartId: string): void => {
    chartRenderState.value[chartId] = true
  }

  /**
   * 处理 Tab 切换，返回需要加载的数据类型（或 null 表示已加载过）
   */
  const handleTabChange = (tabKey: string): 'profile' | 'balance' | 'invoices' | 'usage' | null => {
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
      // 返回需要首次加载的 tab key
      if (tabKey === 'profile') return 'profile'
      if (tabKey === 'balance') return 'balance'
      if (tabKey === 'invoices') return 'invoices'
      if (tabKey === 'usage') return 'usage'
    }
    return null
  }

  onUnmounted(() => {
    if (tabLoadTimer) clearTimeout(tabLoadTimer)
  })

  return {
    activeTab,
    loadedTabs,
    chartRenderState,
    shouldRenderBalanceTrend,
    markChartForRender,
    handleTabChange,
  }
}
