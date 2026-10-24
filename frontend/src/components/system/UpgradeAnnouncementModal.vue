<template>
  <a-modal v-model:visible="isVisible" :width="600" :mask-closable="false" @close="handleClose">
    <template #title>
      <div class="upgrade-title">
        <icon-arrow-rise class="upgrade-title-icon" />
        <span class="upgrade-title-text">系统升级公告</span>
      </div>
    </template>
    <div class="upgrade-subtitle">系统近期完成了 {{ updates.length }} 次部署更新</div>
    <div class="upgrade-body">
      <div v-for="(update, index) in updates" :key="update.head_sha" class="deploy-block">
        <div class="deploy-head">
          <span class="deploy-time">{{ fmtCST(update.deployed_at) }}</span>
          <a-tag size="small" color="green">部署成功</a-tag>
          <span class="deploy-count">共 {{ update.commits.length }} 条提交</span>
        </div>
        <ul class="commit-list">
          <li v-for="commit in update.commits" :key="commit.sha" class="commit-item">
            <span class="commit-sha">{{ commit.sha }}</span>
            <span class="commit-message" :title="commit.message">{{ commit.message }}</span>
            <span class="commit-meta">{{ commit.author }} · {{ fmtCST(commit.date) }}</span>
          </li>
        </ul>
        <div v-if="index < updates.length - 1" class="deploy-divider" />
      </div>
    </div>
    <template #footer>
      <div class="upgrade-footer">
        <a-button @click="openGitHub">在 GitHub 查看完整记录</a-button>
        <a-button type="primary" @click="handleClose">我知道了</a-button>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { IconArrowRise } from '@arco-design/web-vue/es/icon'
import type { DeployUpdate } from '@/api/system'

const props = defineProps<{
  visible: boolean
  updates: DeployUpdate[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  close: []
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

/** ISO UTC → 北京时间展示串（后端返回 UTC，公告按 CST 阅读） */
const fmtCST = (iso: string) =>
  new Date(iso).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })

const openGitHub = () => {
  const url = props.updates[0]?.html_url
  if (url) window.open(url, '_blank')
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}
</script>

<style scoped>
.upgrade-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.upgrade-title-icon {
  color: var(--color-success-light-4, #00b42a);
  font-size: 18px;
}

.upgrade-title-text {
  font-size: 16px;
  font-weight: 600;
}

.upgrade-subtitle {
  margin-bottom: 12px;
  color: var(--color-text-3);
  font-size: 13px;
}

.upgrade-body {
  height: 440px;
  overflow-y: auto;
  padding: 16px 20px;
}

.deploy-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.deploy-time {
  font-weight: 600;
  font-size: 14px;
}

.deploy-count {
  color: var(--color-text-3);
  font-size: 12px;
}

.commit-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.commit-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 0 3px 12px;
  border-left: 2px solid var(--color-border-2);
  font-size: 13px;
}

.commit-sha {
  flex-shrink: 0;
  color: var(--color-text-3);
  font-family: monospace;
  font-size: 12px;
}

.commit-message {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.commit-meta {
  flex-shrink: 0;
  color: var(--color-text-3);
  font-size: 12px;
}

.deploy-divider {
  margin: 12px 0;
  border-top: 1px dashed var(--color-border-2);
}

.upgrade-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
