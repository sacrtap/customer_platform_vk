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

### Mistake 5: 聚合端臆造源数据语义（单位 / 时区）

[来源: Bug fix 2026-10-16 — 运营工作台同步状态栏：成功率 98.1% 无意义、最近同步时间差 8 小时]

**Bad**: 聚合端看到 `SyncTaskLog.success_count/failed_count/skipped_count` 就假定它们
是同一单位的"成功/失败/跳过数量"，`Σsuccess/(Σsuccess+Σfailed+Σskipped)` 一把梭：

- `consumption_sync` 的 success_count = 成功同步**天数**（可上万）
- `check_balance_warning` 的 success_count = 正常客户数，failed_count = **严重预警客户数**（不是失败！）
- `email/invoice` 的 count = 发送**条数**

同时 `executed_at` 有的任务写 `datetime.now()`（本地）、有的写 `datetime.utcnow()`（UTC），
聚合端 `MAX(executed_at)` 字符串比较被 8h 时差误导，返回的不是真实最近一次。

**Good**: 跨任务/跨写入端聚合前，先核查每个源的字段语义与时间基准（单位是否一致、
是否同本地/UTC）；语义不一时改用**任务级**口径（本案例按 status 终值计数，partial 计 0.5），
时间统一为本地写入。

**Rule**: 任何"多源写入、一端聚合"的指标，先在契约里写死：

- 每个写入端各 count 字段的**单位**（天数/条数/客户数），禁止混合汇总
- 参与聚合的**业务域**（哪些 task 算"同步"）先与用户可见的参照页面对齐——2026-10-16 工作台同步状态栏曾把余额检查任务算成同步异常，与同步日志页（仅消费同步、100% 成功）矛盾引发二次返工
- `*_at` 时间字段的**写入基准**：统一用 `cst_now()`（显式 CST，不依赖进程本地时区），禁止 `datetime.now()`/`datetime.utcnow()`——前者依赖进程 TZ，后者偏 8h
- 历史脏数据按写入端区分一次性修正（`to_char(executed_at::timestamp + interval '8 hours', ...)`）

> **复发复盘（2026-10-23，break-loop）**：Mistake 5 首轮"修复"把 `datetime.utcnow()` 统一成 `datetime.now()`（naive 本地时间）并写进本规则，只消除"任务间时区混用"，却把"进程本地时区==CST"的**隐式假设**固化成规则。生产容器（无 tzdata，`main.py::_force_cst_timezone` 的 `time.tzset()` 静默回退 UTC）下 `datetime.now()` 退化为 UTC，CST 01:00 触发的同步任务 `executed_at` 被记成前一天 17:00。**教训**：修时区 bug 时"统一到本地时间"仍是隐式假设——必须统一到**显式时区函数**（`cst_now()`），且别把依赖进程状态的方案写进 spec 当规则。`utils/timezone.py` 早有 `cst_now()`、`analytics.py` 多处已用，但 `sync_task_service.py:159/958` 漏改——典型 **C. Change Propagation Failure**（改了规则没改全调用点）。

> **同类扩展修复（2026-10-24）**：复发复盘预警的 `billing.py` invoice.*_at 同类潜伏地已修复——14 处写入点（`services/billing.py` 10 处 `datetime.now().isoformat()` + `now_str` 驱动 `discount_applied_at`/`applied_at`，`routes/webhooks.py` 3 处 `datetime.utcnow()`）统一改 `cst_now().strftime("%Y-%m-%d %H:%M:%S")`。`webhooks.py` 此前用 `datetime.utcnow()` 与 `billing.py` 的 `datetime.now()` 混用（同 2026-10-16 `executed_at` 同款问题），一并统一。回归测试 `test_cancel_invoice_cancelled_at_uses_cst`（freeze UTC 17:00 断言 `cancelled_at == CST 01:00`）守护。

