<template>
  <div class="balance-whitelist-page">
    <PageHeader
      eyebrow="System"
      title="余额白名单"
      subtitle="白名单客户通过开放平台 /api/v1/balances 接口按静态余额返回"
    >
      <template #actions>
        <a-button v-if="can('balance_whitelist:manage')" @click="handleOpenBatchImport"
          >按 ERP 批量导入</a-button
        >
        <a-button v-if="can('balance_whitelist:manage')" type="primary" @click="handleOpenAdd"
          >添加客户</a-button
        >
      </template>
    </PageHeader>

    <div class="table-section">
      <div class="search-bar">
        <a-input
          v-model="keyword"
          placeholder="按客户名称 / 公司 ID 搜索"
          allow-clear
          style="width: 260px"
          @press-enter="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix><icon-search /></template>
        </a-input>
        <a-button @click="handleSearch">搜索</a-button>
      </div>

      <a-table
        :columns="columns"
        :data="items"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #static_balance="{ record }">
          <span class="balance-cell">¥ {{ formatMoney(record.static_balance) }}</span>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button
              v-if="can('balance_whitelist:manage')"
              type="text"
              size="small"
              @click="handleOpenEdit(record)"
            >
              编辑余额
            </a-button>
            <a-popconfirm
              v-if="can('balance_whitelist:manage')"
              content="确认将该客户移出白名单？移出后接口将恢复返回真实计算余额。"
              @ok="handleRemove(record.id)"
            >
              <a-button type="text" size="small" status="danger"> 移出 </a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template #created_at="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
        <template #empty>
          <EmptyState
            title="暂无白名单客户"
            description="点击「按 ERP 批量导入」或「添加客户」建立余额白名单"
          />
        </template>
      </a-table>
    </div>

    <!-- 按 ERP 批量导入弹窗（两步：预检 → 确认导入） -->
    <a-modal
      v-model:visible="batchImportVisible"
      title="按 ERP 批量导入"
      :ok-text="batchImportConfirmed ? '确认导入' : '预检查'"
      :ok-button-props="{ disabled: !selectedErpValue }"
      :confirm-loading="batchImportSubmitting"
      width="560px"
      @before-ok="handleBatchImportSubmit"
      @cancel="handleBatchImportCancel"
    >
      <a-form layout="vertical">
        <a-form-item label="选择 ERP 名单" required>
          <a-select
            v-model="selectedErpValue"
            :options="erpOptions"
            placeholder="请选择 ERP 系统"
            :loading="erpLoading"
            @change="handleErpChange"
          />
        </a-form-item>

        <a-alert v-if="previewResult" type="info" style="margin-top: 12px">
          <template #title>预检查结果</template>
          将导入 <b>{{ previewResult.imported }}</b> 条，已存在跳过
          <b>{{ previewResult.skipped }}</b> 条（已存在客户不覆盖其既有静态余额）
        </a-alert>
        <a-alert
          v-if="batchImportDone"
          type="success"
          style="margin-top: 12px"
          title="导入完成"
          :content="`成功导入 ${lastImport.imported} 条，跳过 ${lastImport.skipped} 条`"
        />
      </a-form>
    </a-modal>

    <!-- 添加客户弹窗 -->
    <a-modal
      v-model:visible="addVisible"
      title="添加客户到白名单"
      :confirm-loading="submitting"
      width="520px"
      @before-ok="handleAddSubmit"
      @cancel="handleAddCancel"
    >
      <a-form ref="addFormRef" :model="addForm" :rules="addFormRules" layout="vertical">
        <a-form-item field="customer_id" label="客户" required>
          <CustomerAutoComplete
            :key="addCustomerPickerKey"
            v-model="addForm.customer_id"
            placeholder="输入客户名称搜索选择"
            width="100%"
          />
        </a-form-item>
        <a-form-item field="static_balance" label="静态余额（元）">
          <a-input-number
            v-model="addForm.static_balance"
            placeholder="默认 1000 元"
            :min="0"
            :precision="2"
            style="width: 100%"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 编辑余额弹窗 -->
    <a-modal
      v-model:visible="editVisible"
      title="编辑静态余额"
      :confirm-loading="submitting"
      width="420px"
      @before-ok="handleEditSubmit"
      @cancel="handleEditCancel"
    >
      <a-form ref="editFormRef" :model="editForm" :rules="editFormRules" layout="vertical">
        <a-form-item label="客户">
          <div class="edit-customer-info">
            {{ editForm.customer_name }} <span class="muted">#{{ editForm.company_id }}</span>
          </div>
        </a-form-item>
        <a-form-item field="static_balance" label="静态余额（元）" required>
          <a-input-number
            v-model="editForm.static_balance"
            :min="0"
            :precision="2"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item field="remark" label="备注">
          <a-input
            v-model="editForm.remark"
            placeholder="选填，最长 200 字符"
            :max-length="200"
            show-word-limit
            allow-clear
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconSearch } from '@arco-design/web-vue/es/icon'
import type { FormInstance } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
import { useUserStore } from '@/stores/user'
import { getErpSystemsList } from '@/api/erpSystems'
import type { ErpSystem } from '@/types'
import type { BalanceWhitelistItem } from '@/types'
import {
  getBalanceWhitelist,
  batchImportBalanceWhitelist,
  addBalanceWhitelist,
  updateBalanceWhitelist,
  removeBalanceWhitelist,
} from '@/api/balanceWhitelist'
import { formatDateTime } from '@/utils/formatters'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// ========== 列表状态 ==========
const loading = ref(false)
const items = ref<BalanceWhitelistItem[]>([])
const keyword = ref('')

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'right' as const },
  { title: '客户ID', dataIndex: 'company_id', width: 100, align: 'right' as const },
  { title: '客户名称', dataIndex: 'customer_name', width: 200 },
  { title: 'ERP', dataIndex: 'erp_system', width: 140 },
  { title: '静态余额', slotName: 'static_balance', width: 130, align: 'right' as const },
  { title: '备注', dataIndex: 'remark', width: 180, ellipsis: true, tooltip: true },
  { title: '添加时间', slotName: 'created_at', width: 170 },
  { title: '操作', slotName: 'action', width: 150, fixed: 'right' as const },
]

