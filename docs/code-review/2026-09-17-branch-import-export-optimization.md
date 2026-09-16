# 代码审查报告 — 导入导出功能优化

**日期**: 2026-09-17
**工具**: open-code-review (`ocr`) v1.12.4 (f1101fd7f, darwin/amd64)
**审查范围**: `main..feature/import-export-optimization` — 121 个变更文件（+8476 / -896），ocr 从中选中 68 个可审条目
**审查命令**: `ocr review --audience agent --from main --to HEAD`
**发现问题**: 3 高、11 中、21 低（共 35 条）
**处置结果**:

| 严重度 | 条数 | 已修复 | 判定误报 |
|---|---|---|---|
| high | 3 | 3 | 0 |
| medium | 11 | 9 | 2 |
| low | 21 | 0（按约定仅报告） | 0 |

**审查轮次**: 共 3 轮「审查 → 修复 → 验证」。本文件 §一～§七 为**第 1 轮**；§八 为**第 2 轮**（1 高 + 18 中 + 20 低，落代码面全部有终态）；§九 为第 3 轮复核（修复后重跑，用于判定 blocker/critical/major 是否清空）。

> 第 2 轮的意义：第 1 轮的修复本身引入了 2 条回归（M1、M10）并留下 1 条语义缺口（M9），第 2 轮独立复现后一并修复 —— 这也是「单轮审查不足以判定收敛」的直接证据。此外，第 1 轮判为低危的 3 条（#22、#18、#15）被第 2 轮重报为 medium，说明「低危只报告不落代码」的约定留下了真实缺口。

> **严重度对应**：本次目标要求修复 blocker/critical/major。ocr 只产出 high/medium/low 三档，对应关系取 `high → blocker/critical`、`medium → major`、`low → minor（报告项，不落代码）`。因此**落代码的修复面 = 3 高 + 11 中 = 14 条**。
>
> 14 条中 12 条已修复、2 条判定为误报。其中 1 条误报（`test_customers_api.py:835-839`）所指向的**真实缺陷 ocr 并未报告**，在验证过程中被发现并已修复（见 §4.2）。

---

## 一、审查范围与命令

```bash
# 审查（第 1 轮）
ocr review --audience agent --from main --to HEAD
# → Review complete: 35 finding(s) across 68 selected item(s).

# 取值范围
git diff main --stat | tail -1
# → 121 files changed, 8476 insertions(+), 896 deletions(-)
```

审查覆盖的代码文件（按模块分组，省略 `.trellis/tasks/archive/**` 元数据）：

- **后端路由**：`routes/billing/{invoices,balances,pricing,packages,imports}.py`、`routes/customers.py`、`routes/analytics.py`、`routes/sync_logs.py`
- **后端服务/工具**：`services/{billing,cost_calc,customers,analytics,invoice_excel,sync_task_service}.py`、`utils/{tiers,excel_import}.py`、`tasks/file_cleanup.py`、`cache/base.py`、`middleware/{auth,audit}.py`、`models/billing.py`、`repository/customer_repo.py`
- **脚本**：`scripts/{seed,check_detail_files}.py`、`scripts/backfill_balance_archives.sql`
- **前端**：`api/{billing,index}.ts`、`composables/{useBalance,useInvoice}.ts`、`utils/{tiers,invoiceFormatters}.ts`、`views/billing/{Balance,Invoices,PricingRules,PackagePlans}.vue`、`views/billing/components/{ImportModal,PricingRuleModal,GenerateInvoiceModal}.vue`
- **测试**：`tests/**`（含 integration / e2e / unit）、`tests/integration/{conftest,test_customers_api,test_billing_import_export_api,test_auth_api}.py`

**LLM 可靠性**：39/393 请求经重试恢复，2 次未恢复（规划阶段 `packages/pricing/cost_calc/tiers` 文件组），该项已在 §7 记为未收敛面。

---

## 二、findings 全表

### 高危（3 条，全部修复）

| # | 位置 | 问题 | 状态 |
|---|---|---|---|
| 1 | `backend/app/routes/billing/invoices.py:1536-1540` | 逐行 `flush()` 失败后会话中毒（`PendingRollback`），后续行与最终 `commit` 全失败 → 整批落空、返回 500 | ✅ 已修复 |
| 2 | `backend/app/routes/billing/packages.py:676-678` | 同上；且 `package_type` 全列唯一 + 软删除，软删除套餐类型会漏检并必然撞唯一约束 | ✅ 已修复 |
| 3 | `backend/app/tasks/file_cleanup.py:44-49` | 软链接防御只排除指向存储根**外部**，`temp/` 指向**内部**业务目录时校验通过 → 误删业务凭证（事故 B） | ✅ 已修复 |

### 中危（11 条：9 修复 / 2 误报）

| # | 位置 | 问题 | 状态 |
|---|---|---|---|
| 4 | `backend/app/routes/billing/invoices.py:1518-1523` | `invoice_no` 自动生成 check-then-act 竞态；预加载 `select(Invoice.invoice_no)` 全表扫描 | ✅ 已修复 |
| 5 | `backend/app/routes/billing/invoices.py:1480-1481` | `total_amount` 空单元格（NaN）绕过金额校验进入 DB | ❌ **误报**（§4.1） |
| 6 | `backend/app/routes/billing/balances.py:645-652` | 导出超 5 万行静默截断，前端仍提示「导出成功」 | ✅ 已修复 |
| 7 | `frontend/src/views/billing/Balance.vue:321-324` | 导出请求未覆盖 axios 全局 15s 超时，大导出前端先断 | ✅ 已修复 |
| 8 | `backend/scripts/check_detail_files.py:54-57` | `os.path.join` 遇绝对路径/`../` 越界，检查存储根之外的文件并可误重置 | ✅ 已修复 |
| 9 | `backend/tests/integration/test_customers_api.py:835-839` | 「断言与 fixture 清除策略矛盾」 | ❌ **误报**；其指向的真实缺陷已修复（§4.2） |
| 10 | `backend/app/routes/billing/balances.py:242-243` | count 路径日期/标签解析无容错，畸形参数 500（数据路径却静默忽略） | ✅ 已修复 |
| 11 | `backend/scripts/seed.py:272-277` | `billing:import` 一次性映射 4 个新导入码 → 权限膨胀，违反最小权限 | ✅ 已修复 |
| 12 | `backend/app/routes/billing/pricing.py:489-490` | 包年规则未校验 `package_type` 存在且 active → 静默创建 `unit_price=None` 规则并按 0 元结算 | ✅ 已修复 |
| 13 | `backend/app/services/cost_calc.py:386-387` | 结算热路径 `_calc_tiered` 未捕获 `TierFormatError`，单条脏数据中断整批结算 | ✅ 已修复 |
| 14 | `backend/app/routes/billing/pricing.py:457-459` | fixed 缺 `unit_price`、tiered 缺 `tiers` 均可通过校验 → 静默按 0 元结算 | ✅ 已修复 |

### 低危（21 条，按约定仅报告）