> **第三轮复发（2026-10-26，break-loop）——写入端已统一，读出口仍是漏的**：同步日志页「完成时间」显示 `01:09:21`，而同一任务「创建时间」是 `09:09:00`。这次**写入端完全正确**（`completed_at = datetime.now(timezone.utc)` 写进 timestamptz 列，DB 里就是 `09:09:21+08`），错在**读出口**：`isoformat()` 输出 `2026-10-26T01:09:21+00:00`，前端 `formatDate` 只做纯截断（`replace('T',' ').substring(0,19)`）**不做时区转换**，UTC 时刻被当成 CST 墙钟。三轮下来三条独立路径：
> 1. 2026-10-16 写入端混用（`now()` vs `utcnow()`）
> 2. 2026-10-23 「统一到本地时间」仍是隐式假设（依赖进程 TZ）
> 3. 2026-10-26 写入端统一了，但 **timestamptz 与 naive 两种列类型在同一张表混排，`isoformat()` 对它们的输出语义不同**
>
> **教训**：时区口径是**写入 + 读取 + 前端解析**三段链，任何一段单独修好都不够；且「逐列看都对、只有列与列的相对关系错」是最难自查的形态——本次两列单独看都是合法时间，只有 `completed_at < created_at` 这一**关系断言**能抓住。跨层输出多个时间列时，必须断言它们的相对关系（见 `.trellis/spec/backend/quality-guidelines.md`「API JSON 响应的时间字段」）。实测命令：`psql -tAc "SELECT created_at::text, completed_at::text FROM sync_tasks ORDER BY created_at DESC LIMIT 5"`——一列带 `+08`、一列不带，一眼看出列类型不同。

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

## ORM 模型 ↔ 数据库 Schema 契约（模型改了，库必须同源升级）

[来源: Bug fix 2026-10-13 — 客户管理页 `GET /api/v1/customers` 恒 500，`column customers.balance_warning_level does not exist`]

这是**跨层契约（B 类）**：ORM 模型与数据库 schema 是同一实体的两份声明，代码里
`select(Customer)` 隐含「库中有 `Customer` 的全部列」这一契约。当两者的**版本不一致**时，
契约破裂，且失败面是**整个实体**的所有查询（列表/详情/KPI/导出/后台任务），不只一个端点。

### 关键盲区：三层都是「假绿」

| 层 | 假绿原因 |
|---|---|
| 单测 | `MagicMock(spec=Model)` 校验的是**模型**，与真实 DB 无关 |
| 集成/E2E | conftest 用 `metadata.create_all` **全新库按当前模型建全列**——永远不会缺列 |
| CI（本 bug 时） | 只 `alembic upgrade head` 建库；没有比对「模型 vs 运行库」 |

→ 「模型有列」和「迁移链有该列」在 CI 里都成立，唯独「**运行库已执行该迁移**」无人校验。
> 修复后已补两道门禁：CI 加 `scripts/check_schema_drift.py`；单测级加 `TestModelMigrationParity`。

### Checklist: 任何 ORM 模型字段变更后

- [ ] 模型：`Mapped[...] = mapped_column(...)`，可空性注解与列 nullable 一致（否则映射期直接报错）
- [ ] 迁移：写 `backend/alembic/versions/` 迁移
- [ ] **应用**：`cd backend && python -m alembic upgrade head`
- [ ] **验证**：`cd backend && python scripts/check_schema_drift.py`（无「模型有、库里没有」的表/列）
- [ ] 环境核对：本地 / 测试 / 预发 / 生产是否都已 `upgrade head`
- [ ] 测试库**不要**再手写 `ALTER TABLE ... ADD COLUMN` 补列清单——已由 `tests/_test_data.py::sync_test_schema` 按 metadata 自动同步（防止清单滞后于模型）

### Real-world example (2026-10-13, balance_warning_level)

余额预警任务修复（`005e5b7`）给 `Customer` 加了 `balance_warning_level` /
`balance_warning_updated_at` 两个字段和一版迁移，但**没有把迁移应用到本地库**（停在
`v1w2x3y4z5a6`）。模型已有该列 → `select(Customer)` 生成的 SQL 带该列 → Postgres 报
`UndefinedColumnError` → 整个客户列表 500。修复即 `alembic upgrade head`，端点恢复正常
（`total=1274`）。教训：**「写了迁移」不是「升了库」**；CI 绿色与单测绿色都不能证明运行库已升级。

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

## Import/Export Symmetry (导入/导出字段对称性)

