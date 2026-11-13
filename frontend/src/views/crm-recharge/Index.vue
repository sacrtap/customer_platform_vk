<template>
  <div class="crm-recharge-page">
    <PageHeader
      eyebrow="CRM"
      title="CRM充值管理"
      subtitle="CRM 回款镜像查询、客户绑定与人工入账（不自动充值）"
    >
      <template #actions>
        <button v-if="canConfig" class="btn" @click="openSettingsModal">CRM 配置</button>
        <button v-if="canSync" class="btn primary" @click="openSyncModal">同步CRM回款</button>
      </template>
    </PageHeader>

    <div class="card pad main-card">
      <div class="filters">
        <a-date-picker
          v-model="filters.month"
          mode="month"
          value-format="YYYY-MM"
          placeholder="全部月份"
          style="width: 150px"
          @change="handleSearch"
        />
        <FilterDropdown
          v-model="filters.status"
          label="状态"
          :options="STATUS_OPTIONS"
          @apply="handleSearch"
        />
        <CustomerSearchInput
          v-model="filters.keyword"
          placeholder="搜索CRM客户 / 合同 / 回款ID"
          @search="handleSearch"
        />
        <button type="button" class="btn primary" @click="handleSearch">查询</button>
        <button type="button" class="btn" @click="handleReset">重置</button>
      </div>

      <div class="sync-bar">
        <span class="sync-hint">
          每月自动同步：每日 22:00（仅 CRM 启用时执行）<template v-if="!crmEnabled">
            · 当前 CRM 未启用，请在右上角「CRM 配置」填写并验证凭据
          </template>
        </span>
        <span class="sync-hint">
          {{
            latestSuccessAt
              ? `所选月份最近成功同步：${formatDateTime(latestSuccessAt)}`
              : '所选月份尚无成功同步'
          }}
        </span>
        <span v-if="activeRun" class="sync-active">
          <span class="sync-dot" />
          任务 #{{ activeRun.id }} {{ syncStatusLabel(activeRun.status) }}
          <template v-if="activeRun.phase">· {{ syncPhaseLabel(activeRun.phase) }}</template>
          <template v-if="activeRun.customer_count">
            · 已同步 {{ activeRun.customer_count }} 个客户
          </template>
          <template v-if="activeRun.scanned_payment_count">
            · 已检查 {{ activeRun.scanned_payment_count }} 笔回款
          </template>
          <template v-if="activeRun.payment_count != null">
            · 已镜像 {{ activeRun.payment_count }} 笔
          </template>
        </span>
        <button v-if="canSync" class="btn btn-sm" @click="openRunsModal">同步记录</button>
      </div>

      <DataTable
        :columns="tableColumns"
        :data="payments as unknown as Record<string, unknown>[]"
        :loading="loading"
        :pagination="paginationConfig"
        :row-key="'id'"
        :scroll="{ x: 1916 }"
        :storage-key="STORAGE_KEY"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
      >
        <template #external_id="{ record }">
          <span class="cell-nowrap">#{{ (record as CrmPaymentItem).external_id }}</span>
        </template>

        <template #crm_customer_name="{ record }">
          <span class="cell-ellipsis" :title="(record as CrmPaymentItem).crm_customer_name || ''">
            {{ (record as CrmPaymentItem).crm_customer_name || '-' }}
          </span>
        </template>

        <template #contract_title="{ record }">
          <span class="cell-ellipsis" :title="(record as CrmPaymentItem).contract_title || ''">
            {{ (record as CrmPaymentItem).contract_title || '-' }}
          </span>
        </template>

        <template #amount="{ record }">
          <span class="amount">{{ formatAmount((record as CrmPaymentItem).amount) }}</span>
        </template>

        <template #receive_date="{ record }">
          <span class="cell-nowrap">{{ formatDate((record as CrmPaymentItem).receive_date) }}</span>
        </template>

        <template #approve_status="{ record }">
          <span class="cell-nowrap">{{
            approveLabel((record as CrmPaymentItem).approve_status)
          }}</span>
        </template>

        <template #industry_label="{ record }">
          <span class="cell-ellipsis" :title="(record as CrmPaymentItem).industry_label || ''">
            {{ (record as CrmPaymentItem).industry_label || '-' }}
          </span>
        </template>

        <template #bound_customer_name="{ record }">
          <span
            v-if="(record as CrmPaymentItem).bound_customer_id"
            class="link-text"
            :title="`客户ID ${(record as CrmPaymentItem).bound_customer_id}`"
            @click="openCustomer(record as CrmPaymentItem)"
          >
            {{ (record as CrmPaymentItem).bound_customer_name }}
          </span>
          <span v-else class="subtle">未绑定</span>
        </template>

        <template #status="{ record }">
          <span class="tag" :class="statusClass((record as CrmPaymentItem).status)">
            {{ statusLabel((record as CrmPaymentItem).status) }}
          </span>
          <div v-if="(record as CrmPaymentItem).blocked_reason" class="blocked-reason">
            {{ (record as CrmPaymentItem).blocked_reason }}
          </div>
        </template>

        <template #recharge_total="{ record }">
          <span class="amount">{{ formatAmount((record as CrmPaymentItem).total_amount) }}</span>
        </template>

        <template #recharge_date="{ record }">
          <span class="cell-nowrap">{{
            formatDate((record as CrmPaymentItem).recharge_date)
          }}</span>
        </template>

        <template #recharge_created_at="{ record }">
          <span class="cell-nowrap">
            {{ formatDateTime((record as CrmPaymentItem).recharge_created_at) }}
          </span>
        </template>

        <template #action="{ record }">
          <button
            v-if="canImport && (record as CrmPaymentItem).status === 'pending'"
            class="btn btn-primary-sm"
            @click.stop="openImportModal(record as CrmPaymentItem)"
          >
            导入充值
          </button>
          <button
            v-else-if="canRevoke && (record as CrmPaymentItem).status === 'imported'"
            class="btn btn-sm"
            @click.stop="openRevokeModal(record as CrmPaymentItem)"
          >
            撤销导入
          </button>
          <button
            v-else-if="(record as CrmPaymentItem).status === 'imported'"
            class="btn btn-sm"
            @click.stop="goBalance(record as CrmPaymentItem)"
          >
            余额记录
          </button>
          <span v-else-if="(record as CrmPaymentItem).status === 'pending'" class="subtle">
            无导入权限
          </span>
          <span v-else class="subtle">-</span>
        </template>
      </DataTable>
    </div>

    <!-- 导入充值 -->
    <a-modal
      v-model:visible="importVisible"
      title="导入CRM回款"
      width="560px"
      :ok-loading="importing"
      @before-ok="submitImport"
    >
      <div v-if="currentPayment" class="import-body">
        <div class="import-grid">
          <div class="import-row">
            <span class="import-label">CRM客户</span>
            <span>{{ currentPayment.crm_customer_name || '-' }}</span>
          </div>
          <div class="import-row">
            <span class="import-label">合同</span>
            <span>{{ currentPayment.contract_title || '-' }}</span>
          </div>
          <div class="import-row">
            <span class="import-label">回款日期</span>
            <span>{{ formatDate(currentPayment.receive_date) }}</span>
          </div>
          <div class="import-row">
            <span class="import-label">中台客户</span>
            <span>
              {{ currentPayment.bound_customer_name || '-' }}
              <span class="subtle">#{{ currentPayment.bound_customer_id }}</span>
            </span>
          </div>
          <div class="import-row">
            <span class="import-label">实充金额</span>
            <span class="amount">{{ formatAmount(currentPayment.amount) }}</span>
          </div>
        </div>
        <a-form layout="vertical" style="margin-top: 12px">
          <a-form-item label="赠送金额（额外增加，可填 0）">
            <a-input v-model="bonusAmountInput" placeholder="0.00" />
          </a-form-item>
        </a-form>
        <p class="import-tip">
          实充金额必须等于CRM回款金额；入账归期取回款日期
          {{ formatDate(currentPayment.receive_date) }}。导入后余额增加「实充 + 赠送」，同一回款重复
          提交不会重复入账。
        </p>
      </div>
    </a-modal>

    <!-- 撤销 CRM 充值导入 -->
    <a-modal
      v-model:visible="revokeVisible"
      title="撤销CRM充值导入"
      width="560px"
      :ok-loading="revoking"
      ok-text="确认撤销"
      @before-ok="submitRevoke"
    >
      <div v-if="currentPayment" class="import-body">
        <div class="import-row">
          <span class="label">回款ID</span>
          <span>#{{ currentPayment.external_id }}</span>
        </div>
        <div class="import-row">
          <span class="label">CRM客户</span>
          <span>{{ currentPayment.crm_customer_name || '-' }}</span>
        </div>
        <div class="import-row">
          <span class="label">入账客户</span>
          <span>
            {{ currentPayment.bound_customer_name || '-' }}
            <span class="subtle">#{{ currentPayment.bound_customer_id }}</span>
          </span>
        </div>
        <div class="import-row">
          <span class="label">入账金额</span>
          <span class="amount">
            实充 {{ formatAmount(currentPayment.real_amount) }} / 赠送
            {{ formatAmount(currentPayment.bonus_amount) }}
          </span>
        </div>
        <a-form layout="vertical" style="margin-top: 12px">
          <a-form-item label="撤销原因（必填，写入审计）">
            <a-textarea
              v-model="revokeReason"
              :auto-size="{ minRows: 2, maxRows: 4 }"
              placeholder="例如：CRM客户绑定错误，需改绑后重新导入"
            />
          </a-form-item>
          <a-form-item v-if="isSuperAdmin">
            <a-checkbox v-model="revokeForce">余额不足时强制撤销（线下核对欠款）</a-checkbox>
          </a-form-item>
        </a-form>
        <p class="import-tip">
          撤销会立即扣回该笔「实充 + 赠送」，并把回款释放为待导入。撤销不会改绑定关系：
          正确顺序是「撤销 → 改绑 → 重新导入」。
        </p>
      </div>
    </a-modal>

    <!-- 同步CRM回款 -->
    <a-modal
      v-model:visible="syncVisible"
      title="同步CRM回款"
      width="520px"
      :ok-loading="syncStarting"
      ok-text="开始同步"
      @before-ok="submitSync"
    >
      <a-form layout="vertical">
        <a-form-item label="同步月份">
          <a-date-picker
            v-model="syncMonth"
            mode="month"
            value-format="YYYY-MM"
            style="width: 100%"
            :disabled-date="disableFutureMonth"
          />
        </a-form-item>
      </a-form>
      <p v-if="!crmEnabled" class="sync-warning">
        CRM 未启用：请先在「CRM
        配置」中开启开关并填写、验证企业ID/登录手机号/密码，否则同步会被拒绝。
      </p>
      <p class="import-tip">
        同步只读取 CRM
        回款并更新本地镜像，不会自动入账。当月由计划任务每日自动同步；历史月需在此手动触发。
      </p>
      <p v-if="activeRun" class="sync-progress">
        当前任务 #{{ activeRun.id }}：{{ syncStatusLabel(activeRun.status) }}
        <span v-if="activeRun.phase">（{{ syncPhaseLabel(activeRun.phase) }}）</span>
        <span v-if="activeRun.scanned_payment_count">
          ，已检查 {{ activeRun.scanned_payment_count }} 笔回款
        </span>
        <span v-if="activeRun.scanned_contract_count">
          ，已扫描 {{ activeRun.scanned_contract_count }} 个合同
        </span>
        <span v-if="activeRun.payment_count != null">
          ，本月已镜像 {{ activeRun.payment_count }} 笔回款
        </span>
      </p>
    </a-modal>

    <!-- 同步记录 -->
    <a-modal v-model:visible="runsVisible" title="同步记录" width="1040px" :footer="false">
      <a-table
        :data="syncRuns as unknown as Record<string, unknown>[]"
        :pagination="false"
        :bordered="false"
        size="small"
      >
        <template #columns>
          <a-table-column title="任务" data-index="id" :width="70" />
          <a-table-column title="月份" data-index="month" :width="100" />
          <a-table-column title="触发" :width="80">
            <template #cell="{ record }">
              {{ (record as CrmSyncRunItem).trigger === 'manual' ? '手动' : '自动' }}
            </template>
          </a-table-column>
          <a-table-column title="状态" :width="100">
            <template #cell="{ record }">
              <a-tag :color="syncStatusColor((record as CrmSyncRunItem).status)" size="small">
                {{ syncStatusLabel((record as CrmSyncRunItem).status) }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="进度" :width="190">
            <template #cell="{ record }">
              <span v-if="isRunActive(record as CrmSyncRunItem)">
                已检查 {{ (record as CrmSyncRunItem).scanned_payment_count ?? 0 }} 笔 / 已镜像
                {{ (record as CrmSyncRunItem).payment_count ?? 0 }} 笔
              </span>
              <span v-else>
                {{ (record as CrmSyncRunItem).payment_count ?? '-' }} /
                {{ (record as CrmSyncRunItem).eligible_count ?? '-' }}
              </span>
            </template>
          </a-table-column>
          <a-table-column title="开始时间" :width="160">
            <template #cell="{ record }">
              {{ formatDateTime((record as CrmSyncRunItem).started_at) }}
            </template>
          </a-table-column>
          <a-table-column title="完成时间" :width="160">
            <template #cell="{ record }">
              {{ formatDateTime((record as CrmSyncRunItem).finished_at) }}
            </template>
          </a-table-column>
          <a-table-column title="失败原因" data-index="error_message" />
        </template>
      </a-table>
    </a-modal>

    <!-- CRM 配置（开关 + 凭据，保存前验证） -->
    <a-modal
      v-model:visible="settingsVisible"
      title="CRM 配置"
      width="560px"
      :footer="false"
      :mask-closable="false"
    >
      <a-form layout="vertical">
        <a-form-item label="启用 CRM 同步">
          <div class="setting-switch-row">
            <a-switch v-model="settingsForm.enabled" />
            <span class="subtle">
              开启且凭据完整后，每日 22:00 自动同步当月回款（只读镜像，不自动充值）
            </span>
          </div>
        </a-form-item>
        <a-form-item label="API 地址">
          <a-input v-model="settingsForm.base_url" placeholder="https://lxcrm.weiwenjia.com" />
          <template #help>仅支持官方 HTTPS 域名，留空按官方默认地址处理</template>
        </a-form-item>
        <a-form-item label="企业ID" required>
          <a-input v-model="settingsForm.corp_id" placeholder="CRM 企业ID" />
        </a-form-item>
        <a-form-item label="登录手机号" required>
          <a-input v-model="settingsForm.phone" placeholder="CRM 登录账号手机号" />
        </a-form-item>
        <a-form-item label="登录密码">
          <a-input-password
            v-model="settingsForm.password"
            :placeholder="settings.password_set ? '已配置，留空则不修改' : '请输入登录密码'"
            allow-clear
          />
          <template #help>
            <span v-if="!settings.credential_key_configured" class="settings-warn">
              服务端未注入 CRM_CREDENTIAL_KEY，暂不能保存密码，请联系运维注入后重试
            </span>
            <span v-else>密码加密存储，提交后不会再以明文展示</span>
          </template>
        </a-form-item>
        <a-form-item v-if="settings.password_set">
          <a-checkbox v-model="settingsForm.clear_password">清除已保存的密码</a-checkbox>
        </a-form-item>
      </a-form>

      <div
        v-if="verifyResult"
        class="verify-result"
        :class="!verifyResult.ok ? 'fail' : verifyResult.warning ? 'warn' : 'ok'"
      >
        <template v-if="verifyResult.ok">
          ✅ 登录凭据有效<template v-if="verifyResult.warning">
            ，但客户列表读取失败：{{ verifyResult.warning }}</template
          >
          <template v-else
            >：该账号可访问 {{ verifyResult.customer_total ?? '-' }} 位 CRM 客户</template
          >
        </template>
        <template v-else>{{ verifyResult.message }}</template>
      </div>

      <p class="import-tip">
        当前来源：{{
          settings.source === 'database' ? '页面保存的配置' : '部署环境变量'
        }}；已保存手机号：{{ settings.phone_masked || '未配置' }}；密码：{{
          settings.password_set ? '已配置' : '未配置'
        }}。 更换企业ID/手机号/密码后需重新验证才能保存，旧登录凭证会立即失效。
      </p>

      <div class="settings-footer">
        <button type="button" class="btn" :disabled="verifying" @click="verifyCredentials">
          {{ verifying ? '验证中…' : '验证账号密码' }}
        </button>
        <button type="button" class="btn primary" :disabled="saving" @click="submitSettings()">
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import DataTable, { type DataTableColumn } from '@/components/DataTable.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'
import { useUserStore } from '@/stores/user'
import { handleError } from '@/utils/errorHandler'
import { formatCurrency, formatDate, formatDateTime } from '@/utils/formatters'
import {
  createCrmSyncRun,
  getCrmPayments,
  getCrmSettings,
  getCrmSyncRuns,
  importCrmPayment,
  revokeCrmImport,
  testCrmCredentials,
  updateCrmSettings,
  type CrmPaymentItem,
  type CrmSettings,
  type CrmSyncRunItem,
} from '@/api/crmRecharge'

const router = useRouter()
const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)
const crmEnabled = ref(true)
const canSync = computed(() => can('crm_recharge:sync') && can('customers:view_all'))
const canImport = computed(() => can('crm_recharge:import') && can('billing:recharge'))
const canRevoke = computed(() => can('crm_recharge:revoke') && can('billing:recharge'))
const isSuperAdmin = computed(() => userStore.isSuperAdmin)

