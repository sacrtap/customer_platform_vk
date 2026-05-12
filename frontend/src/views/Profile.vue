<template>
  <div class="profile-page">
    <div class="profile-card">
      <div class="profile-header">
        <h1 class="profile-title">个人信息</h1>
      </div>

      <div v-if="loading" class="profile-loading">
        <a-spin size="large" />
      </div>

      <a-form
        v-else
        ref="formRef"
        layout="vertical"
        :model="formData"
        :rules="rules"
        @submit="handleSubmit"
      >
        <!-- 头像区域 -->
        <div class="avatar-section">
          <div class="avatar-wrapper">
            <div v-if="formData.avatar_url" class="avatar-preview">
              <img :src="formData.avatar_url" alt="头像" />
            </div>
            <div v-else class="avatar-preview avatar-default">
              {{ formData.username?.charAt(0)?.toUpperCase() || 'U' }}
            </div>
          </div>
          <div class="avatar-actions">
            <a-button type="primary" size="small" @click="showAvatarUrlInput"> 更换头像 </a-button>
            <a-button v-if="formData.avatar_url" size="small" @click="removeAvatar">
              移除
            </a-button>
          </div>
          <a-input
            v-if="avatarUrlInputVisible"
            v-model="avatarUrlInput"
            placeholder="输入头像图片 URL"
            size="small"
            style="margin-top: 8px; max-width: 300px"
            @blur="handleAvatarUrlConfirm"
            @press-enter="handleAvatarUrlConfirm"
          />
        </div>

        <!-- 表单字段 -->
        <a-form-item label="用户名" field="username">
          <a-input v-model="formData.username" disabled />
        </a-form-item>

        <a-form-item label="邮箱" field="email">
          <a-input v-model="formData.email" placeholder="请输入邮箱" />
        </a-form-item>

        <a-form-item label="手机号" field="phone">
          <a-input v-model="formData.phone" placeholder="请输入手机号" />
        </a-form-item>

        <a-form-item label="最后登录时间">
          <a-input :model-value="formatLastLogin()" disabled />
        </a-form-item>

        <!-- 操作按钮 -->
        <div class="form-actions">
          <a-button type="primary" html-type="submit" :loading="submitLoading"> 保存 </a-button>
          <a-button @click="handleCancel">取消</a-button>
        </div>
      </a-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { getProfile, updateProfile, type UserProfile } from '@/api/users'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const submitLoading = ref(false)
const formRef = ref<FormInstance>()

const formData = reactive({
  id: 0,
  username: '',
  email: '',
  phone: '',
  avatar_url: '',
  real_name: '',
  last_login_at: '',
})

const avatarUrlInputVisible = ref(false)
const avatarUrlInput = ref('')

const rules = {
  email: [{ type: 'email', message: '邮箱格式不正确' }],
  phone: [
    {
      pattern: /^\d{11}$/,
      message: '请输入 11 位手机号',
    },
  ],
}

const formatLastLogin = () => {
  if (!formData.last_login_at) return '暂无记录'
  return new Date(formData.last_login_at).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const loadProfile = async () => {
  loading.value = true
  try {
    const res = await getProfile()
    const profile: UserProfile = res.data
    formData.id = profile.id
    formData.username = profile.username
    formData.email = profile.email || ''
    formData.phone = profile.phone || ''
    formData.avatar_url = profile.avatar_url || ''
    formData.real_name = profile.real_name || ''
    formData.last_login_at = profile.last_login_at || ''
  } catch {
    Message.error('加载个人信息失败')
  } finally {
    loading.value = false
  }
}

const showAvatarUrlInput = () => {
  avatarUrlInputVisible.value = true
  avatarUrlInput.value = formData.avatar_url || ''
}

const handleAvatarUrlConfirm = () => {
  formData.avatar_url = avatarUrlInput.value
  avatarUrlInputVisible.value = false
}

const removeAvatar = () => {
  formData.avatar_url = ''
}

const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitLoading.value = true
  try {
    await updateProfile({
      email: formData.email || undefined,
      phone: formData.phone || undefined,
      avatar_url: formData.avatar_url || undefined,
      real_name: formData.real_name || undefined,
    })
    Message.success('保存成功')

    // 更新 store 中的用户信息
    userStore.setUserInfo({
      ...userStore.userInfo!,
      email: formData.email,
      phone: formData.phone,
      avatar_url: formData.avatar_url,
    })
  } catch (error) {
    Message.error((error as Error)?.message || '保存失败')
  } finally {
    submitLoading.value = false
  }
}

const handleCancel = () => {
  router.back()
}

onMounted(() => {
  loadProfile()
})
</script>

<style scoped>
.profile-page {
  max-width: 600px;
  margin: 0 auto;
}

.profile-card {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2, #eef0f3);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.profile-header {
  padding: 24px;
  border-bottom: 1px solid var(--neutral-2, #eef0f3);
}

.profile-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--neutral-10, #1d2330);
  margin: 0;
}

.profile-loading {
  padding: 60px 0;
  display: flex;
  justify-content: center;
}

.avatar-section {
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  border-bottom: 1px solid var(--neutral-2, #eef0f3);
}

.avatar-wrapper {
  width: 80px;
  height: 80px;
}

.avatar-preview {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-default {
  background: linear-gradient(135deg, #0369a1 0%, #0284c7 100%);
  color: white;
  font-weight: 600;
  font-size: 32px;
}

.avatar-actions {
  display: flex;
  gap: 8px;
}

.form-actions {
  display: flex;
  gap: 12px;
  padding: 0 24px 24px;
}
</style>
