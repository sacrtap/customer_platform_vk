# AGENTS.md - 客户运营中台开发指南

**最后更新**: 2026-04-14 (修正 Python 版本约束 + Graphify 重建命令)
**项目状态**: Phase 0-7 完成 | **测试覆盖率**: 46%+ (CI 门槛 ≥50%)

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
# 后端 (RTK 插件自动处理，无需手动加前缀)
cd backend && source .venv/bin/activate && python -m pytest tests/ -v
cd backend && source .venv/bin/activate && python -m pytest --cov=app --cov-report=html  # 覆盖率

# 前端
cd frontend && npm run test:e2e
```

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
   - 文档/图片变更需运行 `graphify . --update`（含 LLM 语义提取）

---

## 核心文档索引

| 文档            | 路径                                                          |
| --------------- | ------------------------------------------------------------- |
| **文档导航**    | `docs/README.md` (完整文档索引)                                 |
| 系统设计        | `docs/superpowers/specs/2026-04-01-customer-platform-design.md` |
| 部署指南        | `deploy/README.md`                                              |
| 数据库迁移      | `docs/guides/database-migration-guide.md`                       |
| RTK 命令映射    | `~/.config/opencode/docs/RTK-MAPPING.md` (全局)                 |
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
