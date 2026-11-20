# 数据库变更日志

> 本文件记录所有 Alembic 数据库迁移的历史记录。
> 最后更新: 2026-11-20

---

## 迁移历史

### 旧迁移链（2026-04 ~ 2026-04-21，2026-05-07 重置时已删除）

> 下列文件已随 `9d8e48a`（chore(migration): remove all old migration files）删除，仅作历史记录；原文可从 git 历史取回，勿在 `backend/alembic/versions` 中查找。

| 序号 | 迁移文件 | 变更内容 | 日期 | 关联文档 |
|------|----------|----------|------|----------|
| 0 | `001_initial.py` | 初始表结构：users, roles, permissions, user_roles, role_permissions, customers, customer_profiles, tags, customer_tags, profile_tags, customer_balances, recharge_records, pricing_rules, invoices, invoice_items, consumption_records, daily_usage, sync_logs, audit_logs | 2026-04-01 | Phase 0 后端初始化 |
| 1 | `002_add_customer_groups.py` | 新增客户分组表 `customer_groups` 及关联字段 | 2026-04-03 | 客户分组设计（已随分群功能移除而删除） |
| 2 | `734bdc29cc5e_add_token_blacklist_table.py` | 新增 JWT Token 黑名单表 `token_blacklist` | 2026-04-01 | - |
| 3 | `a5d21c5761aa_add_all_missing_tables.py` | 补充缺失表：groups 关联、余额相关表扩展 | 2026-04-03 | - |
| 4 | `dc8859579c78_merge_heads.py` | 合并多个迁移头（解决并行迁移冲突） | 2026-04-03 | - |
| 5 | `003_add_customer_detail_fields.py` | 客户详情字段扩展：新增 manager_name, region, contact_person, phone 等 | 2026-04-14 | [客户详情字段设计](../specs/2026-04-14-customer-detail-fields-design.md) |
| 6 | `003_add_files_table.py` | 新增附件表 `files`（支持支付凭证、减免证明上传） | 2026-04-14 | - |
| 7 | `004_drop_business_type.py` | 删除 `customers.business_type` 列（迁移至行业类型） | 2026-04-15 | [删除业务类型设计](../specs/2026-04-15-delete-business-type-use-profile-industry-design.md) |
| 8 | `fd0d4d39cef3_add_industry_types_table.py` | 新增行业类型表 `industry_types` 及 `customer_industries` 关联表 | 2026-04-15 | [行业类型设计](../specs/2026-04-14-business-type-to-industry-type-design.md) |
| 9 | `005_convert_price_policy_to_english.py` | `customers.price_policy` 值迁移：中文→英文（定价→fixed, 阶梯→tiered, 包年→yearly） | 2026-04-17 | [price_policy 迁移设计](../specs/2026-04-17-customer-data-import-type-migration-design.md) |
| 10 | `288fbca5e3ed_restore_token_blacklist_table.py` | 恢复 Token 黑名单表（之前迁移丢失后重建） | 2026-04-01 | - |
| 11 | `b0ec7f3a8b31_alter_company_id_to_integer.py` | `customers.company_id` 类型变更：VARCHAR(50) → INTEGER（外键关联） | 2026-04-17 | [导入类型迁移](../specs/2026-04-17-customer-data-import-type-migration-design.md) |
| 12 | `dd4170648c62_remove_customer_level_column_from_.py` | 删除 `customers.customer_level` 列（等级体系迁移至画像表） | 2026-04-15 | [客户详情优化](../specs/2026-04-15-customer-detail-optimization-design.md) |

### 当前迁移链（2026-05-07 起，共 49 个）

> 2026-05-07 以 `05c6bedcf166_initial_schema.py` 重建基线，以下按 `down_revision` 链（无 merge 节点）排序，当前 `head` 为 `m8n9o0p1q2r3`。

