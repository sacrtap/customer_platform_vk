<template>
  <!-- 导入对话框 -->
  <a-modal
    v-model:visible="isVisible"
    title="导入客户"
    :confirm-loading="importLoading"
    width="560px"
    :hide-cancel="false"
    @cancel="resetState"
  >
    <div class="import-modal-content">
      <a-alert type="info" style="margin-bottom: 20px">
        请下载模板文件，填写后上传 Excel 文件进行导入
        <template #action>
          <a-button type="text" size="small" @click="downloadTemplate">
            <template #icon>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            </template>
            下载模板
          </a-button>
        </template>
      </a-alert>

      <div
        class="upload-area"
        @click="triggerFileInput"
        @drop.prevent="handleFileDrop"
        @dragover.prevent
        @dragenter.prevent
      >
        <input
          ref="fileInputRef"
          type="file"
          accept=".xlsx,.xls"
          class="file-input-hidden"
          @change="handleFileInputChange"
        />
        <div v-if="!importFile" class="upload-placeholder">
          <div class="upload-icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <div class="upload-text-primary">点击或拖拽文件到此处</div>
          <div class="upload-text-secondary">仅支持 .xlsx / .xls 格式的 Excel 文件</div>
        </div>
        <div v-else class="file-selected">
          <div class="file-icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>
          <div class="file-info">
            <div class="file-name">{{ importFile.name }}</div>
            <div class="file-size">{{ formatFileSize(importFile.size) }}</div>
          </div>
          <div class="file-remove" @click.stop="removeFile">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </div>
        </div>
      </div>

      <!-- 预检查结果区 -->
      <div v-if="previewResult" class="preview-result">
        <div class="preview-summary">
          <span class="preview-ok">可入库：{{ previewResult.success_count }} 条</span>
          <span class="preview-error">错误：{{ previewResult.error_count }} 条</span>
        </div>
        <div v-if="previewResult.errors?.length" class="preview-errors">
          <div class="preview-errors-title">错误明细（含行号）：</div>
          <ul class="preview-errors-list">
            <li v-for="(err, idx) in previewResult.errors ?? []" :key="idx">{{ err }}</li>
          </ul>
          <div
            v-if="previewResult.error_count > (previewResult.errors?.length ?? 0)"
            class="preview-more"
          >
            ... 还有
            {{ previewResult.error_count - (previewResult.errors?.length ?? 0) }} 条错误未显示
          </div>
        </div>
      </div>

      <div class="import-tips">
        <div class="tips-title">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          导入须知
        </div>
        <ul class="tips-list">
          <li>请使用下载的模板文件填写客户信息</li>
          <li>确保必填字段（公司 ID、客户名称等）已填写</li>
          <li>单次导入建议不超过 1000 条数据</li>
        </ul>
      </div>
    </div>

    <template #footer>
      <a-button @click="resetState">取消</a-button>
      <a-button :loading="previewLoading" :disabled="!importFile" @click="handlePreview">
        {{ previewResult ? '重新预检查' : '预检查' }}
      </a-button>
      <a-button
        type="primary"
        :loading="importLoading"
        :disabled="!previewResult || previewResult.success_count === 0"
        @click="handleImportSubmit"
      >
        确认导入
      </a-button>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'
import { importCustomers, downloadImportTemplate } from '@/api/customers'
import type { ImportResult } from '@/types'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'imported'): void
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const importLoading = ref(false)
const previewLoading = ref(false)
const importFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const previewResult = ref<ImportResult | null>(null)

const resetState = () => {
  previewResult.value = null
  importFile.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
  isVisible.value = false
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileInputChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    validateAndSetFile(file)
  }
}

const handleFileDrop = (event: DragEvent) => {
  const file = event.dataTransfer?.files[0]
  if (file) {
    validateAndSetFile(file)
  }
}

const validateAndSetFile = (file: File) => {
  const allowedTypes = [
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
  ]
  const allowedExtensions = ['.xlsx', '.xls']
  const hasValidExtension = allowedExtensions.some((ext) => file.name.toLowerCase().endsWith(ext))
  const hasValidType = allowedTypes.includes(file.type)

  if (!hasValidType && !hasValidExtension) {
    Message.error('仅支持上传 Excel 文件（.xlsx 或 .xls）')
    return
  }

  importFile.value = file
  previewResult.value = null // 更换文件后需重新预检查
}

