# 验收边界与最终验证结果（2026-11-10）

## 目标
结算单明细文件三优化：uv/pv 删列、处理完成时间取 nest.created、时间列 −16h 时区根因修复（含前端 3 处快捷范围 UTC 串 bug）。

## 改动文件
| 文件 | 改动 |
|---|---|
| `backend/app/models/daily_order.py` | 新增 `nest_created`（timestamptz，可空） |
| `backend/alembic/versions/j5k6l7m8n9_add_daily_order_nest_created.py` | 迁移（revises i4j5k6l7m8n9，dev 已 upgrade） |
| `backend/app/services/order_sync.py` | SELECT/JOIN 加 nest_created；`_rows_to_dicts` naive→aware UTC（external_naive_to_utc）；DailyOrder 落库 |
| `backend/app/services/invoice_excel.py` | 表头 29→27 删 uv/pv；处理完成时间取 nest_created；`_fmt_dt` aware→CST |
| `backend/app/tasks/invoice_detail_generator.py` | `_order_row_to_dict` 26→27 键 |
| `backend/app/utils/timezone.py` | 新增共享工具 `external_naive_to_utc` |
| `backend/scripts/backfill_daily_order_detail_columns.py` | SQL/JOIN/_COLS/_ROW_IDX 扩展 + naive→UTC 转换 |
| `frontend/src/utils/date.ts`（新增）+ `__tests__/date.test.ts`（新增） | `toLocalDateStr` 本地分量格式化 |
| `frontend/src/views/analytics/Consumption.vue`、`Payment.vue`、`billing/Balance.vue` | 3 处快捷范围 toISOString→toLocalDateStr |
| 测试 4 文件 | nest_created 键/落库、_fmt_dt CST（含跨日）、external_naive_to_utc 断言 |

## 跑了哪些验证
1. **单测**：`pytest tests/unit` 878 passed（含新增 6 个回归用例）；`vitest run src/utils/__tests__/date.test.ts` 4 passed；`vue-tsc --noEmit` 0 错；ESLint 0 issue。
2. **迁移**：`alembic upgrade head` → j5k6l7m8n9（修正了初版 down_revision 分叉）；列类型核实 timestamptz。
3. **数据**：外部库对照实证外部 datetime 为 UTC 墙钟（SZZY_1794137638：外部 upload 02:10:28 ↔ 示例表 CST 10:10:28）；回填 1670 周期 nest_created 17721 行（外部缺失 45 留空）；C3 存量修正全表 7 列 +8h 已执行（dev）。
4. **端到端**：1670 重置 pending → regenerate → completed；Excel 断言：

| 断言 | 结果 |
|---|---|
| 27 列、无 uv/pv | ✓ |
| 六列时间对齐示例表（19:33:59/10:10:28/10:25:38/10:25:40/13:39:52/14:13:43） | ✓ 6/6 |
| 处理完成时间取到 nest.created（原 None） | ✓ |
| 计费零回归：B3=C3=963、D3=25570、数据行 963、计费 8 列 4 行 | ✓ 与 regenerate 前一致 |

## 结论
**通过**。生产上线待办：① 执行迁移 j5k6l7m8n9；② 执行一次 C3 存量修正（非幂等）；③ 按需 regenerate 历史结算单明细（已生成文件不回改）。
