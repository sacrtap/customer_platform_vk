<template>
  <a-modal
    v-model:visible="isVisible"
    title="批量下载明细文件"
    width="520px"
    :mask-closable="false"
    :footer="false"
    @cancel="emit('update:visible', false)"
  >
    <div class="batch-download-content">
      <!-- loading：获取元数据 -->
      <div v-if="phase === 'loading'" class="state-block">
        <a-spin />
        <p class="state-text">正在获取下载信息…</p>
      </div>

      <!-- ready：统计与跳过提示 -->
      <template v-else-if="phase === 'ready'">
        <a-alert type="info">
          共 {{ totalCount }} 项 · 可下载 {{ completedList.length }} 项
        </a-alert>
        <a-alert v-if="skippedCount > 0" type="warning" class="skip-alert">
          {{ skippedCount }} 个明细文件未生成完成，将跳过
        </a-alert>
        <div class="modal-actions">
          <a-button :disabled="completedList.length === 0" type="primary" @click="startDownload">
            开始下载
          </a-button>
          <a-button @click="emit('update:visible', false)">取消</a-button>
        </div>
      </template>

      <!-- downloading：进度 -->
      <template v-else-if="phase === 'downloading'">
        <div class="progress-stats">
          第 {{ current.index }}/{{ completedList.length }} 个 · 成功 {{ successCount }} · 失败
          {{ failedList.length }} · 跳过 {{ skippedCount }}
        </div>
        <div v-if="current.fileName" class="current-file">{{ current.fileName }}</div>
        <a-progress
          :percent="progressPercent"
          :status="cancelled ? 'danger' : 'normal'"
          :show-text="true"
        />
        <div class="modal-actions">
          <a-button status="danger" @click="cancelDownload">取消下载</a-button>
        </div>
      </template>

      <!-- done：汇总 -->
      <template v-else>
        <a-alert :type="failedList.length > 0 ? 'warning' : 'success'">
          下载完成 · 成功 {{ successCount }} · 失败 {{ failedList.length }} · 跳过
          {{ skippedCount }}
          <span v-if="cancelled" class="cancelled-tip">（已取消）</span>
        </a-alert>
        <ul v-if="failedList.length" class="failed-list">
          <li v-for="f in failedList" :key="f.id">{{ f.invoice_no }}：{{ f.reason }}</li>
        </ul>
        <div class="modal-actions">
          <a-button type="primary" @click="emit('update:visible', false)">关闭</a-button>
        </div>
      </template>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { downloadInvoiceDetail, getBatchDownloadDetailMeta } from '@/api/billing'

interface BatchDownloadMetaItem {
  id: number
  invoice_no: string
  customer_id: number
  customer_name: string | null
  detail_file_status: string | null
}

interface FailedItem {
  id: number
  invoice_no: string
  reason: string
}

const props = defineProps<{
  visible: boolean
  ids: number[]
}>()
const emit = defineEmits<{ 'update:visible': [value: boolean] }>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

type Phase = 'loading' | 'ready' | 'downloading' | 'done'
const phase = ref<Phase>('loading')
const completedList = ref<BatchDownloadMetaItem[]>([])
const skippedCount = ref(0)
const totalCount = computed(() => completedList.value.length + skippedCount.value)
const successCount = ref(0)
const failedList = ref<FailedItem[]>([])
const cancelled = ref(false)
const current = reactive<{ index: number; fileName: string }>({ index: 0, fileName: '' })

const progressPercent = computed(() =>
  completedList.value.length === 0
    ? 0
    : Math.round((current.index / completedList.value.length) * 100) / 100
)

