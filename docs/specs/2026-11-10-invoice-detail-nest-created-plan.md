# 结算单明细文件优化：移除 uv/pv 列 + 处理完成时间取 nest.created + 时间列时区根因修复

> 2026-11-10 制订（v2，并入时区根因分析）。样本单据：`INV-20261110-26502-0H58`（invoice id=1670，customer 26502，周期 2026-10-31 16:00 ~ 2026-11-09 15:59:59 UTC，文件 `backend/uploads/invoices/2026/11/invoice_1670.xlsx`，状态 completed）。参照基准：`~/Downloads/模型订单列表-深圳中原示例表.xlsx`（业务导出样例，含同单 SZZY_1794137638）。

---

## 一、问题与实证

### 1.1 时间列全部错误：统一偏差 −16 小时（双重时区错误叠加）

同单三方对比（外部原始 vs 示例表 vs 我们的文件）：

| 列 | 外部原始（UTC 墙钟） | 示例表（正确） | 我们的文件 | 误差 |
|---|---|---|---|---|
| 创建时间 | 2026-11-08 11:33:59 | 2026-11-08 19:33:59 | 2026-11-08 03:33:59 | −16h |
| 上传完成时间 | 2026-11-09 02:10:28 | 2026-11-09 10:10:28 | 2026-11-08 18:10:28 | −16h |
| 处理完成时间 | nest.created 02:25:38 | 2026-11-09 10:25:38 | （空） | 缺取数 |
| 第一次分配时间 | 2026-11-09 02:25:40 | 2026-11-09 10:25:39 | 2026-11-08 18:25:40 | −16h（示例表 1s 差为导出时差） |
| 户型图绘制时间 | 2026-11-09 05:39:52 | （空） | 2026-11-08 21:39:52 | −16h |
| 审核发布时间 | 2026-11-09 06:13:43 | 2026-11-09 14:13:43 | 2026-11-08 22:13:43 | −16h |

**错误 1（落库偏移）**：外部 naive datetime 经 aiomysql 读出后写入 PG `timestamptz`，被 PG 按会话时区 `Asia/Shanghai` 解释——02:10:28 被当 CST，绝对时刻变成 11-08 18:10:28 UTC（实证：`upload_date AT TIME ZONE 'UTC'` = 18:10:28）。

**错误 2（显示未转换）**：`invoice_excel._fmt_dt` 直接 `strftime`，未做 UTC→CST。

**计费不受影响的原因**：计费窗口用 `sync_date`（代码生成的 aware UTC，`local_date_to_utc_start`），不经 naive 落库路径——bug 只污染展示列，故长期潜伏。

### 1.2 「处理完成时间」全空

第 17 列当前取 `nest_model_order.finish_date`（实证 NULL）。正解 = 房源主表 `nest.created`（关联 `nest.nest_id = nest_model_order.nest_id`；828905 实测 `nest.created = 2026-11-09 02:25:38` UTC = CST 10:25:38，与示例表吻合）。旧版（F9 前）同样取 finish_date，属一直存在的口径缺失。

### 1.3 uv / pv 死列

第 19/20 列数据行恒 0（`invoice_excel.py:497-498` 硬编码），1670 文件 963 行全 0，无数据源。注：示例表中 uv/pv 也是 0，但业务确认移除。

---

## 二、数据链路（改动前后）

```mermaid
flowchart LR
    subgraph EXT["外部 MySQL（naive datetime = UTC 墙钟）"]
        NMO[("nest_model_order")]
        NEST[("nest · created")]
    end
    subgraph FIX["修复点"]
        S["同步层：naive→aware UTC（C1）"]
        D["显示层：UTC→CST（C2）"]
    end
    subgraph PG[("本地 PostgreSQL timestamptz")]
        DO[("daily_orders")]
    end
    subgraph XLS["明细 Excel"]
        M["月份明细 sheet<br/>29→27 列 · 全时间列 CST"]
    end
    NMO --> S --> DO
    NEST -.->|"LEFT JOIN（B1）"| NMO
    DO -->|"_order_row_to_dict<br/>+nest_created（B5）"| M
    D -.->|"_fmt_dt 转换"| M
```

