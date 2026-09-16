# 技术设计：遗留项修复

> 对应 `prd.md` 的 R1–R6 与 AC1–AC10。四个缺陷按「单一 owner / 物理隔离 / 显式配置」三条原则修复。

---

## 1. 总体策略

| 缺陷 | 策略 | 核心原则 |
|---|---|---|
| B 清理任务删业务文件 | 清理范围**物理收缩**到专用 `temp/` 子目录 | 物理隔离优于白名单约定 |
| B′ 存储路径随 cwd 漂移 | 启动期校验 + 日志告警 + 文档化语义 | 显式配置优于隐式默认 |
| B″ 状态与实体脱节 | 生成成功才置 `completed`；提供检出/处置脚本 | 状态必须可由实体验证 |
| C `tiers` 形态冲突 | 全链路收敛为**数组**，后端单一归一化 owner | 单一 owner 优于多处各自解析 |
| D `tiers` 键名三套 | 统一 `min` / `max` / `price` | 同上 |
| A 后端「折扣」文案 | 6 处用户可见 + 2 处注释统一为「减免」 | 术语单一来源 |

**顺序**：B（数据安全，最高优先）→ C/D（契约）→ A（文案，低风险）。

---

## 2. 缺陷 B：清理任务收缩（R1，最高优先）

### 2.1 清理范围收缩

`backend/app/tasks/file_cleanup.py` 改为只清理**专用临时子目录**：

```python
TEMP_SUBDIR = "temp"          # 唯一被清理的目录：<FILE_STORAGE_PATH>/temp/
RETENTION_DAYS = 7

async def cleanup_temp_files():
    storage_root = Path(settings.file_storage_path)
    temp_dir = storage_root / TEMP_SUBDIR

    if not temp_dir.exists():
        logger.info("📁 临时目录不存在（%s），无文件可清理", temp_dir)
        return

    # 仅遍历 temp_dir —— 不再 os.walk(storage_root)
    ...
    # 空目录清理同样只作用于 temp_dir 及其子目录
```

**关键约束**：
- `os.walk` 的根必须是 `temp_dir`，**不得**再以 `storage_root` 为根
- 需要防御：若 `temp_dir` 被误配为软链接指向外部，应拒绝（`Path.resolve()` 后确认仍在 `storage_root` 下）
- 保留期常量与日志格式维持（审计连续性）

**验证要点（AC1/AC2）**：
- 在 `temp/` 放一个 8 天前的文件 → 被删
- 在 `invoices/`、`avatars/`、`<YYYY>/<MM>/` 各放一个 8 天前的文件 → **全部保留**

### 2.2 存储根路径显式化（R2）

`config.py` 默认值保持 `./uploads`（开发友好），在应用启动处增加一次性校验：

```python
# backend/app/main.py（create_app 内，注册静态目录之前）
storage = Path(settings.file_storage_path)
if not storage.is_absolute():
    logger.warning(
        "FILE_STORAGE_PATH 为相对路径（%s），将相对进程 cwd（%s）解析。"
        "生产环境请设置为绝对路径，否则从不同目录启动会导致文件写入不同位置。",
        storage, Path.cwd(),
    )
```

- 同步更新 `.env.example`（若存在）与 `README` 的配置说明
- 该告警为 **warning 而非 fatal**：不阻断开发启动，但使问题可见（符合 AC3）

### 2.3 状态与实体一致性（R3）

**写入侧**（`services/invoice_excel.py`）：

```python
# 现行（需确认）：先置状态还是先落盘？
# 目标：落盘成功后置 completed；异常置 failed（不得停留在 generating）
try:
    workbook.save(abs_path)
    _assert_file_written(abs_path)        # 二次确认文件存在且非空
except Exception:
    invoice.detail_file_status = "failed"
    raise
else:
    invoice.detail_file_status = "completed"
    invoice.detail_file_path = rel_path
```

**检出与处置**（AC4）：新增运维脚本 `backend/scripts/check_detail_files.py`：

| 模式 | 行为 |
|---|---|
| `--detect`（默认） | 扫描 `detail_file_status='completed'` 的记录，逐个检查磁盘文件是否存在，输出不一致清单（id / invoice_no / path / 状态） |
| `--reset-pending` | 将不一致记录重置为 `pending`（等待重新生成），并打印受影响 id |

- 选择**脚本**而非新端点：无需新增权限码与前端入口，符合「供运维按需触发」的定位
- 脚本必须支持 `--dry-run`（先看结果再决定），且 `--reset-pending` 需显式传入才会写库

**当前已知不一致**：`invoice_35..38`（4 条，2026-07，文件已被删）→ 由该脚本处置，不在本任务自动重生成（决策 6）。

---

## 3. 缺陷 C + D：tiers 契约收敛（R4/R5）

### 3.1 目标契约（唯一形态）

```
DB / API / 前端表单 / 结算计算 —— 一致为：

tiers = [
  {"min": 0,    "max": 1000, "price": 10},
  {"min": 1001, "max": 5000, "price": 8},
  {"min": 5001, "max": null, "price": 5},
]
```

- `min` / `max`：**整数**用量边界；`max = null` 表示无上界
- `price`：单价（数值）
- 数组顺序即阶梯顺序；`null` 整体表示「无阶梯配置」

### 3.2 后端单一 owner

新建 `backend/app/utils/tiers.py`：

