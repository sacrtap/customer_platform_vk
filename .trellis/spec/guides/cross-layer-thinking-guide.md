# Cross-Layer Thinking Guide

> **Purpose**: Think through data flow across layers before implementing.

---

## The Problem

**Most bugs happen at layer boundaries**, not within layers.

Common cross-layer bugs:

- API returns format A, frontend expects format B
- Database stores X, service transforms to Y, but loses data
- Multiple layers implement the same logic differently

---

## Before Implementing Cross-Layer Features

### Step 1: Map the Data Flow

Draw out how data moves:

```
Source → Transform → Store → Retrieve → Transform → Display
```

For each arrow, ask:

- What format is the data in?
- What could go wrong?
- Who is responsible for validation?

### Step 2: Identify Boundaries

| Boundary              | Common Issues                     |
| --------------------- | --------------------------------- |
| API ↔ Service         | Type mismatches, missing fields   |
| Service ↔ Database    | Format conversions, null handling |
| Backend ↔ Frontend    | Serialization, date formats       |
| Component ↔ Component | Props shape changes               |

### Step 3: Define Contracts

For each boundary:

- What is the exact input format?
- What is the exact output format?
- What errors can occur?

---

## Common Cross-Layer Mistakes

### Mistake 1: Implicit Format Assumptions

**Bad**: Assuming date format without checking

**Good**: Explicit format conversion at boundaries

### Mistake 2: Scattered Validation

**Bad**: Validating the same thing in multiple layers

**Good**: Validate once at the entry point

### Mistake 3: Leaky Abstractions

**Bad**: Component knows about database schema

**Good**: Each layer only knows its neighbors

### Mistake 4: Every Consumer Parses The Same Payload

**Bad**: A command reads JSONL events and casts fields inline:

```typescript
const thread = (ev as { thread?: string }).thread;
const labels = (ev as { labels?: string[] }).labels;
```

This looks local, but it means every consumer owns a private version of the
event contract. The next field change will update one command and miss another.

**Good**: Decode once at the event boundary, then export typed projections:

```typescript
if (!isThreadEvent(ev)) return false;
return ev.thread === filter.thread;
```

**Rule**: For append-only logs, JSON streams, RPC payloads, or config files,
create one owner for:

- event / payload type definitions
- type guards and normalization from `unknown`
- metadata projections used by UI commands
- reducers that replay state from the source of truth

Rendering code may format fields, but it must not redefine the payload contract.

---

## Checklist for Cross-Layer Features

Before implementation:

- [ ] Mapped the complete data flow
- [ ] Identified all layer boundaries
- [ ] Defined format at each boundary
- [ ] Decided where validation happens

After implementation:

- [ ] Tested with edge cases (null, empty, invalid)
- [ ] Verified error handling at each boundary
- [ ] Checked data survives round-trip
- [ ] Checked that consumers import shared decoders / projections instead of
      casting payload fields locally
- [ ] Checked that derived state points back to the source event identifier
      (`seq`, `id`, `version`) instead of inventing a second cursor

---

## Frontend-Backend Option Consistency

When the backend defines an enum or a fixed set of valid values (e.g., `InvoiceStatus`, `SETTLEMENT_CYCLE_MAP`), every frontend component that renders or filters by that field must support **exactly the same set of values**.

### Checklist: When a backend enum or value set changes

- [ ] Search ALL frontend components that reference this field: `grep -r "field_name" frontend/src/`
- [ ] Update every `statusOptions`, `statusMap`, `getStatusText`, `getStatusTagClass` in all components
- [ ] Verify filter dropdowns include ALL enum values
- [ ] Verify display mappings (text + CSS class) cover ALL enum values
- [ ] If a new status is added to the backend enum, add it to `frontend/src/constants/customerOptions.ts` first, then propagate

### Real-world example (2026-09-11)

Backend `InvoiceStatus` had 8 values (`draft`, `pending_ops`, `pending_sales`, `pending_customer`, `customer_confirmed`, `paid`, `completed`, `cancelled`), but:
- `InvoiceFilters.vue` only had 6 (missing `pending_ops` and `pending_sales`)
- `CustomerInvoicesTab.vue` only had 6 (missing `pending_ops` and `pending_sales`)
- `InvoiceStatusBadge.vue` correctly had all 8

