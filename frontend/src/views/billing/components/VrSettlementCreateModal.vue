<template>
  <a-modal
    v-model:visible="isVisible"
    title="创建VR结算单"
    width="640px"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form layout="vertical">
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

const form = reactive({
  create_mode: 'manual' as 'manual' | 'auto',
  customer_id: undefined as number | undefined,
  period_start: '',
  period_end: '',
  total_amount: undefined as number | undefined,
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
  if (list && list.length > 0) {
    fileList.value = list
  }
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
    } catch {
      Message.error('文件上传失败')
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
</style>