const STORAGE_KEY = 'crm_recharge_table_columns'

const STATUS_OPTIONS = [
  { label: '待导入', value: 'pending' },
  { label: '已导入', value: 'imported' },
  { label: '不可导入', value: 'blocked' },
]

const payments = ref<CrmPaymentItem[]>([])
const total = ref(0)
const loading = ref(false)
const latestSuccessAt = ref<string | null>(null)

const filters = reactive({
  month: '',
  status: 'all',
  keyword: '',
})

const pagination = reactive({ current: 1, pageSize: 20 })

const paginationConfig = computed(() => ({
  current: pagination.current,
  pageSize: pagination.pageSize,
  total: total.value,
  showTotal: true,
  showPageSize: true,
  showJumper: true,
  pageSizeOptions: [10, 20, 50, 100],
}))

interface ColumnDef {
  key: string
  title: string
  width?: number
  align?: 'left' | 'center' | 'right'
  ellipsis?: boolean
  tooltip?: boolean
}

const columnDefs: ColumnDef[] = [
  { key: 'external_id', title: '回款ID', width: 96 },
  { key: 'crm_customer_name', title: 'CRM客户', width: 200, ellipsis: true, tooltip: true },
  { key: 'contract_title', title: '合同', width: 240, ellipsis: true, tooltip: true },
  { key: 'amount', title: '回款金额', width: 120, align: 'right' },
  { key: 'receive_date', title: '回款日期', width: 118 },
  { key: 'approve_status', title: '审批', width: 96 },
  { key: 'industry_label', title: '行业', width: 140, ellipsis: true, tooltip: true },
  { key: 'bound_customer_name', title: '中台客户', width: 160, ellipsis: true, tooltip: true },
  { key: 'status', title: '状态', width: 200 },
  { key: 'recharge_total', title: '入账金额', width: 120, align: 'right' },
  { key: 'recharge_date', title: '归期', width: 118 },
  { key: 'recharge_created_at', title: '入账时间', width: 168 },
]

