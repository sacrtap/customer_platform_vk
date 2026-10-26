# 数据备份功能执行计划

## Context

需求：在「数据清空」侧边菜单下方新增「数据备份」菜单项与页面；实现每日数据库自动备份，支持自定义定时备份时间；每 5 天清理一次超过 5 天的备份，清理前必须先校验最近 5 天的备份文件存在且有效；全过程任务记录留痕（备份/清理/恢复）。页面支持选择指定备份进行恢复（在线恢复 `pg_restore --clean --if-exists`，破坏性操作，前端二次确认 + 输入备份日期、后端二次校验日期匹配）。

技术决策（已确认）：备份格式 `pg_dump -Fc`（custom 二进制），有效性校验用 `pg_restore --list`（exit 0 即有效）；清理用独立 `IntervalTrigger(days=5)` 任务；页面含定时配置区、任务记录列表、手动「立即备份」按钮、备份文件下载、选择指定备份恢复（在线 `pg_restore --clean --if-exists -d`，不强制停服，提示低峰期 + 恢复后重启刷新连接池）；恢复为破坏性操作，前端 `Modal.confirm` + 输入备份日期双保险，后端校验日期匹配。

复刻现有「每日自动同步」整套模式：`sync_schedule_configs` 配置表 + `register_sync_daily_auto` 动态注册 + `routes/sync_schedule.py` GET/PUT 立即生效；留痕复刻 `SyncTask`(主表) 模式。

部署前提：app 镜像 `deploy/docker/Containerfile` 当前未装 postgresql-client，pg_dump/pg_restore 不可用——本方案在镜像中加装 `postgresql-client`（唯一可行方案：app 容器通过 compose 网络连 `db:5432`，备份文件落 `app_uploads` 命名卷）。

## Approach

### 1. 配置层：config.py 增备份配置项

文件 `backend/app/config.py`，在 `Settings` 类（`:10-99`）内、Redis 配置（`:76-77`）后新增 3 个字段：

```python
# 数据备份配置
backup_dir: str = "/app/uploads/backups"          # 备份文件目录（挂载于 app_uploads 命名卷）
backup_retention_days: int = 5                     # 备份保留天数（超过即清理）
backup_cleanup_interval_days: int = 5              # 清理任务执行间隔（天）
```

同步在仓库根 `.env.example` 增 `BACKUP_DIR`、`BACKUP_RETENTION_DAYS`、`BACKUP_CLEANUP_INTERVAL_DAYS` 三个键（带注释与默认值）。

### 2. 容器层：Containerfile 加装 postgresql-client

文件 `deploy/docker/Containerfile`，`apt-get install` 块（`:16-23`）新增 `postgresql-client`（提供 `pg_dump`/`pg_restore`，备份与恢复共用）。此为唯一可行方案：app 容器已通过 compose 网络 `db:5432` 连库，pg_dump/pg_restore 直连，备份文件落 `/app/uploads/backups/`（`app_uploads` 卷，持久化、容器重建不丢）。

### 3. 模型层：新建 backup 模型并注册

新文件 `backend/app/models/backup.py`，定义两表，均继承 `Base, TimestampMixin`（无软删，与 `SyncScheduleConfig`/`SyncTask` 一致，`base.py:13-17`）：

**BackupScheduleConfig**（仿 `SyncScheduleConfig`，`models/sync_schedule.py:9-42`）：
```python
class BackupScheduleConfig(Base, TimestampMixin):
    __tablename__ = "backup_schedule_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="任务名称（单行 daily_backup）")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否启用每日备份")
    backup_time: Mapped[str] = mapped_column(String(5), nullable=False, default="02:00", server_default="02:00", comment="备份时间 HH:MM")
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, comment="更新人")
```

