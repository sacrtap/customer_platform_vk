<template>
  <div class="role-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>角色权限</h1>
        <p class="header-subtitle">角色管理与权限配置</p>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="$message.info('新建角色开发中')">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
            </svg>
          </template>
          新建角色
        </a-button>
      </div>
    </div>
    
    <div class="table-section">
      <a-table :columns="columns" :data="data" :loading="loading" row-key="id" :pagination="pagination">
        <template #is_system="{ record }">
          <a-tag v-if="record.is_system" color="blue">系统角色</a-tag>
          <a-tag v-else color="gray">自定义</a-tag>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="$message.info('权限配置开发中')">权限配置</a-button>
            <a-button type="text" size="small" @click="$message.info('编辑开发中')" :disabled="record.is_system">编辑</a-button>
            <a-popconfirm content="确认删除？" @ok="$message.info('删除开发中')">
              <a-button type="text" size="small" status="danger" :disabled="record.is_system">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const loading = ref(false)

const pagination = {
  current: 1,
  pageSize: 20,
  total: 30,
  showTotal: true,
  showPageSize: true,
}

const columns = [
  { title: '角色名称', dataIndex: 'name', width: 150 },
  { title: '描述', dataIndex: 'description', width: 300 },
  { title: '类型', slotName: 'is_system', width: 120 },
  { title: '创建时间', dataIndex: 'created_at', width: 180 },
  { title: '操作', slotName: 'action', width: 280, fixed: 'right' as const },
]

const data = ref([
  { id: 1, name: '系统管理员', description: '系统最高权限，可管理所有功能', is_system: true, created_at: '2026-01-01' },
  { id: 2, name: '运营经理', description: '负责客户管理、结算配置、数据分析', is_system: true, created_at: '2026-01-01' },
  { id: 3, name: '销售', description: '客户跟进、业务管理', is_system: true, created_at: '2026-01-01' },
  { id: 4, name: '数据分析师', description: '查看数据分析报表', is_system: true, created_at: '2026-01-01' },
  { id: 5, name: '高层管理者', description: '全局数据查看、决策支持', is_system: true, created_at: '2026-01-01' },
])
</script>

<style scoped>
.role-management-page {
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-6: #646a73;
  --neutral-10: #1d2330;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

.header-actions {
  display: flex;
  gap: 12px;
}

.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
</style>
