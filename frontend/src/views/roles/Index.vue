<template>
  <div class="role-management-page">
    <PageHeader eyebrow="System" title="角色权限" subtitle="角色管理与权限配置">
      <template #actions>
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索角色名或描述"
          style="width: 300px"
          allow-clear
          @search="handleSearch"
          @clear="handleSearch"
          @press-enter="handleSearch"
        />
        <a-button v-if="can('roles:export')" :loading="exporting" @click="handleExport"
          >导出</a-button
        >
        <a-button v-if="can('roles:import')" @click="importVisible = true">导入</a-button>
        <a-button v-if="can('roles:create')" type="primary" @click="handleCreate"
          >新建角色</a-button
        >
      </template>
    </PageHeader>

    <DataTable
      :columns="columns"
      :data="roles"
      :loading="loading"
      row-key="id"
      :pagination="pagination"
      :scroll="{ x: 900 }"
      :storage-key="'roles_table_columns'"
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
    </DataTable>

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
      width="900px"
      @before-ok="handlePermissionSubmit"
      @cancel="handlePermissionModalCancel"
    >
      <div class="permission-config">
        <div class="permission-header">
          <span class="permission-count"> 已选择 {{ selectedPermissionIds.length }} 项权限 </span>
          <a-input
            v-model="permissionKeyword"
            placeholder="搜索权限名称/编码"
            allow-clear
            style="width: 240px"
          />
          <a-button size="small" @click="toggleAllPermissions">
            {{ isAllPermissionsSelected ? '取消全选' : '全选' }}
          </a-button>
        </div>
        <div v-if="permissionGroups.length > 0" class="permission-groups-grid">
          <section v-for="group in permissionGroups" :key="group.key" class="permission-group-card">
            <header class="permission-group-header">
              <div>
                <div class="permission-group-title">{{ group.title }}</div>
                <div class="permission-group-count">
                  {{
                    group.permissions.filter((perm) => selectedPermissionIds.includes(perm.id))
                      .length
                  }}
                  / {{ group.permissions.length }} 项
                </div>
              </div>
              <a-button size="small" @click="togglePermissionGroup(group)">
                {{ isGroupAllSelected(group) ? '取消全选' : '全选' }}
              </a-button>
            </header>

            <a-checkbox-group v-model="selectedPermissionIds" class="permission-list">
              <a-tooltip
                v-for="permission in group.permissions"
                :key="permission.id"
                :content="permissionTooltip(group, permission)"
                position="top"
              >
                <a-checkbox
                  :value="permission.id"
                  :class="[
                    'permission-item',
                    { 'permission-item--dangerous': isDangerousPermission(permission) },
                  ]"
                >
                  <div class="permission-item-content">
                    <span class="permission-name">{{ permission.name }}</span>
                    <span class="permission-code">{{ permission.code }}</span>
                  </div>
                </a-checkbox>
              </a-tooltip>
            </a-checkbox-group>
          </section>
        </div>
        <a-empty v-if="permissionGroups.length === 0" description="暂无可用权限" />
      </div>
    </a-modal>

    <!-- 导入弹窗 -->
    <ImportModal
      v-model:visible="importVisible"
      title="批量导入角色"
      :import-api="importRoles"
      :template-api="fetchRoleTemplate"
      template-file-name="角色导入模板.xlsx"
      @success="loadRoles"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import DataTable, { type DataTableColumn } from '@/components/DataTable.vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { handleError } from '@/utils/errorHandler'
