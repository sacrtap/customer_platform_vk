<template>
  <a-modal
    :visible="visible"
    title="新建群组"
    width="600px"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="form" layout="vertical">
      <a-form-item label="群组名称" required>
        <a-input
          v-model="form.name"
          placeholder="请输入群组名称"
          maxlength="100"
          show-word-limit
        />
      </a-form-item>

      <a-form-item label="群组描述">
        <a-textarea
          v-model="form.description"
          placeholder="请输入群组描述（可选）"
          maxlength="500"
          show-word-limit
          :auto-size="{ minRows: 3, maxRows: 5 }"
        />
      </a-form-item>

      <a-form-item label="群组类型" required>
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

const props = defineProps<{
  visible: boolean
  defaultFilter?: any
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit', data: any): void
}>()

const form = reactive({
  name: '',
  description: '',
  group_type: 'dynamic' as 'dynamic' | 'static',
})

watch(
  () => props.visible,
  (val) => {
    if (val) {
      form.name = ''
      form.description = ''
      form.group_type = 'dynamic'
    }
  }
)

const handleSubmit = () => {
  if (!form.name) {
    return
  }

  emit('submit', {
    ...form,
    filter_conditions: form.group_type === 'dynamic' ? props.defaultFilter : null,
  })
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>
