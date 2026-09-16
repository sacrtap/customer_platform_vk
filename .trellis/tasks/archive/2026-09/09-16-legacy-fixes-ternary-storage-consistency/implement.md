# 执行计划：遗留项修复

> 对应 `prd.md`（AC1–AC10）与 `design.md`。按数据安全优先级排序：**先止血（清理任务）→ 再契约（tiers）→ 后文案**。

---

## 阶段 0：前置确认（实现首步，勿跳过）

- [ ] 读 `services/invoice_excel.py`：确认 `detail_file_status` 的置位时机与异常分支现状
- [ ] 查 `backend/scripts/` 现有运维脚本的命名与 `argparse` 风格（新脚本对齐）
- [ ] 确认 `.env.example` / `README` 是否存在、需同步的配置说明段落
- [ ] 若任一项推翻 `design.md` 的假设 → 回到 planning 修订设计

---

## 阶段 1：清理任务收缩 + 存储路径显式化（R1/R2 → AC1/AC2/AC3）

### 1.1 `backend/app/tasks/file_cleanup.py`

- [ ] 引入 `TEMP_SUBDIR = "temp"`；`os.walk` 根由 `settings.file_storage_path` 改为 `<storage>/temp/`
- [ ] `temp_dir` 不存在时直接返回（不再遍历整个存储根）
- [ ] 空目录清理同样只作用于 `temp/` 子树
- [ ] 增加软链接防御：`temp_dir.resolve()` 必须仍位于 `<storage>.resolve()` 之下
- [ ] 保留既有日志格式与 `retention_days = 7`

### 1.2 `backend/app/main.py`

- [ ] `create_app` 内、注册 `/uploads/` 静态目录之前，增加「相对路径告警」（`logger.warning`，不阻断启动）

### 1.3 配置说明

- [ ] 同步 `.env.example` / `README`：`FILE_STORAGE_PATH` 语义（相对进程 cwd）+ 生产须绝对路径

### 验证（AC1/AC2/AC3）

- [ ] 单元/集成测试：在 `temp/` 放过期文件 → 被删；在 `invoices/`、`avatars/`、`<YYYY>/<MM>/` 各放过期文件 → **全部保留**
- [ ] 手工：`cleanup_temp_files()` 在 `temp/` 不存在时执行 → 无删除、无异常
- [ ] 手工：以相对路径启动 → 日志出现告警；设为绝对路径 → 任意 cwd 下产物位置一致
- [ ] 端到端：跑一次清理任务后，`GET /billing/invoices/39/download-detail` 仍返回有效 xlsx

---

## 阶段 2：状态与实体一致性（R3 → AC4）

### 2.1 写入侧 `services/invoice_excel.py`

- [ ] 落盘成功后再置 `completed`；异常置 `failed`（不得停留 `generating`）
- [ ] 落盘后二次确认文件存在且非空

### 2.2 运维脚本 `backend/scripts/check_detail_files.py`（新建）

- [ ] `--detect`（默认）：列出「状态 `completed` 但文件缺失」的记录（id / invoice_no / path）
- [ ] `--reset-pending`：将不一致记录重置为 `pending`；支持 `--dry-run`
- [ ] 输出统计（一致数 / 不一致数），退出码：有不一致且未处置 → 非 0

### 验证（AC4）

- [ ] 对已知 4 条不一致记录（`invoice_35..38`）运行 `--detect` → 全部被列出
- [ ] `--dry-run --reset-pending` 不写库；`--reset-pending` 后 DB 状态变为 `pending`，`--detect` 不再报它们
- [ ] 处置后 `POST /billing/invoices/<id>/regenerate-detail` 可重建文件并回到 `completed`

---

## 阶段 3：tiers 后端契约收敛（R4 → AC5/AC6/AC7）

### 3.1 新建 `backend/app/utils/tiers.py`

- [ ] `TierFormatError(ValueError)`
- [ ] `normalize_tiers(raw) -> list[dict] | None`：`None`/JSON-null/`{}` → `None`；`list` → 逐项校验；`{"ranges": [...]}` → 兼容取 `ranges`；其它 → raise
- [ ] `parse_tiers_or_raise(raw, row_num=None) -> list[dict]`：翻译为行级错误文案

### 3.2 消费点改造

- [ ] `services/billing.py:1258-1259,1293`：`_calculate_tiered_price` 入参改为数组（`normalize_tiers` 结果），函数内 `ranges` 变量改名/改写
- [ ] `services/billing.py` 的 `calculate-items` 调用链：捕获 `TierFormatError` → `40002` 业务错误
- [ ] `services/cost_calc.py:385-390`：`min_quantity` → `min`，排序键同步
- [ ] `services/analytics.py:2287-2289`：改用 `normalize_tiers`；取最后一项 `max`，`null` 时走既有 fallback
- [ ] `routes/billing/pricing.py:425-434`：改用 `parse_tiers_or_raise`（保留现有行级错误文案风格）

### 验证（AC5/AC6/AC7）

