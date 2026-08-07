<template>
  <div class="database-management">
    <PageHeader eyebrow="System" title="数据库管理" subtitle="系统级数据操作管理" />

    <!-- 清空客户数据 -->
    <a-card :bordered="false" style="margin-bottom: 24px">
      <template #title>
        <div class="card-header">
          <span>清空客户数据</span>
        </div>
      </template>

      <a-alert type="warning" style="margin-bottom: 24px">
        此操作不可逆，将删除所有客户及关联数据（含客户画像、标签、结算记录、发票、每日订单等）。
      </a-alert>

      <a-descriptions :column="1" bordered style="margin-bottom: 24px">
        <a-descriptions-item label="操作名称">清空客户数据</a-descriptions-item>
        <a-descriptions-item label="影响范围">
          {{ AFFECTED_TABLES.join('、') }}
        </a-descriptions-item>
        <a-descriptions-item label="权限要求">需具备「数据清空」权限</a-descriptions-item>
      </a-descriptions>

      <a-space>
        <a-button
          v-if="can('system:database_clear')"
          status="danger"
          :loading="clearing"
          @click="handleClearConfirm"
        >
          清空客户数据
        </a-button>
      </a-space>

      <div v-if="lastResult" class="result-info">
        <a-alert :type="lastResult.success ? 'success' : 'error'" style="margin-top: 16px">
          {{ lastResult.message }}
        </a-alert>
      </div>
    </a-card>

    <!-- 清空消耗分析数据 -->
    <a-card :bordered="false" style="margin-bottom: 24px">
      <template #title>
        <div class="card-header">
          <span>清空消耗分析数据</span>
        </div>
      </template>

      <a-alert type="warning" style="margin-bottom: 24px">
        此操作不可逆，将删除所有每日订单原始数据和每日消费计算结果（含同步任务记录）。不会删除客户、计费规则、结算单等数据。
      </a-alert>

      <a-descriptions :column="1" bordered style="margin-bottom: 24px">
        <a-descriptions-item label="操作名称">清空消耗分析数据</a-descriptions-item>
        <a-descriptions-item label="影响范围">
          {{ CONSUMPTION_TABLES.join('、') }}
        </a-descriptions-item>
        <a-descriptions-item label="说明">
          清空后消耗分析页面将无数据展示，需重新执行数据同步后恢复
        </a-descriptions-item>
        <a-descriptions-item label="权限要求">需具备「数据清空」权限</a-descriptions-item>
      </a-descriptions>

      <a-space>
        <a-button
          v-if="can('system:database_clear')"
          status="danger"
          :loading="clearingConsumption"
          @click="handleClearConsumptionConfirm"
        >
          清空消耗分析数据
        </a-button>
      </a-space>

      <div v-if="lastConsumptionResult" class="result-info">
        <a-alert
          :type="lastConsumptionResult.success ? 'success' : 'error'"
          style="margin-top: 16px"
        >
          {{ lastConsumptionResult.message }}
        </a-alert>
      </div>
    </a-card>

    <!-- 清空结算单数据 -->
    <a-card :bordered="false" style="margin-bottom: 24px">
      <template #title>
        <div class="card-header">
          <span>清空结算单数据</span>
        </div>
      </template>

      <a-alert type="warning" style="margin-bottom: 24px">
        此操作不可逆，将删除所有结算单及结算单明细（含关联结算单的消费流水）。不会删除客户、计费规则、余额、消耗分析等数据。
      </a-alert>

      <a-descriptions :column="1" bordered style="margin-bottom: 24px">
        <a-descriptions-item label="操作名称">清空结算单数据</a-descriptions-item>
        <a-descriptions-item label="影响范围">
          {{ INVOICE_TABLES.join('、') }}
        </a-descriptions-item>
        <a-descriptions-item label="说明">
          清空后结算管理页面将无数据展示，需重新生成结算单后恢复
        </a-descriptions-item>
        <a-descriptions-item label="权限要求">需具备「数据清空」权限</a-descriptions-item>
      </a-descriptions>

      <a-space>
        <a-button
          v-if="can('system:database_clear')"
          status="danger"
          :loading="clearingInvoices"
          @click="handleClearInvoicesConfirm"
        >
          清空结算单数据
        </a-button>
      </a-space>

      <div v-if="lastInvoiceResult" class="result-info">
        <a-alert :type="lastInvoiceResult.success ? 'success' : 'error'" style="margin-top: 16px">
          {{ lastInvoiceResult.message }}
        </a-alert>
      </div>
    </a-card>

    <!-- 清空余额数据 -->
    <a-card :bordered="false">
      <template #title>
        <div class="card-header">
          <span>清空余额数据</span>
        </div>
      </template>

      <a-alert type="warning" style="margin-bottom: 24px">
        此操作不可逆，将删除所有客户余额、充值记录和消费流水。不会删除客户、计费规则、结算单、消耗分析等数据。
      </a-alert>

      <a-descriptions :column="1" bordered style="margin-bottom: 24px">
        <a-descriptions-item label="操作名称">清空余额数据</a-descriptions-item>
        <a-descriptions-item label="影响范围">
          {{ BALANCE_TABLES.join('、') }}
        </a-descriptions-item>
        <a-descriptions-item label="说明">
          清空后余额管理页面将无数据展示，需重新导入或充值后恢复
        </a-descriptions-item>
        <a-descriptions-item label="权限要求">需具备「数据清空」权限</a-descriptions-item>
      </a-descriptions>

      <a-space>
        <a-button
          v-if="can('system:database_clear')"
          status="danger"
          :loading="clearingBalance"
          @click="handleClearBalanceConfirm"
        >
          清空余额数据
        </a-button>
      </a-space>

      <div v-if="lastBalanceResult" class="result-info">
        <a-alert :type="lastBalanceResult.success ? 'success' : 'error'" style="margin-top: 16px">
          {{ lastBalanceResult.message }}
        </a-alert>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { Message, Modal } from '@arco-design/web-vue'
