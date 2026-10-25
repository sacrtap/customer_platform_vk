# 系统升级自动公告提示

## Context

用户登录后，自动弹框提示系统近期 deploy 相关的更新。数据来源已确认：仓库 `sacrtap/customer_platform_vk` **没有 GitHub Releases**，部署靠手动触发的 `Deploy` workflow（`workflow_dispatch` → staging/production）。因此「deploy 更新」取 **Deploy workflow runs** 的成功运行，每次更新的「摘要」取**该次部署相对上一次部署之间的全部提交**（GitHub compare API），更新时间取部署触发时间。

经确认的取舍（用户已选）：
- **触发**：仅当存在用户未看过的新部署时弹（localStorage 记已读，避免每次登录打扰）。
- **摘要口径**：两次部署间全部提交（compare API），信息全、文案较杂，靠弹框固定高度+滚动承载。
- **过滤**：仅 `conclusion=success` 的部署。
- **GitHub 鉴权**：暂不配 Token，走匿名请求（60/h），靠后端 Redis 缓存兜底。

技术栈已核实：后端 Sanic 24.12 + SQLAlchemy 2.0 async + httpx 0.28 + Redis；前端 Vue 3.4 + Arco Design Vue 2.54 + axios + pinia。

## Approach

### 后端

#### 1. 配置字段 — `backend/app/config.py`
在 `Settings` 类「外部 API 配置」块之后（`external_api_token` 行，约 `config.py:63` 之后）新增：
```python
    # GitHub 部署公告配置
    github_repo: str = "sacrtap/customer_platform_vk"  # 读取部署更新的仓库
    github_token: str = ""  # 可选；留空走匿名请求（60/h，靠缓存兜底）
    github_workflow_file: str = "deploy.yml"  # 部署 workflow 文件名
```
pydantic-settings 自动映射环境变量 `GITHUB_REPO` / `GITHUB_TOKEN` / `GITHUB_WORKFLOW_FILE`。默认值即本仓库，无需 .env 即可运行。

同步在项目根 `.env.example` 增补（注释说明，Token 默认空）：
```
# GitHub 部署公告（留空走匿名请求，60/h）
GITHUB_REPO=sacrtap/customer_platform_vk
GITHUB_TOKEN=
GITHUB_WORKFLOW_FILE=deploy.yml
```

#### 2. 缓存 TTL 登记 — `backend/app/cache/base.py`
在 `CacheService.__init__` 的 `_ttl_config` 字典中（`base.py:33-52`），`"default": 300,` 行之前新增：
```python
            "system_updates": 600,  # 10 分钟（GitHub 部署更新摘要，匿名 60/h 限流兜底）
```
登记后 `cache_service.set("system_updates", data)` 自动取 600s TTL（`set` 签名 `set(prefix, data, *parts, ttl=None)`，`ttl=None` 走 `ttl_for(prefix)`）。Redis 不可用时 `CacheService` 自动降级返回 None（不抛异常），路由静默降级为实时拉取/空数据。

#### 3. GitHub 客户端服务 — 新建 `backend/app/services/github_updates.py`
仿 `backend/app/services/external_api.py` 的 `ExternalAPIClient` 模式（类 + 全局单例 + 工厂函数；`async with httpx.AsyncClient(timeout=...) as client:`；`httpx.HTTPError` 吞异常记 error 日志返回 None）。无等价现有客户端（仓库无任何 GitHub API 调用代码），故新建。

GitHub API 返回结构已真实验证：
- workflow runs：`GET /repos/{repo}/actions/workflows/{workflow_file}/runs?per_page={n}` → `workflow_runs[]`，每项含 `head_sha`/`created_at`/`html_url`/`status`/`conclusion`/`head_commit`。（`deploy.yml` 作为 workflow_id 已验证可用。）
- compare：`GET /repos/{repo}/compare/{base}...{head}` → `status`(`ahead`/`identical`)/`total_commits`/`commits[]`，每项含 `sha`/`commit.message`/`commit.author.name`/`commit.author.date`。（真实两次部署间返回 28 条提交。）