/** 剔除 Windows 非法字符与控制字符，trim 首尾空白与点；空串回退 unknown */
function sanitizeFilename(s: string): string {
  return (
    (s || '')
      // eslint-disable-next-line no-control-regex -- 文件名需剔除控制字符
      .replace(/[\\/:*?"<>|\x00-\x1f]/g, '')
      .replace(/^[\s.]+|[\s.]+$/g, '') || 'unknown'
  )
}

function buildFileName(item: BatchDownloadMetaItem): string {
  const namePart = item.customer_name
    ? sanitizeFilename(item.customer_name)
    : `#${item.customer_id}`
  return `${namePart}-${item.invoice_no}.xlsx`
}

/** 从任意 reject 值提取可展示文案（axios 拦截器 reject 为普通对象，非 Error 实例） */
function pickErrorMessage(error: unknown, fallback: string): string {
  const msg = (error as { message?: unknown } | null | undefined)?.message
  return typeof msg === 'string' && msg ? msg : fallback
}

watch(
  () => props.visible,
  async (visible) => {
    if (!visible) return
    phase.value = 'loading'
    completedList.value = []
    skippedCount.value = 0
    successCount.value = 0
    failedList.value = []
    cancelled.value = false
    current.index = 0
    current.fileName = ''
    try {
      const res = await getBatchDownloadDetailMeta(props.ids)
      const list: BatchDownloadMetaItem[] = res.data?.list || []
      completedList.value = list.filter((d) => d.detail_file_status === 'completed')
      skippedCount.value = list.length - completedList.value.length
      phase.value = 'ready'
    } catch (error) {
      Message.error(pickErrorMessage(error, '获取下载信息失败'))
      emit('update:visible', false)
    }
  }
)

// File System Access API 类型：TS DOM lib 默认未包含，本地最小声明
interface FileSystemDirectoryHandle {
  getFileHandle(name: string, options?: { create?: boolean }): Promise<FileSystemFileHandle>
}
interface FileSystemFileHandle {
  createWritable(): Promise<{
    write(data: Blob): Promise<void>
    close(): Promise<void>
  }>
}

const startDownload = async () => {
  if (completedList.value.length === 0) return

  // Chrome/Edge 支持选目录写入；Safari/Firefox 不支持，降级为浏览器逐个下载
  let dirHandle: FileSystemDirectoryHandle | null = null
  const picker = (
    window as unknown as {
      showDirectoryPicker?: () => Promise<FileSystemDirectoryHandle>
    }
  ).showDirectoryPicker
  if (typeof picker === 'function') {
    try {
      dirHandle = await picker.call(window)
    } catch (e) {
      // 用户取消选目录：回到 ready 阶段重新开始
      if ((e as Error)?.name === 'AbortError') return
      Message.error('无法访问所选目录，将使用浏览器逐个下载')
      dirHandle = null
    }
  }

  phase.value = 'downloading'
  successCount.value = 0
  failedList.value = []
  cancelled.value = false
  current.index = 0
  current.fileName = ''

  // 串行下载：避免浏览器多文件下载拦截与目录写入竞态；每项后检查取消标志
  for (let i = 0; i < completedList.value.length; i++) {
    if (cancelled.value) break
    const item = completedList.value[i]
    current.index = i + 1
    current.fileName = buildFileName(item)
    try {
      const res = await downloadInvoiceDetail(item.id)
      const blob = new Blob([res.data])
      if (dirHandle) {
        const fh = await dirHandle.getFileHandle(current.fileName, { create: true })
        const writable = await fh.createWritable()
        await writable.write(blob)
        await writable.close()
      } else {
        // 降级：浏览器逐个下载。先挂载再 click（Firefox 兼容），延迟回收 object URL
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = current.fileName
        document.body.appendChild(link)
        link.click()
        window.setTimeout(() => {
          window.URL.revokeObjectURL(url)
          link.remove()
        }, 1000)
      }
      successCount.value++
    } catch (error) {
      failedList.value.push({
        id: item.id,
        invoice_no: item.invoice_no,
        reason: pickErrorMessage(error, '下载失败'),
      })
    }
  }
  phase.value = 'done'
}

const cancelDownload = () => {
  cancelled.value = true
}
</script>

<style scoped>
.batch-download-content {
  padding: 4px 0;
}
.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px 0;
}
.state-text {
  font-size: 13px;
  color: var(--muted);
}
.skip-alert {
  margin-top: 12px;
}
.progress-stats {
  font-size: 14px;
  margin-bottom: 8px;
}
.current-file {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 8px;
  word-break: break-all;
}
.failed-list {
  margin: 12px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--error);
}
.cancelled-tip {
  margin-left: 4px;
  color: var(--muted);
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}
</style>