import service from '@/api'
import { handleError } from '@/utils/errorHandler'
import { useUserStore } from '@/stores/user'
import type { ApiResponse } from '@/types'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

const AFFECTED_TABLES = [
  'customers',
  'customer_profiles',
  'customer_balances',
  'customer_tags',
  'profile_tags',
  'invoices',
  'invoice_items',
  'consumption_records',
  'daily_consumptions',
  'daily_orders',
  'pricing_rules',
  'recharge_records',
] as const

const CONSUMPTION_TABLES = [
  'daily_consumptions',
  'daily_orders',
  'sync_tasks',
  'sync_task_logs',
] as const

const BALANCE_TABLES = ['customer_balances', 'recharge_records', 'consumption_records'] as const

const INVOICE_TABLES = [
  'invoices',
  'invoice_items',
  'consumption_records (关联结算单的记录)',
] as const

const clearing = ref(false)
const clearingConsumption = ref(false)
const clearingInvoices = ref(false)
const clearingBalance = ref(false)
const lastResult = ref<{ success: boolean; message: string } | null>(null)
const lastConsumptionResult = ref<{ success: boolean; message: string } | null>(null)
const lastInvoiceResult = ref<{ success: boolean; message: string } | null>(null)
const lastBalanceResult = ref<{ success: boolean; message: string } | null>(null)

interface ClearData {
  deleted_count: number
}

interface ConsumptionClearData {
  deleted_count: number
  daily_consumptions_deleted: number
  daily_orders_deleted: number
}

interface BalanceClearData {
  deleted_count: number
  balances_deleted: number
  recharges_deleted: number
  consumption_records_deleted: number
}

interface InvoiceClearData {
  deleted_count: number
  invoices_deleted: number
  invoice_items_deleted: number
  consumption_records_linked_deleted: number
}

