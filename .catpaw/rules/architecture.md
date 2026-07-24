---
name: architecture
description: "客户运营中台系统架构设计原则：前后端分离、分层架构、技术栈版本要求和数据流路径"
ruleType: Model Request
---

## Architecture & Data Flow

### 整体架构

前后端分离架构，采用**分层架构 + 垂直业务切片**设计：

```
Frontend (Vue 3 + Pinia)
  ↓ HTTP (Axios, baseURL=/api/v1)
Backend (Sanic + SQLAlchemy ORM)
  Routes → Middleware (Auth/Audit) → Services → Models → PostgreSQL
                                      ↓
                                    Redis Cache
```

### 后端架构模式

- **框架**: Sanic 22.12.0（异步 Python Web 框架）
- **ORM**: SQLAlchemy 2.0.25（AsyncSession + asyncpg）
- **数据库**: PostgreSQL 18
- **缓存**: Redis 7（CacheService 单例，TTL 可配置）
- **定时任务**: APScheduler 3.10.4
- **认证**: JWT（PyJWT 2.8.0）+ RBAC 权限校验中间件
- **审计**: 自动审计日志中间件（PUT/DELETE 前置捕获 before 状态）

### 前端架构模式

- **框架**: Vue 3.4 + Composition API (`<script setup lang="ts">`)
- **状态管理**: Pinia 2.1.7（setup store，localStorage 持久化）
- **UI 组件库**: Arco Design 2.54.3
- **路由**: Vue Router 4.2.5（懒加载 + 导航守卫）
- **HTTP 客户端**: Axios 1.6.5（请求/响应拦截器，401 自动刷新 Token）
- **构建工具**: Vite 7.3.3 + vue-tsc 3.2.6

### 数据流路径

**典型 C(R)UD 操作**:
```
前端 View → API 函数调用 → Axios 拦截器注入 JWT → HTTP POST/GET/PATCH
  ↓
后端 Route (@auth_required + @require_permission) → Service 层
  ↓
Service 构造注入 db_session → ORM 查询/更新 → PostgreSQL
  ↓
CacheService 读写穿透（可选）→ Redis
  ↓
Audit Middleware 记录变更对比 → audit_logs 表
  ↓
JSON 响应返回前端 → 更新 Pinia Store → UI 重渲染
```

**Token 刷新机制**:
- 响应拦截器检测 401 → 检查是否正在刷新 → 未刷新则调用 `/auth/refresh`
- 并发请求加入队列 → 刷新成功后批量通知 → 失败则跳转登录页

### 模块化规范

#### 文件大小限制
- 单个文件不超过 500 行（测试文件除外）
- 超过限制时必须按业务域拆分为包结构

#### 目录结构规范
- `backend/services/` 按业务域拆分（analytics/, billing/, customers/）
- `backend/routes/` 按业务域拆分（billing/, customers/）
- `frontend/views/` 按功能模块组织子目录

#### 新功能组织
- 新功能必须按业务域组织到对应模块目录
- 包内 `__init__.py` 必须显式导出所有公共 API

### TypeScript 类型完整性

- 所有新组件必须提供完整类型定义
- 禁止使用 `any` 类型（除明确标注的例外）
- `npm run type-check` 必须 0 errors 才能提交
