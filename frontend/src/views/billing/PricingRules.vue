<template>
  <div class="pricing-rules-page">
    <!-- PageHeader -->
    <PageHeader eyebrow="Billing" title="计费规则" subtitle="管理客户定价、阶梯与包年计费规则">
      <template #actions>
        <button v-if="can('billing:pricing_import')" class="btn" @click="importModalVisible = true">
          导入规则
        </button>
        <button
          v-if="can('billing:pricing_export')"
          class="btn"
          :disabled="exporting"
          @click="handleExport"
        >
          {{ exporting ? '导出中...' : '导出' }}
        </button>
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
          <button type="button" class="btn" @click="handleReset">重置</button>
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-section">
        <!-- 规则优先级说明 -->
        <div class="priority-hint">
          <span class="hint-icon">ⓘ</span>
          规则匹配优先级：1) 设备类型精确匹配 2) 有效期最新的规则 3) 创建时间最早的规则
        </div>
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
                  <span
                    v-if="record.device_type"
                    class="tag"
                    :class="getDeviceTypeTagClass(record.device_type)"
                  >
                    {{ record.device_type }}系列
                  </span>
                  <span v-else class="subtle">-</span>
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
                    <template v-if="record.unit_price">
                      <span class="amount">¥{{ record.unit_price.toFixed(2) }}</span>
                      <span
                        v-if="
                          record.multi_floor_pricing_type === 'incremental' &&
                          record.additional_floor_price
                        "
                        class="subtle incremental-price"
                      >
                        + 其他层 ¥{{ record.additional_floor_price.toFixed(2) }}
                      </span>
                    </template>
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
                    {{ formatDate(record.effective_date) }} 至 {{ formatDate(record.expiry_date) }}
                  </span>
                  <span v-else-if="record.effective_date" class="cell-nowrap">
                    {{ formatDate(record.effective_date) }} 起
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
        <Pagination
          :current="pagination.current"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @page-change="onPageChange"
          @page-size-change="onPageSizeChange"
        />
      </div>
    </div>

    <!-- 创建/编辑规则弹窗 -->
    <PricingRuleModal
      v-model:visible="modalVisible"
      :edit-data="editData"
      :package-plan-options="packagePlanOptions"
      @saved="onModalSaved"
    />

    <!-- 导入弹窗 -->
    <ImportModal
      v-model:visible="importModalVisible"
      title="批量导入计费规则"
      :import-api="billingApi.importPricingRules"
      :template-api="billingApi.downloadPricingRuleTemplate"
      template-file-name="计费规则导入模板.xlsx"
      @success="fetchData"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import * as billingApi from '@/api/billing'
import PageHeader from '@/components/PageHeader.vue'
import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import PricingRuleModal from './components/PricingRuleModal.vue'
import ImportModal from './components/ImportModal.vue'
import Pagination from '@/components/ui/Pagination.vue'
import { formatDate } from '@/utils/formatters'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

interface PricingRule {
  id: number
  customer_id?: number
  customer_name?: string
  device_type?: string
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

const filters = reactive({
  keyword: '',
  device_type: '',
  pricing_type: '',
})

const modalVisible = ref(false)
const editData = ref<PricingRule | null>(null)

// --- 导入 / 导出 ---
const importModalVisible = ref(false)
const exporting = ref(false)

// 导出计费规则：按当前筛选条件导出全部匹配数据
const handleExport = async () => {
  exporting.value = true
  try {
    const res = await billingApi.exportPricingRules({
      keyword: filters.keyword || undefined,
      device_type: filters.device_type || undefined,
      pricing_type: filters.pricing_type || undefined,
    })
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `pricing_rules_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    Message.success('导出成功')
  } catch (err: unknown) {
    Message.error((err as Error)?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

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
const onPageChange = (page: number) => {
  pagination.current = page
  fetchData()
}

const onPageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  fetchData()
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

const handleReset = () => {
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
.priority-hint {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 10px;
}
.hint-icon {
  margin-right: 4px;
  font-weight: 700;
}
.pricing-rules-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
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

.incremental-price {
  display: block;
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
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

@media (max-width: 1100px) {
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
