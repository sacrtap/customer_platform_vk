<template>
  <div ref="rootRef" class="search-input-wrap">
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      aria-hidden="true"
    >
      <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
    <input
      ref="inputRef"
      v-model="localKeyword"
      type="text"
      placeholder="搜索客户名称 / 公司 ID"
      @input="onInput"
      @keydown.enter="onEnter"
      @keydown.down.prevent="moveHighlight(1)"
      @keydown.up.prevent="moveHighlight(-1)"
      @focus="onFocus"
    />

    <!-- 联想下拉 -->
    <transition name="fade">
      <div
        v-if="showDropdown && (suggestions.length > 0 || loadingSuggestions)"
        class="suggestions"
      >
        <div v-if="loadingSuggestions" class="suggestion-loading">搜索中…</div>
        <template v-else>
          <div
            v-for="(item, idx) in suggestions"
            :key="item.id"
            class="suggestion-item"
            :class="{ active: idx === highlightIndex }"
            @mousedown.prevent="selectSuggestion(item)"
            @mouseenter="highlightIndex = idx"
          >
            <span class="sug-name">{{ item.name }}</span>
            <span class="sug-id">#{{ item.company_id }}</span>
          </div>
        </template>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { getCustomers } from '@/api/customers'

interface Suggestion {
  id: number
  name: string
  company_id: number
}

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: []
  select: [item: Suggestion]
}>()

const rootRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
const localKeyword = ref(props.modelValue)
const showDropdown = ref(false)
const loadingSuggestions = ref(false)
const suggestions = ref<Suggestion[]>([])
const highlightIndex = ref(-1)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

// 同步外部 modelValue 变化
watch(
  () => props.modelValue,
  (val) => {
    if (val !== localKeyword.value) {
      localKeyword.value = val
    }
  }
)

function onInput() {
  emit('update:modelValue', localKeyword.value)

  if (debounceTimer) clearTimeout(debounceTimer)

  const kw = localKeyword.value.trim()
  if (kw.length < 1) {
    showDropdown.value = false
    suggestions.value = []
    return
  }

  debounceTimer = setTimeout(async () => {
    await fetchSuggestions(kw)
  }, 300)
}

async function fetchSuggestions(keyword: string) {
  loadingSuggestions.value = true
  showDropdown.value = true
  try {
    const res = await getCustomers({
      keyword,
      page: 1,
      page_size: 8,
    })
    suggestions.value = (res.data?.list || []).map((c: Record<string, unknown>) => ({
      id: c.id as number,
      name: c.name as string,
      company_id: c.company_id as number,
    }))
    highlightIndex.value = -1
  } catch {
    suggestions.value = []
  } finally {
    loadingSuggestions.value = false
  }
}

function onFocus() {
  const kw = localKeyword.value.trim()
  if (kw.length >= 1 && suggestions.value.length > 0) {
    showDropdown.value = true
  }
}

function onEnter() {
  if (showDropdown.value && highlightIndex.value >= 0 && suggestions.value[highlightIndex.value]) {
    selectSuggestion(suggestions.value[highlightIndex.value])
  } else {
    showDropdown.value = false
    emit('search')
  }
}

function moveHighlight(dir: number) {
  if (suggestions.value.length === 0) return
  const len = suggestions.value.length
  highlightIndex.value = (highlightIndex.value + dir + len) % len
}

function selectSuggestion(item: Suggestion) {
  localKeyword.value = item.name
  emit('update:modelValue', item.name)
  showDropdown.value = false
  emit('select', item)
  emit('search')
}

function handleClickOutside(e: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) {
    showDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>

<style scoped>
.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  padding: 9px 12px;
  width: 180px;
  flex-shrink: 0;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
  position: relative;
}
.search-input-wrap:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
}
.search-input-wrap svg {
  flex-shrink: 0;
  color: var(--muted);
}
.search-input-wrap input {
  border: 0;
  outline: 0;
  width: 100%;
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: transparent;
}
.search-input-wrap input::placeholder {
  color: var(--muted);
}

/* 联想下拉 */
.suggestions {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 100;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  max-height: 320px;
  overflow-y: auto;
}
.suggestion-loading {
  padding: 12px 16px;
  font-size: 13px;
  color: var(--muted);
  text-align: center;
}
.suggestion-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 14px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}
.suggestion-item:hover,
.suggestion-item.active {
  background: #eff6ff;
}
.sug-name {
  color: var(--ink);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sug-id {
  color: var(--muted);
  font-size: 12px;
  flex-shrink: 0;
  margin-left: 8px;
}

.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 0.15s,
    transform 0.15s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 1100px) {
  .search-input-wrap {
    width: 100%;
  }
}
</style>