| # | 位置 | 问题 |
|---|---|---|
| 15 | `backend/app/utils/tiers.py:105-108` | 归一化只校验单条结构，不校验区间连续性：重叠区间重复计费、空隙按下一档、末档有上界则超出不计费（导入路径绕过前端 `getTierError`/`coverageGaps`） |
| 16 | `backend/app/services/customers.py:1098` | 被替换的 `convert_date_field` 支持 4 种日期格式，`parse_date_to_object` 仅 `%Y-%m-%d`，其余格式静默置空（数据静默丢失） |
| 17 | `backend/app/routes/billing/pricing.py:641` | `float(r.unit_price) if r.unit_price else None` 真值判断，单价为 0 导出为空（`additional_floor_price` 同理） |
| 18 | `backend/app/routes/billing/invoices.py:1546-1549` | `commit()` 后写审计，审计失败返回 500 但数据已落库 → 客户端重试产生重复 draft 结算单；`str(e)` 泄漏内部异常 |
| 19 | `backend/app/routes/billing/invoices.py:1455-1459` | `int(company_id)` 静默截断小数（`100001.9 → 100001`），可能挂到错误客户 |
| 20 | `backend/app/routes/billing/invoices.py:1411-1412` | 导入端点无后端文件大小限制，前端 10MB 可绕过 → 内存占用风险 |
| 21 | `frontend/src/views/billing/components/ImportModal.vue:165-166` | `revokeObjectURL` 紧随 `a.click()`，Safari/Firefox 可能撤销过早致下载失败 |
| 22 | `frontend/src/views/billing/components/ImportModal.vue:123` | 弹窗关闭不重置 `file`/`result`，重开会重复提交同一文件 |
| 23 | `backend/scripts/check_detail_files.py:64-69` | `--detect` 同时 `store_true` + `default=True` 且从未被读取，为死代码接口，误导运维 |
| 24 | `backend/scripts/check_detail_files.py:104-106` | `exists()` 与 `getsize()` 之间 TOCTOU，文件被并发删除时脚本带 traceback 中止 |
| 25 | `backend/tests/integration/test_auth_api.py:354` | 硬编码 `50000`，建议引用 `ErrorCodes.INTERNAL_ERROR` |
| 26 | `backend/app/cache/base.py:24-25` | 注释声称「调用方一律经 `ttl_for()`」，但 `analytics.py`（8 处）与 `customers.py`（2 处）仍硬编码 TTL |
| 27 | `backend/tests/test_cache.py:48-50` | 全量快照断言被替换为抽样，约 12 个 key 失去配置级回归保护 |
| 28 | `backend/scripts/backfill_balance_archives.sql:25` | 人工补偿脚本建议加 `\set ON_ERROR_STOP on` |
| 29 | `frontend/src/api/billing.ts:159` | `tiers` 类型与 `types/index.ts` 不一致（`Tier[]` vs `Tier[] \| null`） |
| 30 | `frontend/src/api/billing.ts:584-587` | 3 组导入/模板下载函数结构完全重复，建议抽 helper |
| 31 | `backend/scripts/seed.py:287-288` | `permissions.get(new_code)` 对新码缺失静默跳过，配合 2.7 无条件删旧码 → 笔误将静默降权 |
| 32 | `frontend/src/utils/tiers.ts:38` | `t.min != null` 使用松散比较，违反项目 lint 规范 |
| 33 | `backend/tests/e2e/conftest.py:23-25` | integration/e2e conftest 各自「清 sys.modules + 重载 app」，同进程两套 app 模块树并存 |
| 34 | `backend/tests/e2e/conftest.py:94-95` | `test_user` 命中已存在分支不校验密码/权限，数据漂移时无法自愈 |
| 35 | `.trellis/scripts/common/io.py:148` | `write_text_atomic` 会强制补 `\n`（含空串 → `"\n"`），docstring 未声明该规范化契约（**禁区文件，只报不改**） |

---

## 三、已修复项逐条说明

### 3.1 高危

**#1 `invoices.py:1536-1540` — 导入事务中毒（行级错误隔离失效）**

逐行 `db.add(invoice); await db.flush()` 抛 DB 级异常后仅记录错误、不回滚会话，SQLAlchemy 会话进入 `PendingRollback`，后续所有行的 `flush()` 与最终 `await db.commit()` 全部抛错，被外层 `except` 捕获返回 500 —— 此前已 flush 成功的行一并落空。

- **修复**：用 `async with db.begin_nested():`（SAVEPOINT）包裹每行 `add + flush`，单行失败只回滚该行的 SAVEPOINT，外层事务与已成功行不受影响；`existing_invoice_nos.add` 与 `success_count += 1` 移到 SAVEPOINT 块外，仅在该行成功后执行。
- **附带**：新增模块级 `logger`（`logging.getLogger(__name__)`），替换 except 内的 `import logging` 行内导入；外层 `except` 补 `await db.rollback()`，避免把中毒会话归还连接池。

**#2 `packages.py:676-678` — 同类事务中毒 + 软删除唯一约束冲突**

`PackagePlan.package_type` 为 `unique=True`，而删除是软删除（置 `deleted_at`），上方 `existing_types` 只预加载 `deleted_at IS NULL` 的行 —— Excel 中出现已被软删除的 `package_type` 时预检放行、flush 必然撞唯一约束，触发与 #1 相同的事务中毒。

- **修复**：以 `async with db_session.begin_nested():` 包裹逐行 `add + flush`；`existing_types.add` / `success_count += 1` 置于 SAVEPOINT 块外。
- **未改**：未把软删除行纳入去重预检 —— 该做法会让「重新导入一个已删除的套餐类型」被拒绝，而 SAVEPOINT + 行级错误已能给出准确反馈，改动面更小。

**#3 `file_cleanup.py:44-49` — 软链接内部指向盲区**

原防御 `resolved_temp.relative_to(storage_root)` 只排除指向存储根**外部**的软链接。若 `temp/` 被误配为指向存储根**内部**业务目录（`invoices/`、`avatars/`、`<YYYY>/<MM>/`），校验通过，随后 `os.walk(resolved_temp)` 会遍历业务目录，删除超 7 天的业务凭证文件并 `shutil.rmtree` 空目录 —— 恰好复现文档所述事故 B。

- **修复**：改为精确相等校验 `if resolved_temp != storage_root / TEMP_SUBDIR: 拒绝清理并记录 error`。正常 `temp/` 与「指向存储根外部」两类场景行为不变。

### 3.2 中危

**#4 `invoices.py:1518-1523` — 单号竞态与全表预加载**

- **修复（全表扫描）**：预加载范围收敛为「本日自动生成前缀 `INV-YYYYMMDD-%`」∪「本次 Excel 显式指定的单号（`in (…)`，行数上限 1000）」。原 `select(Invoice.invoice_no)` 全表加载该列，随表增长内存与耗时无限膨胀。
- **修复（竞态后果）**：并发下两个请求仍可能生成相同单号，但唯一约束冲突现在由 #1 的 SAVEPOINT 隔离为单行错误，不再升级为整批 500。
- **未改**：单号格式与 `while True` 生成器保持原样（`k=4` 即每客户每日 1 万种组合；超过需 10 次满额导入，且届时由 SAVEPOINT 兜底）。

**#6 `balances.py:645-652` — 导出静默截断**

- **修复**：`rows, _ = …` 改为 `rows, total = …`；导出响应新增 `X-Total-Count`（匹配总数）与 `X-Truncated`（`total > len(rows)` 时为 `"true"`）。前端 `Balance.vue` 读取 `x-truncated`，命中时提示「数据超过 5 万条，仅导出了前 5 万条，请缩小筛选范围后再导出」。
- **注意**：当前前端同源访问（Vite 代理/nginx），自定义响应头可直接读取；若改为跨域直连，需在 `config.py` 的 `cors_expose_headers` 中补充这两个头。

**#7 `Balance.vue:321-324` — 导出超时**

- **修复**：`exportBalances`（`api/billing.ts`）请求配置新增 `timeout: 120000`。导出为请求内同步完成的最坏路径（5 万行 + 近 30 天消费聚合 + openpyxl 生成 Excel），120s 取自 ocr 建议区间上限，其余接口仍用全局 15s。

**#8 `check_detail_files.py:54-57` — 路径拼接越界**

- **修复**：`_resolve_file_path` 返回 `str | None`：`(storage_root / detail_file_path).resolve()` 后校验仍在存储根之下，越界（绝对路径/`../`）返回 `None`；`main()` 将此类路径记入新增的 `out_of_root` 列表，单列「越界路径告警」并**不参与 `--reset-pending` 重置**，避免误重置正常 completed 记录。退出码语义不变（仅「不一致且未处置」返回 1）。

**#10 `balances.py:242-243` — count 路径解析无容错**

数据路径对 `recharge_date_from/to` 用 try/except 容错并**静默忽略**非法值，count 路径却无保护直接 `datetime.fromisoformat` → 畸形参数 500；`tag_ids` 的 `int(t.strip())` 同样无保护。

- **修复**：解析前移到共用的 `_parse_balance_filters`（日期 → `datetime`，`recharge_date_to` → 当日 23:59:59，`tag_ids` → `list[int]`），畸形输入抛 `ValueError`，由 `get_balances` / `export_balances` 既有的 `except ValueError → 40001` 统一转 400。两条路径共用同一份解析结果，行为完全一致；顺带消除了数据路径「静默忽略非法筛选而返回全量数据」的不一致。
- **未改**：同文件 `get_balance_stats`（KPI 端点）有独立的、同样无保护的 `tag_ids` 解析 —— 不在本 finding 范围，已在 §6 记录。

**#11 `seed.py:272-277` — 权限膨胀**

