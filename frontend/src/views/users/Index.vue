<template>
  <div class="user-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>用户管理</h1>
        <p class="header-subtitle">系统账号与权限管理</p>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="$message.info('新建用户开发中')">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
            </svg>
          </template>
          新建用户
        </a-button>
      </div>
    </div>
    
    <div class="table-section">
      <a-table :columns="columns" :data="data" :loading="loading" row-key="id" :pagination="pagination">
        <template #status="{ record }">
          <span :class="['status-badge', record.is_active ? 'success' : 'danger']">
            <span class="status-dot"></span>
            {{ record.is_active ? '启用' : '禁用' }}
          </span>
        </template>
        <template #action>
          <a-space>
            <a-button type="text" size="small" @click="$message.info('编辑开发中')">编辑</a-button>
            <a-button type="text" size="small" @click="$message.info('重置密码开发中')">重置密码</a-button>
            <a-popconfirm content="确认删除？" @ok="$message.info('删除开发中')">
              <a-button type="text" size="small" status="danger">删除</a-button>
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
  total: 50,
  showTotal: true,
  showPageSize: true,
}

const columns = [
  { title: '用户名', dataIndex: 'username', width: 150 },
  { title: '邮箱', dataIndex: 'email', width: 200 },
  { title: '真实姓名', dataIndex: 'real_name', width: 120 },
  { title: '角色', dataIndex: 'roles', width: 150 },
  { title: '状态', slotName: 'status', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', width: 180 },
  { title: '操作', slotName: 'action', width: 280, fixed: 'right' as const },
]

const data = ref([
  { id: 1, username: 'admin', email: 'admin@example.com', real_name: '管理员', roles: ['系统管理员'], is_active: true, created_at: '2026-01-01' },
  { id: 2, username: 'liming', email: 'liming@example.com', real_name: '李明', roles: ['运营经理'], is_active: true, created_at: '2026-02-15' },
  { id: 3, username: 'wangwu', email: 'wangwu@example.com', real_name: '王五', roles: ['销售'], is_active: true, created_at: '2026-03-01' },
  { id: 4, username: 'zhaoliu', email: 'zhaoliu@example.com', real_name: '赵六', roles: ['数据分析师'], is_active: false, created_at: '2026-03-10' },
])
</script>

<style scoped>
.user-management-page {
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-10: #1d2330;
  --success-1: #e8ffea;
  --success-6: #22c55e;
  --danger-1: #ffe8e8;
  --danger-6: #ef4444;
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

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.success {
  background: var(--success-1);
  color: var(--success-6);
}

.status-badge.danger {
  background: var(--danger-1);
  color: var(--danger-6);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
</style>
