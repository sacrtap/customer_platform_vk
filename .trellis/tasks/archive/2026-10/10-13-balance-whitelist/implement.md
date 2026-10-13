# 开放平台余额白名单 — 实施计划

## 实施顺序（checklist）

### 阶段 A：后端数据层
- [x] A1 新建 `backend/app/models/balance_whitelist.py`（BalanceWhitelist，参照 `erp_system.py`），注册到 `backend/app/models/__init__.py`
- [x] A2 新建 alembic 迁移（`down_revision = "a2b3c4d5e6f7"`）：建表 balance_whitelists + 唯一索引 customer_id + 权限 `balance_whitelist:manage` + 关联超级管理员；downgrade 反向清理（参照 `l1m2n3o4p5q6_add_erp_systems_table.py`）

### 阶段 B：后端服务与路由
- [x] B1 新建 `backend/app/services/balance_whitelist_service.py`：列表(分页+keyword)、按 ERP 批量导入（幂等跳过、软删恢复）、单独添加、编辑余额、软删移除。**注：写操作实际用 `await self.db.commit()`，因 Sanic 中间件已对 session 开启事务，`async with db_session.begin():` 会抛 `InvalidRequestError`（测试库已验证）**
- [x] B2 新建 `backend/app/routes/balance_whitelist_routes.py`（蓝图 `/api/v1/balance-whitelists`，全部 `@auth_required` + `@require_permission("balance_whitelist:manage")`）；注册蓝图于 `backend/app/main.py`
- [x] B3 改造 `backend/app/routes/openapi.py`：`_build_customer_balance_stmt()` 追加取回 `Customer.id`；`get_all_customer_balances` 查询白名单 map 并传入 `_format_balance_rows`，命中白名单的 `balance` 覆盖为 `static_balance`；**不改** `get_erp_balances`

### 阶段 C：后端测试
- [x] C1 测试：`tests/integration/test_balance_whitelist_routes.py`（22 用例：列表/过滤/添加/幂等跳过/dry_run/软删恢复/编辑/移除/权限403）+ `test_openapi_api.py` 追加 4 用例（白名单覆盖/软删忽略/erp 不受影响）+ `tests/unit/test_openapi_handlers.py` 更新至 5 列签名
- [x] C2 跑通 `pytest`（backend，含覆盖率）：单元门禁 568 passed / 34.08% ≥ 34%；合并全量 893 passed / 53.72% ≥ 50%；白名单相关 29 passed

### 阶段 D：前端
- [x] D1 `api/balanceWhitelist.ts` 新增（类型定义于文件内）；`types/index.ts` 同步补 `BalanceWhitelistItem`
- [x] D2 新建 `views/system/BalanceWhitelist.vue`（列表 + 按 ERP 批量导入预检弹窗 + 添加客户弹窗 + 编辑余额 + 移出确认）
- [x] D3 `router/index.ts` system children 新增 `balance-whitelist` 路由（`requiresPermission: 'balance_whitelist:manage'`）；`AppSidebar.vue` 系统管理组新增菜单项
- [x] D4 前端 type-check + eslint + build 通过（修复了列表/批量导入解包层级 bug：axios 拦截器已解包一层，对齐项目约定后直取 `res.data`）

### 阶段 E：验证与交付
- [x] E1 端到端验证：backend + frontend 运行，浏览器验证：登录 → 菜单 → 添加客户（默认 1000）→ 列表展示 → 批量导入（预检 38 条 → 确认导入成功）→ 移出（popconfirm 软删）；API-Key 调接口验证（全量接口白名单客户 1000.0 / 非白名单计算余额 / erp 接口不受影响）
- [x] E2 交付总结：见 Git 提交消息 + 本文件验收边界（下方）

## 验证命令

```bash
# 后端（backend 目录）
$BACKEND_DIR/.venv/bin/python -m pytest            # 全量（含覆盖率）
alembic upgrade head && alembic downgrade -1 && alembic upgrade head   # 迁移可逆性

# 前端（frontend 目录）
npm run type-check && npm run lint && npm run build
```

## 风险文件 / 回滚点