This meant users could not filter by `pending_ops` or `pending_sales` status, and those statuses displayed as raw English text in the customer detail tab.

---

## Semantic Rename Propagation (文案/字段语义重命名)

当把一个**面向用户的术语**改名（如「折扣」→「减免」、「客户」→「账户」），改动几乎从不只在一处。

### Checklist: 术语重命名后必须全栈检索旧词

- [ ] `grep -rn "<旧词>" frontend/src/` — 前端 UI 文案、提示语、表头
- [ ] `grep -rn "<旧词>" backend/app/` — **导出表头、导入模板说明、导入校验错误文案**、日志/审计
- [ ] 检查 `backend/app/routes/**/import-template` 与 `/export` 生成的**列名/说明行**（用户在 Excel 里直接看到）
- [ ] 检查 `backend/scripts/seed.py` 等数据初始化文案
- [ ] 注释/docstring 单独确认（可接受保留，但要有意为之而非遗漏）
- [ ] 把「旧词残留」写进测试：导出/导入模板文案断言（见下）

> **关键区分**：AC 写「详情页和列表页显示『减免金额』」时，**范围限定在前端**。后端导出/导入文案属于**另一层**，
> 若不同步，会出现「前端叫减免、导出的 Excel 表头叫折扣」——同一份文件里两套术语。

### Real-world example (2026-09-16)

09-02 把「折扣」重构为「减免」（允许负值=加价），前端全部改完（`grep 折扣|折后 frontend/src` 为 0），
但后端仍存 8 处：

| 位置 | 内容 | 用户可见性 |
|---|---|---|
| `routes/billing/invoices.py:1259` | 导出表头「折扣金额」 | **用户可见**（下载的 Excel） |
| `routes/billing/invoices.py:1365`、`:1595` | 导入模板说明文案 | **用户可见** |
| `routes/billing/invoices.py:1473`、`:1476`、`:1479` | 导入校验行级错误文案 | **用户可见** |
| `models/billing.py:126`、`middleware/audit.py:91` | 注释 | 不可见 |

结果：**同一份导出文件，前端列表列头是「减免金额」，Excel 表头是「折扣金额」**。8 处中 6 处面向用户。

**教训**：术语重命名的 grep 必须覆盖**后端生成用户可见文本**的位置（导出/模板/错误文案），而不是只 grep 前端。

**已修复（2026-09-17，任务 `09-16-legacy-fixes-ternary-storage-consistency`）**：8 处全部统一为「减免」，
`grep -rn "折扣" backend/app` 为 0。修复时的**硬约束**（缺一即破坏存量导入）：

1. 模板第 2 行说明**必须保留** `必填：` / `可选：` 前缀 —— `utils/excel_import.py::_is_template_note_row` 据此判定说明行；
2. **列名与列顺序不得变**（否则已下载模板的存量导入会错列）——表头文案可改，列数不可改。

> **可复用的验证手法**：把模板契约写进集成测试（`test_billing_import_export_api.py` 的模板下载用例），
> 断言「列名与列序 == 期望列表」「说明行逐列以 `必填：/可选：` 开头」「表头与说明行均不含旧词」。
> 只断言新文案出现是不够的 —— 必须同时锁住**未变的部分**（列序、前缀），才能同时防「漏改」与「改坏」。

---

## Widening vs Narrowing Parser (同一结构的宽严解析不一致)

同一个字段/结构，**两端解析宽容度不同**时，宽的一端能写出的数据，严的一端会崩。

### Checklist: 结构形态有多副本时

- [ ] 找全该结构的**所有**解析点：`grep -rn "<字段名>" frontend/src backend/app`
- [ ] 若某端做多种形态兼容（`Array.isArray(x) || x.ranges`），说明**历史或他处确实产生过多种形态** → 另一端必须同样兼容，或统一归一化
- [ ] 归一化收敛到**单一 owner 函数**，而非每个消费点各自 `try/except`
- [ ] 严的一端对异形输入必须**可控失败**（4xx + 可读文案），不得裸抛异常变成 500

### Real-world example (2026-09-16)

`pricing_rules.tiers` 字段：

