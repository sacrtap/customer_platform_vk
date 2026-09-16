# 遗留项修复：术语统一、tiers 契约收敛、存储与状态一致性

## Goal

修复 09-16 验收暴露并在规划期进一步定位的遗留缺陷，消除「同一语义/契约存在多个副本，只有部分副本被更新」这一类问题在结算域的具体表现：

1. **A** 后端用户可见的「折扣」文案统一为「减免」
2. **B** 每日清理任务无差别删除业务凭证文件（结算明细 / 付款凭证 / 减免附件 / 头像），导致 DB 状态与磁盘实体永久脱节
3. **C** `pricing_rules.tiers` 前后端及服务层契约不一致：写入端统一写数组，结算计算读对象 → 导入任何阶梯规则后结算必 500
4. **D** `tiers` 条目字段名存在三套（`min/max/price`、`min_quantity`、`threshold`），消费端各自猜键名

---

## Background（调研结论，均有源码/磁盘/DB 证据）

### 缺陷 B 的性质修正（规划期新发现，严重性最高）

`backend/app/tasks/file_cleanup.py` 每日 03:00 执行：

```python
upload_dir = settings.file_storage_path          # 默认 "./uploads"
for root, dirs, files in os.walk(upload_dir):    # 递归全部子目录，无排除规则
    if file_mtime < cutoff_timestamp:            # 7 天前
        os.remove(file_path)
```

**无任何白名单/排除目录**，因此以下业务文件一旦超过 7 天即被当作「临时文件」删除：

| 文件类型 | 存储位置 | 写入方 |
|---|---|---|
| 结算单明细 Excel（对账凭证） | `uploads/invoices/<YYYY>/<MM>/invoice_<id>.xlsx` | `services/invoice_excel.py:607-610` |
| 通用上传文件 | `uploads/<YYYY>/<MM>/<uuid>.xlsx` | `routes/files.py:231-235` |
| 付款凭证 `payment_proof` | 同通用上传 | `routes/billing/invoices.py:621` |
| 减免附件 `discount_attachment` | 同通用上传 | `routes/billing/invoices.py:719` |
| 用户头像 | `uploads/avatars/` | `routes/users.py:811-821` |

**故障链证据（DB + 磁盘实测，2026-09-16）**：

```
detail_file_status 分布：completed=5, pending=1
5 条 completed 记录的文件实存性（backend/uploads/ 下）：
  MISSING  invoices/2026/07/invoice_35.xlsx   ← 2026-07 生成，>7 天
  MISSING  invoices/2026/07/invoice_36.xlsx
  MISSING  invoices/2026/07/invoice_37.xlsx
  MISSING  invoices/2026/07/invoice_38.xlsx
  EXISTS   invoices/2026/08/invoice_39.xlsx   ← 09-16 手动 regenerate 后重建
```

即 **状态-实体不一致率 4/5（80%）**，且缺失文件**全部是 7 天前的产物**，与清理任务行为完全吻合（置信度 97%）。
（`invoices/2026/07/` 下 4 个文件被删后目录仍存在，因空目录清理存在遍历时序问题。）

**附带问题**：`FILE_STORAGE_PATH` 未设置（`.env` 无该键，`config.py:49` 默认 `./uploads`），相对路径**相对进程 cwd** 解析。历史上曾从项目根启动过后端，留下 `uploads/invoices/2026/07/` 空目录树（项目根 `uploads/` 现仅 3 个空目录、无文件），而当前产物集中在 `backend/uploads/`。即：文件位置随启动目录漂移，DB 状态不受影响 → 静默不一致。

### 缺陷 C：tiers 契约矩阵

| 位置 | 期望形态 | 证据 |
|---|---|---|
| 导入模板说明（`routes/billing/pricing.py:312-313`） | **数组** | `tiers (可选) - 阶梯配置 JSON 字符串，如 [{"min":1,"max":null,"price":5}]` |
| 导入解析（`routes/billing/pricing.py:425-434`） | **强制数组** | `if not isinstance(tiers, list): raise ValueError("tiers 必须是数组")` |
| 前端表单提交（`PricingRuleModal.vue:323,371`） | **数组** | `tiers: [] as Tier[]` |
| 结算计算（`services/billing.py:1293`） | **对象** ❌ | `ranges = tiers.get("ranges", [])` |
| 前端类型声明（`types/index.ts:203`） | 对象 | `tiers: Record<string, unknown> \| null` |
| 前端格式化（`api/billing.ts:158`） | 两者皆可 | `Array<...> \| Record<string, unknown>` |

