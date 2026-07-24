<template>
  <div class="pricing-rules-page">
    <!-- PageHeader -->
    <PageHeader eyebrow="Billing" title="计费规则" subtitle="管理客户定价、阶梯与包年计费规则">
      <template #actions>
        <button v-if="can('billing:edit')" class="btn primary" @click="showCreateModal">
          新建规则
        </button>
      </template>
    </PageHeader>

    <!-- 筛选 + 表格 在同一卡片内 -->
    <div class="card pad main-card">
      <!-- 筛选器 -->
      <div class="filters-container">
        <div class="filters">
          <CustomerSearchInput v-model="filters.keyword" @search="handleSearch" />
          <FilterDropdown
            v-model="filters.device_type"
            label="设备类型"
            :options="deviceTypeOptions"
            @apply="handleSearch"
          />
          <FilterDropdown
            v-model="filters.pricing_type"
            label="计费类型"
            :options="pricingTypeOptions"
            @apply="handleSearch"
          />
          <button type="button" class="btn primary" @click="handleSearch">筛选</button>
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-section">
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th style="width: 200px">客户</th>
                <th style="width: 100px">设备类型</th>
                <th style="width: 100px">楼层类型</th>
                <th style="width: 120px">计费类型</th>
                <th style="width: 100px">单价</th>
                <th style="width: 100px">套餐类型</th>
                <th style="width: 200px">有效期</th>
                <th style="width: 150px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in data" :key="record.id">
                <!-- 客户 -->
                <td>
                  <span v-if="record.customer_name" class="cust-name">{{
                    record.customer_name
                  }}</span>
                  <span v-else class="subtle">客户{{ record.customer_id }}</span>
                </td>
                <!-- 设备类型 -->
                <td>
                  <span class="tag" :class="getDeviceTypeTagClass(record.device_type)">
                    {{ record.device_type }}系列
                  </span>
                </td>
                <!-- 楼层类型 -->
                <td>
                  <span
                    v-if="record.layer_type"
                    class="tag"
                    :class="record.layer_type === 'multi' ? 'violet' : 'blue'"
                  >
                    {{ record.layer_type === 'multi' ? '多层' : '单层' }}
                  </span>
                  <span v-else class="subtle">-</span>
                </td>
                <!-- 计费类型 -->
                <td>
                  <span class="tag" :class="getPricingTypeTagClass(record.pricing_type)">
                    {{ getPricingTypeText(record.pricing_type) }}
                  </span>
                </td>
                <!-- 单价 -->
                <td>
                  <template v-if="record.pricing_type === 'fixed'">
                    <span v-if="record.unit_price" class="amount"
                      >¥{{ record.unit_price.toFixed(2) }}</span
                    >
                    <span v-else class="subtle">-</span>
                  </template>
                  <template v-else-if="record.pricing_type === 'tiered'">
                    <span
                      v-if="record.tiers"
                      class="tag green has-tooltip"
                      :data-tooltip="formatTiersTooltip(record.tiers)"
                    >
                      阶梯计价
                    </span>
                    <span v-else class="subtle">未配置</span>
                  </template>
                  <template v-else-if="record.pricing_type === 'package'">
                    <span class="tag amber">包年计费</span>
                  </template>
                  <span v-else class="subtle">-</span>
                </td>
                <!-- 套餐类型 -->
                <td>
                  <span v-if="record.package_type" class="tag violet"
                    >{{ record.package_type }} 套餐</span
                  >
                  <span v-else class="subtle">-</span>
                </td>
                <!-- 有效期 -->
                <td>
                  <span v-if="record.effective_date && record.expiry_date" class="cell-nowrap">
                    {{ record.effective_date }} 至 {{ record.expiry_date }}
                  </span>
                  <span v-else-if="record.effective_date" class="cell-nowrap">
                    {{ record.effective_date }} 起
                  </span>
                  <span v-else class="subtle">-</span>
                </td>
                <!-- 操作 -->
                <td style="white-space: nowrap">
                  <button
                    v-if="can('billing:edit')"
                    class="btn"
                    style="padding: 4px 10px; font-size: 12px"
                    @click="showEditModal(record)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="can('billing:delete')"
                    class="btn btn-danger"
                    style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
                    @click="handleDelete(record)"
                  >
                    删除
                  </button>
                </td>
              </tr>
              <tr v-if="data.length === 0 && !loading">
                <td :colspan="8" class="empty-state">暂无计费规则数据</td>
              </tr>
              <tr v-if="loading">
                <td :colspan="8" class="loading-state">加载中...</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页 -->
        <div class="pagination">
          <span class="page-total">共 {{ pagination.total.toLocaleString() }} 条</span>
          <div class="pagination-right">
            <span class="page-size">
              每页
              <select
                class="page-size-select"
                :value="pagination.pageSize"
                @change="onPageSizeChange"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">
                  {{ size }}
                </option>
              </select>
              条
            </span>
            <div class="page-controls">
              <button
                class="page-btn"
                :disabled="pagination.current <= 1"
                @click="onPageChange(pagination.current - 1)"
              >
                ‹
              </button>
              <button
                v-for="p in displayPages"
                :key="p"
                class="page-btn"
                :class="{ active: p === pagination.current, ellipsis: p === -1 }"
                :disabled="p === -1"
                @click="p > 0 && onPageChange(p)"
              >
                {{ p === -1 ? '…' : p }}
              </button>
              <button
                class="page-btn"
                :disabled="pagination.current >= totalPages"
                @click="onPageChange(pagination.current + 1)"
              >
                ›
              </button>
            </div>
            <span class="page-jump">
              跳至
              <input
                type="number"
                class="page-jump-input"
                :value="pagination.current"
                :min="1"
                :max="totalPages"
                @keydown.enter="onJumpPage(($event.target as HTMLInputElement).value)"
              />
              页
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建/编辑规则弹窗 -->
    <PricingRuleModal
      v-model:visible="modalVisible"
      :edit-data="editData"
      :package-plan-options="packagePlanOptions"
      @saved="onModalSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import * as billingApi from '@/api/billing'
