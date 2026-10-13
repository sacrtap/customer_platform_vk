<template>
  <a-modal
    v-model:visible="isVisible"
    title="批量导入充值"
    :footer="false"
    width="560px"
    @cancel="emit('update:visible', false)"
  >
    <div class="import-content">
      <a-alert type="info" style="margin-bottom: 20px">
        请选择文件进行导入：可下载模板填写充值数据，也可直接使用「余额导出」文件回灌充值
        <template #action
          ><a-button type="text" size="small" @click="downloadTemplate"
            >下载模板</a-button
          ></template
        >
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
          accept=".xlsx"
          class="file-input-hidden"
          @change="handleFileInputChange"
        />
        <div v-if="!file" class="upload-placeholder">
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
          <div class="upload-text-secondary">仅支持 .xlsx 格式的 Excel 文件</div>
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
            <div class="file-name">{{ file.name }}</div>
            <div class="file-size">{{ formatFileSize(file.size) }}</div>
          </div>
          <a-button type="text" status="danger" size="small" @click.stop="removeFile"
            >移除</a-button
          >
        </div>
      </div>
      <div v-if="result" class="import-result">
        <a-alert :type="result.error_count === 0 ? 'success' : 'warning'">
          <template #title>{{ previewed ? '预检查结果' : '导入结果' }}</template>
          <div>成功：{{ result.success_count }} 条，失败：{{ result.error_count }} 条</div>
          <div v-if="previewed" class="preview-tip">
            预检查仅提示问题，不会写入数据。确认无误后点击「确认导入」完成充值。
          </div>
          <ul v-if="result.errors?.length" class="error-list">
            <li v-for="(err, i) in result.errors" :key="i">
              {{ typeof err === 'string' ? err : `第 ${err.row} 行：${err.message}` }}
            </li>
          </ul>
        </a-alert>
      </div>
      <div class="import-actions">
        <a-button :disabled="!file || importing" :loading="previewing" long @click="handlePreview">
          预检查
        </a-button>
        <a-button
          type="primary"
          :disabled="!file || !previewed"
          :loading="importing"
          long
          @click="handleSubmit"
        >
          确认导入
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { importBalances, downloadBalanceImportTemplate } from '@/api/billing'

interface ImportResult {
  success_count: number
  error_count: number
  dry_run?: boolean
  errors?: (string | { row: number; message: string })[]
}

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [value: boolean]; success: [] }>()

const isVisible = computed({ get: () => props.visible, set: (val) => emit('update:visible', val) })

const fileInputRef = ref<HTMLInputElement>()
const file = ref<File | null>(null)
const previewing = ref(false)
const importing = ref(false)
const previewed = ref(false)
const result = ref<ImportResult | null>(null)

const resetState = () => {
  result.value = null
  previewed.value = false
  file.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
  isVisible.value = false
}

const triggerFileInput = () => fileInputRef.value?.click()
const handleFileInputChange = (event: Event) => {
  const t = event.target as HTMLInputElement
  if (t.files?.[0]) validateAndSetFile(t.files[0])
}
const handleFileDrop = (event: DragEvent) => {
  if (event.dataTransfer?.files[0]) validateAndSetFile(event.dataTransfer.files[0])
}
const validateAndSetFile = (f: File) => {
  if (!f.type.includes('spreadsheetml') && !f.name.endsWith('.xlsx')) {
    Message.error('仅支持 .xlsx 格式的 Excel 文件')
    return
  }
  if (f.size > 10 * 1024 * 1024) {
    Message.error('文件大小不能超过 10MB')
    return
  }
  file.value = f
  result.value = null
  previewed.value = false // 更换文件后需重新预检查
}
const removeFile = () => {
  file.value = null
  result.value = null
  previewed.value = false
  if (fileInputRef.value) fileInputRef.value.value = ''
}
const formatFileSize = (b: number) => {
  if (b === 0) return '0 B'
  const k = 1024,
    s = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(b) / Math.log(k))
  return parseFloat((b / Math.pow(k, i)).toFixed(2)) + ' ' + s[i]
}

const downloadTemplate = async () => {
  const res = await downloadBalanceImportTemplate()
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = '余额导入模板.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

// 第一步：预检查（dry_run=true，不落库），返回可入库条数与错误明细（含行号）
const handlePreview = async () => {
  if (!file.value) {
    Message.warning('请选择要导入的文件')
    return
  }
  previewing.value = true
  try {
    const res = await importBalances(file.value, true)
    result.value = res.data as ImportResult
    previewed.value = true
    if (res.data.error_count === 0) {
      Message.success(`预检查通过：可导入 ${res.data.success_count} 条`)
    } else {
      Message.warning({
        content: `预检查完成：可导入 ${res.data.success_count} 条，错误 ${res.data.error_count} 条`,
        duration: 5000,
      })
    }
  } catch (error: unknown) {
    Message.error((error as Error).message || '预检查失败')
  } finally {
    previewing.value = false
  }
}

// 第二步：确认导入（正式落库，仅导入预检查通过的行）
const handleSubmit = async () => {
  if (!file.value) {
    Message.warning('请选择要导入的文件')
    return false
  }
  importing.value = true
  try {
    const res = await importBalances(file.value)
    result.value = res.data as ImportResult
    previewed.value = false
    if (res.data.error_count === 0) {
      Message.success(`导入成功：${res.data.success_count} 条`)
      emit('success')
      resetState()
    } else {
      Message.warning({
        content: `导入完成：成功 ${res.data.success_count} 条，失败 ${res.data.error_count} 条`,
        duration: 5000,
      })
    }
    return res.data.error_count === 0
  } catch (error: unknown) {
    Message.error((error as Error).message || '导入失败')
    return false
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.import-content {
  padding: 0;
}
.upload-area {
  border: 1px dashed var(--line);
  border-radius: 12px;
  padding: 32px 16px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
}
.upload-area:hover {
  border-color: var(--primary);
}
.file-input-hidden {
  display: none;
}
.upload-icon {
  color: var(--muted);
}
.upload-text-primary {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink);
}
.upload-text-secondary {
  font-size: 12px;
  color: var(--muted);
}
.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.file-selected {
  display: flex;
  align-items: center;
  gap: 12px;
}
.file-icon {
  color: var(--green);
}
.file-info {
  flex: 1;
  text-align: left;
}
.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink);
}
.file-size {
  font-size: 12px;
  color: var(--muted);
}
.import-result {
  margin-top: 16px;
}
.preview-tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
}
.import-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}
.import-actions .arco-btn {
  flex: 1;
}
.error-list {
  margin-top: 8px;
  padding-left: 16px;
  font-size: 12px;
  color: var(--red);
}
</style>