import {
  getRoles,
  getRole,
  createRole,
  updateRole,
  deleteRole,
  getPermissions,
  updateRolePermissions,
  importRoles,
  fetchRoleTemplate,
  exportRoles,
  type Role as ApiRole,
} from '@/api/roles'
import {
  buildPermissionGroups,
  filterPermissionsByKeyword,
  type PermissionGroup,
} from './permissionGroups'
import EmptyState from '@/components/EmptyState.vue'
import ImportModal from '@/views/billing/components/ImportModal.vue'
import { useExportAction } from '@/composables/useExportAction'
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
const columns: DataTableColumn[] = [
  { key: 'id', title: 'ID', dataIndex: 'id', width: 56, align: 'right', defaultVisible: true },
  {
    key: 'name',
    title: '角色名称',
    dataIndex: 'name',
    width: 94,
    defaultVisible: true,
  },
  {
    key: 'description',
    title: '描述',
    dataIndex: 'description',
    ellipsis: true,
    tooltip: true,
    defaultVisible: true,
  },
  {
    key: 'is_system',
    title: '类型',
    slotName: 'is_system',
    width: 106,
    align: 'center',
    defaultVisible: true,
  },
  {
    key: 'created_at',
    title: '创建时间',
    slotName: 'created_at',
    width: 156,
    defaultVisible: true,
  },
  {
    key: 'action',
    title: '操作',
    slotName: 'action',
    fixed: 'right' as const,
    width: 206,
    defaultVisible: true,
  },
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
const permissionKeyword = ref('')

/** 高危权限：授予前需确认业务必要性（删除/清空/同步管理等破坏性或全局性操作） */
const DANGEROUS_PERMISSION_CODES = [
  'system:database_clear',
  'system:database_backup',
  'sync_tasks:manage',
  'customers:delete',
  'users:delete',
  'roles:delete',
  'files:delete',
  'billing:delete',
  'erp_systems:manage',
  'api_keys:manage',
]

const isDangerousPermission = (perm: Permission) => DANGEROUS_PERMISSION_CODES.includes(perm.code)

/** 权限项 hover 提示：分组路径 + 权限码 + 描述；高危权限追加警告前缀 */
const permissionTooltip = (group: PermissionGroup, permission: Permission): string => {
  const base = `${group.title} · ${permission.name}（${permission.code}）`
  const desc = permission.description ? `：${permission.description}` : ''
  return isDangerousPermission(permission)
    ? `高危权限，请谨慎授予 — ${base}${desc}`
    : `${base}${desc}`
}

/** 搜索关键词过滤后的权限（全选/计数均基于当前可见集合） */
const filteredPermissions = computed(() =>
  filterPermissionsByKeyword(allPermissions.value, permissionKeyword.value)
)

const permissionGroups = computed(() => buildPermissionGroups(filteredPermissions.value))

const isGroupAllSelected = (group: PermissionGroup<Permission>) =>
  group.permissions.length > 0 &&
  group.permissions.every((perm) => selectedPermissionIds.value.includes(perm.id))

const togglePermissionGroup = (group: PermissionGroup<Permission>) => {
  const groupIds = group.permissions.map((perm) => perm.id)
  if (isGroupAllSelected(group)) {
    selectedPermissionIds.value = selectedPermissionIds.value.filter((id) => !groupIds.includes(id))
  } else {
    selectedPermissionIds.value = Array.from(new Set([...selectedPermissionIds.value, ...groupIds]))
  }
}
const isAllPermissionsSelected = computed(() => {
  const visibleIds = filteredPermissions.value.map((p) => p.id)
  return visibleIds.length > 0 && visibleIds.every((id) => selectedPermissionIds.value.includes(id))
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
    const data = res.data as { list?: ApiRole[]; total?: number }
    roles.value = ((data.list as ApiRole[]) || []).map((item: ApiRole) => ({
      ...item,
      isSystem: item.isSystem || false,
    }))
    pagination.total = (data.total as number) || 0
  } catch (error: unknown) {
    handleError(error, '加载角色列表失败')
  } finally {
    loading.value = false
  }
}

const loadPermissions = async () => {
  try {
    const res = await getPermissions()
    allPermissions.value = res.data || []
  } catch (error: unknown) {
    handleError(error, '加载权限列表失败')
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

// ========== 导入/导出 ==========
const importVisible = ref(false)

const { exporting, run } = useExportAction({
  exportApi: exportRoles,
  filename: () => `roles_${new Date().toISOString().slice(0, 10)}.xlsx`,
  onSuccess: (res) => {
    if (res.headers?.['x-truncated'] === 'true') {
      Message.warning('数据超过 5 万条，仅导出了前 5 万条，请缩小筛选范围后再导出')
    }
  },
})

const handleExport = () => {
  run(undefined)
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
    handleError(error, '角色创建或更新失败')
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
    handleError(error, '角色删除失败')
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
    handleError(error, '加载角色权限失败')
  }

  permissionModalVisible.value = true
}

const handlePermissionModalCancel = () => {
  permissionModalVisible.value = false
  currentRole.value = null
  selectedPermissionIds.value = []
  permissionKeyword.value = ''
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
    handleError(error, '权限配置失败')
    return false
  } finally {
    savingPermissions.value = false
  }
}

const toggleAllPermissions = () => {
  const visibleIds = filteredPermissions.value.map((p) => p.id)
  if (isAllPermissionsSelected.value) {
    // 取消全选：仅移除当前可见（过滤后）集合，保留搜索外的既有选择
    selectedPermissionIds.value = selectedPermissionIds.value.filter(
      (id) => !visibleIds.includes(id)
    )
  } else {
    selectedPermissionIds.value = Array.from(
      new Set([...selectedPermissionIds.value, ...visibleIds])
    )
  }
}

onMounted(() => {
  loadRoles()
  loadPermissions()
})
</script>

<style scoped>
.role-management-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.header-info h1 {
  margin: 4px 0 2px 0;
  font-size: 26px;
  font-weight: 850;
  color: var(--ink);
  line-height: 1.2;
}

.header-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.permission-config {
  max-height: 620px;
  overflow-y: auto;
}

.permission-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.permission-count {
  font-size: 14px;
  color: var(--muted);
}

.permission-groups-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.permission-group-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel);
  padding: 14px;
  min-width: 0;
}

.permission-group-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}

.permission-group-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

.permission-group-count {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
}

.permission-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.permission-item {
  align-items: center;
}

.permission-item-content {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}

.permission-name {
  font-size: 14px;
  color: var(--ink);
  line-height: 1.5;
}

.permission-code {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.4;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* 高危权限：warning 色左边框标识（如删除、清空数据、同步管理等破坏性操作） */
.permission-item--dangerous {
  border-left: 3px solid var(--red);
  padding-left: 8px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
</style>
