# 系统升级自动公告提示 — PRD

## Goal

用户登录后，若存在其未看过的新部署，自动弹框提示系统近期部署更新。数据源为 GitHub 仓库 `sacrtap/customer_platform_vk` 的 **Deploy workflow 成功运行**；每次更新的摘要取**该次部署相对上一次部署之间的全部提交**（compare API），更新时间取部署触发时间（`created_at`）。

## Background

- 仓库没有 GitHub Releases，部署靠手动触发的 `Deploy` workflow（`workflow_dispatch` → staging/production），因此「deploy 更新」= Deploy workflow 的成功运行。
- 技术栈：后端 Sanic 24.12 + SQLAlchemy 2.0 async + httpx 0.28 + Redis；前端 Vue 3.4 + Arco Design Vue 2.54 + axios + pinia。

## Requirements

1. **触发**：仅当存在用户未看过的新部署时弹框（localStorage 记已读，避免每次登录打扰）。
2. **摘要口径**：两次部署间全部提交（compare API），不过滤 `chore(trellis)` 等噪声；固定高度弹框 + 滚动承载。
3. **过滤**：仅 `conclusion=success` 的部署；展示最近 3 次。
4. **鉴权**：接口登录即可访问（`@auth_required`，不加 `require_permission`）；GitHub 侧暂不配 Token，走匿名请求（60/h），靠后端 Redis 缓存兜底。
5. **降级**：GitHub 不可达 / 限流 / Redis 不可用均不得导致用户可见错误——接口返回空数组，前端静默不弹。

## Acceptance Criteria

- [ ] AC1 `GET /api/v1/system/updates`（带有效 JWT）返回 `{code:0, data:{updates:[...]}}`，长度 ≤3，每项含 `deployed_at`(ISO UTC)、`head_sha`(7位)、`status:"success"`、`html_url`、`commits[]`（每项 `sha`/`message`/`author`/`date`）。
- [ ] AC2 每条 update 的 `commits` 对应该次部署相对上一次成功部署的新增提交；最旧一条无前序基线时回退为 `head_commit` 单条摘要；compare 为 identical 时为 `[]` 且不报错。
- [ ] AC3 未认证请求该接口返回 401；响应信封 `{code,message,data}` 与全站一致。
- [ ] AC4 同一数据第二次请求命中 Redis 缓存（TTL 600s），无新 GitHub 出站请求；缓存不缓存空结果（失败可重试）。
- [ ] AC5 后端单元测试覆盖 4 个用例：正常 3 条 + commits 透传；identical compare → `[]`；成功部署仅 1 条 → 回退单条；GitHub 不可达 → `[]`。
- [ ] AC6 前端：登录进入首页后自动弹出「系统升级公告」弹框，600px 宽、body 固定 440px 高度可滚动，展示 ≤3 次部署块，每块含时间（CST）+「部署成功」徽标 + 提交数 + 提交列表（短 sha + 标题 + 作者/时间）。
- [ ] AC7 关闭路径：「我知道了」按钮与右上角 ✕ 均可关，均 emit `close`；关闭后写入 localStorage（key 含用户 id）。
- [ ] AC8 已读语义：刷新 / 重新登录，无新部署时不再弹；清空 localStorage key 后再次出现；接口失败时静默不弹不报错。
- [ ] AC9 质量门禁：`cd backend && ruff check app/ tests/`、`python -m pytest tests/ -q` 相关测试全绿、`pyright` 0 error；`cd frontend && pnpm type-check` 通过。

## Constraints

- Python 3.12.x；所有 API 加 `@auth_required`；本接口只读不落库，无事务。
- 新增配置走 pydantic-settings 环境变量映射，默认值即本仓库，无需 `.env` 即可运行。
- 前端不直接调 axios，必须经 `@/api/system`；不用 `any`。

## Non-Goals

- 不做提交消息降噪过滤（用户已选全部提交展示）。
- 不配 GitHub Token（默认匿名 + 缓存兜底；需要时 `.env` 设 `GITHUB_TOKEN` 即提升至 5000/h）。
- 不改前端路由/导航，弹框只挂载在 `Dashboard.vue`。
