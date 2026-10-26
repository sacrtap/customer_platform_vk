# 数据备份功能 — 需求

## 背景

现有系统无数据库备份能力。需要在「数据清空」侧边菜单下方新增「数据备份」菜单项与页面，提供：
- 每日数据库自动备份（可自定义定时备份时间）
- 每 5 天清理一次超过 5 天的备份，**清理前必须校验最近 5 天的备份文件存在且有效**
- 全过程任务记录留痕（备份 / 清理 / 恢复）
- 选择指定备份进行恢复（在线恢复，破坏性操作，前端二次确认 + 输入备份日期，后端二次校验日期匹配）

## 功能需求

### FR1 定时备份配置
- 配置表单行（单行 `daily_backup`）：`enabled`（开关）+ `backup_time`（HH:MM）
- 启用后按每日定时时间自动执行 `pg_dump -Fc` 整库备份
- 保存后调度器立即生效（不等重启）
- 页面展示下次执行时间（`next_run_time`）

### FR2 手动备份
- 页面「立即备份」按钮，触发后异步执行（HTTP 立即返回 pending 记录，前端轮询）
- 备份文件命名 `backup_YYYYMMDD_HHMMSS.dump`，落 `settings.backup_dir`

### FR3 定时清理 + 清理前校验
- 独立清理任务，每 5 天执行一次（`IntervalTrigger(days=5)`，首次延后 5 天避免启动即清理）
- 清理条件：仅当**最近 5 天**（保留窗口）内全部 success 备份文件存在且 `pg_restore --list` 校验通过时才执行删除
- 删除对象：`created_at < now - 5d` 的 success 备份文件
- 校验失败 → 不删任何文件，写 failed 记录留痕（含无效明细）

### FR4 任务记录留痕
- 单表 `BackupRecord`，`task_type` 区分 `daily_backup` / `manual_backup` / `cleanup` / `restore`
- 字段覆盖：状态流转（pending/running/success/failed）、文件路径、文件大小、业务日期、耗时、错误信息、操作人、起止时间、清理专属字段（`retention_check_passed` / `deleted_count`）
- 页面分页列表展示，状态用彩色 tag

### FR5 备份恢复（破坏性）
- 仅 success 的备份行显示「恢复」按钮
- 前端 `Modal.confirm` + 输入该备份日期（YYYY-MM-DD）双保险
- 后端校验 `confirm_date == source.backup_date`，不匹配返回 400 且**不创建记录**
- 在线恢复 `pg_restore --clean --if-exists -d`，异步执行
- 页面横幅提示：恢复将覆盖整库，建议低峰期执行，恢复后需重启服务

### FR6 备份下载
- success 备份行「下载」按钮，流式下载 `.dump` 文件
- 路径安全：下载/校验/删除/恢复前校验文件在 `backup_dir` 内（防路径穿越）

## 权限

| 操作 | 权限码 |
|---|---|
| 查看配置 / 记录列表（GET） | `system:view`（已有） |
| 改配置 / 手动备份 / 恢复 / 下载（PUT/POST/GET download） | `system:database_backup`（新） |
| 菜单与路由守卫 | `system:database_backup` |

## 约束

- 部署前提：app 镜像需加装 `postgresql-client`（提供 `pg_dump` / `pg_restore`）
- 数据库事务：写操作在 `async with db_session.begin()` 或路由 session 内显式 commit
- 时区统一用 `app.utils.timezone` 的 `cst_now` / `cst_today`
- Python 3.12.x；测试覆盖率 ≥50%（CI 全量口径）
- 复刻现有「每日自动同步」整套模式，不引入新约定

## 验收标准

1. `backup_schedule_configs` / `backup_records` 两表由迁移创建；`system:database_backup` 权限插入并关联超级管理员；`scripts/seed.py` 与 `tests/_test_data.py` 同步
2. 手动备份链路：`POST /perform` → pending 记录 → 轮询至 success → `backup_dir` 下生成 `.dump` 且 `file_size_bytes>0` → `pg_restore --list` exit 0
3. 定时配置：`PUT /schedule {"enabled":true,"backup_time":"02:00"}` → 200 → `GET /schedule` 返回非空 `next_run_time` → 调度器注册 `backup_daily_auto` job
4. 清理校验：近 5 天全有效时 `>5天` 文件被删、cleanup 记录 `deleted_count>0 / retention_check_passed=True / success`；损坏一个近 5 天文件 → `retention_check_passed=False / failed` 且 `>5天` 文件未被删
5. 下载：`GET /records/{id}/download` 返回文件流、Content-Disposition 含文件名；越权路径被拒
6. 恢复链路：`POST /records/{rid}/restore {"confirm_date":"<源 backup_date>"}` → pending restore 记录 → 轮询至 success → 源文件未被破坏；日期不匹配返回 400 且不创建记录；对非 success 记录请求恢复返回 400
7. 前端：超管侧边栏见「数据备份」→ 页面配置区可改可存 → 立即备份产生记录并最终 success → 下载可用 → 恢复弹框要求输日期（错日期前端拦截、对日期提交后出 restore 记录）→ 横幅提示可见；无权限者不见菜单、路由守卫拦截
8. 测试：`tests/unit/test_backup_service.py` + `tests/unit/test_backup_routes.py` 通过；全量覆盖率 ≥50%；前端 `pnpm type-check` 0 errors