const removeFile = () => {
  importFile.value = null
  previewResult.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const downloadTemplate = async () => {
  try {
    const res = await downloadImportTemplate()
    const blob = res.data as Blob
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '客户导入模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    Message.success('模板下载成功')
  } catch (error: unknown) {
    handleError(error, '下载失败')
  }
}

// 第一步：预检查（dry_run=true，不落库），返回可入库条数与错误明细（含行号）
const handlePreview = async () => {
  if (!importFile.value) {
    Message.error('请选择要导入的文件')
    return
  }

  previewLoading.value = true
  try {
    const res = await importCustomers(importFile.value, true)
    const data = (res as { data: ImportResult }).data
    // 归一化 errors（缺字段兜底 []），避免模板访问 .length 抛 TypeError 白屏
    previewResult.value = { ...data, errors: data.errors ?? [] }
    if (data.error_count === 0) {
      Message.success(`预检查通过：可入库 ${data.success_count} 条`)
    } else {
      Message.warning({
        content: `预检查完成：可入库 ${data.success_count} 条，错误 ${data.error_count} 条`,
        duration: 5000,
      })
    }
  } catch (error: unknown) {
    // 失败时清空旧结果，防止用过期（与当前文件不符）的预检数据直接确认导入
    previewResult.value = null
    handleError(error, '预检查失败')
  } finally {
    previewLoading.value = false
  }
}

// 第二步：确认后真正入库
const handleImportSubmit = async () => {
  if (!importFile.value) {
    Message.error('请选择要导入的文件')
    return
  }
  if (!previewResult.value) {
    Message.error('请先执行预检查')
    return
  }

  importLoading.value = true
  try {
    const res = await importCustomers(importFile.value)
    const data = (res as { data: ImportResult }).data
    const { success_count, error_count, errors } = data

    if (error_count > 0) {
      const errorList =
        errors
          ?.slice(0, 10)
          .map((e: string) => `\u2022 ${e}`)
          .join('\n') || ''
      const moreMsg = error_count > 10 ? `\n... 还有 ${error_count - 10} 条错误` : ''
      Message.warning({
        content: `导入完成：成功 ${success_count} 条，失败 ${error_count} 条\n${errorList}${moreMsg}`,
        duration: 8000,
      })
    } else {
      Message.success(`导入成功，共导入 ${success_count} 条客户数据`)
    }
    emit('imported')
    resetState()
  } catch (error: unknown) {
    handleError(error, '导入失败')
  } finally {
    importLoading.value = false
  }
}
</script>

<style scoped>
:deep(.arco-modal) {
  border-radius: 18px;
}

.import-modal-content {
  padding: 4px 0;
}

.upload-area {
  border: 2px dashed var(--line);
  border-radius: 14px;
  padding: 32px 24px;
  text-align: center;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.upload-area:hover {
  border-color: var(--primary);
  background: #eff6ff;
}

.file-input-hidden {
  display: none;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-icon {
  color: var(--muted);
  opacity: 0.5;
}

.upload-text-primary {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.upload-text-secondary {
  font-size: 12px;
  color: var(--muted);
}

.file-selected {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.file-icon {
  color: var(--primary);
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  text-align: left;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: var(--muted);
}

.file-remove {
  cursor: pointer;
  color: var(--muted);
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.file-remove:hover {
  color: var(--red);
  background: rgba(220, 38, 38, 0.08);
}

.import-tips {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--bg);
  border-radius: var(--radius-sm);
}

.tips-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  margin-bottom: 8px;
}

.tips-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
}

/* 预检查结果区 */
.preview-result {
  margin-top: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.preview-summary {
  display: flex;
  gap: 16px;
  padding: 10px 16px;
  background: var(--bg);
  font-size: 13px;
  font-weight: 600;
}

.preview-ok {
  color: var(--green, #10b981);
}

.preview-error {
  color: var(--red, #dc2626);
}

.preview-errors {
  padding: 10px 16px;
  border-top: 1px solid var(--line);
  max-height: 200px;
  overflow-y: auto;
}

.preview-errors-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  margin-bottom: 6px;
}

.preview-errors-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.6;
}

.preview-more {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
}
</style>
