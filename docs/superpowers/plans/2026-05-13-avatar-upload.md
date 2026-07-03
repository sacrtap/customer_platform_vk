# 头像上传功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将个人信息页的头像更换功能从 URL 输入改为文件上传，支持 jpg/png 格式，后端自动压缩超 1024x1024 分辨率的图片。

**Architecture:** 新增专用头像上传接口，使用 Pillow 进行图片验证和压缩，前端使用 Arco Design 的 `<a-upload>` 组件替换现有 URL 输入框。

**Tech Stack:** Python (Sanic), Pillow, Arco Design Vue, TypeScript

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/requirements.txt` | 修改 | 添加 Pillow 依赖 |
| `backend/app/routes/users.py` | 修改 | 新增 `POST /api/v1/users/avatar` 接口 |
| `backend/tests/unit/test_avatar_upload.py` | 创建 | 头像上传单元测试 |
| `frontend/src/api/users.ts` | 修改 | 新增 `uploadAvatar` API 函数 |
| `frontend/src/views/Profile.vue` | 修改 | 替换 URL 输入为上传组件 |

---

### Task 1: 添加 Pillow 依赖

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 在 requirements.txt 中添加 Pillow 依赖**

在 `python-magic==0.4.27` 下方添加：

```
# Image Processing
Pillow==10.2.0
```

- [ ] **Step 2: 安装依赖并验证**

```bash
cd backend && source .venv/bin/activate && pip install Pillow==10.2.0
```

验证安装：
```bash
python -c "from PIL import Image; print('Pillow OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add Pillow dependency for avatar image processing"
```

---

### Task 2: 后端头像上传接口

**Files:**
- Modify: `backend/app/routes/users.py`
- Test: `backend/tests/unit/test_avatar_upload.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/tests/unit/test_avatar_upload.py`：

```python
"""头像上传接口单元测试"""

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.routes.users import upload_avatar


@pytest.fixture
def mock_request():
    """模拟请求对象"""
    request = MagicMock()
    request.ctx = MagicMock()
    request.ctx.user = {"user_id": 1}
    request.ctx.db_session = AsyncMock()
    request.ctx.db_session.commit = AsyncMock()
    request.ip = "127.0.0.1"
    return request


@pytest.fixture
def temp_uploads(tmp_path):
    """创建临时上传目录"""
    avatars_dir = tmp_path / "uploads" / "avatars"
    avatars_dir.mkdir(parents=True)
    return avatars_dir


def create_test_image(width, height, format="JPEG"):
    """创建测试图片"""
    img = Image.new("RGB", (width, height), color="red")
    buffer = io.BytesIO()
    if format == "JPEG":
        img.save(buffer, format="JPEG")
        buffer.name = "test.jpg"
    else:
        img.save(buffer, format="PNG")
        buffer.name = "test.png"
    buffer.seek(0)
    return buffer


