# 技术设计: 开放平台 API-Key 管理与 ERP 余额查询接口

## 1. 架构边界

```
backend/
  app/
    models/
      api_key.py              # 新增：ApiKey 模型
      __init__.py              # 修改：注册 api_key
    middleware/
      auth.py                  # 修改：增加 /api/v1/erp/ API-Key 认证分支
    routes/
      api_keys.py              # 新增：API-Key 管理路由
      openapi.py               # 新增：开放平台 ERP 余额查询路由
    services/
      api_key_service.py      # 新增：API-Key 服务层
    constants/
      error_codes.py           # 修改：增加 API_KEY 相关错误码
    main.py                    # 修改：注册新蓝图
  alembic/versions/
    o4p5q6r7s8t9_add_api_keys_table.py  # 新增迁移
  scripts/
    seed.py                    # 修改：增加 api_keys:manage 权限

frontend/
  src/
    api/
      apiKeys.ts               # 新增：API-Key API 函数
    types/
      index.ts                 # 修改：增加 ApiKey 类型
    views/
      system/
        ApiKeyManagement.vue   # 新增：API-Key 管理页面
      OpenApiGuide.vue         # 新增：API 指南文档页面
    router/
      index.ts                 # 修改：增加 /system/api-keys 和 /openapi 路由
    components/
      layout/
        AppSidebar.vue         # 修改：侧边栏增加 API-Key 菜单项
```

## 2. 数据模型

### 2.1 ApiKey 模型 (`api_key.py`)

```python
class ApiKey(BaseModel):
    __tablename__ = "api_keys"

    name = Column(String(100), nullable=False)          # API-Key 名称
    key_prefix = Column(String(16), nullable=False, index=True)  # 前8位，用于列表脱敏展示
    key_hash = Column(String(255), nullable=False, unique=True, index=True)  # Key 的 SHA-256 哈希
    status = Column(String(20), nullable=False, default="active")  # active/disabled
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)         # 可选过期时间
    last_used_at = Column(DateTime, nullable=True)       # 最后使用时间
```

**设计决策**：
- **不存储明文 Key**：存储 SHA-256 哈希值，创建时仅返回一次明文。
- **key_prefix**：存储前 8 位用于列表识别和脱敏展示（如 `vk_xxxxx****`）。
- **Key 格式**：`vk_` + 32 字符随机字符串，共 35 字符。
- 继承 `BaseModel`，自动获得 `id`、`created_at`、`updated_at`、`deleted_at`。

## 3. 认证流程设计

### 3.1 中间件修改 (`auth.py`)

```
请求进入 auth_middleware
  ├─ 路径以 /api/v1/erp/ 开头？
  │   └─ YES → API-Key 认证流程
  │       ├─ 提取 Authorization: Bearer {key}
  │       ├─ 计算 key 的 SHA-256 哈希
  │       ├─ 查询 api_keys 表（hash 匹配 + status=active + deleted_at IS NULL）
  │       ├─ 检查 expires_at（如设置且已过期 → 401）
  │       ├─ 更新 last_used_at
  │       ├─ 存入 request.ctx.api_key = {id, name}
  │       └─ return（继续执行）
  │       └─ 验证失败 → 401
  └─ NO → 现有 JWT 认证流程（不变）
```

**关键点**：
- API-Key 认证路径不检查 JWT Token、不查 Token 黑名单。
- `last_used_at` 更新采用异步 fire-and-forget 方式，不阻塞响应。

### 3.2 开放平台路由 (`openapi.py`)

```python
openapi_bp = Blueprint("openapi", url_prefix="/api/v1/erp")

@openapi_bp.get("/balances")
async def get_erp_balances(request):
    # 1. 校验 erp_channel 参数
    # 2. 查询 customers (erp_system=erp_channel, deleted_at IS NULL, is_disabled=False)
    # 3. LEFT JOIN customer_balances
    # 4. 计算 balance = total_amount - used_total（无余额记录则 0.00）
    # 5. 返回 [{customer_id, customer_name, balance}]
```

## 4. 前端设计

### 4.1 API-Key 管理页面

参考现有 `ErpSystems.vue` 的模式：
- `PageHeader` + `a-table` + `a-modal` 标准三件套。
- 列：名称、Key（脱敏）、状态（Tag 组件）、描述、创建时间、最后使用时间、操作。
- 创建弹窗成功后，二次弹窗显示完整 Key + 复制按钮（`navigator.clipboard.writeText`）。
- 启用/停用使用 `a-switch` 或 `a-popconfirm` + 按钮切换。

### 4.2 API 指南文档页面 (`OpenApiGuide.vue`)

- 不使用 `Dashboard.vue` 布局（不需要侧边栏），独立的全屏页面。
- 左侧目录导航 + 右侧内容区（类似 API 文档网站风格）。
- 内容包含：概述、认证方式、接口详情、错误码表。
- 路由 `meta: { public: true }` 跳过登录校验。

### 4.3 路由修改

```typescript
// /openapi - 公开页面，不在 Layout children 内
{
  path: '/openapi',
  name: 'OpenApiGuide',
  component: () => import('@/views/OpenApiGuide.vue'),
  meta: { public: true },  // 不需要登录
}

// /system/api-keys - Layout children
{
  path: 'system/api-keys',
  name: 'ApiKeyManagement',
  component: () => import('@/views/system/ApiKeyManagement.vue'),
  meta: { requiresPermission: 'api_keys:manage' },
}
```

### 4.4 侧边栏菜单

在「系统管理」组中 ERP 系统之后增加「API-Key」按钮，权限 `api_keys:manage`。

## 5. 错误码扩展

```python
# error_codes.py 新增
API_KEY_INVALID = 40104      # API-Key 无效或已停用
API_KEY_EXPIRED = 40105      # API-Key 已过期
```

## 6. 兼容性

- 现有 JWT 认证流程不受影响（中间件只在 `/api/v1/erp/` 前缀时走 API-Key 分支）。
- `customer_balances` 表结构不变，只读查询。
- 现有前端路由、权限体系不受影响，仅新增不修改。
