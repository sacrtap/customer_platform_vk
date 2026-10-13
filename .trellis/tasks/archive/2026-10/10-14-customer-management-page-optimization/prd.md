# 客户管理页面优化

## Goal

优化客户管理页面，包含 3 项独立可交付的改进：编辑页消费等级金额范围展示、删除客户功能（含权限）、编辑页字段顺序调整。

## Background（已确认事实，来源：代码探索）

- 编辑页 `frontend/src/views/customers/detail/EditCustomerDialog.vue` 为三列 grid 布局：
  - 列一「客户标识」：客户名称、公司ID、邮箱、账号类型、行业类型、是否房产客户、规模等级
  - 列二「结算配置」：结算方式、结算周期、价格策略、ERP系统、合作状态、启用结算、自动发起结算、消费等级
  - 列三「人员与状态」：商务经理、运营经理、是否重点客户、是否停用、首次回款时间、接入时间
- 编辑页规模等级选项显示方案：`S（超大型 5000人）`（等级 + 语义描述 + 规模值），消费等级目前仅硬编码 `C1`~`C6`，无金额信息
- 消费等级金额口径（`backend/app/models/customers.py:101`）：C1/C2/C3/C4/C5/C6 = 100万/50万/25万/12万/6万/6万以下
- 共享常量 `frontend/src/constants/customerOptions.ts`：`SCALE_LEVEL_OPTIONS`（`S - 超大规模 (5000人)` 格式）、`CONSUME_LEVEL_OPTIONS`（`C1 - 100万` 格式，金额非范围表述）；被筛选器/批量编辑引用
- 删除客户后端已存在：`DELETE /api/v1/customers/<id>`（`backend/app/routes/customers.py:755`），软删除 + 级联软删除余额/画像/结算单，权限码 `customers:delete`，服务端数据可见性校验（经理可见性）
- 权限码 `customers:delete` 已注册于 `backend/scripts/seed.py:51`
- 前端 API `deleteCustomer` 已存在（`frontend/src/api/customers.ts:100`），`useCustomerList.ts` 已有 `handleDelete`（Modal.confirm 确认弹窗 + Message 反馈），`Index.vue` 已绑定 `@delete`
- **缺口**：`CustomerTable.vue` 操作列仅有「编辑」（`can('customers:edit')` 控制）与「详情」按钮，无删除按钮
- 集成测试已有删除接口用例（`backend/tests/integration/test_customers_api.py`）

## Requirements

- R1 编辑页「消费等级」下拉选项参考规模等级显示方案，展示对应等级的金额范围
- R2 客户列表增加删除客户入口（操作列按钮），受 `customers:delete` 权限控制
- R3 编辑页字段顺序：消费等级移到「合作状态」下方；首次回款时间、接入时间移到「运营经理」下方
- R4 删除客户时补全级联软删除（用户确认）：新增 BalanceWhitelist、DailyOrder、CustomerTag、ProfileTag（现有余额/画像/结算单/日消耗级联保持不变）

## Acceptance Criteria

- [ ] AC1 编辑页消费等级下拉每个选项显示等级 + 金额范围（格式参考规模等级）
- [ ] AC2 列表操作列出现「删除」按钮，无 `customers:delete` 权限时不可见；点击后确认删除、成功提示、列表刷新；删除走已有软删除接口
- [ ] AC3 编辑页字段顺序：结算配置列为 结算方式→结算周期→价格策略→ERP系统→合作状态→**消费等级**→启用结算→自动发起结算；人员与状态列为 商务经理→运营经理→**首次回款时间→接入时间**→是否重点客户→是否停用
- [ ] AC4 删除客户后白名单/日订单/客户标签/画像标签记录 `deleted_at` 置位（新增集成测试覆盖），既有级联行为不变

## Out of Scope

- 修改后端删除接口签名/权限码/迁移
- 物理删除或清理历史孤儿数据（仅确保新删除不再产生孤儿）
- 修改消费等级/规模等级的取值字典（C1-C6、S-E 不变）
- 其他页面（新增弹窗、筛选器、批量编辑、分析页）的等级显示格式——除非用户确认同步

## Key Decisions

- 消费等级金额范围采用**区间表述**（用户确认）：C1（100万以上）、C2（50万-100万）、C3（25万-50万）、C4（12万-25万）、C5（6万-12万）、C6（6万以下），格式参考规模等级 `S（超大型 5000人）` 的括号说明样式
- 删除级联补全（用户确认）：BalanceWhitelist、DailyOrder、CustomerTag、ProfileTag 纳入软删除范围，沿用现有 `sa_update` 模式

## Notes

- 子任务：10-14-consumption-level-amount-range / 10-14-customer-delete-and-permission / 10-14-edit-form-field-order
