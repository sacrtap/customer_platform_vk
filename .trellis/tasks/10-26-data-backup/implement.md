# 数据备份功能 — 实施计划

## 执行顺序（每步完成即勾选，遇阻记录到 notes）

### A. 后端基础设施

- [ ] A1. `backend/app/config.py`：`redis_url` 后增 `backup_dir` / `backup_retention_days` / `backup_cleanup_interval_days`
- [ ] A2. `.env.example`：文件存储配置段后增 3 键（带注释）
- [ ] A3. `deploy/docker/Containerfile`：apt-get install 块加 `postgresql-client`
- [ ] A4. `backend/app/models/backup.py`：新建两模型（SQLAlchemy 2.0 typed 声明）
- [ ] A5. `backend/app/models/__init__.py`：注册 `backup` 模块 + `__all__`
- [ ] A6. 新迁移 `c9d0e1f2a3b4_add_backup_feature.py`（`down_revision="b8c9d0e1f2a3"`）：建两表 + 索引 + bulk_insert 默认行 + 权限种子 + 关联超管 + downgrade
- [ ] A7. `backend/scripts/seed.py`：`ALL_PERMISSIONS` 增 `("system:database_backup", "数据备份", "配置定时备份与清理、手动备份、下载备份、恢复备份", "system")`
- [ ] A8. `backend/tests/_test_data.py`：`PERMISSION_ROWS` 增 `("system:database_backup", "数据备份", "system")`

### B. 服务与任务

- [ ] B1. `backend/app/services/backup_service.py`：`BackupService`
  - `get_or_create_schedule_config` / `create_record` / `execute_backup` / `_run_pg_dump`
  - `validate_recent_backups` / `execute_cleanup` / `execute_restore` / `_run_pg_restore`
  - `list_records` / `get_record` / `_abs_path`（路径穿越防护）
- [ ] B2. `backend/app/tasks/backup.py`：`BACKUP_JOB_ID`/`CLEANUP_JOB_ID` + `perform_backup_task` + `perform_cleanup_task` + `register_backup_daily`
- [ ] B3. `backend/app/tasks/scheduler.py`：导入、两个 `monitored_task` 闭包、启动时按配置注册、清理 `IntervalTrigger`（`next_run_time` 延后）

### C. 路由

- [ ] C1. `backend/app/routes/backup.py`：7 端点（见 design §6）
- [ ] C2. `backend/app/main.py`：import + `app.blueprint(backup_bp)`

### D. 前端

- [ ] D1. `AppSidebar.vue`：数据清空按钮后插数据备份按钮（`can('system:database_backup')`）
- [ ] D2. `router/index.ts`：system 组 database-management 后加 backup 路由
- [ ] D3. `useAppLayout.ts`：`navSections` system items 加 backup；`isSubmenuActive('system')` 与 watch 的路径列表加 `/system/backup`；`pageTitle` routeMap 加 `BackupManagement: '数据备份'`
- [ ] D4. `frontend/src/views/system/BackupManagement.vue`：配置区 + 操作区 + 记录列表（下载/恢复 + 日期输入弹框）

### E. 测试

- [ ] E1. `backend/tests/unit/test_backup_service.py`：mock subprocess
  - execute_backup 成功写 file_path/size / 失败写 error_message
  - validate_recent_backups 全 valid→passed=True / 含 invalid→False
  - execute_cleanup passed 删文件 + deleted_count / failed 不删
  - execute_restore returncode 0→success、非0→failed；源不可恢复（非 success / 文件缺失 / 路径越界）→ ValueError
- [ ] E2. `backend/tests/unit/test_backup_routes.py`：mock scheduler + register
  - GET/PUT schedule 结构与校验；GET records 分页；POST perform 返回 pending + 权限码拦截
  - restore confirm_date 不匹配 → 400 且不创建记录
- [ ] E3. `tests/unit/test_test_data_consistency.py` 通过（子集关系）

### F. 验证

- [ ] F1. `cd backend && .venv/bin/python -m pytest tests/unit/test_backup_service.py tests/unit/test_backup_routes.py -v` 通过
- [ ] F2. `cd backend && .venv/bin/python -m ruff check app/ && .venv/bin/python -m pyright` 0 error
- [ ] F3. `cd backend && .venv/bin/python -m alembic upgrade head` + `scripts/check_schema_drift.py`（运行库验证）
- [ ] F4. `cd frontend && pnpm type-check` 0 errors
- [ ] F5. 后端行为冒烟（本地库 + 本地 pg_dump/pg_restore）：备份链路 / 清理校验 / 下载 / 恢复链路 / 日期不匹配 400
- [ ] F6. 前端浏览器验证：菜单 / 页面 / 立即备份 / 恢复弹框日期拦截
- [ ] F7. 全量 `make test` 覆盖率 ≥50%
- [ ] F8. 镜像构建验证（docker 不可用则如实标注，改由 CI 侧验证）

## 验证命令速查

```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_backup_service.py tests/unit/test_backup_routes.py -v
.venv/bin/python -m ruff check app/
.venv/bin/python -m pyright
.venv/bin/python -m alembic upgrade head
.venv/bin/python scripts/check_schema_drift.py
.venv/bin/python -m pytest tests/ -q          # 全量（覆盖率在 CI 合并口径）
```

## Rollback 点

- 迁移可 downgrade（删权限 + drop 两表）
- 前端为纯增量（新菜单/新路由/新页面），回滚 = 删文件 + 还原 3 处改动
- Containerfile 改动仅加包，不影响既有层
