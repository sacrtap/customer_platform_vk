# VitePress 文档站 + CI 路径过滤 经验指南

> 沉淀自 PR #27（openapi-docs-analysis）：基于 VitePress 搭建开放平台文档站、修复 PR checks 集成测试超时的过程。

---

## 1. VitePress 独立文档站工程约定

仓库内文档站（`openapi-docs/`）是独立 VitePress 工程，与主前端 `frontend/` 隔离。构建与部署时注意：

### Gotcha: `.vitepress/` 必须位于构建 root 内

`vitepress build docs` 以 `docs/` 作为 root，**配置文件必须放在 `docs/.vitepress/config.ts`**。

- 若放在工程根 `openapi-docs/.vitepress/config.ts`，配置**不会被加载**（静默失效），导致 `base` 不生效：
  - 产物资源路径错误：`/assets/*.js` 而非 `/openapi/assets/*.js`
  - 部署后文档站资源 404（nginx 无法在 `/openapi/` 下找到资源）
- 症状排查：构建成功后 grep `dist/index.html` 的 `src`/`href`，若为 `/assets/` 而非 `/openapi/assets/`，即为配置未加载。

**正确结构**：

```
openapi-docs/
├── package.json            # scripts: docs:dev / docs:build / docs:preview
├── docs/
│   ├── .vitepress/
│   │   └── config.ts       # ← 必须在此
│   ├── index.md
│   ├── guides/*.md
│   ├── api-reference/*.md
│   └── public/logo.svg
```

### base 与 logo 路径

- `config.ts` 顶层设置 `base: '/openapi/'`（部署路径）。
- **logo 不要重复加 base**：`themeConfig.logo: '/logo.svg'`，VitePress 会自动拼 base 成 `/openapi/logo.svg`；若写 `/openapi/logo.svg` 会双重前缀 `/openapi/openapi/logo.svg`。

### nginx 配合（cleanUrls）

`cleanUrls: true` 时产物文件仍是 `*.html`（如 `getting-started.html`），但站内链接不带扩展名（`/guides/getting-started`）。nginx 需 `$uri.html` 探试：

```nginx
location /openapi/ {
    try_files $uri $uri.html $uri/ /openapi/index.html;
    expires 1h;
}
location = /openapi {
    return 301 /openapi/;
}
```

### Docker 集成

`frontend.Containerfile` builder 阶段追加 openapi-docs 构建，产物 COPY 到 nginx 目录：

```dockerfile
WORKDIR /build/openapi-docs
COPY openapi-docs/package*.json ./
RUN npm ci
COPY openapi-docs/ ./
RUN npm run docs:build
# 阶段 2:
COPY --from=builder /build/openapi-docs/docs/.vitepress/dist /usr/share/nginx/html/openapi
```

---

## 2. CI：按变更路径过滤重型测试（paths-filter 模式）

**问题**：`backend-integration-tests`（真实 Postgres + Redis 全链路，~251 用例）耗时约 44 分钟，`timeout-minutes: 45` 贴边超时被取消 → 即便测试全过也显示 `cancelled` → PR Quality Gate 连锁失败。

**修复**：用 `dorny/paths-filter@v3`（仓库 migration-gate 已有同款先例）仅在后端代码变更时运行：

```yaml
backend-integration-tests:
  timeout-minutes: 60   # 提高余量
  steps:
    - uses: actions/checkout@v4
      with: { fetch-depth: 0 }
    - id: changes
      uses: dorny/paths-filter@v3
      with:
        filters: |
          backend:
            - 'backend/**'
        base: ${{ github.event.pull_request.base.sha || github.event.before }}
    - name: Skip when no backend changes
      if: steps.changes.outputs.backend == 'false'
      run: echo "✅ 无后端变更，跳过集成测试"
    # 后续步骤全部加: if: steps.changes.outputs.backend == 'true'
```

要点：
- 纯前端/文档 PR 秒级跳过（本例 45 分钟 → 39 秒），job 仍为 `success`，Quality Gate 不受影响。
- `fetch-depth: 0` 是 paths-filter 计算 diff 的前提，勿省。
- 提高 `timeout-minutes` 给真实后端 PR 的完整套件留余量。

### Gotcha: gate 失败时 acceptance record 上传报错

`pr-quality-gate` 的 `Upload acceptance record` 步骤 `if: always()`，但其 `path` 引用前一步 `Write acceptance record` 的输出；该步默认 `if: success()`，gate 失败（exit 1）时被跳过 → `path` 为空 → `Input required and not supplied: path`。

**修复**：`Write acceptance record` 加 `if: always()`，失败时也写验收记录。

---

## Checklist

- [ ] 新增 VitePress 文档站时，config 放在 `docs/.vitepress/`，构建后 grep 产物验证 base 生效
- [ ] logo 路径不加 base 前缀
- [ ] nginx 为 cleanUrls 文档站加 `$uri.html` 探试 + 无尾斜杠 301
- [ ] 重型 CI 测试（>15 分钟）加 paths-filter 按变更路径跳过，`fetch-depth: 0`，并提高 timeout 余量
- [ ] Quality Gate 中引用前步输出的步骤，来源步骤记得 `if: always()`
