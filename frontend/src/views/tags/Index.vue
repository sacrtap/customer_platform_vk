<template>
  <div class="tag-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>标签管理</h1>
        <p class="header-subtitle">自定义标签分类与管理</p>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="$message.info('新建标签开发中')">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
              />
            </svg>
          </template>
          新建标签
        </a-button>
      </div>
    </div>

    <div class="tabs-section">
      <a-tabs v-model="activeTab">
        <a-tab-pane key="customer" title="客户标签">
          <div class="tag-list">
            <a-tag
              v-for="tag in customerTags"
              :key="tag.id"
              closable
              @close="$message.info('删除开发中')"
            >
              {{ tag.name }} ({{ tag.count }})
            </a-tag>
          </div>
        </a-tab-pane>
        <a-tab-pane key="profile" title="画像标签">
          <div class="tag-list">
            <a-tag
              v-for="tag in profileTags"
              :key="tag.id"
              closable
              @close="$message.info('删除开发中')"
            >
              {{ tag.name }} ({{ tag.count }})
            </a-tag>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const activeTab = ref('customer')

const customerTags = ref([
  { id: 1, name: '重点客户', count: 28 },
  { id: 2, name: '潜力客户', count: 56 },
  { id: 3, name: '一般客户', count: 120 },
  { id: 4, name: '沉睡客户', count: 35 },
])

const profileTags = ref([
  { id: 1, name: '大型企业', count: 45 },
  { id: 2, name: '中型企业', count: 89 },
  { id: 3, name: '小型企业', count: 156 },
  { id: 4, name: '互联网行业', count: 78 },
  { id: 5, name: '金融行业', count: 42 },
])
</script>

<style scoped>
.tag-management-page {
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-6: #646a73;
  --neutral-10: #1d2330;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--neutral-6);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.tabs-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  padding: 24px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 0;
}
</style>
