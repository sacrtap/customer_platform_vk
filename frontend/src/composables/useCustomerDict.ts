/**
 * 字典数据 composable — 加载并缓存客户经理、行业类型、合作状态、ERP 系统列表
 */
import { ref } from 'vue'
import { getManagers } from '@/api/users'
import { getIndustryTypes } from '@/api/customers'
import { getCooperationStatusesList } from '@/api/cooperationStatuses'
import { getErpSystemsList } from '@/api/erpSystems'
import type { User, IndustryType, CooperationStatus, ErpSystem } from '@/types'

export function useCustomerDict() {
  const managers = ref<User[]>([])
  const industryTypes = ref<IndustryType[]>([])
  const industryTypesLoading = ref(false)
  const cooperationStatuses = ref<CooperationStatus[]>([])
  const erpSystems = ref<ErpSystem[]>([])

  const loadManagers = async () => {
    try {
      const res = await getManagers()
      managers.value = res.data?.list || res.data || []
    } catch (error) {
      console.error('加载客户经理失败:', error)
    }
  }

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

  const loadCooperationStatuses = async () => {
    try {
      const res = await getCooperationStatusesList()
      cooperationStatuses.value = res.data?.data || res.data || []
    } catch (error) {
      console.error('加载合作状态失败:', error)
    }
  }

  const loadErpSystems = async () => {
    try {
      const res = await getErpSystemsList()
      erpSystems.value = res.data?.data || res.data || []
    } catch (error) {
      console.error('加载 ERP 系统失败:', error)
    }
  }

  const loadAllDictData = () => {
    loadManagers()
    loadIndustryTypes()
    loadCooperationStatuses()
    loadErpSystems()
  }

  return {
    managers,
    industryTypes,
    industryTypesLoading,
    cooperationStatuses,
    erpSystems,
    loadManagers,
    loadIndustryTypes,
    loadCooperationStatuses,
    loadErpSystems,
    loadAllDictData,
  }
}
