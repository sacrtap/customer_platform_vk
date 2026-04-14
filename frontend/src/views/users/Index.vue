<template>
  <div class="user-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>用户管理</h1>
        <p class="header-subtitle">系统账号与权限管理</p>
      </div>
      <div class="header-actions">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索用户名、姓名或邮箱"
          style="width: 300px"
          allow-clear
          @search="handleSearch"
          @clear="handleSearch"
          @press-enter="handleSearch"
        />
        <a-button v-if="can('users:create')" type="primary" @click="handleCreate">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
              />
            </svg>
          </template>
          新建用户
        </a-button>
      </div>
    </div>

    <div class="table-section">
      <a-table
        :columns="columns"
        :data="users"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        :scroll="{ x: 'max-content' }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #status="{ record }">
          <span :class="['status-badge', record.is_active ? 'success' : 'danger']">
            <span class="status-dot"></span>
            {{ record.is_active ? '启用' : '禁用' }}
          </span>
        </template>
        <template #roles="{ record }">
          <a-tooltip
            v-if="record.roles && record.roles.length > 0"
            :content="record.roles?.map((r: { name: string }) => r.name).join(', ') || '-'"
          >
            <span>
              <a-tag
                v-for="(role, index) in record.roles"
                v-show="index === 0"
                :key="role.id"
                size="small"
                style="margin-right: 4px"
              >
                {{ role.name }}
                <span v-if="record.roles.length > 1" style="font-size: 10px; opacity: 0.8"
                  >+{{ record.roles.length - 1 }}</span
                >
              </a-tag>
            </span>
          </a-tooltip>
          <span v-else>-</span>
        </template>
        <template #created_at="{ record }">
          <a-tooltip :content="formatDateTime(record.created_at)">
            <span>{{ formatDateTime(record.created_at) }}</span>
          </a-tooltip>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button v-if="can('users:edit')" type="text" size="small" @click="handleEdit(record)">编辑</a-button>
            <a-button type="text" size="small" @click="handleResetPassword(record)">
              重置密码
            </a-button>
            <a-popconfirm v-if="can('users:delete')" content="确认删除该用户？删除后无法恢复。" @ok="handleDelete(record.id)">
              <a-button type="text" size="small" status="danger" class="delete-btn">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无用户数据" description="点击「新建用户」添加第一个用户">
            <template #action>
              <a-button v-if="can('users:create')" type="primary" @click="handleCreate">新建用户</a-button>
            </template>
          </EmptyState>
        </template>
      </a-table>
    </div>

    <!-- 用户编辑对话框 -->
    <a-modal
      v-model:visible="userModalVisible"
      :title="isEditMode ? '编辑用户' : '新建用户'"
      :confirm-loading="submitting"
      width="500px"
      @ok="handleUserSubmit"
      @cancel="handleUserModalCancel"
    >
      <a-form ref="userFormRef" :model="userForm" :rules="userFormRules" layout="vertical">
        <a-form-item field="username" label="用户名">
          <a-input v-model="userForm.username" placeholder="请输入用户名" :disabled="isEditMode" />
        </a-form-item>
        <a-form-item v-if="!isEditMode" field="password" label="密码">
          <a-input-password v-model="userForm.password" placeholder="请输入密码" />
        </a-form-item>
        <a-form-item field="email" label="邮箱">
          <a-input v-model="userForm.email" placeholder="请输入邮箱" />
        </a-form-item>
        <a-form-item field="real_name" label="真实姓名">
          <a-input v-model="userForm.real_name" placeholder="请输入真实姓名" />
        </a-form-item>
        <a-form-item v-if="isEditMode" field="is_active" label="状态">
          <a-switch v-model="userForm.is_active" />
        </a-form-item>
        <a-form-item field="role_ids" label="角色">
          <a-select
            v-model="userForm.role_ids"
            placeholder="请选择角色"
            multiple
            style="width: 100%"
          >
            <a-option v-for="role in availableRoles" :key="role.id" :value="role.id">
              {{ role.name }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 重置密码对话框 -->
    <a-modal
      v-model:visible="passwordModalVisible"
      title="重置密码"
      :confirm-loading="resettingPassword"
      width="400px"
      @before-ok="handlePasswordSubmit"
      @cancel="handlePasswordModalCancel"
    >
      <a-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordFormRules"
        layout="vertical"
      >
        <a-form-item field="newPassword" label="新密码">
          <a-input-password v-model="passwordForm.newPassword" placeholder="请输入新密码" />
        </a-form-item>
        <a-form-item field="confirmPassword" label="确认密码">
          <a-input-password v-model="passwordForm.confirmPassword" placeholder="请再次输入新密码" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  resetPassword,
  assignUserRoles,
  type User as ApiUser,
} from '@/api/users'
import { getRoles } from '@/api/roles'
import EmptyState from '@/components/EmptyState.vue'
import { formatDateTime } from '@/utils/formatters'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// ========== 类型定义 ==========
interface User {
  id: number
  username: string
  email: string | null
  real_name: string | null
  is_active: boolean
  is_system: boolean
  roles: string[]
  role_ids: number[]
  created_at: string
}

