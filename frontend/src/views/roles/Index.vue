<template>
  <div class="role-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>角色权限</h1>
        <p class="header-subtitle">角色管理与权限配置</p>
      </div>
      <div class="header-actions">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索角色名或描述"
          style="width: 300px"
          allow-clear
          @search="handleSearch"
          @clear="handleSearch"
          @press-enter="handleSearch"
        />
        <a-button v-if="can('roles:create')" type="primary" @click="handleCreate">
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
          新建角色
        </a-button>
      </div>
    </div>

    <div class="table-section">
      <a-table
        :columns="columns"
        :data="roles"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #is_system="{ record }">
          <a-tag :color="record.isSystem ? 'blue' : 'gray'" size="small">
            {{ record.isSystem ? '系统角色' : '自定义角色' }}
          </a-tag>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button
              v-if="can('roles:assign')"
              type="text"
              size="small"
              @click="handlePermissionConfig(record)"
            >
              权限配置
            </a-button>
            <a-button
              v-if="can('roles:edit')"
              type="text"
              size="small"
              :disabled="record.isSystem"
              @click="handleEdit(record)"
            >
              编辑
            </a-button>
            <a-popconfirm
              v-if="can('roles:delete')"
              content="确认删除该角色？删除后无法恢复。"
              :disabled="record.isSystem"
              @ok="handleDelete(record.id)"
            >
              <a-button type="text" size="small" status="danger" :disabled="record.isSystem">
                删除
              </a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无角色数据" description="点击「新建角色」创建第一个角色">
            <template #action>
              <a-button v-if="can('roles:create')" type="primary" @click="handleCreate"
                >新建角色</a-button
              >
            </template>
          </EmptyState>
        </template>
        <template #created_at="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
      </a-table>
    </div>

    <!-- 角色编辑对话框 -->
    <a-modal
      v-model:visible="roleModalVisible"
      :title="isEditMode ? '编辑角色' : '新建角色'"
      :confirm-loading="submitting"
      width="500px"
      @before-ok="handleRoleSubmit"
      @cancel="handleRoleModalCancel"
    >
      <a-form ref="roleFormRef" :model="roleForm" :rules="roleFormRules" layout="vertical">
        <a-form-item field="name" label="角色名称">
          <a-input v-model="roleForm.name" placeholder="请输入角色名称" />
        </a-form-item>
        <a-form-item field="description" label="描述">
          <a-textarea
            v-model="roleForm.description"
            placeholder="请输入角色描述"
            :max-length="200"
            show-word-limit
            :auto-size="{ minRows: 3, maxRows: 6 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 权限配置对话框 -->
    <a-modal
      v-model:visible="permissionModalVisible"
      :title="`${currentRole?.name || ''} - 权限配置`"
      :confirm-loading="savingPermissions"
      width="700px"
      @before-ok="handlePermissionSubmit"
      @cancel="handlePermissionModalCancel"
    >
      <div class="permission-config">
        <div class="permission-header">
          <span class="permission-count"> 已选择 {{ selectedPermissionIds.length }} 项权限 </span>
          <a-button size="small" @click="toggleAllPermissions">
            {{ isAllPermissionsSelected ? '取消全选' : '全选' }}
          </a-button>
        </div>
        <a-tree
          v-if="permissionsTree.length > 0"
          v-model:checked-keys="selectedPermissionIds"
          :data="permissionsTree"
          checkable
          :field-names="{ key: 'id', title: 'name', children: 'children' }"
        />
        <a-empty v-else description="暂无可用权限" />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import {
  getRoles,
  getRole,
  createRole,
  updateRole,
  deleteRole,
  getPermissions,
  updateRolePermissions,
  type Role as ApiRole,
} from '@/api/roles'
import EmptyState from '@/components/EmptyState.vue'
import { formatDateTime } from '@/utils/formatters'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// ========== 类型定义 ==========
interface Role {
  id: number
  name: string
  description?: string
  isSystem: boolean
  createdAt?: string
}

interface Permission {
  id: number
  code: string
  name: string
  description?: string
  module?: string
}

// ========== 状态管理 ==========
const loading = ref(false)
const roles = ref<Role[]>([])
const searchKeyword = ref('')
const allPermissions = ref<Permission[]>([])

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
  { title: 'ID', dataIndex: 'id', width: 70, align: 'right' as const },
  { title: '角色名称', dataIndex: 'name', width: 140 },
  { title: '描述', dataIndex: 'description', width: 280, ellipsis: true, tooltip: true },
  { title: '类型', slotName: 'is_system', width: 100, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 160 },
  { title: '操作', slotName: 'action', width: 220, fixed: 'right' as const },
]

// ========== 角色表单 ==========
const roleModalVisible = ref(false)
const isEditMode = ref(false)
const submitting = ref(false)
const roleFormRef = ref<FormInstance>()
const editingRoleId = ref<number | null>(null)

const roleForm = reactive({
  name: '',
  description: '',
})

const roleFormRules = {
  name: [{ required: true, message: '请输入角色名称' }],
}

// ========== 权限配置 ==========
const permissionModalVisible = ref(false)
const savingPermissions = ref(false)
const currentRole = ref<Role | null>(null)
const selectedPermissionIds = ref<number[]>([])

interface PermissionTreeNode {
  id: string | number
  name: string
  title: string
  children?: PermissionTreeNode[]
}