核心实现：
```python
"""GitHub 部署更新客户端 - 读取 Deploy workflow 最近部署摘要"""
import logging
from typing import Any, Dict, List, Optional
import httpx
from ..config import settings

logger = logging.getLogger(__name__)

class GitHubUpdatesClient:
    def __init__(self):
        self.repo = settings.github_repo
        self.token = settings.github_token or None
        self.workflow_file = settings.github_workflow_file
        self.timeout = 15.0
        self.base = "https://api.github.com"

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def _get(self, path: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(f"{self.base}{path}", headers=self._headers())
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
        except httpx.HTTPError as e:
            logger.error(f"GitHub API 请求失败 {path}: {e}")
            return None

    async def get_recent_updates(self, count: int = 3) -> List[Dict[str, Any]]:
        # 需要 count 次成功部署 + 1 条前序基线做 compare；多取几条以过滤成功
        runs_json = await self._get(
            f"/repos/{self.repo}/actions/workflows/{self.workflow_file}/runs?per_page={count + 5}"
        )
        if not runs_json or not runs_json.get("workflow_runs"):
            return []
        succ = [
            r for r in runs_json["workflow_runs"]
            if r.get("status") == "completed" and r.get("conclusion") == "success"
        ]
        if not succ:
            return []
        updates: List[Dict[str, Any]] = []
        for i in range(min(count, len(succ))):
            run = succ[i]
            commits: List[Dict[str, str]] = []
            if i + 1 < len(succ):
                # 本次部署相对上次部署的新增提交
                cmp = await self._get(
                    f"/repos/{self.repo}/compare/{succ[i+1]['head_sha']}...{run['head_sha']}"
                )
                if cmp and cmp.get("commits"):
                    commits = [
                        {
                            "sha": c["sha"][:7],
                            "message": (c.get("commit", {}).get("message", "") or "").split("\n")[0],
                            "author": (c.get("commit", {}).get("author", {}) or {}).get("name", ""),
                            "date": (c.get("commit", {}).get("author", {}) or {}).get("date", ""),
                        }
                        for c in cmp["commits"]
                    ]
            else:
                # 最旧的可见部署无前序基线：回退用 head_commit 作单条摘要
                hc = run.get("head_commit") or {}
                msg = (hc.get("message", "") or "").split("\n")[0]
                if msg:
                    commits = [{
                        "sha": run["head_sha"][:7], "message": msg,
                        "author": (hc.get("author", {}) or {}).get("name", ""),
                        "date": run.get("created_at", ""),
                    }]
            updates.append({
                "deployed_at": run["created_at"],          # ISO UTC，前端按词法比较已读
                "head_sha": run["head_sha"][:7],
                "status": "success",
                "html_url": run.get("html_url", ""),
                "commits": commits,
            })
        return updates

github_updates_client = GitHubUpdatesClient()

def get_github_updates_client() -> GitHubUpdatesClient:
    return github_updates_client
```

错误/边界处理（已在上述代码中体现）：GitHub 不可达 / 限流 403 → `_get` 返回 None → `get_recent_updates` 返回 `[]`；compare 相同 SHA（`status=identical`，重新部署）→ `commits` 为空列表；成功部署不足 count → 返回实际可得的若干条；最旧部署无基线 → 回退 head_commit 单条。

#### 4. 路由 — 新建 `backend/app/routes/system.py`
仿 `backend/app/routes/roles.py:1-19` 的写法（`from sanic import Blueprint` / `from sanic.request import Request` / `from sanic.response import json` / 相对导入 `from ..middleware.auth import auth_required`）。无现有 `system` 路由（已核实 `routes/` 目录无 system.py），`url_prefix="/api/v1/system"` 无冲突。本接口只读不落库，无需 `db_session`/事务；登录即可见，只用 `@auth_required`（不加 `require_permission`）。
```python
# -*- coding: utf-8 -*-
"""系统公告路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json

from ..middleware.auth import auth_required
from ..services.github_updates import get_github_updates_client
from ..cache.base import cache_service

system_bp = Blueprint("system", url_prefix="/api/v1/system")


@system_bp.get("/updates")
@auth_required
async def get_system_updates(request: Request):
    """获取最近 3 次部署更新摘要（仅成功部署，含两次部署间全部提交）"""
    cached = await cache_service.get("system_updates")
    if cached is not None:
        return json({"code": 0, "message": "success", "data": {"updates": cached}})
    client = get_github_updates_client()
    updates = await client.get_recent_updates(3)
    # 仅缓存非空结果：空（GitHub 不可达/限流）不落缓存，下次请求可重试
    if updates:
        await cache_service.set("system_updates", updates)
    return json({"code": 0, "message": "success", "data": {"updates": updates}})
```
响应信封 `{code, message, data}` 与全站一致；前端响应拦截器解包后 `res.data.updates` 即负载。

#### 5. 注册蓝图 — `backend/app/main.py`
在 `create_app()` 的路由蓝图块：
- import 块（`main.py:272-292`，按字母序）在 `sync_tasks` 与 `tags` 之间新增：`from .routes.system import system_bp`
- `app.blueprint(...)` 块（`main.py:294-317`）末尾（`app.blueprint(openapi_customer_bp)` 之后）新增：`app.blueprint(system_bp)`

### 前端