**BackupRecord**（留痕单表，`task_type` 区分 backup/cleanup/restore，仿 `SyncTask` `models/sync_task.py:13-55`）：
```python
class BackupRecord(Base, TimestampMixin):
    __tablename__ = "backup_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="daily_backup/manual_backup/cleanup/restore")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="pending/running/success/failed")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备份文件相对路径（cleanup 为空；restore 为源备份路径）")
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="文件大小")
    backup_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="备份对应业务日期（cleanup 为空；restore 取源备份日期）")
    retention_check_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="仅 cleanup：近5天校验结果")
    deleted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="仅 cleanup：删除文件数")
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="耗时")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败/详情")
    operator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, comment="操作人（定时为 NULL）")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

注册：`backend/app/models/__init__.py` 的 isort-off 导入块（`:14-30`）加 `from . import backup`，`__all__`（`:33-53`）加 `"backup"`、`"BackupScheduleConfig"`、`"BackupRecord"`。供 alembic autogenerate 发现。

### 4. 迁移：建表 + 权限种子 + 默认配置行

新文件 `backend/alembic/versions/<新 revision>_add_backup_feature.py`，`down_revision` 取当前 head（`z5a6b7c8d9e0`，见 glob 最新迁移）。模板完全仿 `u0v1w2x3y4z5_add_sync_execution_details.py`。

`upgrade()`：
1. `op.create_table("backup_schedule_configs", ...)`（字段同模型，含 `created_at`/`updated_at` server_default now()、`UniqueConstraint("task_name")`，仿迁移模板 `:82-117`）
2. `op.bulk_insert(sa.table("backup_schedule_configs", sa.column("task_name",sa.String), sa.column("enabled",sa.Boolean), sa.column("backup_time",sa.String)), [{"task_name":"daily_backup","enabled":False,"backup_time":"02:00"}])` —— 注意 BackupScheduleConfig 无 sync_mode 字段，bulk_insert 只含 task_name/enabled/backup_time
3. `op.create_table("backup_records", ...)`（字段同模型，含索引 `idx_backup_records_type_date` on `["task_type","backup_date"]`、`idx_backup_records_status` on `["status"]`）
4. 权限种子（仿 `:139-165`）：
```python
op.bulk_insert(sa.table("permissions", sa.column("code",sa.String), sa.column("name",sa.String), sa.column("description",sa.String), sa.column("module",sa.String)),
    [{"code":"system:database_backup","name":"数据备份","description":"配置定时备份与清理、手动备份、下载备份、恢复备份","module":"system"}])
op.execute("""INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE r.name='超级管理员' AND p.code='system:database_backup' ON CONFLICT DO NOTHING""")
```
`downgrade()`：反向删 role_permissions → permissions → drop 两表（仿 `:168-182`）。

同步在 `backend/scripts/seed.py` 的 `ALL_PERMISSIONS`（`:44-140`）「系统管理」段（`:107-110` 后、其他模块前）加：
```python
("system:database_backup", "数据备份", "配置定时备份与清理、手动备份、下载备份、恢复备份", "system"),
```

### 5. 服务层：BackupService

新文件 `backend/app/services/backup_service.py`，构造注入仿 `SyncTaskService`（`sync_task_service.py:35-38`）：
```python
class BackupService:
    def __init__(self, db: AsyncSession):
        self.db = db