- [ ] 通过**导入端点**创建一条 tiered 规则（模板示例即数组形态）→ `POST /billing/invoices/calculate-items` 返回 `code=0` 且按阶梯计价正确（**不再 500**）
- [ ] `tiers` 传字符串 / 缺键 / 非法类型 → 返回业务错误码（非 500），文案可读
- [ ] `{"ranges":[...]}` 历史对象形态 → 被 `normalize_tiers` 兼容（不 500）
- [ ] `grep -rn "min_quantity\|threshold" backend/app` → 不再有第二套键名

---

## 阶段 4：tiers 前端收敛（R5 → AC8）

### 4.1 新建 `frontend/src/utils/tiers.ts`

- [ ] `export interface Tier` + `export function parseTiers(raw: unknown): Tier[]`

### 4.2 替换三处重复实现

- [ ] `utils/invoiceFormatters.ts:115` → 改为复用共享实现（保留原导出名以免破坏调用点，或统一改名后同步调用点）
- [ ] `views/billing/components/PricingRuleModal.vue:418` → 删除本地 `parseTiers`，改用共享实现
- [ ] `views/billing/PricingRules.vue:410` → `formatTiersTooltip` 内部改用共享解析

### 4.3 类型修正

- [ ] `types/index.ts:203`：`tiers: Tier[] | null`
- [ ] `api/billing.ts:158`：收敛为 `Tier[]`

### 验证（AC8）

- [ ] `grep -rn "function parseTiers\|const parseTiers" frontend/src` → **仅 1 处**（共享实现）
- [ ] 浏览器实跑：定价规则列表 tooltip 正常显示阶梯；规则弹窗编辑回填正确；结算单生成弹窗预览阶梯渲染与后端返回一致
- [ ] `pnpm type-check` 通过

---

## 阶段 5：后端文案统一（R6 → AC9/AC10）

- [ ] `routes/billing/invoices.py`：1259 / 1365 / 1473 / 1476 / 1479 / 1595 六处「折扣」→「减免」
- [ ] `models/billing.py:126`、`middleware/audit.py:91` 注释同步
- [ ] **保持**模板第 2 行 `必填：`/`可选：` 前缀；**不动**列名与列顺序

### 验证（AC9/AC10）

- [ ] `grep -rn "折扣" backend/app` → 无残留（或仅剩有意保留项，并列出理由）
- [ ] 下载导入模板 → 第 2 行仍以 `可选：` 开头，列名/列序不变
- [ ] 模板回灌导入：说明行未被当作数据行（无虚假行级错误）
- [ ] 导出 Excel 表头为「减免金额」

---

## 阶段 6：整体验证与收尾

- [ ] 后端：`cd backend && .venv/bin/python -m pytest tests/ -x -q`（覆盖率门禁 ≥50%）
- [ ] 后端 lint：`.venv/bin/python -m ruff check app/`
- [ ] 前端：`cd frontend && pnpm type-check` + `eslint` 改动文件
- [ ] 写入性验收产物登记（导入的 tiered 规则、脚本处置的记录）并在结束前恢复或说明保留理由
- [ ] 更新 `spec/backend/file-storage.md`（若实现细节与设计有偏差）
- [ ] 更新 `spec/backend/import-export.md`（若模板文案/契约有变）
- [ ] 归档任务

---

## 验收映射表

| AC | 覆盖阶段 | 关键验证手段 |
|---|---|---|
| AC1 清理不删业务文件 | 1.1 | 测试：temp/ 删、其余留 |
| AC2 明细 7 天后仍可下载 | 1.1 + 2.1 | 跑清理任务后下载 39 号 |
| AC3 相对路径告警 / 绝对路径一致 | 1.2 + 1.3 | 启动日志 + 跨 cwd 对比 |
| AC4 状态-实体一致性可处置 | 2.2 | `check_detail_files.py --detect/--reset-pending` |
| AC5 tiered 导入后结算不再 500 | 3.1 + 3.2 | 导入规则 → calculate-items |
| AC6 非法 tiers 可控失败 | 3.1 + 3.2 | 畸形输入 → 40002 |
| AC7 全链路形态/键名一致 | 3.1–3.2 + 4.2–4.3 | grep 无第二套键名 |
| AC8 解析实现收敛为 1 处 | 4.2 | grep + 浏览器回归 |
| AC9 后端文案无「折扣」且模板契约不变 | 5 | grep + 模板回灌 |
| AC10 保留项有理由说明 | 5 | PR 说明列出 |

---

## 子代理上下文清单（`implement.jsonl` / `check.jsonl` 用）

实现/检查子代理需预读的 spec：

```jsonl
{"file": ".trellis/spec/backend/file-storage.md", "reason": "存储路径语义与状态一致性契约（本任务 R1–R3 的判定依据）"}
{"file": ".trellis/spec/backend/import-export.md", "reason": "导入模板说明行前缀契约、行级错误文案风格、权限码清单（R6/AC9 修改对象）"}
{"file": ".trellis/spec/guides/cross-layer-thinking-guide.md", "reason": "语义重命名传播与宽严解析不一致两类清单（本任务 C/A 的方法论依据）"}
{"file": ".trellis/spec/backend/database-guidelines.md", "reason": "会话/session 使用规范与既有 JSON 字段处理先例"}
```
