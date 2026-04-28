# AGENTS.md - 客户运营中台开发指南

**最后更新**: 2026-04-28 (RTK 指南移至全局 + 添加项目结构说明)
**项目状态**: Phase 0-7 完成 | **测试覆盖率**: 46%+ (CI 门槛 ≥50%)

---

## 项目结构
- `backend/app/` - Sanic 后端应用代码（API/Service/Model/Repository）
- `backend/tests/` - pytest 测试套件（单元测试 + 集成测试）
- `backend/alembic/` - 数据库迁移脚本
- `frontend/src/` - Vue 3 前端源码（组件/路由/状态管理）
- `deploy/` - Docker Compose 部署配置
- `docs/` - 项目文档（按类型分子目录）
- `.opencode/` - OpenCode Agent/Command/Plugin 配置
- `.rtk/` - RTK 项目级过滤器配置

---

## 架构速览

| 层级 | 技术栈                                                                            |
| ---- | --------------------------------------------------------------------------------- |
| **后端** | Python 3.12.x (要求 >=3.12,<3.13，不支持 3.13+) + Sanic 22.12 + SQLAlchemy 2.0 + PostgreSQL + Redis |
| **前端** | Vue 3.4 + TypeScript 5.3 + Arco Design 2.54 + Vite 5.0                            |
| **部署** | Docker Compose (生产) / 本地 PostgreSQL (开发)                                    |

**入口点**:
- 后端: `backend/app/main.py` (uvicorn 启动)
- 前端: `frontend/src/main.ts`
- Alembic: `backend/alembic/` (migrations 被 black 排除)

**后端 scripts**: `backend/scripts/seed.py` | `backend/scripts/create_test_data.py` | `backend/scripts/generate_secrets.py`

---

## 开发命令

### 后端
```bash
cd backend && source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端
```bash
cd frontend && npm run dev  # http://localhost:5173
```

### 测试
```bash
# 后端测试 (使用 Makefile 快捷命令，推荐)
cd backend && make test           # 运行所有测试（无覆盖率，快速）
cd backend && make test-fast      # 仅运行单元测试（最快 ~5-10s）
cd backend && make test-parallel  # 并行运行所有测试（推荐 ~10-20s）
cd backend && make test-cov       # 运行测试 + 覆盖率（CI 用）
cd backend && make test-changed   # 增量测试（仅运行受影响测试 ~2-5s）
cd backend && make test-report    # 运行测试并打开 HTML 报告

# 传统方式（仍可用）
cd backend && source .venv/bin/activate && python -m pytest tests/ -n auto  # 并行测试
cd backend && source .venv/bin/activate && python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=50  # CI 覆盖率

