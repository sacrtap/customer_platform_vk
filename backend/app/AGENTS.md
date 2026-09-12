# backend/app 上下文

> 本文件是 `backend/app` 的包级上下文，**仅补充根级指令未覆盖的核心模块导航**。
> 全局规则（事务/权限/覆盖率/Python 版本/并发安全/日志）见 `.omp/RULES.md` 与根级 `AGENTS.md`，此处不重复。

## 分层边界

`backend/app` 遵循 分层架构：**routes → services → repositories → models**（详见 `.trellis/spec/backend/directory-structure.md`）。

| 层 | 位置 | 职责 | 禁止 |
|---|---|---|---|
| Route | `routes/` | HTTP 处理、入参校验、响应格式化 | 禁止写业务规则（仅编排 service 调用） |
| Service | `services/` | 业务逻辑、事务编排 | 禁止直接操作 HTTP 对象（Request/Response） |
| Repository | `repository/` | 数据访问、查询封装 | 禁止业务判断（billing 域使用；其余域 service 直连 session） |
| Model | `models/` | SQLAlchemy ORM 定义 | 禁止放业务方法（软删/时间戳由 `BaseModel` 提供） |

### billing 域特例

- **`services/billing.py`** 是 billing 域**唯一**业务实现（`BalanceService` / `PricingService` / `InvoiceService` 三个类都在此文件，不是目录）。
- **`routes/billing/`** 是子蓝图目录：`invoices.py` / `balances.py` / `packages.py` / `pricing.py` / `imports.py`，父蓝图 `billing_bp`（`url_prefix="/api/v1/billing"`）在 `__init__.py`。
- **`services/billing/` 目录为空**，不要向其中新增文件；billing 业务一律追加到 `services/billing.py`。
- **`services/cost_calc.py`** 承载消耗/费用计算（订单同步链路），`services/order_sync.py` 承载 ERP 订单同步（外部 MySQL `nest_model_order` 表）。

## 失败诊断入口

排查请求失败时，按此顺序定位：

1. **取关联标识**：响应头 `X-Request-Id` → 按 `request_id=<值>` 检索日志，串起 中间件→路由→服务层→DB 全链路（机制见 `.trellis/spec/backend/logging-guidelines.md` Request Correlation 章节）。
2. **看服务层 error 日志**：`services/*.py` 的 `logger.error`（余额缺失/重试耗尽/提交失败等，均含 customer_id/金额等定位字段）。
3. **看审计记录**：`audit_logs` 表（`who did what`），`routes/billing/invoices.py` 手动 `create_audit_entry` 处是状态流转关键点。
4. **业务失败响应**：`ErrorCodes` 5 位错误码（`constants/error_codes.py`），`{"code": <ErrorCodes>, "message": ...}` 格式见 `.trellis/spec/backend/error-handling.md`。

## 变更后受影响检查（billing 域）

修改 billing 相关文件后，按 **[`docs/code-review/billing-affected-checks.md`](../../docs/code-review/billing-affected-checks.md)** 的映射表运行最小检查——该表是 billing 变更 → 受影响检查的唯一权威路由：

- `services/billing.py`（余额/扣款/充值）→ `pytest tests/unit/test_billing_service.py`
- `services/billing.py`（`InvoiceService` 结算计算）→ `pytest tests/integration/test_billing_api.py::TestInvoiceFlow`
- `routes/billing/*` → `pytest tests/integration/test_billing_api.py`
- `models/billing.py` / `alembic/versions/*.py` → 迁移 upgrade/downgrade 独立测试（真实 Postgres）
- 门禁：`.github/workflows/pr-checks.yml` 的 `backend-integration-tests` job 会自动运行可自动化部分；`migration-gate` job 强制迁移变更必须带测试。

非 billing 模块（customers/auth/analytics 等）的检查：先跑 `pytest tests/unit/` + 对应 `tests/integration/test_<module>_api.py`，再跑 `pytest tests/integration/test_api.py`（冒烟）确认无回归。

## 本地验证命令

```bash
cd backend
.venv/bin/python -m ruff check app/            # lint
.venv/bin/python -m pytest tests/unit/ -q       # 单元（439 tests）
.venv/bin/python -m pytest tests/integration/ -n 1  # 集成（需本地 Postgres；mockserver 依赖用例除外）
```