---

## 三、改动清单

### A. 移除 uv / pv 两列（`backend/app/services/invoice_excel.py`）

1. `DETAIL_HEADERS`（:39-63）删 `"uv"`/`"pv"`（29→27 列，其后列号前移 2）。
2. 数据行 `row_data`（:460-520）删 `0, # uv` / `0, # pv` 两项。
3. 列宽循环 `range(11, len(DETAIL_HEADERS)+1)` 自动适配。
4. 「计费明细」（8 列）与「合计」sheet 零改动。

### B. 「处理完成时间」取 `nest.created`（六处链路）

- **B1 同步层**（`order_sync.py:105-150`）：`DETAIL_SELECT` 末尾追加 `N.created AS nest_created`（序号 29）；`USER_JOINS` 区追加 `LEFT JOIN nest N ON N.nest_id = D.nest_id`（走 nest 主键索引；预检 27202 行全窗口含 JOIN 26s，单日增量可忽略；JOIN 覆盖率 27125/27202=99.7%，未匹配行留空属正常 LEFT JOIN 语义）；`_rows_to_dicts` 映射 `row[29]`；更新头部字段序号注释（0-29）。
- **B2 模型**（`models/daily_order.py` F9 展示列区块）：
  ```python
  nest_created: Mapped[datetime | None] = mapped_column(
      DateTime(timezone=True), nullable=True,
      comment="房源创建时间（外部 nest.created；月份明细「处理完成时间」数据源）",
  )
  ```
- **B3 迁移** `j5k6l7m8n9_add_daily_order_nest_created.py`：`down_revision="i4j5k6l7m8n9"`（当前 head）；可空、不回填（既有约定：外部可能删房源取不回，已生成文件是交付物）；`downgrade()` 逆序删列。
- **B4 落库**（`_match_and_save` 的 `DailyOrder(...)`，:340-380）：追加 `nest_created=order.get("nest_created")`。
- **B5 明细链路**：`invoice_detail_generator._order_row_to_dict`（:31-58）追加 `"nest_created": order.nest_created`（26→27 键）；`invoice_excel.py` 「处理完成时间」项改 `self._fmt_dt(order.get("nest_created"))`。
- **B6 回填脚本**（`scripts/backfill_daily_order_detail_columns.py`）：`BACKFILL_SQL` SELECT/JOIN 同步扩展，`_COLS`/`_ROW_IDX` 加一列。

### C. 时间列时区根因修复（核心，影响全部 6 个时间列）

> **2026-11-10 实证结论（执行期两次对照后定稿）**：外部 MySQL datetime 列为 **UTC 墙钟**——铁证为 `SZZY_1794137638`：外部 `upload_date = 2026-11-09 02:10:28`（naive）、`nest.created = 2026-11-09 02:25:38`（naive），而业务示例表两列分别为 CST `10:10:28`/`10:25:38`（+8h）。存量被 PG 服务端（`SHOW timezone` = Asia/Shanghai）按 CST 解释，**数据层 −8h**；`_fmt_dt` 对 aware UTC 直接 strftime 未转 CST，**显示层再 −8h**——合计 −16h，与最初用户报告吻合。修复：C1 显式标注 UTC（新数据）、C2 显示转 CST、**C3 存量 +8h 修正（dev 已执行，生产上线需同样执行一次）**。排查中曾据「本地读回值 = 外部 naive 按 CST 解释的结果」误判为「外部 CST 墙钟、存量正确」——该对照只证明落库路径，不证明墙钟语义；**业务示例表才是口径基准**，两次翻转后以示例表对齐为最终验收。

- **C1 同步层 naive→aware UTC**（`order_sync.py` `_rows_to_dicts` 出口，一处覆盖全部字段）：对 `create_date`/`upload_date`/`finish_date`/`first_send_zb_date`/`first_edit_time`/`review_release_date`/`nest_created` 七列，naive datetime 统一 `replace(tzinfo=UTC)`（共享工具 `app.utils.timezone.external_naive_to_utc`）；`sync_date` 本就 aware UTC，不动。
  - 备选落点 `DailyOrder(...)` 构造处逐字段包（更啰嗦，不推荐）；backfill 脚本同样经该工具转换（`_DATETIME_COLS`）。