旧 `billing:import` 语义为「导入余额」（历史上仅用于余额充值导入端点），一次性映射为 4 个新码会把计费规则/包年套餐/结算单的导入能力静默授予原角色。

- **修复**：`LEGACY_TO_NEW_PERMISSIONS["billing:import"]` 收敛为仅 `["billing:balance_import"]`（真正的等价迁移），并加注释说明其余导入码需经角色管理显式授予。步骤 1 仍照常创建全部新权限码，步骤 2.7 的旧码清理不受影响。

**#12 `pricing.py:489-490` — 包年规则未校验套餐存在**

- **修复**：导入函数预加载 `active_package_types`（`deleted_at IS NULL AND status == 'active'`，与 `create_pricing_rule` 内部查询条件一致），包年行命中不到时报行级错误「套餐类型 'X' 不存在或已停用」并跳过。

**#13 `cost_calc.py:386-387` — 结算热路径未捕获 `TierFormatError`**

- **修复**：`_calc_tiered` 用 `try/except TierFormatError` 包裹 `normalize_tiers`，捕获后降级为 `tiers = []`（走 `unit_price` 分支）并 `logger.warning`，与 `analytics.py` 对同一函数的既有防御语义对齐。

**#14 `pricing.py:457-459` — fixed/tiered 未校验定价内容**

- **修复**：`pricing_type == "fixed"` 且 `unit_price is None` → 行级错误「定价结算必须填写单价」；`pricing_type == "tiered"` 且无 `tiers` → 行级错误「阶梯结算必须至少配置一条阶梯」。
- **与 ocr 建议的差异**：ocr 建议 tiered 判「`tiers` 非空**或** `unit_price` 非空」。实际改为「`tiers` 必填」——因前端 `PricingRuleModal` 对 tiered 强制要求至少一条阶梯，且结算侧 `_calculate_tiered_price` 对空 `tiers` 直接返回 `Decimal(0)`、完全忽略 `unit_price`，采用建议的宽松判定仍会静默按 0 元结算。此处与前端表单及结算逻辑对齐。

---

## 四、判定为误报的 finding

### 4.1 `invoices.py:1480-1481` — `total_amount` 空值绕过校验（**误报**）

**ocr 主张**：空单元格被读为 NaN，`Decimal(str(nan))` 得 `Decimal('NaN')` 且不抛异常，`NaN < 0` 与 `discount_amount > NaN` 均为 False，空值绕过校验进 DB，flush 时报底层错误。

**证伪**：Python `decimal` 的 `<`/`>` 运算遇到 NaN 会抛 `InvalidOperation`（并非返回 False）：

```
$ .venv/bin/python -c "
from decimal import Decimal, InvalidOperation
d = Decimal(str(float('nan')))
for expr, fn in [(\"NaN < 0\", lambda: d < 0), (\"0 > NaN\", lambda: Decimal(0) > d)]:
    try: print(expr, '=', fn())
    except Exception as e: print(expr, '-> 抛', type(e).__name__)
"
NaN < 0 -> 抛 InvalidOperation
0 > NaN -> 抛 InvalidOperation
```

而路由该处正是 `except (InvalidOperation, ValueError, TypeError)` → 产出行级错误「结算金额格式错误」，NaN 根本到不了 DB 层。**结论：误报，未改代码。**（该处与 `discount_amount` 的 `pd.isna` 判空写法不一致属风格差异，非缺陷。）

### 4.2 `test_customers_api.py:835-839` — 断言与清除策略矛盾（**症状误报，但指向真实缺陷**）

**ocr 主张**：测试断言 `errors == []` 必然失败，因为模板示例行带 `industry="房产经纪"` 而该用例未插入行业类型（`integration/conftest.py:322` 每个用例间 `DELETE FROM industry_types`）。

**证伪（症状层面）**：修复前实测该测试**通过**（`tests/integration/test_customers_api.py` 45 passed）。原因是路由在行业映射阶段追加错误后，紧接着执行

```python
success_count, errors = await service.batch_create_customers(customers_data)
```

**把 `errors` 整体覆盖**，先前追加的行业校验错误被静默丢弃 → `errors` 恒为 `[]`，断言恒成立。故「断言必然失败」不成立。

**但该 finding 的根因分析是对的，并暴露了一个 ocr 未报告的真实缺陷**：导入校验错误会被 service 返回值覆盖而丢失，用户导入含未知行业的文件时拿到 `error_count: 0 / errors: []`，误以为全部成功。

- **修复**：行业映射阶段的错误收集到独立列表 `industry_errors`，与 service 返回值合并 —— `errors = industry_errors + service_errors`；同时移除已失效的 `errors = []` 初始化。
- **配套测试修复**：修复后该错误如实回传，原断言随之失败（契约被真实改变），按 ocr 建议在 `test_import_customers_from_downloaded_template` 中先 `INSERT INTO industry_types (name, sort_order, created_at) VALUES ('房产经纪', 2, NOW()) ON CONFLICT (name) DO NOTHING` 并补清理。
- **回归防护**：新增 `test_import_customers_unknown_industry_reports_error`。

---

## 五、验证证据

### 5.1 修复前后行为可区分（回归防护有效性）

**(a) `invoices.py` 行级 DB 错误隔离** —— 新增测试 `test_import_invoices_row_db_error_isolation`（3 行：正常 / 单号 60 字符超 `String(50)` / 正常）：

```
[POST-FIX]  1 passed                     → 200 / success_count=2 / error_count=1 / 2 行实际落库
[PRE-FIX]   1 failed                     → 500
  AssertionError: {'code': 50001, 'message': "导入失败：This Session's transaction has been
  rolled back due to a previous exception during flush ...
  (sqlalchemy.dialects.postgresql.asyncpg.Error) StringDataRightTruncationError:
  value too long for type character varying(50)"}
  assert 500 == 200
```

**(b) `customers.py` 校验错误丢失** —— 新增测试 `test_import_customers_unknown_industry_reports_error`：

```
[POST-FIX]  1 passed
[PRE-FIX]   1 failed
  AssertionError: {'error_count': 0, 'errors': [], 'success_count': 2}
  assert False
```

### 5.2 针对性测试

```
$ .venv/bin/python -m pytest tests/integration/test_billing_import_export_api.py \
    tests/integration/test_customers_api.py tests/integration/test_billing_api.py \
    tests/unit/services/test_cost_calc.py tests/unit/test_tasks.py \
    tests/unit/test_test_data_consistency.py -q -p no:randomly
```

修复导致的既有契约变化共 2 处，均已按新契约修正断言并复测通过：

| 失败测试 | 原因 | 处置 |
|---|---|---|
| `test_import_customers_from_downloaded_template` | 断言 `errors == []` 此前靠「错误被吞掉」成立，修复后错误如实回传 | 用例内 seed 模板示例行所需的行业类型（`房产经纪`） |
| `test_import_pricing_rules_requires_device_and_layer_for_non_package` | 该用例的包年行 `package_type='A'` 在 `package_plans` 中不存在，被 #12 新校验拒绝 | 用例内 seed 一个 active 套餐并以该类型入行，补 try/finally 清理 |

### 5.3 lint / 格式化 / 前端

```
$ .venv/bin/ruff check <全部 12 个改动文件>        → All checks passed!
$ .venv/bin/ruff format --check <全部 12 个改动文件> → 12 files already formatted
$ cd frontend && npx vitest run                    → Test Files 14 passed / Tests 89 passed
$ npx vue-tsc --noEmit                             → exit 0（无输出）
$ npx eslint src/api/billing.ts src/views/billing/Balance.vue → 无输出
```

### 5.4 全量后端套件 + 覆盖率门禁

```
$ cd backend && .venv/bin/python -m pytest tests/ --cov=app --cov-fail-under=50 -q
...
TOTAL                                        10519   4461    58%
Required test coverage of 50% reached. Total coverage: 57.59%
================ 878 passed, 476 warnings in 319.69s (0:05:19) =================
EXIT=0
```

- 退出码 0；878 passed（门禁要求 ≥876）；覆盖率 57.59%（门禁 ≥50%）。
- 分层套件（`tests/e2e/` 与 `tests/integration/`）共用测试库，本次以单进程串行执行（`pytest.ini` 默认未启用 xdist），避免并发伪失败。

---

## 六、未修项及原因

### 6.1 低危 21 条 —— 按目标约定不落代码

目标明确「修复面：仅 blocker/critical/major 落代码；minor/nit/风格类只在报告列出」。21 条 low 全部仅记录于 §2。

