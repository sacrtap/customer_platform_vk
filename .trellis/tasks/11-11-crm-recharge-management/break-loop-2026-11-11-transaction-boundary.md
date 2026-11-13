# Break-Loop 分析：CRM 同步「系统繁忙」= 请求级事务边界冲突

- **日期**: 2026-11-11
- **现象**: CRM 回款页 → 选择月份 → 确认 → 前端提示 `系统繁忙，请稍后重试`
- **后端事实**: `POST /api/v1/crm-recharge/sync-runs` → HTTP 500，
  `sqlalchemy.exc.InvalidRequestError: A transaction is already begun on this Session`
  （`app/routes/crm_recharge.py` `create_crm_sync_run` 的 `async with db.begin()`）
- **结论**: 缺陷在**请求级事务边界**，与 CRM 上游、限流、业务校验无关。

---

## 1. 根因分类

- **主分类**: **E. Implicit Assumption**（隐式假设）+ **B. Cross-Layer Contract**（框架神话 ↔ 业务代码）
  代码假设「进入路由体时 session 上没有活动事务」。该假设在 SQLAlchemy 2.0 的 autobegin
  语义 + Sanic 装饰器链下**不成立**：`@auth_required` 读用户、`@require_permission` 校验权限
  （缓存 miss 时查 DB）、任何预检/dry-run 查询，都会留下一个活动事务。
- **放大器**: **D. Test Coverage Gap** —— 该路由**没有任何集成测试**，
  所以 500 从未在 CI 暴露；手动验证又只在「权限缓存已热」的进程里点过，侥幸通过。
- **不属于**: C（变更传播）不是本缺陷本身，但**同类残留**（见 §4）确属 C。

### 为什么「开发偶发、上线必炸」

是否冲突取决于「进入路由前到底有没有查过库」，而这只由**缓存是否命中**决定：

| 状态 | 前置查询 | 裸 `db.begin()` |
|---|---|---|
| 权限/用户缓存热 | 无 | 侥幸 200 |
| 进程重启后首次请求 | 有 | 必然 500 |
| 换账号 / 缓存失效 | 有 | 必然 500 |

因此「本地点通过一次」不构成证据；这类缺陷必须结构化消除。

---

## 2. 贝叶斯推理记录

| 假设 | 先验 | 依据 |
|---|---|---|
| H1 事务边界（autobegin 冲突） | 40% | 同类缺陷本项目已出现过 5 次（users 批量导入、数据库清理、余额充值、资金导入、CRM 绑定各有一处手工 rollback/commit），是最高基率 |
| H2 上游 CRM 接口异常（500/token/限流） | 30% | 前端文案「系统繁忙」暗示后端 5xx，且本模块强依赖外部 |
| H3 业务校验（客户/回款/金额） | 20% | 403/400 分支丰富 |
| H4 其他（数据库连接、序列化） | 10% | 兜底 |

**判别性证据**（不是再收集同类证据，而是找「只在某一假设下才出现」的事实）：

| 证据 | H1 预测 | H2 预测 | H3 预测 | 观测 |
|---|---|---|---|---|
| traceback 首个项目帧在 `sqlalchemy/orm/session.py::begin` | 是 | 否 | 否 | **是** |
| 是否出现 `httpx` / `CrmUpstreamError` 帧 | 否 | 是 | 否 | 否 |
| HTTP 体是否被业务 handler 包装（`{"code":...}`） | 否（未捕获） | 否 | 是（带业务 message） | 未捕获，Sanic 默认 500 体 |

**后验**: H1 ≈ 99%，其余合计 ≈1%。

**证伪路径**（留给后人）：把 `begin_write` 换回裸 `db.begin()` 后在**冷缓存**下打同一接口，
应复现 500；换回 `begin_write` 后必 202。

---

## 3. 修复

