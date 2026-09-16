# 导入导出功能优化 — 实施计划

## 有序实施清单

### Phase 0: 权限细粒度拆分与存量迁移（前置）
0. `backend/scripts/seed.py`：
   - ALL_PERMISSIONS：移除 `("billing:import", ...)` 与 `("billing:export", ...)`，新增 8 码（balance/pricing/package/invoice × import/export）
   - PRESET_ROLES：「运营经理」「销售经理」中原 `billing:export` 替换为全部 4 个导出码（等价迁移）
   - 新增存量迁移逻辑（步骤 2.6）：扫描 role_permissions 中旧码 `billing:export` → 为新角色授予 4 导出码；旧码 `billing:import` → 4 导入码；幂等可重复执行
   - 新增旧码清理（步骤 2.7）：等价授予完成后解除绑定并删除废弃 Permission 记录，避免权限清单残留僵尸权限
1. `backend/tests/integration/conftest.py`：权限注册列表（L221 附近）与 FULL_PERMISSIONS（L442 附近）改用新码（8 个全量）
2. 后端使用点：`backend/app/routes/billing/imports.py:20`（import_balance）→ `billing:balance_import`；`backend/app/routes/billing/invoices.py:1147`（export_invoices）→ `billing:invoice_export`
3. 前端使用点：`frontend/src/views/billing/Balance.vue:15` → `can('billing:balance_import')`；`frontend/src/views/billing/Invoices.vue:6` → `can('billing:invoice_export')`

### Phase 1: 后端 — 共享辅助函数抽取（余额导出前置）
4. `backend/app/routes/billing/balances.py`：
   - 抽取 `_parse_balance_filters(request) -> dict`（参数解析+校验）
   - 抽取 `_query_balance_rows(db, filters, sort_by, sort_order, limit) -> list[dict]`（查询 + 燃尽统计组装）
   - `get_balances` 改为调用共享函数（行为不变）
   - 新增 `GET /billing/balances/export`（权限 billing:balance_export）：调用 `_query_balance_rows(limit=50000)` → DataFrame → raw 返回；列对齐 BalanceTable

### Phase 2: 后端 — 计费规则导入导出
5. `backend/app/routes/billing/pricing.py`：
   - 新增 `POST /pricing-rules/import`（权限 billing:pricing_import）：读 Excel → company_id→customer_id 映射 → 逐行 `create_pricing_rule`（日期 local_date_to_utc_start/end，捕获 ValueError 为行错误）→ 审计 → invalidate_billing_cache
   - 新增 `GET /pricing-rules/import-template`（openpyxl，英文列名 + 第2行中文说明，tiers 附样例 JSON）
   - 新增 `GET /pricing-rules/export`（权限 billing:pricing_export）：PricingService.get_pricing_rules(limit 50000) → DataFrame → raw
   - 审计：`build_batch_audit_summary(operation="pricing_rule_import", module=billing)` + `create_audit_entry`

### Phase 3: 后端 — 包年套餐导入导出
6. `backend/app/routes/billing/packages.py`：
   - 新增 `POST /package-plans/import`（权限 billing:package_import）：读 Excel → 校验（name/package_type/base_fee/限量 limit_count、package_type 唯一含软删除）→ 逐行创建 → 审计
   - 新增 `GET /package-plans/import-template`
   - 新增 `GET /package-plans/export`（权限 billing:package_export）：筛选 keyword/status/is_unlimited → DataFrame → raw

### Phase 4: 后端 — 结算单导入
7. `backend/app/routes/billing/invoices.py`：
   - 新增 `POST /invoices/import`（权限 billing:invoice_import）：读 Excel → company_id→customer_id 映射 → 受控字段（company_id/period_start/period_end/total_amount/discount_amount/invoice_no 可选）→ status 固定 draft、is_auto_generated=False → invoice_no 缺省按 `INV-YYYYMMDD-{customer_id}-{4位随机码}` 生成 → 逐行创建 → 审计
   - 新增 `GET /invoices/import-template`
   - 仅主表导入（明细 Deferred）