**其中 3 条的实际影响高于 ocr 给出的档位，建议优先排期**（本次未改，等待确认）：

| # | 位置 | 为何值得提级 |
|---|---|---|
| 15 | `utils/tiers.py:105-108` | 导入路径可写入重叠/有空隙/末档有上界的阶梯区间，`_calc_tiered` 按 `max-min+1` 切块会**重复计费或漏计费**，且全程静默 —— 与本轮已修的「静默少计费」（#12/#14）同源 |
| 16 | `services/customers.py:1098` | 日期格式静默置空（`2024/01/15` 等）属**数据静默丢失**，且导入不报错 |
| 26 | `cache/base.py:24-25` | 注释声称的「唯一 TTL 来源」与存量 10 处硬编码不符，属文档与实现漂移，会让后续维护者据错误前提改缓存时长 |

### 6.2 越界/禁区 —— 只报不改

- `#35 .trellis/scripts/common/io.py:148`：位于目标指定的禁区 `.trellis/scripts/`（TD-3 已由用户明确排除）。

### 6.3 已识别但不在 finding 范围

- `balances.py` 的 `get_balance_stats`（KPI 端点）存在与 #10 同型的、无保护的 `tag_ids` 解析。本次只修复了 `_query_balance_rows` 的两条路径，未扩展至该端点。
- `balances.py` 导出新增的自定义响应头在跨域直连部署下需补 `cors_expose_headers`（当前同源部署不受影响）。

### 6.4 终态为「不修」的中危 finding（2 条，均为误报）

| # | 位置 | 终态 | 原因 |
|---|---|---|---|
| 5 | `backend/app/routes/billing/invoices.py:1480-1481` | 不修 | 经证伪为**误报**：`Decimal('NaN') < 0` 抛 `InvalidOperation` 并被既有 `except (InvalidOperation, ValueError, TypeError)` 捕获 → 产出行级错误，NaN 到不了 DB 层。缺陷不存在，无代码可修（§4.1 含复现命令与实际输出） |
| 9 | `backend/tests/integration/test_customers_api.py:835-839` | 不修（该 finding 本身） | 经证伪为**误报**：修复前该断言恒成立（行业校验错误被 service 返回值覆盖）。其**指向的真实缺陷已修复**并加回归测试，属另一条独立改动（§4.2） |

---

## 七、未收敛面

1. **ocr 规划阶段 1 个文件组未完成审查**：`backend/app/routes/billing/packages.py, pricing.py, services/cost_calc.py, utils/tiers.py, tests/unit/services/test_cost_calc.py, frontend/src/utils/tiers.ts, views/billing/{PackagePlans,PricingRules}.vue, components/PricingRuleModal.vue` 这一组在规划阶段连续 7 次 provider 错误（HTTP 502/524）后失败。该组文件在 **core review 阶段仍有产出**（#2/#12/#13/#14 均出自该组），故结论有效；但 `utils/tiers.py` 的区间连续性校验（#15）是否还有未被发现的同族问题，未获第二轮独立复核。
2. **`tiers.ts` / `PackagePlans.vue` / `PricingRules.vue` / `PricingRuleModal.vue`** 未产出 finding，属「审了但无发现」，非「未审」。
3. **LLM 请求可靠性**：393 次请求中 39 次重试后恢复、2 次未恢复；重试报告显示规划与 core review 两个阶段均受影响。
4. **低危档位的严重度标定未经独立复核**：§6.1 列出的 3 条由本次人工复核提级建议，ocr 原始档位仍为 low。

**第 2 轮的收敛情况**（详见 §八）：本章第 1 条（`utils/tiers.py` 的区间连续性同族问题）已由第 2 轮 M12 独立复现并修复；§6.3 的 `cors_expose_headers` 项已由第 2 轮 M5 关闭；§6.1 提级建议的 3 条中，#15 由 M12 修复，其余两条未在第 2 轮的 medium 组中出现。

---

## 八、第 2 轮审查与修复（round 2）

**日期**: 2026-09-17
**命令**: `ocr review --audience agent --from main --to HEAD`（与第 1 轮同范围、同参数、同版本）
**问题总数**: 1 高、18 中、20 低（共 39 条，会话 ID `39d8b583`）
**落代码面**: 1 high + 18 medium = 19 条（low 按「修复面仅 blocker/critical/major」约定不进代码）
**终态**: 19 条全部有终态 —— 全部已修复；其中 1 条（M6）的子主张经实测证伪后按修正主张修复

第 2 轮针对的是**第 1 轮修复完成后的工作树**，因此同时承担两项职责：(a) 复核第 1 轮改动是否引入新缺陷；(b) 独立复现第 1 轮因 provider 连续错误而未能完成规划的文件组（§7.1）。实测结论：**第 1 轮的修复引入了 1 条新回归（M10）**，并暴露出 1 条既有语义缺口（M9）；**M1 是本分支自身引入的回归**（非第 1 轮修复所致，证据见 §8.1）。此外，第 1 轮判为低危的 3 条（#22、#18、#15）被第 2 轮重报为 medium，说明第 1 轮「低危只报告不落代码」的约定留下了真实缺口。

### 8.1 回归与「低危提级」

| 类型 | 条目 | 依据 |
|---|---|---|
| 第 1 轮修复引入的回归 | M10 | 第 1 轮把行业校验错误改为「如实回传」后，`bool(float('nan')) is True` 使每个未填行业的行都多报一条「行业类型 'nan' 不存在」 |
| 第 1 轮修复暴露的既有缺口 | M9 | 行业映射失败的行一直会被创建，只是第 1 轮之前该错误被 service 返回值覆盖而不可见；错误可见后「报错同时成功计数 +1」才成为可感知的误判 |
| 本分支引入的回归 | M1 | `git diff main -- backend/app/services/analytics.py` 显示 main 上为 `tiers[-1].get("threshold")`（旧数据每档 threshold 有限），本分支（`a619eda`，`git merge-base --is-ancestor a619eda main` → 不在 main 上）改为 `tiers[-1].get("max")` 并加 `is not None` 守卫，而规范阶梯形态允许末档 `max: null` → 守卫静默跳过 |
| 低危提级 | M2、M8、M12 | 分别对应第 1 轮低危 #22（弹窗关闭不重置状态）、#18（审计失败误报为导入失败）、#15（阶梯区间连续性）—— 三者均是第 1 轮「低危只报告不落代码」约定下被搁置、但第 2 轮重报为 medium 的真实缺陷 |

> 其余 13 条 medium（M3～M7、M11、M13～M19）均为第 2 轮**新报出**的条目，与第 1 轮的 35 条无对应关系。

### 8.2 finding 全表与终态