导入与导出是**同一份数据的两个方向**，模板、导出、服务解析三处必须列对齐——
缺一列=用户数据静默丢失，多一列=该列永远无法导入。

### Checklist: 修改导入/导出任一端时

- [ ] 模板 headers、导出列、服务解析字段**三处列名逐一 diff**
- [ ] 新增强制/枚举转换字段后，检查是否存在「仅导出有」或「仅模板有」的列
- [ ] 枚举转换函数实现方向正确（`中文→存储值`，不是反写）
- [ ] 未知枚举值报行级错误，绝不静默置空（`map.get(k)` 命中 None 要察觉）
- [ ] 集成测试断言：导出字段能完整回灌导入，落库后回读值一致

### Real-world example (2026-09-29, customer import)

模板补 `auto_initiate_settlement` 列 + 服务层补 `scale_level`/`auto_initiate_settlement`
处理 + settlement_type 中文→英文转换 + 未知合作状态行级报错。
根因同 `Widening vs Narrowing Parser`，这里强调了**回灌对称**这个测试视角：
导出文件本身就是最好的导入测试夹具。

### Real-world example (2026-10-13, is_real_estate 三处遗漏)

`is_real_estate`（是否房产客户）前端全链路已支持（新增/编辑/筛选/详情/批量编辑），
但**导入模板、导出文件、批量导入服务三处均未加该列**（服务 `optional_fields`/布尔
转换/Customer 构造三处也漏），文件链路完全无法读写该字段。修复补全模板+导出列，
并在服务补齐 NaN 清洗、`convert_bool_field` 转换与 ORM 构造传参。
教训：字段在前端表单存在 ≠ 文件链路存在——**为字段新增/同步时，按
「模板列 ↔ 导出列 ↔ 服务解析 ↔ ORM 构造」四处逐一核对**，尤其注意 ORM 构造只写了
`data.get` 却可能没传（转换了但不落库）。

**同族复发（2026-10-25, settlement_account_id）**：结算账户字段前端六处全支持
（三个表单 + 详情 + 列表序列化 + 结算单侧），但导入/导出/模板三处都没有——而 PRD
当初写的是「Excel 导入不支持该字段」，于是没人把文件链路纳入核对范围。结果是用户
页面配好的结算账户，经导出→回灌**静默丢失**（无报错，扣款对象悄悄变回自身余额）。
说明「四处核对」的触发条件不该是「导入是否支持该字段」，而是「该字段是否可被页面
写入」——只要页面能写，文件链路就必须至少能读能显，否则文件就是静默重置通道。

### 操作型 vs 实体型导入（回灌适用性判定）

不是所有导入都要求「导出可回灌」——先按语义分类再定契约：

| 类型 | 判定 | 契约 |
|---|---|---|
| 实体型（客户/计费规则/套餐） | 导入创建实体，导出是该实体的查询视图 | **导出 ⊇ 模板列，导出文件必须可直接回灌** |
| 操作型（余额充值/结算单导入） | 导入是补录动作，导出是不同语义的列表快照 | 只要求**模板列 == 服务解析列**（无静默丢列）；余额/结算单均已提供**列别名软回灌**（导出中文列→英文列；余额 2026-10-13、结算单 2026-10-25），且**导出端必须含 `company_id` 主键列**（结算单 2026-10-25 补） |

判错代价：对操作型强行要求回灌会把「充值动作」误当「实体同步」；对实体型放任
「模板缺列」则用户数据静默丢失。核验时先标性质，再选断言。

**预检查（dry_run）成为导入标配（2026-10-13）**：客户/余额导入的「预检查 → 确认导入」
两步流程已推广到全部 5 个导入端点（计费规则/套餐/结算单本次补齐）。前端通用
`ImportModal` 先发 `?dry_run=true` 展示「可导入 N 条 / 错误 M 条 + 行号明细」，确认后才
真实导入。实现要点：dry_run 分支**先于** commit/缓存失效/审计（请求零副作用）；
套餐/结算单循环内仍维护判重集合（`existing_types` / `existing_invoice_nos`），保证
预检查与真实导入去重一致——预检结果与落库结果不一致会让用户「确认时才知道有错」，
两阶段就失去意义。

