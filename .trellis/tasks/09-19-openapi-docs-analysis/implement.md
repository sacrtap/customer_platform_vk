# Implement — 基于 VitePress 的开放平台开发者文档站

## 执行清单

### 阶段 A：VitePress 独立工程搭建
- [ ] A1. 创建 `openapi-docs/package.json`（依赖仅 `vitepress`，scripts: `docs:dev` / `docs:build`）
- [ ] A2. 编写 `openapi-docs/.vitepress/config.ts`：`base: '/openapi/'`、标题/描述、nav + sidebar（guides / api-reference）
- [ ] A3. 编写首页 `docs/index.md`（平台概述、API 输出为主、快速入口）
- [ ] A4. `npm install && npm run docs:build` 本地验证构建成功

### 阶段 B：文档内容写作
- [ ] B1. `guides/getting-started.md`：API 基础路径、统一响应结构 `{code,message,data}`、通用约定
- [ ] B2. `guides/authentication.md`：API-Key 获取（系统管理→API-Key 管理页）、`Authorization: Bearer` 传递、状态含义（启用/停用/过期/删除）、安全提示、curl/Python 示例
- [ ] B3. `guides/error-codes.md`：错误码表（0/40004/40104/40105/50000）与错误响应示例
- [ ] B4. `api-reference/index.md`：API 索引（预留扩展结构说明）
- [ ] B5. `api-reference/erp-balances.md`：GET /api/v1/erp/balances 完整页面（描述/参数/curl+Python 示例/响应示例/渠道编码对照表/错误码）
- [ ] B6. 渠道编码对照表：从 `backend` ERP 系统数据组织静态表（与 OpenApiGuide.vue 现有 FALLBACK 列表一致）

### 阶段 C：移除旧页面
- [ ] C1. 删除 `frontend/src/views/OpenApiGuide.vue`
- [ ] C2. 删除 `frontend/src/router/index.ts` 中 `/openapi` 路由（`name: 'OpenApiGuide'`）
- [ ] C3. 检索 `OpenApiGuide` / `openapi` 残留引用（grep + codegraph），清理测试/导入

### 阶段 D：部署集成
- [ ] D1. 修改 `deploy/docker/frontend.Containerfile`：builder 阶段追加 openapi-docs 构建；阶段 2 COPY 产物到 `/usr/share/nginx/html/openapi`
- [ ] D2. 修改 `deploy/docker/frontend-nginx.conf`：新增 `location /openapi/`（try_files + expires 1h），注意与静态缓存规则顺序

### 阶段 E：验证与收尾
- [ ] E1. 本地构建 openapi-docs 产物，检查 `/openapi/` base 资源路径正确
- [ ] E2. 后端 API 不动；确认 `GET /api/v1/erp/balances` 文档与 `backend/app/routes/openapi.py` 实现一致
- [ ] E3. 前端 `npm run build`（或 CI）通过，确认删除 OpenApiGuide.vue 后无引用错误
- [ ] E4. `task.py validate` 通过；提交并推送分支；创建 PR

## 验证命令

```bash
cd openapi-docs && npm run docs:build        # 阶段 A/E1
cd frontend && npx vue-tsc --noEmit          # 阶段 E3 类型检查
python3 .trellis/scripts/task.py validate 09-19-openapi-docs-analysis
```

## 不涉及范围

- 不改动后端 `openapi_bp` / `_authenticate_api_key` / `api_keys_bp`（认证与管理功能已完备）
- 不新增后端 API（本期仅文档化现有 balances 接口）
- 不改动 `deploy/scripts/deploy.sh`（镜像流程无需变化）
