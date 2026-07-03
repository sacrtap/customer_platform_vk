# 头像上传功能设计

**日期**: 2026-05-13
**状态**: 已确认
**范围**: 个人信息页头像更换功能（URL 输入 → 文件上传）

---

## 背景

当前个人信息页（`Profile.vue`）的头像更换功能通过 URL 输入框实现，用户需手动输入图片地址。改为文件上传方式，提升用户体验。

---

## 后端设计

### 新增接口 `POST /api/v1/users/avatar`

**认证**: `@auth_required`

**请求**: `multipart/form-data`，字段名 `file`

**验证规则**:
- 格式：仅 `.jpg`、`.jpeg`、`.png`
- 文件大小：最大 2MB
- MIME 类型：`image/jpeg`、`image/png`（python-magic 验证）

**处理流程**:
1. 验证文件存在、非空
2. 扩展名白名单检查
3. 文件大小检查（2MB）
4. MIME 类型验证
5. 使用 Pillow 打开图片，宽高任一超过 1024 时等比缩放到最大边 1024
6. 生成随机文件名：`{user_id}_{uuid}.{ext}`，存储到 `uploads/avatars/` 目录
7. 查询当前用户的旧 `avatar_url`，若存在且为本地上传文件则删除旧文件
8. 更新用户 `avatar_url` 为 `/uploads/avatars/{filename}`
9. 返回 `{ "code": 0, "data": { "avatar_url": "/uploads/avatars/..." } }`

**新增依赖**: Pillow（图片处理库）

---

## 前端设计

### Profile.vue 改动

**移除**:
- `avatarUrlInputVisible`、`avatarUrlInput` 相关状态和逻辑
- URL 输入框组件

**新增**:
- `<a-upload>` 组件，配置：
  - `accept="image/jpeg,image/png,.jpg,.jpeg,.png"`
  - `:show-file-list="false"`
  - `:custom-request="handleAvatarUpload"`
  - 按钮文案："更换头像"

**上传流程**:
1. 用户选择图片 → 触发 `handleAvatarUpload`
2. 前端校验：文件大小 ≤ 2MB，格式 jpg/png
3. 调用 `POST /api/v1/users/avatar`，FormData 上传
4. 上传中显示 loading 状态
5. 成功：更新 `formData.avatar_url`，刷新预览，提示成功
6. 失败：显示具体错误信息

### API 层

`frontend/src/api/users.ts` 新增 `uploadAvatar(file: File)` 函数。

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/routes/users.py` | 新增 | 头像上传接口 |
| `backend/requirements.txt` | 新增 | 添加 Pillow 依赖 |
| `frontend/src/api/users.ts` | 新增 | uploadAvatar 函数 |
| `frontend/src/views/Profile.vue` | 修改 | 替换 URL 输入为上传组件 |
