# 文件存储契约（发票明细 / 本地产物）

> 本地文件落盘路径的解析规则，以及「DB 状态 ↔ 磁盘实体」一致性要求。

## Scope / Trigger

- 触发：新增或修改任何把文件写入本地磁盘的端点/后台任务（结算单明细 Excel、导入导出产物、头像等）
- 强制深度理由：**环境配置键** + **跨层契约**（DB 状态 ↔ 文件系统实体）+ 部署行为差异

---

## Signatures

### 配置键

```python
# backend/app/config.py (Settings)
file_storage_path: str = "./uploads"        # 默认值；环境变量 FILE_STORAGE_PATH 覆盖
```

### 路径解析

```python
base = getattr(settings, "file_storage_path", "./uploads")
abs_path = os.path.join(base, relative_path)   # relative_path 形如 invoices/2026/08/invoice_39.xlsx
```

### 已落地的相对路径格式与 DB 列

```
invoices/<YYYY>/<MM>/invoice_<invoice_id>.xlsx
```

| 列 | 内容 |
|---|---|
| `invoices.detail_file_path` | **相对**路径（不含存储根） |
| `invoices.detail_file_status` | `pending` / `generating` / `completed` / `failed` |

---

## Contracts

| 项 | 约定 |
|---|---|
| 配置来源 | 环境变量 `FILE_STORAGE_PATH`；未设置时回退 `./uploads` |
| **相对路径语义** | **相对进程 cwd** —— 既不是项目根，也不是 `backend/` |
| 生产要求 | `FILE_STORAGE_PATH` **必须为绝对路径** |
| DB 存储 | 只存相对路径；绝对前缀仅来自配置，禁止把绝对路径入库 |

---

## Validation & Error Matrix

| 条件 | 结果 |
|---|---|
| 文件不存在但 DB `detail_file_status=completed` | 下载端点返回 `404 明细文件不存在`（**状态与实体不一致**，需巡检/自愈） |
| 生成失败（外部库不可用） | `detail_file_status=failed`；允许 `POST /invoices/<id>/regenerate-detail` 重试 |
| 配置为相对路径且 cwd 变化 | 文件写入另一目录，**DB 仍为 `completed`** → 静默不一致（最难排查） |

---

## Good/Base/Bad Cases

- **Good**：`FILE_STORAGE_PATH=/srv/app/uploads`（绝对）→ 无论从哪个目录启动，产物都在同一处
- **Base**：开发环境未设置 → 落在 `<cwd>/uploads`；只要**启动目录固定**，行为自洽
- **Bad**：同一份代码，一次从项目根启动（写 `<repo>/uploads`），一次从 `backend/` 启动（写 `<repo>/backend/uploads`）
  → 两个目录各有一半产物，而 DB 里全部标记 `completed`

---

## Tests Required

| 断言点 | 说明 |
|---|---|
| 路径解析 | 给定 `FILE_STORAGE_PATH`，生成的绝对路径必须以该前缀开头 |
| 状态与实体一致 | 生成完成后，所有 `detail_file_status=completed` 的记录其文件必须存在 |
| 自愈能力 | 对「状态 completed 但文件缺失」的记录调用 `regenerate-detail` 后恢复可下载 |

> 现有覆盖：`backend/tests/integration/` 中的结算单明细用例已断言下载返回有效 xlsx；
> **缺口**：尚无「状态 completed ⇒ 文件存在」的一致性断言。

---

## Wrong vs Correct

### 1. 存储根目录

```python
# ❌ Wrong：相对默认值 + 依赖 cwd —— 换启动目录即换存储位置
base = "./uploads"

# ✅ Correct：显式绝对路径；相对值至少在启动时告警
base = Path(settings.file_storage_path)
if not base.is_absolute():
    logger.warning(
        "FILE_STORAGE_PATH is relative (%s); resolved against cwd %s", base, Path.cwd()
    )
```

### 2. 状态与实体

```python
# ❌ Wrong：先置状态，不校验文件真的落盘
invoice.detail_file_status = "completed"
await db.commit()

# ✅ Correct：落盘成功才置 completed；失败置 failed（而非停留在 generating）
try:
    write_file(abs_path)
except OSError:
    invoice.detail_file_status = "failed"
else:
    invoice.detail_file_status = "completed"
```

> **Warning（真实事故 2026-09-16 发现，根因 2026-09-17 定位并修复）**：
>
> **现象**：`invoice_39` 的 `detail_file_status=completed`、`detail_file_path=invoices/2026/08/invoice_39.xlsx`，
> 但 `backend/uploads/invoices/2026/` 是**空目录**。下载端点返回 `404 明细文件不存在`，而列表页仍显示「已完成」。
>
> **主因（置信度 97%）—— 清理任务无差别删除业务文件**：`tasks/file_cleanup.py` 的
> `cleanup_temp_files` 每日 03:00 以**存储根**为 `os.walk` 起点，且**无任何排除规则**，
> 把超过 7 天保留期的业务文件当「临时文件」删除。DB + 磁盘实测：
> 5 条 `completed` 记录中 **4 条文件已 MISSING**（`invoice_35..38`，全部为 7 月产物），
> **状态-实体不一致率 80%**；缺失文件**全部是 7 天前的产物**，与清理任务行为完全吻合。
> `avatars/`（用户头像）、`payment_proof`（付款凭证）、`discount_attachment`（减免附件）同属受害者。
>
> **次因 —— 存储根为相对路径**：`FILE_STORAGE_PATH` 未设置时回退 `./uploads`，相对进程 cwd 解析；
> 历史上曾从项目根启动过后端，留下 `uploads/invoices/2026/07/` 空目录树（项目根 `uploads/` 现仅空目录）。
> 文件位置随启动目录漂移，而 DB 状态不受影响 → 静默不一致。**此项是真实存在的独立缺陷，但不是本次事故的主因**。
>
> **修复**：
> 1. 清理范围**物理收缩**到 `<FILE_STORAGE_PATH>/temp/`（见下节「临时文件清理边界」），业务目录永不被扫描；
> 2. 启动期对相对路径 `logger.warning`（不阻断启动）；
> 3. 落盘后二次确认文件存在且非空，失败置 `failed`；
> 4. 提供 `backend/scripts/check_detail_files.py --detect / --reset-pending` 处置存量不一致记录。

