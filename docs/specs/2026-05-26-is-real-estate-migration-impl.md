# `is_real_estate` 字段迁移（customers 主表新增列）实施记录

> 归档来源：`.omo/plans/is-real-estate-field-implementation.md`、`.omo/notepads/is-real-estate-field-implementation/learnings.md`、`.omo/evidence/task-1-data-stats.txt`、`.omo/evidence/task-f2-frontend-behavior-verification.md`（2026-11-19 蒸馏合并，原件已删除）
> 状态：已实施（字段冗余的统一见 `docs/specs/2026-05-29-is-real-estate-unify-and-filter-fixes.md`）
> 关联：设计文档 `docs/specs/2026-05-26-is-real-estate-field-migration-design.md`（本方案的设计依据，已归档）
> 锚点说明：文中 `文件:行号` 为 2026-05/06 期快照，定位以符号名与路径为准

## Context

`is_real_estate`（是否房产客户）原存放在 `customer_profiles` 画像表。列表页筛选、客户详情等主链路都读 `Customer`，读画像表既不对称也不经济。本次把字段迁到 `customers` 主表，详情页显示 + 两个编辑弹窗提供设置入口；Profile API 保持向后兼容，旧列暂不删。

## Approach

### 1. Alembic 迁移：新列 + 历史数据回填

新增 `backend/alembic/versions/a1b2c3d4e5f6_add_is_real_estate_to_customers.py`：

- `revision = "a1b2c3d4e5f6"`，`down_revision = "c889ecfba4e3"`
- upgrade：
  ```sql
  ALTER TABLE customers ADD COLUMN is_real_estate Boolean NULL
  ```
  然后从 `customer_profiles` 回填：
  ```sql
  UPDATE customers SET is_real_estate = (
      SELECT customer_profiles.is_real_estate
      FROM customer_profiles
      WHERE customer_profiles.customer_id = customers.id
  )
  WHERE EXISTS (
      SELECT 1 FROM customer_profiles
      WHERE customer_profiles.customer_id = customers.id
  )
  ```
- downgrade：`DROP COLUMN customers.is_real_estate`
- 迁移验证：`alembic upgrade head` 后 `\d customers` 可见 `is_real_estate | boolean`；`SELECT COUNT(*) FROM customers WHERE is_real_estate IS NOT NULL` = 1234/1324。

### 2. 迁移前数据核验（原始数字）

执行前对两表分布做了统计，结论是"零冲突、可安全迁移"：

| 统计项 | 数值 |
|---|---|
| customers 总数 | 1324 |
| customer_profiles 行数 | 1234 |
| 无 profile 的客户（迁移后留 NULL） | 90 |
| profile 中 `is_real_estate=false` | 1234（100%） |
| profile 中 `is_real_estate=true` / NULL | 0 / 0 |
| 两表不一致（Customer NULL 而 Profile 有值） | 0 |
| 两表冲突（均非 NULL 但值不同） | 0 |
| 孤立 profile（无对应 customer） | 0 |

补充结论：90 个 NULL 全部来自"无 profile 记录"的客户；系统内不存在真实房产客户，无数据丢失风险。未加索引（父字段 `is_key_customer` 有索引，任务规格未要求）。

### 3. 模型与后端 API

- 模型 `backend/app/models/customers.py`：`is_real_estate = Column(Boolean, nullable=True, default=None)`，位于 `is_key_customer` 之后；`hasattr(Customer, 'is_real_estate')` → True，新实例默认 `None`。
- `backend/app/routes/customers.py` 三处：
  1. `list_customers` 响应字典在 `is_key_customer` 后新增 `"is_real_estate": c.is_real_estate`
  2. `create_customer` docstring 加 `"is_real_estate": "boolean (optional)"`
  3. `update_customer` docstring 加同样一行（两端点均为字典模式透传 service，无额外逻辑）
- `CustomerProfile.is_real_estate` 列**保留不动**，Profile 端点读写逻辑原样，向后兼容。

### 4. 前端四处

- `frontend/src/types/index.ts`：`Customer` 接口新增 `is_real_estate: boolean | null`
- `frontend/src/api/customers.ts`：`createCustomer` / `updateCustomer` 两个签名新增 `is_real_estate?: boolean | null`
- `frontend/src/views/customers/Detail.vue`：基础信息三态标签 `true`→绿"是" / `false`→灰"否" / `null`→"-"
- 编辑弹窗 `a-select`（`allow-clear`，选项 `-`/是/否）：`Detail.vue` 与 `Index.vue` 各一处；配套 `editForm`/`customerForm` 字段、打开弹窗填充（`?? null`）、提交透传

## Critical files & anchors

- `backend/alembic/versions/a1b2c3d4e5f6_add_is_real_estate_to_customers.py` — 迁移脚本，revises `c889ecfba4e3`
- `backend/app/models/customers.py` — `Customer.is_real_estate` 列定义
- `backend/app/routes/customers.py` — list 响应 + create/update docstring 三处
- `frontend/src/types/index.ts` / `frontend/src/api/customers.ts` — 类型与两个 API 签名
- `frontend/src/views/customers/Detail.vue` / `Index.vue` — 三态展示与两处编辑入口

## Verification

- `cd frontend && npx vue-tsc --noEmit` → 0 错误（Detail.vue / Index.vue / 类型签名各轮均通过）
- 后端 `pytest tests/ -k customer` → 36/37 通过，唯一失败为既有 `MissingGreenlet` 异步懒加载问题，与本次无关
- 提交：`43a385c`（前端类型与 API 签名）、`c7b4837`（列表页编辑弹窗）、`053c542`（详情页展示与编辑）
- 前端行为验证（F2，2026-05-29）三项结论：
  - 列表筛选"房产客户"：PASS——下拉为"是/否"，正确传 `is_real_estate` 参数；`true` → total=0、`false` → total=1234、与 prepaid 组合筛选正确
  - 详情页展示：PASS——`GET /api/v1/customers/{id}` 返回 `customer.is_real_estate`，null 显示 "-"
  - 基础信息编辑：PASS——PUT 更新成功，未改动其他字段
  - 发现项（记录备查）：① Profile 端点 `GET/PUT /api/v1/customers/{id}/profile` 500——`routes/customers.py` 仍引用已被 drop 的 `profile.is_real_estate`；② `GET /api/v1/analytics/profile/real-estate` 500——`services/analytics.py` 仍引用 `CustomerProfile.is_real_estate`。该两处由后续 `b2c3d4e5f6g7` 统一迁移解决（见 Step 2 文档）

## Assumptions

- 迁移为纯新增列 + 回填，未删 `customer_profiles.is_real_estate`，Profile API 保持可用。
- 新列 `nullable=True` 且无 DB 默认值，NULL 语义由前端三态展示处理（"-"）。
- 索引未加：列表筛选 `is_real_estate` 初期数据量下不需要，后续若成为高频筛选再补。

## 实施结果（截至 2026-11-19 核实）

- 迁移链、模型字段、路由三处、前端四处均已在位；`Customer.is_real_estate` 与 `CustomerProfile.is_real_estate` 的并存问题已由 2026-05-29 的 `b2c3d4e5f6g7` 迁移清理（drop profile 列），详见 `docs/specs/2026-05-29-is-real-estate-unify-and-filter-fixes.md`。
