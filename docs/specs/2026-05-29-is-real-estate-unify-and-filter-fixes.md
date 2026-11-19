# `is_real_estate` 字段统一与筛选/编辑 bug 链修复

> 归档来源：`.omo/plans/unify-is-real-estate-field.md`、`fix-customer-is-real-estate-filter.md`、`customer-filter-is-real-estate-fix.md`、`fix-customer-filter-combination-issue.md`、`fix-is-real-estate-filter.md`、`fix-customer-edit-is-real-estate.md` 及 `.omo/notepads/` 下 6 份配套记录（2026-11-19 蒸馏合并，原件已删除）
> 状态：已实施——`is_real_estate` 现由 `Customer` 单表管理
> 关联：`docs/specs/2026-05-26-is-real-estate-migration-impl.md`（字段迁入 `Customer` 的初次实施）
> 锚点说明：文中 `文件:行号` 为 2026-05/06 期快照，定位以符号名与路径为准

## Context

2026-05-26 字段迁入 `Customer` 主表后，系统里同时存在 `Customer.is_real_estate` 与 `CustomerProfile.is_real_estate` 两份存储：筛选、列表、导出走 Customer 表，但详情返回与画像编辑走 Profile 表。同期用户接连报告三个症状：组合筛选"房产客户"切换是/否结果不变、编辑"是否房产客户"不生效、画像页与房产统计 500。本篇覆盖字段统一 + 这一串 bug 链的根因与修复。

## Approach

### 1. 统一字段：删除 `CustomerProfile.is_real_estate`

**冗余根因**：两列并存且不同步——列表返回用 `c.is_real_estate`（Customer 表），详情返回用 `customer.profile.is_real_estate`（Profile 表），画像编辑写 Profile 表。前端所有端点本就统一读 `customer.is_real_estate`，无需改动。

迁移 `backend/alembic/versions/b2c3d4e5f6g7_unify_is_real_estate_field.py`：

- `revision = "b2c3d4e5f6g7"`，`down_revision = "a1b2c3d4e5f6"`（承接 2026-05-26 的加列迁移）
- upgrade：先把 Profile 非 NULL 值同步到 Customer（仅 Customer 为 NULL 的行），再 `DROP COLUMN customer_profiles.is_real_estate`
- downgrade：只能把列加回 `customer_profiles`，**无法恢复已删除的数据**（设计上接受，回滚后以 NULL 呈现）
- 迁移链双向验证通过：upgrade `c889ecfba4e3 → a1b2c3d4e5f6 → b2c3d4e5f6g7`；downgrade 原路返回；head = `b2c3d4e5f6g7`
- 代码侧 `services/customers.py::create_or_update_profile` 移除 `is_real_estate` 两处：`updatable_fields` 列表条目、新建 profile 时的 `is_real_estate=data.get(...)`

### 2. 组合筛选失效 bug

**根因**：前端三处（`loadCustomers` / `handleRefresh` / `handleExport`）均已正确传参，但后端两处缺失——`routes/customers.py` 的 `list_customers` / `export_customers` 的 filters 字典缺 `is_real_estate` 提取，`services/customers.py::get_all_customers` 的条件构建缺对应 WHERE 子句。参数到不了 SQL，筛选条件被完全忽略，与"前端漏传"的表象无关。

修复：

- 路由层参照 `is_key_customer` 的布尔转换模板，两个端点各加：
  ```python
  is_real_estate = request.args.get("is_real_estate")
  if is_real_estate is not None:
      filters["is_real_estate"] = is_real_estate.lower() == "true"
  ```
- 服务层加 `Customer.is_real_estate == value` 条件（用 Customer 表字段，与列表返回同源；无 filters 键时不加条件）
- 前端 `api/customers.ts` 的 `getCustomers` / `exportCustomers` 类型签名补 `is_real_estate?: boolean`
- 另有中间版本曾用 `CustomerProfile.is_real_estate` + JOIN 实现筛选（`services/customers.py` 房产客户筛选段），导致"筛选用一列、显示用另一列"，统一改为 Customer 字段并移除多余 JOIN

测试证据（修复前 3 个集成测试全挂，输出原文）：