| 序号 | 迁移文件 | 变更内容 | 日期 | 关联文档 |
|------|----------|----------|------|----------|
| 0 | `05c6bedcf166_initial_schema.py` | 重建初始基线：users, roles, permissions, user_roles, role_permissions, customers, customer_profiles, industry_types, tags, customer_tags, profile_tags, customer_balances, recharge_records, pricing_rules, invoices, invoice_items, consumption_records, daily_usage, sync_task_logs, webhook_signatures, audit_logs, files 共 22 张表 | 2026-05-07 | - |
| 1 | `cc8c81328d2e_add_token_blacklist_table.py` | 新增 JWT 黑名单表 `token_blacklist`（jti / expires_at 索引） | 2026-05-09 | - |
| 2 | `8f6a04467a12_seed_industry_types.py` | 行业类型种子数据 8 条：项目、房产经纪、房产ERP、房产平台、公共安全、租房、待确认、无 | 2026-05-11 | - |
| 3 | `ce46b7a9d7bc_add_industry_type_foreign_key.py` | `customer_profiles` 新增 `industry_type_id` 外键并回填，删除旧 `industry` 文本列 | 2026-05-11 | - |
| 4 | `c889ecfba4e3_add_profile_fields_to_users.py` | `users` 新增 `phone`、`avatar_url`、`last_login_at` | 2026-05-13 | - |
| 5 | `a1b2c3d4e5f6_add_is_real_estate_to_customers.py` | `customers` 新增 `is_real_estate`，并从 `customer_profiles.is_real_estate` 回填 | 2026-05-26 | [is_real_estate 迁移设计](../specs/2026-05-26-is-real-estate-field-migration-design.md) |
| 6 | `b2c3d4e5f6g7_unify_is_real_estate_field.py` | 统一房产标识至 `customers`（补同步 NULL 值），删除 `customer_profiles.is_real_estate` | 2026-05-30 | [is_real_estate 统一修复](../specs/2026-05-29-is-real-estate-unify-and-filter-fixes.md) |
| 7 | `41b931a886e0_add_daily_orders_and_daily_consumption_.py` | 新增 `daily_orders`（`order_code` + `create_date` 唯一）与 `daily_consumptions`（客户/日期/设备/图层维度消费） | 2026-06-14 | - |
| 8 | `59e4cca22335_add_sync_tasks_table.py` | 新增 `sync_tasks` 同步任务表（日期区间、进度、成功/失败计数、操作人） | 2026-06-24 | - |
| 9 | `6c04c664b261_extend_sync_task_logs_with_audit_fields.py` | `sync_task_logs` 新增 `task_id`、`operator_id`、`start_date`、`end_date` 等审计字段 | 2026-06-24 | - |
| 10 | `cfeac70bcd04_add_discount_applied_at_to_invoices.py` | `invoices` 新增 `discount_applied_at`（减免生效时间） | 2026-07-02 | - |
| 11 | `a7b8c9d0e1f2_add_invoice_multi_role_approval.py` | `invoices` 新增运营经理/销售经理确认字段（`ops_confirmed_by/at`、`sales_confirmed_by/at`）及对应审批权限 | 2026-07-25 | - |
| 12 | `d3e4f5a6b7c8_add_package_plans_table.py` | 新增包年套餐表 `package_plans`（限量/不限量，经 `package_type` 关联 `pricing_rules`） | 2026-07-25 | - |
| 13 | `e4f5a6b7c8d9_add_cancelled_by_to_invoices.py` | `invoices` 新增 `cancelled_by`（取消操作人） | 2026-07-25 | - |
| 14 | `f5a6b7c8d9e0_add_customer_confirmed_by_and_completed_by.py` | `invoices` 新增 `customer_confirmed_by`、`completed_by` | 2026-07-25 | - |
| 15 | `g6b7c8d9e0f1_add_cooperation_statuses_table.py` | 新增合作状态字典表 `cooperation_statuses` 并预置 4 条（active / suspended / terminated / noused） | 2026-07-27 | - |
| 16 | `h7c8d9e0f1g2_add_multi_floor_pricing_fields.py` | `pricing_rules` 新增 `multi_floor_pricing_type`、`additional_floor_price`；`daily_consumptions` 新增 `total_floor_count` | 2026-08-07 | - |
| 17 | `i8d9e0f1g2h3_add_upload_date_and_order_status_to_daily_orders.py` | `daily_orders` 新增 `upload_date`、`order_status`；唯一约束 `(order_code, create_date)` → `(order_code, sync_date)` | 2026-08-07 | - |
| 18 | `j9e0f1g2h3i4_make_device_type_nullable.py` | `pricing_rules.device_type`、`invoice_items.device_type` 改为可空（包年结算不区分设备类型） | 2026-08-12 | - |
| 19 | `k0f1g2h3i4j5_add_over_limit_unit_price_to_package_plans.py` | `package_plans` 新增 `over_limit_unit_price`（超量单价，默认 `base_fee / limit_count`） | 2026-08-19 | - |
| 20 | `l1m2n3o4p5q6_add_erp_systems_table.py` | 新增 ERP 系统字典表 `erp_systems`，并插入权限 `erp_systems:manage` | 2026-08-25 | - |
| 21 | `m2n3o4p5q6r7_add_value_column_to_erp_systems.py` | `erp_systems` 补 `value` 列并用 `name` 回填（兼容旧库，全新库为 no-op） | 2026-08-25 | - |
| 22 | `n3o4p5q6r7s8_convert_erp_systems_value_to_english.py` | `erp_systems.value` 由中文名转为英文标识符，同步更新 `customers.erp_system` | 2026-08-25 | - |
| 23 | `o4p5q6r7s8t9_add_api_keys_table.py` | 新增开放平台密钥表 `api_keys` | 2026-08-26 | - |
| 24 | `p5q6r7s8t9u0_add_invoice_detail_file_fields.py` | `invoices` 新增 `detail_file_path`、`detail_file_status`（pending / generating / completed / failed） | 2026-09-03 | - |
| 25 | `q6r7s8t9u0v1_add_invoice_discount_histories.py` | 新增结算单减免修改历史表 `invoice_discount_histories` | 2026-09-03 | - |
| 26 | `r7s8t9u0v1w2_change_date_to_timestamptz.py` | 日期列改 timestamptz（`invoices.period_start/end`、`pricing_rules.effective_date/expiry_date`、`daily_consumptions.consumption_date`） | 2026-09-07 | - |
| 27 | `s8t9u0v1w2x3_over_limit_unit_price_null_semantics.py` | `over_limit_unit_price` 语义改为 NULL=自动计算（`base_fee / limit_count`），等于默认值的存量转 NULL | 2026-09-12 | - |
| 28 | `t9u0v1w2x3y4_add_forecast_unit_prices_table.py` | 新增预测单价配置表 `forecast_unit_prices`（L/N/X 设备类型，支持页面运行时修改） | 2026-09-16 | - |
| 29 | `u0v1w2x3y4z5_add_sync_execution_details.py` | 新增同步执行明细表 `sync_task_log_details`（info/warning/error + 客户维度）与定时同步配置表 `sync_schedule_configs` | 2026-09-17 | - |
| 30 | `a2b3c4d5e6f7_add_auto_initiate_settlement_field.py` | `customers` 新增 `auto_initiate_settlement`（Boolean，默认按「是」处理） | 2026-09-29 | - |
| 31 | `v1w2x3y4z5a6_add_balance_whitelists_table.py` | 新增余额白名单表 `balance_whitelists`（开放平台 `/api/v1/balances` 静态余额），并插入权限 `balance_whitelist:manage` | 2026-10-13 | - |
| 32 | `w2x3y4z5a6b7_add_balance_warning_to_customers.py` | `customers` 新增余额预警 `balance_warning_level`（warning/critical，带索引）、`balance_warning_updated_at` | 2026-10-13 | - |
| 33 | `x3y4z5a6b7c8_add_remark_to_balance_whitelists.py` | `balance_whitelists` 新增 `remark` 业务备注 | 2026-10-13 | - |
| 34 | `y4z5a6b7c8d9_add_settlement_account.py` | `customers`/`invoices` 新增 `settlement_account_id`（客户级代扣结算账户，单据生成时快照） | 2026-10-21 | [结算账户方案](../specs/2026-10-21-settlement-account-plan.md) |
| 35 | `z5a6b7c8d9e0_drop_paid_status_migrate_to_completed.py` | 废弃 paid 状态：存量 `status='paid'` 迁移为 `completed`，并回填 `completed_at`/`completed_by` | 2026-10-23 | - |
| 36 | `335fb6b0948d_add_require_reconciliation_drop_auto_.py` | `customers` 新增 `require_reconciliation`（是否对账），删除 `auto_initiate_settlement` 死字段 | 2026-10-23 | - |
| 37 | `b8c9d0e1f2a3_add_discount_approval_fields.py` | `invoices` 新增减免审批字段 `discount_approver_id`、`discount_approved_at`、`discount_approval_comment` | 2026-10-24 | - |
| 38 | `c9d0e1f2a3b4_add_backup_feature.py` | 新增定时备份配置表 `backup_schedule_configs`（单行 daily_backup）与备份留痕表 `backup_records` | 2026-10-26 | [数据备份方案](../specs/2026-10-26-data-backup-plan.md) |
| 39 | `d0e1f2a3b4c5_add_vr_settlements.py` | 新增 `vr_settlements`（VR 结算主表）与 `vr_settlement_discount_histories`；`consumption_records` 新增 `vr_settlement_id` 关联列 | 2026-11-03 | [VR 结算方案](../specs/2026-11-03-vr-settlement-plan.md) |
| 40 | `e2f3a4b5c6d7_add_remark_to_vr_settlements.py` | `vr_settlements` 新增 `remark` 备注（创建时填写、全链路只读） | 2026-11-03 | - |
| 41 | `f1a2b3c4d5e6_add_invoice_item_subtotal_order_count.py` | `invoice_items` 新增 `subtotal`、`order_count`（修正多层递增模式的小计口径，可空不回填） | 2026-11-10 | [明细一致性方案](../specs/2026-11-05-invoice-detail-consistency-plan.md) |
| 42 | `g2h3i4j5k6l7_add_invoice_item_multi_floor_freeze.py` | `invoice_items` 新增 `multi_floor_pricing_type`、`additional_floor_price` 冻结快照，避免规则变更后明细漂移 | 2026-11-10 | - |
| 43 | `h3i4j5k6l7m8_add_daily_order_house_level_unique_key.py` | `daily_orders` 唯一键改为 `(order_code, COALESCE(custom_code,''), sync_date)`，支持同一订单号多房源 | 2026-11-10 | - |
| 44 | `i4j5k6l7m8n9_add_daily_order_detail_snapshot_columns.py` | `daily_orders` 新增 19 个明细展示快照列（`project_name`/`city`/`nest_area`/`editor_*` 等），月明细不再回查外部库 | 2026-11-10 | - |
| 45 | `j5k6l7m8n9_add_daily_order_nest_created.py` | `daily_orders` 新增 `nest_created`（「处理完成时间」改取房源主表 nest.created） | 2026-11-10 | [nest_created 方案](../specs/2026-11-10-invoice-detail-nest-created-plan.md) |
| 46 | `k6l7m8n9o0p1_add_crm_recharge.py` | 新增 CRM 只读镜像表 `crm_customers`/`crm_payments`/`crm_sync_runs`；`customers` 新增 `crm_customer_id`；`recharge_records` 新增 `recharge_date`（回填后非空） | 2026-11-13 | [CRM 充值方案](../specs/2026-11-11-crm-recharge-management-plan.md) |
| 47 | `l7m8n9o0p1q2_add_crm_settings.py` | 新增 `crm_settings` 单行页面配置（`base_url`/`corp_id`/`phone`/`password_cipher` 密文），空表时运行期回退环境变量 | 2026-11-13 | - |
| 48 | `m8n9o0p1q2r3_add_scanned_payment_count.py` | `crm_sync_runs` 新增 `scanned_payment_count`（全局回款列表主路径的已检查回款数） | 2026-11-13 | - |

