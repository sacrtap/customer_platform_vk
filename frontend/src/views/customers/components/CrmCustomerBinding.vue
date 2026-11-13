<template>
  <div class="crm-binding">
    <div class="binding-head">
      <span class="binding-title">CRM 客户绑定</span>
      <span class="subtle binding-hint">
        绑定后该客户的 CRM 回款才可导入充值；绑定即时生效，随本区块独立保存
      </span>
    </div>

    <div v-if="crmCustomerId" class="binding-row">
      <div class="binding-name">
        <span>{{ crmCustomerName || `CRM客户 #${crmCustomerId}` }}</span>
        <span class="subtle">CRM ID {{ crmCustomerExternalId ?? '-' }}</span>
      </div>
      <div class="binding-actions">
        <button class="btn btn-sm" :disabled="!canBind" @click="openPicker">更换</button>
        <button class="btn btn-sm" :disabled="!canBind || saving" @click="handleUnbind">
          解绑
        </button>
      </div>
    </div>

    <div v-else class="binding-row">
      <span class="subtle">未绑定 CRM 客户，绑定后未入账回款才可导入</span>
      <button class="btn btn-sm primary" :disabled="!canBind" @click="openPicker">
        查找CRM客户
      </button>
    </div>

    <p v-if="!canBind" class="binding-hint subtle">
      需要「编辑客户」与「绑定CRM客户」权限才能修改绑定
    </p>

    <a-modal v-model:visible="pickerVisible" title="绑定 CRM 客户" width="640px" :footer="false">
      <div class="picker-filters">
        <input
          v-model="query"
          class="input"
          placeholder="搜索 CRM 客户名称"
          @keyup.enter="handleSearch"
        />
        <button type="button" class="btn primary" @click="handleSearch">搜索</button>
      </div>

      <p v-if="!directorySynced && !loading" class="picker-hint">
        CRM 客户目录尚未同步，请管理员先在「CRM充值管理」执行一次同步
      </p>

      <div class="picker-list">
        <div
          v-for="item in candidates"
          :key="item.id"
          class="picker-item"
          :class="{ unavailable: item.unavailable && !item.bound_to_current }"
        >
          <div class="picker-item-main">
            <div class="picker-name">{{ item.name }}</div>
            <div class="subtle picker-meta">
              CRM ID {{ item.external_id }} · 负责人 {{ item.owner_name || '-' }} · 匹配度
              {{ Math.round(item.score * 100) }}%
            </div>
          </div>
          <div class="picker-item-action">
            <span v-if="item.bound_to_current" class="tag green">已绑定本客户</span>
            <span v-else-if="item.unavailable" class="tag gray">已绑定其他客户</span>
            <button v-else class="btn btn-sm primary" :disabled="saving" @click="handleBind(item)">
              绑定
            </button>
          </div>
        </div>
        <div v-if="!candidates.length && !loading" class="subtle picker-empty">
          没有可推荐的 CRM 客户，请调整搜索关键词
        </div>
      </div>

      <a-pagination
        v-if="total > pageSize"
        :current="page"
        :page-size="pageSize"
        :total="total"
        size="small"
        class="picker-pagination"
        @change="onPageChange"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { handleError } from '@/utils/errorHandler'
import {
  getCrmCustomerCandidates,
  updateCrmCustomerBinding,
  type CrmCustomerCandidate,
  type CrmBindingResult,
} from '@/api/crmRecharge'

const props = defineProps<{
  customerId: number | null
  crmCustomerId: number | null
  crmCustomerName: string | null
  crmCustomerExternalId: number | null
}>()

const emit = defineEmits<{
  updated: [result: CrmBindingResult]
}>()

const userStore = useUserStore()
const canBind = computed(() => userStore.hasPermission('customers:crm_bind'))

const pickerVisible = ref(false)
const loading = ref(false)
const saving = ref(false)
const query = ref('')
const candidates = ref<CrmCustomerCandidate[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const directorySynced = ref(true)

const openPicker = () => {
  if (!props.customerId) {
    Message.warning('请先保存客户后再绑定 CRM 客户')
    return
  }
  query.value = ''
  page.value = 1
  candidates.value = []
  pickerVisible.value = true
  loadCandidates()
}

const loadCandidates = async () => {
  if (!props.customerId) return
  loading.value = true
  try {
    const res = await getCrmCustomerCandidates(props.customerId, {
      query: query.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    candidates.value = (res.data?.list || []) as CrmCustomerCandidate[]
    total.value = res.data?.total || 0
    directorySynced.value = res.data?.directory_synced !== false
    if (!directorySynced.value) Message.warning(res.data?.message || 'CRM客户目录尚未同步')
  } catch (error) {
    handleError(error, 'CRM客户推荐加载失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  page.value = 1
  loadCandidates()
}

const onPageChange = (next: number) => {
  page.value = next
  loadCandidates()
}

const applyResult = (result: CrmBindingResult, message: string) => {
  emit('updated', result)
  Message.success(message)
}

const handleBind = async (item: CrmCustomerCandidate) => {
  if (!props.customerId) return
  saving.value = true
  try {
    const res = await updateCrmCustomerBinding(props.customerId, item.id)
    applyResult(res.data as CrmBindingResult, 'CRM客户绑定已保存')
    pickerVisible.value = false
  } catch (error) {
    handleError(error, '绑定CRM客户失败')
  } finally {
    saving.value = false
  }
}

const handleUnbind = async () => {
  if (!props.customerId) return
  saving.value = true
  try {
    const res = await updateCrmCustomerBinding(props.customerId, null)
    applyResult(res.data as CrmBindingResult, '已解绑CRM客户')
  } catch (error) {
    handleError(error, '解绑CRM客户失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.crm-binding {
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  padding: 12px;
  background: var(--surface, transparent);
}

.binding-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.binding-title {
  font-weight: 600;
  font-size: 14px;
}

.binding-hint {
  font-size: 12px;
}

.binding-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
}

.binding-name {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}

.binding-actions {
  display: flex;
  gap: 8px;
}

/* 按钮与输入框：与列表页 .btn / CustomerSearchInput 同一视觉规格 */
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 12px;
  cursor: pointer;
  font-weight: 700;
  white-space: nowrap;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}

.btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.btn.primary:hover {
  background: #1e40af;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.input {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  padding: 9px 12px;
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  outline: 0;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}

.input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
}

.input::placeholder {
  color: var(--muted);
}

.subtle {
  color: var(--muted);
}

.picker-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.picker-filters .input {
  flex: 1;
}

.picker-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
}

.picker-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 6px;
}

.picker-item.unavailable {
  opacity: 0.6;
}

.picker-item-main {
  min-width: 0;
}

.picker-name {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker-meta {
  font-size: 12px;
  margin-top: 2px;
}

.picker-item-action {
  flex-shrink: 0;
}

.picker-hint,
.picker-empty {
  font-size: 12px;
  margin: 8px 0;
}

.picker-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.tag-success {
  background: rgba(0, 180, 42, 0.12);
  color: #16a34a;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.tag-muted {
  background: rgba(120, 120, 120, 0.12);
  color: var(--muted);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
</style>
