<template>
  <div class="database-management">
    <PageHeader eyebrow="System" title="数据库管理" subtitle="系统级数据操作管理" />

    <a-card :bordered="false">
      <template #title>
        <div class="card-header">
          <span>数据操作</span>
        </div>
      </template>

      <a-alert type="warning" style="margin-bottom: 24px">
        以下操作不可逆，请谨慎执行。清空操作将删除所有客户及关联数据（含客户画像、标签、结算记录、发票等）。
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
  'daily_usage',
  'pricing_rules',
  'recharge_records',
] as const

const clearing = ref(false)
const lastResult = ref<{ success: boolean; message: string } | null>(null)

interface ClearData {
  deleted_count: number
}

const handleClearConfirm = () => {
  Modal.confirm({
    title: '确认清空客户数据',
    content:
      '此操作将不可恢复地删除所有客户及关联数据（含客户画像、标签、结算记录、发票等），确定继续？',
    okText: '确定清空',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    hideCancel: false,
    onBeforeOk: async () => {
      clearing.value = true
      try {
        // 拦截器已返回 ApiResponse 格式（不是 AxiosResponse），res 即 { code, message, data }
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
        // Axios 拦截器 reject 的是 AppError { code, message, category }
        handleError(error, '数据清空失败')
        lastResult.value = { success: false, message: '数据清空失败' }
      } finally {
        clearing.value = false
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

.page-header {
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--muted);
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.result-info {
  margin-top: 16px;
}
</style>