- **C2 显示层 UTC→CST**（`invoice_excel.py` `_fmt_dt`，:320-327）：aware datetime 先 `astimezone(CST)`（复用项目既有 `CST` 常量，`app.utils.timezone`）再 `strftime`；None/naive/非 datetime 分支行为不变。`_fmt_dt` 同时服务 `recharge_records.created_at` 等同为 timestamptz 的列，一并受益。
- **C3 历史数据修正（dev 库已执行；生产上线需执行一次）**：存量 7 列绝对时刻偏 −8h（外部 UTC 墙钟被按 CST 解释），修正 = 全表 `+ interval '8 hours'`：
  ```sql
  UPDATE daily_orders SET
    create_date = create_date + interval '8 hours',
    upload_date = upload_date + interval '8 hours',
    finish_date = finish_date + interval '8 hours',
    first_send_zb_date = first_send_zb_date + interval '8 hours',
    first_edit_time = first_edit_time + interval '8 hours',
    review_release_date = review_release_date + interval '8 hours',
    nest_created = nest_created + interval '8 hours';
  ```
  非幂等，**仅执行一次**；执行后新同步数据走 C1 显式 UTC 路径，不再偏差。已生成文件不回改（交付物不变性，需新口径时 regenerate-detail）。
- **C4 验证不回归计费**：C1/C2 只动展示层时间值与显式时区标注，`sync_date` 与计费窗口不变；1670 端到端实测合计 B3=C3=963、D3=25570、数据行 963、计费行 4，与 regenerate 前完全一致。

### D. 测试更新

| 文件 | 改动 |
|---|---|
| `tests/unit/test_order_sync.py` | SELECT 字段 29→30；`_rows_to_dicts` naive→aware UTC 断言（逐列或抽样）；`nest_created` 映射断言 |
| `tests/unit/test_invoice_excel.py` | 表头 29→27（无 uv/pv）；「处理完成时间」取 `nest_created`；`_fmt_dt` aware UTC→CST 断言（`02:10:28+00:00` → `'2026-11-09 10:10:28'`，跨日用例）；None → `""` |
| `tests/unit/test_invoice_detail_generator.py` | `_order_row_to_dict` 键 26→27、`nest_created` 断言 |
| `tests/unit/test_detail_recovery.py` | 列数/键数派生断言同步更新 |
| `tests/unit/test_timezone_utils.py`（若涉及） | 确认既有 CST 工具无回归 |
| `frontend/src/utils/__tests__/date.test.ts`（新增） | `toLocalDateStr` UTC 边界用例（见 E 节） |

### E. 前端快捷时间范围 UTC 日期串 Bug（2026-11-10 排查新增，3 处）

**根因**：`Date.prototype.toISOString()` 返回 UTC 渲染串，而后端一律按 CST 语义解释日期串——凡绕过 picker/`formatDate` 自洽链、直接 `toISOString().split('T')[0]` 拼日期串的快捷筛选，日期偏 1 天。

| 位置 | 构造 | 实际查询区间（CST 11-10 打开） | 偏差 |
|---|---|---|---|
| `Consumption.vue:597-598`（消耗分析） | `new Date(y, m-3, d)` / `new Date()` | start 本地 00:00 → ISO 串 UTC 前一天 16:00 → 日期串 **早 1 天**（多算 1 天）；end 在 **CST 00–08** 少 1 天，08–24 当天 | start −1d；end 时段相关 |
| `Payment.vue:277-278`（回款分析） | 同款 | 同上 | 同上 |
| `Balance.vue:235-236`（余额「本月」卡片） | `new Date(y, m, 1)` / `new Date(y, m+1, 0)` | firstDay 11-01 00:00 CST → 串 '10-31'（多算 1 天）；lastDay 11-30 00:00 CST → 串 '11-29'（少算 1 天）→ 实际查 **[10-31, 11-29]** | 「本月」错 3 天 |

