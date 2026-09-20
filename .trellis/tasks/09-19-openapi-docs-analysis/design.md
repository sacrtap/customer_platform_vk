# Design — 基于 VitePress 的开放平台开发者文档站

## 1. 边界与选址

- 仓库内新建独立工程目录 `openapi-docs/`（用户已确认）：拥有独立 `package.json`，依赖仅 `vitepress`，与 `frontend/` 互不干扰。
- 目标部署路径：`https://<host>/openapi/`（staging 为 `customer-staging.jiazoushi.com`），VitePress `base: '/openapi/'`。
- 本期文档内容仅覆盖现有 API：`GET /api/v1/erp/balances`（用户已确认：仅现有接口 + api-reference 预留扩展结构）。
- 旧页面 `frontend/src/views/OpenApiGuide.vue` 及其 `/openapi` 路由**彻底删除**（用户已确认），`/openapi` 由 VitePress 静态产物接管。

## 2. 站点结构

```
openapi-docs/
├── package.json            # 仅依赖 vitepress
├── .vitepress/
│   └── config.ts           # base: '/openapi/'；导航、侧边栏、主题配置
└── docs/
    ├── index.md            # 首页/平台概述（API 输出为主，简介 + 快速入口）
    ├── guides/
    │   ├── getting-started.md   # 快速开始：API 基础路径、通用响应结构
    │   ├── authentication.md    # 认证：API-Key 获取（系统管理→API-Key）、传递方式、状态含义、安全注意
    │   └── error-codes.md       # 错误码说明（0/40004/40104/40105/50000 等）
    └── api-reference/
        ├── index.md        # API 索引（预留扩展结构，未来接口在此加页）
        └── erp-balances.md # GET /api/v1/erp/balances 单接口页
```

导航（`config.ts`）：
- **指南 Guides**：快速开始 / 认证 / 错误码
- **API 参考 API Reference**：按接口分页（每页模板：接口描述、请求参数表、请求示例 curl/Python、响应示例、错误码、渠道编码对照）

每接口页内容模板：
1. 接口描述 + 业务场景
2. 端点（方法 + 路径 + 认证要求）
3. 请求参数表（名称/位置/类型/必填/说明）
4. 请求示例（curl + Python requests）
5. 响应示例（JSON，成功 + 失败）
6. 错误码（本接口可能返回的）
7. 附注（渠道编码对照表等）

## 3. 认证方案（API-Key 管理）

- 文档明确说明：所有 API 使用 API-Key 认证，传递方式 `Authorization: Bearer {api_key}`。
- Key 获取流程：登录客户运营中台 → 系统管理 → **API-Key 管理**页面 → 创建（命名 + 可选描述/过期时间）→ 创建后仅展示一次完整明文（`vk_` 前缀），需立即保存。
- Key 状态含义：启用（可调用）/ 停用（40104 拒绝，可在页面重新启用）/ 过期（40105 拒绝）/ 删除（永久失效）。
- 安全提示：Key 只在创建时展示一次；勿提交到 Git/前端代码/日志；疑似泄露立即停用并重建。
- 后端证据：`backend/app/middleware/auth.py::_authenticate_api_key`（Bearer 校验，40104/40105）；`backend/app/routes/api_keys.py`（管理端点，权限 `api_keys:manage`）；`frontend/src/views/system/ApiKeyManagement.vue`（管理页面）。

## 4. 移除旧页面

- 删除 `frontend/src/views/OpenApiGuide.vue`。
- 删除 `frontend/src/router/index.ts` 中 `/openapi` 路由项（`name: 'OpenApiGuide'`）。
- 检查 `OpenApiGuide` / `openapi` 其它引用（如测试、导入），一并清理。
- 前端 SPA 不再承载 `/openapi`，nginx 层接管。

## 5. 部署方案

沿用现有 Docker 多阶段构建（`deploy/docker/frontend.Containerfile`），扩展为构建两个前端产物：

```
阶段 1 (builder, node:22-alpine):
  a. npm ci + vite build（frontend/ → dist）——现有逻辑
  b. cd openapi-docs && npm ci && npm run build（→ openapi-docs/.vitepress/dist）
阶段 2 (nginx:alpine):
  COPY --from=builder /build/dist /usr/share/nginx/html
  COPY --from=builder /build/openapi-docs/.vitepress/dist /usr/share/nginx/html/openapi
  COPY deploy/docker/frontend-nginx.conf /etc/nginx/conf.d/default.conf
```

nginx 配置（`frontend-nginx.conf` 修改）：
```nginx
# VitePress 开放平台文档站（纯静态，无需 SPA fallback）
location /openapi/ {
    try_files $uri $uri/ /openapi/index.html;
    expires 1h;
}
```
注意：VitePress 以 `base: '/openapi/'` 构建后，资源引用为 `/openapi/assets/*`，与 SPA 的 `location /`（`try_files ... /index.html`）不冲突；但需保证 `location /openapi/` 位于通用静态缓存规则之前（或排除），避免 `expires 1y` 对文档页造成长期缓存。

nginx location 顺序要点：
- `location /openapi/` 精确前缀优先于 `location /`。
- 静态资源缓存规则 `~* \.(js|css|...)$` 会命中 `/openapi/assets/*`——文档站 assets 带 hash，`expires 1y` 可接受；文档 HTML 由 `location /openapi/` 控制 `expires 1h`。

CI/CD：现有 GitHub Actions 构建 frontend 镜像的流程不变（`frontend.Containerfile` 自动包含 openapi-docs 构建）；部署脚本 `deploy/scripts/deploy.sh` 无需改动（仍走镜像拉取）。

## 6. 文档维护流程

- API 变更时：更新 `openapi-docs/docs/api-reference/*.md` → 本地 `npm run docs:dev` 预览 → 提交 → CI 构建镜像自动包含新文档。
- 新增 API：在 `api-reference/` 新建 md 页 + 更新 `index.md` 索引 + 按页面模板写作。
- 文档与代码同仓库同 PR，保证接口文档与实现同步演进。

## 7. 本地开发

```bash
cd openapi-docs
npm install
npm run docs:dev   # 本地预览 http://localhost:5173/openapi/
npm run docs:build # 产物 .vitepress/dist（base 已为 /openapi/）
```

## 8. 验收映射

| AC | 验证方式 |
|---|---|
| AC1 API 清单 | 本 design + prd 已列（来源 `backend/app/routes/openapi.py`） |
| AC2 VitePress 可构建 | `npm run docs:build` 成功，产物含 `/openapi/` base 资源 |
| AC3 站点结构 | 目录/导航/模板按 §2 落地 |
| AC4 认证章节 | authentication.md 覆盖获取/传递/状态/安全，curl+Python 示例 |
| AC5 旧页移除 + nginx | OpenApiGuide.vue 与路由删除；nginx 配置含 `/openapi/` location |
| AC6 validate | `task.py validate` 通过 |

## 9. 风险与兼容

- 风险：VitePress 版本与 Node 22 兼容性——选用 LTS 版本 vitepress，容器内 `npm ci` 锁定。
- 兼容：`/openapi` 不带尾斜杠时 nginx `location /openapi/` 会 301 重定向到 `/openapi/`，行为可接受（原 SPA 路由不受影响）。
- 旧书签/外链 `https://host/openapi`（无尾斜杠）由 nginx 自动重定向，无需额外处理。