**软回灌 vs 硬回灌（2026-10-13, balance import）**：余额导出列是中文展示名
（客户ID/实充余额（元）/赠送余额（元）），导入期待英文存储列——用户拿导出文件
回灌触发的是「缺少必填列」**列级 40003**，误导性极强（文件其实没问题）。修复：
导入端做列名别名归一（`df.rename` 中文展示列 → 英文存储列），导出文件即可上传，
之后按同一行级校验路径处理。语义边界：快照金额按「本次充值」入账（0 元与负金额
2026-10-13 起均允许导入，用于批量初始化/迁移与后付费应收余额快照；负值扣减余额）
——**软回灌不改变导入语义**（加的是列兼容+金额校验放开，不是「以快照覆盖余额」
的新功能）。凡是列级报错，先怀疑「导入/导出列名不是同一套」，再怀疑数据本身。

**导出缺主键列 = 回灌必断（2026-10-25, invoice export）**：结算单导出曾只有
「客户名称」而缺 `company_id`，且其余列全是中文展示名——用户拿导出文件回灌报
「缺少必填列：company_id, period_start, period_end, total_amount」，四条里三条是
别名问题、一条是导出根本没给主键列。同类坑 2026-10-13 已在余额导入修过一次，
但只修了导入端别名归一，**没回头核导出端是否给了主键列**——于是结算单换了一条
路径再踩一遍。两条硬规则：

1. **凡导入以 `company_id` 为主键列，导出就必须含 `company_id`**（balances /
   pricing-rules / invoices 现已一致）。修「缺少必填列」时别只加 `df.rename`，
   先确认导出端给了主键列——否则下次用户换个筛选条件导出照样断。
2. **别名归一是导入端的事，主键列是导出端的事**，两端各自漏都会复现同一症状。

**加列要管存量文件（2026-10-25, invoice legacy reflow）**：给导出补 `company_id` 后，
用户手里**升级前导出的旧文件**（纯中文列、无 company_id、末行还带「共 N 条记录」
统计行）仍会撞列级拦截。修复不是回滚新列，而是导入端做**三级降级**：`company_id`
允许缺列（必填列里剔除）→ 按「客户名称」解析 customer.id（重名行级拒绝，不静默
挂错人）→ 剔除导出统计行（否则产生「客户名称为空」虚假错误）。判据：**新列服务
未来，降级解析服务存量**——只做前者，升级当天用户全部存量文件报废。

**PRD 写「不支持」≠ 链路可以不读（2026-10-25, settlement_account_id）**：结算账户
（代扣余额）PRD 明确「Excel 导入不支持该字段」，于是导入/导出/模板三处都没有该列。
但客户在页面配好的结算账户，经「导出 → 回灌」后**静默退回「用自身余额」**——用户
看不到任何报错，只是扣款对象悄悄变了。教训：**字段只进页面表单而不进文件链路时，
文件就成了一个「悄悄重置该字段」的通道**。新增字段的核对清单必须含「导出列」，
不能因为导入侧当初判定「不支持」就跳过——不支持可以是不写，但不能是不读不显。

### 枚举转换方向（`convert_*_to_storage` 族）

统一三态契约：中文→英文存储值；英文原样透传（幂等）；**未知→None 由调用方报行级错误**。
`map.get(k, k)` 的透传写法会让「无效值校验」形同虚设（校验点拿到永远非 None 的结果）。
方向性单测用 parametrize 覆盖三态 + display 反向映射。

---

## 可配置字典 vs 硬编码白名单（Dictionary-Driven Enums vs Hardcoded Whitelists）

带管理页面的枚举（合作状态/行业/账号类型等）有**两个潜在真相源**：数据库字典表
（页面可增删改）与代码里硬编码的校验白名单。页面每次新增/编辑枚举后，硬编码校验
就成了过期快照——「页面有该值、导入/校验不认」是典型的跨层契约脱节（B 类）。

### Checklist: 校验/转换一个页面可配置的枚举字段时

- [ ] 确认该枚举是否有管理页面/字典表（`*_statuses`/`*_types` 表 + CRUD 路由），
      有则**读表校验**，禁止硬编码集合