| # | 严重度 | 位置 | 问题 | 终态 |
|---|---|---|---|---|
| H1 | high | `backend/app/routes/billing/pricing.py:514-525` | 与第 1 轮 #1 同型的事务中毒：逐行导入失败不回滚，会话进入 `PendingRollback` → 后续所有行与最终审计 `commit` 全部失败，返回 500 而前面的行已永久落库 | ✅ 行级回滚 + 外层 `except` 回滚 |
| M1 | medium | `backend/app/services/analytics.py:2293-2297` | 末档 `max` 为 `null` 时 `expected_usage` 恒为 0 → 落入 `expected_usage = actual_usage` 回退 → `usage_rate` 恒 100%，健康度评分中 50% 权重的用量维度失效（**本分支回归**） | ✅ 末档无上界时改用其 `min` |
| M2 | medium | `ImportModal.vue:123-125` | 组件常驻挂载、关闭不重置 `file`/`result`/`loading` → 重开直接点「开始导入」会重复提交同一文件（计费规则重复建、结算单再生成、余额重复入账） | ✅ `watch(visible)` 重置（含清空 file input） |
| M3 | medium | `backend/app/services/cost_calc.py:390-391` | 降级分支仅 `logger.warning` 且不含定位信息，历史脏数据可能静默按 0 元结算 | ✅ `logger.error` + 规则 id / 客户 id |
| M4 | medium | `backend/app/routes/billing/packages.py:664-671` | 包年套餐导入未校验 `device_type`/`layer_type` 取值域（模型仅 `String(20)`），非法字符串静默入库 | ✅ 值域白名单（空值仍表「通用」） |
| M5 | medium | `backend/app/config.py:46` | `X-Truncated`/`X-Total-Count` 未进 `cors_expose_headers`，跨域部署下前端读不到 → 截断提示永不触发 | ✅ 补两个响应头 |
| M6 | medium | `backend/app/routes/billing/invoices.py:1502-1505` | `Infinity` 绕过负数校验写入 `DECIMAL(12,2)`（**NaN 一项为误报**，见 §8.4） | ✅ 判空 + `is_finite()` |
| M7 | medium | `backend/app/routes/billing/invoices.py:1492-1493` | 账期以本地朴素 datetime 入库，与其它路径（`local_date_range_to_utc`）的 UTC 口径不一致 → 按 UTC 范围的查询/导出/详情重算错位 | ✅ 统一转 UTC |
| M8 | medium | `backend/app/routes/billing/invoices.py:1573-1576` | `commit()` 后写审计失败 → 返回 500 但数据已落库，客户端重试产生重复 draft 结算单 | ✅ 审计失败解耦（不影响导入结果） |
| M9 | medium | `backend/app/routes/customers.py:811-823` | 行业映射失败的行仍被创建：响应同时给出「行业类型 'X' 不存在」与 success_count，用户易误判并重复导入 | ✅ 只把 `valid_rows` 交 service |
| M10 | medium | `backend/app/routes/customers.py:815` | `bool(float('nan'))` 为 `True` → 每个未填行业的行多报一条「行业类型 'nan' 不存在」（**第 1 轮改动引入的回归**） | ✅ NaN 先归一化为 `None` |
| M11 | medium | `frontend/src/api/billing.ts:586-594` | 三个导入接口未放宽超时；后端为同步逐行处理（≤1000 行），前端超时中断后服务端仍会提交 → 「失败」但数据已写入 | ✅ 统一放宽（见 §8.5） |
| M12 | medium | `backend/app/utils/tiers.py:105-108` | 归一化只校验单条结构、不校验区间连续性：重叠区间**重复计费**、缺口**漏计费**、非末档 `max: null` 亦可通过 | ✅ 新增覆盖完整性校验 |
| M13 | medium | `frontend/src/api/billing.ts:602-610` | `exportPricingRules` 未放宽超时（后端同步 50000 行 + openpyxl） | ✅ 同 M11 |
| M14 | medium | `frontend/src/api/billing.ts:630-636` | `exportPackagePlans` 同上 | ✅ 同 M11 |
| M15 | medium | `backend/app/routes/billing/balances.py:675-678` | 导出在 async handler 内同步执行 pandas 组装 + openpyxl 写盘（上限 50000 行），阻塞事件循环 | ✅ 移入 `asyncio.to_thread` |
| M17 | medium | `backend/app/routes/billing/pricing.py:666-671` | 导出列给 `customer_id`（数据库内部主键），与导入模板主键 `company_id` 不一致 → 导出文件无法回灌 | ✅ 改为 `company_id` |
| M18 | medium | `backend/app/routes/billing/invoices.py:1601-1604` | 导入成功后未清 billing 缓存（同文件其余 12 个写端点均清） | ✅ 补 `invalidate_billing_cache()` |
| M19 | medium | `backend/app/routes/billing/invoices.py:1654` | 模板第 3 行示例数据会被当真数据导入 → 用户补填上传即为 100001 静默生成 `¥12500.50` 的 draft 结算单 | ✅ 移除示例行 + 同步改用例 |

> **编号完整性**：本轮 39 条原始清单可由 `ocr session comments 39d8b583-a307-49a7-9735-33d4f4863fdd` 完整复现，其严重度分布为 **1 高 + 18 中 + 20 低**。18 条 medium 全部映射到 M1–M15 / M17–M19；**M16 是分组阶段的空编号**（原始清单中无对应条目，详见 §8.6）。20 条 low 按约定不落代码，详见 §8.8。

### 8.3 逐条修复说明（择要）

**H1 `pricing.py:514-525` — 导入事务中毒**

`create_pricing_rule` 内部逐行 `commit`，因此失败行本身的工作不会落库；但 DB 级异常会让会话进入 `PendingRollback`，此后每一行的 `create_pricing_rule` 与最终审计 `commit` 都会失败 —— 表现与第 1 轮 #1 完全相同（整批 500，而前面的行已永久落库）。

- **修复**：行级 `except`（`ValueError` 与兜底 `Exception` 两处）补 `await db_session.rollback()`，隔离中毒会话；外层 `except` 同样补回滚，避免把中毒会话归还连接池。
- **未改**：`create_pricing_rule` 的逐行 commit 语义保持原样（改为整批单事务会牵动 `create_pricing_rule` 的对外契约与冲突检查，超出本 finding 范围）。

**M1 `analytics.py:2293-2297` — 末档无上界导致用量维度失效**

- **修复**：末档 `max` 为 `None` 时改用该档 `min`（阶梯入口边界，语义最接近旧实现的末档 `threshold`）。
- **未改**：单档 `{"min": 0, "max": null}` 仍走 `expected_usage = actual_usage` 回退 —— 该形态无阈值可比，与旧实现 `threshold=0` 的行为一致。

**M12 `utils/tiers.py` — 阶梯覆盖完整性校验**

新增 `_validate_tier_coverage`，在 `parse_tiers_or_raise`（导入路径唯一入口）内生效：

- 相邻档必须连续：后一档 `min` 必须等于前一档 `max + 1`（同时拒绝缺口与重叠）；
- 非末档 `max` 不得为 `null`（仅末档可无上界）；
- **末档允许有上界**（前端 `PricingRuleModal.getTierError` 同样允许，`unlimited` 是可选行为）—— 此时超出末档 `max` 的用量不再计费，属定价语义而非格式错误；
- 首档 `min` 允许非 0（前端编辑器要求为 0，但强制该约束与导入模板既有示例 `[{"min":1,"max":null,"price":5}]` 冲突）。

> **本轮自查发现并修正的实现缺陷**：该校验的第一版对「末档有上界」未加守卫，会取 `tiers[index + 1]` 抛 `IndexError`（绕过 `TierFormatError` 的文案翻译，退化为难懂的行级错误）。核验前端契约（`getTierError` 仅在「非末档设置不限」时报错，末档有上界合法）后改为「末档不参与连续性校验」，并补 `tests/unit/test_tiers_validation.py` 锁住该边界。

**M17 `pricing.py:666-671` — 导出列与导入主键对齐**

- **修复**：导出列 `customer_id` → `company_id`（`r.customer.company_id`），与 `balances` 导出的 `company_id` 约定及导入模板主键一致。
- **验证**：既有 `test_export_pricing_rules_success` 只断言返回 xlsx、未断言列名，故该契约收紧不破坏既有测试。

### 8.4 M6 的主张修正（部分误报）

ocr 主张「`NaN < 0` 恒为 False → NaN 绕过负数校验」。主会话实测：

```
Decimal('nan')  (d < 0)  → 抛 InvalidOperation   ← 既有 except 已覆盖，不是缺陷
Decimal('inf')  (d < 0)  → False，且 is_finite() == False   ← 真实漏洞
Decimal('-inf') (d < 0)  → True                  ← 被既有负数校验拦住
```

即 **NaN 一项是误报**（与第 1 轮 #5 同源，第 1 轮已证伪，第 2 轮再次报出），**Infinity 一项属实**。修复按修正后的主张执行：判空 → 「结算金额为空」；`not is_finite()` → 「结算金额格式错误」；`discount_amount` 分支同样处理。

### 8.5 超时策略统一

M11/M13/M14（以及第 1 轮 #7）本质相同。为避免「按 finding 逐个打补丁」留下策略不一致，`frontend/src/api/billing.ts` 引入单一常量：

```ts
const LONG_RUNNING_REQUEST_TIMEOUT = 120000
```

并把**全部同步重载端点**统一到该常量：`importBalances`、`importPricingRules`、`importPackagePlans`、`importInvoices`、`exportBalances`、`exportPricingRules`、`exportPackagePlans`、`exportInvoices`。

- 其中 `importBalances`（`/billing/import`，≤1000 行同步逐行）与 `exportInvoices`（`/billing/invoices/export`，openpyxl 同步生成）**不在 finding 名单内**，但与本批三条同型（后端同步、同样会超过全局 15s），由切片一并标出并交主会话裁决后纳入，避免留下「部分导入放宽、部分不放宽」的隐性不一致。
- 轻量端点（4 个 `import-template` GET、`getInvoiceFileStatus` 等）保持全局 15s，不滥用放宽。

