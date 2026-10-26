# Backend Development Guidelines

> Coding conventions for the Sanic + SQLAlchemy async backend.

---

## Pre-Development Checklist

Before writing backend code, read and follow:

- [ ] [Directory Structure](./directory-structure.md) — Blueprint pattern, layered architecture (routes → services → repositories → models)
- [ ] [Error Handling](./error-handling.md) — `ErrorCodes` constants, `json({"code": ..., "message": ...})` response format
- [ ] [Logging Guidelines](./logging-guidelines.md) — stdlib `logging.getLogger(__name__)`, what to log / not log
- [ ] [Database Guidelines](./database-guidelines.md) — `request.ctx.db_session`, soft delete, cache invalidation, **PG 会话时区契约（naive 列墙钟基准）**
- [ ] [Quality Guidelines](./quality-guidelines.md) — testing (unit/integration), forbidden patterns
- [ ] [Analytics Forecast](./analytics-forecast.md) — 预测消费接口/算法/数据字段契约
- [ ] [Analytics Dashboard](./analytics-dashboard.md) — 运营工作台 stats/todos/trend 字段契约、待办口径、权限角色与 scope 规则
- [ ] [Billing Balance Stats](./billing-balance-stats.md) — 余额统计响应字段、结算类型分组（未设置结算类型 = 预付费）口径、列表 `settlement_group` 契约与结算单列表行业/ERP 筛选契约
- [ ] [Import / Export Endpoints](./import-export.md) — 批量导入导出端点签名、模板结构、行级错误与权限码变更清单
- [ ] [File Storage](./file-storage.md) — `FILE_STORAGE_PATH` 解析规则、相对路径语义、DB 状态与磁盘实体一致性

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
8. **ORM 模型字段有变更时**：除写迁移外，必须**应用到运行库并验证**
   ```bash
   cd backend && python -m alembic upgrade head && python scripts/check_schema_drift.py   # 或 make db-migrate
   ```
   「写了迁移文件」≠「运行库已升级」——漏掉本步时 CI/单测全绿，但本地与生产启动后
   所有触及该实体的查询 500（`column ... does not exist`）。见 database-guidelines.md「Schema Drift」一节。

---

**Language**: Specs are written in English. Code comments and user-facing messages are in Chinese.
