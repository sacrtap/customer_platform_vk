# 执行计划

按依赖树有序执行，每步后跑对应测试。

1. [x] 数据层迁移：`backend/alembic/versions/<hash>_add_require_reconciliation_drop_auto_initiate.py`（alembic revision 生成骨架 + 手写 upgrade/downgrade）
2. [x] 后端模型 `backend/app/models/customers.py:57-58`：删 auto 字段，加 `require_reconciliation`
3. [x] 服务层 `backend/app/services/customers.py`：
   - `create_customer` 构造替换 + 经理非空校验
   - `update_customer` 可更新字段替换 + 综合校验
   - 删除筛选分支（不新增 require 筛选）
   - 导入字段/导入构造替换
4. [x] 服务层 `backend/app/services/billing.py` `submit_invoice`：开关优先分流
5. [x] 路由 `backend/app/routes/customers.py`：列表/详情响应字段、两处筛选删除、导出列/导出响应替换
6. [x] 路由 `backend/app/routes/billing/balances.py`：删除三处 auto 筛选
7. [x] 前端 `frontend/src/types/index.ts:115`：字段替换
8. [x] 前端表单四组件：CustomerFormModal.vue / AddCustomerModal.vue / EditCustomerDialog.vue / CustomerBatchEditModal.vue
9. [x] 前端筛选与详情：CustomerFilters.vue / BalanceFilters.vue / CustomerBasicTab.vue
10. [x] 测试：test_customers_api.py / test_customer_service.py / test_balance_filters.py / test_customer_service_batch.py / test_billing_service.py / useBalance.test.ts
11. [x] 验证：
    - `cd backend && source .venv/bin/activate && alembic upgrade head` + schema drift 检查
    - `pytest backend/tests/ -q`（覆盖率 ≥50%）
    - `cd frontend && npm run type-check && npm run test`
    - UI 端到端核验（uvicorn :8000 + vite :5173，admin/admin123 注入 localStorage 四键）

## 验证结果（2026-10-23 执行）

| 验证项 | 命令 | 结果 |
|---|---|---|
| 迁移应用 | `alembic upgrade head` + `check_schema_drift.py` | ✅ head=335fb6b0948d，drift PASSED |
| submit 单测 | `pytest tests/unit/test_billing_service.py -k submit` | ✅ 9 passed |
| 对账集成测试 | `pytest tests/integration/test_customers_api.py -k "reconcil or 对账"` | ✅ 4 passed |
| 客户服务/筛选单测 | `pytest tests/unit/test_customer_service.py tests/unit/test_balance_filters.py` | ✅ 50 passed |
| 后端全量 | `pytest tests/ -q` | 1248 passed；5 failed + 3 errors 均为存量失败（test_analytics_service MagicMock、test_pricing_repo tiers NOT NULL），main 基线同样失败，与本次无关 |
| 前端 type-check | `npm run type-check` | ✅ 0 error |
| 前端单测 | `npm run test` | ✅ 131 passed |
| UI 端到端 | `npx playwright test tests/e2e/test_customer_reconciliation.spec.ts --project=chromium` | ✅ 4/4 passed（渲染默认否 / required 拦截 / 开对账创建成功 True / 不开创建成功 False） |

### 实施期发现并修复的缺陷

`update_customer` 对账校验最初放在 `setattr` 赋值之后：校验抛 `ValueError` 时 ORM 对象已被改脏且 session 未 rollback，后续请求 flush 会把 `require_reconciliation=True` 落库（绕过拦截）。已将校验前置到赋值之前，并新增回归测试 `test_update_customer_validation_failure_leaves_no_dirty_state`。教训已沉淀至 `.trellis/spec/backend/database-guidelines.md` Forbidden Patterns。