const tableColumns = computed<DataTableColumn[]>(() => [
  ...columnDefs.map((col) => ({
    key: col.key,
    title: col.title,
    width: col.width,
    align: col.align,
    ellipsis: col.ellipsis,
    tooltip: col.tooltip,
  })),
  { key: 'action', title: '操作', slotName: 'action', fixed: 'right' as const, width: 140 },
])

const formatAmount = (value: string | null | undefined): string => {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  return Number.isFinite(num) ? formatCurrency(num) : '-'
}

const approveLabel = (value: string | null): string => {
  if (value === 'approved') return '已通过'
  if (value === 'applying') return '审批中'
  return value || '-'
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待导入',
  imported: '已导入',
  blocked: '不可导入',
}

const statusLabel = (status: string) => STATUS_LABELS[status] || status
// 用全局 .tag 修饰类（amber/green/gray），与其他列表页状态标签同一套色板
const statusClass = (status: string) =>
  status === 'pending' ? 'amber' : status === 'imported' ? 'green' : 'gray'

const SYNC_STATUS_LABELS: Record<string, string> = {
  pending: '排队中',
  running: '执行中',
  succeeded: '成功',
  failed: '失败',
}

const syncStatusLabel = (status: string) => SYNC_STATUS_LABELS[status] || status

