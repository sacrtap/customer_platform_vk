# 充值支持负数金额（双向资金流动）

> 归档来源：`.omo/plans/negative-recharge-amount.md`（2026-11-19 蒸馏归档，原件已删除）
> 状态：已实施 —— `backend/app/routes/billing/balances.py` 充值校验现为 `if real_amount == 0 and bonus_amount == 0:`（零金额阻断、负数放行）
> 关联：`docs/specs/2026-05-26-balance-page-fixes.md`（同一页面的列宽/预填/时间格式修复）
> 锚点说明：文中 `文件:行号` 为 2026-05 期快照，定位以符号名与路径为准

## Context

**原始请求**：用户检查余额管理页面充值功能时发现——充值金额不允许负数，赠送金额后端缺少校验。业务需要支持负数金额实现双向资金流动（充值/扣款同一表单）。

**访谈决策**：

- 实充金额：支持正数和负数
- 赠送金额：支持正数和负数，无限制
- 额度限制：不限额
- UX 术语：保留"充值"标签，用正负号区分方向
- 交互方案：最小改动 + 负数二次确认

**研究结论**（改动前的防御现状）：

- 前端三层防御：UI `min=0.01`、提交前校验（`<= 0` 报错）、后端校验 `<= 0`
- Service 层 `balance += amount` 天然支持负数
- DB `DECIMAL` 字段允许负数，无 `CheckConstraint`

## Approach

### 前端（`Balance.vue`，3 处）

1. 移除两个 `a-input-number` 的 `:min`（`real_amount` 的 `0.01`、`bonus_amount` 的 `0`）
2. placeholder 增加负数含义提示
3. `handleRecharge` 校验拆分：null/undefined → 报错；`=== 0` → 报错；`< 0` → `Modal.confirm` 显示扣除总金额，取消则中止提交（需 `import { Modal } from '@arco-design/web-vue'`）

### 后端（`routes/billing.py`，1 处）

校验从 `real_amount <= 0` 改为 `real_amount == 0`（错误信息"金额不能为零"）——正负均放行，仅零金额阻断。

### 测试

- 后端：充值测试断言从"必须大于 0"改为"不能为零"，新增 ≥3 个负数用例
- 前端：新增负数金额确认对话框 E2E 用例

## 完成定义与护栏

完成定义 5 条：前端可输入负数并提交；负数时弹出确认对话框；后端接受负数金额；零金额仍被阻断；现有测试通过。

护栏（Must NOT Have）4 条：不得修改 Service 层核心逻辑；不得修改数据库模型；不得改变 API 字段签名；不得破坏现有正数充值功能。

## Critical files & anchors

- `frontend/src/views/billing/Balance.vue` — 移除 `:min`、placeholder、`handleRecharge` 校验 + `Modal.confirm`
- `backend/app/routes/billing.py` — 充值校验 `== 0`（现位于 `routes/billing/balances.py`）
- `backend/tests/**` — 充值测试改断言 + 负数用例
- `frontend/tests/e2e/**` — 负数确认对话框 E2E

## Verification

```bash
cd backend && pytest tests/ -v -k billing                    # 全部 PASS
cd frontend && npx playwright test --grep "充值|balance"      # 全部 PASS
```

- 后端 31 个测试全过、前端 9 个测试全过
- curl 验证：`real_amount=5000` → 200；`real_amount=-3000` → 200 且余额扣减；`real_amount=0` → 400"不能为零"
- Playwright 验证：正数无弹窗直接提交；负数弹确认（文案"本次操作将从客户余额中扣除 XXX 元"）；取消不提交且表单保持；确认后扣减成功；0 金额阻断

## Assumptions

- Service 层 `balance += amount` 与 DB DECIMAL 均无需改动，全部收口在路由校验。
- 负数仅代表扣款方向，不引入独立的"扣款"入口或端点。