---

## 临时文件清理边界（清理任务的范围契约）

### Scope / Trigger

- 触发：修改 `backend/app/tasks/file_cleanup.py`，或新增任何写入 `<FILE_STORAGE_PATH>` 的文件生产者
- 强制深度理由：**数据丢失级事故**（业务凭证被当临时文件删除，且 DB 状态不随之变化）

### Signatures

```python
# backend/app/tasks/file_cleanup.py
TEMP_SUBDIR = "temp"          # 唯一被清理的目录：<FILE_STORAGE_PATH>/temp/
RETENTION_DAYS = 7            # 保留期

async def cleanup_temp_files() -> None
```

### Contracts

| 项 | 约定 |
|---|---|
| **被清理范围** | `<FILE_STORAGE_PATH>/temp/` 子树**唯一**。`os.walk` 的根**必须**是该目录，不得是存储根 |
| **业务目录（永不清除）** | `invoices/**`、`avatars/**`、`<YYYY>/<MM>/**`（通用上传：付款凭证 / 减免附件） |
| `temp/` 不存在 | 记 info 日志并 `return` —— **不遍历存储根、不执行任何删除** |
| 空目录清理 | 同样只作用于 `temp/` 子树 |
| 软链接防御 | `temp_dir.resolve()` 必须位于 `<storage>.resolve()` 之下，否则记 error 并 `return` |

> **设计依据（为何用「物理隔离」而非「白名单豁免」）**：`uploads/` 下**不存在任何临时文件生产者**
> （已 grep 全后端确认），三类现有目录全为业务数据。若采用「全量扫描 + 排除 `invoices/`、`avatars/`」
> 的白名单方案，**通用上传目录（`<YYYY>/<MM>/`）中的付款凭证与减免附件仍会被删除** —— 白名单必然遗漏。
> 物理隔离使「临时」成为显式路径约定，而非靠穷举排除项维持正确性。

### Validation & Error Matrix

| 条件 | 结果 |
|---|---|
| `temp/` 下文件超过保留期 | **删除**（预期行为） |
| `temp/` 下文件在保留期内 | 保留 |
| `invoices/**`、`avatars/**`、`<YYYY>/<MM>/**` 下文件超过保留期 | **保留**（回归断言点） |
| `temp/` 不存在 | 无操作，记 info 日志 |
| `temp/` 解析后越出存储根（软链接） | 记 error，不清理 |

### Good/Base/Bad Cases

- **Good**：`temp/` 放 8 天前文件 + `invoices/2026/07/invoice_35.xlsx` 同为 8 天前 → 执行清理 → 前者删除、后者保留
- **Base**：`temp/` 不存在 → 执行清理 → 无任何文件变动
- **Bad（历史事故）**：以存储根为 `os.walk` 起点 → 结算明细、头像、凭证全部在 7 天后被删除，而 DB 仍标 `completed`

### Tests Required

| 断言点 | 说明 |
|---|---|
| 删该删的 | `temp/` 下过期文件被删除 |
| 留该留的 | `invoices/`、`avatars/`、`<YYYY>/<MM>/` 下过期文件**全部保留**；业务目录下的**空目录也保留** |
| 无目录即无操作 | `temp/` 缺失时不抛异常、不删除任何文件 |
| 越界防御 | 指向存储根之外的软链接被拒绝清理 |

> 现有覆盖：`backend/tests/unit/test_tasks.py::TestFileCleanupTask`（含上述四组断言）。
> 反向验证手法：临时把 `os.walk` 根改回存储根 → 该测试立即以「业务文件被清理任务误删」失败。

### Wrong vs Correct

```python
# ❌ Wrong：以存储根为遍历起点 —— 「临时文件」与「业务文件」无法区分
upload_dir = settings.file_storage_path
for root, dirs, files in os.walk(upload_dir):
    if file_mtime < cutoff_timestamp:
        os.remove(file_path)

# ✅ Correct：只管显式临时目录；目录不存在即无操作
temp_dir = Path(settings.file_storage_path) / TEMP_SUBDIR
if not temp_dir.exists():
    logger.info("临时目录不存在（%s），无文件可清理", temp_dir)
    return
resolved_temp = temp_dir.resolve()
try:
    resolved_temp.relative_to(Path(settings.file_storage_path).resolve())
except ValueError:
    logger.error("临时目录越出存储根，拒绝清理：%s", resolved_temp)
    return
for root, dirs, files in os.walk(resolved_temp):
    ...
```