**修复**：新增 `frontend/src/utils/date.ts` `toLocalDateStr(d: Date): string`（`getFullYear/getMonth/getDate` 本地分量，padStart 补零）；三处调用点替换。原生 `input[type=date]`（自定义范围）与 SyncDialog 本地 `formatDate`（:149）本就走本地分量，不动。

**验证**：单元测试（vitest）覆盖 `toLocalDateStr` 的 UTC 边界（构造 `new Date('2026-11-01T00:30:00+08:00')` 期望 '2026-11-01'）；人工回归：CST 00–08 与 08–24 各点一次「近3个月」「本月」，断点请求参数日期串。

---

## 四之补、时间参数排查结论（2026-11-10，其余页面全部正确）

| 页面/功能 | 链路 | 结论 |
|---|---|---|
| 结算单生成 / 批量 / 试算（`GenerateInvoiceModal`） | arco range-picker → `local_date_range_to_utc` | ✅ 正确。实证 1670：period_start=2026-10-31 16:00Z、period_end=2026-11-09 15:59:59Z = CST 11-01 00:00 ~ 11-09 23:59:59，与逐日同步窗口严格同源 |
| 手动同步（`SyncDialog`） | 本地分量 `formatDate`（:149-157）→ `date.fromisoformat` + `local_date_to_utc_start` | ✅ 正确 |
| VR 结算创建（`VrSettlementCreateModal`） | 同 GenerateInvoiceModal 模式 | ✅ 正确（同链路自洽） |
| 定价规则生效/失效（`PricingRuleModal`） | a-date-picker + `local_date_to_utc_start/end` | ✅ 正确（start/end 的 ISO 串日期偏移与 CST 语义相互抵消，数值自洽） |
| 消耗/回款自定义范围 | `input[type=date]` 本地串 | ✅ 正确 |
| 分析类端点（analytics.py 5 处 + 默认 30 天区间 :1253-1255） | `local_date_range_to_utc` / `local_date_to_utc_start/end` | ✅ 正确 |
| 消耗/回款/余额快捷范围 | `toISOString` UTC 串 | ❌ 见 E 节修复 |

**已知 1 秒边界**（不修，记录）：`local_date_range_to_utc` 的 end = CST 23:59:59（=UTC 15:59:59Z），同步窗口上界为次日 16:00Z——恰在 CST 23:59:59.xxx 上传的订单会被同步纳入但不计入结算（极少见，方向为少算）。

**另一隐性依赖**（不在本次范围，记录）：`utils/formatters.ts` `toDate` 依赖「后端 naive 列按服务器本地（CST）渲染」；与本次 timestamptz 修复不冲突，全链路时区治理建议后续统一收口。

---

## 四、验证方案

### 自动化

```
cd backend && ./.venv/bin/pytest tests/unit/test_invoice_excel.py tests/unit/test_order_sync.py \
  tests/unit/test_invoice_detail_generator.py tests/unit/test_detail_recovery.py tests/unit/test_timezone_utils.py -q
./.venv/bin/pytest tests/integration/test_invoice_generation_guard.py -q
```

### 迁移

```
./.venv/bin/alembic upgrade head && ./.venv/bin/alembic current   # 期望 j5k6l7m8n9
```

### dev 端到端（主路径）

1. 回填 1670 周期 `nest_created`（17721 行，外部缺失 45 行留空）+ 执行 C3 存量修正（全表 7 列 +8h，一次性；实证依据见 C 节）——dev 库已执行。
2. 重置 1670 `detail_file_status=pending` 后调 `generate_invoice_detail`（生产同款 `expire_on_commit=False` session；HTTP 端点 `POST /api/v1/billing/invoices/1670/regenerate-detail` 走 APScheduler 同路径），轮询至 `completed`。
3. 读 `invoice_1670.xlsx` 断言（对齐示例表同单 SZZY_1794137638）——**2026-11-10 实测结果**：

