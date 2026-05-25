# 支持负数金额充值实施计划

## TL;DR

> **Quick Summary**: 修改充值功能，使实充金额和赠送金额均支持正负数输入，负数时增加二次确认对话框，防止误操作。
> 
> **Deliverables**: 
> - 前端 `Balance.vue` 去掉输入限制 + 二次确认
> - 后端 `routes/billing.py` 校验规则从 `<= 0` 改为 `== 0`
> - 更新/新增对应测试用例
> 
> **Estimated Effort**: Short
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1+2 → Task 3

---

## Context

### 原始请求
用户检查余额管理页面充值功能时发现：充值金额不允许负数，赠送金额后端缺少校验。业务现在需要支持负数金额实现双向资金流动（充值/扣款同一表单）。

### 采访总结
**关键讨论**：
- 实充金额范围：C — 支持正数和负数
- 赠送金额范围：D — 支持正数和负数，无限制
- 额度限制：不限额
- UX 术语：A — 保留"充值"标签，用正负号区分方向
- 交互方案：B — 最小改动 + 负数二次确认

### 研究结果
- 前端有 3 层防御：UI min=0.01、提交前校验、后端 <= 0
- Service 层 `balance += amount` 天然支持负数
- 数据库 DECIMAL 字段允许负数，无 CheckConstraint

---

## Work Objectives

### 核心目标
使充值功能支持正负数金额，负数时弹二次确认，后端校验同步调整。

### 具体交付物
- 修改 `frontend/src/views/billing/Balance.vue`（3 处改动）
- 修改 `backend/app/routes/billing.py`（1 处改动）
- 更新测试

### 完成定义
- [ ] 前端可输入负数并提交
- [ ] 负数时弹出确认对话框
- [ ] 后端接受负数金额
- [ ] 零金额仍被阻断
- [ ] 现有测试通过

### Must Have
- 实充金额支持正负数
- 赠送金额支持正负数
- 负数必须二次确认
- 零金额始终阻断

### Must NOT Have（护栏）
- 不得修改 Service 层核心逻辑
- 不得修改数据库模型
- 不得改变 API 字段签名
- 不得破坏现有正数充值功能

---

## Verification Strategy

### 测试决策
- **Infrastructure exists**: YES
- **Automated tests**: TDD
- **Framework**: pytest (后端), vitest/jest (前端)

### QA Policy
每项任务需包含 Agent 执行 QA 场景：
- **前端**: Playwright 输入负数 → 确认对话框出现 → 确认/取消行为验证
- **后端**: pytest 测试零金额/正数/负数请求

---

## Execution Strategy

### 并行执行 Waves

```
Wave 1（开始 - 可并行 2 个独立任务）:
├── Task 1: 前端改动（Balance.vue） [quick]
└── Task 2: 后端改动（routes/billing.py） [quick]

Wave 2（Wave 1 后 - 测试 + 验证）:
├── Task 3: 更新后端测试 + 运行验证 [quick]
└── Task 4: 前端 E2E 测试 + 运行验证 [quick]

Wave FINAL（4 个并行审查 → 用户确认）:
├── Task F1: 计划合规审计 [oracle]
├── Task F2: 代码质量审查 [unspecified-high]
├── Task F3: 手动 QA [unspecified-high]
└── Task F4: 范围检查 [deep]
```

---

## TODOs