const handleClearConfirm = () => {
  Modal.confirm({
    title: '确认清空客户数据',
    content:
      '此操作将不可恢复地删除所有客户及关联数据（含客户画像、标签、结算记录、发票、每日订单等），确定继续？',
    okText: '确定清空',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    hideCancel: false,
    onBeforeOk: async () => {
      clearing.value = true
      try {
        const res = (await service.post<ClearData>(
          '/system/database/clear'
        )) as unknown as ApiResponse<ClearData>
        if (res.code === 0) {
          const deletedCount = res.data?.deleted_count ?? 0
          const msg = res.message || `成功清空 ${deletedCount} 条客户数据`
          Message.success(msg)
          lastResult.value = { success: true, message: msg }
        } else {
          const msg = res.message || '数据清空失败：请稍后重试'
          Message.error(msg)
          lastResult.value = { success: false, message: msg }
        }
      } catch (error) {
        handleError(error, '数据清空失败')
        lastResult.value = { success: false, message: '数据清空失败' }
      } finally {
        clearing.value = false
      }
      return true
    },
  })
}

const handleClearConsumptionConfirm = () => {
  Modal.confirm({
    title: '确认清空消耗分析数据',
    content: '此操作将不可恢复地删除所有每日订单和每日消费记录（含同步任务记录），确定继续？',
    okText: '确定清空',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    hideCancel: false,
    onBeforeOk: async () => {
      clearingConsumption.value = true
      try {
        const res = (await service.post<ConsumptionClearData>(
          '/system/database/clear-consumption'
        )) as unknown as ApiResponse<ConsumptionClearData>
        if (res.code === 0) {
          const msg = res.message || '消耗分析数据清空成功'
          Message.success(msg)
          lastConsumptionResult.value = { success: true, message: msg }
        } else {
          const msg = res.message || '消耗分析数据清空失败：请稍后重试'
          Message.error(msg)
          lastConsumptionResult.value = { success: false, message: msg }
        }
      } catch (error) {
        handleError(error, '消耗分析数据清空失败')
        lastConsumptionResult.value = { success: false, message: '消耗分析数据清空失败' }
      } finally {
        clearingConsumption.value = false
      }
      return true
    },
  })
}

const handleClearInvoicesConfirm = () => {
  Modal.confirm({
    title: '确认清空结算单数据',
    content: '此操作将不可恢复地删除所有结算单及结算单明细（含关联结算单的消费流水），确定继续？',
    okText: '确定清空',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    hideCancel: false,
    onBeforeOk: async () => {
      clearingInvoices.value = true
      try {
        const res = (await service.post<InvoiceClearData>(
          '/system/database/clear-invoices'
        )) as unknown as ApiResponse<InvoiceClearData>
        if (res.code === 0) {
          const msg = res.message || '结算单数据清空成功'
          Message.success(msg)
          lastInvoiceResult.value = { success: true, message: msg }
        } else {
          const msg = res.message || '结算单数据清空失败：请稍后重试'
          Message.error(msg)
          lastInvoiceResult.value = { success: false, message: msg }
        }
      } catch (error) {
        handleError(error, '结算单数据清空失败')
        lastInvoiceResult.value = { success: false, message: '结算单数据清空失败' }
      } finally {
        clearingInvoices.value = false
      }
      return true
    },
  })
}

const handleClearBalanceConfirm = () => {
  Modal.confirm({
    title: '确认清空余额数据',
    content: '此操作将不可恢复地删除所有客户余额、充值记录和消费流水，确定继续？',
    okText: '确定清空',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    hideCancel: false,
    onBeforeOk: async () => {
      clearingBalance.value = true
      try {
        const res = (await service.post<BalanceClearData>(
          '/system/database/clear-balance'
        )) as unknown as ApiResponse<BalanceClearData>
        if (res.code === 0) {
          const msg = res.message || '余额数据清空成功'
          Message.success(msg)
          lastBalanceResult.value = { success: true, message: msg }
        } else {
          const msg = res.message || '余额数据清空失败：请稍后重试'
          Message.error(msg)
          lastBalanceResult.value = { success: false, message: msg }
        }
      } catch (error) {
        handleError(error, '余额数据清空失败')
        lastBalanceResult.value = { success: false, message: '余额数据清空失败' }
      } finally {
        clearingBalance.value = false
      }
      return true
    },
  })
}
</script>

<style scoped>
.database-management {
  padding: 0;
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.result-info {
  margin-top: 16px;
}
</style>
