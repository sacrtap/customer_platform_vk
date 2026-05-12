<template>
  <div class="profile-page">
    <div class="profile-card">
      <!-- 页面标题 -->
      <div class="profile-header">
        <h1 class="profile-title">个人信息</h1>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="profile-loading">
        <a-spin size="large" />
      </div>

      <!-- 主内容区：左右分栏 -->
      <div v-else class="profile-content">
        <!-- 左侧：头像区域 -->
        <div class="avatar-sidebar">
          <div class="avatar-wrapper">
            <div v-if="formData.avatar_url" class="avatar-preview">
              <img :src="formData.avatar_url" alt="头像" />
            </div>
            <div v-else class="avatar-preview avatar-default">
              {{ formData.username?.charAt(0)?.toUpperCase() || 'U' }}
            </div>
          </div>
          <div class="avatar-actions">
          <a-upload
            :show-file-list="false"
            accept="image/jpeg,image/png,.jpg,.jpeg,.png"
            :custom-request="handleAvatarUpload"
          >
            <a-button type="primary" size="small" :loading="avatarUploading">
              更换头像
            </a-button>
          </a-upload>
            <a-button v-if="formData.avatar_url" size="small" @click="removeAvatar">
              移除
            </a-button>
          </div>
        </div>

        <!-- 右侧：表单区域 -->
        <div class="form-section">
          <a-form
            ref="formRef"
            layout="vertical"
            :model="formData"
            :rules="rules"
            @submit="handleSubmit"
          >
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
              <a-button type="primary" html-type="submit" :loading="submitLoading">
                保存
              </a-button>
              <a-button @click="handleCancel">取消</a-button>
            </div>
          </a-form>
        </div>
      </div>
    </div>

    <!-- 修改密码对话框（保留原有功能） -->
    <a-modal
      v-model:visible="changePasswordVisible"
      title="修改密码"
      :mask-closable="false"
      @ok="handleChangePassword"
      @cancel="changePasswordVisible = false"
    >
      <a-form ref="changePasswordFormRef" :model="changePasswordForm" layout="vertical">
        <a-form-item
          label="当前密码"
          field="current_password"
          :rules="[{ required: true, message: '请输入当前密码' }]"
        >
          <a-input-password
            v-model="changePasswordForm.current_password"
            placeholder="请输入当前密码"
            size="large"
          />
        </a-form-item>
        <a-form-item
          label="新密码"
          field="new_password"
          :rules="[
            { required: true, message: '请输入新密码' },
            { minLength: 6, message: '密码长度不能少于 6 位' },
          ]"
        >
          <a-input-password
            v-model="changePasswordForm.new_password"
            placeholder="请输入新密码（至少 6 位）"
            size="large"
          />
        </a-form-item>
        <a-form-item
          label="确认新密码"
          field="confirm_password"
          :rules="[
            { required: true, message: '请再次输入新密码' },
            { validator: validateConfirmPassword, message: '两次输入的密码不一致' },
          ]"
        >
          <a-input-password
            v-model="changePasswordForm.confirm_password"
            placeholder="请再次输入新密码"
            size="large"
          />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-button @click="changePasswordVisible = false">取消</a-button>
        <a-button type="primary" :loading="changePasswordLoading" @click="handleChangePassword">
          确认修改
        </a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import type { RequestOption } from '@arco-design/web-vue/es/upload/interfaces'
import { getProfile, updateProfile, changePassword, uploadAvatar, type UserProfile } from '@/api/users'
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

// 修改密码相关
const changePasswordVisible = ref(false)
const changePasswordFormRef = ref<FormInstance>()
const changePasswordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})
const changePasswordLoading = ref(false)

const validateConfirmPassword = (_value: string, callback: (error?: string) => void) => {
  if (changePasswordForm.confirm_password !== changePasswordForm.new_password) {
    callback('两次输入的密码不一致')
  } else {
    callback()
  }
}

const handleChangePassword = async () => {
  if (!changePasswordFormRef.value) return
  try {
    await changePasswordFormRef.value.validate()
  } catch {
    return
  }
  changePasswordLoading.value = true
  try {
    await changePassword({
      current_password: changePasswordForm.current_password,
      new_password: changePasswordForm.new_password,
    })
    Message.success('密码修改成功')
    changePasswordVisible.value = false
  } catch (error) {
    Message.error((error as Error)?.message || '密码修改失败')
  } finally {
    changePasswordLoading.value = false
  }
}

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

const avatarUploading = ref(false)

const handleAvatarUpload = (option: RequestOption) => {
  const { fileItem, onSuccess, onError } = option
  const file = fileItem.file as File

  // 前端校验
  const allowedTypes = ['image/jpeg', 'image/png']
  if (!allowedTypes.includes(file.type)) {
    Message.error('仅支持 JPG/PNG 格式的图片')
    onError(new Error('不支持的文件格式'))
    return
  }

  if (file.size > 2 * 1024 * 1024) {
    Message.error('图片大小不能超过 2MB')
    onError(new Error('文件大小超过限制'))
    return
  }

  avatarUploading.value = true

  uploadAvatar(file)
    .then((res) => {
      const newAvatarUrl = res.data.avatar_url
      formData.avatar_url = newAvatarUrl

      // 同步更新 store
      userStore.setUserInfo({
        ...userStore.userInfo!,
        avatar_url: newAvatarUrl,
      })

      Message.success('头像上传成功')
      onSuccess(res)
    })
    .catch((error) => {
      Message.error((error as Error)?.message || '头像上传失败')
      onError(error)
    })
    .finally(() => {
      avatarUploading.value = false
    })

  return {
    abort() {
      // 当前实现不支持取消
    },
  }
}

const removeAvatar = async () => {
  try {
    await updateProfile({ avatar_url: '' })
    formData.avatar_url = ''
    userStore.setUserInfo({
      ...userStore.userInfo!,
      avatar_url: '',
    })
    Message.success('头像已移除')
  } catch (error) {
    Message.error('移除头像失败')
  }
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
  max-width: 900px;
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
  padding: 24px 32px;
  border-bottom: 1px solid var(--neutral-2, #eef0f3);
}

.profile-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--neutral-10, #1d2330);
  margin: 0;
}

.profile-loading {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

/* 主内容区：左右分栏 */
.profile-content {
  display: flex;
  min-height: 400px;
}

/* 左侧：头像侧边栏 */
.avatar-sidebar {
  width: 240px;
  flex-shrink: 0;
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  border-right: 1px solid var(--neutral-2, #eef0f3);
  background: var(--neutral-1, #f7f8fa);
}

.avatar-wrapper {
  width: 100px;
  height: 100px;
}

.avatar-preview {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
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
  font-size: 40px;
}

.avatar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

/* 右侧：表单区域 */
.form-section {
  flex: 1;
  padding: 32px;
}

:deep(.arco-form-item) {
  margin-bottom: 24px;
}

:deep(.arco-form-item:last-child) {
  margin-bottom: 0;
}

.form-actions {
  display: flex;
  gap: 12px;
  padding-top: 8px;
}

/* 响应式：小屏幕下改为上下布局 */
@media (max-width: 768px) {
  .profile-page {
    max-width: 100%;
  }

  .profile-content {
    flex-direction: column;
  }

  .avatar-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--neutral-2, #eef0f3);
    padding: 24px;
  }

  .form-section {
    padding: 24px;
  }
}
</style>