```

方法（全部 `await self.db.commit()` 显式提交，事务在调用方 `async with db_session.begin()` 或路由 `request.ctx.db_session`）：
- `get_or_create_schedule_config() -> BackupScheduleConfig`：仿 `_get_or_create_config`（`routes/sync_schedule.py:28-39`），单行 `daily_backup`
- `create_record(task_type: str, operator_id: int | None, file_path: str | None = None, backup_date: date | None = None) -> BackupRecord`：插 pending 记录（`started_at=cst_now()`；`backup_date` 默认 `cst_today()` 当 task_type 含 backup，restore 由调用方传源日期）、commit、refresh、返回
- `async execute_backup(record_id: int) -> BackupRecord`：核心——`pending→running`（commit）→ 调 `_run_pg_dump()` → 成功写 `file_path/file_size_bytes/duration_seconds/status=success/completed_at`，失败写 `status=failed/error_message`，`finally` commit。`operator_id` 已在 create 时写入
- `_run_pg_dump(dest_path: Path) -> tuple[bool, str]`：`asyncio.create_subprocess_exec("pg_dump","-Fc","-f",str(dest_path), settings.database_url, env={**os.environ}, stdout=PIPE, stderr=PIPE)` → `await proc.communicate()` → returncode 0 即成功，否则 stderr 入 error。目录不存在则 `dest_path.parent.mkdir(parents=True, exist_ok=True)`
- `execute_cleanup() -> BackupRecord`：清理流程，见下
- `validate_recent_backups(days: int) -> dict`：查保留窗口内 `task_type in ('daily_backup','manual_backup') and status='success'` 的记录（`backup_date >= cst_today()-timedelta(days=days)`），逐条 `pg_restore --list <file>` 校验（`create_subprocess_exec("pg_restore","--list",file_path)` exit 0=valid），返回 `{"passed":bool, "total":n, "valid":n, "invalid_records":[...], "missing":[...]}`
- `execute_cleanup()` 流程：创建 cleanup pending 记录 → running → 调 `validate_recent_backups(settings.backup_retention_days)`：
  - `passed=True`：删除 `created_at < cst_now()-timedelta(days=settings.backup_retention_days)` 的 success 备份文件（`Path.unlink(missing_ok=True)`）+ 写 `deleted_count=N/retention_check_passed=True/status=success`
  - `passed=False`：不删任何文件，写 `retention_check_passed=False/status=failed/error_message=无效明细`，留痕
  - `finally` commit
- `async execute_restore(source_record_id: int, operator_id: int) -> BackupRecord`：恢复指定备份——查 source 记录，校验 `task_type in ('daily_backup','manual_backup') and status='success' and file_path` 存在且文件在 `backup_dir` 内（`Path.is_relative_to`），否则抛 `ValueError("源备份不可恢复")` → `create_record('restore', operator_id, file_path=source.file_path, backup_date=source.backup_date)` → `pending→running` → `_run_pg_restore(file_path)` → 成功 `status=success/completed_at`，失败 `status=failed/error_message`，`finally` commit
- `_run_pg_restore(file_path: Path) -> tuple[bool, str]`：`asyncio.create_subprocess_exec("pg_restore","--clean","--if-exists","-d",settings.database_url,str(file_path), env={**os.environ}, stdout=PIPE, stderr=PIPE)` → `await proc.communicate()` → returncode 0 即成功（`--clean` 的 DROP 阶段 stderr 含 notice 可忽略，仅以 returncode 判定），非0 则 stderr 入 error
- `list_records(page:int, page_size:int, task_type:str|None) -> dict`：仿 `SyncTaskService.list_tasks`（`:625`），含 total/items
- `get_record(record_id:int) -> BackupRecord`

文件路径安全：备份文件名 `backup_YYYYMMDD_HHMMSS.dump`，存 `settings.backup_dir`；下载/校验/删除/恢复前用 `Path(settings.backup_dir).resolve()` 校验 `file.resolve().is_relative_to(backup_root)`（防路径穿越）。

时区统一用 `app.utils.timezone` 的 `cst_now`/`cst_today`（`CST` 已用于所有 CronTrigger）。

### 6. 任务层：tasks/backup.py

新文件 `backend/app/tasks/backup.py`，提供纯执行函数（供 scheduler 闭包调用）+ 动态注册函数（仿 `register_sync_daily_auto` `scheduler.py:287-360`）。恢复为手动触发，不在 scheduler 注册：

```python
BACKUP_JOB_ID = "backup_daily_auto"
CLEANUP_JOB_ID = "cleanup_old_backups"

async def perform_backup_task(session): ...   # create_record('daily_backup', None) + execute_backup
async def perform_cleanup_task(session): ...  # execute_cleanup()
def register_backup_daily(session_factory, enabled: bool, backup_time: str) -> None:
    """仿 register_sync_daily_auto：幂等 remove→add，CronTrigger(hour,minute,CST)，任务内二次校验 BackupScheduleConfig.enabled（仿 :314-322）"""