import PageHeader from '@/components/PageHeader.vue'
import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import PricingRuleModal from './components/PricingRuleModal.vue'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

interface PricingRule {
  id: number
  customer_id?: number
  customer_name?: string
  device_type: string
  layer_type?: string
  pricing_type: 'fixed' | 'tiered' | 'package'
  unit_price?: number
  tiers?: Array<{ min: number; max: number | null; price: number }> | Record<string, unknown>
  package_type?: string
  package_limits?: Record<string, unknown>
  effective_date?: string
  expiry_date?: string | null
}

// 筛选选项
const deviceTypeOptions = [
  { label: 'X 系列', value: 'X' },
  { label: 'N 系列', value: 'N' },
  { label: 'L 系列', value: 'L' },
]

const pricingTypeOptions = [
  { label: '定价结算', value: 'fixed' },
  { label: '阶梯结算', value: 'tiered' },
  { label: '包年结算', value: 'package' },
]

const data = ref<PricingRule[]>([])
const loading = ref(false)
const packagePlanOptions = ref<billingApi.PackagePlan[]>([])

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})

const pageSizeOptions = [10, 20, 50, 100]

const filters = reactive({
  keyword: '',
  device_type: '',
  pricing_type: '',
})

const modalVisible = ref(false)
const editData = ref<PricingRule | null>(null)

// --- 标签样式辅助 ---
const getPricingTypeText = (type: string) => {
  const map: Record<string, string> = {
    fixed: '定价结算',
    tiered: '阶梯结算',
    package: '包年结算',
  }
  return map[type] || type
}

const getDeviceTypeTagClass = (type: string) => {
  const map: Record<string, string> = {
    X: 'blue',
    N: 'green',
    L: 'amber',
  }
  return map[type] || 'gray'
}

