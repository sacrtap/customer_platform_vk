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

> **Warning（真实事故 2026-09-16）**：`invoice_39` 的 `detail_file_status=completed`、
> `detail_file_path=invoices/2026/08/invoice_39.xlsx`，但 `backend/uploads/invoices/2026/` 是**空目录**，
> 而项目根 `uploads/invoices/2026/07/` 留有 5 天前的文件 —— 证明历史上曾从不同 cwd 启动后端，
> 产物分裂到两个 `uploads/`。下载端点返回 404，而列表页仍显示「已完成」。
> 当时以 `regenerate-detail` 重建文件消除症状；**根因（相对路径配置）需显式设置 `FILE_STORAGE_PATH` 才能根治**。