interface Role {
  id: number
  name: string
  description?: string
}

// ========== 状态管理 ==========
const loading = ref(false)
const users = ref<User[]>([])
const searchKeyword = ref('')
const availableRoles = ref<Role[]>([])

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 表格列定义
const columns = [
  { title: 'ID', dataIndex: 'id', width: 60, align: 'right' as const },
  { title: '用户名', dataIndex: 'username', width: 100, ellipsis: true, tooltip: true },
  { title: '邮箱', dataIndex: 'email', width: 200, ellipsis: true, tooltip: true },
  { title: '真实姓名', dataIndex: 'real_name', width: 90, ellipsis: true, tooltip: true },
  { title: '角色', slotName: 'roles', width: 120 },
  { title: '状态', slotName: 'status', width: 90, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 170 },
  { title: '操作', slotName: 'action', width: 190, fixed: 'right' as const },
]

// ========== 用户表单 ==========
const userModalVisible = ref(false)
const isEditMode = ref(false)
const submitting = ref(false)
const userFormRef = ref<FormInstance>()
const editingUserId = ref<number | null>(null)

const userForm = reactive({
  username: '',
  password: '',
  email: '',
  real_name: '',
  is_active: true,
  role_ids: [] as number[],
})

const userFormRules = {
  username: [
    { required: true, message: '请输入用户名' },
    { minLength: 3, message: '用户名至少 3 个字符' },
  ],
  password: [
    { required: true, message: '请输入密码' },
    { minLength: 6, message: '密码至少 6 个字符' },
  ],
  email: [
    { required: true, message: '请输入邮箱' },
    {
      validator: (value: string, callback: (error?: Error) => void) => {
        if (!value) {
          callback()
          return
        }
        // 严格的邮箱正则校验
        const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
        if (!emailRegex.test(value)) {
          callback(new Error('请输入有效的邮箱地址'))
        } else {
          callback()
        }
      },
    },
  ],
  real_name: [{ required: true, message: '请输入真实姓名' }],
  role_ids: [
    { required: true, message: '请选择角色' },
    {
      validator: (value: number[], callback: (error?: Error) => void) => {
        if (!value || value.length === 0) {
          callback(new Error('请至少选择一个角色'))
        } else {
          callback()
        }
      },
    },
  ],
}

// ========== 密码重置表单 ==========
const passwordModalVisible = ref(false)
const resettingPassword = ref(false)
const passwordFormRef = ref<FormInstance>()
const resettingUserId = ref<number | null>(null)

const passwordForm = reactive({
  newPassword: '',
  confirmPassword: '',
})