// 模块英文标识到中文名称的映射（与侧边栏菜单保持一致）
const MODULE_NAME_MAP: Record<string, string> = {
  customers: '客户管理',
  billing: '结算管理',
  analytics: '客户分析',
  tags: '标签管理',
  users: '用户管理',
  roles: '角色权限',
  system: '系统设置',
  groups: '客户分组',
  files: '文件管理',
  webhooks: 'Webhook 管理',
  profiles: '客户画像',
}
const permissionsTree = computed(() => {
  const tree: PermissionTreeNode[] = []
  const moduleMap = new Map<string, PermissionTreeNode>()

  allPermissions.value.forEach((perm) => {
    const moduleKey = perm.module || '其他'
    const moduleName = MODULE_NAME_MAP[moduleKey] || moduleKey
    if (!moduleMap.has(moduleKey)) {
      const moduleNode = {
        id: `module-${moduleKey}`,
        name: moduleName,
        title: moduleName,
        children: [],
      }
      moduleMap.set(moduleKey, moduleNode)
      tree.push(moduleNode)
    }
    const moduleNode = moduleMap.get(moduleKey)!
    moduleNode.children!.push({
      id: perm.id,
      name: perm.name,
      title: perm.name,
    })
  })

  return tree
})
const isAllPermissionsSelected = computed(() => {
  const allPermIds = allPermissions.value.map((p) => p.id)
  return allPermIds.length > 0 && allPermIds.every((id) => selectedPermissionIds.value.includes(id))
})

// ========== 数据加载 ==========
const loadRoles = async () => {
  loading.value = true
  try {
    const res = await getRoles({
      page: pagination.current,
      page_size: pagination.pageSize,
      keyword: searchKeyword.value || undefined,
    })
    const data = res.data as any
    roles.value = ((data.list as ApiRole[]) || []).map((item: ApiRole) => ({
      ...item,
      isSystem: item.isSystem || false,
    }))
    pagination.total = (data.total as number) || 0
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载角色列表失败')
  } finally {
    loading.value = false
  }
}

const loadPermissions = async () => {
  try {
    const res = await getPermissions()
    allPermissions.value = res.data || []
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载权限列表失败')
  }
}

// ========== 事件处理 ==========
const handleSearch = () => {
  pagination.current = 1
  loadRoles()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  loadRoles()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  loadRoles()
}

const handleCreate = () => {
  isEditMode.value = false
  editingRoleId.value = null
  Object.assign(roleForm, {
    name: '',
    description: '',
  })
  roleModalVisible.value = true
}

const handleEdit = (record: Role) => {
  isEditMode.value = true
  editingRoleId.value = record.id
  Object.assign(roleForm, {
    name: record.name,
    description: record.description || '',
  })
  roleModalVisible.value = true
}

const handleRoleModalCancel = () => {
  roleModalVisible.value = false
  roleFormRef.value?.resetFields()
}

const handleRoleSubmit = async () => {
  try {
    await roleFormRef.value?.validate()
  } catch {
    return false
  }

  submitting.value = true
  try {
    if (isEditMode.value && editingRoleId.value) {
      await updateRole(editingRoleId.value, {
        name: roleForm.name,
        description: roleForm.description || undefined,
      })
      Message.success('角色更新成功')
    } else {
      await createRole({
        name: roleForm.name,
        description: roleForm.description || undefined,
      })
      Message.success('角色创建成功')
    }
    loadRoles()
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '操作失败')
    return false
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteRole(id)
    Message.success('删除成功')
    loadRoles()
  } catch (error: unknown) {
    Message.error((error as Error).message || '删除失败')
  }
}

const handlePermissionConfig = async (record: Role) => {
  currentRole.value = record
  selectedPermissionIds.value = []

  try {
    const res = await getRole(record.id)
    const roleData = res.data as ApiRole
    selectedPermissionIds.value = roleData.permissions?.map((p) => p.id) || []
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载角色权限失败')
  }

  permissionModalVisible.value = true
}

const handlePermissionModalCancel = () => {
  permissionModalVisible.value = false
  currentRole.value = null
  selectedPermissionIds.value = []
}

const handlePermissionSubmit = async () => {
  if (!currentRole.value) return false

  // 过滤掉模块节点 ID（字符串），只保留数字类型的权限 ID
  const validPermIds = selectedPermissionIds.value.filter(
    (id): id is number => typeof id === 'number'
  )

  savingPermissions.value = true
  try {
    await updateRolePermissions(currentRole.value.id, validPermIds)
    Message.success('权限配置成功')
    loadRoles()
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '权限配置失败')
    return false
  } finally {
    savingPermissions.value = false
  }
}

const toggleAllPermissions = () => {
  if (isAllPermissionsSelected.value) {
    selectedPermissionIds.value = []
  } else {
    selectedPermissionIds.value = allPermissions.value.map((p) => p.id)
  }
}

onMounted(() => {
  loadRoles()
  loadPermissions()
})
</script>

<style scoped>
.role-management-page {
  padding: 0; /* 移除 padding，由 Dashboard 统一提供 */
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
  font-size: 20px;
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

.permission-config {
  max-height: 500px;
  overflow-y: auto;
}

.permission-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--neutral-2);
}

.permission-count {
  font-size: 14px;
  color: var(--neutral-6);
}
</style>
