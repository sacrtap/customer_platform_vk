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

---

## 七、未收敛面

1. **ocr 规划阶段 1 个文件组未完成审查**：`backend/app/routes/billing/packages.py, pricing.py, services/cost_calc.py, utils/tiers.py, tests/unit/services/test_cost_calc.py, frontend/src/utils/tiers.ts, views/billing/{PackagePlans,PricingRules}.vue, components/PricingRuleModal.vue` 这一组在规划阶段连续 7 次 provider 错误（HTTP 502/524）后失败。该组文件在 **core review 阶段仍有产出**（#2/#12/#13/#14 均出自该组），故结论有效；但 `utils/tiers.py` 的区间连续性校验（#15）是否还有未被发现的同族问题，未获第二轮独立复核。
2. **`tiers.ts` / `PackagePlans.vue` / `PricingRules.vue` / `PricingRuleModal.vue`** 未产出 finding，属「审了但无发现」，非「未审」。
3. **LLM 请求可靠性**：393 次请求中 39 次重试后恢复、2 次未恢复；重试报告显示规划与 core review 两个阶段均受影响。
4. **低危档位的严重度标定未经独立复核**：§6.1 列出的 3 条由本次人工复核提级建议，ocr 原始档位仍为 low。
