# CRM 充值管理 — 实施清单

顺序 1→7。第 5 步（资金事务化）先把现有手动/Excel 路径改完并通过既有测试，再接 CRM 导入。

## 1. 数据模型与迁移

- [ ] `backend/app/models/crm_recharge.py`：`CrmCustomer` / `CrmPayment` / `CrmSyncRun`（字段与约束见 design.md）
- [ ] `backend/app/models/customers.py::Customer` 增 `crm_customer_id` + 部分唯一索引
- [ ] `backend/app/models/billing.py::RechargeRecord` 增 `recharge_date`、`crm_payment_id`（UNIQUE）
- [ ] `backend/app/models/__init__.py` 注册新模块
- [ ] `backend/alembic/versions/<new>_crm_recharge.py`：建表 → FK → 新列 → 回填 → NOT NULL/默认 → 索引/约束；downgrade 反向
- [ ] 验证：`.venv/bin/python -m alembic upgrade head` + `scripts/check_schema_drift.py`

## 2. CrmClient

- [ ] `backend/app/config.py`：5 个 CRM 设置项 + 官方域名校验
- [ ] `backend/app/cache/base.py::_ttl_config` 增 `crm_token: 1800`
- [ ] `backend/app/services/crm_client.py`：`CrmClient`（async context manager、httpx.AsyncClient 复用、限流、登录锁、token 缓存、分页、错误分类）
- [ ] 验证：`tests/unit/test_crm_recharge.py` 内以 `httpx.MockTransport` 覆盖业务 code、分页错误、401 重放

## 3. 同步服务与调度

- [ ] `backend/app/services/crm_recharge.py`：纯函数 `normalize_crm_name` / `score_crm_candidate` / `resolve_industry_paths` / `parse_industry_path`
- [ ] 同上：`CrmRechargeService.create_sync_run` / `execute_sync_run` / `recover_stale_sync_runs`
- [ ] `backend/app/tasks/scheduler.py`：`_sync_crm_payments`（`@monitored_task('crm_payment_sync', ...)`、Cron 22:00 CST、仅 enabled + 凭据完整时注册）+ scheduler-status job 集合
- [ ] `backend/app/main.py::on_start` 调 `recover_stale_sync_runs`

## 4. 路由与权限

- [ ] `backend/app/routes/crm_recharge.py::crm_recharge_bp`（7 端点，权限按 design.md）
- [ ] `backend/app/main.py::create_app` 注册蓝图
- [ ] `backend/scripts/seed.py::ALL_PERMISSIONS` + `backend/tests/_test_data.py::PERMISSION_ROWS` + `test_permission_drift.py` 豁免（如需）
- [ ] 客户详情/列表响应补 `crm_customer_id` / `crm_customer_external_id` / `crm_customer_name`（只读）

## 5. 资金原子性与业务日期

- [ ] `BalanceService.recharge` 事务内化 + `recharge_date`/`crm_payment_id` 参数；`batch_import_recharge` 复用
- [ ] `routes/billing/balances.py::recharge`、`routes/billing/imports.py::import_balance` 外层事务 + savepoint + `create_audit_entry(auto_commit=False)`
- [ ] `CrmRechargeService.import_payment`：幂等 → 实时复核 → 锁内复查 → recharge → snapshot → 审计 → 缓存失效
- [ ] 日期读点切换：`balances.py`（最近充值/本月 stats/排序/导出）、`analytics.py::get_balance_trend`、`invoice_excel.py::_query_balance_info`、`billing.py::get_recharge_records` 响应字段
- [ ] `routes/database_management.py::clear_balance_data` 表锁 + CRM 凭据保护
- [ ] 精确 grep `RechargeRecord.created_at` 剩余命中，除创建时间展示/排序/迁移外全部改 `recharge_date`

## 6. 前端

- [ ] `frontend/src/types/index.ts`、`frontend/src/api/billing.ts`：`RechargeRecord` 增 `recharge_date`/`crm_payment_id`/`crm_payment_external_id`
- [ ] `frontend/src/api/crmRecharge.ts` + 类型
- [ ] `frontend/src/views/system/CrmRecharge.vue`（同步区/筛选/表格/导入弹窗/5s 轮询）
- [ ] `frontend/src/views/customers/components/CrmCustomerBinding.vue` + `EditCustomerDialog.vue` 集成（列表与详情复用）
- [ ] `frontend/src/router/index.ts`、`AppSidebar.vue`、`useAppLayout.ts::navSections`、`permissionGroups.ts`
- [ ] `RechargeRecordModal.vue`、`BalanceTable.vue`、`useBalance.ts` 日期口径

## 7. 验证

```bash
# backend
cd backend
POSTGRES_DB=customer_platform_test .venv/bin/python -m pytest tests/unit/test_crm_recharge.py tests/unit/test_billing_service.py tests/unit/test_permission_drift.py tests/unit/test_route_names.py -q
POSTGRES_DB=customer_platform_test .venv/bin/python -m pytest tests/integration/test_crm_recharge_api.py tests/integration/test_billing_api.py tests/integration/test_billing_import_export_api.py tests/integration/test_invoice_excel.py -q
POSTGRES_DB=customer_platform_test .venv/bin/python -m pytest tests/integration/test_migrations.py -q
.venv/bin/python -m ruff check app/ tests/
.venv/bin/python -m pyright

# frontend
cd frontend
npx vitest run src/views/crm-recharge src/views/customers/components/__tests__/CrmCustomerBinding.test.ts
npm run type-check
```

- [x] 集成测试用真实 PG/Redis 专用实例，`POSTGRES_DB=customer_platform_test`；CRM 响应用脱敏 fixture / MockTransport
- [x] 验收结论写入任务笔记（目标、改动文件、命令与输出、通过/失败）→ `acceptance.md`
