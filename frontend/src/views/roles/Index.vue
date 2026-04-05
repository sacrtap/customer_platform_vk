<template>
  <div class="role-list">
    <a-card>
      <template #title>
        <a-space>
          <span>角色管理</span>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><icon-plus /></template>
            新建角色
          </a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data="data" :loading="loading" row-key="id">
        <template #name="{ record }">
          <a-space>
            <span>{{ record.name }}</span>
            <a-tag v-if="record.is_system" color="red">系统</a-tag>
          </a-space>
        </template>
        <template #permissions="{ record }">
          <a-tag v-for="perm in record.permissions" :key="perm.id" color="arcoblue">{{ perm.name }}</a-tag>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="text" size="small" :disabled="record.is_system" @click="showEditModal(record)">编辑</a-button>
            <a-button type="text" size="small" @click="showPermissionModal(record)">权限</a-button>
            <a-button
              type="text"
              size="small"
              status="danger"
              :disabled="record.is_system"
              @click="handleDelete(record)"
            >
              删除
            </a-button>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 创建/编辑角色弹窗 -->
    <a-modal v-model:visible="modalVisible" :title="modalTitle" :confirm-loading="modalLoading" @ok="handleSubmit">
      <a-form :model="formData" layout="vertical">
        <a-form-item label="角色名称" :rules="[{ required: true, message: '请输入角色名称' }]">
          <a-input v-model="formData.name" :disabled="isEdit" placeholder="请输入角色名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model="formData.description" placeholder="请输入角色描述" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 权限分配弹窗 -->
    <a-modal v-model:visible="permissionModalVisible" title="分配权限" :confirm-loading="permissionLoading" @ok="handlePermissionSubmit">
      <a-transfer
        v-model="selectedPermissionIds"
        :data="permissionOptions"
        title-text="可选权限"
        :selected-keys="selectedPermissionIds"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconPlus } from '@arco-design/web-vue/es/icon'
import api from '@/api'

interface Role {
  id: number
  name: string
  description: string
  is_system: boolean
  permissions: { id: number; name: string }[]
}

interface Permission {
  id: number
  code: string
  name: string
}

const columns = [
  { title: '角色名称', dataIndex: 'name', slotName: 'name' },
  { title: '描述', dataIndex: 'description' },
  { title: '权限', slotName: 'permissions' },
  { title: '操作', slotName: 'action', width: 200 },
]

const data = ref<Role[]>([])
const loading = ref(false)
const permissions = ref<Permission[]>([])

const modalVisible = ref(false)
const modalTitle = ref('新建角色')
const modalLoading = ref(false)
const isEdit = ref(false)

const permissionModalVisible = ref(false)
const permissionLoading = ref(false)
const currentRoleId = ref<number | null>(null)
const selectedPermissionIds = ref<number[]>([])

const permissionOptions = computed(() =>
  permissions.value.map((p) => ({
    value: p.id,
    label: `${p.name} (${p.code})`,
  }))
)

const formData = reactive({
  id: null as number | null,
  name: '',
  description: '',
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await api.get('/roles')
    data.value = res.data
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '加载失败')
  } finally {
    loading.value = false
  }
}

const fetchPermissions = async () => {
  try {
    const res = await api.get('/permissions')
    permissions.value = res.data
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '加载权限失败')
  }
}

const showCreateModal = () => {
  isEdit.value = false
  modalTitle.value = '新建角色'
  Object.assign(formData, { id: null, name: '', description: '' })
  modalVisible.value = true
}

const showEditModal = (record: Role) => {
  isEdit.value = true
  modalTitle.value = '编辑角色'
  Object.assign(formData, {
    id: record.id,
    name: record.name,
    description: record.description,
  })
  modalVisible.value = true
}

const handleSubmit = async () => {
  modalLoading.value = true
  try {
    if (isEdit.value) {
      await api.put(`/roles/${formData.id}`, {
        name: formData.name,
        description: formData.description,
      })
      Message.success('更新成功')
    } else {
      await api.post('/roles', {
        name: formData.name,
        description: formData.description,
      })
      Message.success('创建成功')
    }
    modalVisible.value = false
    fetchData()
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

const showPermissionModal = (record: Role) => {
  currentRoleId.value = record.id
  selectedPermissionIds.value = record.permissions.map((p) => p.id)
  permissionModalVisible.value = true
}

const handlePermissionSubmit = async () => {
  permissionLoading.value = true
  try {
    await api.post(`/roles/${currentRoleId.value}/permissions`, {
      permission_ids: selectedPermissionIds.value,
    })
    Message.success('权限分配成功')
    permissionModalVisible.value = false
    fetchData()
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '分配失败')
  } finally {
    permissionLoading.value = false
  }
}

const handleDelete = (record: Role) => {
  Modal.warning({
    title: '确认删除',
    content: `确定要删除角色 ${record.name} 吗？`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        await api.delete(`/roles/${record.id}`)
        Message.success('删除成功')
        fetchData()
      } catch (err: unknown) {
        Message.error(((err as Error)?.message) || '删除失败')
      }
    },
  })
}

onMounted(() => {
  fetchData()
  fetchPermissions()
})
</script>

<style scoped>
.role-list {
  padding: 20px;
}
</style>
