# "我的"用户中心功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在系统顶部 Header 增加"我的"用户入口，包含圆形头像、下拉菜单（个人信息、修改密码、退出登录），新增个人信息页面和密码修改功能。

**Architecture:** 前端使用 Arco Design 的 a-popover 实现下拉菜单，新增 /profile 路由页面；后端在 users 表新增 email/phone/avatar_url/last_login_at 字段，新增 profile 相关 API 端点。

**Tech Stack:** Vue 3 + TypeScript + Arco Design (前端), Sanic + SQLAlchemy + PostgreSQL (后端), Alembic (迁移)

---

## 文件结构映射

| 文件 | 操作 | 职责 |
| ---- | ---- | ---- |
| `backend/app/models/users.py` | 修改 | User 模型新增 phone, avatar_url, last_login_at 字段 |
| `backend/app/services/users.py` | 修改 | UserService 新增 get_profile, update_profile, change_password 方法 |
| `backend/app/routes/users.py` | 修改 | 新增 /profile, /password 路由 |
| `backend/alembic/versions/xxx_add_profile_fields.py` | 新增 | 数据库迁移脚本 |
| `frontend/src/stores/user.ts` | 修改 | UserInfo 接口扩展 |
| `frontend/src/api/users.ts` | 修改 | 新增 profile 相关 API 调用 |
| `frontend/src/router/index.ts` | 修改 | 新增 /profile 路由 |
| `frontend/src/views/Dashboard.vue` | 修改 | Header 右侧布局重构，新增用户头像和下拉菜单 |
| `frontend/src/views/Profile.vue` | 新增 | 个人信息页面 |

---

### Task 1: 后端 — 数据库迁移（新增 profile 字段）

**Files:**
- Create: `backend/alembic/versions/xxx_add_profile_fields.py`

- [ ] **Step 1: 创建 Alembic 迁移脚本**

```python
"""add profile fields to users table

Revision ID: xxx
Revises: ce46b7a9d7bc
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = 'xxx'
down_revision = 'ce46b7a9d7bc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'phone')
```

> **注意**: `email` 字段已存在于 users 表，无需迁移。`last_login_at` 需要在登录时更新（后续任务处理）。

- [ ] **Step 2: 运行迁移验证**

```bash
cd backend && source .venv/bin/activate
alembic upgrade head
```

Expected: 迁移成功，users 表新增 phone, avatar_url, last_login_at 字段

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/xxx_add_profile_fields.py
git commit -m "feat(profile): add phone, avatar_url, last_login_at fields to users table"
```

---

### Task 2: 后端 — User 模型更新

**Files:**
- Modify: `backend/app/models/users.py`

- [ ] **Step 1: 修改 User 模型，新增字段**

在 `backend/app/models/users.py` 的 User 类中，在 `is_system` 字段后新增：

```python
class User(BaseModel):
    """用户表"""

    __tablename__ = "users"

    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100))
    real_name = Column(String(50))
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    phone = Column(String(20))  # 新增
    avatar_url = Column(String(500))  # 新增
    last_login_at = Column(DateTime)  # 新增

    # 关联
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    created_tags = relationship("Tag", back_populates="creator")

    def __repr__(self):
        return f"<User {self.username}>"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/users.py
