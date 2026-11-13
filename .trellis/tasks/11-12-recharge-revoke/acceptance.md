# 验收记录：余额充值记录撤销

## 验收目标

余额管理「充值记录」支持逐条撤销手动/Excel 充值：软删记录 + 回退余额；
余额已被消耗时仅超级管理员可 `force` 撤销并标记线下核对；CRM 来源充值在余额页禁止撤销；
软删后所有充值统计口径不再计入该笔。

## 实际变更文件

后端：
- `backend/app/services/billing.py`：新增 `RechargeRevokeError`、`serialize_balance`、
  `BalanceService.revoke_recharge`（锁序客户→余额行→记录，加锁复核软删，余额不足 403/409/force）
- `backend/app/routes/billing/balances.py`：`POST /billing/recharge-records/<id>/revoke`
  （`billing:recharge_revoke` + `billing:view`，force 仅超管生效，缓存失效）
- `backend/app/services/invoice_excel.py`：结算单期间充值汇总加 `deleted_at` 过滤
- `backend/app/services/analytics.py`：充值趋势 + 历史累计充值加 `deleted_at` 过滤
- `backend/scripts/seed.py`：新增权限 `billing:recharge_revoke`（billing 组，计数 23→24）
- `backend/scripts/fix_add_recharge_revoke_permission.py`：存量库幂等补权限，仅关联超管 + 失效权限缓存
- `backend/tests/_test_data.py`：同步权限行
- `backend/tests/unit/test_recharge_revoke.py`：9 个用例（新增）
- `backend/tests/integration/test_billing_api.py`：3 个用例（新增）

前端：
- `frontend/src/api/billing.ts`：`revokeRechargeRecord` + 类型
- `frontend/src/views/billing/components/RechargeRecordModal.vue`：撤销按钮 + 撤销弹窗（余额预览、原因必填、超管强制勾选），`can`/`isSuperAdmin` 由父页面注入
- `frontend/src/views/billing/Balance.vue`：注入权限 prop，`@revoked` 刷新余额列表
- `frontend/src/views/billing/components/__tests__/RechargeRecordModal.revoke.test.ts`：5 个用例（新增）

规范：
- `.trellis/spec/backend/recharge-revoke.md` + `index.md` 条目

## 已执行验证

| 命令 | 结果 |
|---|---|
| `pytest tests/unit/test_recharge_revoke.py -q` | 9 passed |
| `pytest tests/unit -q` | 995 passed |
| `pytest tests/integration/test_billing_api.py -q` | 79 passed（含新增 3 个） |
| `pytest tests/unit/test_permission_drift.py tests/unit/test_test_data_consistency.py -q` | 5 passed |
| `pytest tests/unit/test_invoice_excel.py tests/unit/test_invoice_detail_generator.py -q` | 24 passed |
| `pytest tests/integration/test_analytics_api.py -k trend -q` | 7 passed |
| `pyright` | 0 error, 0 warning |
| `ruff check app tests scripts` + `ruff format --check` | All checks passed |
| `vitest run src/views/billing` | 66 passed（含新增 5 个） |
| `vue-tsc --noEmit` + `eslint src/views/billing` | 无问题 |

### 真实环境端到端（开发库 + 运行中的后端 8000）

- 建临时客户 → 充值 10000/2000 → `POST /billing/recharge-records/<id>/revoke`
  → `200`，返回余额 `0/0/0`；记录列表 `total=0`；重复撤销 `400 该充值记录已撤销`。
- 余额不足分支（手工把余额清零模拟已消耗）：非 force → `409 余额不足以回退…`；
  `force=true` → `200`，`needs_manual_reconciliation=true`，余额 `-5000.00`（欠款语义）。
- 清理：删除临时客户、余额、充值记录与对应审计，开发库无残留。

### 浏览器验收（前端 5173，headless Chromium）

- 余额管理 → 按客户名称筛选 → 「记录」→ 充值记录 tab：
  - 表头新增「操作」列，「手动/导入」来源记录显示红色描边「撤销」按钮（权限已生效）；
  - 点击后弹窗展示客户/入账金额/来源/归期/入账时间/撤销后余额 ¥0.00、原因必填输入、
    超管「余额不足时强制撤销」勾选与说明文案；
  - 未提交（避免影响真实库），关闭页面。
- 布局：首版 modal 宽 990 导致操作列需横向滚动，已调整为 modal 1160 + 表格 1045，
  金额明细 `nowrap`，实测撤销按钮完整可见、金额不折行。

### 统计口径证据

`test_revoke_removes_recharge_from_balance_trend`：历史月充值 10000 → 撤销前该月趋势余额
10000，撤销后 0。修复前该断言失败（趋势仍计入软删记录）。

## 结论

功能完成，全部验证通过。权限补丁脚本已在开发库执行：
`billing:recharge_revoke` id=361，已关联 `超级管理员`，权限缓存已失效。
