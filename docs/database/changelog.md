# 数据库变更日志

> 本文件记录所有 Alembic 数据库迁移的历史记录。
> 最后更新: 2026-04-27

---

## 迁移历史

| 序号 | 迁移文件 | 变更内容 | 日期 | 关联文档 |
|------|----------|----------|------|----------|
| 0 | `001_initial.py` | 初始表结构：users, roles, permissions, user_roles, role_permissions, customers, customer_profiles, tags, customer_tags, profile_tags, customer_balances, recharge_records, pricing_rules, invoices, invoice_items, consumption_records, daily_usage, sync_logs, audit_logs | 2026-04-01 | Phase 0 后端初始化 |
| 1 | `002_add_customer_groups.py` | 新增客户分组表 `customer_groups` 及关联字段 | 2026-04-03 | [客户分组设计](../superpowers/specs/2026-04-03-customer-groups-design.md) |
| 2 | `734bdc29cc5e_add_token_blacklist_table.py` | 新增 JWT Token 黑名单表 `token_blacklist` | 2026-04-01 | - |
| 3 | `a5d21c5761aa_add_all_missing_tables.py` | 补充缺失表：groups 关联、余额相关表扩展 | 2026-04-03 | - |
| 4 | `dc8859579c78_merge_heads.py` | 合并多个迁移头（解决并行迁移冲突） | 2026-04-03 | - |
| 5 | `003_add_customer_detail_fields.py` | 客户详情字段扩展：新增 manager_name, region, contact_person, phone 等 | 2026-04-14 | [客户详情字段设计](../superpowers/specs/2026-04-14-customer-detail-fields-design.md) |
| 6 | `003_add_files_table.py` | 新增附件表 `files`（支持支付凭证、减免证明上传） | 2026-04-14 | - |
| 7 | `004_drop_business_type.py` | 删除 `customers.business_type` 列（迁移至行业类型） | 2026-04-15 | [删除业务类型计划](../superpowers/plans/2026-04-15-delete-business-type-use-profile-industry-plan.md) |
| 8 | `fd0d4d39cef3_add_industry_types_table.py` | 新增行业类型表 `industry_types` 及 `customer_industries` 关联表 | 2026-04-15 | [行业类型设计](../superpowers/specs/2026-04-14-business-type-to-industry-type-design.md) |
| 9 | `005_convert_price_policy_to_english.py` | `customers.price_policy` 值迁移：中文→英文（定价→fixed, 阶梯→tiered, 包年→yearly） | 2026-04-17 | [price_policy 迁移设计](../superpowers/specs/2026-04-17-customer-data-import-type-migration-design.md) |
| 10 | `288fbca5e3ed_restore_token_blacklist_table.py` | 恢复 Token 黑名单表（之前迁移丢失后重建） | 2026-04-01 | - |
| 11 | `b0ec7f3a8b31_alter_company_id_to_integer.py` | `customers.company_id` 类型变更：VARCHAR(50) → INTEGER（外键关联） | 2026-04-17 | [导入类型迁移](../superpowers/specs/2026-04-17-customer-data-import-type-migration-design.md) |
| 12 | `dd4170648c62_remove_customer_level_column_from_.py` | 删除 `customers.customer_level` 列（等级体系迁移至画像表） | 2026-04-15 | [客户详情优化](../superpowers/specs/2026-04-15-customer-detail-optimization-design.md) |

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

1. **迁移顺序**：部分迁移存在合并（merge）操作，执行时需确保所有迁移文件完整
2. **生产环境**：执行迁移前务必备份数据库（`pg_dump`）
3. **数据迁移**：`005_convert_price_policy_to_english.py` 包含数据转换，执行时注意观察日志
4. **公司 ID 类型**：`b0ec7f3a8b31` 将 company_id 从 VARCHAR 改为 INTEGER，影响外部同步接口