- [ ] 服务层查询字典时与页面同源过滤（如 `deleted_at IS NULL`），不另起口径
- [ ] 错误提示里的可选值**动态拼接**（来自同一次查询），不要写死文案
- [ ] 模板/文档中的可选值说明同步动态化（如导入模板第 2 行提示）
- [ ] 集成测试：测试库插入新枚举 → 断言该值可通过校验/导入（证明校验与页面实时对齐）
- [ ] spec 中该字段规则写「读字典表」，不要写死具体值列表

### Real-world example (2026-10-13, customer import bding)

「合作状态」页面是 `cooperation_statuses` 表驱动（可新增「拓展中/bding」），而
`CustomerService.batch_create_customers` 硬编码 `{"active", "suspended", "terminated", "noused"}`
校验 → 页面新增 `bding` 后，导入预检查仍报「行306: 无效的合作状态: bding」。
修复：导入校验改为实时查询字典表（`value` 直接匹配 + `name` 中文映射），模板提示
同步动态化；并在集成测试 conftest 预置迁移默认枚举（测试库 TRUNCATE 后需恢复，
否则合法值也会被误报无效）。
教训：**「未知值报行级错误」的强化（2026-09-29）方向正确，但它钉死的是白名单本身，
不是「与页面同源」这一原则——报错逻辑应基于实时字典，而非代码里的静态集合。**

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

---

## Time Field Cross-Layer Contract（UTC 存储 ↔ CST 日期串）

计费/日期型表单字段的跨层契约：**DB 存 UTC 时刻**（`DateTime(timezone=True)`，
CST 当日 00:00 写入后是 UTC 前一日 16:00），**API 读出口给表单回填必须是 CST
日期串 `"YYYY-MM-DD"`**，**写入口只接受纯日期串**（`local_date_to_utc_start` /
`local_date_to_utc_end` 内部用 `date.fromisoformat`，遇 ISO 时刻即抛错）。

同一字段的读出口与写入口格式不一致时，编辑弹窗会把列表返回值原样回填进
日期选择器并原样提交——**改任何其他字段保存都会失败**（先冲突检查、再写库，
两处都解析日期）。

### Checklist: 新增/修改「日期型表单字段」时

- [ ] 读出口（列表/详情序列化）必须 `utc_to_cst_date_str(...)`，禁止 `isoformat()`
      —— `"2026-03-31T16:00:00+00:00"` 会让前端日期选择器拿到无效值
- [ ] 写入口（create/update/check-conflict）解析格式必须与读出口**闭合**：
      把 GET 返回值原样回传 PUT 必须成功，且往返后 DB 值不变（CST 日期不偏移）
- [ ] 若字段会被「列表 → 编辑弹窗回填 → 提交」，把回填值纳入保存链路一并验证；
      日期格式错误会伪装成「参数格式错误」/ 500，与业务校验无关
- [ ] 同一文件内多个读出口（列表、冲突响应、Excel 导出）格式保持一致
      （`_build_pricing_rules_excel` 已按 CST 输出，见其注释）
- [ ] 验证手法：集成测试走「创建 → GET 列表 → 原样回填 → check-conflict → PUT」，
      断言列表返回 `"YYYY-MM-DD"`、PUT 200、DB 中仍是原 CST 时刻

### Real-world example (2026-09-28)

计费规则编辑：点击任意条目 → 修改「单价」→ 确定 → 提示**「参数格式错误」**。

**现象**：任何字段的编辑都无法保存；创建正常（创建时日期由用户从选择器新选，
格式天然正确）。

**根因**：`GET /billing/pricing-rules` 列表用 `effective_date.isoformat()` 输出
UTC ISO 时刻（如 `"2026-03-31T16:00:00+00:00"`）；编辑弹窗 `a-date-picker`
回填该值并原样提交 → `check-conflict` 的 `date.fromisoformat()` 拒绝 → 400
「参数格式错误」；绕过冲突检查直接 PUT 同样 500（`local_date_to_utc_start`
在 try 外抛 ValueError）。导出路径 `_build_pricing_rules_excel` 早已用
`utc_to_cst_date_str` 并注释了同一原因，列表端点漏了。

