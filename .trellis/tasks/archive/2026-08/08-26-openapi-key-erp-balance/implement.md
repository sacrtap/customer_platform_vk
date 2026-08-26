# 实施计划: 开放平台 API-Key 管理与 ERP 余额查询接口

## 执行清单

### Phase 1: 后端 - 数据模型与迁移

- [ ] 1.1 创建 `backend/app/models/api_key.py` — ApiKey 模型
- [ ] 1.2 在 `backend/app/models/__init__.py` 注册 `api_key` 模型
- [ ] 1.3 创建 Alembic 迁移 `o4p5q6r7s8t9_add_api_keys_table.py`（down_revision = `n3o4p5q6r7s8`）
- [ ] 1.4 执行迁移：`cd backend && alembic upgrade head`
- [ ] 1.5 在 `backend/scripts/seed.py` 中添加 `api_keys:manage` 权限

**验证**: `alembic upgrade head` 成功，`api_keys` 表存在。

### Phase 2: 后端 - 错误码与中间件

- [ ] 2.1 在 `backend/app/constants/error_codes.py` 增加 `API_KEY_INVALID`、`API_KEY_EXPIRED`
- [ ] 2.2 修改 `backend/app/middleware/auth.py`：增加 `/api/v1/erp/` 前缀的 API-Key 认证分支

**验证**: 中间件对 `/api/v1/erp/` 路径走 API-Key 认证，其他路径走 JWT。

### Phase 3: 后端 - API-Key 管理服务与路由

- [ ] 3.1 创建 `backend/app/services/api_key_service.py` — CRUD + 生成 Key + 验证 Key
- [ ] 3.2 创建 `backend/app/routes/api_keys.py` — Blueprint `/api/v1/api-keys`
- [ ] 3.3 在 `backend/app/main.py` 注册 `api_keys_bp` 和 `openapi_bp`

**验证**: `ruff check app/` 无 lint 错误。

### Phase 4: 后端 - 开放平台 ERP 余额查询路由

- [ ] 4.1 创建 `backend/app/routes/openapi.py` — Blueprint `/api/v1/erp`，实现 `GET /balances`

**验证**: 使用 curl 测试 `GET /api/v1/erp/balances?erp_channel=qiaofang` 返回数据。

### Phase 5: 前端 - 类型与 API 函数

- [ ] 5.1 在 `frontend/src/types/index.ts` 增加 `ApiKey` 接口
- [ ] 5.2 创建 `frontend/src/api/apiKeys.ts` — API 函数

### Phase 6: 前端 - API-Key 管理页面

- [ ] 6.1 创建 `frontend/src/views/system/ApiKeyManagement.vue`
- [ ] 6.2 在 `frontend/src/router/index.ts` 增加 `/system/api-keys` 路由
- [ ] 6.3 在 `frontend/src/components/layout/AppSidebar.vue` 增加 API-Key 菜单项

**验证**: 页面可创建/查看/停用/删除 API-Key。

### Phase 7: 前端 - API 指南文档页面

- [ ] 7.1 创建 `frontend/src/views/OpenApiGuide.vue`
- [ ] 7.2 在 `frontend/src/router/index.ts` 增加 `/openapi` 路由（`meta: { public: true }`）
- [ ] 7.3 修改路由守卫：`meta.public` 跳过登录检查

**验证**: `http://localhost:5173/openapi` 可公开访问。

### Phase 8: 质量检查

- [ ] 8.1 `cd backend && ruff check app/`
- [ ] 8.2 `cd frontend && pnpm type-check`

## 回滚点

- Phase 1 后回滚：`alembic downgrade n3o4p5q6r7s8`
- Phase 2-4 后回滚：删除新增文件，还原 auth.py 和 main.py
- Phase 5-7 后回滚：删除新增前端文件，还原 router 和 sidebar

## 验证命令

```bash
# 后端 lint
cd backend && ruff check app/

# 前端 type-check
cd frontend && pnpm type-check

# 迁移状态
cd backend && alembic current

# 接口测试（需先创建 API-Key）
curl -H "Authorization: Bearer vk_xxxxx" "http://localhost:8000/api/v1/erp/balances?erp_channel=qiaofang"
```