const SYNC_STATUS_COLORS: Record<string, string> = {
  pending: 'gray',
  running: 'arcoblue',
  succeeded: 'green',
  failed: 'red',
}

const syncStatusColor = (status: string) => SYNC_STATUS_COLORS[status] || 'gray'

const isRunActive = (run: CrmSyncRunItem) => run.status === 'pending' || run.status === 'running'

// 阶段文案：合同阶段按合同逐个拉回款（上游限流），是长耗时阶段，
// 必须让用户看到扫描进度，否则会被当成卡死/失败。
const SYNC_PHASE_LABELS: Record<string, string> = {
  customers: '同步客户',
  payments: '拉取回款列表',
  contracts: '扫描合同与回款',
  completed: '已完成',
}

const syncPhaseLabel = (phase: string) => SYNC_PHASE_LABELS[phase] || phase

// ==================== 列表 ====================

const loadPayments = async () => {
  loading.value = true
  try {
    const res = await getCrmPayments({
      month: filters.month || undefined,
      status: filters.status === 'all' ? undefined : (filters.status as 'pending'),
      keyword: filters.keyword.trim() || undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    payments.value = (res.data?.list || []) as CrmPaymentItem[]
    total.value = res.data?.total || 0
    crmEnabled.value = res.data?.crm_enabled !== false
  } catch (error) {
    handleError(error, 'CRM回款列表加载失败')
  } finally {
    loading.value = false
  }
}

const loadLatestSync = async () => {
  if (!canSync.value) return
  try {
    const res = await getCrmSyncRuns({
      month: filters.month || undefined,
      page: 1,
      page_size: 5,
    })
    latestSuccessAt.value = res.data?.latest_success_at || null
    activeRun.value = pickActiveRun((res.data?.list || []) as CrmSyncRunItem[])
  } catch {
    // 同步状态为辅助信息，失败不阻塞列表
  }
}

const pickActiveRun = (runs: CrmSyncRunItem[]): CrmSyncRunItem | null =>
  runs.find((run) => run.status === 'pending' || run.status === 'running') || null

const handleSearch = () => {
  pagination.current = 1
  loadPayments()
  loadLatestSync()
}

const handleReset = () => {
  filters.month = ''
  filters.status = 'all'
  filters.keyword = ''
  handleSearch()
}

const onPageChange = (page: number) => {
  pagination.current = page
  loadPayments()
}

const onPageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  loadPayments()
}

const openCustomer = (record: CrmPaymentItem) => {
  if (record.bound_customer_id) router.push(`/customers/${record.bound_customer_id}`)
}

const goBalance = (record: CrmPaymentItem) => {
  if (record.bound_customer_id) {
    router.push({ path: '/billing/balances', query: { keyword: record.bound_customer_name || '' } })
  }
}

// ==================== 导入 ====================

const importVisible = ref(false)
const importing = ref(false)
const currentPayment = ref<CrmPaymentItem | null>(null)
const bonusAmountInput = ref('0')

const openImportModal = (record: CrmPaymentItem) => {
  if (!crmEnabled.value) {
    Message.warning('CRM 未启用：导入前需实时复核源回款，请先配置 CRM 凭据')
    return
  }
  currentPayment.value = record
  bonusAmountInput.value = '0'
  importVisible.value = true
}

const submitImport = async (): Promise<boolean> => {
  const payment = currentPayment.value
  if (!payment || !payment.bound_customer_id) {
    Message.warning('该回款尚未绑定中台客户，请先在客户管理中完成绑定')
    return false
  }
  importing.value = true
  try {
    const res = await importCrmPayment(payment.id, {
      customer_id: payment.bound_customer_id,
      real_amount: String(payment.amount ?? '0'),
      bonus_amount: bonusAmountInput.value.trim() || '0',
    })
    Message.success(res.data?.message || '充值成功')
    importVisible.value = false
    await loadPayments()
    return true
  } catch (error) {
    handleError(error, '导入充值失败')
    return false
  } finally {
    importing.value = false
  }
}

const revokeVisible = ref(false)
const revoking = ref(false)
const revokeReason = ref('')
const revokeForce = ref(false)

const openRevokeModal = (record: CrmPaymentItem) => {
  currentPayment.value = record
  revokeReason.value = ''
  revokeForce.value = false
  revokeVisible.value = true
}

const submitRevoke = async (): Promise<boolean> => {
  const payment = currentPayment.value
  if (!payment || !payment.bound_customer_id) {
    Message.warning('该回款未绑定中台客户，无法撤销')
    return false
  }
  if (!revokeReason.value.trim()) {
    Message.warning('请填写撤销原因')
    return false
  }
  revoking.value = true
  try {
    const res = await revokeCrmImport(payment.id, {
      customer_id: payment.bound_customer_id,
      reason: revokeReason.value.trim(),
      force: revokeForce.value,
    })
    Message.success(res.data?.message || '已撤销CRM充值导入')
    revokeVisible.value = false
    await loadPayments()
    return true
  } catch (error) {
    handleError(error, '撤销失败')
    return false
  } finally {
    revoking.value = false
  }
}

// ==================== 同步 ====================

const syncVisible = ref(false)
const syncStarting = ref(false)
const syncMonth = ref('')
const activeRun = ref<CrmSyncRunItem | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const disableFutureMonth = (current: Date) => {
  const now = new Date()
  return (
    current.getFullYear() > now.getFullYear() ||
    (current.getFullYear() === now.getFullYear() && current.getMonth() > now.getMonth())
  )
}

const openSyncModal = () => {
  if (!syncMonth.value) {
    const now = new Date()
    syncMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  }
  syncVisible.value = true
}

const submitSync = async (): Promise<boolean> => {
  if (!crmEnabled.value) {
    Message.warning('CRM 未启用：请先配置 CRM_ENABLED 与企业ID/登录凭据')
    return false
  }
  if (!syncMonth.value) {
    Message.warning('请选择同步月份')
    return false
  }
  syncStarting.value = true
  try {
    const res = await createCrmSyncRun(syncMonth.value)
    Message.success(res.data?.message || '同步任务已创建')
    filters.month = syncMonth.value
    await loadPayments()
    // 先取回刚创建的 run：否则 activeRun 仍为 null，pollSync 会在第一轮直接退出
    await loadLatestSync()
    schedulePoll()
    return true
  } catch (error) {
    handleError(error, '创建同步任务失败')
    return false
  } finally {
    syncStarting.value = false
  }
}

const schedulePoll = () => {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = setTimeout(() => {
    pollTimer = null
    void pollSync()
  }, 3000)
}

let pollFailures = 0

/**
 * 同步任务轮询：主页面状态条、同步记录弹窗共用
 *
 * 不按月份过滤查询 —— 用户切换筛选时也要能看到仍在执行的任务；
 * 只按月份过滤的 `latest_success_at` 在任务结束后由 `loadLatestSync` 补。
 */
const pollSync = async () => {
  try {
    const res = await getCrmSyncRuns({ page: 1, page_size: 10 })
    const runs = (res.data?.list || []) as CrmSyncRunItem[]
    pollFailures = 0
    if (runsVisible.value) {
      syncRuns.value = runs
    }
    const next = pickActiveRun(runs)
    if (next) {
      activeRun.value = next
      schedulePoll()
      return
    }
    const wasActive = activeRun.value !== null
    activeRun.value = null
    await loadLatestSync()
    if (wasActive) {
      await loadPayments()
      Message.success('CRM 同步已结束，列表已刷新')
    }
  } catch {
    // 连续失败时停止轮询，避免后端不可用时无限重试
    pollFailures += 1
    if (pollFailures <= 5) schedulePoll()
  }
}

// ==================== 同步记录 ====================

const runsVisible = ref(false)
const syncRuns = ref<CrmSyncRunItem[]>([])

const refreshRuns = async () => {
  const res = await getCrmSyncRuns({ month: filters.month || undefined, page: 1, page_size: 20 })
  syncRuns.value = (res.data?.list || []) as CrmSyncRunItem[]
}

const openRunsModal = async () => {
  runsVisible.value = true
  try {
    await refreshRuns()
    // 弹窗内没有独立定时器：任务仍在执行时复用主页面轮询，列表随每次轮询刷新
    if (activeRun.value) schedulePoll()
  } catch (error) {
    handleError(error, '同步记录加载失败')
  }
}

// ==================== CRM 配置 ====================

const canConfig = computed(() => can('crm_recharge:config'))

const emptySettings: CrmSettings = {
  enabled: false,
  base_url: 'https://lxcrm.weiwenjia.com',
  corp_id: '',
  phone_masked: '',
  password_set: false,
  credentials_complete: false,
  active: false,
  source: 'environment',
  credential_key_configured: true,
  crm_enabled_for_requests: false,
}

const settingsVisible = ref(false)
const settings = ref<CrmSettings>({ ...emptySettings })
const settingsForm = reactive({
  enabled: false,
  base_url: '',
  corp_id: '',
  phone: '',
  password: '',
  clear_password: false,
})
const verifying = ref(false)
const saving = ref(false)
const verifyResult = ref<{
  ok: boolean
  message: string
  customer_total?: number | null
  warning?: string | null
} | null>(null)

const applySettings = (data: CrmSettings) => {
  settings.value = data
  settingsForm.enabled = data.enabled
  settingsForm.base_url = data.base_url
  settingsForm.corp_id = data.corp_id
  settingsForm.phone = ''
  settingsForm.password = ''
  settingsForm.clear_password = false
  verifyResult.value = null
  crmEnabled.value = data.active
}

const loadSettings = async () => {
  try {
    const res = await getCrmSettings()
    applySettings((res.data || emptySettings) as CrmSettings)
  } catch (error) {
    handleError(error, 'CRM 配置加载失败')
  }
}

const openSettingsModal = async () => {
  settingsVisible.value = true
  await loadSettings()
}

/** 表单值 → 提交体；手机号留空表示沿用已保存的号码 */
const buildSettingsPayload = (extra: Record<string, unknown> = {}) => {
  const payload: Record<string, unknown> = {
    enabled: settingsForm.enabled,
    base_url: settingsForm.base_url.trim() || undefined,
    corp_id: settingsForm.corp_id.trim(),
    ...extra,
  }
  if (settingsForm.phone.trim()) payload.phone = settingsForm.phone.trim()
  if (settingsForm.password) payload.password = settingsForm.password
  if (settingsForm.clear_password) payload.clear_password = true
  return payload
}

const validateSettingsForm = (needPassword: boolean): boolean => {
  if (!settingsForm.corp_id.trim()) {
    Message.warning('请填写企业ID')
    return false
  }
  if (!settingsForm.phone.trim() && !settings.value.phone_masked) {
    Message.warning('请填写登录手机号')
    return false
  }
  if (needPassword && !settingsForm.password && !settings.value.password_set) {
    Message.warning('请填写登录密码')
    return false
  }
  return true
}

const verifyCredentials = async () => {
  if (!validateSettingsForm(true)) return
  verifying.value = true
  verifyResult.value = null
  try {
    const res = await testCrmCredentials(buildSettingsPayload())
    const data = res.data as unknown as {
      corp_id?: string
      customer_total?: number | null
      warning?: string | null
    }
    verifyResult.value = {
      ok: true,
      message: (res as { message?: string }).message || '验证通过',
      customer_total: data?.customer_total ?? null,
      warning: data?.warning ?? null,
    }
  } catch (error) {
    // axios 拦截器把业务错误 reject 成 { code, message, category }
    verifyResult.value = {
      ok: false,
      message: errorMessageOf(error, '验证失败，请检查账号密码'),
    }
  } finally {
    verifying.value = false
  }
}

const errorMessageOf = (error: unknown, fallback: string): string => {
  const message = (error as { message?: unknown })?.message
  return typeof message === 'string' && message ? message : fallback
}

const errorCodeOf = (error: unknown): number | string | undefined =>
  (error as { code?: number | string })?.code

/** 后端约定的「验证失败但可强制保存」业务码 */
const FORCEABLE_CODES = new Set<number | string>([42201, 42202])

const submitSettings = async (force = false) => {
  force = force === true
  // 清除密码时不需要填写密码；其余情况要求新密码或已有密码
  if (!validateSettingsForm(!settings.value.password_set && !settingsForm.clear_password)) return
  saving.value = true
  try {
    const res = await updateCrmSettings(buildSettingsPayload(force ? { force: true } : {}))
    applySettings((res.data || emptySettings) as CrmSettings)
    const saved = res.data as unknown as CrmSettings | undefined
    if (saved?.verification_warning) {
      Message.warning(
        `CRM 配置已保存；登录凭据有效，但客户列表读取失败：${saved.verification_warning}`
      )
    } else if (saved?.verified_customer_total == null) {
      Message.success('CRM 配置已保存')
    } else {
      Message.success(`CRM 配置已保存并验证通过（可访问 ${saved.verified_customer_total} 位客户）`)
    }
    settingsVisible.value = false
    await loadPayments()
    await loadLatestSync()
  } catch (error) {
    const code = errorCodeOf(error)
    const message = errorMessageOf(error, '当前凭据无法通过 CRM 验证')
    if (code !== undefined && FORCEABLE_CODES.has(code) && !force) {
      Modal.confirm({
        title: '验证未通过，仍要保存吗？',
        content: `${message}。强制保存后同步与导入仍会失败，直到凭据恢复。`,
        okText: '仍然保存',
        cancelText: '返回修改',
        onOk: () => submitSettings(true),
      })
      return
    }
    handleError(error, 'CRM 配置保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadPayments()
  loadLatestSync().then(() => {
    if (activeRun.value) schedulePoll()
  })
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<style scoped>
.crm-recharge-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.main-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.sync-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: var(--muted);
}

.sync-hint {
  white-space: nowrap;
}

/* 执行中的同步任务：列表页常驻可见，避免用户回到列表后失去进度 */
.sync-active {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.sync-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: sync-pulse 1.2s ease-in-out infinite;
}

@keyframes sync-pulse {
  0%,
  100% {
    opacity: 0.3;
  }

  50% {
    opacity: 1;
  }
}

/* 按钮样式（与 VrSettlements.vue / Invoices.vue 一致） */
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

.btn.btn-primary-sm {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.btn.btn-primary-sm:hover {
  background: #1e40af;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.cell-nowrap {
  white-space: nowrap;
}

.cell-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

.amount {
  font-variant-numeric: tabular-nums;
}

.subtle {
  color: var(--muted);
}

.link-text {
  color: var(--accent);
  cursor: pointer;
}

.blocked-reason {
  margin-top: 2px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.3;
}

.import-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.import-row {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 12px;
  font-size: 14px;
}

.import-label {
  color: var(--muted);
}

.sync-warning {
  margin: 0 0 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fef3c7;
  color: #b45309;
  font-size: 12px;
  line-height: 1.5;
}

.import-tip {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--muted);
}

.sync-progress {
  margin-top: 8px;
  font-size: 13px;
  color: var(--accent);
}
.setting-switch-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.settings-warn {
  color: #b45309;
}

.verify-result {
  margin: 0 0 12px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
}

.verify-result.ok {
  background: #dcfce7;
  color: #15803d;
}

.verify-result.warn {
  background: #fef3c7;
  color: #b45309;
}

.verify-result.fail {
  background: #fee2e2;
  color: #b91c1c;
}

.settings-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
