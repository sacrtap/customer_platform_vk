# AGENTS.md - 客户运营中台项目开发指南

**最后更新**: 2026-04-06  
**项目状态**: Phase 0-7 完成，Docker 部署配置已完善  
**测试覆盖率**: 54% (核心模块 60%+)  

---

## 🤖 Agent 工作指南

### 语言与沟通
- **思考过程**: 使用中文表述
- **回答语言**: 中文回复
- **文档语言**: 所有生成文档使用中文，保存到 `docs/` 目录
- **API/代码文档**: 优先使用 Context7 查询

### Context-Mode 强制规则 ⚠️
本项目使用 context-mode MCP 工具，**必须遵守**:

| 禁止操作 | 替代方案 |
|---------|---------|
| `curl` / `wget` 命令 | `context-mode_ctx_fetch_and_index(url, source)` |
| Shell 中 HTTP 请求 | `context-mode_ctx_execute(language, code)` |
| 大输出 Shell 命令 | `context-mode_ctx_batch_execute(commands, queries)` |
| 分析性文件读取 | `context-mode_ctx_execute_file(path, language, code)` |

**工具优先级**: GATHER → FOLLOW-UP → PROCESSING → WEB → INDEX

---

## 🏗️ 架构概览

### 技术栈
| 层级 | 技术 |
|------|------|
| **后端** | Python 3.12 + Sanic 22.12 + SQLAlchemy 2.0 + PostgreSQL 18 + Redis 7 |
| **前端** | Vue 3.4 + TypeScript 5.3 + Arco Design 2.54 + Vite 5.0 |
| **部署** | Docker Compose (生产) / 本地 PostgreSQL (开发) |

### 核心目录
```
customer_platform_vk/
├── backend/              # Python 后端
│   ├── app/              # 应用代码 (models, routes, services, middleware, tasks)
│   ├── tests/            # 测试 (unit, integration, performance)
│   ├── alembic/          # 数据库迁移
│   └── scripts/          # 工具脚本 (seed.py, create_test_data.py)
├── frontend/             # Vue3 + TypeScript 前端
│   └── src/              # views, components, api, stores, router
├── deploy/               # Docker 部署配置
└── docs/                 # 项目文档
    ├── design-system/    # 设计系统源文件 (ui-ux-pro-max 生成)
    ├── design/           # 设计规范文档 (DESIGN-SPEC.md, QUICK-REFERENCE.md)
    ├── prototypes/       # HTML 原型 (login.html, dashboard.html)
    └── superpowers/      # 需求文档与设计规范
```

---

## 🚀 开发环境 Setup

### 后端 Setup (必须使用虚拟环境)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env: DATABASE_URL, JWT_SECRET 等

createdb -U postgres customer_platform
python -m alembic upgrade head
python scripts/seed.py  # 创建 admin 账号
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端 Setup
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### 测试数据库
```bash
createdb -U postgres customer_platform_test
# 配置 backend/.env.test
TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/customer_platform_test
```

---

## 🧪 测试命令

### 后端测试
```bash
cd backend && source .venv/bin/activate

# 单个测试函数 (最常用)
python -m pytest tests/unit/test_auth_service.py::TestAuthService::test_login_success -v

# 单个测试文件
python -m pytest tests/integration/test_api.py -v

# 所有测试
python -m pytest

# 覆盖率报告
python -m pytest --cov=app --cov-report=html
```

### 前端测试
```bash
cd frontend
npm run test:e2e  # Playwright E2E
npx playwright test
```

---

## 📝 代码规范

### Python 后端
- **导入顺序**: 标准库 → 第三方库 → 本地模块
- **类型注解**: 所有函数必须有类型注解
- **命名**: 类 `PascalCase` | 函数 `snake_case` | 常量 `UPPER_CASE`
- **格式化**: `black` (line-length=100) + `flake8`

### TypeScript 前端
- **类型安全**: 禁止使用 `any`
- **导入**: `import { ref } from 'vue'` | `import X from '@/components/X.vue'`
- **命名**: 组件 `PascalCase` | 变量 `camelCase` | 常量 `UPPER_CASE`
- **格式化**: `prettier` + `eslint`

---

## ⚠️ 关键安全要求

