<template>
  <a-modal
    :visible="visible"
    title="添加标签"
    :confirm-loading="loading"
    width="500px"
    @ok="handleAddTag"
    @cancel="handleCancel"
  >
    <a-form layout="vertical">
      <a-form-item label="选择标签" required>
        <a-select
          v-model="selectedTagIds"
          placeholder="请选择标签"
          multiple
          allow-clear
          :loading="allTagsLoading"
        >
          <a-option v-for="tag in availableTags" :key="tag.id" :value="tag.id">
            {{ tag.name }}
          </a-option>
        </a-select>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Tag } from '@/types'

const props = defineProps<{
  visible: boolean
  loading: boolean
  allTags: Tag[]
  allTagsLoading: boolean
  customerTags: Tag[]
}>()

const emit = defineEmits<{
  add: [tagIds: number[]]
  close: []
}>()

const selectedTagIds = ref<number[]>([])

const availableTags = computed(() => {
  const customerTagIds = new Set(props.customerTags.map(t => t.id))
  return props.allTags.filter(t => !customerTagIds.has(t.id))
})

const handleAddTag = () => {
  if (selectedTagIds.value.length === 0) return
  emit('add', [...selectedTagIds.value])
  selectedTagIds.value = []
}

const handleCancel = () => {
  selectedTagIds.value = []
  emit('close')
}
</script>