### Phase 5: 前端 — API 层
8. `frontend/src/api/billing.ts` 新增：
   - `exportBalances(params)` → GET /billing/balances/export (blob)
   - `importPricingRules(file)`、`downloadPricingRuleTemplate()`、`exportPricingRules(params)`
   - `importPackagePlans(file)`、`downloadPackagePlanTemplate()`、`exportPackagePlans(params)`
   - `importInvoices(file)`、`downloadInvoiceTemplate()`

### Phase 6: 前端 — 通用导入弹窗 + 页面接线
9. 新建 `frontend/src/views/billing/components/ImportModal.vue`（props: title/importApi/templateApi/templateFileName；复用 ImportBalanceModal 样式模式）
10. `Balance.vue`：PageHeader 加「导出」按钮 `can('billing:balance_export')`，抽 `buildBalanceExportParams()`（复用 filters+advancedFilters+sortState 映射）调 exportBalances
11. `PricingRules.vue`：加「导入规则」「导出」按钮 + ImportModal（pricing_import/pricing_export）
12. `PackagePlans.vue`：加「导入套餐」「导出」按钮 + ImportModal（package_import/package_export）
13. `Invoices.vue`：加「导入」按钮 + ImportModal（invoice_import）

### Phase 7: 测试
14. 后端集成测试 `backend/tests/integration/`：
    - balances export：筛选参数生效、文件返回、无数据 40002、权限拦截（billing:balance_export）
    - pricing import：成功创建三种类型、必填缺失、行级错误（含冲突）、模板下载、权限拦截（pricing_import）
    - pricing export：筛选、文件返回（pricing_export）
    - packages import：成功、package_type 重复报错、必填缺失（package_import）
    - packages export：筛选、文件返回（package_export）
    - invoices import：成功 draft 状态、company_id 不存在、金额非法、invoice_no 自动生成、权限拦截（invoice_import）
    - 权限迁移回归：conftest FULL_PERMISSIONS 用新码后既有 billing 测试通过；旧码无残留引用
15. 前端测试（如有既有组件测试惯例）：ImportModal 基础行为可选；页面按钮权限 v-if 不强制

### Phase 8: 验证
16. 后端：`make test-cov`（覆盖率 ≥50% 维持）；若涉及大重构跑 `make test-all`
17. 前端：`npm run type-check`、`npm run lint`、`npm run test`（既有套件不回归）
18. 客户管理导入导出检查（REQ-1）：读代码确认端点/按钮/模板/错误反馈链路完整；必要时冒烟验证
19. 全库 grep `billing:import`/`billing:export`（除注释/文档说明外）应为空，验证 AC-6

## 验证命令

```bash
# 后端（backend/ 目录）
make test-fast        # 快速单测
make test-cov         # 全量+覆盖率（CI 标准 ≥50%）
# 前端（frontend/ 目录）
npm run type-check
npm run lint
npm run test
```

## 风险文件 / 回滚点

| 文件 | 风险 | 回滚 |
|------|------|------|
| backend/scripts/seed.py | 权限码变更影响存量角色绑定 | 保留旧码→新码映射逻辑，幂等重跑；必要时角色回绑旧码 |
| backend/tests/integration/conftest.py | 夹具权限变更影响既有 billing 测试 | git revert 单文件 |
| backend/app/routes/billing/balances.py | get_balances 机械重构，影响既有余额列表 | 恢复共享函数抽取（git revert 单文件） |
| backend/app/routes/billing/pricing.py | 新增 3 端点；导入依赖服务层冲突检查 | 移除新端点 |
| backend/app/routes/billing/packages.py | 新增 3 端点 | 移除新端点 |
| backend/app/routes/billing/invoices.py | 新增 2 端点（+export 权限码变更）；invoice_no 唯一性 | 移除新端点 |
| frontend/src/views/billing/*.vue | 页面接线 + 权限码变更 | 移除按钮与 ImportModal 引用 |

## task.py start 前检查

- [ ] prd.md 需求/验收完整（已完成，5 项关键决策均已确认）
- [ ] design.md 覆盖数据流与契约（已完成，含权限迁移清单）
- [ ] 后端共享函数抽取后 `make test-fast` 通过（实施中）
- [ ] 新增端点权限装饰器齐全（@auth_required + @require_permission，且用新码）
- [ ] 全库无旧权限码残留引用（AC-6）
- [ ] 审计日志在导入端点统一落库