**修复**：列表端点改用 `utc_to_cst_date_str`（与导出同一约定），回归测试
`test_pricing_rule_list_dates_round_trip_to_edit` 覆盖「列表回填 → 提交」全链路。

> **教训**：跨层日期契约要在**读出口**守：写入口只认 `"YYYY-MM-DD"`，那么凡是要
> 回填表单的读出口就必须吐 `"YYYY-MM-DD"`。别用「浏览器时区恰好转对」来掩盖
> —— 同一 ISO 串在不同时区/不同选择器下表现不一致，且回灌写入口必炸。

---

## Data Visibility Filter vs Business Parameter（可见性强制 vs 业务参数语义分离）

数据可见性（按权限强制过滤）与前端业务参数（如「我的客户」mine=true）**不能合并
为同一个服务端输入**——即使它们的取值在多数场景相同（都是当前用户 ID）。

### 契约原则

- **服务端强制可见性**（无 `customers:view_all` 时只显示自己负责的客户）由
  `customer_scope_user_id(request)` 返回的 `scope_user_id` 独占驱动，**只允许
  None（有 view_all → 全量）或 user_id（受限 → 归属过滤）两种取值**；
- **业务参数**（前端显式请求，如 mine=true 的「我的客户」卡片计数）只影响对应的
  业务输出项（`my_customers`），**不得反向污染全量统计卡片**；
- 前端会无条件携带的参数（如本案例前端 `loadKpiData` 固定传 `mine: 'true'`），
  服务端必须假设它**对任何用户都出现**——包括有 view_all 的 admin；
- 缓存 key 必须同时包含两种输入（`{"mine": mine_user_id, "visibility": scope_user_id}`），
  否则不同组合命中同一缓存。

### Checklist: 新增「按当前用户过滤」的统计/列表接口时

- [ ] 区分「服务端强制可见性」与「前端业务筛选参数」，接口签名用独立参数
      （如 `visibility_user_id` vs `mine_user_id`），禁止合并为一个参数
- [ ] 全量统计项（总数/重点/待完善等卡片）只受可见性参数约束；
      即使前端传了业务参数，有 view_all 的用户也必须看到全量
- [ ] 回归测试覆盖**有 view_all 用户 + 携带业务参数**组合（admin+mine=true），
      以及**受限用户 ± 业务参数**组合——缺任何一组都抓不到此类 bug
- [ ] 缓存 key 纳入全部影响输出的参数

### Real-world example (2026-09-29)

客户管理页顶部 KPI 卡片：admin（有 view_all）进入页面后 total/key_customers/
incomplete_profile 显示接近 0。

**现象**：admin 明明能看全部客户，列表全量，但 KPI 卡片数字异常小。

**根因**：前端 `loadKpiData` **无条件**传 `mine: 'true'`（该参数本意是「我的客户」
卡片计数）；route 层 `mine=true → mine_user_id = admin.user_id`，而 admin 的
`scope_user_id` 为 None（有 view_all）不触发覆盖 → `mine_user_id` 保持 admin ID；
KPI 可见性改造时用 `mine_user_id` 过滤三个全量卡片 → admin 的 total 只统计
admin 名下客户（≈0）。此前测试只覆盖「受限用户无 mine」与「admin 无 mine」，
漏掉了「admin + mine=true」（前端真实请求形态），所以两个方向的修复各自都
看起来正确。

**修复**：service `get_kpi_stats` 新增 `visibility_user_id` 参数（= route 的
`scope_user_id`），total/key/incomplete 三个全量卡片只按它过滤；`mine_user_id`
仅保留「我的客户」计数语义；`new_this_month` 同理改用 `scope_user_id`；缓存 key
加入 visibility。回归测试补充 admin+mine=true（全量）与受限+mine=true（归属）两组。

> **教训**：可见性过滤必须由服务端独立参数独占驱动，业务参数不得复用它；
> 前端无条件携带的参数 = 服务端必须对全角色正确。测试矩阵要包含
> 「最高权限 + 业务参数」组合，那正是 bug 最易藏身的地方。