- [ ] 1. 前端 Balance.vue 改动

  **What to do**:
  - 移除 `real_amount` 的 `:min="0.01"` 属性（第 247 行）
  - 移除 `bonus_amount` 的 `:min="0"` 属性（第 257 行）
  - 更新 `real_amount` placeholder 添加负数提示
  - 修改 `handleRecharge` 校验（第 575-578 行）：
    - 将 `!rechargeForm.real_amount || rechargeForm.real_amount <= 0` 拆开
    - 改为：null/undefined → 报错；=== 0 → 报错
    - 当 `real_amount < 0` 时，调用 `Modal.confirm` 显示扣除总金额
    - 用户取消则 return false
  - 需要 `import { Modal } from '@arco-design/web-vue'`

  **Must NOT do**:
  - 不修改表单整体结构
  - 不改变其他校验逻辑（如 customer_id 必填）
  - 不修改充值按钮文案或页面标题

  **推荐 Agent Profile**:
  - **Category**: `quick` — 单文件少量改动
  - **Skills**: [`frontend-ui-ux`]
  - **Skills Omitted**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 Task 2 并行）
  - **Blocked By**: None

  **References**:
  - `frontend/src/views/billing/Balance.vue:242-261` — 充值金额和赠送金额的 a-input-number 定义
  - `frontend/src/views/billing/Balance.vue:570-616` — handleRecharge 完整实现
  - `frontend/src/views/billing/Balance.vue:306` — 现有 import（Arco Design 组件）
  - `frontend/src/utils/formatters.ts:formatCurrency` — 金额格式化函数

  **Acceptance Criteria**:
  - [ ] `:min` 属性已从两个 a-input-number 移除
  - [ ] placeholder 提示负数含义
  - [ ] `handleRecharge` 中：null → 报错，0 → 报错，< 0 → Modal.confirm
  - [ ] Modal.confirm 确认后可正常提交
  - [ ] Modal.confirm 取消后中止提交
  - [ ] `import { Modal }` 已添加

  **QA Scenarios**:

  ```
  Scenario: 正数充值正常提交（回归测试）
    Tool: Playwright
    Steps:
      1. 导航至 http://localhost:5173/billing/balances
      2. 点击某行的"充值"按钮
      3. 输入充值金额 5000
      4. 点击确定
    Expected Result: 充值成功，无确认对话框弹出
    Evidence: .omo/evidence/task-1-positive-recharge.png

  Scenario: 负数金额弹出确认对话框
    Tool: Playwright
    Steps:
      1. 导航至充值页面，点击"充值"
      2. 输入充值金额 -3000
      3. 点击确定
    Expected Result: 弹出确认对话框，显示"本次操作将从客户余额中扣除 XXX 元"
    Evidence: .omo/evidence/task-1-negative-confirm.png

  Scenario: 确认对话框点击取消
    Tool: Playwright
    Steps:
      1. 输入负数金额，触发确认对话框
      2. 点击"取消"
    Expected Result: 对话框关闭，不提交充值请求，表单保持打开
    Evidence: .omo/evidence/task-1-negative-cancel.png

  Scenario: 确认对话框点击确认
    Tool: Playwright
    Steps:
      1. 输入负数金额 -3000，触发确认对话框
      2. 点击"确认扣款"
    Expected Result: 提交成功，余额被扣减
    Evidence: .omo/evidence/task-1-negative-confirmed.png

  Scenario: 零金额被阻断
    Tool: Playwright
    Steps:
      1. 输入充值金额 0
      2. 点击确定
    Expected Result: 显示错误提示"充值金额不能为 0"，不提交
    Evidence: .omo/evidence/task-1-zero-blocked.png
  ```

  **Commit**: YES (group: 1-2)
  - Message: `feat(billing): 支持负数金额充值，添加二次确认`
  - Files: `frontend/src/views/billing/Balance.vue`
  - Pre-commit: `cd frontend && npm run lint`

- [ ] 2. 后端 routes/billing.py 校验调整

  **What to do**:
  - 第 378 行：将 `real_amount <= 0` 改为 `real_amount == 0`
  - 错误信息保持或调整为"金额不能为零"

  **Must NOT do**:
  - 不修改 Service 层
  - 不修改数据库模型
  - 不修改 API 响应格式

  **推荐 Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`backend-development`]
  - **Skills Omitted**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 Task 1 并行）
  - **Blocked By**: None

  **References**:
  - `backend/app/routes/billing.py:357-382` — 充值路由完整实现
  - `backend/app/routes/billing.py:375-376` — real_amount/bonus_amount 解析
  - `backend/app/routes/billing.py:378-382` — 校验逻辑及错误响应

  **Acceptance Criteria**:
  - [ ] 第 378 行条件改为 `real_amount == 0`
  - [ ] 正数金额请求正常通过
  - [ ] 负数金额请求正常通过
  - [ ] 零金额请求返回 400 错误

  **QA Scenarios**:

  ```
  Scenario: 正数充值请求通过
    Tool: Bash (curl)
    Steps:
      1. curl -X POST http://localhost:8000/api/v1/billing/recharge \
         -H "Authorization: Bearer <token>" \
         -H "Content-Type: application/json" \
         -d '{"customer_id": 1, "real_amount": 5000}'
    Expected Result: HTTP 200，返回更新后的余额
    Evidence: .omo/evidence/task-2-positive-response.txt

  Scenario: 负数充值请求通过
    Tool: Bash (curl)
    Steps:
      1. curl -X POST http://localhost:8000/api/v1/billing/recharge \
         -H "Authorization: Bearer <token>" \
         -H "Content-Type: application/json" \
         -d '{"customer_id": 1, "real_amount": -3000}'
    Expected Result: HTTP 200，余额被正确扣减
    Evidence: .omo/evidence/task-2-negative-response.txt

  Scenario: 零金额请求被拒绝
    Tool: Bash (curl)
    Steps:
      1. curl -X POST http://localhost:8000/api/v1/billing/recharge \
         -H "Authorization: Bearer <token>" \
         -H "Content-Type: application/json" \
         -d '{"customer_id": 1, "real_amount": 0}'
    Expected Result: HTTP 400，返回错误信息包含"不能为零"
    Evidence: .omo/evidence/task-2-zero-rejected.txt
  ```

  **Commit**: YES (group: 1-2)
  - Message: `feat(billing): 支持负数金额充值，添加二次确认`
  - Files: `backend/app/routes/billing.py`
  - Pre-commit: `cd backend && ruff check app/routes/billing.py`

