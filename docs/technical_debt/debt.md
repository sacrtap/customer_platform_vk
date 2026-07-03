# 技术债务清单

**创建日期**: 2026-06-29  
**最后更新**: 2026-07-02  
**维护规则**: 所有新发现的技术债务必须记录在此文件中

---

## 目录

- [高优先级债务](#高优先级债务)
- [中优先级债务](#中优先级债务)
- [低优先级债务](#低优先级债务)
- [已解决债务](#已解决债务)

---

## 高优先级债务

### TD-001: 后端单文件代码量过大

**发现日期**: 2026-06-29  
**影响范围**: 可维护性、代码复用、团队协作  
**严重程度**: 🔴 高

**问题描述**:
多个核心文件代码行数超过 1000 行，违反单一职责原则：

| 文件路径 | 行数 | 问题 |
|---------|------|------|
| `backend/app/routes/billing.py` | 1,912 | 结算路由过于集中 |
| `backend/app/services/analytics.py` | 1,301 | 分析服务逻辑复杂 |
| `backend/app/services/billing.py` | 995 | 结算业务逻辑臃肿 |
| `backend/app/routes/customers.py` | 949 | 客户路由功能过多 |
| `backend/app/services/customers.py` | 917 | 客户服务需要拆分 |

**当前核实**: 2026-07-02 仍成立。执行时复核：上述 5 个后端文件仍有 2 个超过 1000 行、3 个接近 1000 行，债务仍成立。

**影响**:
- 代码审查困难，容易遗漏问题
- 多人协作时 Git 冲突频繁
- 难以编写单元测试
- 代码复用性差，容易出现重复代码

**建议解决方案**:
1. 按功能模块拆分为子文件（如 `billing/invoices.py`, `billing/payments.py`）
2. 提取公共逻辑到工具类
3. 使用蓝图（Blueprint）模式组织路由
4. 每个文件控制在 300-500 行以内

**预计工作量**: 2-3 周

---

### TD-002: 前端单文件代码量过大

**发现日期**: 2026-06-29  
**影响范围**: 可维护性、渲染性能、组件复用  
**严重程度**: 🔴 高

**问题描述**:
多个 Vue 组件文件超过 1000 行，组件粒度过粗：

| 文件路径 | 行数 | 问题 |
|---------|------|------|
| `frontend/src/views/customers/Detail.vue` | 2,331 | 混合了表单、表格、图表等多种功能 |
| `frontend/src/views/customers/Index.vue` | 2,026 | 列表页功能过于集中 |
| `frontend/src/views/Dashboard.vue` | 1,689 | 仪表盘混合多个业务模块 |
| `frontend/src/views/billing/Balance.vue` | 1,373 | 余额管理逻辑复杂 |
| `frontend/src/views/billing/Invoices.vue` | 1,037 | 发票管理需要拆分 |

**当前核实**: 2026-07-02 仍成立。执行时复核：列出的 5 个 Vue 文件仍全部超过 1000 行；项目已有通用组件目录 `frontend/src/components`，但 `frontend/src/views/customers/components` 与 `frontend/src/views/billing/components` 当前没有拆分组件，债务仍成立。

**影响**:
- 组件复用性差
- 首次渲染时间长（大组件难以懒加载）
- 难以编写组件单元测试
- 样式隔离困难

**建议解决方案**:
1. 拆分为更小的子组件（每个组件 100-300 行）
2. 提取表单、表格、图表为独立组件
3. 使用 Composition API 的 `composables` 提取逻辑
4. 引入组件文档（Storybook）

**预计工作量**: 2-3 周

---
## 中优先级债务

### TD-004: Python 版本锁定与技术栈落后

**发现日期**: 2026-06-29  
**影响范围**: 性能、安全性、新特性使用  
**严重程度**: 🟡 中

**问题描述**:
```txt
# requirements.txt
Python 版本要求：>=3.12,<3.13
Sanic 版本：22.12.0（2022 年底发布，落后 2+ 年）
```

**依赖版本问题**:
- `httpx==0.23.3` - 被降级以兼容 sanic-testing
- `pytest-asyncio==1.3.0` - 当前固定在 1.x，需结合 `pytest==9.0.3` 和 Sanic 测试兼容性评估升级策略
- 无法使用 Python 3.13+；`requirements.txt` 还明确备注不兼容 Python 3.14+

**当前核实**: 2026-07-02 仍成立。`backend/requirements.txt` 固定 Python `>=3.12,<3.13`，Sanic/Sanic Ext/Sanic Testing 均为 `22.12.0`，`httpx==0.23.3`、`pytest==9.0.3`、`pytest-asyncio==1.3.0`；`backend/pyproject.toml` 使用 `target-version = "py312"`。

**影响**:
- 错过安全补丁
- 无法使用新语法（如 Python 3.12 的 f-string 改进）
- 依赖库兼容性问题
- 技术债务持续累积

**建议解决方案**:
1. 评估升级到 Sanic 24.x（需要测试兼容性）
2. 升级 pytest-asyncio 到最新稳定版
3. 先验证并支持 Python 3.13；Python 3.14+ 在 Sanic 生态兼容性确认后再放开
4. 建立依赖更新流程（Dependabot/Renovate）

**预计工作量**: 1-2 周

---

### TD-005: 缺少 Repository 模式

**发现日期**: 2026-06-29
**解决日期**: 2026-07-03
**影响范围**: 代码组织、可测试性、数据访问逻辑复用
**严重程度**: 🟡 中

**问题描述**:
`backend/app/repository/__init__.py` 仅为空文件，Service 层直接操作 ORM：

```python
# Service 中直接写查询（示例）
async with db_session.begin():
    result = await db_session.execute(select(Customer))
    customers = result.scalars().all()
```

**影响**:
- 数据访问逻辑分散在各个 Service 中
- 难以单元测试（需要 mock 数据库）
- 查询逻辑重复（相同查询在多处出现）
- 违反依赖倒置原则

**当前核实**: ✅ 2026-07-03 已解决。已创建完整的 Repository 层架构：
- `backend/app/repository/base.py` - 基础 Repository 实现（泛型、软删除过滤）
- `backend/app/repository/protocols.py` - Protocol 接口定义（依赖注入支持）
- `backend/app/repository/customer_repo.py` - CustomerRepository
- `backend/app/repository/balance_repo.py` - BalanceRepository
- `backend/app/repository/invoice_repo.py` - InvoiceRepository
- `backend/app/repository/pricing_repo.py` - PricingRepository

Service 层已改造：
- CustomerService、BalanceService、PricingService、InvoiceService 全部使用 Repository
- 路由层所有实例化点已更新为注入 Repository
- 全量测试通过（532 passed），代码审查完成

**解决方式**:
1. 创建 Repository 层，封装数据访问逻辑
2. 使用 Protocol 定义接口契约，支持依赖注入
3. 改造 4 个核心 Service 使用 Repository 模式
4. 更新路由层所有 Service 实例化点
5. 编写完整的 Repository 单元测试

**预计工作量**: 1-2 周（实际完成）

---

### TD-006: PostgreSQL 18 版本激进

**发现日期**: 2026-06-29  
**影响范围**: 生产环境稳定性  
**严重程度**: 🟡 中

**问题描述**:
```yaml
# deploy/docker-compose.yml
image: postgres:18-alpine
```

项目开发/测试 Compose 当前使用 `postgres:18-alpine`；是否适合生产取决于生产部署基线与扩展兼容性。

**当前核实**: 2026-07-02 仍成立，但原路径与版本描述需修正。根目录没有 `docker-compose.yml`；实际 Compose 文件是 `deploy/docker-compose.yml`，该文件标注用于本地开发和测试环境，并使用 `postgres:18-alpine`。

**影响**:
- 生产环境稳定性未经充分验证
- 部分扩展可能不兼容
- 社区支持资源较少
- 备份恢复工具可能不成熟

**建议解决方案**:
1. 开发/测试环境可继续使用 PostgreSQL 18
2. 生产环境使用经验证的稳定 PostgreSQL 主版本（例如当前组织标准版本；如无标准，优先评估 PostgreSQL 16/17）
3. 在 CI 中测试多版本兼容性
4. 建立数据库版本升级流程

**预计工作量**: 0.5 天

---


## 低优先级债务

### TD-008: 缓存策略不明确

**发现日期**: 2026-06-29  
**影响范围**: 性能优化、数据一致性  
**严重程度**: 🟢 低

**问题描述**:
代码层已有 Cache-Aside + TTL + 手动失效的分散实现，但缺少统一策略文档、命名规范、监控指标和缓存穿透/击穿/雪崩防护约定。

**当前核实**: 2026-07-02 部分缓解。`backend/app/cache/base.py` 已存在 `CacheService`，包含按 namespace 的 TTL 配置、Redis `setex` 写入，以及 pattern/customer/tag/analytics/billing 失效方法；多处路由使用 cache-aside 模式，写操作后也会失效缓存。

**待明确问题**:
- 已实际采用 Cache-Aside，需文档化适用范围与失效责任
- 缓存失效机制（TTL 与手动失效的统一规范）
- 缓存穿透/击穿/雪崩防护措施
- 缓存预热策略

**建议解决方案**:
1. 制定缓存策略文档
2. 为不同数据类型选择合适的策略
3. 实现缓存监控和告警
4. 添加缓存命中率指标

**预计工作量**: 1 周

---

### TD-009: 定时任务监控缺失

**发现日期**: 2026-06-29  
**影响范围**: 运维可观测性  
**严重程度**: 🟢 低

**问题描述**:
APScheduler 任务有启动日志；同步任务已有列表、统计、进度、取消和卡住任务检测，但通用定时任务仍缺少统一执行历史、失败告警、超时策略和面向全部 job 的管理/监控 API。

**当前核实**: 2026-07-02 部分缓解。`backend/app/tasks/scheduler.py` 注册多个 APScheduler job，并有启动日志和每小时 `check_stuck_sync_tasks`；`backend/app/services/sync_task_service.py` 与 `backend/app/routes/sync_tasks.py` 已提供同步任务列表、统计、进度、取消和卡住任务检测能力。

**待解决问题**:
- 任务执行失败如何告警？
- 任务执行历史如何查看？
- 任务并发控制如何实现？
- 任务执行超时如何处理？
- 同步任务已有部分能力，需扩展到所有 APScheduler job

**建议解决方案**:
1. 集成任务监控（如 Celery Flower 或自建管理界面）
2. 添加任务执行日志
3. 实现任务失败重试机制
4. 提供任务管理 API

**预计工作量**: 1 周

---

## 已解决债务

### TD-003: 备份文件管理不当

**解决日期**: 2026-06-29  
**解决方式**: 
- 删除所有 `.bak` 文件
- 在 `.gitignore` 中添加 `*.bak` 规则
- 建立代码审查流程，避免手动备份

**当前核实**: 2026-07-02 已解决。仓库非 `.git` 路径下未发现 `.bak` 文件；`.gitignore` 包含 `*.bak`，且包含 `.venv.bak/`、`venv.bak/`。

---

### TD-007: 安全隐患 - 默认密钥

**解决日期**: 2026-07-02  
**解决方式**:
- 应用运行时 Settings 已使用 `secrets.token_urlsafe(32)` 生成缺省 JWT/WEBHOOK secret
- 固定弱密钥不再直接进入 settings
- `deploy/docker-compose.yml` 仍保留开发默认值，后续建议作为部署配置硬化项单独跟踪

**当前核实**: 2026-07-02 已解决。`backend/app/config.py` 的 JWT/WEBHOOK secret 使用 `default_factory=lambda: os.getenv(...) or secrets.token_urlsafe(32)`；固定弱密钥不再作为应用 Settings 的缺省值。

---

## 附录：技术债务评估标准

### 严重程度定义

- 🔴 **高**: 严重影响开发效率、代码质量或系统稳定性，需要立即解决
- 🟡 **中**: 影响可维护性或存在潜在风险，计划在 1-2 个月内解决
- 🟢 **低**: 优化项，可以在日常迭代中逐步改进

### 优先级排序原则

1. **安全性问题** > 功能性问题 > 性能问题 > 代码质量问题
2. **影响范围**：影响多个模块的问题优先
3. **解决成本**：成本低、收益高的问题优先
4. **技术风险**：可能导致系统不稳定的问题优先

---

## 变更记录

| 日期 | 变更内容 | 操作人 |
|------|---------|--------|
| 2026-06-29 | 初始创建，记录 9 项技术债务 | 架构评估 |
| 2026-07-02 | 复核技术债务：更新 TD-001/TD-002 行数，修正 TD-004/TD-006 事实描述，TD-007 标记为已解决，TD-008/TD-009 标记为部分缓解 | 代码审查 |
| 2026-06-29 | 核实技术债务：TD-001 更新文件行数（1910行）、TD-002 更新 Balance.vue 行数（1373行）、TD-003 标记为已解决 | 代码审查 |