| 列 | 期望值 | 实测 |
|---|---|---|
| 房源名称/订单编号 | 壹成中心璞誉府(11-09 15:00-16:00杨娜) / SZZY_1794137638 | ✓ |
| 创建时间 | `2026-11-08 19:33:59` | ✓ |
| 上传完成时间 | `2026-11-09 10:10:28` | ✓ |
| 处理完成时间 | `2026-11-09 10:25:38` | ✓（原为 None） |
| 第一次分配时间 | `2026-11-09 10:25:40` | ✓ |
| 户型图绘制时间 | `2026-11-09 13:39:52` | ✓ |
| 审核发布时间 | `2026-11-09 14:13:43` | ✓ |
| 列数/uv/pv | 27 列，无 uv/pv | ✓ |
| 计费不回归 | 合计 B3=C3、月份明细行数、计费明细 8 列双口径与 regenerate 前**完全一致**（B3=C3=963、D3=25570、数据行 963、计费行 4） | ✓ |

### 边界冒烟

- `nest_id` 为空的订单（同步层不过滤 nest_id）：不报错、时间列正常、处理完成时间空。
- 外部 `finish_date` 非 NULL 的历史单：确认「处理完成时间」改取 nest_created 后无异常（该列语义从「编辑完成」变更为「房源创建」，需在交付说明中告知业务）。

---

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| C1/C3 改存储语义影响面大 | 只碰展示列；计费窗口（sync_date）不动；C1 显式 UTC 标注（外部 UTC 墙钟实证）；C3 非幂等，**仅执行一次**，执行前以 `SELECT ... WHERE upload_date > now()+1day` 抽检（dev 执行前为 0 异常行） |
| 生产存量数据修正时机 | 随上线执行一次 C3 脚本；执行窗口避开同步任务（`sync_lock:*`）；执行后当日同步数据自动覆盖为正确值 |
| 列数 29→27 波及相关测试 | 第四节已列全；跑单测即暴露 |
| 99.3% JOIN 覆盖率外的行 | LEFT JOIN 留空，与既有留空列同语义 |
| 「处理完成时间」语义变化 | 该列原先恒空，无历史依赖；交付说明告知业务：现=房源创建时间 |
| 已生成文件不回改 | 既定交付物不变性；需新口径 regenerate |

回滚：纯代码 + 可空列迁移，revert / `downgrade()` 即回滚；C3 数据修正回滚 = 反向 `- interval '8 hours'`（同样仅一次，且须确认回滚窗口内无新同步写入）。

---

## 六、不在本次范围

- uv/pv 数据源（直接删列；后续如需 UV/PV 统计另案接入 `nest_3d_operations` 等表）。
- 「接单时间」「户型图最新绘制人」「发布人」「编辑人账号/姓名」等既有留空列（示例表中同为空，非本次缺陷）。
- `nest.changed` 的利用（预留「最新变更时间」需求）。
- 历史已生成文件的批量重生成（按需 regenerate-detail）。

---

## 附：关键锚点（行号为 2026-11-10 实测，执行前以 read/codegraph 复核）

- `backend/app/services/invoice_excel.py:39-63`（DETAIL_HEADERS）、:320-327（_fmt_dt）、:460-520（row_data，finish_date 项约 :495、uv/pv 约 :497-498）
- `backend/app/services/order_sync.py:105-150`（DETAIL_SELECT/USER_JOINS/_rows_to_dicts）、:340-380（DailyOrder 构造）
- `backend/app/tasks/invoice_detail_generator.py:31-58`（_order_row_to_dict）
- `backend/app/models/daily_order.py:49-90`（F9 展示列区块）
- `backend/scripts/backfill_daily_order_detail_columns.py`（BACKFILL_SQL/_COLS/_ROW_IDX）
- 迁移链：`f1a2b3c4d5e6 → g2h3i4j5k6l7 → h3i4j5k6l7m8 → i4j5k6l7m8n9（head）→ j5k6l7m8n9（新增）`
- CST 工具：`app/utils/timezone.py`（CST 常量，C2 复用）