#### 6. API 模块 — 新建 `frontend/src/api/system.ts`
仿 `frontend/src/api/billing.ts:1`（`import api from './index'`，默认导出的共享 axios 实例，baseURL `/api/v1`）。
```ts
import api from './index'

export interface DeployCommit {
  sha: string
  message: string
  author: string
  date: string
}

export interface DeployUpdate {
  deployed_at: string
  head_sha: string
  status: string
  html_url: string
  commits: DeployCommit[]
}

export function getSystemUpdates() {
  return api.get('/system/updates')
}
```
返回的是响应拦截器解包后的整个信封，调用方取 `res.data.updates`（与 `Login.vue:250` `res.data.access_token` 一致）。

#### 7. 弹框组件 — 新建 `frontend/src/components/system/UpgradeAnnouncementModal.vue`
基于 Arco `a-modal`，固定高度 + 滚动（仿 `frontend/src/views/customers/detail/EditCustomerDialog.vue:8` 的 `:body-style="{ height: '...px', overflowY: 'auto' }"`)。`v-model:visible`（仿 `DiscountApprovalModal.vue` 的 `v-model:visible` 简单用法）。

契约：
- props：`updates: DeployUpdate[]`
- `v-model:visible`
- `:mask-closable="false"`（防误触，必须手动点按钮/关闭）—— 满足「允许用户手动关闭」且不误关
- `:width="600"`
- header：`#title` 插槽 = Arco 图标（`IconArrowRise`，不存在则用 `IconSync`）+ 标题「系统升级公告」+ 副标题「系统近期完成了 N 次部署更新」
- body：`:body-style="{ height: '440px', overflowY: 'auto', padding: '16px 20px' }"`；按 `updates` 渲染时间轴式部署块，每块含：
  - 头行：部署时间（CST 格式 `YYYY-MM-DD HH:mm`）+「部署成功」绿色徽标 + 提交数「共 N 条提交」
  - 提交列表：每条一行 = 灰色短 sha + 提交标题（`message`，单行省略）+ 作者/时间（muted）
  - 同一部署块的提交用竖线/缩进区分；块间留分隔
- footer：`#footer` 插槽 = 右对齐两个按钮：`<a-button @click="openGitHub">在 GitHub 查看完整记录</a-button>`（`window.open(updates[0].html_url)`）+ `<a-button type="primary" @click="handleClose">我知道了</a-button>`
- 关闭路径：右上角 Arco 内置 ✕（`closable` 默认 true）与「我知道了」按钮均可关；两路都 emit `close`
- `handleClose()`：`emit('update:visible', false); emit('close')`
- 时间格式化内联（无需外部依赖）：
  ```ts
  const fmtCST = (iso: string) =>
    new Date(iso).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
  ```
- 空状态：`updates` 为空时不渲染列表（父级已控制不显示）

#### 8. 挂载与「已读」逻辑 — `frontend/src/views/Dashboard.vue`
`Dashboard.vue` 是 `/` 路由 Layout 根组件，`onMounted` 覆盖全部登录入口（新登录 + 已登录刷新 + 已登录访问 `/login` 被守卫重定向回 `/`，`force:true` 会重新渲染 Dashboard）。

模板（在修改密码 `a-modal` 之后，`.main` 的 `</div>` 之前，约 `Dashboard.vue:73` 之后插入）：
```vue
<UpgradeAnnouncementModal
  v-model:visible="upgradeVisible"
  :updates="upgradeUpdates"
  @close="handleUpgradeClose"
/>
```
script（`Dashboard.vue:79` `import { ref, reactive } from 'vue'` → 改为 `import { ref, reactive, onMounted } from 'vue'`）：
```ts
import { onMounted } from 'vue'  // 并入第 79 行现有 vue 导入
import { useUserStore } from '@/stores/user'
import { getSystemUpdates, type DeployUpdate } from '@/api/system'
import UpgradeAnnouncementModal from '@/components/system/UpgradeAnnouncementModal.vue'

const userStore = useUserStore()
const upgradeVisible = ref(false)
const upgradeUpdates = ref<DeployUpdate[]>([])

onMounted(async () => {
  const uid = userStore.userInfo?.id
  if (!uid) return
  try {
    const res = await getSystemUpdates()
    const updates: DeployUpdate[] = res.data?.updates || []
    if (!updates.length) return
    const READ_KEY = `upgrade_announcement_last_read_${uid}`
    const lastRead = localStorage.getItem(READ_KEY)
    const latest = updates[0].deployed_at  // ISO UTC，词法可比较
    if (lastRead !== latest && (!lastRead || latest > lastRead)) {
      upgradeUpdates.value = updates
      upgradeVisible.value = true
    }
  } catch {
    // 接口失败静默：不打扰用户
  }
})

const handleUpgradeClose = () => {
  const uid = userStore.userInfo?.id
  if (uid && upgradeUpdates.value.length) {
    localStorage.setItem(
      `upgrade_announcement_last_read_${uid}`,
      upgradeUpdates.value[0].deployed_at,
    )
  }
  upgradeVisible.value = false
}
```
「已读」按用户维度（`userInfo.id`）记最近一次展示的部署时间；同 ISO UTC 字符串词法比较判定「未读」。关弹即写入，下次登录/刷新无新部署则不弹。