```typescript
// 前端 frontend/src/utils/invoiceFormatters.ts —— 宽容：两种形态都认
export function parseTiers(raw: unknown): TierRange[] {
  if (Array.isArray(raw)) arr = raw
  else if (typeof raw === 'object' && Array.isArray(raw.ranges)) arr = raw.ranges
}
```

```python
# 后端 backend/app/services/billing.py —— 严格：只认对象
ranges = tiers.get("ranges", [])   # tiers 若是 list → AttributeError → HTTP 500
```

后果：把 `tiers` 写成裸数组（前端可见形态之一）时，`calculate-items` 返回 **500** 而非 400/降级为 0。
两端对同一字段的「合法形态」定义不同，且无归一化 owner。

**正确方向**：定义一次（如后端 Pydantic 模型 + 前端同一归一化函数），两端共用；异形输入返回 `40002` 类业务错误。

**已修复（2026-09-17，任务 `09-16-legacy-fixes-ternary-storage-consistency`）**：收敛为**数组**单一形态
`[{"min": int, "max": int|null, "price": number}]`，并建立两个唯一 owner：

- 后端 `backend/app/utils/tiers.py`：`normalize_tiers()`（归一化）/ `parse_tiers_or_raise()`（校验 + 行级文案）/ `TierFormatError`
- 前端 `frontend/src/utils/tiers.ts`：`parseTiers()`（唯一解析实现）

消费点全部改为调用 owner：`services/billing.py`、`services/cost_calc.py`、`services/analytics.py`、
`routes/billing/pricing.py`（导入校验）；前端 `invoiceFormatters.ts`、`PricingRules.vue`、`PricingRuleModal.vue`。

**修复过程中新暴露的三类坑（值得记住）**：

1. **宽严收敛会制造新的 500 面**：把「宽容」替换为「严格归一化」后，原先靠 `isinstance(x, list)` 守卫而
   **侥幸不崩**的调用点（如 `analytics` 健康度评分）会开始抛 `TierFormatError` → 500。
   收敛时必须 `grep` 出**全部**消费点，而非只改已知的那几个；纯展示型消费点应 `try/except` 降级为「无阶梯配置」。
2. **写入口必须校验，否则缺陷被推迟到结算期**：`create` / `update` 若不归一化，非法 `tiers` 会落库，
   直到生成结算单时才炸，而那时用户已看不到上下文。写入口统一经 `normalize_tiers`（非法 → `40001`）。
3. **边界校验决定「静默错值」还是「显式失败」**：只校验类型不校验关系，`max < min` 会让下游
   `容量 = max - min + 1` 变负 → **静默算出负数金额**。必须补 `max >= min`、`price >= 0` 两条关系校验。
   （`price == 0`、`max == min` 仍合法，不要过度收紧。）

> **验证手法**：用边界矩阵（本例 22 例：空数组/缺键/类型错/关系错/混合类型/null 等）逐一断言
> 「返回 `None`」或「抛 `TierFormatError`」，不允许出现「不崩但错值」。再用端到端用例锁住
> 「导入 → 存储形态为数组 → 结算计价正确」这条链路。

---

## Cross-Platform Template Consistency

In Trellis, command templates (e.g., `record-session.md`) exist in **multiple platforms** with identical or near-identical content. This is a cross-layer boundary.

### Checklist: After Modifying Any Command Template