const formatMoney = (value: number) => value.toLocaleString('zh-CN', { minimumFractionDigits: 2 })

// ========== 数据加载 ==========
const loadList = async () => {
  loading.value = true
  try {
    const res = await getBalanceWhitelist({
      page: pagination.current,
      page_size: pagination.pageSize,
      keyword: keyword.value.trim() || undefined,
    })
    items.value = res.data?.items ?? []
    pagination.total = res.data?.total ?? 0
  } catch (error) {
    Message.error('加载余额白名单失败')
    console.error('Failed to load balance whitelist:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  loadList()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  loadList()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  loadList()
}

// ========== 按 ERP 批量导入 ==========
const batchImportVisible = ref(false)
const erpOptions = ref<{ label: string; value: string }[]>([])
const erpLoading = ref(false)
const selectedErpValue = ref<string | undefined>(undefined)
const previewResult = ref<{ imported: number; skipped: number } | null>(null)
const batchImportDone = ref(false)
const batchImportSubmitting = ref(false)
const lastImport = ref({ imported: 0, skipped: 0 })
let batchImportConfirmed = false

const loadErpOptions = async () => {
  erpLoading.value = true
  try {
    const res = await getErpSystemsList()
    const list: ErpSystem[] = res.data?.data || res.data || []
    erpOptions.value = list.map((e) => ({ label: e.name, value: e.value }))
  } catch (error) {
    Message.error('加载 ERP 系统列表失败')
    console.error('Failed to load ERP systems:', error)
  } finally {
    erpLoading.value = false
  }
}

const handleOpenBatchImport = () => {
  batchImportConfirmed = false
  previewResult.value = null
  batchImportDone.value = false
  selectedErpValue.value = undefined
  loadErpOptions()
  batchImportVisible.value = true
}

const handleErpChange = () => {
  // 更换 ERP 后须重新预检
  batchImportConfirmed = false
  previewResult.value = null
  batchImportDone.value = false
}

const handleBatchImportSubmit = async () => {
  if (!selectedErpValue.value) {
    Message.warning('请先选择 ERP 名单')
    return false
  }
  try {
    batchImportSubmitting.value = true
    if (!batchImportConfirmed) {
      // 第一步：预检（不落库）
      const res = await batchImportBalanceWhitelist(selectedErpValue.value, true)
      const data = res.data || { imported: 0, skipped: 0 }
      previewResult.value = { imported: data.imported, skipped: data.skipped }
      batchImportConfirmed = true
      return false // 保持弹窗打开，等待用户确认
    }
    // 第二步：确认导入
    const res = await batchImportBalanceWhitelist(selectedErpValue.value, false)
    const data = res.data || { imported: 0, skipped: 0 }
    lastImport.value = { imported: data.imported, skipped: data.skipped }
    batchImportDone.value = true
    Message.success(`导入完成：成功 ${data.imported} 条，跳过 ${data.skipped} 条`)
    await loadList()
    return true
  } catch (error) {
    const msg = error instanceof Error ? error.message : '操作失败'
    Message.error(`导入失败: ${msg}`)
    console.error('Failed to batch import balance whitelist:', error)
    return false
  } finally {
    batchImportSubmitting.value = false
  }
}

const handleBatchImportCancel = () => {
  batchImportConfirmed = false
  previewResult.value = null
  batchImportDone.value = false
}

// ========== 添加客户 ==========
const addVisible = ref(false)
const submitting = ref(false)
const addFormRef = ref<FormInstance>()
const addCustomerPickerKey = ref(0)

const addForm = reactive<{
  customer_id: number | undefined
  static_balance: number | undefined
}>({
  customer_id: undefined,
  static_balance: 1000,
})

const addFormRules = {
  customer_id: [{ required: true, message: '请选择客户' }],
}

const handleOpenAdd = () => {
  addCustomerPickerKey.value += 1 // 重建 CustomerAutoComplete 清空显示文本（见组件规范）
  addForm.customer_id = undefined
  addForm.static_balance = 1000
  addVisible.value = true
}

const handleAddSubmit = async () => {
  try {
    await addFormRef.value?.validate()
  } catch {
    Message.warning('请选择客户')
    return false
  }
  if (addForm.customer_id === undefined) {
    Message.warning('请选择客户')
    return false
  }
  submitting.value = true
  try {
    await addBalanceWhitelist({
      customer_id: addForm.customer_id,
      static_balance: addForm.static_balance ?? 1000,
    })
    Message.success('添加成功（默认余额已设为静态优先级）')
    await loadList()
    return true
  } catch (error) {
    const msg = error instanceof Error ? error.message : '操作失败'
    Message.error(`添加失败: ${msg}`)
    console.error('Failed to add balance whitelist:', error)
    return false
  } finally {
    submitting.value = false
  }
}

const handleAddCancel = () => {
  addForm.customer_id = undefined
}

// ========== 编辑余额 ==========
const editVisible = ref(false)
const editFormRef = ref<FormInstance>()
const editForm = reactive<{
  id: number | null
  customer_name: string
  company_id: number | null
  static_balance: number | undefined
  remark: string | undefined
}>({
  id: null,
  customer_name: '',
  company_id: null,
  static_balance: undefined,
  remark: undefined,
})

const editFormRules = {
  static_balance: [{ required: true, message: '请输入静态余额' }],
}

const handleOpenEdit = (record: BalanceWhitelistItem) => {
  editForm.id = record.id
  editForm.customer_name = record.customer_name
  editForm.company_id = record.company_id
  editForm.static_balance = record.static_balance
  editForm.remark = record.remark ?? undefined
  editVisible.value = true
}

const handleEditSubmit = async () => {
  try {
    await editFormRef.value?.validate()
  } catch {
    Message.warning('请输入静态余额')
    return false
  }
  if (editForm.id === null || editForm.static_balance === undefined) {
    return false
  }
  submitting.value = true
  try {
    const remark = editForm.remark?.trim() ? editForm.remark.trim() : null
    await updateBalanceWhitelist(editForm.id, editForm.static_balance, remark)
    Message.success('更新成功')
    await loadList()
    return true
  } catch (error) {
    const msg = error instanceof Error ? error.message : '操作失败'
    Message.error(`更新失败: ${msg}`)
    console.error('Failed to update balance whitelist:', error)
    return false
  } finally {
    submitting.value = false
  }
}

const handleEditCancel = () => {
  editForm.id = null
  editForm.remark = undefined
}

// ========== 移出白名单 ==========
const handleRemove = async (id: number) => {
  try {
    await removeBalanceWhitelist(id)
    Message.success('已移出白名单')
    await loadList()
  } catch (error) {
    Message.error('移出失败')
    console.error('Failed to remove balance whitelist:', error)
  }
}

// ========== 生命周期 ==========
onMounted(() => {
  loadList()
})
</script>

<style scoped>
.balance-whitelist-page {
  padding: 0; /* 移除 padding，由 Dashboard 统一提供 */
}

.table-section {
  width: 100%;
  background: white;
  border-radius: 16px;
  border: 1px solid var(--soft);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid var(--soft);
}

.balance-cell {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.edit-customer-info {
  font-size: 14px;
}

.edit-customer-info .muted {
  color: var(--muted);
  font-size: 12px;
}

:deep(.arco-table) {
  font-size: 14px;
}

:deep(.arco-table th) {
  background: var(--bg);
  color: var(--muted);
  font-weight: 600;
}

:deep(.arco-table td) {
  color: #334155;
}

:deep(.arco-table tr:hover td) {
  background: var(--bg);
}
</style>
