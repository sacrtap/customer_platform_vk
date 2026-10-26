# 数据备份功能 — 验收边界与最终验证结果

任务：`10-26-data-backup` ｜ 分支：`feat/data-backup`

## 1. 功能范围（验收边界）

在「数据清空」菜单下新增「数据备份」菜单与页面（路由 `/system/backup`，权限 `system:database_backup`）：

| # | 需求 | 实现位置 |
|---|---|---|
| 1 | 菜单 + 页面 | `AppSidebar.vue`、`router/index.ts`、`useAppLayout.ts`、`views/system/BackupManagement.vue` |
| 2 | 每日数据库自动备份（可自定义时间） | `backup_schedule_configs` 表 + `tasks/backup.py::register_backup_daily` + `scheduler.py` 启动注册 + `PUT /schedule` |
| 3 | 每 5 天清理超过 5 天的备份，清理前校验最近 5 天备份存在且有效 | `BackupService.execute_cleanup` / `validate_recent_backups` + `scheduler.py` 的 `IntervalTrigger(days=5)` |
| 4 | 全过程留痕（备份/清理/恢复） | `backup_records` 表，四类 `task_type` |
| 5 | 选择指定备份在线恢复（前端二次确认 + 输入备份日期，后端二次校验） | `routes/backup.py::restore_backup` + `BackupManagement.vue` 恢复弹框 |

**不在本次范围**：`deploy/docker-compose.yml` 的 dockerfile 路径错位（既有问题，CI 的 `deploy.yml` 路径正确）；
备份文件的异地/对象存储归档；恢复后的自动服务重启。

## 2. 改动文件清单

后端新增：`app/models/backup.py`、`app/services/backup_service.py`、`app/routes/backup.py`、
`app/tasks/backup.py`、`alembic/versions/c9d0e1f2a3b4_add_backup_feature.py`、
`tests/unit/test_backup_service.py`、`tests/unit/test_backup_routes.py`

后端修改：`app/config.py`、`app/main.py`、`app/models/__init__.py`、`app/tasks/scheduler.py`、
`scripts/seed.py`、`tests/_test_data.py`

部署/配置：`.env.example`、`deploy/docker/Containerfile`（+`postgresql-client`）

前端新增：`frontend/src/views/system/BackupManagement.vue`
前端修改：`AppSidebar.vue`、`router/index.ts`、`composables/useAppLayout.ts`

## 3. 最终验证结果

### 3.1 静态检查

| 检查 | 命令 | 结果 |
|---|---|---|
| Lint | `ruff check app/` | All checks passed |
| 类型 | `pyright`（仅覆盖 `app/`） | 0 errors 0 warnings |
| 前端类型 | `pnpm type-check` | 0 errors |
| 测试数据一致性 | `tests/unit/test_test_data_consistency.py` | passed |

### 3.2 单元测试

| 文件 | 结果 |
|---|---|
| `tests/unit/test_backup_service.py` | 25 passed |
| `tests/unit/test_backup_routes.py` | 25 passed |
| **全量 `pytest tests/`** | **1360 passed**（472.82s） |

### 3.3 数据库迁移

- `alembic upgrade head` → `c9d0e1f2a3b4` 已应用到本地库
- `scripts/check_schema_drift.py` → PASSED
- 已验证落库：两表、两索引、`backup_schedule_configs` 默认行、权限种子 `system:database_backup`、超管角色关联

### 3.4 真实链路冒烟（本地 PG + 本地 pg_dump/pg_restore，`BACKUP_DIR=/tmp/backup_api`）

