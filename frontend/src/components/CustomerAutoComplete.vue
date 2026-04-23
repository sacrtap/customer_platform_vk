<template>
  <a-auto-complete
    :model-value="displayText"
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

interface CustomerOption {
  value: string
  label: string
  id: number
}

const props = withDefaults(
  defineProps<{
    modelValue?: number
    placeholder?: string
    width?: number | string
  }>(),
  {
    modelValue: undefined,
    placeholder: '请输入客户名称搜索',
    width: 250,
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: number | undefined]
}>()

const displayText = ref('')
const autocompleteOptions = ref<CustomerOption[]>([])
const idByName = ref<Map<string, number>>(new Map())
let searchTimer: ReturnType<typeof setTimeout> | null = null

const handleInput = (value: string) => {
  displayText.value = value
  if (value === '' && props.modelValue !== undefined) {
    emit('update:modelValue', undefined)
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
      idByName.value = new Map()
      return
    }

    try {
      const res = await getCustomers({ keyword: value.trim(), page: 1, page_size: 50 })
      const list = res.data?.list || []
      const options: CustomerOption[] = []
      const nameToId = new Map<string, number>()

      for (const customer of list) {
        options.push({
          value: customer.name,
          label: customer.name,
          id: customer.id,
        })
        nameToId.set(customer.name, customer.id)
      }

      autocompleteOptions.value = options
      idByName.value = nameToId
    } catch (error) {
      console.error('客户搜索失败:', error)
      Message.error('客户搜索失败，请稍后重试')
      autocompleteOptions.value = []
      idByName.value = new Map()
    }
  }, 300)
}

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

const handleSelect = (value: string) => {
  displayText.value = value
  const customerId = idByName.value.get(value)
  emit('update:modelValue', customerId)
}

const handleClear = () => {
  displayText.value = ''
  autocompleteOptions.value = []
  idByName.value = new Map()
  emit('update:modelValue', undefined)
}
</script>
