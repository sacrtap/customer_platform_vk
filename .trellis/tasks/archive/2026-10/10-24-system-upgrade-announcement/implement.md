# 系统升级自动公告提示 — Implement

## 前置核对（先读再改）

- [ ] `read backend/app/config.py`：定位 `external_api_token` 行后的插入点；确认 Settings 字段风格（类型注解 + 默认值）。
- [ ] `read backend/app/cache/base.py`：确认 `_ttl_config` 与 `set(prefix, data, *parts, ttl=None)` / `ttl_for` 签名。
- [ ] `read backend/app/services/external_api.py`：确认 ExternalAPIClient 模式（httpx 用法、异常处理、日志）。
- [ ] `read backend/app/routes/roles.py:1-19`：确认 Blueprint + `@auth_required` 头部写法。
- [ ] `read backend/app/main.py:270-320`：确认 import 块与 blueprint 注册块位置与排序。
- [ ] `read frontend/src/api/billing.ts:1-20`：确认 api 模块写法。
- [ ] `read frontend/src/views/Dashboard.vue`：确认模板结构、script 导入、onMounted 是否已存在。
- [ ] `read frontend/src/components/billing/DiscountApprovalModal.vue`（或同类）：确认 `v-model:visible` 弹框写法。
- [ ] `read frontend/src/views/customers/detail/EditCustomerDialog.vue`：确认 `:body-style` 固定高度滚动写法。
- [ ] `read backend/tests/` 下一个 mock httpx 的现有测试：确认 mock 约定（pytest-asyncio、unittest.mock 等）。
- [ ] 确认 `.env.example` 存在与「外部 API」块位置。

## 实施顺序

### 1. 后端配置与缓存
- [ ] `backend/app/config.py`：`external_api_token` 后新增 `github_repo` / `github_token` / `github_workflow_file`（中文注释）。
- [ ] `.env.example`：外部 API 块后增补三项（Token 留空 + 注释说明匿名 60/h）。
- [ ] `backend/app/cache/base.py`：`_ttl_config` 中 `"default": 300` 前加 `"system_updates": 600`。

### 2. GitHub 客户端服务
- [ ] 新建 `backend/app/services/github_updates.py`：`GitHubUpdatesClient`（`_headers` / `_get` / `get_recent_updates`）+ 全局单例 + `get_github_updates_client()` 工厂。

### 3. 路由与注册
- [ ] 新建 `backend/app/routes/system.py`：`system_bp` + `GET /updates`（`@auth_required`，缓存包装，仅非空写缓存）。
- [ ] `backend/app/main.py`：import 块（`sync_tasks` 与 `tags` 之间）+ `app.blueprint(system_bp)`（注册块末尾）。

### 4. 前端 API 与组件
- [ ] 新建 `frontend/src/api/system.ts`：`DeployCommit` / `DeployUpdate` 接口 + `getSystemUpdates()`。
- [ ] 新建 `frontend/src/components/system/UpgradeAnnouncementModal.vue`：按 design 契约（600px、body 440px 滚动、title/footer 插槽、时间轴块、`mask-closable=false`）。
- [ ] `frontend/src/views/Dashboard.vue`：vue 导入补 `onMounted`；引入 `useUserStore` / `getSystemUpdates` / 组件；模板插入弹框；新增 `upgradeVisible` / `upgradeUpdates` / `onMounted` / `handleUpgradeClose`。

### 5. 测试
- [ ] 新建 `backend/tests/test_github_updates.py`（mocked httpx，4 用例）：正常 3 条透传 / identical → `[]` / 仅 1 条成功 → 回退单条 / 不可达 → `[]`。
- [ ] 如有 Sanic test_client 约定，补一条 `/api/v1/system/updates` 带 token 200 + `data.updates` 断言（可选）。

## 验证命令

```bash
# 后端静态检查 + 测试
cd backend && ruff check app/ tests/ && python -m pyright 2>/dev/null | tail -1
cd backend && python -m pytest tests/test_github_updates.py -v

# 前端类型检查
cd frontend && pnpm type-check

# 端到端（后端 127.0.0.1:8000，Redis 可用）
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"<账号>","password":"<密码>"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
curl -s http://127.0.0.1:8000/api/v1/system/updates -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# 无 token 应 401
```

前端浏览器验证：登录 → 弹框出现（≤3 部署块、440px 滚动）→ 关 → 刷新不弹 → 清 localStorage 再弹 → 后端停掉静默不弹。

## 验收边界（交付前填写）

- 目标：见 prd.md AC1–AC9。
- 改动文件：
  - 后端：`app/config.py`（3 个 GitHub 配置字段）、`app/cache/base.py`（`system_updates` TTL 600）、`app/services/github_updates.py`（新建）、`app/routes/system.py`（新建）、`app/main.py`（import + blueprint 注册）、`.env.example`（GitHub 配置注释块）
  - 前端：`src/api/system.ts`（新建）、`src/components/system/UpgradeAnnouncementModal.vue`（新建）、`src/views/Dashboard.vue`（弹框挂载 + onMounted 已读逻辑）
  - 测试：`backend/tests/unit/test_github_updates_service.py`（5 用例）、`backend/tests/unit/test_system_updates_route.py`（3 用例）
- 跑了哪些验证：
  - `cd backend && .venv/bin/python -m pytest tests/unit tests/integration -q`：**372 passed**（无并发窗口，含新增 8 用例）
  - `ruff check app/ tests/`：No issues；`.venv/bin/pyright`：0 errors
  - `cd frontend && pnpm type-check` 通过、`pnpm lint`：No issues
  - 真实接口（后端 127.0.0.1:8000 + Redis）：带 token 返回 3 条成功部署（commits 28/2/1）；无 token → 401；Redis `cache:system_updates:` TTL=600；冷请求 1.5-2s（真实出站 GitHub）vs 热请求 0.15s
  - 浏览器（Chromium 实测）：登录后自动弹出公告（600px 宽、body 440px 可滚动、3 个部署块、31 条提交、CST 时间正确、绿色徽标、双按钮）→「我知道了」关闭并写入 `upgrade_announcement_last_read_32` → 刷新不弹 → 清 key 后再弹；XHR 层验证 500 时 `getSystemUpdates()` reject（onMounted catch 静默降级）
- 结论：**通过**（AC1–AC9 全部满足；既有集成测试失败为并发踩踏测试库所致，无并发基线 372 全过可证）

## Rollback

revert 本任务提交即可；无迁移、无 schema 变更、无配置破坏性默认值。
