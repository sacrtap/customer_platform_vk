# 明细文件优化：uv/pv删列+处理完成时间取nest.created+时间列时区修复

## Goal

结算单明细文件三优化：1) 月份明细移除 uv/pv 死列（29→27 列）；2) 处理完成时间改取外部 nest.created（新增 daily_orders.nest_created 列+同步层 LEFT JOIN nest）；3) 修复时间列双重时区错误（naive 落库按 CST 解释致 -8h + 显示未转 CST 再 -8h = 总计 -16h），并修正前端 3 处快捷时间范围 toISOString UTC 串 bug（消耗/回款/余额）。终态：1670 同单六列时间对齐示例表（CST），计费三表 453 口径零回归。方案：docs/specs/2026-11-10-invoice-detail-nest-created-plan.md

## Requirements

- TBD

## Acceptance Criteria

- [ ] TBD

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
