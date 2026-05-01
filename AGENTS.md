# AGENTS.md - 客户运营中台开发指南

**最后更新**: 2026-04-30
**项目状态**: Phase 0-7 完成 | **CI 要求**: 测试覆盖率 ≥50%

---

## 项目结构
- `backend/app/` - Sanic 后端应用（API/Service/Model/Repository）
- `backend/tests/` - pytest 测试套件
- `backend/alembic/` - 数据库迁移脚本
- `frontend/src/` - Vue 3 前端源码
- `deploy/` - Docker Compose 部署配置
- `docs/` - 项目文档
- `.opencode/` - OpenCode 配置

---

## 架构速览

| 层级 | 技术栈                                                                            |
| ---- | --------------------------------------------------------------------------------- |
| **后端** | Python 3.12.x (严格，不支持 3.13+) + Sanic 22.12 + SQLAlchemy 2.0 + PostgreSQL 18 + Redis 7 |
| **前端** | Vue 3.4 + TypeScript 5.3 + Arco Design 2.54 + Vite 5.0                            |
| **部署** | Docker Compose (生产) / 本地 PostgreSQL (开发)                                    |

**入口点**:
- 后端: `backend/app/main.py` (Sanic 应用，通过 uvicorn ASGI 启动)
- 前端: `frontend/src/main.ts`
- Alembic: `backend/alembic/` (migrations 被 black 排除)

---

## 快速开始

```bash
# 后端启动
cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端启动
cd frontend && npm run dev  # http://localhost:5173

# 运行测试
cd backend && make test-parallel  # 并行测试（推荐）

# 代码检查
cd backend && black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
```

> 完整命令清单、环境变量配置、虚拟环境初始化、Git 工作流 → 详见 [docs/guides/agents-guide.md](docs/guides/agents-guide.md)

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
| 任何完成声明前       | `verification-before-completion`                 | → 运行验证命令 → 确认输出 → 才能声称成功                      |

**显式声明格式**: 加载技能后，第一句话必须说明 "正在使用 [技能名] 来 [目的]"

**subagent-driven模型下的subagent派遣规则**:
- 在派遣任何任务给到 subagent 前，优先查看 `.opencode/agents/` 目录（项目级）或 `~/.config/opencode/agents/`（全局）下已有的subagent
- 根据任务类型和内容，派遣最匹配的 subagent 执行

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

## 项目工具

### Graphify 知识图谱

**图谱状态**: 2554 节点 · 5133 边 · 398 社区 | 输出目录: `graphify-out/`

#### 查询工作流（回答架构问题时必须使用）

1. **优先查询图谱**，而非直接读取源码
2. 使用 `graphify query "问题"` 执行 BFS/DFS 遍历
3. 根据查询结果组织回答，必须显示回复给用户相关信息，并引用 `source_file` 和 `source_location` 作为证据
4. 如果图谱信息不足，再回退到源码阅读

**常用命令**:
- `graphify query "认证模块依赖哪些服务？"` — BFS 广度查询（默认）
- `graphify query "问题" --dfs` — DFS 深度追踪特定路径
- `graphify path "AuthModule" "Database"` — 最短路径分析
- `graphify explain "Customer"` — 节点及邻居解释
- `graphify god_nodes` — 查看核心节点（当前核心：SQLAlchemy ORM、Alembic、AnalyticsService）

**输出要求**:
- 展示查询到的关键节点和关系
- 说明跨越了哪些社区边界
- 标注关系的置信度（EXTRACTED/INFERRED/AMBIGUOUS）
- 引用具体的 source_file 和 source_location

#### 维护工作流

- **代码变更后**: 运行 `graphify update .` 增量更新（仅处理变更文件，无需 LLM）
- **Git hook 自动重建**: `graphify hook install`（已安装，commit 时自动触发）
- **完整重建**: `graphify .`（当图谱质量下降或结构大改时）

#### 图谱质量说明

当前图谱存在过度碎片化问题（300+ 单节点社区），建议定期运行：
- `graphify . --cluster-only` — 重新聚类，改善社区结构
- `graphify . --mode deep` — 深度模式，增强 INFERRED 边连接

### 浏览器交互与测试
→ 遵循全局配置，使用 OpenCode 内置 Playwright 工具（详见 `~/.config/opencode/AGENTS.md`）


## 业务模块

| 模块         | 说明                                               |
| ------------ | -------------------------------------------------- |
| 账号治理     | RBAC 权限模型 + 自定义角色                         |
| 客户信息管理 | 统一客户基础信息 + 画像，Excel 导入/导出           |
| 结算管理     | 3 种计费模式 (定价/阶梯/包年)，余额管理 (先赠后实) |
| 画像管理     | 双等级体系 (规模等级 + 消费等级)，自定义标签       |
| 客户分析     | 消耗/回款/健康度/画像分析，预测回款                |

> 业务模块详情 → 详见 [docs/guides/agents-guide.md](docs/guides/agents-guide.md)

---

## 详细参考

| 内容               | 路径                                                          |
| ------------------ | ------------------------------------------------------------- |
| **完整开发指南**   | [docs/guides/agents-guide.md](docs/guides/agents-guide.md)    |
| **文档导航**       | [docs/README.md](docs/README.md)                              |
| **系统设计**       | `docs/superpowers/specs/2026-04-01-customer-platform-design.md` |
| **部署指南**       | [deploy/README.md](deploy/README.md)                          |
| **数据库迁移**     | `docs/guides/database-migration-guide.md`                     |
