## Important Files

### 入口文件

| 文件 | 说明 |
|------|------|
| `backend/app/main.py` | Sanic 应用工厂 `create_app()`，初始化所有组件 |
| `frontend/src/main.ts` | Vue 应用入口，注册 Pinia/Router/Arco Design |
| `backend/app/config.py` | Pydantic Settings，加载 `.env` 配置 |

### 配置文件

| 文件 | 说明 |
|------|------|
| `.env.example` | 环境变量模板（DATABASE_URL/JWT_SECRET/REDIS_URL 等） |
| `backend/pyproject.toml` | Ruff + pytest 配置 |
| `frontend/package.json` | NPM 依赖 + 脚本 |
| `deploy/docker-compose.yml` | Docker Compose 编排（nginx + app + db + redis） |

### 关键模块

| 文件 | 说明 |
|------|------|
| `backend/app/models/__init__.py` | 11+ ORM 模型（User, Customer, Billing 等） |
| `backend/app/services/customers/` | 客户服务包（CRUD + 导入导出） |
| `backend/app/services/billing/` | 结算服务包（余额/定价/发票） |
| `backend/app/services/analytics/` | 分析服务包（消耗/回款/健康度） |
| `backend/app/middleware/auth.py` | JWT 认证 + RBAC 权限校验中间件 |
| `backend/app/middleware/audit.py` | 自动审计日志中间件 |
| `backend/app/cache/base.py` | Redis 缓存服务（CacheService 单例） |
| `frontend/src/api/index.ts` | Axios 实例 + 拦截器（Token 刷新） |
| `frontend/src/stores/user.ts` | 用户状态 Store（token/userInfo/permissions） |
| `frontend/src/router/index.ts` | 路由配置 + 导航守卫 |

### 工具脚本

| 文件 | 说明 |
|------|------|
| `backend/scripts/seed.py` | 初始化种子数据（admin 账号 + 权限 + 角色） |
| `scripts/pre-commit-check.sh` | 提交前完整验证脚本 |
