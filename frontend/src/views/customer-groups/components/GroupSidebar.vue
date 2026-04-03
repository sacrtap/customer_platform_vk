<template>
  <a-card class="group-sidebar">
    <template #title>
      <a-space>
        <icon-folder />
        <span>群组</span>
      </a-space>
    </template>

    <a-menu :selected-keys="[selectedGroupId?.toString() || 'all']" @menu-item-click="handleMenuClick">
      <a-menu-item key="all">
        <template #icon><icon-apps /></template>
        全部客户
      </a-menu-item>

      <a-divider style="margin: 8px 0" />

      <a-menu-item key="create">
        <template #icon><icon-plus /></template>
        新建群组
      </a-menu-item>

      <a-divider style="margin: 8px 0" />

      <a-menu-item
        v-for="group in groups"
        :key="group.id.toString()"
        :data-group="group"
      >
        <template #icon>
          <icon-folder v-if="group.group_type === 'dynamic'" />
          <icon-user-group v-else />
        </template>
        {{ group.name }}
      </a-menu-item>
    </a-menu>
  </a-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { IconFolder, IconApps, IconPlus, IconUserGroup } from '@arco-design/web-vue/es/icon'

interface CustomerGroup {
  id: number
  name: string
  group_type: 'dynamic' | 'static'
}

const props = defineProps<{
  groups: CustomerGroup[]
  selectedGroupId: number | null
}>()

const emit = defineEmits<{
  (e: 'update:selectedGroupId', value: number | null): void
  (e: 'select', group: CustomerGroup | null): void
  (e: 'create'): void
}>()

const selectedGroupId = ref(props.selectedGroupId)

const handleMenuClick = (key: string, event: any) => {
  if (key === 'create') {
    emit('create')
  } else if (key === 'all') {
    selectedGroupId.value = null
    emit('update:selectedGroupId', null)
    emit('select', null)
  } else {
    const group = props.groups.find(g => g.id.toString() === key)
    if (group) {
      selectedGroupId.value = group.id
      emit('update:selectedGroupId', group.id)
      emit('select', group)
    }
  }
}
</script>

<style scoped>
.group-sidebar {
  height: fit-content;
}

:deep(.arco-menu-item) {
  margin-bottom: 4px;
}
</style>
