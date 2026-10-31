# 备份恢复并发互斥修复 — 验收记录

**日期**: 2026-10-31
**状态**: 已完成并验证

## 目标（验收边界）

防止备份/恢复/清理任务并发执行导致的数据损坏：`pg_restore --clean` 会 DROP 全库对象，与并发的 `pg_dump`/清理存在对象消失冲突风险。任何创建留痕的入口（手动备份、手动恢复、定时备份、定时清理）在存在 `pending`/`running` 任务时必须拒绝或跳过；前端在有进行中任务时禁用「立即备份」与「恢复」按钮。主链路其余行为不变。

## 改动文件

| 文件 | 改动 |
|---|---|
| `backend/app/services/backup_service.py` | 新增 `has_active_task()`（查询区段）：`SELECT count(*) WHERE status IN ('pending','running') > 0` |
| `backend/app/routes/backup.py` | `perform_backup` / `restore_backup` 在 `create_record` 前加并发闸，返回 `409 {"code":409,...}`（restore 置于源可恢复性校验之后，先报源问题） |
| `backend/app/tasks/backup.py` | `perform_backup_task` / `perform_cleanup_task` 有进行中任务时 `logger.info` + 跳过（系统入口容错风格） |
| `frontend/src/views/system/BackupManagement.vue` | 「立即备份」按钮 `:disabled="hasPendingTask()"`；操作列「恢复」按钮 `v-if="!hasPendingTask()"`（下载保持可用） |
| `backend/tests/unit/test_backup_service.py` | 新增 `TestHasActiveTask`（3 例：>0→True / 0→False / None→False） |
| `backend/tests/unit/test_backup_routes.py` | 新增 2 个 409 用例；既有 2 个 201 用例补 `has_active_task` mock（新依赖适配，行为断言不变） |

## 最终验证结果

1. **单元测试**：`pytest tests/unit/test_backup_service.py tests/unit/test_backup_routes.py` → 59 passed；全量 `pytest tests/unit/ -n auto` → **812 passed**，无回归。
2. **端到端（真实测试库 customer_platform_test，一次性脚本已验证并清理）**：
   - 有 pending 任务时 `POST /perform` → 409、`POST /records/<id>/restore`（confirm_date 正确）→ 409，且 `backup_records` 无新增留痕；
   - 无进行中任务时两接口均 201，行为与改动前一致。
3. **静态检查**：ruff check + ruff format 通过；pyright 0 errors；前端 `vue-tsc --noEmit`、`eslint`、`prettier --check` 均通过。

## 备注

- 并发检查为同事务 `select count`，未用行锁（内部系统低并发，TOCTOU 窗口可接受）；若未来出现真实并发误判可升级 `SELECT ... FOR UPDATE`。
- 409 响应体采用 `{"code": 409, ...}` 数值 code，与 `analytics.py:269` / `sync_tasks.py:146` 既有约定一致，未引入新 ErrorCodes 成员。