**后果**：通过导入功能创建任何 tiered 规则 → DB 存**数组** → 结算调用 `_calculate_tiered_price` 在 list 上执行 `.get()` → `AttributeError` → **HTTP 500**。当前库中 `tiers` 全为 `NULL`（无 tiered 规则），故该缺陷从未在生产暴露。

### 缺陷 D：tiers 字段名三套

| 消费点 | 使用的键名 | 代码 |
|---|---|---|
| 导入示例 / 前端表单 / `invoiceFormatters.parseTiers` | `min` / `max` / `price` | `pricing.py:313`、`invoiceFormatters.ts:74-77` |
| `services/cost_calc.py:390` | **`min_quantity`** | `sorted(tiers, key=lambda t: t.get("min_quantity", 0))` |
| `services/analytics.py:2289` | **`threshold`** | `float(tiers[-1].get("threshold", 0))` |

即同一 JSON 结构有 3 套键名约定，后两处对现行数据（`min/max/price`）取值恒为默认 0。

### 缺陷 A：后端「折扣」文案（8 处，6 处用户可见）

| 位置 | 内容 | 用户可见 |
|---|---|---|
| `routes/billing/invoices.py:1259` | 导出表头 `折扣金额` | ✅ 下载的 Excel |
| `routes/billing/invoices.py:1365` | 导入端点 docstring 字段说明 | ⚠️ 开发文档（接口文档渲染） |
| `routes/billing/invoices.py:1473` | 行级错误 `折扣金额不能为负数` | ✅ |
| `routes/billing/invoices.py:1476` | 行级错误 `折扣金额格式错误` | ✅ |
| `routes/billing/invoices.py:1479` | 行级错误 `折扣金额不能大于结算金额` | ✅ |
| `routes/billing/invoices.py:1595` | 导入**模板第 2 行说明** `可选：折扣金额（元）` | ✅ |
| `models/billing.py:126` | 注释 | ❌ |
| `middleware/audit.py:91` | 注释 | ❌ |

**已知硬约束**：模板第 2 行说明必须以 `必填：` 或 `可选：` 开头 —— `utils/excel_import.py::_is_template_note_row` 依赖该前缀判定说明行（见 `spec/backend/import-export.md`）。**修改文案时必须保留前缀，且不得改变列顺序/列名。**

---

## Requirements

### R1: 清理任务不得删除业务凭证（最高优先）

- `cleanup_temp_files` 必须**只清理明确的临时目录**，或对业务目录设置白名单/排除规则
- 至少不得删除：`invoices/**`（结算明细）、`avatars/**`（头像）、以及被 `payment_proof` / `discount_attachment` 引用的文件
- 清理范围与排除项应可配置或集中声明，而非散落在 `os.walk` 中靠约定

### R2: 存储根路径显式化

- 生产环境必须显式设置 `FILE_STORAGE_PATH` 为**绝对路径**；未设置或为相对路径时至少启动期告警
- 明确并文档化「相对路径相对进程 cwd」的语义

### R3: 状态与实体一致性

- 「`detail_file_status = completed` ⇒ 文件存在」必须可校验
- 生成失败或文件不可达时状态如实反映（`failed`），不得停留在 `completed`
- 对历史不一致记录（状态 completed 但文件已删）提供处置路径：重置为 `pending` 以便重新生成，或由运维按需触发

### R4: tiers 契约收敛为单一形态

- 全链路（导入、前端表单、服务层结算计算、cost_calc、analytics、前端解析与类型）统一为**同一形态与同一键名**
- 收敛目标形态与键名由 `Resolved Decisions` 决定
- 异形/非法输入必须可控失败（`40002` 类业务错误），不得裸抛异常变成 500

### R5: tiers 解析消除重复实现

- 前端现有 3 份等价解析（`invoiceFormatters.ts:115`、`PricingRuleModal.vue:418`、`PricingRules.vue:410`）合并为单一共享实现
- 后端 `tiers` 归一化收敛到单一 owner 函数，供 `billing.py` / `cost_calc.py` / `analytics.py` 共用

### R6: 后端用户可见文案统一为「减免」

- 覆盖：导出表头、导入模板说明行、导入行级错误文案
- 保留模板说明行的 `必填：` / `可选：` 前缀契约
- 注释类（`models/billing.py:126`、`middleware/audit.py:91`）一并更新以保持一致

