<template>
  <a-modal
    v-model:visible="isVisible"
    :title="title"
    :ok-text="loading ? '导入中...' : '开始导入'"
    :confirm-loading="loading"
    width="560px"
    @before-ok="handleSubmit"
    @cancel="emit('update:visible', false)"
  >
    <div class="import-content">
      <a-alert type="info" style="margin-bottom: 20px">
        请下载模板文件，填写后上传 Excel 文件进行导入
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
          <template #title>导入结果</template>
          <div>成功：{{ result.success_count }} 条，失败：{{ result.error_count }} 条</div>
          <ul v-if="result.errors?.length" class="error-list">
            <li v-for="(err, i) in result.errors" :key="i">{{ err }}</li>
          </ul>
        </a-alert>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'

interface ImportResult {
  success_count: number
  error_count: number
  errors?: string[]
}

/**
 * 从任意 reject 值中安全提取可展示的错误文案。
 * 后端经 axios 拦截器统一 reject 为 { code, message, category } 普通对象（非 Error 实例），
 * 因此不能只判 instanceof Error；对 null/undefined 或缺失 message 的情况回退到兜底文案，
 * 避免 `(error as Error).message` 在 error 为 null/undefined 时二次抛 TypeError、用户无任何提示。
 */
const pickErrorMessage = (error: unknown, fallback: string): string => {
  const msg = (error as { message?: unknown } | null | undefined)?.message
  return typeof msg === 'string' && msg ? msg : fallback
}

const props = defineProps<{
  visible: boolean
  /** 弹窗标题，如「批量导入计费规则」 */
  title: string
  /** 导入接口（返回 { data: ImportResult } 的响应） */
  importApi: (file: File) => Promise<{ data: ImportResult }>
  /** 模板下载接口（blob 响应） */
  templateApi: () => Promise<{ data: Blob }>
  /** 下载的模板文件名 */
  templateFileName: string
}>()
const emit = defineEmits<{ 'update:visible': [value: boolean]; success: [] }>()

const isVisible = computed({ get: () => props.visible, set: (val) => emit('update:visible', val) })

const fileInputRef = ref<HTMLInputElement>()
const file = ref<File | null>(null)
const loading = ref(false)
const result = ref<ImportResult | null>(null)

// 本组件由父级常驻挂载（v-model:visible 只控制显隐，关闭不销毁实例），重开时必须清空
// 上次选择与结果，否则用户直接再点「开始导入」会重复提交同一文件 —— 计费规则会重复建
// 数据、结算单会再生成一条、余额充值可能重复入账。同时清空 input.value，否则重新选择
// 同一个文件不会触发 change 事件。
watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    file.value = null
    result.value = null
    loading.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
)

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
}
const removeFile = () => {
  file.value = null
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
  try {
    const res = await props.templateApi()
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = props.templateFileName
    // Firefox 部分版本对不在文档树中的锚点 click() 不触发下载，需先挂载到 DOM；
    // 回收时再 remove，避免遗留无用的 DOM 节点。
    document.body.appendChild(a)
    a.click()
    // 延迟回收 object URL：部分浏览器（Safari/Firefox）可能在下载开始前就撤销，
    // 导致下载失败；用 setTimeout 在下一拍回收，既保证下载已启动又不永久泄漏，
    // 并顺带把已无用的锚点从 DOM 移除。
    setTimeout(() => {
      URL.revokeObjectURL(url)
      a.remove()
    }, 1000)
  } catch (error: unknown) {
    // 模板下载失败时给用户明确提示，避免未处理的 Promise rejection
    Message.error(pickErrorMessage(error, '模板下载失败'))
  }
}

const handleSubmit = async () => {
  if (!file.value) {
    Message.warning('请选择要导入的文件')
    return false
  }
  loading.value = true
  try {
    const res = await props.importApi(file.value)
    result.value = res.data
    if (res.data.success_count > 0) {
      Message.success(`导入成功：${res.data.success_count} 条`)
      emit('success')
    }
    const hasErrors = res.data.error_count > 0
    if (hasErrors) {
      // 部分失败时清空已选文件：此时返回 false 会让弹窗保持打开、确认按钮恢复为
      // 可用的「开始导入」，若不清空，用户看到错误结果后再点一次就会重复提交同一
      // 文件 —— 余额充值会重复入账、计费规则/结算单会重复建数据。removeFile 会同时
      // 清空 input.value，使同一文件可被重新选择并触发 change 事件。
      removeFile()
    }
    return !hasErrors
  } catch (error: unknown) {
    Message.error(pickErrorMessage(error, '导入失败'))
    return false
  } finally {
    loading.value = false
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
.error-list {
  margin-top: 8px;
  padding-left: 16px;
  font-size: 12px;
  color: var(--red);
}
</style>