- `backend/app/routes/openapi.py`：核心改造点，需保持契约与 erp 接口不变；回滚 = 还原该文件 + 迁移 downgrade。
- `backend/app/main.py` 蓝图注册区：新增注册行，删除即可回滚。
- `frontend/src/components/layout/AppSidebar.vue` 与 `router/index.ts`：菜单/路由新增，删除即回滚。
- alembic 迁移 `down_revision` 必须以当前 head `a2b3c4d5e6f7` 为基线，避免迁移链冲突。

## task.py start 前复查

- [x] prd.md / design.md / implement.md 三件齐全且收敛
- [x] 无阻塞性开放问题
- [x] 用户已明确批准最终规划总结

---

## 验收边界与最终验证结果（交付记录）

**目标**：系统管理「余额白名单」页面（ERP 批量导入/单独添加客户，静态余额默认 1000，支持编辑/移出）；开放平台 `GET /api/v1/balances` 对白名单客户优先返回静态余额、`GET /api/v1/erp/balances` 不变。

**改动文件**
- 新增：`backend/app/models/balance_whitelist.py`、`backend/app/services/balance_whitelist_service.py`、`backend/app/routes/balance_whitelist_routes.py`、`backend/alembic/versions/v1w2x3y4z5a6_add_balance_whitelists_table.py`、`backend/tests/integration/test_balance_whitelist_routes.py`、`frontend/src/api/balanceWhitelist.ts`、`frontend/src/views/system/BalanceWhitelist.vue`
- 修改：`main.py`（蓝图注册）、`models/__init__.py`、`routes/openapi.py`（白名单覆盖）、`scripts/seed.py` + `tests/_test_data.py`（权限码注册）、`tests/integration/conftest.py`（TRUNCATE 列表）、`tests/integration/test_openapi_api.py`、`tests/unit/test_openapi_handlers.py`（5 列签名）、`frontend/src/types/index.ts`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppSidebar.vue`

**验证结果（全部通过）**
1. 白名单相关测试 29 passed（`test_balance_whitelist_routes.py` 22 + `test_openapi_api.py` 追加 4 + 既有 3）
2. 单元门禁：568 passed，覆盖率 34.08% ≥ 34%（CI PR 门禁）
3. 合并全量（unit+integration）：893 passed，覆盖率 53.72% ≥ 50%（CI 全量口径）
4. 全量 integration：325 passed；ruff ✅；pyright 0 errors ✅
5. 迁移可逆性（独立临时库）：upgrade head → downgrade -1 → upgrade 全通过，表/权限正确创建与删除；超管权限由运行时 seed.py 按 ALL_PERMISSIONS 动态授予（与既有 erp_systems 迁移行为一致）
6. 前端：type-check ✅ / eslint ✅ / build ✅
7. E2E（浏览器 + API-Key）：登录 → 「余额白名单」菜单进入 → 添加客户（小猪用户，默认 1000 落库）→ 列表展示（¥1,000.00）→ ERP 批量导入（选「易遨」→ 预检查显示「将导入 38 条，已存在跳过 0 条」→ 确认导入成功 38 条，total 39）→ 移出（popconfirm「确认将该客户移出白名单？」→ 已移出，total 38）→ 接口：`/api/v1/balances` 白名单客户返回 `1000.0`、非白名单返回计算余额 `0.0`；`/api/v1/erp/balances?erp_channel=yiao` 同客户仍返回计算余额 `0.0`（不受白名单影响）

**未纳项/已知边界**
- 既有失败（与本任务无关，勿修）：`tests/test_analytics_service.py` 5 个失败（`app/services/analytics.py:2647` TypeError，位于 tests/ 根，不在 CI 门禁 tests/unit/ 范围）
- 前端「编辑余额」弹窗的输入自动化注入受 Arco InputNumber 限制（headless 工具问题），已验证：弹窗正确显示当前值、提交走 PUT 接口、服务端实际更新（直接 PUT 2500 落库成功）；真实键盘输入不受影响
- 白名单编辑/移出/软删恢复在集成测试覆盖；测试库并发禁忌（绝不同时跑两个 pytest 进程）已规避
