---
name: directories
description: "客户运营中台项目目录结构约定：前后端关键目录、文件职责和组织规范"
ruleType: Model Request
---

## Key Directories

### 后端 (`backend/`)

| 目录 | 职责 | 关键文件 |
|------|------|----------|
| `app/main.py` | Sanic 应用工厂，初始化 DB/CORS/中间件/蓝图/调度器 | `create_app()` |
| `app/config.py` | Pydantic Settings，支持 `.env` 文件 | `settings` 单例 |
| `app/models/` | SQLAlchemy ORM 模型（11+ 个） | `users.py`, `customers.py`, `billing.py` |
| `app/routes/` | 按业务域拆分的包结构路由 | `auth.py`, `customers/`, `billing/`, `analytics/` |
| `app/services/` | 按业务域拆分的包结构服务层 | `customers/`, `billing/`, `analytics/`, `sync_task_service.py` |
| `app/middleware/` | 认证 + 审计中间件 | `auth.py`, `audit.py` |
| `app/cache/` | Redis 缓存服务 | `base.py` (CacheService) |
| `tests/unit/` | 单元测试（≈20 个测试文件） | `test_billing_service.py`, `test_cache.py` |
| `tests/integration/` | 集成测试（≈15 个测试文件） | `test_customers_api.py`, `test_billing_api.py` |
| `scripts/` | 工具脚本 | `seed.py`, `create_test_data.py`, `generate_secrets.py` |

### 前端 (`frontend/`)

| 目录 | 职责 | 关键文件 |
|------|------|----------|
| `src/main.ts` | Vue 应用入口，注册 Pinia/Router/Arco Design | - |
| `src/router/index.ts` | 路由配置（懒加载 + 守卫） | `routes[]`, `router.beforeEach` |
| `src/api/` | Axios API 封装（纯函数导出） | `index.ts` (拦截器), `customers.ts`, `billing.ts` |
| `src/stores/` | Pinia Store（状态管理） | `user.ts`, `customer.ts` |
| `src/views/` | 页面组件（11 个模块） | `Dashboard.vue`, `Home.vue`, `customers/`, `billing/`, `analytics/` |
| `src/components/` | 通用组件 | `StatCard.vue`, `TagSelector.vue`, `charts/` |
| `src/types/` | TypeScript 类型定义 | `index.ts` ( ApiResponse, Customer, User 等) |
| `src/utils/` | 工具函数 | `errorHandler.ts`, `formatters.ts` |
