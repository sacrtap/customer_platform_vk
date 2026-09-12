# billing 核心链变更 → 受影响检查映射

**创建日期**: 2026-09-12
**目的**: 为 billing 相关变更提供到受影响检查的确定路由，确保最终变更总能被覆盖其行为与风险的检查验证。
**配套门禁**: `.github/workflows/pr-checks.yml` 的 `backend-integration-tests` job（PR 合并前自动运行真实 Postgres + Redis 集成测试）。

---

## 使用方式

修改 billing 相关文件后，按下面映射运行最小相关检查；PR 门禁会自动执行其中可自动化的部分。若映射未覆盖你的变更面，应补充对应检查而不是跳过。

## 后端变更面映射

| 变更文件 / 变更面 | 最小受影响检查 | 覆盖的行为与风险 |
|---|---|---|
| `backend/app/services/billing.py`（余额扣款/充值/重算） | `pytest tests/unit/test_billing_service.py`（行级锁、先赠后实、余额不足、十进制精度） | 并发扣款 `SELECT FOR UPDATE`、tenacity 重试耗尽、`batch_import` 部分失败回滚 |
| `backend/app/services/billing.py`（`InvoiceService` 结算计算） | `pytest tests/integration/test_billing_api.py::TestInvoiceFlow`（结算单生成/提交/确认/付款/完成全链路） | 套餐内用量上限、`over_limit_unit_price` NULL=自动计算语义、结算金额正确性 |
| `backend/app/routes/billing/balances.py`（余额路由） | `pytest tests/integration/test_billing_api.py`（余额列表/筛选/充值 API） | 余额惰性补建唯一索引安全、分页/筛选参数、`@auth_required`/`@require_permission` |
| `backend/app/routes/billing/packages.py`（套餐路由） | `pytest tests/integration/test_billing_api.py::test_*pricing*` + `pytest tests/unit/test_billing_service.py` | 套餐删除前关联计费规则检查、`over_limit_unit_price` NULL 语义 |
| `backend/app/models/billing.py`（模型变更） | 新增/更新 Alembic 迁移测试 + `pytest tests/integration/test_billing_api.py` | 字段变更与迁移一致、invoice 状态流转字段 |
| `backend/alembic/versions/*.py`（迁移变更） | 迁移 upgrade/downgrade 独立测试（真实 Postgres 执行） | 数据语义反转（如 NULL=自动计算）前后一致性、downgrade 与业务计算一致 |
| `backend/tests/integration/test_billing_api.py`（集成测试变更） | `pytest tests/integration/test_billing_api.py` | 测试自身正确性，xdist 并行安全（worker_id 唯一化） |

## 前端变更面映射

| 变更文件 / 变更面 | 最小受影响检查 | 覆盖的行为与风险 |
|---|---|---|
| `frontend/src/api/billing.ts`（API 层） | `cd frontend && npx vue-tsc --noEmit` + `npx vitest run`（相关 composable 测试） | API 参数与后端端点契约一致（如 export 参数对齐） |
| `frontend/src/composables/useBalance.ts`（余额逻辑） | `cd frontend && npx vitest run src/composables/__tests__/useBalance.test.ts` | KPI 数据来源 `getBalanceStats`、余额区间边界、排序状态机 |
| `frontend/src/views/billing/**`（结算单/套餐/计费规则视图） | `cd frontend && npx vue-tsc --noEmit` + `npm run lint` + 相关组件单测 | 类型安全、状态步骤映射（paid/completed）、导出参数 |
| `frontend/src/constants/invoiceStatus.ts`（状态常量） | `cd frontend && npx vue-tsc --noEmit` + `npx vitest run` | 常量与后端枚举一致、徽章映射 |

## 跨栈变更映射

| 变更场景 | 必须运行的检查 |
|---|---|
| 结算单生成/结算流程修改（前后端同改） | 单元测试 + 集成测试全链路 + `@smoke` E2E（`npx playwright test --grep="@smoke"`） |
| 数据库语义变更（迁移 + 后端 + 前端同改） | 迁移测试 + 集成测试 + 前端相关单测；**必须同 PR 合并**，防止语义漂移 |
| 计费规则新增计费模式 | 单元测试（`PricingRule` 三种计费计算）+ 集成测试（规则 API）+ 前端规则表单测试 |

## 最小验证命令

```bash
# 后端（单元 + 集成，需本地 Postgres + Redis，或用 docker compose）
cd backend
pytest tests/unit/test_billing_service.py
pytest tests/integration/test_billing_api.py -n 1

# 前端
cd frontend
npx vue-tsc --noEmit
npx vitest run

# PR 门禁（合并前自动执行）
# .github/workflows/pr-checks.yml → backend-integration-tests job（真实 Postgres + Redis + alembic upgrade + seed）
```

## 维护约定

- 每次 billing 相关变更必须能映射到上表至少一个检查；无法映射时先补检查再合入。
- 新增 billing 功能时同步更新本映射。
- 迁移文件必须与业务代码同 PR，且需迁移独立测试（见 `migration-no-gate` 修复项）。
