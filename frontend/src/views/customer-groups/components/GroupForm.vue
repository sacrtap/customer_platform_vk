<template>
  <a-modal
    :visible="visible"
    title="新建群组"
    width="600px"
    :ok-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item label="群组名称" field="name" required>
        <a-input
          v-model="form.name"
          placeholder="请输入群组名称"
          maxlength="100"
          show-word-limit
        />
      </a-form-item>

      <a-form-item label="群组描述" field="description">
        <a-textarea
          v-model="form.description"
          placeholder="请输入群组描述（可选）"
          maxlength="500"
          show-word-limit
          :auto-size="{ minRows: 3, maxRows: 5 }"
        />
      </a-form-item>

      <a-form-item label="群组类型" field="group_type" required>
        <a-radio-group v-model="form.group_type">
          <a-radio value="dynamic">
            <template #icon><icon-folder /></template>
            动态群组（保存筛选条件）
          </a-radio>
          <a-radio value="static">
            <template #icon><icon-user-group /></template>
            静态群组（手动管理成员）
          </a-radio>
        </a-radio-group>
      </a-form-item>

      <a-alert
        v-if="form.group_type === 'dynamic' && defaultFilter"
        type="info"
        style="margin-top: 16px"
      >
        将保存当前筛选条件：{{ JSON.stringify(defaultFilter) }}
      </a-alert>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { IconFolder, IconUserGroup } from '@arco-design/web-vue/es/icon'
import type { FormInstance } from '@arco-design/web-vue'
import type { CreateGroupParams } from '@/types/customer-groups'

const props = defineProps<{
  visible: boolean
  defaultFilter?: Record<string, unknown> | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit', data: CreateGroupParams): void
}>()

const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  description: '',
  group_type: 'dynamic' as 'dynamic' | 'static',
})

const rules: Record<string, any> = {
  name: [
    { required: true, message: '请输入群组名称' },
    { minLength: 2, message: '群组名称至少 2 个字符' },
    { maxLength: 100, message: '群组名称不能超过 100 个字符' },
  ],
  group_type: [
    { required: true, message: '请选择群组类型' },
  ],
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      form.name = ''
      form.description = ''
      form.group_type = 'dynamic'
      formRef.value?.clearValidate()
    }
  }
)

const handleSubmit = async () => {
  const valid = await formRef.value?.validate()
  if (valid) return

  emit('submit', {
    ...form,
    filter_conditions: form.group_type === 'dynamic' ? props.defaultFilter : null,
  })
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>