| 场景 | 结果 |
|---|---|
| 手动备份 | 315KB dump 落盘，记录 `pending → running → success`，`file_path`/`file_size_bytes` 写入 |
| `validate_recent_backups` 正场景 | 窗口内有效备份 → `passed=True` |
| 清理正场景 | 窗口内有效 → 删除 1 个超期文件 |
| 清理负场景 | 窗口内存在损坏文件 → **拒绝删除**，`retention_check_passed=False` |
| 恢复（错日期） | API 400，不创建记录 |
| 恢复（正确日期） | restore 记录落库并到 `success`；源 dump `pg_restore --list` exit 0（未被破坏） |
| 下载 | `Content-Disposition` 含文件名，字节与源文件一致 |
| 定时配置 | `PUT /schedule` 后 DB 中 `enabled=true, backup_time='03:30', updated_by=43` |

### 3.5 前端浏览器验证（dev server 5173 + 后端 8000）

| 场景 | 结果 |
|---|---|
| 菜单显隐 | 超管侧边栏「数据清空」下方可见「数据备份」 |
| 页面渲染 | 警告横幅、定时备份配置区、立即备份、任务记录表格均正常 |
| 保存配置 | 「配置已保存」，DB 校验通过 |
| 立即备份 | 新记录 id=5 落库并到「成功」，文件大小 315.0 KB |
| 恢复弹框 | 标题/警告文案/日期输入框（placeholder `YYYY-MM-DD`）/危险按钮齐全 |
| **错日期前端拦截** | 提示「输入日期与该备份日期不一致」，弹窗不关闭、不提交 |
| 正确日期提交 | 「恢复任务已创建」，restore 记录 id=6 落库并到「成功」 |

## 4. 修复的关键缺陷（本次会话）

**恢复链路污染源备份记录 + restore 留痕不落库**。三层根因，依次修复：

1. **同一 session 在表被 DROP 后不可用** — `pg_restore --clean --if-exists` DROP 并重建全库对象（含 `backup_records`），
   pending 留痕行随之消失；ORM `UPDATE` 抛 `StaleDataError: ... 0 were matched`，session 转入
   `PendingRollbackError`，其 greenlet 上下文已死，再 `await self.db.rollback()` 报
   `greenlet_spawn has not been called`。
   → 修复：`execute_restore` 先取字段快照，`_run_pg_restore` 之后的终态写入改用 `session_factory`
   新开短会话（`_write_final_state`）；`rowcount=0` 时按快照 `INSERT` 重插同 id 终态行。
2. **naive/aware 混用** — 重插时把 `cst_now()`（aware）写给 `TimestampMixin` 的 naive 列
   `created_at/updated_at`，asyncpg 在 Cython 层抛 `can't subtract offset-naive and offset-aware datetimes`
   （堆栈无 Python 帧）。
   → 修复：显式 `.replace(tzinfo=None)`。

经验已沉淀至 `.trellis/spec/backend/database-guidelines.md`（新增两节 + 两条 Forbidden Pattern）。

## 5. 已知非缺陷现象（排查时勿误判）

`pg_dump` 捕获的是 dump 执行时刻的库快照。备份任务「先 `_mark_running` 再 `pg_dump`」，
因此 dump 内该留痕行恒为 `running`、`completed_at IS NULL`。**恢复该备份后列表显示「执行中」是快照语义的固有正确行为**，
已用 `pg_restore --data-only --table=backup_records` 核对 dump 原始内容证实。

## 6. 未覆盖 / 需 CI 侧验证

- **镜像构建**：本机 docker 不可用，未执行 `docker build -f deploy/docker/Containerfile backend/`。
  `postgresql-client` 的安装由 CI `deploy.yml` 验证。
- **定时任务真实触发**：仅验证了注册（`next_run_time` 计算正确，`2026-10-27T02:00:00+08:00`）与
  `IntervalTrigger(days=5)` 的清理 job 注册，未等待真实 cron 到点。
- **非超管门控的前端实测**：路由 `meta.requiresPermission` 与后端 `@require_permission` 双层已就位；
  因 `hasPermission` 对超管恒真，未在浏览器构造非超管身份实测（单元测试已覆盖权限拒绝分支）。
