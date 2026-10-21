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
import type { IndustryType, ErpSystem } from '@/types'

interface Filters {
  keyword: string
  status: string
  industry_type: string
  erp_system: string
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
})

// 行业按名称匹配（后端按 IndustryType.name 筛选）；ERP 按 value 匹配（Customer.erp_system）
const industryOptions = computed(() =>
  industryTypes.value.map((it) => ({ label: it.name, value: it.name }))
)

const erpSystemOptions = computed(() =>
  erpSystems.value.map((es) => ({ label: es.name, value: es.value }))
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