---

## Acceptance Criteria

- [ ] **AC1** 清理任务执行后，`uploads/invoices/**`、`uploads/avatars/**` 下超过保留期的文件**仍存在**；而临时目录中的过期文件被删除（需有测试证明「删该删的、留该留的」）
- [ ] **AC2** 结算明细文件超过 7 天后仍可下载（`GET /billing/invoices/<id>/download-detail` 返回有效 xlsx），即使已跑过清理任务
- [ ] **AC3** `FILE_STORAGE_PATH` 为相对路径时，应用启动产生明确告警；设为绝对路径后，从任意 cwd 启动文件都落在同一位置
- [ ] **AC4** 存在「`detail_file_status=completed` 但文件缺失」的记录时，可被检出并按约定处置（重置 `pending` 或重新生成），处置后状态与实体一致
- [ ] **AC5** 通过导入功能创建 tiered 规则并调用 `POST /billing/invoices/calculate-items`，返回 `code=0` 且按阶梯正确计价（**不再 500**）
- [ ] **AC6** `tiers` 传入非法形态（如字符串、缺键、`null` 值异常）时返回业务错误码（非 500），且错误文案可读
- [ ] **AC7** 全链路 `tiers` 形态与键名一致：导入 → 存储 → 结算计算 → 前端展示 使用同一形态与同一键名（`grep` 不再出现第二套键名）
- [ ] **AC8** 前端 `tiers` 解析实现收敛为 1 处；后端归一化为 1 处 owner（可通过检索调用点验证）
- [ ] **AC9** 后端导出表头、导入模板说明、导入错误文案中不再出现「折扣」；模板第 2 行仍以 `必填：`/`可选：` 开头，列名与列顺序不变
- [ ] **AC10** 全仓检索 `折扣` 仅剩有意的历史记录（如有），并在 PR 说明中列出保留项与理由

---

## Out of Scope

- 结算单业务流程（状态流转、审批链路）的重构
- 外部 MySQL `nest_model_order` 的字段映射变更
- 已归档的 09-02 / 09-03 任务范围内的其它实现
- 部署编排（systemd / Docker workdir）本身的修改 —— 本任务只保证代码层面对配置缺失有明确反馈

---

## Resolved Decisions

1. **验收判「不通过」的处置**：在本任务内修复（沿用 09-16 的既定决策）。
2. **写入性验收**：允许在开发库创建/修改数据用于验证，但必须登记并在结束前恢复或说明保留理由。
3. **术语统一方向**：以「减免」为准（与前端已落地的 R2.1/R2.4 一致）。
4. **清理任务收口方式（用户已确认）**：**收缩到专用临时目录** —— `cleanup_temp_files` 改为只清理 `uploads/temp/`（当前不存在，故实际不删任何现有文件），使「临时文件」与「业务文件」在存储层物理分离。
   - 依据：`uploads/` 下无任何临时文件生产者（grep 全后端确认），现有三类目录 `invoices/`、`avatars/`、`<YYYY>/<MM>/` 全为业务数据。
5. **tiers 目标形态（规划决定，理由见下）**：统一为**数组** `[{"min": int, "max": int|null, "price": number}]`。
   - 依据：导入模板说明（`pricing.py:313`）、导入解析强制校验（`pricing.py:425-432`）、前端表单提交（`PricingRuleModal.vue:323,371`）**三处已是数组**；仅结算计算（`billing.py:1293`）读对象 → 改动面 1 处 vs 3 处。
   - 存量风险：库中 `json_typeof(tiers)` 实测 `array=0, object=0, json_null=13, sql_null=1`，**无数组/对象存量数据**，无需数据迁移。
6. **存量不一致记录处置**：提供**检出 + 重置为 `pending`** 的处置路径（供运维按需触发，或由详情页 `/regenerate-detail` 单独重生成）；不在本任务做自动批量重生成（避免触发外部 MySQL 批量查询、以及再次被清理任务影响的连锁反应）。
   - 现状：4 条记录（`invoice_35..38`，2026-07）处于「completed 但文件已删」。

## Open Questions

（无 —— 上述 6 项决策已闭合规划期的全部待决问题。）

## Notes

- 本任务为复杂任务，需 `design.md`（技术设计）与 `implement.md`（执行计划）后方可 `task.py start`。
- 相关 spec：`spec/backend/file-storage.md`（本次新增）、`spec/backend/import-export.md`、`spec/guides/cross-layer-thinking-guide.md`。
