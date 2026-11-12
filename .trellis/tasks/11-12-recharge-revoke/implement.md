# 余额充值记录撤销（实施清单）

## 1. 权限
- [ ] `backend/scripts/seed.py`：`billing:recharge_revoke`
- [ ] `backend/tests/_test_data.py`：同步权限行
- [ ] `backend/scripts/fix_add_recharge_revoke_permission.py`：幂等补权限 + 关联超管 + 失效缓存

## 2. 服务
- [ ] `backend/app/services/billing.py`：`BalanceService.revoke_recharge(...)`
  - 锁序 Customer → 余额行 → 记录
  - CRM 来源 400、已撤销 400、可见性 403
  - 余额不足：403 / 409 / force 成功 + shortfall
  - 软删 + 审计（`billing_recharge_revoke`）

## 3. 路由
- [ ] `backend/app/routes/billing/balances.py`：`POST /recharge-records/<id>/revoke`
  - 权限 `billing:recharge_revoke` + `billing:view`
  - `force` 仅超级管理员生效（角色名常量）
  - 提交后失效 customer/analytics/billing_consumption 缓存

## 4. 统计口径
- [ ] `backend/app/services/invoice_excel.py`：充值汇总加 `deleted_at` 过滤
- [ ] `backend/app/services/analytics.py`：充值趋势 + 历史累计加 `deleted_at` 过滤

## 5. 前端
- [ ] `frontend/src/api/billing.ts`：`revokeRechargeRecord` + 类型
- [ ] `frontend/src/views/billing/components/RechargeRecordModal.vue`：操作列 + 撤销弹窗 + 权限/来源控制
- [ ] 撤销成功后通知父页面刷新余额列表

## 6. 测试
- [ ] 单测：正常撤销 / CRM 来源拒绝 / 已撤销拒绝 / 余额不足非超管 403 / 超管未 force 409 / force 标记
- [ ] 集成：路由状态码、软删后列表消失、结算单充值汇总不含、趋势不含
- [ ] 前端：按钮可见性、原因必填、提交参数

## 7. 文档
- [ ] `.trellis/spec/backend/recharge-revoke.md` + index
- [ ] `acceptance.md` 记录真实验证

## 验证命令
```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_billing_service.py tests/unit/test_recharge_revoke.py -q
.venv/bin/python -m pytest tests/integration/test_recharge_records_api.py -q
.venv/bin/python -m pyright
.venv/bin/python -m ruff check app tests scripts && .venv/bin/python -m ruff format --check app tests scripts

cd ../frontend
npx vitest run src/views/billing/components/__tests__/RechargeRecordModal.test.ts
npx vue-tsc --noEmit && npx eslint src/views/billing src/api/billing.ts
```