### 8.6 M16 编号说明（分组阶段的空编号）

本轮 39 条 ocr 原始清单（可由 `ocr session comments 39d8b583-a307-49a7-9735-33d4f4863fdd` 复现）中**没有对应 M16 的条目** —— 18 条 medium 已全部映射到 M1–M15 / M17–M19。M16 是分组派发阶段留下的空编号，无对应 finding、无落代码面，故不在 §8.2 表中。

> 该编号在编写本报告时一度被认为「条目文本因上下文压缩而丢失」；发现 `ocr session` 可复现历史会话后核对确认：清单是完整的，M16 本身不存在对应 finding。

### 8.7 验证证据

**(a) 针对性测试**

```
$ .venv/bin/python -m pytest tests/integration/test_billing_import_export_api.py \
    tests/integration/test_customers_api.py tests/integration/test_billing_api.py \
    tests/unit/services/test_cost_calc.py tests/unit/test_tasks.py \
    tests/unit/test_test_data_consistency.py tests/test_analytics_service.py -q -p no:randomly
→ 1 failed, 221 passed in 110.64s
  FAILED tests/integration/test_customers_api.py::test_import_customers_success
    AssertionError: assert 0 == 2
```

该失败是 M9 契约变更的直接结果：行业映射失败的行不再入库，而该用例的两行恰好用了未 seed 的行业名（`互联网`/`房地产`）。按新契约在用例内 seed 行业后复测：

```
$ .venv/bin/python -m pytest tests/integration/test_customers_api.py -q -p no:randomly
→ 46 passed in 41.50s
```

**(b) 本轮新增的回归测试**

M1（末档无上界导致用量维度失效）→ `tests/test_analytics_service.py::TestCustomerHealthScoreService::test_get_health_score_unbounded_last_tier`：

```
[POST-FIX]  1 passed（usage_rate = 49.9，score = 70.95）
[PRE-FIX]   回退到修复前的 app/services/analytics.py 后：
            assert result["usage_rate"] == 49.9
            E   assert 100.0 == 49.9
            1 failed
```

该用例直接锁住原始症状：未修复时预期用量被回退为实际用量，`usage_rate` 恒为 100%。

M12（阶梯覆盖完整性）→ `tests/unit/test_tiers_validation.py`：

```
$ .venv/bin/python -m pytest tests/unit/test_tiers_validation.py -q -p no:randomly
→ 6 passed in 0.05s
```

覆盖：连续（末档有/无上界）、单档、相邻档缺口、相邻档重叠、非末档无上界。

**(c) lint / 格式化 / 前端**

```
$ .venv/bin/ruff check <11 个改动 .py 文件>        → All checks passed!
$ .venv/bin/ruff format --check <同上>             → 11 files already formatted
$ cd frontend && npx eslint src/api/billing.ts src/views/billing/components/ImportModal.vue
                                                   → 无输出（通过）
$ npx prettier --check src/api/billing.ts src/views/billing/components/ImportModal.vue
                                                   → All matched files use Prettier code style!
$ npx vue-tsc --noEmit                             → exit 0（无输出）
$ npx vitest run                                   → Test Files 14 passed / Tests 89 passed
```

**(d) 全量后端套件 + 覆盖率门禁（末轮，覆盖最终工作树）**

```
$ cd backend && .venv/bin/python -m pytest tests/ --cov=app --cov-fail-under=50 -q
...
Required test coverage of 50% reached. Total coverage: 57.65%
pytest: 885 passed, 476 warnings in 319.09s (0:05:19)
PYTEST_EXIT=0
```

- 退出码 0；885 passed（门禁要求 ≥876）；覆盖率 57.65%（门禁要求 ≥50%）。该次运行包含本轮新增的 `tests/unit/test_tiers_validation.py`（6 例）与 `test_get_health_score_unbounded_last_tier`，故由第 1 轮的 878 增至 885。
- 单进程串行执行（`pytest.ini` 默认未启用 xdist）。
- **运行环境注意**：`tests/e2e/` 与 `tests/integration/` 共用测试库，两个 pytest 进程并发时会互相拖慢并可能产生伪失败 —— 本次验证过程中一度出现「两个 pytest 进程同时运行」，单进程耗时由 5.3 分钟升至 20 分钟以上；清理后恢复正常。后续复核务必保证同一时刻只有一个 pytest 进程。

### 8.8 本轮未收敛面

1. **第 1 轮 21 条低危中仍有 18 条未落代码**：除被第 2 轮重报为 medium 的 #22 / #18 / #15 外，其余维持「报告项」状态（§6.1）。其中 §6.1 提级建议的 #16（`services/customers.py` 日期格式静默置空）、#26（`cache/base.py` TTL 注释与实现漂移）本轮未处理。
2. **本轮 20 条 low 同样按约定未落代码**，其中 3 条与已修缺陷同族、影响高于 low 档位，建议优先排期：
   - `utils/excel_import.py:38` —— 说明行识别用 `startswith(("必填", "可选"))`，当上传文件没有说明行时，首行数据中首列以「可选」开头的文本行（包年套餐模板首列是自由文本 `name`，如「可选服务包」）会被静默丢弃。
   - `invoices.py:1479-1483` —— `company_id` 为 `100001.9` 时 `int()` 静默截断为 `100001`，可能把结算单挂到错误客户名下（错误文案却称「不是有效整数」）。
   - `invoices.py:1414-1415` —— 导入端点无服务端体积上限，前端 10MB 校验可绕过。
3. **`create_pricing_rule` 的逐行 commit 语义未改**（H1 的未改项）：导入因此不是原子操作，中途失败时前序行已永久落库。改为整批单事务会牵动 `create_pricing_rule` 的对外契约与冲突检查，超出该 finding 范围。
4. **末档有上界时超出部分不计费**（M12 的未改项）：`_calc_tiered` 按 `max - min + 1` 切块，末档 `max` 有限时超过该值的用量不被计费。导入校验已按前端契约放行该形态（`getTierError` 允许末档有上界），但结算侧的定价口径未改 —— 属定价语义问题而非导入格式问题。
5. **`invoices` 导入端点仍无后端文件大小限制**（第 1 轮低危 #20 = 本轮 low 之一）。
6. **`get_balance_stats` 的 `tag_ids` 解析仍无保护**（第 1 轮 §6.3）：与 #10 同型，未扩展修复。

---

## 九、第 3 轮审查与修复（round 3）

### 9.1 本轮范围与结果

```
$ ocr review --from main --to HEAD ... （diff 范围为第 2 轮修复提交后的全量分支改动）
[ocr] Summary: 69 file(s) reviewed, 25 comment(s), ~22039081 token(s) used, 52m38s elapsed
[ocr] Session: 1043cab0-32c4-4568-ace7-5b0ad3268188
Review failed (cancelled): 25 finding(s); 3 of 69 selected item(s) failed.
```

- 69 个文件 / 25 条 finding / 52m38s。严重度分布：**high 1 / medium 7 / low 17**。
- 与第 1、2 轮的关键差别：第 1 轮口径内的高危（H1/H2/H3）已清零，本轮新增 1 条 high —— 与第 2 轮修复引入的**回归无关**，而是第 2 轮新写的 `pricing` 导出代码自身缺陷（`M17` 导出/导入闭合性只覆盖了 customers，未覆盖 pricing）。
- **本轮审查覆盖不完整**：69 个条带中 3 个因 provider 错误（HTTP 502/524/530）失败，含 `invoices.py` 所在分组。该分组的问题在第 1、2 轮已审过，但本轮未复核，见 §9.7。

### 9.2 finding 全表与终态