## Optional Field Absent vs Explicit Null（可选字段「未传」与「显式 null」的区别）

部分更新（PUT/PATCH）接口里，**「JSON body 缺少该键」与「键存在但值为 null/空」是两种不同语义**，
不能都当作「不改」或都当作「清空」：

| 请求形态 | 语义 | 实现 |
|---|---|---|
| body 不含 `field` 键 | **不改动**该字段（向后兼容旧客户端） | `if "field" in data:` 才写库 |
| `field: null` 或 `field: ""`/空白 | **显式清空**（存 NULL） | `_normalize` 后写 None |

判定必须用**键存在性**（`"field" in data`），不能用 `data.get("field")` 是否为 None ——
后者无法区分「未传」与「传 null」。

前端契约：编辑表单提交时，若值被清空则**显式传 `null`**（不是省略键），
例如 `const v = form.field?.trim() ? form.field.trim() : null; api.put(..., { field: v })`。

### Checklist: 新增/修改部分更新接口时

- [ ] 区分「未传（保持）」与「显式空（清空）」，用 `in data` 判键存在
- [ ] 服务层收「是否提供」标志（如 `remark_provided: bool`），仅在提供时写库
- [ ] 规范化函数统一处理：`null` / 空串 / 空白 → `None`；超长等 → `ValueError` → 400
- [ ] 前端清空时显式传 `null`，不要把「清空」实现成「省略字段」
- [ ] 回归测试覆盖三态：不传（保持原值）/ 传值（更新）/ 传 null 或空白（清空）

### Real-world example (2026-10-13, balance_whitelists.remark)

余额白名单「编辑余额」弹窗新增备注字段：`PUT /api/v1/balance-whitelists/<id>` 用
`remark_provided = "remark" in data` 判定；`service.update(..., remark_provided=...)`
仅在提供时写 `record.remark`。前端清空备注提交 `null`。
若误用 `data.get("remark")`，则「只改余额不改备注」的旧调用会静默清空备注。

## Mock 层缺陷伪装成业务层 Bug（测试替身的链式属性陷阱）

**跨层类型：B（测试替身 ↔ 被测代码的隐式契约）**。症状与根因严重分离：业务代码
`expected_usage == 0` 走进兜底分支，现场报的是
`TypeError: '<' not supported between instances of 'MagicMock' and 'int'`，
而真正的缺陷在测试 helper 少定义了一条链。

### MagicMock 的三个静默陷阱

| 陷阱 | 机制 | 症状 |
|---|---|---|
| 未定义的链式属性 | `result.scalars().first()` 中 `scalars_result` 只设了 `.all`/`.unique`，`.first` 自动生成新 MagicMock | 被测代码读到「假行对象」，其任意属性都是 MagicMock，不报错直到下游比较/运算 |
| `side_effect` 列表错位 | 服务方法有前置 execute（如先查客户资格），测试列表漏第一项 | 整体错位一位：customer_stmt 拿到用量行、pricing_stmt 拿到余额行；下游字段是 MagicMock |
| Mock 行缺校验字段 | `normalize_tiers` 要求每档有 `price`，mock 数据只给 `min`/`max` | 校验抛 `TierFormatError` 被降级处理，业务流程静默走兜底分支，断言值与预期不符 |

### Checklist: 写/改 Mock DB helper 与 side_effect 时

- [ ] helper 显式定义被测代码用到的**每一条链**：`.first()` / `.scalars().first()` / `.scalar()` / `.scalar_one_or_none()`
- [ ] `side_effect` 列表长度 = 该方法（含私有 helper）全部 `await self.db.execute(...)` 次数，顺序逐一对应
- [ ] 服务方法新增/删除 execute 时，同步检查依赖它的全部测试列表
- [ ] mock 行对象的字段值遵守与被测代码相同的校验契约（如 tiers 每档必含 `price`）
- [ ] 症状是「下游 MagicMock 比较/运算 TypeError」时，先怀疑测试替身，再怀疑业务代码
- [ ] 判别手段：把测试数据搬进独立脚本直接调用被测方法——脚本过而 pytest 不过，说明差异在 pytest 环境（fixture/顺序/污染），不在数据本身

