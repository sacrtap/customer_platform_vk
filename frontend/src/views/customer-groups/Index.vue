<template>
  <div class="customer-groups-page">
    <a-page-header title="客户分群" subtitle="管理客户群组" />

    <div class="groups-layout">
      <!-- 左侧边栏 -->
      <GroupSidebar
        v-model:selectedGroupId="selectedGroupId"
        :groups="groups"
        @create="showCreateModal"
        @select="handleGroupSelect"
      />

      <!-- 右侧内容 -->
      <a-card class="groups-content">
        <template #title>
          <a-space>
            <span>{{ currentGroupTitle }}</span>
            <a-tag v-if="selectedGroup" :color="selectedGroup.group_type === 'dynamic' ? 'blue' : 'green'">
              {{ selectedGroup.group_type === 'dynamic' ? '动态群组' : '静态群组' }}
            </a-tag>
          </a-space>
        </template>

        <!-- 客户表格 -->
        <a-table
          :columns="columns"
          :data="customers"
          :loading="loading"
          :pagination="pagination"
          row-key="id"
          @page-change="onPageChange"
        >
          <template #actions="{ record }">
            <a-space>
              <a-button type="text" size="small" @click="handleViewCustomer(record)">
                查看
              </a-button>
              <a-button
                v-if="selectedGroup?.group_type === 'static'"
                type="text"
                size="small"
                status="danger"
                @click="handleRemoveMember(record.id)"
              >
                移除
              </a-button>
            </a-space>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- 新建群组表单 -->
    <GroupForm
      v-model:visible="formVisible"
      :default-filter="defaultFilter"
      :submitting="submitting"
      @submit="handleCreateGroup"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { CustomerGroup, CreateGroupParams } from '@/types/customer-groups'
import * as groupApi from '@/api/customer-groups'
import GroupSidebar from './components/GroupSidebar.vue'
import GroupForm from './components/GroupForm.vue'

interface ApiError {
  message?: string
  code?: number
}

interface Customer {
  id: number
  name: string
  company_id: string | number
}

const router = useRouter()

const groups = ref<CustomerGroup[]>([])
const selectedGroupId = ref<number | null>(null)
const selectedGroup = ref<CustomerGroup | null>(null)
const customers = ref<Customer[]>([])
const loading = ref(false)
const submitting = ref(false)
const formVisible = ref(false)
const defaultFilter = ref<Record<string, unknown> | null>(null)

const currentGroupTitle = computed(() => {
  if (!selectedGroup.value) return '全部客户'
  return selectedGroup.value.name
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})

const columns = [
  { title: 'ID', dataIndex: 'id', width: 80 },
  { title: '公司名称', dataIndex: 'name', width: 200 },
  { title: '公司 ID', dataIndex: 'company_id', width: 120 },
  { title: '操作', slotName: 'actions', width: 150 },
]

const fetchGroups = async () => {
  try {
    const res = await groupApi.getCustomerGroups()
    groups.value = res.data.list || res.data
  } catch (err: unknown) {
    const error = err as ApiError
    Message.error(error?.message || '加载群组失败')
  }
}

const fetchCustomers = async () => {
  if (!selectedGroupId.value) {
    router.push('/customers')
    return
  }

  loading.value = true
  try {
    const res = await groupApi.applyGroupFilter(selectedGroupId.value, {
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    customers.value = res.data.list
    pagination.total = res.data.total
  } catch (err: unknown) {
    const error = err as ApiError
    Message.error(error?.message || '加载客户失败')
  } finally {
    loading.value = false
  }
}

const handleGroupSelect = (group: CustomerGroup | null) => {
  selectedGroup.value = group
  selectedGroupId.value = group?.id || null
  pagination.current = 1
  if (group) {
    fetchCustomers()
  }
}

const showCreateModal = (filter?: Record<string, unknown>) => {
  defaultFilter.value = filter || null
  formVisible.value = true
}

const handleCreateGroup = async (data: CreateGroupParams) => {
  submitting.value = true
  try {
    await groupApi.createCustomerGroup(data)
    Message.success('创建成功')
    formVisible.value = false
    await fetchGroups()
  } catch (err: unknown) {
    const error = err as ApiError
    Message.error(error?.message || '创建失败')
  } finally {
    submitting.value = false
  }
}

const handleRemoveMember = async (customer_id: number) => {
  if (!selectedGroupId.value) return

  try {
    await groupApi.removeGroupMember(selectedGroupId.value, customer_id)
    Message.success('移除成功')
    fetchCustomers()
  } catch (err: unknown) {
    const error = err as ApiError
    Message.error(error?.message || '移除失败')
  }
}

const handleViewCustomer = (customer: Customer) => {
  window.open(`/customers/${customer.id}`, '_blank')
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchCustomers()
}

onMounted(() => {
  fetchGroups()
})
</script>

<style scoped>
.customer-groups-page {
  padding: 20px;
}

.groups-layout {
  display: flex;
  gap: 16px;
  margin-top: 16px;
}

GroupSidebar {
  width: 280px;
  flex-shrink: 0;
}

.groups-content {
  flex: 1;
}
</style>
