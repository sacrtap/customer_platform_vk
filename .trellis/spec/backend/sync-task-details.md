# 同步任务执行明细（sync_task_log_details）字段契约

> 本文记录同步日志「执行信息」页的数据来源与字段职责。排查「某条目为什么没有
> 外部公司名 / 客户名」前先读这里。改动 `services/sync_task_service.py`、
> `services/order_sync.py`、`services/cost_calc.py` 的明细发射逻辑前必读。

## 1. 外部公司名 `company_name` 的真实来源：`nest_user.owner_company` 聚合，不是订单表字段

`_fetch_orders`（`app/services/order_sync.py`）的 SQL 里**没有** `nest_model_order.company_name`
这一列。明细/订单里的「外部公司名」来自按 `group_type` 的聚合子查询：

```sql
INNER JOIN (
  SELECT group_type, MAX(owner_company) AS owner_company
  FROM nest_user GROUP BY group_type
) AS U ON D.group_type = U.group_type
```

三个直接后果：

1. **`group_type` 在 `nest_user` 无对应行的订单根本不会进入同步**（INNER JOIN 滤掉），
   不会产生任何明细——「订单丢了」类问题先查这个 JOIN，不要只查状态条件。
2. **`group_type IS NULL` 的订单同样被滤掉**：SQL 的 `NULL = NULL` 不成立。
   `nest_user` 中 `group_type IS NULL` 的行（实测 19 行）`owner_company` 全为空，
   自成一个「空组」，但对应的订单进不了管线，因此**外部公司名为空的订单在已同步
   数据里不可能出现**。
3. 同一 `group_type` 多行 `nest_user` 时取 `MAX(owner_company)`——非确定性取一，
   上游若同组公司名不一致，明细显示的是字典序最大值。

实测（2026-11-17，`3dnest_engine_new`）：1404 个 group_type 中唯一空组即
`group_type IS NULL` 组；近 90 天符合结算状态（`order_status 3-12 或 15`）的
266872 条订单中仅 1 条 `group_type` 为 NULL。

## 2. 字段职责矩阵：哪些明细类型携带哪些客户维度字段

`SyncDetail`（`app/services/dto.py`）的客户维度字段由**各发射点自行决定传不传**，
没有统一填充逻辑。当前全景（发射点 → 字段）：

| 明细 category | level | customer_id | customer_name | external_customer_id | company_name | 发射点 |
|---|---|---|---|---|---|---|
| `cost_calc` | info/warning/error | ✅ | ✅ | — | — | `cost_calc.py::_emit` |
| `order_save`（成功，按客户聚合） | info | ✅ | ✅ | — | — | `order_sync.py` 成功聚合循环 |
| `order_save`（单条处理失败） | error | — | — | ✅ | ✅ | `order_sync.py` 异常分支（2026-11-17 补传，与 order_match 同口径；group_type 缺失时为 None） |
| `order_save`（批量提交失败） | error | — | — | — | — | `order_sync.py` 提交异常分支 |
| `order_match`（未匹配内部客户） | warning | — | — | ✅ | ✅ | `order_sync.py` 未匹配分支 |
| `order_move`（跨日迁移） | warning | ✅ | ✅ | — | — | `order_sync.py::_migrate_cross_day_orders`（2026-11-17 补传：名称按客户批量预取，`customer_id` 为空时跳过查询且名称为 None） |
| `order_fetch`（外部拉取失败） | error | — | — | — | — | `order_sync.py::sync_orders` |
| `data_check`（跳过/无订单/无消费） | info/warning | — | — | — | — | `sync_task_service.py` |
| `system`（任务级） | * | — | — | — | — | `sync_task_service.py` |

**结论（回答「为什么有些条目没有外部公司名称」）**：只有 `order_match` 与
`order_save` 单条失败两条路径传 `company_name`；其余类型在设计上只走内部客户
维度或任务级维度。实测 21046 条明细中 21008 条（99.8%）`company_name IS NULL`，
且这 21008 条里绝大多数（cost_calc 10670 + order_save 成功 9735 = 20405 条）
本身就是内部客户行，公司名列展示内部 `customer_name` 属预期行为。

判断某行「该不该有外部公司名」只需看 category：`order_match` / `order_save`
之外的 category 一律没有，不是数据缺失。