---

## 当前表结构概览

### 用户与权限模块
| 表名 | 说明 |
|------|------|
| `users` | 用户表 |
| `roles` | 角色表 |
| `permissions` | 权限表 |
| `user_roles` | 用户-角色关联 |
| `role_permissions` | 角色-权限关联 |
| `token_blacklist` | JWT Token 黑名单 |

### 客户管理模块
| 表名 | 说明 |
|------|------|
| `customers` | 客户基础信息 |
| `customer_profiles` | 客户画像 |
| `customer_groups` | 客户分组 |
| `customer_tags` | 客户-标签关联 |
| `profile_tags` | 画像-标签关联 |
| `tags` | 标签定义 |
| `industry_types` | 行业类型字典 |
| `customer_industries` | 客户-行业关联 |

### 结算与余额模块
| 表名 | 说明 |
|------|------|
| `customer_balances` | 客户余额 |
| `recharge_records` | 充值记录 |
| `pricing_rules` | 计费规则 |
| `invoices` | 结算单 |
| `invoice_items` | 结算单明细 |
| `consumption_records` | 消费流水 |

### 系统模块
| 表名 | 说明 |
|------|------|
| `daily_usage` | 每日用量 |
| `sync_logs` | 同步任务日志 |
| `audit_logs` | 操作审计日志 |
| `files` | 附件文件 |

