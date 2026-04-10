# AGENTS.md - 客户运营中台开发指南

**最后更新**: 2026-04-07
**项目状态**: Phase 0-7 完成 | **测试覆盖率**: 46%+ (CI 门槛 ≥50%)

---

## Agent 必读规则

- **语言**: 中文思考、中文回答、中文文档（保存到 `docs/`）
- **Context-Mode**: 禁止 `curl`/`wget`/直接 HTTP 请求，使用 `context-mode_ctx_*` 工具系列
- **Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use. See more commands in RTK.md.

## 架构速览

| 层级 | 技术栈 |
|------|------|
| **后端** | Python 3.12 (⚠️ 不支持 3.14+) + Sanic 22.12 + SQLAlchemy 2.0 + PostgreSQL + Redis |
| **前端** | Vue 3.4 + TypeScript 5.3 + Arco Design 2.54 + Vite 5.0 |
| **部署** | Docker Compose (生产) / 本地 PostgreSQL (开发) |

**入口点**:
- 后端: `backend/app/main.py` (Sanic app, uvicorn 启动)
- 前端: `frontend/src/main.ts`
- Alembic: `backend/alembic/` (migrations 目录被 black 排除)

**后端 scripts**:
- `scripts/seed.py` — 创建 admin 账号 + 权限 + 角色（首次启动必需）
- `scripts/create_test_data.py` — 创建测试用户和客户数据（可选）
- `scripts/generate_secrets.py` — 生成 JWT/Webhook 安全密钥

---

## 开发环境

### 后端

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 编辑 DATABASE_URL, JWT_SECRET (运行 generate_secrets.py 生成)

createdb -U postgres customer_platform
python -m alembic upgrade head
python scripts/seed.py
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend && npm install && npm run dev  # http://localhost:5173
```

### 测试数据库

```bash
createdb -U postgres customer_platform_test
# 配置 backend/.env.test: TEST_DATABASE_URL=postgresql+asyncpg://.../customer_platform_test
```

---

## 测试

### 后端

```bash
cd backend && source .venv/bin/activate

# ⚠️ pytest.ini 默认启用覆盖率 (--cov=app)，单测不想跑覆盖率时加 --no-cov
python -m pytest tests/unit/test_auth_service.py::TestAuthService::test_login_success -v
python -m pytest tests/integration/test_api.py -v
python -m pytest --cov=app --cov-report=html
```

- 使用 `pytest-asyncio` auto 模式，`asyncio_default_fixture_loop_scope = function`
- 集成测试使用 Sanic ASGI Client（已移除 pytest-sanic）
- Fixture 定义在 `tests/conftest.py`
- CI 覆盖门槛: ≥50% (`--cov-fail-under=50`)

### 前端

```bash
cd frontend
npm run test:e2e           # Playwright E2E
npx playwright test --ui   # UI 模式
```

---

## 代码质量

### 验证顺序

```bash
# 后端
cd backend && black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203

# 前端
cd frontend && npm run lint && npm run format && npx vue-tsc --noEmit
```

### 约定

| 后端 Python | 前端 TypeScript |
|------------|----------------|
| `black` line-length=100, 排除 `migrations/` | 禁止 `any`，`strict: true` |
| `flake8` max-line-length=120, 忽略 E203 | `noUnusedLocals` + `noUnusedParameters` 开启 |
| 所有函数必须有类型注解 | 路径别名 `@/*` → `src/*` |
| 类 `PascalCase` / 函数 `snake_case` | 组件 `PascalCase` / 变量 `camelCase` |

---

## 安全约束 (必须遵守)

1. **数据库事务**: 所有修改操作必须在事务中执行
2. **并发安全**: 余额扣款使用行级锁 (`FOR UPDATE`)
3. **Webhook 验证**: 验证时间戳窗口 + 签名去重
4. **权限校验**: 所有 API 端点必须添加 `@auth_required` 装饰器
5. **审计日志**: 关键操作必须记录到 `audit_logs` 表
6. **JWT 密钥**: 生产环境必须使用 32+ 字符随机密钥（用 `generate_secrets.py` 生成）

---

## 设计规范

- **主色**: `#0F172A` | **强调色**: `#0369A1` | **字体**: Plus Jakarta Sans
- **圆角**: 8-16px | **动效**: 150-300ms
- 禁止表情符号图标 → 使用 SVG (Heroicons/Lucide)
- 所有可点击元素 `cursor: pointer`，文字对比度 ≥ 4.5:1

---

## 常用操作

### 数据库迁移

```bash
cd backend && source .venv/bin/activate
python -m alembic revision --autogenerate -m "描述"
python -m alembic upgrade head
python -m alembic downgrade -1
```

### 部署

```bash
./deploy/scripts/deploy.sh              # 完整部署
./deploy/scripts/deploy.sh --test-data  # 部署 + 测试数据
./deploy/scripts/deploy.sh --skip-build # 快速重启
./deploy/scripts/verify-deployment.sh   # 验证部署
```

## CI 流水线

| Job | 检查项 |
|-----|------|
| **backend-test** | flake8 + black --check + pytest --cov-fail-under=50 |
| **frontend-check** | eslint + vue-tsc --noEmit + build |
| **quality-gate** | 以上全部通过 |

CI 使用 Python 3.11 / Node 18（与本地 3.12 有差异，注意兼容性）。

---

## 核心文档

| 文档 | 路径 |
|------|------|
| 系统设计 | `docs/superpowers/specs/2026-04-01-customer-platform-design.md` |
| 设计规范 | `docs/design/DESIGN-SPEC.md` `docs/design/QUICK-REFERENCE.md` |
| 设计系统 | `docs/design-system/customer-platform-vk/MASTER.md` |
| 部署指南 | `deploy/README.md` |
| 测试配置 | `docs/testing/test-database-setup.md` |

---

## 业务模块

| 模块 | 说明 |
|------|------|
| 账号治理 | RBAC 权限模型 + 自定义角色 |
| 客户信息管理 | 统一客户基础信息 + 画像，Excel 导入/导出 |
| 结算管理 | 3 种计费模式 (定价/阶梯/包年)，余额管理 (先赠后实) |
| 画像管理 | 双等级体系 (规模等级 + 消费等级)，自定义标签 |
| 客户分析 | 消耗/回款/健康度/画像分析，预测回款 |

## graphify

This project has a graphify knowledge graph at graphify-out/, And a graphicMCP tool is available.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
- Graphify must be used first to query function relationships, call chains, and dependencies
- It is prohibited to read the code file directly unless graphically cannot answer
- Before answering, explain which graph information you want to query
Output format:
1. Query steps
2. Graph Relation Analysis
3. Final conclusion