const getPricingTypeTagClass = (type: string) => {
  const map: Record<string, string> = {
    fixed: 'blue',
    tiered: 'green',
    package: 'amber',
  }
  return map[type] || 'gray'
}

// 获取启用的包年套餐选项
const fetchPackagePlanOptions = async () => {
  try {
    const res = await billingApi.getPackagePlans({ status: 'active', page_size: 100 })
    packagePlanOptions.value = res.data.list || []
  } catch {
    packagePlanOptions.value = []
  }
}

// --- 分页计算 ---
const totalPages = computed(() => Math.ceil(pagination.total / pagination.pageSize) || 1)

const displayPages = computed(() => {
  const current = pagination.current
  const total = totalPages.value
  const pages: number[] = []

  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else {
    pages.push(1)
    if (current > 3) pages.push(-1)
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    if (current < total - 2) pages.push(-1)
    pages.push(total)
  }
  return pages
})

const onPageChange = (page: number) => {
  if (page < 1 || page > totalPages.value) return
  pagination.current = page
  fetchData()
}

const onPageSizeChange = (e: Event) => {
  pagination.pageSize = Number((e.target as HTMLSelectElement).value)
  pagination.current = 1
  fetchData()
}

const onJumpPage = (val: string) => {
  const page = parseInt(val)
  if (page >= 1 && page <= totalPages.value) {
    onPageChange(page)
  }
}

// --- 数据请求 ---
const fetchData = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.device_type) params.device_type = filters.device_type
    if (filters.pricing_type) params.pricing_type = filters.pricing_type

    const res = await billingApi.getPricingRules(params)
    data.value = res.data.list || []
    pagination.total = res.data.total || data.value.length
    pagination.pageSize = res.data.page_size || pagination.pageSize
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchData()
}

const _handleReset = () => {
  filters.keyword = ''
  filters.device_type = ''
  filters.pricing_type = ''
  pagination.current = 1
  fetchData()
}

const showCreateModal = () => {
  editData.value = null
  modalVisible.value = true
}

const showEditModal = (record: PricingRule) => {
  editData.value = record
  modalVisible.value = true
}

const onModalSaved = () => {
  fetchData()
}

// 格式化阶梯配置的 tooltip 内容
const formatTiersTooltip = (tiers: Record<string, unknown> | undefined): string => {
  if (!tiers) return '未配置阶梯'
  let ranges: Array<{ min: number; max: number | null; price: number }> = []
  if (Array.isArray(tiers)) {
    ranges = tiers as Array<{ min: number; max: number | null; price: number }>
  } else if (typeof tiers === 'object' && tiers !== null && 'ranges' in tiers) {
    ranges = (tiers as { ranges: Array<{ min: number; max: number | null; price: number }> }).ranges
  }
  if (!ranges || ranges.length === 0) return '未配置阶梯'
  return ranges
    .map((r) => {
      const maxStr = r.max === null || r.max === undefined ? '不限' : r.max
      return `${r.min}-${maxStr}: ¥${r.price}`
    })
    .join('\n')
}

const handleDelete = (record: PricingRule) => {
  Modal.confirm({
    title: '确认删除',
    content: '确定要删除此定价规则吗？此操作不可恢复。',
    onOk: async () => {
      try {
        await billingApi.deletePricingRule(record.id)
        Message.success('删除成功')
        fetchData()
      } catch (err: unknown) {
        Message.error((err as Error)?.message || '删除失败')
      }
    },
  })
}

onMounted(() => {
  fetchData()
  fetchPackagePlanOptions()
})
</script>

<style scoped>
.pricing-rules-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px 44px;
  max-width: 1440px;
  margin: 0 auto;
}

/* 覆盖 PageHeader 的 margin-bottom，使用 gap 控制间距 */
.pricing-rules-page :deep(.page-header) {
  margin-bottom: 0;
}