### Real-world example (2026-10-23, analytics 健康度 5 例全挂)

`tests/test_analytics_service.py` 的 `make_mock_execute_result` 只定义 `scalars_result.all/unique`，
未定义 `.first`；且 5 个 `TestCustomerHealthScoreService` 用例的 `side_effect` 列表都漏了
首个 `customer_stmt` 结果（该 execute 是后加的资格校验）。两者叠加使 `pricing_result`
成为 MagicMock → `tiers` 非法 → `expected_usage=0` → 走历史基线分支 →
`earliest` 也是 MagicMock → `min(90, ...)` TypeError。修复：helper 补链 + 5 个用例补 customer 行。

判别过程的关键实验：把同一份 mock 数据搬进独立 Python 脚本调用
`service.get_customer_health_score()` —— 脚本直接返回 `score=86.0`（与断言一致），
证明数据本身无误，问题在 pytest 加载路径；随后逐行比对才发现 helper 缺链。

## Same Field, Divergent Validation Across Entry Points（同字段跨入口校验脱节）

**跨层类型：B（入口层 ↔ 服务层的字段契约）**。同一个业务字段有多条写入路径
（页面表单、审批提交、批量导入、定时任务），每条路径各自写了一份校验。症状：
用户在入口 A 被明确告知「该值合法」（help 文案、placeholder、已有数据），在入口 B
却被同一条规则拒绝，报错文案还与业务语义相反。

### 模式识别

| 信号 | 含义 |
|---|---|
| 报错文案说「X 不能为负/不能为 Y」，但另一入口的 help 文案说「可以为 Y」 | 校验规则单点漂移，不是业务变更 |
| 服务层注释写明「允许为负值（加价），不校验上限」，某路由却 reject | 路由层比服务层更严，且这份「更严」没有对应需求 |
| 前端三个组件行为一致，唯独导入/批量路径报错 | 批量路径是后加的，复制校验时「顺手」加了限制 |

### 判定优先级（哪个入口的规则是基准）

1. **服务层业务方法是基准**——它被所有入口复用，注释即业务语义（如
   `apply_discount`：正数减免、负数加价）
2. **前端 help/placeholder 文案是用户承诺**——「可为负值」写在那儿，用户就按此填数
3. **批量导入/导出是补录通道，不是第二套规则**——它应当复用或宽于主链路校验，
   不得单独更严（更严 = 合法数据被拦；更松 = 脏数据绕过主链路兜底，同样不行）

### Checklist: 新增/修改任一批量导入校验规则时

- [ ] 该字段在**页面表单/审批提交**入口是否允许此值？不允许 → 导入侧才可拒绝
- [ ] 服务层对应方法（`apply_*` / `update_*` / `create_*`）的 docstring/注释怎么规定？
      导入校验必须与服务层一致，**不是另起一套**
- [ ] 前端 help 文案 / placeholder 是否向用户承诺了该值合法？承诺了就不能在后端拦
- [ ] 保留的边界约束是否只有「非有限值」与「跨字段上限」这类真正必要项？
- [ ] 导入模板第 2 行说明是否同步反映真实语义（负值/单位/格式）？
- [ ] 补一条回归测试：把用户报障的那个值原样导入，断言 success

### Real-world example (2026-10-26, 结算单导入负减免金额)

用户导入 `结算单_2026-10-26.xlsx` 预检查报「减免金额不能为负」，但业务需要支持
负值。根因：`routes/billing/invoices.py` 导入校验单独写了
`if discount_amount < 0: errors.append(...)`，而 `services/billing.py:1586`
明确「减免金额允许为负值（加价），不校验上限」，前端 `SubmitModal`
placeholder 甚至写着「请输入减免金额（可为负值）」、`InvoiceDetailDrawer`
对负减免显示为绿色 `+`。三处入口都允许，唯独导入拒绝——纯校验规则脱节。
修复：删除导入侧的 `< 0` 拒绝（保留 NaN/Inf 与 `> total_amount` 上限检查），
模板说明改为「可选：减免金额（元），负值为加价」，补回归测试
`test_import_invoices_negative_discount_allowed`（total 10000 / discount -500
导入成功并落库）。