# 前端
cd frontend && npm run test:e2e
```

**注意**：
1. 后端测试需要本地 PostgreSQL 运行并已创建测试数据库 `customer_platform_test`。
   如未创建，可执行：`createdb -U postgres customer_platform_test`
2. 增量测试 (`make test-changed`) 需要首次运行建立基线，后续只运行受影响测试。

### 代码质量
```bash
cd backend && black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
cd frontend && npm run lint && npm run format && npm run type-check  # TypeScript 类型检查
cd frontend && npm run type-check:watch  # 持续监听模式
```

### 数据库迁移
```bash
cd backend && python -m alembic revision --autogenerate -m "描述" && python -m alembic upgrade head
```

### 部署
```bash
./deploy/scripts/deploy.sh              # 完整部署
./deploy/scripts/deploy.sh --skip-build # 快速重启
./deploy/scripts/verify-deployment.sh   # 验证部署
```

---

## 安全约束 (必须遵守)

1. **数据库事务**: 所有修改操作必须在事务中执行
2. **并发安全**: 余额扣款使用行级锁 (`FOR UPDATE`)
3. **Webhook 验证**: 验证时间戳窗口 + 签名去重
4. **权限校验**: 所有 API 端点必须添加 `@auth_required` 装饰器
5. **审计日志**: 关键操作必须记录到 `audit_logs` 表
6. **JWT 密钥**: 生产环境必须使用 32+ 字符随机密钥

---

## Superpowers 流程入口规则

**核心原则**: 技能是链式流程，加载入口技能后后续流程自动引导。

| 用户意图             | 入口技能（必须加载）                           | 后续自动流程                                                  |
| -------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| 新功能/改功能/加组件 | `brainstorming`                                  | → using-git-worktrees → writing-plans → subagent-driven → TDD |
| 修 bug/调试问题      | `systematic-debugging`                           | → TDD（写复现测试）→ verification-before-completion           |
| 提交代码             | `git-commit`                                     | 分析 diff → 生成 conventional commit                          |
| 完成开发/准备合并    | `finishing-a-development-branch`                 | → 验证测试 → 提供合并选项                                     |
| 收到代码审查反馈     | `receiving-code-review`                          | → 理解反馈 → 验证 → 修复                                      |
| 有规格文档要实现     | `writing-plans`                                  | → 分解任务 → subagent-driven                                  |
| 有计划要执行         | `subagent-driven-development` 或 `executing-plans` | → 逐任务执行 → 审查 → 完成                                    |

**显式声明格式**: 加载技能后，第一句话必须说明 "正在使用 [技能名] 来 [目的]"

**禁止跳过流程**:
- 新功能不得跳过 brainstorming 直接写代码
- 修 bug 不得跳过 systematic-debugging 直接提修复
- 完成开发不得跳过 verification-before-completion 直接声称成功

---

## 代码约定

| 后端 Python                                  | 前端 TypeScript                              |
| -------------------------------------------- | -------------------------------------------- |
| `black` line-length=100, 排除 `migrations/`  | 禁止 `any`，`strict: true`                   |
| `flake8` max-line-length=120, 忽略 E203      | `noUnusedLocals` + `noUnusedParameters` 开启 |
| 所有函数必须有类型注解                       | 路径别名 `@/*` → `src/*`                     |
| 类 `PascalCase` / 函数 `snake_case`          | 组件 `PascalCase` / 变量 `camelCase`         |

---

## 设计规范
- **主色**: `#0F172A` | **强调色**: `#0369A1` | **字体**: Plus Jakarta Sans
- **圆角**: 8-16px | **动效**: 150-300ms
- 禁止表情符号图标 → 使用 SVG (Heroicons/Lucide)

---

## 项目专属工具

### Graphify 知识图谱
本项目使用 Graphify 构建代码知识图谱。

**核心规则：**
1. 架构问题优先查询 `graphify-out/GRAPH_REPORT.md`
2. 使用 `graphify_query_graph` 等工具追踪依赖关系
3. 更新图谱（二选一）：
   - **手动触发**：`graphify update .`（代码文件 AST 重建，无需 LLM）
   - **自动触发**：运行 `graphify hook install` 安装 Git hooks，每次 `git commit` 后自动重建
   - 文档/图片变更需要调用技能运行 `/graphify . --update`（含 LLM 语义提取）

### RTK Token 优化工具
RTK 使用策略已在**全局 AGENTS.md** 中定义，此处补充项目特定说明：

- 项目级过滤器位于 `.rtk/filters.toml`，针对 pytest/black/flake8/alembic 等命令优化
- 本项目已配置 `on_empty` 提示，避免 RTK 空输出导致 LLM 误判
- 详细使用规则请参考全局开发偏好

---

## 核心文档索引

| 文档            | 路径                                                          |
| --------------- | ------------------------------------------------------------- |
| **文档导航**    | `docs/README.md` (完整文档索引)                                 |
| 系统设计        | `docs/superpowers/specs/2026-04-01-customer-platform-design.md` |
| 部署指南        | `deploy/README.md`                                              |
| 数据库迁移      | `docs/guides/database-migration-guide.md`                       |
| Graphify 工作流 | `Graphify.md` (项目级)                                          |

---

## 文档目录规范

新增文档时遵循以下目录约定：

| 文档类型 | 存放目录                | 示例                         |
| -------- | ----------------------- | ---------------------------- |
| 开发指南 | `docs/guides/`            | 数据库迁移、部署操作指南     |
| 设计文档 | `docs/design/`            | 设计规范、样式更新记录       |
| 性能优化 | `docs/performance/`       | 查询优化、缓存分析、监控集成 |
| 测试计划 | `docs/testing/plans/`     | 功能测试计划、集成测试计划   |
| 测试报告 | `docs/testing/reports/`   | 单元测试报告、修复报告       |
| 测试环境 | `docs/testing/setup/`     | 测试数据库配置               |
| 设计规格 | `docs/superpowers/specs/` | AI 工作流产出的功能规格      |
| 实现计划 | `docs/superpowers/plans/` | AI 工作流产出的实现计划      |
| 原型文件 | `docs/prototypes/`        | HTML 原型                    |
| 用户文档 | `docs/` (根目录)          | user-manual.md               |

**规则**: 覆盖率 HTML 报告等自动生成产物不纳入 `docs/` 目录。

---

## 业务模块

| 模块         | 说明                                               |
| ------------ | -------------------------------------------------- |
| 账号治理     | RBAC 权限模型 + 自定义角色                         |
| 客户信息管理 | 统一客户基础信息 + 画像，Excel 导入/导出           |
| 结算管理     | 3 种计费模式 (定价/阶梯/包年)，余额管理 (先赠后实) |
| 画像管理     | 双等级体系 (规模等级 + 消费等级)，自定义标签       |
| 客户分析     | 消耗/回款/健康度/画像分析，预测回款                |

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (or use `graphify hook install` for auto-rebuild on commit)
