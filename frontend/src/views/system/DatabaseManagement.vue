<template>
  <div class="database-management">
    <div class="page-header">
      <div class="header-title">
        <h1>数据库管理</h1>
        <p class="header-subtitle">系统级数据操作管理</p>
      </div>
    </div>

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
          customers、customer_profiles、customer_balances、customer_tags、profile_tags、
          invoices、invoice_items、consumption_records、daily_usage、pricing_rules、recharge_records
        </a-descriptions-item>
        <a-descriptions-item label="权限要求">需具备「数据清空」权限</a-descriptions-item>
      </a-descriptions>

      <a-space>
        <a-button
          status="danger"
          :loading="clearing"
          @click="handleClearConfirm"
        >
          清空客户数据
        </a-button>
      </a-space>

      <div v-if="lastResult" class="result-info">
        <a-alert
          :type="lastResult.success ? 'success' : 'error'"
          style="margin-top: 16px"
        >
          {{ lastResult.message }}
        </a-alert>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import service from '@/api'

const clearing = ref(false)
const lastResult = ref<{ success: boolean; message: string } | null>(null)

interface ClearResponse {
  code: number
  message: string
  data: {
    deleted_count: number
  }
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
        const response = await service.post<ClearResponse>('/system/database/clear')
        const { data } = response
        if (data.code === 0) {
          lastResult.value = {
            success: true,
            message: data.message || `成功清空 ${data.data?.deleted_count || 0} 条客户数据`,
          }
          Message.success(lastResult.value.message)
        } else {
          const msg = data.message || '数据清空失败'
          lastResult.value = { success: false, message: msg }
          Message.error(msg)
        }
      } catch (error: any) {
        const msg =
          error.response?.data?.message || '数据清空失败，请稍后重试'
        lastResult.value = { success: false, message: msg }
        Message.error(msg)
      } finally {
        clearing.value = false
      }
      // Modal 的 onBeforeOk 返回 false 阻止关闭（让用户看到结果）
      return false
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
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--neutral-6);
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.result-info {
  margin-top: 16px;
}
</style>