---

## 迁移操作指南

### 查看当前迁移状态
```bash
cd backend && python -m alembic current
```

### 查看迁移历史
```bash
cd backend && python -m alembic history --verbose
```

### 创建新迁移
```bash
cd backend && python -m alembic revision --autogenerate -m "描述"
```

### 执行迁移
```bash
cd backend && python -m alembic upgrade head
```

### 回滚一个迁移
```bash
cd backend && python -m alembic downgrade -1
```

---

## 注意事项

1. **迁移顺序**：当前迁移链（`05c6bedcf166` → `m8n9o0p1q2r3`，共 49 个）无 merge 节点，是单条线性链，按 `down_revision` 顺序执行即可；旧链的 `dc8859579c78_merge_heads.py` 已随 2026-05-07 重置删除
2. **生产环境**：执行迁移前务必备份数据库（`pg_dump`）
3. **数据迁移**：以下迁移含数据写入/转换，执行时注意观察日志——`8f6a04467a12`（行业类型种子）、`n3o4p5q6r7s8`（`erp_systems.value` 中文→英文并同步 `customers.erp_system`）、`s8t9u0v1w2x3`（`over_limit_unit_price` 等于默认值的存量归为 NULL）、`z5a6b7c8d9e0`（`paid` → `completed` 并回填完成时间/操作人）、`k6l7m8n9o0p1`（`recharge_date` 回填为非空）；原 `005_convert_price_policy_to_english.py` 已随旧链删除，基线直接按最终结构建表，无需再执行
4. **公司 ID 类型**：`customers.company_id` 在基线 `05c6bedcf166` 中即为 INTEGER（唯一索引 `ix_customers_company_id`），旧链 `b0ec7f3a8b31` 的 VARCHAR → INTEGER 变更已随 2026-05-07 重置并入基线，无需再执行
