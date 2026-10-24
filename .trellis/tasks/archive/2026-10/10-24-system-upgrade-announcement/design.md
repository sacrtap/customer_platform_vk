# 系统升级自动公告提示 — Design

## 架构与数据流

```mermaid
flowchart LR
  FE["Dashboard.vue<br/>onMounted"] -->|GET /api/v1/system/updates| RT["routes/system.py<br/>@auth_required"]
  RT -->|get prefix=system_updates| CA["cache_service<br/>(Redis, TTL 600s)"]
  CA -->|miss| GH["services/github_updates.py<br/>GitHubUpdatesClient"]
  GH -->|GET workflows/runs| GHAPI["api.github.com<br/>(匿名 60/h)"]
  GH -->|GET compare/base...head| GHAPI
  GH -->|updates 非空| CA
  RT -->|信封 {code,message,data}| FE
  FE -->|"updates[0].deployed_at ≠ localStorage"| MODAL["UpgradeAnnouncementModal.vue"]
```

## 后端设计

### 1. 配置（`backend/app/config.py`）

`Settings` 的「外部 API 配置」块之后新增三个字段，pydantic-settings 自动映射 `GITHUB_REPO` / `GITHUB_TOKEN` / `GITHUB_WORKFLOW_FILE`：

```python
github_repo: str = "sacrtap/customer_platform_vk"
github_token: str = ""
github_workflow_file: str = "deploy.yml"
```

### 2. 缓存 TTL（`backend/app/cache/base.py`）

`CacheService.__init__` 的 `_ttl_config` 中 `"default": 300` 之前登记 `"system_updates": 600`。`set(prefix, data, *parts, ttl=None)` 走 `ttl_for(prefix)`；Redis 不可用时 `CacheService` 降级返回 None，路由静默降级。

### 3. GitHub 客户端（`backend/app/services/github_updates.py`，新建）

仿 `services/external_api.py` 的 `ExternalAPIClient` 模式：类 + 全局单例 + 工厂函数；`async with httpx.AsyncClient(timeout=...)`；`httpx.HTTPError` 吞异常记 error 日志返回 None。

对外契约 `get_recent_updates(count=3) -> list[dict]`：

| 字段 | 来源 | 说明 |
|---|---|---|
| `deployed_at` | run `created_at` | ISO UTC，前端词法可比较 |
| `head_sha` | run `head_sha[:7]` | 短 sha |
| `status` | 常量 `"success"` | 只取 success 部署 |
| `html_url` | run `html_url` | 跳 GitHub 查看完整记录 |
| `commits[]` | compare `commits[]` | `{sha:7, message:首行, author, date}` |

拉取策略：`per_page={count+5}` 多取几条以过滤成功；对第 i 次部署取 `compare/{succ[i+1].head_sha}...{run.head_sha}`；最旧部署无前序基线回退 `head_commit` 单条。

边界：404/限流/不可达 → `[]`；identical → `commits: []`；成功不足 count → 返回实际条数。

### 4. 路由（`backend/app/routes/system.py`，新建）

仿 `routes/roles.py` 头部写法；`url_prefix="/api/v1/system"`（已核实无冲突）。只读、无 `db_session`。缓存命中直接返回；未命中拉取，**仅非空结果写缓存**（失败可下次重试）。

### 5. 注册（`backend/app/main.py`）

import 块按字母序插在 `sync_tasks` 与 `tags` 之间；`app.blueprint(...)` 块末尾追加。

## 前端设计

### 6. API（`frontend/src/api/system.ts`，新建）

`import api from './index'`（共享 axios 实例，baseURL `/api/v1`），导出 `DeployCommit` / `DeployUpdate` 接口 + `getSystemUpdates()`。

### 7. 弹框（`frontend/src/components/system/UpgradeAnnouncementModal.vue`，新建）

- props：`updates: DeployUpdate[]`；`v-model:visible`；`:mask-closable="false"`；`:width="600"`。
- `#title` 插槽：图标（`IconArrowRise`，不存在则 `IconSync`）+「系统升级公告」+ 副标题「系统近期完成了 N 次部署更新」。
- body `:body-style="{ height: '440px', overflowY: 'auto', padding: '16px 20px' }"`：时间轴式部署块（头行：CST 时间 + 绿色「部署成功」徽标 + 共 N 条提交；提交列表：短 sha + 标题省略 + 作者/时间 muted）。
- `#footer` 插槽：「在 GitHub 查看完整记录」（`window.open(updates[0].html_url)`）+ primary「我知道了」。
- `handleClose()`：`emit('update:visible', false); emit('close')`。
- 时间格式化内联：`toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })`。

### 8. 挂载（`frontend/src/views/Dashboard.vue`）

`Dashboard.vue` 是 `/` 路由 Layout 根组件，`onMounted` 覆盖全部登录入口（新登录 + 已登录刷新 + 守卫重定向回 `/`）。修改密码 modal 之后插入组件挂载；`onMounted` 中按 `userStore.userInfo?.id` 取已读 key `upgrade_announcement_last_read_{uid}`，ISO UTC 词法比较 `updates[0].deployed_at > lastRead` 决定弹出；`handleUpgradeClose` 写入该 key。

## Tradeoffs

| 决策 | 选择 | 理由 |
|---|---|---|
| 数据源 | Deploy workflow runs | 仓库无 Releases；部署即 workflow 运行 |
| 摘要口径 | 两次部署间全部提交 | 用户已选；信息全，滚动承载 |
| 触发 | localStorage 按用户记已读 | 避免每次登录打扰；key 含 uid 贴合「每用户至少看一次」 |
| 缓存 | Redis 600s，仅缓存非空 | 匿名 60/h 兜底；空结果不缓存以便失败重试 |
| 失败策略 | 全链路静默降级 | 公告属增强信息，不得打扰用户 |

## Rollback

纯增量：新增 2 个后端文件 + 3 处小改 + 2 个前端文件 + 1 处 Vue 改动。回滚即 revert 对应提交，无数据迁移、无 schema 变更。
