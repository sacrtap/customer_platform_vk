# 同步任务 created_at 时区锁定修复

## Goal

锁定应用与测试引擎的 PG 会话时区为 `Asia/Shanghai`，使 `timestamp without time zone`
列在所有环境写入 CST 墙钟，修复 staging 同步日志「创建时间」少 8 小时；同时消除
本次改动新引入的 Python 侧 naive 比较耦合风险。

## Background

消耗分析页「手动同步」提交后，同步日志页任务「创建时间」本地正确、staging 少 8 小时。
定时同步走同一创建链路。

根因（已逐行核实）：

- 手动/定时同步同一条创建链路，`SyncTask(...)` 均未显式设 `created_at`，
  由 `TimestampMixin.created_at`（`DateTime` naive）+ `server_default=func.now()`
  在 DB 侧写入，写入值 = **PG 会话时区**的墙钟。
- `create_async_engine` 未设时区，会话时区跟随容器 `TZ`。本地 `TZ=Asia/Shanghai`
  → CST 墙钟；staging 容器 `TZ=UTC` → UTC 墙钟，少 8 小时。
- 读出口 `_task_to_dict` 已用 `naive_cst_datetime_str(task.created_at)`，
  **前提是 naive 列已存 CST 墙钟**。staging 该前提被破坏，UTC 墙钟被当 CST 输出。

即：创建时间生成规则一致，不一致在「naive 列依赖会话时区」而会话时区未锁定。

## Requirements

- R1：主应用 `create_async_engine` 必须锁定会话时区 `Asia/Shanghai`，
  naive 时间列在所有部署环境写入 CST 墙钟。
- R2：测试引擎（integration / e2e / repository / audit_helpers）必须同步锁定，
  使 CI（UTC runner）行为与生产一致，避免「测试通过而生产偏差」。
- R3：新增回归测试证明会话时区锁定生效（在 `TZ=UTC` 下断言 CST 墙钟语义）。
- R4：不得改 `TimestampMixin` 列类型、`_task_to_dict` 读出口分工、
  `executed_at=cst_now()` 写入侧、`scheduler.py` 的 `timezone=CST` 触发器。
- R5：本次改动使「naive 列语义」从「跟随容器 TZ」变为「恒为 CST」，
  必须排查并修正所有依赖「naive 列 == 本地 naive now」的 Python 侧比较点，
  不得把 8 小时偏差留到运行时才暴露。

## Non-Goals

- 不改 `DateTime` → `DateTime(timezone=True)`（需 Alembic 迁移 + 排查所有读出口，风险不匹配）。
- 不改 `_task_to_dict` 的 `naive_cst_datetime_str` / `utc_to_cst_datetime_str` 分工。
- 不改 `backend/scripts/*` 一次性脚本的引擎。
- 不处理 timestamptz 列（存绝对 UTC 时刻，与会话时区无关）。

## Acceptance Criteria

- [ ] AC1 `backend/app/main.py` 主引擎带 `connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}}`，
      应用连接执行 `SHOW timezone` 返回 `Asia/Shanghai`。
- [ ] AC2 integration / e2e / repository / audit_helpers 四处测试引擎同步锁定，
      `TZ=UTC` 下新建记录的 `created_at` 为 CST 墙钟。
- [ ] AC3 新增回归测试在 `TZ=UTC` 下通过，且移除 `server_settings` 后该测试失败
      （证明断言真实锁定行为，而非恒真）。
- [ ] AC4 `TZ=UTC python -m pytest tests/services/test_sync_task_service.py tests/integration -q` 全绿。
- [ ] AC5 R5 排查出的 Python 侧 naive 比较点全部改为显式 CST 口径，且有测试覆盖。
- [ ] AC6 `ruff check app/`、`pyright` 0 error。
- [ ] AC7 全量测试无新增失败（`python -m pytest tests/ -q` 对比基线）。

## Notes

- 计划文档：`CREATED_AT_时区锁定修复_PLAN.md`（已归档至 `docs/specs/`）。
- 本任务为计划文档的 Trellis 化执行，调研阶段补充了计划未覆盖的影响面（见 design.md）。
