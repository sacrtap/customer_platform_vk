<template>
  <a-auto-complete
    :model-value="modelValue"
    :placeholder="placeholder"
    :data="autocompleteOptions"
    :filter-option="false"
    allow-clear
    :style="{ width: typeof width === 'number' ? width + 'px' : width }"
    @input="handleInput"
    @search="handleSearch"
    @select="handleSelect"
    @clear="handleClear"
  />
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getCustomers } from '@/api/customers'

interface KeywordOption {
  value: string
  label: string
}

const props = withDefaults(
  defineProps<{
    modelValue?: string
    placeholder?: string
    width?: number | string
  }>(),
  {
    modelValue: '',
    placeholder: '请输入公司名称或公司 ID',
    width: '100%',
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const autocompleteOptions = ref<KeywordOption[]>([])
let searchTimer: ReturnType<typeof setTimeout> | null = null

const handleInput = (value: string) => {
  emit('update:modelValue', value)
  if (value === '' && props.modelValue !== '') {
    autocompleteOptions.value = []
  }
}

const handleSearch = (value: string) => {
  // 清除之前的定时器
  if (searchTimer) {
    clearTimeout(searchTimer)
  }

  // 300ms 防抖
  searchTimer = setTimeout(async () => {
    if (!value || value.trim() === '') {
      autocompleteOptions.value = []
      return
    }

    try {
      const res = await getCustomers({ keyword: value.trim(), page: 1, page_size: 50 })
      const list = res.data?.list || []
      const options: KeywordOption[] = []

      for (const customer of list) {
        const label = customer.company_id
          ? `${customer.name}（${customer.company_id}）`
          : customer.name
        options.push({
          value: customer.name,
          label,
        })
      }

      autocompleteOptions.value = options
    } catch (error) {
      console.error('关键词联想搜索失败:', error)
      Message.error('联想搜索失败，请稍后重试')
      autocompleteOptions.value = []
    }
  }, 300)
}

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

const handleSelect = (value: string) => {
  emit('update:modelValue', value)
}

const handleClear = () => {
  autocompleteOptions.value = []
  emit('update:modelValue', '')
}
</script>
