# Backend Development Guidelines

> Coding conventions for the Sanic + SQLAlchemy async backend.

---

## Pre-Development Checklist

Before writing backend code, read and follow:

- [ ] [Directory Structure](./directory-structure.md) — Blueprint pattern, layered architecture (routes → services → repositories → models)
- [ ] [Error Handling](./error-handling.md) — `ErrorCodes` constants, `json({"code": ..., "message": ...})` response format
- [ ] [Logging Guidelines](./logging-guidelines.md) — stdlib `logging.getLogger(__name__)`, what to log / not log
- [ ] [Database Guidelines](./database-guidelines.md) — `request.ctx.db_session`, soft delete, cache invalidation, **写事务用 `begin_write`（裸 `db.begin()` 会因 autobegin 抛 500）**, **PG 会话时区契约（naive 列墙钟基准）**
- [ ] [Quality Guidelines](./quality-guidelines.md) — testing (unit/integration), forbidden patterns
- [ ] [Analytics Forecast](./analytics-forecast.md) — 预测消费接口/算法/数据字段契约
- [ ] [Analytics Consumption Filters](./analytics-consumption-filters.md) — 消耗分析页多维度筛选跨层契约（四处同步、cache_key 陷阱、ERP 口径、缓存隔离测试写法）
- [ ] [Analytics Dashboard](./analytics-dashboard.md) — 运营工作台 stats/todos/trend 字段契约、待办口径、权限角色与 scope 规则
- [ ] [Billing Balance Stats](./billing-balance-stats.md) — 余额统计响应字段、结算类型分组（未设置结算类型 = 预付费）口径、列表 `settlement_group` 契约、结算单列表行业/ERP 筛选契约、消耗记录接口 Invoice/VR 二选一关联契约
- [ ] [Invoice Detail Consistency](./invoice-consistency.md) — 结算单明细一致性契约：快照即准（生成不比对外部，原 F1 已移除）/Excel 三表同源（F2）/subtotal+order_count+多层计费冻结列（F3）/详情冻结快照组装（F4）/周期去重（F5）/同步层当天重拉+跨日迁移（F6）/计费明细双口径（F7）/房源级识别键（F8）
- [ ] [Import / Export Endpoints](./import-export.md) — 批量导入导出端点签名、模板结构、行级错误与权限码变更清单
- [ ] [File Storage](./file-storage.md) — `FILE_STORAGE_PATH` 解析规则、相对路径语义、DB 状态与磁盘实体一致性
- [ ] [Permission Model](./permission-model.md) — 权限码单一事实源（seed.py）、三层引用、`--sync-permissions` 上线入口、通配语义、共享端点白名单、高危清单
- [ ] [Runtime Credential Config](./runtime-credential-config.md) — 页面可维护的第三方凭据：密文落库/运行期缓存/保存前验证/动态调度/axios 拦截器错误形态与测试隔离
- [ ] [CRM Upstream Quirks](./crm-upstream-quirks.md) — CRM 开放 API 实测怪癖：`/received_payments` 上游 500、`/list` 可用、日期筛选被忽略、同步耗时与策略
- [ ] [CRM Recharge Revoke](./crm-recharge-revoke.md) — CRM 充值导入的撤销契约：唯一键覆盖软删导致只能物理删除、余额不足需超管 force、改绑硬阻断、撤销→改绑→重导入顺序
- [ ] [Recharge Revoke](./recharge-revoke.md) — 余额充值记录撤销：余额池化只能按当前余额判定、手动充值不受唯一键约束故软删保凭据、锁序与 recharge 一致并加锁复核、余额不足超管 force + 线下核对、软删必须被所有 RechargeRecord 聚合口径遵守
- [ ] [Audit Log Description](./audit-log-description.md) — 审计详情可读化契约：描述器 `audit_describe.py` 产出 `description`、changes 结构兼容矩阵、变更前快照必须先固化、路由内已写业务审计的端点须在中间件跳过

---

## Quick Reference

| Concern | Pattern | Source |
|---------|---------|--------|
| Framework | Sanic (async) + Blueprint | `backend/app/main.py` |
| ORM | SQLAlchemy async (`AsyncSession`) | `backend/app/models/` |
| Auth | `@auth_required` + `@require_permission("module:action")` | `backend/app/middleware/auth.py` |
| Error codes | `ErrorCodes` class (5-digit numeric) | `backend/app/constants/error_codes.py` |
| Response format | `{"code": 0, "message": "...", "data": {...}}` | All routes |
| Testing | pytest + pytest-asyncio (unit/integration/e2e) | `backend/tests/` |
| Migrations | Alembic (`backend/alembic/versions/`) | `backend/alembic/` |
| Cache | Redis via `cache_service` singleton | `backend/app/cache/base.py` |
| Batch import | `read_import_dataframe()` → 行级错误 `{success_count, error_count, errors[:10]}` | `backend/app/utils/excel_import.py` |
| Batch export | 复用列表查询函数 + `limit=50000`，空数据 `40002` | `backend/app/routes/billing/balances.py` |

---

## Quality Check

Before submitting code:

1. **Lint passes**: `cd backend && ruff check app/`
2. **Tests pass**: `cd backend && python -m pytest tests/ -v`
3. **Every new route has `@auth_required`** (or is in the skip-paths list)
4. **Error responses use `ErrorCodes` constants** — no hardcoded numbers
5. **Cache invalidated after mutations** — `cache_service.invalidate_*()`
6. **Test coverage ≥ 50%** for new code (CI gate: merged unit + integration coverage, see pr-checks.yml)
7. **Type check passes**: `cd backend && pyright` → 0 error（配置 `backend/pyrightconfig.json`；模型字段须用 `Mapped[...] = mapped_column(...)`）
8. **写事务边界**：多步写入用 `async with begin_write(db)`，不要把裸 `db.begin()` 放在任何查询/权限校验之后（autobegin → `InvalidRequestError` → 前端「系统繁忙」）
9. **ORM 模型字段有变更时**：除写迁移外，必须**应用到运行库并验证**
   ```bash
   cd backend && python -m alembic upgrade head && python scripts/check_schema_drift.py   # 或 make db-migrate
   ```
   「写了迁移文件」≠「运行库已升级」——漏掉本步时 CI/单测全绿，但本地与生产启动后
   所有触及该实体的查询 500（`column ... does not exist`）。见 database-guidelines.md「Schema Drift」一节。

---

**Language**: Specs are written in English. Code comments and user-facing messages are in Chinese.