```

`register_backup_daily` 的内部 `_run` 闭包：`async with session_factory() as session` → 二次校验配置 enabled → `perform_backup_task(session)`，仿 `scheduler.py:309-351`。

### 7. 调度器注册

文件 `backend/app/tasks/scheduler.py`，`start_scheduler` 内（`:37-216`）：
- 导入区（`:44-51`）加 `from .backup import perform_backup_task, perform_cleanup_task, register_backup_daily, BACKUP_JOB_ID, CLEANUP_JOB_ID`
- 闭包协程（仿 `:57-89`）：
```python
@monitored_task("backup_daily_auto", "每日数据库备份")
async def _backup_daily():
    async with session_factory() as session:
        return await perform_backup_task(session)

@monitored_task("cleanup_old_backups", "过期备份清理")
async def _cleanup_old_backups():
    async with session_factory() as session:
        return await perform_cleanup_task(session)
```
- 动态注册（仿 `:164-189`）：读 `BackupScheduleConfig` where `task_name=='daily_backup'`，`enabled` 则 `register_backup_daily(session_factory, True, cfg.backup_time)`，否则不注册
- 清理任务（固定，`:208` 前、`scheduler.start()` 前）：
```python
scheduler.add_job(
    _cleanup_old_backups,
    trigger=IntervalTrigger(days=settings.backup_cleanup_interval_days),
    id=CLEANUP_JOB_ID, name="过期备份清理", replace_existing=True,
    next_run_time=cst_now() + timedelta(days=settings.backup_cleanup_interval_days),  # 避免启动即清理
)
```
（`next_run_time` 使首次延后，之后每 5 天；`timedelta` 已 import `:9`）

### 8. 路由层：routes/backup.py + main.py 注册

新文件 `backend/app/routes/backup.py`，仿 `routes/sync_schedule.py`：
```python
backup_bp = Blueprint("backup", url_prefix="/api/v1/system/backup")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
```
端点（全部 `@auth_required` + `@require_permission`，`request.ctx.db_session` 取 DB，`request.ctx.user["user_id"]` 取用户，仿 `sync_schedule.py:67-134`）：
- `GET /schedule` → `@require_permission("system:view")`：返回 `BackupScheduleConfig` + `next_run_time`（`get_scheduler().get_job(BACKUP_JOB_ID)`，仿 `_config_dict` `:42-55`）
- `PUT /schedule` → `@require_permission("system:database_backup")`：校验 `backup_time` 格式 + `enabled` bool，更新配置 commit，调 `register_backup_daily(request.app.ctx.async_session_maker, enabled, backup_time)` 立即生效（仿 `_reschedule_job` `:58-64`）
- `GET /records` → `@require_permission("system:view")`：分页列表（query: page/page_size/task_type），`BackupService.list_records`
- `GET /records/<int:rid>` → `@require_permission("system:view")`：单条
- `POST /perform` → `@require_permission("system:database_backup")`：手动备份——`rec=await service.create_record("manual_backup", operator_id=user_id)`，`asyncio.create_task(_run_backup(rec.id, session_factory))` 异步执行（避免 HTTP 超时；备份可能耗时数分钟，axios timeout 15s），立即返回 pending 记录。`_run_backup` 内新建独立 session 调 `execute_backup`
- `POST /records/<int:rid>/restore` → `@require_permission("system:database_backup")`：恢复指定备份——请求体需含 `confirm_date`（用户输入的源备份日期，YYYY-MM-DD）；查 source 记录，校验 `confirm_date == str(source.backup_date)`，不匹配返回 `code=400, message="确认日期与备份日期不匹配"`（防误触，不创建记录）→ 校验源可恢复（success 备份、文件存在、路径在 backup_dir 内）→ `rec=service.create_record('restore', user_id, file_path=source.file_path, backup_date=source.backup_date)` → `asyncio.create_task(_run_restore(rec.id, source.id, session_factory))` 异步执行 `execute_restore(source.id, user_id)`（恢复耗时，避免 HTTP 超时），立即返回 pending restore 记录。`_run_restore` 内新建独立 session 调 `execute_restore`
- `GET /records/<int:rid>/download` → `@require_permission("system:database_backup")`：校验文件路径在 `backup_dir` 内，`await sanic.response.file(file_path, filename=...)` 流式下载

注册：`backend/app/main.py` 蓝图清单（`:272-293` import + `:295-319` `app.blueprint(backup_bp)`）加 `from .routes.backup import backup_bp` 与 `app.blueprint(backup_bp)`。

### 9. 前端：菜单 + 路由 + 页面

**菜单**：`frontend/src/components/layout/AppSidebar.vue`，在「数据清空」按钮（`:395-403`）后插入「数据备份」按钮，结构完全一致：
```html
<button v-if="can('system:database_backup')" class="nav-btn"
  :class="{ active: $route.path === '/system/backup' }"
  @click="goTo('/system/backup')">
  <span class="nav-icon"><svg>…备份/磁盘图标…</svg></span>
  <span class="nav-text">数据备份</span>
