## Code Conventions & Common Patterns

### 后端 Python 规范

#### 错误处理

- **统一错误码**: `backend/app/constants/error_codes.py` 定义 5 位数字错误码
  - `4xxxx`: 客户端错误（如 `40001` 参数错误）
  - `5xxxx`: 服务端错误（如 `50001` 内部错误）
- **响应格式**: `return json(code=N, message="...", data=None)` 终止请求，不抛异常
- **事务管理**: 所有修改操作必须在事务中执行（`async with db_session.begin()`）

#### 异步模式

- **全异步**: Sanic + AsyncSession + asyncpg，所有 I/O 操作使用 `async/await`
- **部分双模式**: 某些 Service 支持 sync/async 两种接口（如 `CustomerService`）
- **Session 获取**: 从 `request.ctx.db_session` 获取，不在路由层创建

#### 依赖注入

- **构造注入**: Service 通过构造函数注入 `db_session`（如 `CustomerService(db_session)`）
- **静态/单例**: `AuthService` 全静态方法，`CacheService` 单例模式
- **Session 生命周期**: 每个请求独立 Session，中间件管理创建/关闭

#### 路由组织

- **Blueprint**: 按业务领域分为 17 个 Blueprint（`/api/v1/<module>`）
- **装饰器鉴权**: `@auth_required` + `@require_permission("module:action")`
- **通配符权限**: 支持 `*` 匹配（如 `customers:*` 匹配所有客户相关权限）

#### 模型基类

- `TimestampMixin`: 自动添加 `created_at`, `updated_at`
- `SoftDeleteMixin`: 软删除支持（`deleted_at` 字段）
- `BaseModel`: 继承 `DeclarativeBase`，提供通用方法

#### 审计日志

- **自动记录**: `audit_middleware` 拦截 PUT/DELETE 请求
- **变更对比**: 前置捕获 before 状态，后置记录 diff
- **工具函数**: `create_audit_entry()`, `build_batch_audit_summary()`

### 前端 TypeScript 规范

#### 组件规范

- **命名**: `PascalCase`（如 `CustomerDetail.vue`, `StatCard.vue`）
- **语法**: `<script setup lang="ts">` + Composition API
- **Props**: `defineProps<T>()` + `withDefaults()`
- **Emits**: `defineEmits<{ event: [payload] }>()`

#### 状态管理

- **Pinia Store**: setup store 风格（非 options API）
- **持久化**: `localStorage` 存储 token/userInfo/permissions
- **缓存策略**: `customer.ts` 使用 Map + TTL 细粒度缓存
- **权限检查**: `hasPermission(code)` 方法，支持超级管理员豁免

#### API 调用

- **纯函数导出**: 每个 API 模块导出独立函数（如 `getCustomers()`, `updateCustomer()`）
- **统一实例**: `axios.create({ baseURL: '/api/v1', timeout: 15000 })`
- **拦截器**:
  - 请求：注入 `Authorization: Bearer <token>`
  - 响应：401 自动刷新 Token + 并发队列等待
- **类型安全**: 使用 `ApiResponse<T>` 泛型封装响应结构

#### 路由守卫

- **meta 字段**: `requiresAuth`, `requiresPermission: 'module:action'`
- **导航守卫**: `router.beforeEach()` 检查登录态和权限
- **懒加载**: `component: () => import('@/views/...')`

#### 工具函数

- **错误处理**: `handleError(error)` 统一分类处理（网络/权限/业务/未知）
- **格式化**: `formatCurrency()`, `formatDate()`, `formatPercent()`
- **错误分类**: `ErrorCategory` 枚举（NETWORK, AUTH, BUSINESS, UNKNOWN）

### 通用约定

#### 数据库事务

- **强制事务**: 所有写操作必须在 `async with db_session.begin():` 块内
- **行级锁**: 余额扣款使用 `FOR UPDATE` 防止并发冲突
- **原子性**: 多表更新确保要么全部成功，要么全部回滚

#### 缓存策略

- **Redis 前缀**: 按模块区分（如 `customer:`, `billing:`）
- **TTL 配置**: 各模块独立 TTL（如客户列表 5 分钟，详情 1 小时）
- **失效策略**: 写操作后主动失效相关缓存键

#### 权限校验

- **装饰器优先**: 所有 API 端点必须添加 `@auth_required`
- **细粒度权限**: `@require_permission("customers:view")` 精确到动作
- **超级管理员**: 拥有所有权限，豁免具体权限检查