1. **数据库事务**: 所有修改操作必须在事务中执行
2. **并发安全**: 余额扣款使用行级锁 (`FOR UPDATE`)
3. **Webhook 验证**: 验证时间戳窗口 + 签名去重
4. **权限校验**: 所有 API 端点必须添加 `@auth_required` 装饰器
5. **审计日志**: 关键操作必须记录到 `audit_logs` 表
6. **JWT 密钥**: 生产环境必须使用 32+ 字符随机密钥

---

## 🎨 设计规范

### 设计系统文件
| 文件 | 路径 | 用途 |
|------|------|------|
| **设计系统源文件** | `docs/design-system/customer-platform-vk/MASTER.md` | ui-ux-pro-max 生成的全局设计规则 |
| **完整设计规范** | `docs/design/DESIGN-SPEC.md` | 人工编写的详细设计文档 |
| **快速参考卡片** | `docs/design/QUICK-REFERENCE.md` | 开发速查手册 |
| **登录页原型** | `docs/prototypes/login.html` | 登录页面 HTML 原型 |
| **仪表盘原型** | `docs/prototypes/dashboard.html` | 仪表盘页面 HTML 原型 |

### 核心设计参数
| 类别 | 值 |
|------|-----|
| **主色** | `#0F172A` (深海军蓝) |
| **强调色** | `#0369A1` (天空蓝) |
| **字体** | Plus Jakarta Sans |
| **风格** | Trust & Authority (专业权威) |
| **圆角** | 8-16px |
| **动效** | 150-300ms |

### UI 开发约束
- ❌ 禁止使用表情符号作为图标 → 使用 SVG (Heroicons/Lucide)
- ✅ 所有可点击元素必须有 `cursor: pointer`
- ✅ 悬停过渡时间 150-300ms
- ✅ 文字对比度 ≥ 4.5:1 (WCAG AA)
- ✅ 焦点状态对键盘导航可见
- ✅ 尊重 `prefers-reduced-motion`

---

## 🔧 常用操作

### 数据库迁移
```bash
python -m alembic revision --autogenerate -m "描述"
python -m alembic upgrade head
python -m alembic downgrade -1
```

### 部署
```bash
./deploy/scripts/deploy.sh
./deploy/scripts/deploy.sh --test-data  # 创建测试数据
./deploy/scripts/deploy.sh --skip-build  # 跳过构建
./deploy/scripts/verify-deployment.sh   # 验证部署
```

### 代码质量
```bash
# 后端
cd backend && black app/ tests/ && flake8 app/ tests/

# 前端
cd frontend && npm run lint && npm run format
```

---

## 📚 核心文档索引

| 文档类型 | 路径 |
|---------|------|
| **系统设计** | `docs/superpowers/specs/2026-04-01-customer-platform-design.md` |
| **设计规范** | `docs/design/DESIGN-SPEC.md` |
| **快速参考** | `docs/design/QUICK-REFERENCE.md` |
| **设计系统** | `docs/design-system/customer-platform-vk/MASTER.md` |
| **部署指南** | `deploy/README.md` |
| **测试配置** | `docs/testing/test-database-setup.md` |

---

## 🎯 业务功能模块

| 模块 | 说明 |
|------|------|
| **账号治理** | RBAC 权限模型 + 自定义角色 |
| **客户信息管理** | 统一客户基础信息 + 画像数据，支持 Excel 导入/导出 |
| **结算管理** | 3 种计费模式 (定价/阶梯/包年)，余额管理 (先赠后实) |
| **画像管理** | 双等级体系 (规模等级 + 消费等级)，自定义标签 |
| **客户分析** | 消耗/回款/健康度/画像分析，预测回款 |

### 用户角色
系统管理员 | 运营经理 | 销售/业务人员 | 数据分析师 | 高层管理者

---

## ⚡ 开发注意事项

### 后端
- **异步优先**: 所有数据库操作使用异步 SQLAlchemy
- **测试架构**: 集成测试使用 Sanic ASGI Client (已移除 pytest-sanic)
- **事件循环**: 使用 pytest-asyncio，避免事件循环冲突

### 前端
- **API 调用**: 使用 `src/api/` 封装的 Axios 实例
- **状态管理**: 使用 Pinia stores
- **路由权限**: 所有路由必须配置权限校验

### 测试
- **测试隔离**: 集成测试使用独立测试数据库
- **Fixture 复用**: 参考 `tests/conftest.py`
- **覆盖率要求**: 核心模块覆盖率 ≥ 60%