</button>
```

**路由**：`frontend/src/router/index.ts`，在 `database-management` 路由（`:99-111`）后加：
```ts
{ path: 'backup', name: 'BackupManagement',
  component: () => import('@/views/system/BackupManagement.vue'),
  meta: { requiresPermission: 'system:database_backup' } },
```

**页面**：新文件 `frontend/src/views/system/BackupManagement.vue`，仿 `DatabaseManagement.vue` 结构（`PageHeader` + `a-card` + `a-alert` + `a-button` + `Modal.confirm` + `service` 直调 + `res.code===0` 判定 + `handleError`）：
- 配置区卡片：`a-switch`(enabled) + `a-time-picker` 或 `a-input`(backup_time HH:MM) + 保存按钮 → `PUT /system/backup/schedule`
- 操作区卡片：「立即备份」`a-button status="primary"` → `Modal.confirm` → `POST /system/backup/perform` → 轮询/刷新记录列表
- 记录列表卡片：`a-table`（列：时间/类型/状态/文件大小/耗时/操作人/错误/操作），分页，`GET /system/backup/records`；状态用 `a-tag`（success绿/failed红/running蓝/pending灰）；操作列仅 `task_type in ('daily_backup','manual_backup') and status='success'` 行显示「下载」+「恢复」按钮，cleanup/restore 行无操作按钮。下载 `GET /system/backup/records/{id}/download`（window 触发或 axios blob）；恢复点击 → `Modal.confirm` 弹框含 `a-input` 要求输入该备份日期（YYYY-MM-DD，与 `backup_date` 一致）→ 提交前前端校验非空且格式正确 → `POST /system/backup/records/{id}/restore` body `{confirm_date}` → 提交后轮询列表至 restore 记录 success；列表上方 `a-alert` 横幅提示「恢复将覆盖整库，建议低峰期执行，恢复后需重启服务」
- `script setup`：`import service from '@/api'`、`useUserStore`、`handleError`、`ApiResponse<T>`，沿用 `service.get/put/post` 直调模式（与 DatabaseManagement.vue 一致，不新建 api 模块）

**冗余配置同步**（可选）：`frontend/src/composables/useAppLayout.ts:104-108` 的 `navSections` 加一行 `{ key:'backup', label:'数据备份', to:'/system/backup', permission:'system:database_backup' }`（该配置无消费方，但保持一致）。

### 10. 测试

**单元**（`backend/tests/unit/test_backup_service.py`）：mock `asyncio.create_subprocess_exec` 的 `pg_dump`/`pg_restore`（returncode 0/非0 分支），验证：`execute_backup` 成功写 file_path/size、失败写 error_message；`validate_recent_backups` 全 valid→passed=True、含 invalid→passed=False；`execute_cleanup` passed 时删除文件+deleted_count、failed 时不删；`execute_restore` mock `_run_pg_restore` returncode 0→写 success、非0→写 failed/error_message，且源记录不可恢复（非 success/文件缺失/路径越界）时抛 `ValueError`。仿 `tests/unit/test_sync_task_service.py` 结构。

**路由**（`backend/tests/unit/test_backup_routes.py` 或 integration）：mock `get_scheduler`/`register_backup_daily`（仿 `tests/unit/test_sync_schedule_routes.py:57-65`），验证 GET/PUT schedule、GET records、POST perform 返回结构 + 权限码拦截；`POST /records/{id}/restore` 的 `confirm_date` 不匹配源 `backup_date` 时返回 400 且不创建 restore 记录。

覆盖率维持 ≥50%（CI 全量口径）。

## Critical files & anchors

- `backend/app/tasks/scheduler.py` — `start_scheduler`（`:37-216`）注册备份/清理任务；`register_sync_daily_auto`（`:287-360`）是 `register_backup_daily` 的直接复刻模板
- `backend/app/routes/sync_schedule.py`（`:28-134`）+ `backend/app/models/sync_schedule.py`（`:9-42`）— 路由 GET/PUT + 配置表模型的直接复刻模板
- `backend/app/services/sync_task_service.py`（`:35-38` 构造注入、`:178-440` execute 终态链）— BackupService 留痕与 execute 终态更新模板
- `backend/app/models/sync_task.py`（`:13-55`）+ `backend/alembic/versions/u0v1w2x3y4z5_add_sync_execution_details.py`（`:29-182`）— BackupRecord 字段模板 + 迁移建表/权限种子/关联超管模板
- `frontend/src/components/layout/AppSidebar.vue`（`:395-403`）+ `frontend/src/router/index.ts`（`:99-111`）+ `frontend/src/views/system/DatabaseManagement.vue` — 菜单插入点 + 路由模板 + 页面结构模板

## Verification

前置：重新构建 app 镜像（`docker compose -f deploy/docker-compose.yml build app`，验证 postgresql-client 安装成功：`docker compose run --rm app sh -c "which pg_dump pg_restore"` 输出两路径）。运行迁移 `alembic upgrade head`，确认 `backup_schedule_configs`/`backup_records` 表创建、`system:database_backup` 权限插入并关联超管。

后端行为验证（`backend/` 目录，`$BACKEND_DIR/.venv/bin/python`）：
1. 手动备份链路：以超管 token `POST /api/v1/system/backup/perform` → 返回 pending `BackupRecord` → 轮询 `GET /records/{id}` 至 `status=success` → 确认 `settings.backup_dir` 下生成 `backup_*.dump` 文件、`file_size_bytes>0` → `pg_restore --list <file>` exit 0（有效性）。
2. 定时配置生效：`PUT /schedule` body `{"enabled":true,"backup_time":"02:00"}` → 200 → `GET /schedule` 返回 `next_run_time` 非空 → 调度器 `GET /api/v1/system/scheduler-status`（或日志）见 `backup_daily_auto` job。
3. 清理校验逻辑：构造 >5 天的 success 备份记录 + 文件 → 触发 `perform_cleanup_task(session)`（或等 `IntervalTrigger`，或测试直接调 service）→ 近 5 天全有效时：`>5天` 文件被删、cleanup 记录 `deleted_count>0/retention_check_passed=True/status=success`；人为损坏一个近 5 天文件（`pg_restore --list` 非0）→ cleanup 记录 `retention_check_passed=False/status=failed`、`>5天` 文件**未被删**。
4. 下载：`GET /records/{id}/download` 返回文件流、Content-Disposition 含文件名；越权路径（篡改 file_path）被拒。
5. 恢复链路：选一条 success 备份记录 `rid`（已知 `backup_date`），`POST /api/v1/system/backup/records/{rid}/restore` body `{"confirm_date":"<源 backup_date 的 YYYY-MM-DD>"}` → 返回 pending restore 记录（`task_type='restore'`、`file_path/backup_date` 取自源）→ 轮询 `GET /records/{new_id}` 至 `status=success` → `pg_restore --list <源file>` 仍 exit 0（源文件未被破坏）；`confirm_date` 与源 `backup_date` 不匹配时返回 `code=400` 且不创建 restore 记录；对非 success 备份记录请求恢复返回 400。

前端验证：超管登录 → 侧边栏「数据清空」下方见「数据备份」→ 进入页面 → 配置区开关/时间可改并保存 → 「立即备份」触发后记录列表出现新行并最终 success → 下载按钮可下载 `.dump` 文件 → success 备份行可见「恢复」按钮，点击弹框要求输入日期，输入错误日期被前端拦截、输入正确日期提交后列表出现 restore 记录并最终 success；横幅提示可见。非超管无 `system:database_backup` 权限者不见菜单、路由守卫拦截。

测试：`cd backend && .venv/bin/python -m pytest tests/unit/test_backup_service.py tests/unit/test_backup_routes.py -v` 通过；全量 `make test` 覆盖率 ≥50%。前端 `npm run type-check` 0 errors。

## Assumptions & contingencies

- **pg_dump/pg_restore 执行环境**：方案依赖 app 镜像加装 `postgresql-client`（步骤 2），备份与恢复共用。若部署侧不允许改镜像，则备份/恢复执行不可行——此时 fallback：把备份执行拆为独立容器/宿主 cron 脚本调用 db 容器内 pg_dump 导出至共享卷，本功能仅保留配置页面 + 留痕（记录由脚本回调 API 写入）。此 fallback 需用户另行确认，默认按步骤 2 执行。
- **备份/恢复耗时与异步**：pg_dump/pg_restore 整库可能数分钟，手动备份与恢复均用 `asyncio.create_task` 异步执行、立即返回 pending，前端轮询；定时备份在调度协程内 `await` 同步完成（不阻塞其他 job，APScheduler 单 job 独立协程）。
- **IntervalTrigger 重启重置**：`cleanup_old_backups` 用 `IntervalTrigger(days=5)` + `next_run_time=启动后5天`；进程重启会重置计时（清理延后），但清理逻辑有「校验近 5 天」保护，重启不影响数据安全，仅影响清理及时性——可接受（非关键维护任务）。
- **保留窗口语义**：「最近 5 天」= `created_at >= cst_now()-5d` 的 success 备份；「超过 5 天」= `created_at < cst_now()-5d`。清理前校验保留窗口内全部 success 备份文件存在且 `pg_restore --list` 通过，任一无效则中止清理并留痕 failed。
- **配置表独立**：新建 `backup_schedule_configs`（而非复用 `sync_schedule_configs`），因后者含 `sync_mode` 字段语义不匹配；独立表语义清晰、与现有 sync 配置平行。
- **权限拆分**：查看（GET schedule/records）用现有 `system:view`，操作（PUT schedule/POST perform/POST restore/GET download）用新 `system:database_backup`，与 sync_schedule（GET `system:view` / PUT `system:sync_schedule`）模式一致；菜单与路由守卫用 `system:database_backup`。
- **恢复为破坏性在线操作**：`pg_restore --clean --if-exists -d` 会先 DROP 再重建整库对象；app 连接池与恢复进程共存时，恢复期间的写操作可能失败/阻塞——故前端横幅提示「低峰期执行、恢复后重启服务」以刷新连接池，但后端不强制停服（与现有部署兼容）。若需严格维护模式，需另行改部署，不在本方案范围。
- **恢复日期二次校验**：前端要求用户输入源备份日期文本、后端校验与 `backup_date` 完全一致才执行（`confirm_date == str(source.backup_date)`），构成双保险防误触；不匹配返回 400 不创建 restore 记录。
- **恢复留痕**：每次恢复创建一条 `task_type='restore'` 的 BackupRecord（operator_id=操作人、file_path/backup_date 取自源备份），与备份/清理记录同表展示；源备份文件不被恢复操作修改/删除。