| 层面 | 动作 |
|---|---|
| 战术 | `create_crm_sync_run` 在显式写事务前结束隐式事务 |
| 结构 | 新增 `app/utils/db.py::begin_write`（`rollback` + `begin`），**替换全部 11 处**裸 `db.begin()`/`db_session.begin()`（8 个路由文件），新增写端点不可能再写错 |
| 数据正确性 | `customers/{id}/follow-up`（`async with db.begin(): pass`）、`users/me/preferences`（同款）单独核查：前者审计条目未提交 → 改为 `await db.commit()`（真实落库，已 curl 验证 audit_logs 有新行）；后者 `users` 表**没有** `preferences` 列且前端零调用 → 属独立产品决策，本次不动，已在 Issue 记录里列出 |
| 回归锚点 | `tests/integration/test_crm_sync_routes.py`（7 用例：202/409/400×2/未启用 + `begin_write` 语义 + 冷缓存路径）、`test_customers_api.py::test_create_follow_up_persists_audit` |

---

## 4. 系统性扩展

### 同源残留（已排查全仓 15 处写事务）

| 位置 | 修复前状态 | 处置 |
|---|---|---|
| `crm_recharge.py` 绑定 / 导入 | 已有 `await db.rollback()`（网络调用前，语义正确） | 换 helper，保留时序 rollback |
| `crm_recharge.py` 同步创建 | **缺失** → 本次 500 | 换 helper + 补测试 |
| `crm_recharge.py` 配置保存 | 已有 `commit()` | 换 helper |
| `customers.py` follow-up | **`async with db.begin(): pass`** → 必然 500 | 改 `await db.commit()` + 测试 |
| `users.py` 批量导入 / `roles.py` / `industry_type_routes.py` / `balance_whitelist_routes.py` | 已有预检后 `commit()` | 换 helper |
| `database_management.py` / `billing/balances.py` / `billing/imports.py` | 已有 `rollback()` | 换 helper |
| `users.py::update_user_preferences` | 同款 `begin(): pass`，但**无持久化列、无调用方** | 记录为独立缺陷，待产品决策（删除端点 or 加列 + 迁移） |

### 架构级观察

1. **框架语义没有被封装**：`AsyncSession` 直接暴露给路由，每个写端点都要自己记得
   「先结束隐式事务」。已用 `begin_write` 封装 —— 这是本项目当前的正确抽象层级
   （再往上一层需要自定义 Session 工厂，收益不抵改动面）。
2. **前端兜底文案掩盖可诊断性**：`系统繁忙` 对用户正确，对开发是死胡同。已把
   「拿后端 traceback」写进排查指南（见 §5 的 cross-layer 指南）。

### 流程级观察

- **并发跑 pytest 会污染共享测试库**：本次排查中出现 7 + 72 个假失败，根因是两个
  pytest 进程同时使用 `customer_platform_test`（`test_user` 的 session 级
  `TRUNCATE ... users CASCADE` 与另一进程的断言互相踩）。
  规则：**本地同一时刻只跑一个 pytest 进程**；需要并行必须给每个 worker 独立库
  （`PYTEST_XDIST_WORKER` 机制已支持，但手工并发不设该变量就是共享）。
- 新增路由必须带**至少一个**走真实 HTTP 的集成用例（本次缺测试是 500 逃逸的直接原因）。

---

## 5. 知识沉淀（已落盘）

- [x] `.trellis/spec/backend/database-guidelines.md` → `### 写事务必须用 begin_write，不要裸写 db.begin()`
      （autobegin 成因、两张正确写法表、回归锚点命令、traceback 特征）
- [x] `.trellis/spec/backend/index.md` → Pre-Development Checklist 与 Quality Check 各加一条
- [x] `.trellis/spec/guides/cross-layer-thinking-guide.md` → `## 通用错误文案 ↔ 后端真实异常`
      （排查顺序、假设检查表、冷/热缓存差异）
- [x] 代码锚点：`app/utils/db.py` docstring 写明「何时用 `begin_write`、何时用 `db.commit()`」
- [x] 回归测试：`tests/integration/test_crm_sync_routes.py`（含 helper 语义单元级断言）

## 6. 遗留（需产品决策，不在本次范围）

| 事项 | 证据 | 建议 |
|---|---|---|
| `GET/PUT /users/me/preferences` 无持久化能力 | `users` 表无 `preferences` 列；`grep frontend/src` 零调用；PUT 修复前 100% 500 | 优先删除端点；若确需偏好功能，需加列 + 迁移 + 前端接入 |