| # | 位置 | 级别 | 结论 | 终态 |
|---|---|---|---|---|
| R3-H1 | `backend/app/routes/billing/pricing.py:683-684` | **high** | 导出→导入日期无法往返一致 | 已修 |
| R3-M1 | `backend/app/routes/billing/packages.py:782` | medium | 导入模板第 3 行示例数据被当真数据导入 | 已修 |
| R3-M2 | `backend/tests/e2e/test_sync_task_e2e.py:105-115` | medium | 未 mock `OrderSyncService`，测试发起真实外网 MySQL 连接 | 已修 |
| R3-M3 | `backend/app/services/customers.py:1098-1099` | medium | `parse_date_to_object` 对 Excel 日期单元格返回 datetime | **主张部分证伪**，契约违反属实 → 已修 |
| R3-M4 | `backend/app/routes/billing/balances.py:684` | medium | 导出 5 万行组装在事件循环内同步执行 | 已修 |
| R3-M5 | `frontend/src/views/billing/components/ImportModal.vue:197` | medium | 部分失败后可在同一打开会话内重复提交同一文件 | 已修 |
| R3-M6 | `backend/app/routes/billing/pricing.py:425-430` | medium | `multi_floor_pricing_type` 与单价未做取值校验 | 已修 |
| R3-M7 | `backend/app/routes/billing/pricing.py:357-358` | medium | 客户映射未过滤软删除客户 | 已修 |
| R3-L1 | `backend/app/routes/customers.py:842` | low | 行业映射失败行被剔除后行号错位 | 仅报告 |
| R3-L2 | `backend/app/services/customers.py:1098` | low | 仅支持 `%Y-%m-%d` 一种文本日期格式 | 仅报告 |
| R3-L3 | `frontend/src/api/index.ts:170-172` | low | `JSON.parse` 结果未做类型收敛 | 仅报告 |
| R3-L4 | `backend/app/utils/excel_import.py:38` | low | 说明行识别前缀过宽 | 仅报告 |
| R3-L5 | `frontend/.../ImportModal.vue:181` | low | `a.click()` 后立即 `revokeObjectURL` | 仅报告 |
| R3-L6 | `backend/app/routes/billing/pricing.py:642` | low | `int(request.args...)` 对非数字参数抛 500 | 仅报告 |
| R3-L7 | `backend/app/routes/billing/packages.py:736-737` | low | 外层 except 未回滚会话（与 H1 同族） | 仅报告 |
| R3-L8 | `backend/app/routes/billing/pricing.py:690-692` | low | 导出的 pandas/openpyxl 同步 CPU 密集 | 仅报告 |
| R3-L9 | `frontend/src/api/billing.ts:608-613` | low | 新增导入函数手写 `Content-Type` 不必要 | 仅报告 |
| R3-L10 | `backend/scripts/check_detail_files.py:73-78` | low | `--detect` 参数 `store_true` + `default=True` 组合失效 | 仅报告 |
| R3-L11 | `frontend/src/composables/useBalance.ts:174-175` | low | 导出参数构建重复 | 仅报告 |
| R3-L12 | `frontend/src/utils/tiers.ts:38` | low | 宽松不等 `!=` 违反本文件 ESLint 规则 | 仅报告 |
| R3-L13 | `backend/app/services/cost_calc.py:414-415` | low | 首档 `min > 0` 时低于 min 的用量被计费 | **文档错误已修**，行为未改 |
| R3-L14 | `frontend/src/views/billing/Balance.vue:339-343` | low | blob 响应下服务端错误体无法解析 | 仅报告 |
| R3-L15 | `backend/app/routes/billing/invoices.py:1479-1483` | low | `company_id` 浮点单元格被 `int()` 截断 | 仅报告 |
| R3-L16 | `backend/app/routes/billing/invoices.py:1557` | low | 结算单号 4 位随机码空间过小 | 仅报告 |
| R3-L17 | `backend/app/routes/billing/packages.py:626` | low | `int(limit_count_raw)` 静默截断小数 | 仅报告 |

**终态：blocker/critical/major（= high/medium）8 条全部落地修复；low 17 条按目标约定仅报告。**

### 9.3 逐条修复说明

#### 9.3.1 R3-H1 —— pricing 导出→导入日期漂移（high）

**缺陷**：`effective_date` / `expiry_date` 是 UTC 时刻列（CST 当日 00:00 存为 UTC 前一日 16:00）。导出直接 `.isoformat()` 得到 `2026-06-30T16:00:00+00:00`；导入端按 `str(...)[:10]` 取前 10 字符得 `2026-06-30`，再按 CST 解析 —— **导出再导入整体提前一天**。

**单元级复现**（修复前）：

```
导出前(CST 输入)        : 2026-04-01
DB 存储(UTC)            : 2026-03-31 16:00:00+00:00
旧导出 .isoformat()[:10] : 2026-03-31
旧导入回读后(CST)        : 2026-03-30 16:00:00+00:00
往返一致(旧): False
```

**修复**：改用既有工具 `app/utils/timezone.py::utc_to_cst_date_str`（它同时正确处理 `None`、naive datetime、纯 `date`）。

```
往返一致(新): True
```

**回归防护**：新增 `tests/integration/test_billing_import_export_api.py::test_export_pricing_rules_date_round_trip`（导出 → 删原规则 → 回灌 → 再导出，断言日期恒为 `2026-07-01`）。**pre-fix 精确失败**：

```
E   AssertionError: assert '2026-06-30T16:00:00+00:00' == '2026-07-01'
```

#### 9.3.2 R3-M6 —— pricing 导入取值校验缺失（medium）

- `multi_floor_pricing_type` 此前原样落库，结算侧按「非 `incremental` 即 `unified`」静默处理 —— 用户以为配置生效，实际金额口径不是所选方式。现限定 `unified/incremental`（与模型字段、UI 下拉、模板说明三处一致）。
- `unit_price` / `additional_floor_price` 此前允许负数，会直接参与结算产生负向账单；UI 输入框限制非负，导入端不应放宽。现拒绝负值。

#### 9.3.3 R3-M7 —— pricing 客户映射未过滤软删除客户（medium）

预加载 `company_id -> customer_id` 时未加 `deleted_at IS NULL`：软删除客户已不可在页面选择，导入却仍可命中并为其创建规则（且导出后无法回灌）。现与列表页/导出端查询条件对齐。

#### 9.3.4 R3-M1 —— 模板示例数据行（medium）

`read_import_dataframe` 只丢弃第 2 行（说明行），第 3 行会被当作真实数据。`packages` 模板与 `pricing` 模板都内嵌了示例数据行：用户在示例行下方续写（而非覆盖）时会静默创建一条示例套餐/规则。两处均移除示例行（与第 2 轮 `invoices.py` 的处理同源）。

连带调整：共享测试 helper `_fill_template_example_row` 原依赖示例行其余列的内容，现改为「先写一整行合法数据（`default_row`）再按列覆盖」，pricing 与 packages 两个模板回灌用例的**断言语义不变**（pricing 仍 `success_count==1 / error_count==1 / errors[0] 以「第 4 行」开头`；packages 仍 `success_count==1 / errors==[]`）。

#### 9.3.5 R3-M4 —— balances 导出行组装移入线程（medium）

实测 5 万行组装约 **317ms 纯 CPU**（Decimal→float ×30 万、属性访问、`_compute_burn_down` ×5 万），原先在 Sanic 事件循环内同步执行。切分边界：

- 所有 `await db.execute(...)` 与 Redis 查询留在异步层（`_query_balance_rows_raw`，返回四元组）；
- 仅纯 CPU 行组装移入 `asyncio.to_thread(_assemble_balance_rows, ...)`；
- 安全性依据：`_assemble_balance_rows` 只访问已加载标量列、`selectinload` 三级预加载的关系、以及纯 Python dict，不触发懒加载；且返回后到 `to_thread` 之间无 commit/expire。
- 响应头（`X-Total-Count` / `X-Truncated`）、文件名、列顺序、截断判断均未变。

#### 9.3.6 R3-M5 —— 导入弹窗同一会话重复提交（medium）

部分失败（`error_count > 0`）时弹窗保持打开且确认按钮可用，用户再点一次会重新提交同一文件（余额会再次入账、计费规则/结算单会重复建数据）。第 2 轮加的重置只在弹窗**重开**时生效。现于有错误结果时清空已选文件与 file input（保留结果展示），再次点击仅提示「请选择要导入的文件」，需重新选文件才能提交；**成功路径行为不变**（仍返回 true、关闭弹窗、emit success）。

#### 9.3.7 R3-M2 —— e2e 用例真实外连（medium）

`test_concurrent_sync_conflict` 的第一个 POST 会触发路由内 `request.app.add_task(run_task())`，在测试事件循环内真实执行 `execute_task -> OrderSyncService.sync_orders`（配了 `EXTERNAL_MYSQL_URL` 即真实外连，`connect_timeout=10`；否则真实写库并与 `db_session` 夹具 teardown 竞态）。现整个测试体包进 `patch('app.services.sync_task_service.OrderSyncService')`，与同文件 `test_full_sync_flow` 写法一致，断言不变（201 / 409 / 冲突文案）。