const passwordFormRules = {
  newPassword: [
    { required: true, message: '请输入新密码' },
    { minLength: 6, message: '密码至少 6 个字符' },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码' },
    {
      validator: (value: string | undefined, callback: (error?: Error) => void) => {
        if (!value) {
          callback()
          return
        }
        if (value !== passwordForm.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
    },
  ],
}

// ========== 数据加载 ==========
const loadUsers = async () => {
  loading.value = true
  try {
    const res = await getUsers({
      page: pagination.current,
      page_size: pagination.pageSize,
      keyword: searchKeyword.value || undefined,
    })
    users.value = ((res.data as Record<string, unknown>).list as ApiUser[]).map((item: ApiUser) => ({
      ...item,
      roles: item.roles || [],
      role_ids: item.roles?.map((r) => r.id) || [],
    }))
    pagination.total = ((res.data as Record<string, unknown>).total as number) || 0
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载用户列表失败')
  } finally {
    loading.value = false
  }
}

const loadRoles = async () => {
  try {
    const res = await getRoles({ page: 1, page_size: 100 })
    availableRoles.value = (res.data as Record<string, unknown>).list as Array<Record<string, unknown>> || []
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载角色列表失败')
  }
}

// ========== 事件处理 ==========
const handleSearch = () => {
  pagination.current = 1
  loadUsers()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  loadUsers()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  loadUsers()
}

const handleCreate = () => {
  isEditMode.value = false
  editingUserId.value = null
  Object.assign(userForm, {
    username: '',
    password: '',
    email: '',
    real_name: '',
    is_active: true,
    role_ids: [],
  })
  userModalVisible.value = true
}

const handleEdit = (record: User) => {
  isEditMode.value = true
  editingUserId.value = record.id
  Object.assign(userForm, {
    username: record.username,
    password: '',
    email: record.email || '',
    real_name: record.real_name || '',
    is_active: record.is_active,
    role_ids: record.role_ids || [],
  })
  userModalVisible.value = true
}

const handleUserModalCancel = () => {
  userModalVisible.value = false
  userFormRef.value?.resetFields()
}

const handleUserSubmit = async () => {
  try {
    await userFormRef.value?.validate()
  } catch (error: unknown) {
    if ((error as Error)?.message) {
      Message.error((error as Error).message)
    }
    return
  }

  submitting.value = true
  try {
    if (isEditMode.value && editingUserId.value) {
      await updateUser(editingUserId.value, {
        email: userForm.email || undefined,
        real_name: userForm.real_name || undefined,
        is_active: userForm.is_active,
      })
      if (userForm.role_ids.length > 0) {
        await assignUserRoles(editingUserId.value, userForm.role_ids)
      }
      Message.success('用户更新成功')
    } else {
      const createUserRes = await createUser({
        username: userForm.username,
        password: userForm.password,
        email: userForm.email || undefined,
        real_name: userForm.real_name || undefined,
      })
      // 为新用户分配角色
      const newUserId = createUserRes.data?.id
      if (newUserId && userForm.role_ids.length > 0) {
        await assignUserRoles(newUserId, userForm.role_ids)
      }
      Message.success('用户创建成功')
    }
    userModalVisible.value = false
    loadUsers()
  } catch (error: unknown) {
    Message.error((error as Error).message || '操作失败')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteUser(id)
    Message.success('删除成功')
    loadUsers()
  } catch (error: unknown) {
    Message.error((error as Error).message || '删除失败')
  }
}

const handleResetPassword = (record: User) => {
  resettingUserId.value = record.id
  Object.assign(passwordForm, {
    newPassword: '',
    confirmPassword: '',
  })
  passwordModalVisible.value = true
}

const handlePasswordModalCancel = () => {
  passwordModalVisible.value = false
  passwordFormRef.value?.resetFields()
}

const handlePasswordSubmit = async () => {
  // 二次校验:确保两次密码一致
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    Message.error('两次输入的密码不一致')
    return false // 阻止模态框关闭
  }

  try {
    await passwordFormRef.value?.validate()
  } catch (error: unknown) {
    if ((error as Error)?.message) {
      Message.error((error as Error).message)
    }
    return false // 阻止模态框关闭
  }

  if (!resettingUserId.value) return false

  resettingPassword.value = true
  try {
    await resetPassword(resettingUserId.value, passwordForm.newPassword)
    Message.success('密码重置成功')
    return true // 允许模态框关闭
  } catch (error: unknown) {
    Message.error((error as Error).message || '密码重置失败')
    return false // 阻止模态框关闭
  } finally {
    resettingPassword.value = false
  }
}

onMounted(() => {
  loadUsers()
  loadRoles()
})
</script>

<style scoped>
.user-management-page {
  padding: 0; /* 移除 padding，由 Dashboard 统一提供 */
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
  font-size: 18px;
  font-weight: 600;
  color: var(--neutral-10);
  margin-bottom: 6px;
}

.header-subtitle {
  font-size: 13px;
  color: var(--neutral-6);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.table-section {
  width: 100%;
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

:deep(.arco-table) {
  font-size: 14px;
}

:deep(.arco-table th) {
  background: var(--neutral-1);
  color: var(--neutral-6);
  font-weight: 600;
}

:deep(.arco-table td) {
  color: var(--neutral-7);
}

:deep(.arco-table tr:hover td) {
  background: var(--neutral-1);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
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
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
</style>
