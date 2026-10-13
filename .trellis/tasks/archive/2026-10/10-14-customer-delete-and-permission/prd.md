# 增加删除客户功能及权限配置

## Goal

客户管理增加删除客户功能，并增加对应的权限配置；同时**补全删除客户时的级联软删除范围**（消除孤儿数据）。

## Background（已确认事实，来源：代码探索）

- **后端已有**：
  - 删除接口 `DELETE /api/v1/customers/<id>`（`backend/app/routes/customers.py:755`）：软删除 + 级联软删除，`@require_permission("customers:delete")`，含经理可见性服务端校验
  - 权限码 `customers:delete` 已注册于 `backend/scripts/seed.py:51`
  - 服务 `delete_customer`（`backend/app/services/customers.py:949`）现有级联：CustomerBalance、CustomerProfile、Invoice、DailyConsumption
- **缺口 A（前端入口）**：`CustomerTable.vue` 操作列仅有「编辑」「详情」按钮，无删除按钮；组件已声明 `delete` 事件（272 行）与 `can` prop（259 行）；`useCustomerList.ts` 已有 `handleDelete`（Modal.confirm + Message + 刷新），`Index.vue` 已绑定 `@delete`
- **缺口 B（级联不完整，用户确认补全）**：以下表引用 customer_id 但 `delete_customer` 未处理，软删除不触发外键 `ondelete="CASCADE"`，产生孤儿数据：
  - `balance_whitelists`（`models/balance_whitelist.py:19`，customer_id unique —— 残留有重建冲突隐患）
  - `daily_orders`（`models/daily_order.py:30`，customer_id 可空）
  - `customer_tags`（`models/tags.py:36`）
  - `profile_tags`（`models/tags.py:48`，经 profile_id 关联，画像软删后同样残留）
  - 以上模型均继承 `BaseModel`（含 `deleted_at`，`models/base.py`），可统一软删
- 现有删除测试仅断言 `customers.deleted_at`（`test_customers_api.py:461`），无级联断言

## Requirements

- R1 客户列表操作列增加「删除」按钮，仅具 `customers:delete` 权限的用户可见
- R2 点击删除走确认弹窗（复用 `handleDelete`），删除后刷新列表并提示
- R3 后端 `delete_customer` 补全级联软删除：BalanceWhitelist、DailyOrder、CustomerTag、ProfileTag（连同现有 CustomerBalance/CustomerProfile/Invoice/DailyConsumption）

## Acceptance Criteria

- [ ] AC1 操作列出现「删除」按钮，位于编辑/详情旁
- [ ] AC2 无 `customers:delete` 权限时删除按钮不可见（`can('customers:delete')` 控制）
- [ ] AC3 点击删除弹出确认框，确认后调用 `deleteCustomer`，成功提示「删除成功」并刷新列表；取消无副作用
- [ ] AC4 删除客户后，其 balance_whitelists / daily_orders / customer_tags / profile_tags 记录的 `deleted_at` 均被置位（集成测试断言新增覆盖）
- [ ] AC5 既有级联（余额/画像/结算单/日消耗）行为不变，现有测试全绿

## Out of Scope

- 修改权限码/迁移/接口签名（不变）
- 物理删除或清理历史孤儿数据（仅删除动作生效后不再产生新孤儿）

## Key Decisions

- 复用已有 `handleDelete` 与 `Modal.confirm` 交互模式
- 级联补全采用与现有相同的 `sa_update ... values(deleted_at=func.now())` 模式，事务内一次性提交