#### 9.3.8 R3-M3 —— 日期单元格归一化（medium，主张部分证伪）

见 §9.4。按函数 docstring 契约落地归一化：新增 `isinstance(value, datetime)` 分支返回 `value.date()`（`datetime` 是 `date` 子类，必须先判断）。`pd.Timestamp` 同为 `datetime` 子类，一并覆盖。

#### 9.3.9 同族补修（非本轮 finding）

1. **`app/utils/tiers.py` docstring 事实性错误（第 2 轮 M12 写入）**：原文称「首档 `min > 0` 仅使 0 ~ min-1 的用量不计费」，与 `_calc_tiered` 实际行为**相反**。实测：

   ```
   首档 min=5, max=None, price=10
     用量   3 -> 30   (语义应为 0)      <- 静默多收
   ```

   该注释为第 2 轮自行写入，属本轮发现的**既有错误信息**，已改正（说明首档 `min=1` 与 `min=0` 等价、`min>1` 会多收，并说明为何不强制校验）。**行为未改**（R3-L13 仍属 low，按约定不落代码）。
2. **模板说明行阶梯示例**：由 `[{"min":1,...}]` 改为 `[{"min":0,...}]`（说明行导入时被丢弃，仅作填报引导）。

### 9.4 主张修正与误报

**R3-M3 的核心因果主张被证伪**（修复仍落地）：

- ocr 主张：「`pd.read_excel` 把日期单元格解析为 datetime，向 `Date` 列绑定会抛 `TypeError: expected datetime.date instance, got datetime.datetime`，导致该行 flush 被拒」。
- 实测（asyncpg 0.29.0，真实 Postgres）：对 `DATE` 列绑定 `datetime.datetime` 与 `pandas.Timestamp` **均成功**（驱动内部按 `.toordinal()` 静默截断时间分量）；真正被拒的是**字符串**（`DataError: 'str' object has no attribute 'toordinal'`）—— 那正是第 2 轮已修的点。
- 结论：**「Excel 原生日期单元格会导致导入失败」不成立**（原生日期此前实际能导入成功）。
- 但缺陷仍属实且已修：函数 docstring 与调用点注释都声明「返回 `datetime.date`」，原实现返回 `datetime` 违反自身契约，且依赖驱动隐式截断（换 `psycopg2` 等驱动会真正报错）。

### 9.5 本轮新增/修改的测试

| 用例 | 文件 | 性质 |
|---|---|---|
| `test_export_pricing_rules_date_round_trip` | `tests/integration/test_billing_import_export_api.py` | **新增**，R3-H1 回归防护（pre-fix 失败） |
| `TestParseDateToObject`（5 例） | `tests/unit/test_import_field_mapping.py` | **新增**，R3-M3（datetime/Timestamp 归一化、date 透传、字符串解析、空值） |
| `test_import_pricing_rules_from_downloaded_template` | 同上集成文件 | 适配共享 helper（断言语义不变） |
| `test_import_package_plans_from_downloaded_template` | 同上集成文件 | 适配共享 helper（断言语义不变） |
| `test_concurrent_sync_conflict` | `tests/e2e/test_sync_task_e2e.py` | 补 mock（断言不变） |

### 9.6 验证证据

**(a) 修复前后行为可区分（回归防护有效性）**

R3-H1 的回归用例在 pre-fix 下精确失败、post-fix 下通过（见 §9.3.1）—— 证明该用例真正锁住了缺陷，而非「改完顺手补一条必过的断言」。

**(b) 定向测试（含切片自验）**

```
# R3-H1 回归 + 模板回灌（helper 改动后）
$ pytest tests/integration/test_billing_import_export_api.py -k "date_round_trip or from_downloaded_template or export_pricing_rules_success"
5 passed, 26 deselected in 8.78s

# R3-M3 单测
$ pytest tests/unit/test_import_field_mapping.py
30 passed

# R3-M4（切片自验）
$ pytest tests/integration/test_billing_import_export_api.py -k export_balances        -> 3 passed
$ pytest tests/integration/test_billing_api.py -k "get_balances or balance_stats"      -> 10 passed

# R3-M3 的 asyncpg 绑定实测（证伪依据：真实 Postgres + asyncpg 0.29.0）
datetime.datetime -> DATE 列：成功（按 .toordinal() 截断）
pandas.Timestamp  -> DATE 列：成功
str               -> DATE 列：DataError: 'str' object has no attribute 'toordinal'
```

**(c) 全量后端套件 + 覆盖率门禁（末轮，覆盖最终工作树）**

```
$ cd backend && .venv/bin/python -m pytest tests/ --cov=app --cov-fail-under=50 -q -p no:randomly
...
TOTAL                                        10578   4471    58%
Required test coverage of 50% reached. Total coverage: 57.73%
================ 891 passed, 480 warnings in 324.15s (0:05:24) =================
```

- 退出码 0；891 passed（门禁要求 ≥876）；覆盖率 57.73%（门禁要求 ≥50%）。由第 2 轮的 885 增至 891，增量全部来自本轮新增用例。
- 单进程串行执行（同 §8.7 的运行环境注意：`tests/e2e/` 与 `tests/integration/` 共用测试库，不可并发跑两个 pytest 进程）。

**(d) 前端**

```
$ npx vue-tsc --noEmit        -> 无输出（类型检查通过）
$ npx vitest run              -> Test Files 14 passed (14) / Tests 89 passed (89) in 6.42s
```

**(e) lint / 格式化**

```
$ .venv/bin/ruff check app/ tests/integration/test_billing_import_export_api.py \
      tests/e2e/test_sync_task_e2e.py tests/unit/test_import_field_mapping.py
All checks passed!
$ .venv/bin/ruff format --check <5 个改动的 app 文件>
5 files already formatted
```

### 9.7 本轮未收敛面

1. **审查覆盖缺口**：本轮 69 个条带中 3 个因 provider 错误（HTTP 502/524/530）失败，含 `invoices.py` 所在分组。该分组第 1、2 轮已审，但**本轮未复核**；本节结论不含该分组的第 3 轮结论。
2. **`invoices.py` 同族项未复核**：第 1 轮 low #18（`int()` 截断）与本轮 R3-L15 同型；`invoices.py:1557` 结算单号空间问题（R3-L16）在两轮中均被重报，仍未落代码。
3. **17 条 low 全部仅报告**（按目标约定）。其中与已修 high/medium 同族、建议优先排期的 3 条：
   - `packages.py:736-737` —— 外层 except 未回滚会话，与 H1 同族（`pricing.py` 已修，`packages.py` 未修）；
   - `pricing.py:690-692` —— pricing 导出仍是同步 pandas/openpyxl（`balances.py` 已修，`pricing.py` 未修）；
   - `cost_calc.py:414-415` —— 首档 `min > 0` 静默多收（本轮仅改正了错误注释）。
4. **`create_pricing_rule` 的逐行 commit 语义未改**（承 §8.8 第 3 条）。
5. **末档有上界时超出部分不计费**（承 §8.8 第 4 条，属定价语义）。
6. **`_calc_tiered` 降级路径**：tiers 无法归一化时按 `unit_price` 结算并 `logger.error`（承第 2 轮 H3 修复），本轮未复核。

---

## 十、三轮收口结论

| 轮次 | high | medium | low | 高危残留 |
|---|---|---|---|---|
| 第 1 轮 | 3（全修） | 11（9 修 / 2 误报） | 21（仅报告） | 0 |
| 第 2 轮 | 1（全修） | 19（全修） | 20（仅报告） | 0 |
| 第 3 轮 | 1（全修） | 7（全修） | 17（仅报告） | **0** |
| **合计** | **5 修 5** | **37 修 35 / 2 误报** | **58 仅报告** | **0** |

**跑满 3 轮后无残留 blocker/critical/major，故停止循环**（目标约定的停止条件）。仍需人工关注的是：

1. **low 档位 58 条从未落代码** —— 这是目标约定的边界（「修复面仅 blocker/critical/major」），不代表它们不真实；其中 §9.7 与 §8.8 列出的同族项建议优先排期。
2. **第 3 轮有 3/69 条带未完成审查**，结论不含这些文件的第 3 轮复核。
3. **三轮均为 LLM 审查**，`R3-M3` 的因果主张被实测证伪即为例证：审查结论必须逐条实证，不能直接采信。
