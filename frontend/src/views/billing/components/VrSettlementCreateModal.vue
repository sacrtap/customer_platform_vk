<template>
  <a-modal
    v-model:visible="isVisible"
    title="创建VR结算单"
    width="640px"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="form" layout="vertical">
      <!-- 创建方式选择：自动创建待开发（禁用） -->
      <a-form-item label="创建方式" required>
        <a-radio-group v-model="form.create_mode">
          <a-radio value="manual">手动创建</a-radio>
          <a-radio value="auto" disabled>
            自动创建
            <a-tag size="small" color="gray" style="margin-left: 4px">待开发</a-tag>
          </a-radio>
        </a-radio-group>
      </a-form-item>

      <!-- 手动创建表单（自动模式 disabled 不可选中，恒展示手动区） -->
      <template v-if="form.create_mode === 'manual'">
        <a-form-item label="客户" required>
          <CustomerAutoComplete
            :key="customerPickerKey"
            v-model="form.customer_id"
            placeholder="请选择客户"
            width="100%"
          />
        </a-form-item>
        <a-form-item label="结算周期" required>
          <a-range-picker v-model="periodRange" style="width: 100%" @change="handlePeriodChange" />
        </a-form-item>
        <a-form-item label="结算金额" required>
          <a-input-number
            v-model="form.total_amount"
            placeholder="请输入结算金额"
            :precision="2"
            :min="0.01"
            style="width: 100%"
          >
            <template #prefix>¥</template>
          </a-input-number>
        </a-form-item>
        <a-form-item label="结算明细文件" required>
          <a-upload
            v-model:file-list="fileList"
            :limit="1"
            :auto-upload="false"
            accept=".xlsx,.xls"
            @before-upload="handleBeforeUpload"
            @change="handleFileChange"
          >
            <template #upload-button>
              <a-button>
                <template #icon>+</template>
                选择文件
              </a-button>
            </template>
          </a-upload>
          <div class="form-tip">明细文件仅存档与下载，不解析内容；结算金额请手动填写</div>
        </a-form-item>
        <a-form-item label="备注说明">
          <a-textarea
            v-model="form.remark"
            placeholder="请输入备注说明（选填）"
            :max-length="500"
            :auto-size="{ minRows: 3, maxRows: 6 }"
            show-word-limit
            allow-clear
          />
        </a-form-item>
      </template>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
import { createVrSettlement, uploadDiscountAttachment } from '@/api/vrSettlement'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const formRef = ref<FormInstance>()
const loading = ref(false)

// 明细文件大小上限，与后端 settings.max_file_size（20MB，见 backend/app/config.py）口径一致：
// 前端先拦掉超大文件，避免走完整个上传请求才收到后端超限错误（同 ImportModal 处理）
const MAX_DETAIL_FILE_SIZE = 20 * 1024 * 1024

const form = reactive({
  create_mode: 'manual' as 'manual' | 'auto',
  customer_id: undefined as number | undefined,
  period_start: '',
  period_end: '',
  total_amount: undefined as number | undefined,
  remark: '',
})

const periodRange = ref<string[]>([])

// a-upload 文件列表（受控）
const fileList = ref<{ file?: File; [key: string]: unknown }[]>([])

// 弹窗每次打开时递增：CustomerAutoComplete 的显示文本由组件内部维护，
// 需重建组件才能清空输入框（与 GenerateInvoiceModal 同一处理）
const customerPickerKey = ref(0)

// 打开弹窗时重置表单（保留无状态）
watch(
  () => props.visible,
  (val) => {
    if (val) {
      form.create_mode = 'manual'
      form.customer_id = undefined
      form.period_start = ''
      form.period_end = ''
      form.total_amount = undefined
      form.remark = ''
      periodRange.value = []
      fileList.value = []
      customerPickerKey.value += 1
      nextTick(() => {
        formRef.value?.clearValidate()
      })
    }
  }
)

const handlePeriodChange = (dates: string[]) => {
  if (dates.length === 2) {
    form.period_start = dates[0]
    form.period_end = dates[1]
  } else {
    form.period_start = ''
    form.period_end = ''
  }
}

const handleFileChange = (list: { file?: File; [key: string]: unknown }[]) => {
  // 必须无条件同步：移除文件后 Arco 回传空数组，若守卫 length>0 则条目残留（移除无效）
  fileList.value = list || []
}

// 选中后、入列前拦截：返回 false 时 Arco 不会把文件加进 file-list，
// 因此也不会触发 @change（upload.js uploadFiles → onBeforeUpload → initUpload）
const handleBeforeUpload = (file: File): boolean => {
  if (file.size > MAX_DETAIL_FILE_SIZE) {
    Message.error('文件大小不能超过 20MB')
    return false
  }
  return true
}

const handleCancel = () => {
  emit('update:visible', false)
}

const handleSubmit = async () => {
  // 表单校验（客户/周期/金额/文件必填）
  if (!form.customer_id) {
    Message.error('请选择客户')
    return false
  }
  if (!form.period_start || !form.period_end) {
    Message.error('请选择结算周期')
    return false
  }
  if (form.total_amount === undefined || form.total_amount === null || form.total_amount <= 0) {
    Message.error('结算金额必须大于 0')
    return false
  }
  if (fileList.value.length === 0 || !fileList.value[0]?.file) {
    Message.error('请上传结算明细文件')
    return false
  }

  loading.value = true
  try {
    // 先上传明细文件，拿回文件路径
    let detailFilePath: string
    try {
      const uploadRes = await uploadDiscountAttachment(fileList.value[0].file as File)
      detailFilePath = (uploadRes.data as { file_path?: string })?.file_path || ''
    } catch (error) {
      // 展示后端真实错误（无权限/大小超限/类型不符），避免吞成统一文案后无从排查
      handleError(error, '文件上传失败')
      return false
    }
    if (!detailFilePath) {
      Message.error('文件上传失败')
      return false
    }

    await createVrSettlement({
      customer_id: form.customer_id,
      period_start: form.period_start,
      period_end: form.period_end,
      total_amount: form.total_amount,
      detail_file_path: detailFilePath,
      detail_file_name: (fileList.value[0] as { name?: string }).name || '',
      remark: form.remark.trim() || undefined,
    })
    Message.success('创建成功')
    emit('success')
    return true
  } catch (error) {
    handleError(error)
    return false
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.form-tip {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

/* 上传区收窄，与右侧提示文字保留合理间距 */
:deep(.arco-upload-wrapper) {
  width: 260px;
  max-width: 100%;
  flex-shrink: 0;
  margin-right: 12px;
}

/* auto-upload=false 时进度圈与 ▶ 开始按钮（play 样式）无意义，隐藏 */
:deep(.arco-upload-progress) {
  display: none;
}

/* 文件条目做成输入框外观：背景/边框对齐表单 a-input */
:deep(.arco-upload-list-item) {
  height: 32px;
  margin: 0;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background-color: var(--color-fill-2);
  align-items: center;
  transition: border-color 0.2s;
}
:deep(.arco-upload-list-item:hover) {
  border-color: var(--primary);
}
/* 去掉 Arco content 内置的文件名底色与内边距（框中框灰条） */
:deep(.arco-upload-list-item-content) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  padding: 0;
  background-color: transparent;
}
:deep(.arco-upload-list-item-name) {
  flex: 1;
  min-width: 0;
  margin-right: 4px;
}
:deep(.arco-upload-list-item-name-text) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: default;
}
/* 删除按钮红色（text 列表类型 class 为 arco-upload-icon-remove） */
:deep(.arco-upload-icon-remove) {
  color: var(--red, #ef4444);
  font-size: 14px;
}
</style>