git commit -m "feat(profile): add phone, avatar_url, last_login_at columns to User model"
```

---

### Task 3: 后端 — UserService 新增 profile 方法

**Files:**
- Modify: `backend/app/services/users.py`

- [ ] **Step 1: 在 UserService 类中新增三个方法**

在 `backend/app/services/users.py` 文件末尾（`get_user_roles` 方法后）新增：

```python
    async def get_profile(self, user_id: int) -> Optional[dict]:
        """获取用户个人信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "real_name": user.real_name,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "roles": [r.name for r in user.roles],
        }

    async def update_profile(
        self,
        user_id: int,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        avatar_url: Optional[str] = None,
        real_name: Optional[str] = None,
    ) -> Optional[dict]:
        """更新用户个人信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if real_name is not None:
            user.real_name = real_name

        await self.session.flush()
        await self.session.refresh(user)

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "real_name": user.real_name,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "roles": [r.name for r in user.roles],
        }

    async def change_password(
        self, user_id: int, current_password: str, new_password: str
    ) -> tuple[bool, str]:
        """修改密码

        Returns:
            (success, message)
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"

        # 验证当前密码
        if not self.verify_password(current_password, user.password_hash):
            return False, "当前密码不正确"

        # 密码强度检查
        if len(new_password) < 6:
            return False, "密码长度不能少于 6 位"

        user.password_hash = bcrypt.hashpw(
            new_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        await self.session.flush()
        return True, "密码修改成功"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/users.py
git commit -m "feat(profile): add get_profile, update_profile, change_password methods to UserService"
```

---

### Task 4: 后端 — 新增 profile 和 password 路由

**Files:**
- Modify: `backend/app/routes/users.py`

- [ ] **Step 1: 在 users.py 文件末尾新增三个路由**

```python
@users_bp.get("/profile")
@auth_required
async def get_profile(request: Request):
    """获取当前登录用户的个人信息"""
    current_user = get_current_user(request)
    if not current_user:
        return json({"code": 40101, "message": "未登录"}, status=401)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    profile = await service.get_profile(current_user["user_id"])
    if not profile:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json({"code": 0, "message": "success", "data": profile})


@users_bp.put("/profile")
@auth_required
async def update_profile(request: Request):
    """更新当前登录用户的个人信息"""
    current_user = get_current_user(request)
    if not current_user:
        return json({"code": 40101, "message": "未登录"}, status=401)

    data = request.json
    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    # 邮箱格式验证
    email = data.get("email")
    if email and "@" not in email:
        return json({"code": 40001, "message": "邮箱格式不正确"}, status=400)

    # 手机号格式验证
    phone = data.get("phone")
    if phone and not phone.isdigit():
        return json({"code": 40002, "message": "手机号格式不正确"}, status=400)

    profile = await service.update_profile(
        current_user["user_id"],
        email=email,
        phone=phone,
        avatar_url=data.get("avatar_url"),
        real_name=data.get("real_name"),
    )
    if not profile:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json({"code": 0, "message": "更新成功", "data": profile})


@users_bp.put("/password")
@auth_required
async def change_password(request: Request):
    """修改当前登录用户的密码"""
    current_user = get_current_user(request)
    if not current_user:
        return json({"code": 40101, "message": "未登录"}, status=401)

    data = request.json
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return json(
            {"code": 40001, "message": "当前密码和新密码不能为空"}, status=400
        )

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    success, message = await service.change_password(
        current_user["user_id"], current_password, new_password
    )

    if not success:
        status_code = 400 if "密码" in message else 404
        return json({"code": 40002, "message": message}, status=status_code)

    # 记录敏感操作审计日志
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id"),
        action="change_password",
        module="users",
        record_id=current_user["user_id"],
        record_type="user",
        operation_type="sensitive",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/users.py
git commit -m "feat(profile): add GET/PUT /profile and PUT /password routes"
```

---

### Task 5: 后端 — 登录时更新 last_login_at

**Files:**
- Modify: `backend/app/routes/auth.py`

- [ ] **Step 1: 读取 auth.py 找到登录逻辑**

先读取 `backend/app/routes/auth.py` 找到登录成功后的代码位置，在设置 token 后、返回响应前，更新 `last_login_at`：

```python
# 在登录成功后，返回响应前新增：
user.last_login_at = func.now()
await db_session.commit()
```

具体插入位置需要根据 auth.py 的实际代码确定。找到登录验证成功、准备生成 token 的位置，在返回 json 响应前插入上述代码。

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/auth.py
git commit -m "feat(profile): update last_login_at on successful login"
```

---

### Task 6: 前端 — UserInfo 接口扩展

**Files:**
- Modify: `frontend/src/stores/user.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 修改 stores/user.ts 中的 UserInfo 接口**

```typescript
// 修改前:
export interface UserInfo {
  id: number
  username: string
  roles: string[]
}

// 修改后:
export interface UserInfo {
  id: number
  username: string
  roles: string[]
  email?: string
  phone?: string
  avatar_url?: string
  real_name?: string
  last_login_at?: string
}
```

- [ ] **Step 2: 修改 types/index.ts 中的 User 接口**

```typescript
// 修改前:
export interface User {
  id: number
  username: string
  email: string | null
  real_name: string | null
  is_active: boolean
  is_system: boolean
  roles: string[]
  created_at: string
}

// 修改后:
export interface User {
  id: number
  username: string
  email: string | null
  real_name: string | null
  is_active: boolean
  is_system: boolean
  roles: string[]
  created_at: string
  phone?: string | null
  avatar_url?: string | null
  last_login_at?: string | null
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/user.ts frontend/src/types/index.ts
git commit -m "feat(profile): extend UserInfo and User interfaces with profile fields"
```

---

### Task 7: 前端 — 新增 profile API 调用

**Files:**
- Modify: `frontend/src/api/users.ts`

- [ ] **Step 1: 在 users.ts 文件末尾新增 API 函数**

```typescript
/** 个人信息数据类型 */
export interface UserProfile {
  id: number
  username: string
  email: string | null
  phone: string | null
  avatar_url: string | null
  real_name: string | null
  last_login_at: string | null
  roles: string[]
}

/** 更新个人信息请求数据 */
export interface UpdateProfileData {
  email?: string
  phone?: string
  avatar_url?: string
  real_name?: string
}

/** 修改密码请求数据 */
export interface ChangePasswordData {
  current_password: string
  new_password: string
}

/**
 * 获取当前用户个人信息
 */
export function getProfile() {
  return api.get('/users/profile')
}

/**
 * 更新当前用户个人信息
 */
export function updateProfile(data: UpdateProfileData) {
  return api.put('/users/profile', data)
}

/**
 * 修改当前用户密码
 */
export function changePassword(data: ChangePasswordData) {
  return api.put('/users/password', data)
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/users.ts
git commit -m "feat(profile): add getProfile, updateProfile, changePassword API functions"
```

---

### Task 8: 前端 — 新增 /profile 路由

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 在 router/index.ts 的 children 数组中新增 profile 路由**

在 `path: ''` (Home) 路由后新增：

```typescript
{
  path: 'profile',
  name: 'Profile',
  component: () => import('@/views/Profile.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/router/index.ts
git commit -m "feat(profile): add /profile route"
```

---

### Task 9: 前端 — Dashboard Header 重构（核心 UI 变更）

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: 修改 Header 右侧布局**

找到 `Dashboard.vue` 中 `<div class="header-right">` 部分（约第 486-560 行），替换为：

```vue
<div class="header-right">
  <!-- 搜索 -->
  <ActionButton label="搜索" @click="$message.info('搜索功能开发中')">
    <svg
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  </ActionButton>

  <!-- 通知 -->
  <ActionButton label="消息通知" :badge="3" @click="$message.info('通知功能开发中')">
    <svg
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
      />
    </svg>
  </ActionButton>

  <!-- 设置 -->
  <ActionButton label="系统设置" @click="$message.info('设置功能开发中')">
    <svg
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
      />
    </svg>
  </ActionButton>

  <div class="header-divider"></div>

  <!-- 我的 - 用户头像 + 下拉菜单 -->
  <a-popover
    trigger="click"
    position="br"
    :content-style="{ padding: 0, borderRadius: '12px' }"
    :arrow-style="{ display: 'none' }"
  >
    <div class="user-avatar-btn" :class="{ active: userAvatarActive }">
      <div
        v-if="userStore.userInfo?.avatar_url"
        class="user-avatar-img"
      >
        <img :src="userStore.userInfo.avatar_url" :alt="userStore.userInfo.username" />
      </div>
      <div v-else class="user-avatar-text">
        {{ userStore.userInfo?.username?.charAt(0)?.toUpperCase() || 'U' }}
      </div>
    </div>

    <template #content>
      <div class="user-dropdown">
        <!-- 用户信息头部 -->
        <div class="dropdown-header">
          <div
            v-if="userStore.userInfo?.avatar_url"
            class="dropdown-avatar-img"
          >
            <img :src="userStore.userInfo.avatar_url" :alt="userStore.userInfo.username" />
          </div>
          <div v-else class="dropdown-avatar">
            {{ userStore.userInfo?.username?.charAt(0)?.toUpperCase() || 'U' }}
          </div>
          <div class="dropdown-user-info">
            <div class="dropdown-user-name">{{ userStore.userInfo?.username || '用户' }}</div>
            <div class="dropdown-user-role">{{ userStore.userInfo?.roles?.[0] || '运营经理' }}</div>
          </div>
        </div>

        <!-- 菜单项 -->
        <div class="dropdown-menu">
          <div class="dropdown-item" @click="goToProfile">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            个人信息
          </div>
          <div class="dropdown-item" @click="showChangePasswordModal">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            修改密码
          </div>
        </div>

        <!-- 分隔线 -->
        <div class="dropdown-divider"></div>

        <!-- 退出登录 -->
        <div class="dropdown-menu">
          <div class="dropdown-item danger" @click="handleLogout">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            退出登录
          </div>
        </div>
      </div>
    </template>
  </a-popover>
</div>

<!-- 修改密码对话框 -->
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
```

- [ ] **Step 2: 修改 script setup 部分**

在 `Dashboard.vue` 的 `<script setup>` 中新增：

```typescript
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { changePassword } from '@/api/users'
import ActionButton from '@/components/ActionButton.vue'

// ... 已有代码 ...

// 用户头像下拉菜单
const userAvatarActive = ref(false)

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

const showChangePasswordModal = () => {
  changePasswordVisible.value = true
  changePasswordForm.current_password = ''
  changePasswordForm.new_password = ''
  changePasswordForm.confirm_password = ''
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

const goToProfile = () => {
  router.push('/profile')
}

// ... handleLogout 已有 ...
```

- [ ] **Step 3: 新增下拉菜单相关 CSS**

在 `Dashboard.vue` 的 `<style scoped>` 末尾新增：

```css
/* 用户头像按钮 */
.user-avatar-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.user-avatar-btn:hover,
.user-avatar-btn.active {
  box-shadow: 0 0 0 3px rgba(3, 105, 161, 0.2);
}

.user-avatar-img {
  width: 100%;
  height: 100%;
}

.user-avatar-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar-text {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #0369a1 0%, #0284c7 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 16px;
  border-radius: 50%;
}

/* 下拉菜单 */
.user-dropdown {
  width: 240px;
}

.dropdown-header {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--neutral-1);
  border-bottom: 1px solid var(--neutral-2);
}

.dropdown-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0369a1 0%, #0284c7 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 16px;
  flex-shrink: 0;
}

.dropdown-avatar-img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
  overflow: hidden;
}

.dropdown-avatar-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dropdown-user-info {
  flex: 1;
  overflow: hidden;
}

.dropdown-user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--neutral-10);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-user-role {
  font-size: 12px;
  color: var(--neutral-5);
  margin-top: 2px;
}

.dropdown-menu {
  padding: 8px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--neutral-9);
  font-size: 14px;
  transition: background-color var(--transition-fast);
}

.dropdown-item:hover {
  background: var(--neutral-1);
}

.dropdown-item.danger {
  color: var(--danger-6);
}

.dropdown-item.danger:hover {
  background: var(--danger-1);
}

.dropdown-divider {
  height: 1px;
  background: var(--neutral-2);
  margin: 0 8px;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Dashboard.vue
git commit -m "feat(profile): add user avatar dropdown menu to header with profile, password, logout options"
```

---

### Task 10: 前端 — 个人信息页面 (Profile.vue)

**Files:**
- Create: `frontend/src/views/Profile.vue`

- [ ] **Step 1: 创建 Profile.vue**

```vue
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
            <a-button type="primary" size="small" @click="showAvatarUrlInput">
              更换头像
            </a-button>
            <a-button v-if="formData.avatar_url" size="small" @click="removeAvatar">
              移除
            </a-button>
          </div>
          <a-input
            v-if="avatarUrlInputVisible"
            v-model="avatarUrlInput"
            placeholder="输入头像图片 URL"
            size="small"
            style="margin-top: 8px; max-width: 300px;"
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
          <a-button type="primary" html-type="submit" :loading="submitLoading">
            保存
          </a-button>
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
  email: [
    { type: 'email', message: '邮箱格式不正确' },
  ],
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

:deep(.arco-form) {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-actions {
  display: flex;
  gap: 12px;
  padding-top: 8px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/Profile.vue
git commit -m "feat(profile): add Profile page with avatar, email, phone fields"
```

---

### Task 11: 前端 — 运行类型检查验证

- [ ] **Step 1: 运行 TypeScript 类型检查**

```bash
cd frontend && npm run type-check
```

Expected: 无类型错误

- [ ] **Step 2: 运行 lint 检查**

```bash
cd frontend && npm run lint
```

Expected: 无 lint 错误

- [ ] **Step 3: 修复发现的问题（如有）**

- [ ] **Step 4: Commit（如有修改）**

```bash
git add .
git commit -m "style(profile): fix type check and lint issues"
```

---

## 自审检查

### 1. 设计文档覆盖检查

| 设计文档要求 | 对应 Task | 状态 |
| ------------ | --------- | ---- |
| Header 布局调整（搜索、消息、设置、头像、退出） | Task 9 | ✅ |
| 圆形头像（40px，首字母+渐变） | Task 9 | ✅ |
| 下拉菜单（240px，用户信息+菜单项） | Task 9 | ✅ |
| 消息中心保持在"我的"左侧 | Task 9 | ✅ |
| 个人信息页面（/profile 路由） | Task 8, 10 | ✅ |
| 个人信息字段（用户名/邮箱/手机号/头像/最后登录） | Task 1, 2, 6, 10 | ✅ |
| 密码修改（对话框弹窗） | Task 9 | ✅ |
| 后端 API（GET/PUT /profile, PUT /password） | Task 3, 4 | ✅ |
| 数据库字段（email/phone/avatar_url/last_login_at） | Task 1, 2 | ✅ |
| 登录时更新 last_login_at | Task 5 | ✅ |
| 邮箱格式验证 | Task 4, 10 | ✅ |
| 手机号格式验证 | Task 4, 10 | ✅ |
| 密码长度验证（≥6） | Task 3, 9 | ✅ |
| 审计日志（密码修改） | Task 4 | ✅ |

### 2. 占位符扫描

- ✅ 无 "TBD"/"TODO"/"implement later"
- ✅ 所有步骤都有具体代码
- ✅ 无 "Add appropriate error handling" 等模糊描述
- ✅ 无 "Similar to Task N" 引用

### 3. 类型一致性

- ✅ `UserProfile` 接口在 `api/users.ts` 和 `Profile.vue` 中一致
- ✅ `UserInfo` 扩展字段在 `stores/user.ts` 中定义
- ✅ API 路径统一使用 `/users/profile` 和 `/users/password`
- ✅ 密码验证逻辑在 Service 层和前端表单中一致（≥6 位）