class TestUploadAvatar:
    """头像上传测试"""

    @pytest.mark.asyncio
    async def test_upload_success_small_image(self, mock_request, temp_uploads):
        """测试成功上传小尺寸图片"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            img_buffer = create_test_image(200, 200)
            mock_file = MagicMock()
            mock_file.name = "test.jpg"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            data = response.json
            assert data["code"] == 0
            assert "avatar_url" in data["data"]
            assert data["data"]["avatar_url"].startswith("/uploads/avatars/")

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_extension(self, mock_request, temp_uploads):
        """测试拒绝非图片格式"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            mock_file = MagicMock()
            mock_file.name = "test.gif"
            mock_file.body = b"fake gif content"
            mock_file.type = "image/gif"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 400
            assert response.json["code"] == 400

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, mock_request, temp_uploads):
        """测试拒绝超大文件"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            mock_file = MagicMock()
            mock_file.name = "test.jpg"
            mock_file.body = b"x" * (3 * 1024 * 1024)  # 3MB
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 400

    @pytest.mark.asyncio
    async def test_upload_compresses_large_image(self, mock_request, temp_uploads):
        """测试大尺寸图片自动压缩"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            # 创建 2000x1500 的图片（超过 1024 限制）
            img_buffer = create_test_image(2000, 1500)
            mock_file = MagicMock()
            mock_file.name = "large.jpg"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            # 验证保存的图片尺寸被压缩
            avatar_url = response.json["data"]["avatar_url"]
            saved_path = temp_uploads.parent.parent / avatar_url.lstrip("/")
            with Image.open(saved_path) as img:
                assert img.width <= 1024
                assert img.height <= 1024

    @pytest.mark.asyncio
    async def test_upload_png_format(self, mock_request, temp_uploads):
        """测试 PNG 格式上传"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            img_buffer = create_test_image(300, 300, format="PNG")
            mock_file = MagicMock()
            mock_file.name = "test.png"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/png"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            assert response.json["data"]["avatar_url"].endswith(".png")

    @pytest.mark.asyncio
    async def test_upload_no_file(self, mock_request):
        """测试未上传文件"""
        mock_request.files = {}
        response = await upload_avatar(mock_request)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_upload_deletes_old_avatar(self, mock_request, temp_uploads):
        """测试上传新头像时删除旧头像文件"""
        # 创建旧头像文件
        old_file = temp_uploads / "1_old_avatar.jpg"
        old_file.write_bytes(b"old avatar data")

        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            # 模拟用户已有旧头像
            mock_request.ctx.db_session.execute = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=MagicMock(
                id=1,
                avatar_url="/uploads/avatars/1_old_avatar.jpg"
            ))
            mock_request.ctx.db_session.execute.return_value = mock_result

            img_buffer = create_test_image(200, 200)
            mock_file = MagicMock()
            mock_file.name = "new.jpg"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            assert not old_file.exists()  # 旧文件应被删除
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_avatar_upload.py -v
```

预期：全部失败（`upload_avatar` 函数不存在）

- [ ] **Step 3: 在 users.py 中实现头像上传接口**

在 `backend/app/routes/users.py` 文件顶部添加导入：

```python
import logging
import os
import uuid
from pathlib import Path

from PIL import Image

from ..config import settings
from ..models.users import User
```

在文件末尾（`change_password` 函数之后）添加：

```python
# 头像专用配置
AVATAR_MAX_SIZE = 2 * 1024 * 1024  # 2MB
AVATAR_MAX_DIMENSION = 1024  # 最大宽高
AVATAR_SUBDIR = "avatars"

ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_AVATAR_MIME_TYPES = {"image/jpeg", "image/png"}


@users_bp.post("/avatar")
@auth_required
async def upload_avatar(request: Request):
    """
    上传用户头像

    Request:
        multipart/form-data with field 'file'

    Response:
        {
            "code": 0,
            "data": {
                "avatar_url": "/uploads/avatars/1_uuid.jpg"
            }
        }
    """
    logger = logging.getLogger(__name__)

    # 步骤 1: 检查文件是否存在
    if not request.files or "file" not in request.files:
        return json({"code": 400, "message": "未找到上传文件"}, status=400)

    file_list = request.files["file"]
    file = file_list[0] if isinstance(file_list, list) else file_list

    # 步骤 2: 检查文件名
    if not file.name:
        return json({"code": 400, "message": "文件名不能为空"}, status=400)

    # 步骤 3: 扩展名白名单
    ext = Path(file.name).suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        return json(
            {
                "code": 400,
                "message": f"不支持的文件类型：{ext}，仅支持 .jpg/.jpeg/.png",
            },
            status=400,
        )

    # 步骤 4: 文件大小检查
    file_size = len(file.body)
    if file_size > AVATAR_MAX_SIZE:
        return json(
            {
                "code": 400,
                "message": f"文件大小超过限制 ({AVATAR_MAX_SIZE / 1024 / 1024}MB)",
            },
            status=400,
        )

    # 步骤 5: MIME 类型验证
    try:
        import magic
        detected_mime = magic.from_buffer(file.body, mime=True)
        if detected_mime not in ALLOWED_AVATAR_MIME_TYPES:
            return json(
                {"code": 400, "message": f"不允许的文件类型：{detected_mime}"},
                status=400,
            )
    except Exception as e:
        logger.error(f"MIME 类型检测失败：{str(e)}")
        return json({"code": 500, "message": "文件类型检测失败"}, status=500)

    # 步骤 6: 使用 Pillow 处理图片（验证 + 压缩）
    try:
        img = Image.open(io.BytesIO(file.body))
        img.verify()
        # 重新打开（verify 后图片已消耗）
        img = Image.open(io.BytesIO(file.body))

        # 转换为 RGB（处理 RGBA/P 模式）
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
            ext = ".jpg"  # 转换后使用 JPEG 格式

        # 等比缩放：最大边不超过 AVATAR_MAX_DIMENSION
        width, height = img.size
        if width > AVATAR_MAX_DIMENSION or height > AVATAR_MAX_DIMENSION:
            ratio = AVATAR_MAX_DIMENSION / max(width, height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)

        # 保存到内存 buffer
        output_buffer = io.BytesIO()
        if ext == ".png":
            img.save(output_buffer, format="PNG", optimize=True)
        else:
            img.save(output_buffer, format="JPEG", quality=85, optimize=True)
        processed_data = output_buffer.getvalue()

    except Exception as e:
        logger.error(f"图片处理失败：{str(e)}")
        return json({"code": 400, "message": "图片处理失败，请上传有效的图片文件"}, status=400)

    # 步骤 7: 删除旧头像文件
    current_user = get_current_user(request)
    user_id = current_user.get("user_id")

    db_session = request.ctx.db_session
    user_result = await db_session.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if user and user.avatar_url:
        old_path = Path(settings.file_storage_path) / user.avatar_url.lstrip("/")
        try:
            if old_path.exists():
                old_path.unlink()
                logger.info(f"旧头像已删除：{old_path}")
        except Exception as e:
            logger.warning(f"删除旧头像失败：{str(e)}")

    # 步骤 8: 生成文件名并保存
    avatar_dir = Path(settings.file_storage_path) / AVATAR_SUBDIR
    avatar_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = avatar_dir / stored_filename

    with open(file_path, "wb") as f:
        f.write(processed_data)

    # 步骤 9: 更新用户 avatar_url
    avatar_url = f"/uploads/{AVATAR_SUBDIR}/{stored_filename}"
    user.avatar_url = avatar_url
    await db_session.commit()

    logger.info(f"头像上传成功：用户 {user_id}, 路径 {avatar_url}")

    return json({"code": 0, "data": {"avatar_url": avatar_url}})
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_avatar_upload.py -v
```

预期：全部通过

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/users.py backend/tests/unit/test_avatar_upload.py backend/requirements.txt
git commit -m "feat(profile): add avatar upload endpoint with auto-compression"
```

---

### Task 3: 前端 API 层

**Files:**
- Modify: `frontend/src/api/users.ts`

- [ ] **Step 1: 添加 uploadAvatar 函数**

在 `frontend/src/api/users.ts` 末尾添加：

```typescript
/**
 * 上传用户头像
 */
export function uploadAvatar(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/users/avatar', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/users.ts
git commit -m "feat(profile): add uploadAvatar API function"
```

---

### Task 4: 前端 Profile.vue 改造

**Files:**
- Modify: `frontend/src/views/Profile.vue`

- [ ] **Step 1: 替换模板中的头像更换按钮**

将第 27-29 行的"更换头像"按钮：

```html
<a-button type="primary" size="small" @click="showAvatarUrlInput">
  更换头像
</a-button>
```

替换为：

```html
<a-upload
  :show-file-list="false"
  accept="image/jpeg,image/png,.jpg,.jpeg,.png"
  :custom-request="handleAvatarUpload"
>
  <a-button type="primary" size="small">
    更换头像
  </a-button>
</a-upload>
```

同时删除第 34-42 行的 URL 输入框：

```html
<!-- 删除以下代码 -->
<a-input
  v-if="avatarUrlInputVisible"
  v-model="avatarUrlInput"
  placeholder="输入头像图片 URL"
  size="small"
  class="avatar-url-input"
  @blur="handleAvatarUrlConfirm"
  @press-enter="handleAvatarUrlConfirm"
/>
```

- [ ] **Step 2: 替换 script 中的头像逻辑**

在 imports 中添加 `uploadAvatar`：

```typescript
import { getProfile, updateProfile, changePassword, uploadAvatar, type UserProfile } from '@/api/users'
```

删除以下变量和函数：
- `avatarUrlInputVisible`
- `avatarUrlInput`
- `showAvatarUrlInput`
- `handleAvatarUrlConfirm`
- `removeAvatar`（保留，但改为调用新接口或直接清空 avatar_url 字段）

添加 `handleAvatarUpload` 函数（在 `removeAvatar` 原位置）：

```typescript
const avatarUploading = ref(false)

const handleAvatarUpload = async (option: any) => {
  const { fileItem } = option
  const file = fileItem.file as File

  // 前端校验
  const allowedTypes = ['image/jpeg', 'image/png']
  if (!allowedTypes.includes(file.type)) {
    Message.error('仅支持 JPG/PNG 格式的图片')
    return
  }

  if (file.size > 2 * 1024 * 1024) {
    Message.error('图片大小不能超过 2MB')
    return
  }

  avatarUploading.value = true
  try {
    const res = await uploadAvatar(file)
    const newAvatarUrl = res.data.avatar_url
    formData.avatar_url = newAvatarUrl

    // 同步更新 store
    userStore.setUserInfo({
      ...userStore.userInfo!,
      avatar_url: newAvatarUrl,
    })

    Message.success('头像上传成功')
  } catch (error) {
    Message.error((error as Error)?.message || '头像上传失败')
  } finally {
    avatarUploading.value = false
  }
}
```

更新 `removeAvatar` 函数，改为通过 `updateProfile` 清空头像：

```typescript
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
```

- [ ] **Step 3: 更新按钮 loading 状态**

将上传按钮改为带 loading 状态：

```html
<a-upload
  :show-file-list="false"
  accept="image/jpeg,image/png,.jpg,.jpeg,.png"
  :custom-request="handleAvatarUpload"
>
  <a-button type="primary" size="small" :loading="avatarUploading">
    更换头像
  </a-button>
</a-upload>
```

- [ ] **Step 4: 删除不再使用的 CSS 类**

删除 `.avatar-url-input` 样式（第 392-394 行）：

```css
/* 删除 */
.avatar-url-input {
  width: 100%;
}
```

- [ ] **Step 5: 前端构建验证**

```bash
cd frontend && npm run type-check && npm run lint
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/Profile.vue frontend/src/api/users.ts
git commit -m "feat(profile): replace avatar URL input with file upload component"
```

---

### Task 5: 集成测试与验证

**Files:**
- Modify: `backend/tests/integration/test_users_api.py`

- [ ] **Step 1: 添加集成测试**

在 `backend/tests/integration/test_users_api.py` 末尾添加：

```python
@pytest.mark.asyncio
async def test_upload_avatar_success(test_client, test_user):
    """测试头像上传成功"""
    import io
    from PIL import Image

    # 创建测试图片
    img = Image.new("RGB", (200, 200), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)

    # 登录
    _, login_resp = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    token = login_resp.json["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 上传头像
    _, response = await test_client.post(
        "/api/v1/users/avatar",
        headers=headers,
        files={"file": ("test.jpg", buffer, "image/jpeg")},
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["avatar_url"].startswith("/uploads/avatars/")
```

- [ ] **Step 2: 运行完整测试套件**

```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_avatar_upload.py tests/integration/test_users_api.py -v
```

- [ ] **Step 3: 运行代码质量检查**

```bash
cd backend && source .venv/bin/activate && ruff check app/ tests/ && ruff format app/ tests/ --check
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_users_api.py
git commit -m "test(profile): add avatar upload integration test"
```
