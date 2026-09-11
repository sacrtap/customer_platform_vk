/**
 * 标签管理 composable — 客户标签的加载、添加、移除
 */
import { ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getTags, getCustomerTags, addCustomerTag, removeCustomerTag } from '@/api/tags'
import type { Tag } from '@/types'
import { useCustomerStore } from '@/stores/customer'

export function useCustomerTags(customerId: () => number) {
  const customerStore = useCustomerStore()

  const tagSelectorVisible = ref(false)
  const tagSelectorLoading = ref(false)
  const customerTags = ref<Tag[]>([])
  const allTags = ref<Tag[]>([])
  const allTagsLoading = ref(false)
  const selectedTags = ref<Tag[]>([])

  const loadCustomerTags = async () => {
    const id = customerId()
    const cachedTags = customerStore.getCachedTags(id)
    if (cachedTags && customerStore.hasCachedTags(id)) {
      customerTags.value = cachedTags.customerTags
      allTags.value = cachedTags.allTags
      return
    }
    try {
      const [customerTagsRes, allTagsRes] = await Promise.all([
        getCustomerTags(id),
        getTags({ type: 'customer', page_size: 100 }),
      ])
      customerTags.value = customerTagsRes.data || []
      allTags.value = allTagsRes.data || []
      customerStore.cacheTagsData(id, {
        customerTags: customerTags.value,
        allTags: allTags.value,
      })
    } catch (error) {
      Message.error('加载标签失败')
      console.error('加载标签失败:', error)
    }
  }

  const openTagSelector = async () => {
    tagSelectorVisible.value = true
    await loadCustomerTags()
    selectedTags.value = []
  }

  const closeTagSelector = () => {
    tagSelectorVisible.value = false
    selectedTags.value = []
  }

  const addTags = async (tagIds: number[]) => {
    tagSelectorLoading.value = true
    try {
      const id = customerId()
      await Promise.all(tagIds.map((tagId) => addCustomerTag(id, tagId)))
      Message.success('标签已添加')
      await loadCustomerTags()
      closeTagSelector()
    } catch (error) {
      Message.error('添加标签失败')
      console.error('添加标签失败:', error)
    } finally {
      tagSelectorLoading.value = false
    }
  }

  const removeTag = async (tagId: number) => {
    try {
      await removeCustomerTag(customerId(), tagId)
      Message.success('标签已移除')
      await loadCustomerTags()
    } catch (error) {
      Message.error('移除标签失败')
      console.error('移除标签失败:', error)
    }
  }

  return {
    tagSelectorVisible,
    tagSelectorLoading,
    customerTags,
    allTags,
    allTagsLoading,
    selectedTags,
    loadCustomerTags,
    openTagSelector,
    closeTagSelector,
    addTags,
    removeTag,
  }
}
