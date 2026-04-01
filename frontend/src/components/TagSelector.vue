<template>
  <div class="tag-selector">
    <a-select
      v-model="selectedTagIds"
      :options="tagOptions"
      multiple
      allow-clear
      allow-create
      placeholder="请选择或输入标签"
      :loading="loading"
      @change="handleChange"
      style="width: 100%"
    >
      <template #label="{ data }">
        <a-tag :color="getTagColor(data.type)">{{ data.label }}</a-tag>
      </template>
      <template #option="{ data }">
        <a-space>
          <a-tag :color="getTagColor(data.type)">{{ data.label }}</a-tag>
          <span v-if="data.category" style="font-size: 12px; color: var(--color-text-3)">
            {{ data.category }}
          </span>
        </a-space>
      </template>
    </a-select>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { getTags } from '@/api/tags'

interface TagOption {
  value: number
  label: string
  type: 'customer' | 'profile'
  category?: string
}

const props = defineProps<{
  modelValue?: number[]
  tagType?: 'customer' | 'profile'
}>()

const emit = defineEmits<{
  'update:modelValue': (value: number[]) => void
  change: (value: number[]) => void
}>()

const selectedTagIds = computed({
  get: () => props.modelValue || [],
  set: (value) => emit('update:modelValue', value),
})

const tagOptions = ref<TagOption[]>([])
const loading = ref(false)

const fetchTags = async () => {
  loading.value = true
  try {
    const res = await getTags({
      type: props.tagType,
      page_size: 100,
    })
    tagOptions.value = res.data.list.map((tag: any) => ({
      value: tag.id,
      label: tag.name,
      type: tag.type,
      category: tag.category,
    }))
  } catch (err: any) {
    console.error('加载标签失败:', err)
  } finally {
    loading.value = false
  }
}

const getTagColor = (type: string) => {
  return type === 'customer' ? 'blue' : 'purple'
}

const handleChange = (value: number[]) => {
  emit('change', value)
}

watch(() => props.tagType, fetchTags, { immediate: true })

onMounted(() => {
  fetchTags()
})
</script>

<style scoped>
.tag-selector {
  width: 100%;
}
</style>