### 测试

#### 9. 后端单元测试 — 新建 `backend/tests/` 下对应测试（按现有后端测试约定）
为 `GitHubUpdatesClient.get_recent_updates` 写 mocked httpx 用例（行为定义型，覆盖消费者可见边界；遵循 `backend/tests/` 现有 mock httpx 约定，不引入新框架）：
- 正常：mock runs 返回 4 条成功（含 head_commit）+ mock 3 次 compare 返回 commits[] → 断言得到 3 条 update，每条 commits 来自对应 compare，时间/head_sha/html_url 正确透传。
- compare 相同 SHA（`status=identical`、`commits=[]`）→ 该部署 `commits` 为空列表，不报错。
- 成功部署不足 count（仅 1 条）→ 返回 1 条，回退用 head_commit 单条摘要。
- GitHub 不可达/限流（`_get` 全返回 None）→ 返回 `[]`。

路由层不单独 mock（服务层已覆盖）；如现有测试有 Sanic test_client 约定可补一条 `/api/v1/system/updates` 带 token 返回 200 + `data.updates` 的集成断言（可选）。

## Critical files & anchors

- `backend/app/services/github_updates.py` — 新建；GitHub workflow runs + compare 拉取与汇总逻辑核心
- `backend/app/routes/system.py` — 新建；`/api/v1/system/updates` 路由 + 缓存包装（仿 `roles.py:1-19`）
- `backend/app/main.py:272-317` — 蓝图 import 与 `app.blueprint()` 注册块，新增 system_bp 两处
- `backend/app/config.py:63` 之后 / `backend/app/cache/base.py:51` — 配置字段与 TTL 登记点
- `frontend/src/views/Dashboard.vue:73,79` — 弹框挂载点与 `onMounted` 注入点（覆盖全部登录入口）

## Verification

前提：后端 Sanic 运行于 `127.0.0.1:8000`（`/api` 经 vite 代理转发），Redis 可用（缓存生效；不可用也降级可用）。

**后端端到端**（证明数据链路）：
```bash
# 取一个有效 JWT（登录接口）后：
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"<管理员账号>","password":"<密码>"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
curl -s http://127.0.0.1:8000/api/v1/system/updates -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
预期：`code=0`，`data.updates` 为长度 ≤3 的数组，每项含 `deployed_at`(ISO UTC)、`status:"success"`、`html_url`、`commits[]`（每项 `sha`/`message`/`author`/`date`）；最近一条对应仓库最新成功 Deploy 运行。第二次请求应命中缓存（响应内容一致；可观察后端无新 GitHub 出站请求）。

**前端端到端**（证明交互与已读）：
1. `make dev-frontend`（或 `cd frontend && npm run dev`），浏览器登录 → 进入首页后自动弹出「系统升级公告」弹框，列表展示 3 次部署、每次部署下展开其提交列表，超出区域可滚动（固定高度 440px + 滚动条）。
2. 点「我知道了」或右上角 ✕ → 弹框关闭。
3. 刷新页面 / 重新登录 → **不再弹**（localStorage 已记已读）。
4. 浏览器清空 `upgrade_announcement_last_read_*` → 重新登录 → 弹框再次出现。
5. 后端停掉或断网（接口失败）→ 登录后**不弹**、不报错（静默降级）。

**后端单元测试**：`cd backend && python -m pytest tests/<新建测试文件> -v` 全绿，覆盖第 9 步 4 个用例。

## Assumptions & contingencies

- **匿名限流 60/h**：假设内部用户规模小 + 10 分钟缓存足以兜底。若现实出现 403 限流，`_get` 返回 None → 接口返回空 `updates` → 前端静默不弹（不报错）。后续可在 `.env` 设 `GITHUB_TOKEN` 即提升至 5000/h，无需改代码。
- **compare 提交数量大**：真实两次部署间有 28 条提交（含 `chore(trellis)` 归档/journal 噪声）。按用户选择的「全部提交」展示，不过滤；固定高度+滚动承载。若后续需降噪，可在 `get_recent_updates` 对 `message` 前缀（`chore(trellis)`/`chore: record journal`）过滤——本次不做（用户已选全部）。
- **成功部署不足 3 次**：返回实际可得条数；最旧一条无前序基线时回退用 head_commit 单条摘要，不报错。
- **「已读」按浏览器+用户维度**：同一浏览器不同用户各自记已读（key 含 `userInfo.id`）。若希望「同浏览器一次关闭后任何用户都不再弹」，改为不含 uid 的 key 即可——当前选择更贴合「每个用户至少看一次未读部署」语义。