- [ ] Find all platforms with the same command: `find src/templates/*/commands/trellis/ -name "<command>.*"`
- [ ] Update all platform copies (Markdown `.md` and TOML `.toml`)
- [ ] For Gemini TOML: adapt line continuations (`\\` vs `\`) and triple-quoted strings
- [ ] Run `/trellis:check-cross-layer` to verify nothing was missed

**Real-world example**: Updated `record-session.md` in Claude to use `--mode record`, but forgot iFlow, Kilo, OpenCode, and Gemini — caught by cross-layer check.

---

## Generated Runtime Template Upgrade Consistency

Some generated files are both documentation and runtime input. In Trellis,
`.trellis/workflow.md` is parsed by `get_context.py`, `workflow_phase.py`,
SessionStart filters, and per-turn hooks. Template changes must be validated
against both fresh init and upgrade paths.

### Checklist: After Modifying A Runtime-Parsed Template

- [ ] Identify every runtime parser that reads the template, not just the file
      writer that installs it
- [ ] Check whether relevant syntax lives outside obvious managed regions
      such as tag blocks
- [ ] Verify fresh `init` output and a versioned `update` scenario that writes
      the older `.trellis/.version`
- [ ] Add an upgrade regression using an older pristine template fixture, then
      assert the installed file reaches the current packaged shape
- [ ] Update the backend spec that owns the runtime contract

---

## Versioned Documentation Boundary

Versioned documentation is a cross-layer boundary: source paths, `docs.json`
version routing, and the rendered version selector must all describe the same
release line.

### Checklist: Before Editing Versioned Docs

- [ ] Identify the target release line: stable, beta, or RC
- [ ] Verify the edited MDX path matches that line:
  - stable: `docs-site/{start,advanced,...}` and `docs-site/zh/{start,advanced,...}`
  - beta: `docs-site/beta/**` and `docs-site/zh/beta/**`
  - RC: `docs-site/rc/**` and `docs-site/zh/rc/**`
- [ ] Verify `docs.json` navigation points the version label to the same paths
- [ ] Grep the opposite tree for release-line-specific terms before committing
- [ ] Treat beta content appearing under root release paths as a source-path bug,
      not a rendering bug

**Real-world example**: A beta-only task workflow change documented
`prd.md` + `design.md` + `implement.md`, task-creation consent, and Codex
mode banners under root `start/` and `advanced/` paths. The docs site then
served 0.6 beta behavior under the Release selector. The fix was to restore root
release docs, move the 0.6 content to `beta/` and `zh/beta/`, and add a grep
audit for beta markers against the root release tree.

**Real-world example**: Codex inline mode changed workflow platform markers from
`[Codex]` / `[Kilo, Antigravity, Windsurf]` to `[codex-sub-agent]` /
`[codex-inline, Kilo, Antigravity, Windsurf]`. Fresh init was correct, but
`trellis update` only merged `[workflow-state:*]` blocks and preserved stale
markers outside those blocks. Result: upgraded projects got new hook scripts
but old workflow routing, so `get_context.py --mode phase --platform codex`
could return empty Phase 2.1 detail.

---

## Mode-Detection Probe Checklist

When a CLI auto-detects a mode by probing a remote resource (e.g., checking if `index.json` exists to decide marketplace vs direct download):

### Before implementing:

- [ ] Probe runs in **ALL** code paths that use the result (interactive, `-y`, `--flag` combos)
- [ ] 404 vs transient error are distinguished — don't treat both as "not found"
- [ ] Transient errors **abort or retry**, never silently switch modes
- [ ] Shared state (caches, prefetched data) is **reset** when context changes (e.g., user switches source)
- [ ] **Shortcut paths** (e.g., `--template` skipping picker) must have the same error-handling quality as the probed path — check that downstream functions don't call catch-all wrappers

### After implementing:

- [ ] Trace every path from probe result to the mode-decision branch — no fallthrough
- [ ] External format contracts (giget URI, raw URLs) are tested or at least documented as comments
- [ ] Metadata reads consume a complete response or use a streaming parser — never parse a fixed-size prefix as full JSON
- [ ] When reconstructing a composite identifier from parsed parts, verify **all** fields are included and in the **correct position** (e.g., `provider:repo/path#ref` not `provider:repo#ref/path`)
- [ ] Verify that **action functions** called after a shortcut don't internally use the old catch-all fetch — they must use the probe-quality variant when error distinction matters

**Real-world example**: Custom registry flow had 8 bugs across 3 review rounds: (1) probe only ran in interactive mode, (2) transient errors fell through to wrong mode, (3) giget URI had `#ref` in wrong position, (4) prefetched templates leaked across source switches, (5) `--template` shortcut bypassed probe but `downloadTemplateById` internally used catch-all `fetchTemplateIndex`, turning timeouts into "Template not found".

**Real-world example**: Agent-session update hints fetched npm `latest` metadata with `response.read(4096)` and then parsed it as complete JSON. The `@mindfoldhq/trellis` package metadata exceeded 4 KB, so the JSON was truncated, parse failed silently, and the first session injection showed no update hint. Fix: read the complete response before parsing, and add a regression where `version` is followed by an 8 KB metadata tail.

---

## Cross-Platform Template Consistency

In Trellis, command templates (e.g., `record-session.md`) exist in **multiple platforms** with identical or near-identical content. This is a cross-layer boundary.

### Checklist: After Modifying Any Command Template

- [ ] Find all platforms with the same command: `find src/templates/*/commands/trellis/ -name "<command>.*"`
- [ ] Update all platform copies (Markdown `.md` and TOML `.toml`)
- [ ] For Gemini TOML: adapt line continuations (`\\` vs `\`) and triple-quoted strings
- [ ] Run `/trellis:check-cross-layer` to verify nothing was missed

**Real-world example**: Updated `record-session.md` in Claude to use `--mode record`, but forgot iFlow, Kilo, OpenCode, and Gemini — caught by cross-layer check.

---

## Generated Runtime Template Upgrade Consistency

Some generated files are both documentation and runtime input. In Trellis,
`.trellis/workflow.md` is parsed by `get_context.py`, `workflow_phase.py`,
SessionStart filters, and per-turn hooks. Template changes must be validated
against both fresh init and upgrade paths.

### Checklist: After Modifying A Runtime-Parsed Template

- [ ] Identify every runtime parser that reads the template, not just the file
  writer that installs it
- [ ] Check whether relevant syntax lives outside obvious managed regions
  such as tag blocks
- [ ] Verify fresh `init` output and a versioned `update` scenario that writes
  the older `.trellis/.version`
- [ ] Add an upgrade regression using an older pristine template fixture, then
  assert the installed file reaches the current packaged shape
- [ ] Update the backend spec that owns the runtime contract

**Real-world example**: Codex inline mode changed workflow platform markers from
`[Codex]` / `[Kilo, Antigravity, Windsurf]` to `[codex-sub-agent]` /
`[codex-inline, Kilo, Antigravity, Windsurf]`. Fresh init was correct, but
`trellis update` only merged `[workflow-state:*]` blocks and preserved stale
markers outside those blocks. Result: upgraded projects got new hook scripts
but old workflow routing, so `get_context.py --mode phase --platform codex`
could return empty Phase 2.1 detail.

---

## Mode-Detection Probe Checklist

When a CLI auto-detects a mode by probing a remote resource (e.g., checking if `index.json` exists to decide marketplace vs direct download):

### Before implementing:
- [ ] Probe runs in **ALL** code paths that use the result (interactive, `-y`, `--flag` combos)
- [ ] 404 vs transient error are distinguished — don't treat both as "not found"
- [ ] Transient errors **abort or retry**, never silently switch modes
- [ ] Shared state (caches, prefetched data) is **reset** when context changes (e.g., user switches source)
- [ ] **Shortcut paths** (e.g., `--template` skipping picker) must have the same error-handling quality as the probed path — check that downstream functions don't call catch-all wrappers

### After implementing:
- [ ] Trace every path from probe result to the mode-decision branch — no fallthrough
- [ ] External format contracts (giget URI, raw URLs) are tested or at least documented as comments
- [ ] Metadata reads consume a complete response or use a streaming parser — never parse a fixed-size prefix as full JSON
- [ ] When reconstructing a composite identifier from parsed parts, verify **all** fields are included and in the **correct position** (e.g., `provider:repo/path#ref` not `provider:repo#ref/path`)
- [ ] Verify that **action functions** called after a shortcut don't internally use the old catch-all fetch — they must use the probe-quality variant when error distinction matters

**Real-world example**: Custom registry flow had 8 bugs across 3 review rounds: (1) probe only ran in interactive mode, (2) transient errors fell through to wrong mode, (3) giget URI had `#ref` in wrong position, (4) prefetched templates leaked across source switches, (5) `--template` shortcut bypassed probe but `downloadTemplateById` internally used catch-all `fetchTemplateIndex`, turning timeouts into "Template not found".

**Real-world example**: Agent-session update hints fetched npm `latest` metadata with `response.read(4096)` and then parsed it as complete JSON. The `@mindfoldhq/trellis` package metadata exceeded 4 KB, so the JSON was truncated, parse failed silently, and the first session injection showed no update hint. Fix: read the complete response before parsing, and add a regression where `version` is followed by an 8 KB metadata tail.

---

## When to Create Flow Documentation

Create detailed flow docs when:

- Feature spans 3+ layers
- Multiple teams are involved
- Data format is complex
- Feature has caused bugs before

---

## Event Log / Projection Boundary

Append-only logs are cross-layer contracts. A single event travels through:

```
CLI input → event writer → events.jsonl → reader → filter → reducer → display
```

### Checklist: After Adding A New Event Kind Or Field

- [ ] Add the event kind to the central event taxonomy
- [ ] Add a typed event variant or type guard at the event layer
- [ ] Add normalization helpers for array/object fields that come from
      user input or JSON
- [ ] Keep `seq` / `id` assignment in the event writer only
- [ ] Make filters and reducers consume the typed event guard, not local casts
- [ ] Make display code consume reducer output or typed events, not raw JSON
- [ ] Add at least one regression that proves history replay and live filtering
      use the same filter model

**Real-world example**: Thread channels added `kind: "thread"`, `description`,
`context`, labels, and `lastSeq`. The first implementation replayed thread
state correctly, but several commands still re-parsed event payload fields with
local casts. The fix was to make the core event layer own `ThreadChannelEvent`
and `isThreadEvent`, make `reduceChannelMetadata` the only channel metadata
projection, and make `reduceThreads` the only thread replay reducer.

---

## Backend Relative Resource URLs Must Be Reachable From Every Frontend Entry

后端返回**相对资源路径**（如 `avatar_url: "/uploads/avatars/1_xxx.jpg"`）时，
该路径的「可达性」是 Backend ↔ Frontend 的隐式契约：任何把相对路径直接
绑定到 `:src` / `href` 的消费端（dev server、生产 nginx、其他网关）都必须
把它转发到后端静态服务，否则浏览器拿到的是前端自己的回退页。

### Checklist: 后端新增/修改相对路径资源时

- [ ] 后端挂载静态服务：`app.static("/uploads/", settings.file_storage_path, ...)`（main.py）
- [ ] 认证中间件放行静态前缀（`request.path.startswith("/uploads/")`）
- [ ] **开发环境**：`frontend/vite.config.ts` 的 `server.proxy` 增加
      `'/uploads': { target: 'http://localhost:8000', changeOrigin: true }`
      —— 只配 `/api` 是常见遗漏
- [ ] **生产环境**：nginx 增加 `location /uploads/ { proxy_pass ...; }`
      （`deploy/docker/frontend-nginx.conf`）
- [ ] 任何其他前端入口（二级网关、预览站点）同样需要转发规则
- [ ] 验证时**必须检查响应 Content-Type**，不能只看 HTTP 200：
      SPA fallback 也会返回 200，但 `text/html` 会让 `<img>` 破图

### Real-world example (2026-09-17)

头像上传链路：后端 `upload_avatar` 返回相对路径
`/uploads/avatars/{user_id}_{uuid}.jpg` 并写入 `users.avatar_url`；
前端 `Profile.vue` 把 `formData.avatar_url` 直接绑到 `<img :src>`。

**现象**：上传成功（Message 提示成功、DB 已更新），但个人信息页头像
仍显示默认首字母 —— `<img>` 请求 `http://localhost:5173/uploads/...` 返回
`200 text/html`（vite SPA fallback 的 index.html），破图。

**根因**：`vite.config.ts` 的 proxy 只配了 `/api`，缺 `/uploads`；
生产 nginx 有 `location /uploads/`（`deploy/docker/frontend-nginx.conf`），
所以**生产正常、开发必现** —— 同一份代码两套入口行为不一致。

**修复**：`vite.config.ts` proxy 增加 `'/uploads'` 转发（与 nginx 同构），
vite 检测到配置变更自动重启后立即可用。

**可复用的验证手法**：

```bash
# 对比 dev 代理与后端直连的 Content-Type（不要只看状态码）
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:5173/uploads/avatars/x.jpg
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8000/uploads/avatars/x.jpg
# 期望两侧一致：200 image/jpeg；修复前 dev 侧为 200 text/html
```

> **教训**：后端返回相对路径 ≠ 前端能用。路径的解析终点由**消费端入口**决定
> （vite proxy / nginx location / 其他网关），改资源 URL 契约时必须逐入口核对
> 转发规则，且验证断言 Content-Type 而非仅 HTTP 200。