/* 按钮样式 */
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 12px;
  cursor: pointer;
  font-weight: 700;
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
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}
.btn.primary:hover {
  background: #1e40af;
}
.btn.btn-danger {
  color: var(--red);
  border-color: #fecaca;
}
.btn.btn-danger:hover {
  background: #fef2f2;
  border-color: #fca5a5;
}

/* 筛选器 */
.filters-container {
  margin-bottom: 12px;
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

/* 表格容器 */
.table-section {
  display: flex;
  flex-direction: column;
}
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 15px;
}

/* 表格 */
.table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  table-layout: auto;
}
.table th,
.table td {
  padding: 10px 10px;
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  white-space: nowrap;
}
.table th {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}
.table tbody tr {
  transition: background 0.15s;
}
.table tbody tr:hover td {
  background: #f8fbff;
}

/* 客户名称 */
.cust-name {
  font-weight: 600;
  color: var(--ink);
}

/* 阶梯配置编辑器 */
.tier-editor {
  margin-bottom: 16px;
}
.tier-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.tier-editor-title {
  font-weight: 600;
  color: var(--ink);
  font-size: 14px;
}
.tier-add-btn {
  padding: 5px 12px;
  font-size: 12px;
}
.tier-empty {
  text-align: center;
  padding: 24px;
  color: var(--muted);
  background: #f8fafc;
  border: 1px dashed var(--line);
  border-radius: 10px;
  font-size: 13px;
}
.tier-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid var(--line);
  border-radius: 10px;
  margin-bottom: 8px;
}
.tier-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 32px;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.tier-field {
  flex: 1;
  min-width: 0;
}
.tier-label {
  display: block;
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 4px;
  font-weight: 500;
}
.tier-max-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tier-max-wrap :deep(.arco-checkbox) {
  font-size: 12px;
  white-space: nowrap;
}
.tier-min-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}
.tier-auto-btn {
  flex-shrink: 0;
  border: 1px solid var(--line);
  background: #f1f5f9;
  color: var(--muted);
  border-radius: 6px;
  padding: 0 8px;
  height: 32px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.tier-auto-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: #eff6ff;
}
/* 阶梯输入框校验错误时的红色边框 */
.tier-input-error :deep(.arco-input-wrapper) {
  border-color: #ef4444 !important;
  background-color: #fef2f2 !important;
}
.tier-input-error :deep(.arco-input-wrapper:hover) {
  border-color: #ef4444 !important;
}
.tier-del-btn {
  padding: 6px 10px;
  font-size: 12px;
  flex-shrink: 0;
}
.tier-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.5;
}
.tier-error {
  margin-top: 4px;
  margin-left: 36px;
  font-size: 12px;
  color: var(--red, #ef4444);
  line-height: 1.4;
}
.form-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.4;
}

/* 金额 */
.amount {
  font-weight: 500;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.cell-nowrap {
  white-space: nowrap;
}

/* 空状态 / 加载状态 */
.empty-state,
.loading-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
  font-size: 14px;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #edf2f7;
}
.page-total {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.pagination-right {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}
.page-size {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.page-size-select {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 3px 6px;
  font: inherit;
  font-size: 12px;
  color: var(--ink);
  background: #fff;
  cursor: pointer;
}
.page-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}
.page-btn {
  min-width: 32px;
  height: 32px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 8px;
  padding: 0 8px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.page-btn:hover:not(:disabled):not(.active) {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}
.page-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  cursor: default;
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-btn.ellipsis {
  border: none;
  background: transparent;
  cursor: default;
  opacity: 1;
}
.page-jump {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.page-jump-input {
  width: 48px;
  height: 30px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 6px;
  font: inherit;
  font-size: 12px;
  text-align: center;
  color: var(--ink);
  background: #fff;
}
.page-jump-input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(147, 197, 253, 0.2);
}

@media (max-width: 640px) {
  .pagination {
    justify-content: center;
  }
  .page-size,
  .page-jump {
    display: none;
  }
}
</style>