```
FAILED test_list_customers_filter_is_real_estate_true - AssertionError: Expected 2, got 3
FAILED test_list_customers_filter_is_real_estate_false - AssertionError: Expected 1, got 3
FAILED test_export_customers_filter_is_real_estate - AssertionError: Expected 1, got 2
= 3 failed in 4.76s =
```

三个用例分别覆盖：list 按 true 筛（2/3 命中）、list 按 false 筛（1/3 命中，含 NULL 行不计入）、export 按 true 筛（1/2 命中）。

### 3. 教训：一次被推翻的错误假设

`fix-is-real-estate-filter.md` 接到同一现象后，仅通读后端代码即判定"后端已正确处理（`get_all_customers` line 246-248、路由 line 77-80 均存在 is_real_estate 逻辑）"，把根因锁定为"前端 `loadCustomers` 漏传参数"，只改了前端一行。**该修复未解决问题**——后续取证发现前端三处传参本就齐全，真正根因在后端 filters 提取与 WHERE 缺失（见第 2 节），前端那次改动是无操作。

结论：**改前两端各自取证，不以单侧代码阅读结论下单**。本案例中后端代码里确实存在 `is_real_estate` 字样（Profile 表路径），单侧阅读极易误判为"已处理"。

### 4. 编辑不生效 bug

**根因**：`services/customers.py::update_customer` 的 `updatable_fields` 白名单缺 `is_real_estate`——前端提交被静默丢弃。修复：在 `is_key_customer` 与 `email` 之间加入 `"is_real_estate"`。

### 5. 测试证据

修复后 `pytest tests/ -k customer` → **171 passed / 4 failed**（175 selected, 459 deselected），其中 3 个 is_real_estate 筛选测试全部通过（`test_list_customers_filter_is_real_estate_true` / `_false` / `test_export_customers_filter_is_real_estate`）。4 个失败均为预存问题、与本轮无关：

| 失败用例 | 原因 |
|---|---|
| `test_list_customers_success` | 测试数据为空，列表返回 0 条 |
| `test_update_customer_profile_success` | `MissingGreenlet`：异步上下文懒加载 `industry_type` |
| `test_allowed_sort_fields_contains_expected_fields` | 排序常量字段名 `industry_type_id` 与 `industry` 不符 |
| `test_all_allowed_sort_fields_are_valid_customer_attributes` | 同上，排序字段名不符 |

## Critical files & anchors

- `backend/alembic/versions/b2c3d4e5f6g7_unify_is_real_estate_field.py` — drop Profile 列迁移，revises `a1b2c3d4e5f6`
- `backend/app/routes/customers.py` — `list_customers` / `export_customers` 的 filters 提取；详情/profile 返回字段改源
- `backend/app/services/customers.py` — `get_all_customers` 筛选条件；`create_or_update_profile` 移除两处；`update_customer` 白名单补字段
- `frontend/src/api/customers.ts` — `getCustomers` / `exportCustomers` 类型签名
- `backend/tests/integration/test_customers_api.py` — 3 个筛选集成测试

## Verification

- `pytest tests/ -k customer` → 171 passed / 4 failed（4 个预存失败逐条列于第 5 节）
- `alembic upgrade head` / `downgrade -1` 双向通过；`\d customer_profiles` 不再含 `is_real_estate`
- curl 组合筛选：`account_type=正式账号&is_key_customer=true&is_real_estate=true` 与 `=false` 返回 total 不同；单独 `is_real_estate=true/false` 亦不同
- 画像编辑 `PUT /customers/{id}/profile` 传 `is_real_estate` 被忽略、不报错，`customers.is_real_estate` 不变

## Assumptions

- 2026-05-29 数据核验（0 冲突 / 0 不一致，详见 `2026-05-26-is-real-estate-migration-impl.md`）证明 drop Profile 列无数据损失。
- downgrade 不恢复数据是可接受的设计：回滚场景罕见，且列结构可还原。
- 导入模板未加 `is_real_estate` 列（当时作为独立增强项挂起，未纳入本次）。

## 实施结果（截至 2026-11-19 核实）

- `Customer.is_real_estate` 为唯一存储；`CustomerProfile.is_real_estate` 已不存在。
- 详情/profile 端点返回、画像编辑、`update_customer` 白名单、list/export 筛选均在位；前端未因本次统一改动。