- [ ] 3. 更新后端测试

  **What to do**:
  - 找到测试充值功能的 pytest 测试文件
  - 将"必须大于 0"断言改为"不能为零"断言
  - 新增负数充值测试用例
  - 运行 `pytest` 验证所有测试通过

  **Must NOT do**:
  - 不修改 Service 层测试（service 逻辑不变）
  - 不修改不相关测试文件

  **推荐 Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`test-fixing`]
  - **Skills Omitted**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2（与 Task 4 并行）
  - **Blocked By**: Task 2

  **References**:
  - `backend/tests/` — 测试目录结构
  - `grep -r "recharge" backend/tests/ --include="*.py"` — 找到充值相关测试

  **Acceptance Criteria**:
  - [ ] 找到并更新所有充值测试
  - [ ] 负数充值测试通过
  - [ ] `pytest` 全部通过
  - [ ] 新增 ≥3 个负数金额测试用例

  **QA Scenarios**:

  ```
  Scenario: 运行所有 billing 相关测试
    Tool: Bash (pytest)
    Steps:
      1. cd backend && pytest tests/ -v -k billing
    Expected Result: 所有测试 PASS，0 failures
    Evidence: .omo/evidence/task-3-test-output.txt

  命令: `cd backend && pytest tests/ -v -k billing`
  预期输出: 全部测试 PASS，0 failures
  ```

  **Commit**: YES（独立提交）
  - Message: `test(billing): 更新后端充值测试支持负数金额`
  - Files: `backend/tests/**/*.py`
  - Pre-commit: `cd backend && pytest tests/ -v`

- [ ] 4. 前端 E2E 测试

  **What to do**:
  - 找到充值功能的 Playwright 测试文件
  - 新增负数金额测试用例（确认对话框流程）
  - 运行 Playwright 测试验证

  **Must NOT do**:
  - 不修改不相关 E2E 测试

  **推荐 Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`webapp-testing`, `qa-testing-playwright`]
  - **Skills Omitted**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2（与 Task 3 并行）
  - **Blocked By**: Task 1

  **References**:
  - `frontend/tests/e2e/` — Playwright E2E 测试目录
  - `grep -r "recharge\|充值\|Balance" frontend/tests/ --include="*.spec.ts"`

  **Acceptance Criteria**:
  - [ ] 找到充值 E2E 测试文件
  - [ ] 新增负数金额确认对话框测试
  - [ ] Playwright 测试全部通过

  **QA Scenarios**:

  ```
  Scenario: 运行充值 E2E 测试
    Tool: Bash (npm test)
    Steps:
      1. cd frontend && npx playwright test --grep "充值\|recharge\|balance"
    Expected Result: 所有相关测试 PASS
    Evidence: .omo/evidence/task-4-e2e-output.txt

  命令: `cd frontend && npx playwright test --grep "充值|recharge|balance"`
  预期输出: 所有相关测试 PASS
  ```

  **Commit**: YES（独立提交）
  - Message: `test(billing): 新增前端充值负数金额 E2E 测试`
  - Files: `frontend/tests/e2e/**/*.spec.ts`
  - Pre-commit: `cd frontend && npx playwright test`

---

## Final Verification Wave（所有实现任务完成后执行）

- [ ] F1. **计划合规审计** — `oracle`
  检查：是否所有 Must Have 已实现？Must NOT Have 无违反？证据文件存在？

- [ ] F2. **代码质量审查** — `unspecified-high`
  检查：`tsc --noEmit` / `ruff check` 通过？无 as any / @ts-ignore / console.log？

- [ ] F3. **手动 QA** — `unspecified-high`
  执行 ALL QA scenarios，截图确认。交叉测试：正数 → 负数 → 零数连续操作。

- [ ] F4. **范围检查** — `deep`
  检查：每个任务改动 1:1 于规格？无额外修改？无跨任务文件污染？

---

## Commit Strategy

- **1 + 2**: `feat(billing): 支持负数金额充值，添加二次确认` — Balance.vue, routes/billing.py
- **3**: `test(billing): 更新后端充值测试支持负数金额` — backend/tests/
- **4**: `test(billing): 新增前端充值负数金额 E2E 测试` — frontend/tests/e2e/

---

## Success Criteria

### 验证命令
```bash
cd backend && pytest tests/ -v -k billing  # 全部 PASS
cd frontend && npx playwright test --grep "充值|balance"  # 全部 PASS
```

### 最终检查清单
- [ ] 所有 "Must Have" 已实现
- [ ] 所有 "Must NOT Have" 无违反
- [ ] 所有测试通过
- [ ] 负数二次确认正常工作