**未匹配（`order_match`）的判定条件**（`order_sync.py::_match_customer`，两关都
失败才算未匹配，带上外部字段）：

1. `group_type` 在 `customers.company_id` 找不到（注意 `if group_type:` 对 0 为假，
   group_type=0 的订单跳过本关直接试公司名）；
2. 且 `owner_company`（即 `company_name`）在 `Customer.name` 精确匹配不到。

实测（2026-11-17）：外部全部 689 个有结算订单的 group_type 中，8 个不在内部
客户表——5 个负值与 0 在 `nest_user` 无对应行，其订单被 INNER JOIN 直接滤掉
（无明细）；100110/100271 虽 ID 不匹配但公司名兜底成功（对应内部客户 930/1225）。
历史唯一未匹配群体 1798（茂名世华地产，38 条 warning 集中在 2026-10-29）是
**客户建档时间差**：该客户建于 2026-10-31，晚于同步日期，重同步不会再产生。
即：按当前客户表，新同步基本不会出现 `order_match`，「外部」列多数行为 `-` 属
预期；若上游出现全新 group_type 且未建档，才会重新看到该列有值。

回归测试：`backend/tests/unit/services/test_order_sync.py::test_match_and_save_single_failure_carries_external_customer_id`
（覆盖单条失败带外部ID、group_type 缺失为 None 两种形态）、
`backend/tests/unit/services/test_order_sync_cross_day.py` 的 order_move 客户名断言
（含多客户单次批量预取、`customer_id` 为空跳过查询两种边界）。

**不变量（2026-11-17 两起同类缺口后确立）**：凡发射点传了 `customer_id`，必须**同时**
传 `customer_name`。接口返回的 `company_id` 由左连 customers 补出，而 `customer_name`
**没有任何兜底**——漏传即「公司ID 列只有 ID、没有名称」（用户实测样例：order_move
1617/OPPD_E6Nl1794157803）。新增/改动明细发射点后对照本矩阵逐列核对。

**存量处理口径（2026-11-17 产品确认：不回填）**：三处缺口修复前产生的历史明细
（order_move 371 条、order_save 单条失败存量等）保持原样，不写回填脚本；页面看到
「老记录只有 ID」属已知存量状态，仅修复后**新同步**的明细带全字段。

## 3. 前端展示口径（与后端契约的对应）

执行信息抽屉两列（`.trellis/spec/frontend/component-guidelines.md`
「明细类接口的内部/外部分列」）：

- 「公司ID」列 = 内部维度：`company_id · customer_name`（同格，` · ` 分隔，
  缺失一方省略）。`company_id` 来自 `customers.company_id`，随 `customer_id`
  左连带入，匹配时恒非空
- 「外部」列 = 外部维度：`external_customer_id · company_name`（同格）
- 两列**互不兜底**：内部名称不进「外部」列，外部名称不进「公司ID」列；
  同一明细通常只有一列有值，全空才显示 `-`
- 四种形态（`ID · 名称` / 仅 ID / 仅名称 / `-`）由共用函数
  `formatIdName(id, name)` 统一产出

## 4. 排查用 SQL（dbx，只读）

本地明细分布（`customer-remote` 连接）：

```sql
SELECT category, level, COUNT(*) AS total,
       COUNT(*) FILTER (WHERE company_name IS NULL) AS no_company_name,
       COUNT(*) FILTER (WHERE customer_name IS NOT NULL) AS has_customer_name
FROM sync_task_log_details GROUP BY category, level ORDER BY category, level;
```

外部空组核对（`3dnest_engine_new` 连接）：

```sql
SELECT COUNT(*) AS total_group_types,
       SUM(CASE WHEN max_oc IS NULL OR max_oc = '' THEN 1 ELSE 0 END) AS empty_owner_groups
FROM (SELECT group_type, MAX(owner_company) AS max_oc FROM nest_user GROUP BY group_type) t;
-- 命中 1 时几乎必是 group_type IS NULL 组，用下行确认：
SELECT COUNT(*) FROM nest_user WHERE group_type IS NULL;
```

> 注意 `WHERE group_type IN (SELECT group_type ... WHERE max_oc IS NULL)` 查不到
> 那个空组——`NULL IN (...)` 求值为 NULL，这是 SQL 三值逻辑，不是数据没了。
