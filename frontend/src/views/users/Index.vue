<template>
  <div class="user-list">
    <a-card>
      <template #title>
        <a-space>
          <span>用户管理</span>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><icon-plus /></template>
            新建用户
          </a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data="data" :loading="loading" row-key="id" :pagination="pagination">
        <template #username="{ record }">
          <a-space>
            <a-avatar :size="24">{{ record.username.charAt(0).toUpperCase() }}</a-avatar>
            <span>{{ record.username }}</span>
          </a-space>
        </template>
        <template #roles="{ record }">
          <a-tag v-for="role in record.roles" :key="role.id" color="arcoblue">{{ role.name }}</a-tag>
        </template>
        <template #is_active="{ record }">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="showEditModal(record)">编辑</a-button>
            <a-button type="text" size="small" status="danger" @click="handleDelete(record)">删除</a-button>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 创建/编辑用户弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :confirm-loading="modalLoading"
      @ok="handleSubmit"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item label="用户名" :rules="[{ required: true, message: '请输入用户名' }]">
          <a-input v-model="formData.username" :disabled="isEdit" placeholder="请输入用户名" />
        </a-form-item>
        <a-form-item
          v-if="!isEdit"
          label="密码"
          :rules="[{ required: true, message: '请输入密码' }, { min: 6, message: '密码长度不少于 6 位' }]"
        >
          <a-input-password v-model="formData.password" placeholder="请输入密码" />
        </a-form-item>
        <a-form-item label="邮箱">
          <a-input v-model="formData.email" placeholder="请输入邮箱" />
        </a-form-item>
        <a-form-item label="姓名">
          <a-input v-model="formData.real_name" placeholder="请输入姓名" />
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model="formData.role_ids" multiple placeholder="请选择角色" :loading="rolesLoading">
            <a-option v-for="role in roles" :key="role.id" :value="role.id" :label="role.name" />
          </a-select>
        </a-form-item>
        <a-form-item v-if="isEdit" label="状态">
          <a-switch v-model="formData.is_active" checked-children="启用" unchecked-children="禁用" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconPlus } from '@arco-design/web-vue/es/icon'
import api from '@/api'

interface User {
  id: number
  username: string
  email: string
  real_name: string
  is_active: boolean
  is_system: boolean
  roles: { id: number; name: string }[]
}

interface Role {
  id: number
  name: string
  description: string
}

const columns = [
  { title: '用户名', dataIndex: 'username', slotName: 'username' },
  { title: '邮箱', dataIndex: 'email' },
  { title: '姓名', dataIndex: 'real_name' },
  { title: '角色', slotName: 'roles' },
  { title: '状态', slotName: 'is_active' },
  { title: '操作', slotName: 'action', width: 150 },
]

const data = ref<User[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const modalVisible = ref(false)
const modalTitle = ref('新建用户')
const modalLoading = ref(false)
const isEdit = ref(false)
const roles = ref<Role[]>([])
const rolesLoading = ref(false)

const formData = reactive({
  id: null as number | null,
  username: '',
  password: '',
  email: '',
  real_name: '',
  role_ids: [] as number[],
  is_active: true,
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await api.get('/users')
    data.value = res.data.list
    pagination.total = res.data.total
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '加载失败')
  } finally {
    loading.value = false
  }
}

const fetchRoles = async () => {
  rolesLoading.value = true
  try {
    const res = await api.get('/roles')
    roles.value = res.data
  } catch (err: unknown) {
    Message.error(((err as Error)?.message) || '加载角色失败')
  } finally {
    rolesLoading.value = false
  }
}

const showCreateModal = () => {
  isEdit.value = false
  modalTitle.value = '新建用户'
  Object.assign(formData, {
    id: null,
    username: '',
    password: '',
    email: '',
    real_name: '',
    role_ids: [],
    is_active: true,
  })
  modalVisible.value = true
}

const showEditModal = (record: User) => {
  isEdit.value = true
  modalTitle.value = '编辑用户'
  Object.assign(formData, {
    id: record.id,
    username: record.username,
    email: record.email,
    real_name: record.real_name,
    role_ids: record.roles.map((r) => r.id),
    is_active: record.is_active,
  })
  modalVisible.value = true
}

const handleSubmit = async () => {
  modalLoading.value = true
  try {
    if (isEdit.value) {
      await api.put(`/users/${formData.id}`, {
        email: formData.email,
        real_name: formData.real_name,
        is_active: formData.is_active,
        role_ids: formData.role_ids,
      })
      Message.success('更新成功')
    } else {
      await api.post('/users', {
        username: formData.username,
        password: formData.password,
        email: formData.email,
        real_name: formData.real_name,
        role_ids: formData.role_ids,
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

const handleDelete = (record: User) => {
  Modal.warning({
    title: '确认删除',
    content: `确定要删除用户 ${record.username} 吗？`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        await api.delete(`/users/${record.id}`)
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
  fetchRoles()
})
</script>

<style scoped>
.user-list {
  padding: 20px;
}
</style>
