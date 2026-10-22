<template>
  <div class="filters-container">
    <div class="filters">
      <CustomerSearchInput v-model="filters.keyword" @search="emit('search')" />
      <FilterDropdown
        v-model="filters.status"
        label="状态"
        :options="statusOptions"
        @apply="emit('search')"
      />
      <FilterDropdown
        v-model="filters.industry_type"
        label="行业类型"
        :options="industryOptions"
        @apply="emit('search')"
      />
      <FilterDropdown
        v-model="filters.erp_system"
        label="ERP系统"
        :options="erpSystemOptions"
        @apply="emit('search')"
      />
      <FilterDropdown
        v-model="filters.manager_id"
        label="运营经理"
        :options="managerOptions"
        @apply="emit('search')"
      />
      <FilterDropdown
        v-model="filters.sales_manager_id"
        label="销售经理"
        :options="managerOptions"
        @apply="emit('search')"
      />
      <button type="button" class="btn primary" @click="emit('search')">筛选</button>
      <button type="button" class="btn" @click="emit('reset')">重置</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import { INVOICE_STATUS_OPTIONS } from '@/constants/invoiceStatus'
import { getIndustryTypes } from '@/api/customers'
import { getErpSystemsList } from '@/api/erpSystems'
import { getManagers } from '@/api/users'
import type { IndustryType, ErpSystem } from '@/types'

interface Filters {
  keyword: string
  status: string
  industry_type: string
  erp_system: string
  manager_id: string
  sales_manager_id: string
}

const filters = defineModel<Filters>('filters', { required: true })

const emit = defineEmits<{
  search: []
  reset: []
}>()

const statusOptions = INVOICE_STATUS_OPTIONS

// ===== 字典加载（镜像 useCustomerList 的防御式解包） =====
const industryTypes = ref<IndustryType[]>([])
const erpSystems = ref<ErpSystem[]>([])
const managers = ref<Array<{ id: number; real_name: string | null }>>([])

onMounted(async () => {
  try {
    const res = await getIndustryTypes()
    industryTypes.value = (res.data?.data || res.data || []) as IndustryType[]
  } catch (error) {
    console.error('加载行业类型失败:', error)
  }
  try {
    const res = await getErpSystemsList()
    erpSystems.value = (res.data?.data || res.data || []) as ErpSystem[]
  } catch (error) {
    console.error('加载 ERP 系统失败:', error)
  }
  try {
    const res = await getManagers()
    managers.value = (res.data?.data || res.data || []) as Array<{
      id: number
      real_name: string | null
    }>
  } catch (error) {
    console.error('加载经理列表失败:', error)
  }
})

// 行业按名称匹配（后端按 IndustryType.name 筛选）；ERP 按 value 匹配（Customer.erp_system）
const industryOptions = computed(() =>
  industryTypes.value.map((it) => ({ label: it.name, value: it.name }))
)

const erpSystemOptions = computed(() =>
  erpSystems.value.map((es) => ({ label: es.name, value: es.value }))
)

// 运营/销售经理下拉共用同一经理列表（后端分别按 manager_id / sales_manager_id 过滤）
const managerOptions = computed(() =>
  managers.value.map((m) => ({ label: m.real_name || `#${m.id}`, value: String(m.id) }))
)
</script>

<style scoped>
.filters-container {
  margin-bottom: 12px;
}

.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

/* 按钮基础样式（与全站 .btn 保持一致） */
.btn {
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: white;
  color: var(--ink);
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}
.btn.primary {
  padding: 9px 12px;
  border: 1px solid var(--primary);
  border-radius: 12px;
  background: var(--primary);
  color: white;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn.primary:hover {
  background: #1e40af;
}

@media (max-width: 1100px) {
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