```python
class TierFormatError(ValueError):
    """tiers 结构非法"""

def normalize_tiers(raw: object | None) -> list[dict] | None:
    """把任意历史形态归一化为唯一形态；None/JSON-null → None"""
    # - None / "null" / {} → None
    # - list → 逐项校验 min/max/price 类型
    # - {"ranges": [...]} → 取 ranges（兼容历史对象形态）
    # - 其它 → raise TierFormatError

def parse_tiers_or_raise(raw, *, row_num: int | None = None) -> list[dict]:
    """供导入路径使用：把 TierFormatError 翻译为行级错误文案"""
```

**调用点改造**：

| 文件 | 现状 | 改为 |
|---|---|---|
| `services/billing.py:1293` | `tiers.get("ranges", [])` ❌ | `normalize_tiers(rule.tiers) or []` |
| `services/billing.py:1258` | `rule.tiers or {}` | 同上，避免 `{}` 假值 |
| `services/cost_calc.py:385-390` | `t.get("min_quantity", 0)` ❌ | `t.get("min", 0)`，并按 `min` 排序 |
| `services/analytics.py:2287-2289` | `isinstance(tiers, list)` + `t.get("threshold")` ❌ | `normalize_tiers` + 取最后一项的 `max` |
| `routes/billing/pricing.py:425-434` | 就地校验 | 调用 `parse_tiers_or_raise`（保留行级错误文案风格） |

**`analytics.py` 的语义澄清**：现行 `tiers[-1].get("threshold", 0)` 意图为「取最后一个阶梯的上界作为预期用量参考」。改为 `last.get("max")`；若为 `null`（不限量）则回退到现有 fallback（近 30 天日均 × 30）。**该分支只影响预测展示，不参与账单金额**。

### 3.3 非法输入必须可控失败（AC6）

`calculate-items` 路径（`services/billing.py`）捕获 `TierFormatError` → 返回 `40002` 业务错误（可读文案），不得让 `AttributeError` 冒泡成 500。

### 3.4 前端解析收敛（R5，AC8）

新建 `frontend/src/utils/tiers.ts`：

```ts
export interface Tier { min: number; max: number | null; price: number }

/** 唯一解析实现：后端保证已是数组，此处仅做容错与类型收敛 */
export function parseTiers(raw: unknown): Tier[]
```

**替换三处重复实现**：
- `utils/invoiceFormatters.ts:115`（导出函数，改为 re-export 或直接调用共享实现）
- `views/billing/components/PricingRuleModal.vue:418`（删除本地实现）
- `views/billing/PricingRules.vue:410`（`formatTiersTooltip` 内部改用共享解析）

**类型修正**：
- `types/index.ts:203`：`tiers: Record<string, unknown> | null` → `tiers: Tier[] | null`
- `api/billing.ts:158`：收敛为 `Tier[]`（去除 `Record<string, unknown>` 分支）

---

## 4. 缺陷 A：后端文案统一（R6）

| 位置 | 现状 | 改为 |
|---|---|---|
| `routes/billing/invoices.py:1259` | 导出表头 `折扣金额` | `减免金额` |
| `routes/billing/invoices.py:1365` | docstring `discount_amount (可选) - 折扣金额（元，默认 0）` | `减免金额（元，默认 0）` |
| `routes/billing/invoices.py:1473` | `折扣金额不能为负数` | `减免金额不能为负数` |
| `routes/billing/invoices.py:1476` | `折扣金额格式错误` | `减免金额格式错误` |
| `routes/billing/invoices.py:1479` | `折扣金额不能大于结算金额` | `减免金额不能大于结算金额` |
| `routes/billing/invoices.py:1595` | 模板说明 `可选：折扣金额（元）` | `可选：减免金额（元）` |
| `models/billing.py:126` | 注释 `# 折扣申请时间` | `# 减免申请时间` |
| `middleware/audit.py:91` | 注释 `# 生成/折扣/删除保持…` | `# 生成/减免/删除保持…` |

**硬约束（不可违反）**：
- 模板第 2 行说明**必须**以 `必填：` / `可选：` 开头（`utils/excel_import.py::_is_template_note_row` 据此判定）
- **列名与列顺序不变**（否则已下载模板的存量导入会错列）
- 表头文案可改，但不得改变列数

---

## 5. 影响面 / 风险 / 回滚

| 项 | 评估 |
|---|---|
| DB 迁移 | **无**（`tiers` 无数组/对象存量：`array=0, object=0`） |
| 前端回归面 | 定价规则列表 tooltip、规则弹窗编辑回填、结算单生成弹窗预览（3 处解析合并后须逐一验证） |
| 清理任务变更 | 由「删业务文件」变为「只删 temp/」——**纯收紧**，不会新增删除行为 |
| 存量不一致记录 | 仅通过脚本显式处置，不在代码路径自动触发 |
| 回滚 | 各缺陷改动互相独立；清理任务与 tiers 归一化可单独回退 |

---

## 6. 待实现确认项（实现阶段首个动作）

1. `services/invoice_excel.py` 中 `detail_file_status` 的置位时机与异常分支（确认是否已满足 2.3 的目标语义）
2. `backend/scripts/` 是否已有同类运维脚本（命名与 `argparse` 风格对齐）
3. `.env.example` / `README` 是否存在、需同步哪些配置说明
