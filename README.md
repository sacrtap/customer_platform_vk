# 客户运营中台平台

> 企业内部客户信息管理与运营系统 | 客户画像 | 结算管理 | 数据分析

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Vue 3.4](https://img.shields.io/badge/vue-3.4-green.svg)](https://vuejs.org/)
[![PostgreSQL 18](https://img.shields.io/badge/postgresql-18-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📖 项目简介

客户运营中台平台是一套面向企业内部使用的客户信息管理与运营系统，实现：

- **账号治理**：RBAC 权限模型 + 自定义角色，细粒度权限控制
- **客户信息管理**：统一客户基础信息 + 画像数据，支持 Excel 导入/导出
- **结算管理**：3 种计费模式（定价/阶梯/包年），余额管理（先赠后实），完整结算流程
- **画像管理**：双等级体系（规模等级 + 消费等级），自定义标签，组合筛选
- **客户分析**：消耗分析、回款分析、健康度分析、画像分析四大维度，预测回款

### 用户角色

| 角色 | 核心能力 |
|------|----------|
| **系统管理员** | 账号管理、角色创建、权限配置、系统设置 |
| **运营经理** | 修改结算价格、客户信息、定价配置、客户分析、全局数据查看 |
| **销售/业务人员** | 客户跟进、业务管理 |
| **数据分析师** | 客户分析、报表查看 |
| **高层管理者** | 全局数据查看、决策支持 |

---

## 🛠️ 技术栈

### 后端 (Backend)

| 技术 | 版本 | 说明 |
|------|------|------|
| **Python** | 3.12 | 运行环境 |
| **Sanic** | 24.12.0 | 异步 Web 框架 |
| **SQLAlchemy** | 2.0.51 | ORM 框架 |
| **Alembic** | 1.13.1 | 数据库迁移 |
| **PostgreSQL** | 18 | 主数据库 |
| **Redis** | 7 | 缓存 |
| **PyJWT** | 2.12.1 | JWT 认证 |
| **APScheduler** | 3.10.4 | 定时任务 |
| **Pydantic** | 2.13.4 | 数据验证 |

### 前端 (Frontend)

| 技术 | 版本 | 说明 |
|------|------|------|
| **Vue** | 3.4+ | 前端框架 |
| **Arco Design** | 2.54.3 | UI 组件库 |
| **Pinia** | 2.1.7 | 状态管理 |
| **Vue Router** | 4.2.5 | 路由 |
| **Axios** | 1.6.5 | HTTP 客户端 |
| **ECharts** | 5.4.3 | 数据可视化 |
| **TypeScript** | 5.3.3 | 类型系统 |
| **Vite** | 7.3.3 | 构建工具 |
| **VitePress** | 1.6+ | 开放平台开发者文档站（独立工程 `openapi-docs/`） |

### 部署 (Deploy)

| 技术 | 说明 |
|------|------|
| **Docker/Podman** | 容器运行时 |
| **Docker Compose** | 容器编排 |
| **PostgreSQL 18** | 生产数据库 |
| **Redis 7** | 生产缓存 |

---

## 📁 项目结构

```
customer_platform_vk/
├── backend/              # Python 后端 (Sanic + SQLAlchemy)
│   ├── app/              # 应用代码
│   │   ├── models/       # 数据模型
│   │   ├── routes/       # API 路由
│   │   ├── services/     # 业务服务
│   │   ├── middleware/   # 中间件
│   │   └── tasks/        # 定时任务
│   ├── tests/            # 测试代码
│   │   ├── unit/         # 单元测试
│   │   ├── integration/  # 集成测试
│   │   ├── performance/  # 性能测试
│   │   ├── services/     # 服务层测试
│   │   └── e2e/          # 端到端测试
│   ├── alembic/          # 数据库迁移
│   ├── scripts/          # 工具脚本
│   └── requirements.txt  # Python 依赖
├── frontend/             # Vue3 + TypeScript 前端
│   ├── src/
│   │   ├── views/        # 页面组件
│   │   ├── components/   # 通用组件
│   │   ├── composables/  # 组合式函数
│   │   ├── api/          # API 调用
│   │   ├── stores/       # 状态管理
│   │   └── router/       # 路由配置
│   └── tests/
│       └── e2e/          # Playwright 端到端测试
├── openapi-docs/          # 开放平台开发者文档站（VitePress 独立工程）
│   ├── .vitepress/        # VitePress 配置（base=/openapi/）
│   └── docs/
│       ├── guides/        # 指南：快速开始 / 认证 / 错误码
│       └── api-reference/ # API 参考：接口索引 + 各接口文档
├── deploy/               # 部署配置
│   ├── docker/           # Docker 镜像配置
│   ├── scripts/          # 部署脚本
│   └── monitoring/       # 监控配置
└── docs/                 # 项目文档
```

---

## 🚀 快速开始

### 前置要求

- **Python**: 3.12 (⚠️ 不支持 3.13+)
- **Node.js**: 18+
- **PostgreSQL**: 18 (本地开发)
- **Redis**: 7+ (本地开发，后端必需)
- **Docker/Podman**: 生产部署必需

#### 启动本地服务

```bash
# 启动 PostgreSQL (如使用 Postgres.app 或 Homebrew)
# Postgres.app: 打开应用即可
# Homebrew: brew services start postgresql

# 启动 Redis (必需，否则后端客户 API 会报 500 错误)
# 如未安装: brew install redis
redis-server --daemonize yes

# 验证服务运行正常
redis-cli ping  # 应返回 PONG
psql -h localhost -U postgres -c "SELECT 1"  # 应返回 ?column? = 1
```

### 方式一：本地开发环境

#### 💡 重要提示：必须使用虚拟环境

**为什么使用虚拟环境？**
- 避免系统 Python 包污染
- 项目依赖独立管理
- 支持多项目不同依赖版本
- 便于部署和协作

**推荐的虚拟环境工具：**

| 工具 | 适用场景 | 安装命令 |
|------|----------|----------|
| **venv** | Python 3.3+ 内置，推荐 | 无需安装 |
| **virtualenv** | 需要更多功能 | `pip install virtualenv` |
| **pyenv + venv** | 多 Python 版本管理 | `brew install pyenv` |
| **poetry** | 依赖管理 + 虚拟环境 | `curl -sSL https://install.python-poetry.org | python3 -` |

#### 1. 后端开发环境 (使用 venv)

```bash
# 进入后端目录
cd backend

# ===== 创建虚拟环境 =====
# ⚠️ 必须使用 python3，macOS 系统默认 python 指向 Python 2.7
python3 -m venv .venv

# ===== 激活虚拟环境 =====
# macOS/Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat

# 验证虚拟环境已激活
which python  # 应指向 .venv 目录
python --version  # 应显示 Python 3.12.x

# ===== 安装依赖 =====
# ⚠️ 激活虚拟环境后，python 命令自动指向 Python 3.12
pip install --upgrade pip
pip install -r requirements.txt

# ===== 配置环境变量 =====
cp ../.env.example .env
# 编辑 .env 文件，配置数据库等环境变量
# 至少需要配置 DATABASE_URL 数据库连接字符串

# ===== 创建数据库 =====
# ⚠️ 运行迁移前必须先创建数据库
# 方法 1: 使用 createdb 命令
createdb -U postgres customer_platform

# 方法 2: 使用 psql
psql -U postgres -c "CREATE DATABASE customer_platform;"

# 方法 3: Docker 方式创建
# docker run -d --name customer-platform-db \
#   -e POSTGRES_PASSWORD=postgres \
#   -e POSTGRES_DB=customer_platform \
#   -p 5432:5432 postgres:18

# ===== 运行数据库迁移 =====
# ⚠️ 确保 PostgreSQL 数据库已创建且可访问
python -m alembic upgrade head

# ===== (可选但推荐) 初始化种子数据 =====
# 创建 admin 超级管理员账号、权限定义、角色配置
# 执行后可以使用 admin 账号登录系统
python scripts/seed.py

# 首次启动推荐执行上述种子数据初始化命令
# 默认管理员账号：admin / admin123

# ===== (可选) 创建测试数据 =====
python scripts/generate_test_data.py

# ===== 启动开发服务器 =====
# ⚠️ 以下命令需在激活虚拟环境后执行
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 或使用默认配置启动：
# python app/main.py
```

访问 `http://localhost:8000/health` 验证后端运行正常。

#### 虚拟环境管理技巧

```bash
# 查看已安装的包
pip list

# 导出依赖
pip freeze > requirements.txt

# 退出虚拟环境
deactivate

# 重新激活
source .venv/bin/activate
```

#### 使用 Poetry (可选替代方案)

```bash
# 安装 Poetry
curl -sSL https://install.python-poetry.org | python3 -

# 初始化项目 (如使用 poetry 管理)
cd backend
poetry init  # 按提示配置

# 安装依赖
poetry install

# 激活虚拟环境
poetry shell

# 运行命令
poetry run python -m uvicorn app.main:app --reload
```

#### 2. 前端开发环境

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器 (热重载)
npm run dev

# 访问 http://localhost:5173
```

#### 3. 初始化种子数据（首次启动必需）

```bash
# 创建管理员账号和权限配置
python scripts/seed.py

# 执行后会创建：
# - admin 超级管理员账号（拥有所有权限）
# - 42 个系统权限定义
# - "超级管理员"及"运营经理"、"销售经理"预置角色
```

#### 4. 本地测试账号

```
管理员：admin / admin123        # 种子数据创建后使用
```

**说明**：
- `seed.py` - 创建 admin 管理员账号、42 个权限定义和预置角色（首次启动必需）
- `generate_test_data.py` - 为已有客户生成消耗分析测试数据（可选，需先存在客户数据）
- `replace_test_data.py` - 替换现有测试数据（可选）

### 方式二：Docker Compose 部署 (推荐)

#### 1. 快速部署

```bash
# 克隆项目
git clone https://github.com/sacrtap/customer_platform_vk.git
cd customer_platform_vk

# 复制环境配置
cp ../.env.example .env
# 编辑 .env 文件，修改生产环境配置

# 运行部署脚本
chmod +x deploy/scripts/deploy.sh
./deploy/scripts/deploy.sh

# 或部署并创建测试数据
./deploy/scripts/deploy.sh --test-data
```

#### 2. 手动部署

```bash
cd deploy

# 构建并启动所有服务
docker-compose -f docker-compose.yml up -d --build

# 运行数据库迁移
docker-compose -f docker-compose.yml up migrate

# 初始化种子数据（管理员账号 + 权限 + 预置角色）
docker-compose -f docker-compose.yml up seed

# 清理弃用权限（迁移/种子后执行）
docker-compose -f docker-compose.yml up cleanup

# 查看服务状态
docker-compose -f docker-compose.yml ps

# 查看应用日志
docker-compose -f docker-compose.yml logs -f app
```

> **发版流程**：`deploy.sh` 自动按 `migrate → seed → cleanup` 顺序执行数据库初始化与权限清理，手动部署时请勿省略 cleanup 步骤。

#### 3. 部署验证

```bash
# 运行部署验证脚本
./deploy/scripts/verify-deployment.sh
```

#### 4. 服务访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| **应用 API** | http://localhost:8000 | 后端 API 服务 |
| **健康检查** | http://localhost:8000/health | 健康状态 |
| **开放平台文档站** | http://localhost:8082/openapi/ | VitePress 开发者文档（与主应用同容器托管） |
| **PostgreSQL** | localhost:5432 | 数据库 |
| **Redis** | localhost:6379 | 缓存 |

---

## 🌐 开放平台文档站

开放平台面向外部 ERP 等渠道方提供标准 RESTful API（当前接口：`GET /api/v1/erp/balances`），所有接口通过 **API-Key** 认证（`Authorization: Bearer {api_key}`）。开发者文档由独立的 **VitePress** 工程（`openapi-docs/`）承载，部署于 `/openapi/` 路径，与主应用同容器托管。

### 访问地址

| 环境 | 地址 | 说明 |
|------|------|------|
| **本地开发** | http://localhost:5173/openapi/ | `npm run docs:dev` 热更新预览 |
| **构建产物预览** | http://localhost:4173/openapi/ | `npm run docs:preview` 验证产物 |
| **容器部署** | http://localhost:8082/openapi/ | 与主应用同 nginx 托管 |
| **staging** | https://customer-staging.jiazoushi.com/openapi/ | 生产文档站（部署后生效） |

> 无尾斜杠访问 `/openapi` 时，nginx 自动 301 重定向至 `/openapi/`。

### 本地开发与构建

```bash
cd openapi-docs

# 安装依赖（仅 vitepress）
npm install

# 本地开发（热更新）
npm run docs:dev
# 访问 http://localhost:5173/openapi/

# 生产构建（产物输出至 docs/.vitepress/dist，base=/openapi/）
npm run docs:build

# 预览构建产物
npm run docs:preview
# 访问 http://localhost:4173/openapi/
```

### 部署说明

- 构建已集成至 `deploy/docker/frontend.Containerfile`：构建阶段同时执行 `vite build`（主应用）与 `npm run docs:build`（文档站），产物分别复制到 `/usr/share/nginx/html` 与 `/usr/share/nginx/html/openapi`。
- nginx 配置 `deploy/docker/frontend-nginx.conf` 已包含 `location /openapi/`（静态托管 + cleanUrls `$uri.html` 探试 + 无尾斜杠 301）。
- 发布流程与主应用一致（`deploy/scripts/deploy.sh`），无需额外步骤。

### 文档维护

文档与代码同仓库同 PR，随 API 变更同步演进：

- **接口变更**：更新 `openapi-docs/docs/api-reference/*.md` → `npm run docs:dev` 本地预览 → 提交 → CI 构建镜像自动包含新文档。
- **新增接口**：在 `api-reference/` 新建页面（模板：描述 / 端点 / 参数表 / 请求与响应示例 / 错误码）+ 更新 `api-reference/index.md` 索引 + 更新 `changelog.md`。

---

## 🧪 测试

### 后端测试

⚠️ **注意**: 运行测试前请确保已激活虚拟环境

```bash
cd backend

# 激活虚拟环境 (如未激活)
source .venv/bin/activate

# 运行所有测试
pytest

# 运行单个测试文件
pytest tests/unit/test_auth_service.py -v

# 运行单个测试函数
pytest tests/unit/test_auth_service.py::TestAuthService::test_login_success -v

# 生成覆盖率报告
pytest --cov=app --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html  # macOS
# 或浏览器打开 htmlcov/index.html
```

### 前端测试

```bash
cd frontend

# 运行单元测试（Vitest）
npm test

# 运行单元测试（Watch 模式）
npm run test:ui

# 运行 E2E 测试（Playwright）
npm run test:e2e

# 运行单个 E2E 测试文件
npx playwright test tests/e2e/test_sync_task.spec.ts

# 生成 E2E 测试报告
npm run test:e2e:report
```

### 当前测试状态

- **后端测试**: 654 项（unit 447 + integration 207）
- **前端 E2E 测试**: 34 个 spec 文件
- **前端单元测试**: Vitest
- **测试状态**: ✅ 全部通过

---

## 📝 常用命令

⚠️ **注意**: 以下后端命令需在激活虚拟环境后执行

### 工具脚本

#### Better Harness Inspector（会话洞察）

生成 [Better Harness](https://github.com/QoderAI/better-harness) Harness Inspector 页面，汇总当前仓库最近 15 天（含今天）的 Agent 会话证据（OMP/Codex 等全部支持宿主），并自动打开浏览器：

```bash
./scripts/better-harness-inspector.sh
```

**说明**：
- 输出到 `docs/better-harness/better-harness-inspector/inspector.html`（目录自动创建；产物已被 `.gitignore` 排除，不入库）
- 通过 pi adapter 读取 OMP 会话（`~/.omp/agent`），需要 `@qoder-ai/better-harness >= 0.7.0-alpha1`（含 OMP 支持；官方 npm `latest`=0.6.6 不含）。脚本优先使用本地 omp 插件包，缺失时自动回退 `npx` 拉取指定版本
- 时间窗口：最近 15 天（含今天）；`--platform all` 扫描全部宿主，无会话数据的宿主显示 no-evidence 属正常

### 后端命令

```bash
cd backend

# 激活虚拟环境
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 代码格式化
ruff format app/ tests/
ruff check app/ tests/

# 数据库迁移
python -m alembic revision --autogenerate -m "描述"
python -m alembic upgrade head
python -m alembic downgrade -1

# 创建测试数据（消耗分析）
python scripts/generate_test_data.py

# 备份数据库
python scripts/backup_db.py
```

### 前端命令

```bash
cd frontend

# 开发模式
npm run dev

# 生产构建
npm run build

# 类型检查
npx vue-tsc --noEmit

# 代码检查与格式化
npm run lint
npm run format
```

### 开放平台文档站命令（openapi-docs/）

```bash
cd openapi-docs

# 安装依赖
npm install

# 本地预览（热更新，VitePress 开发服务器）
npm run docs:dev
# 访问 http://localhost:5173/openapi/

# 生产构建（产物输出至 docs/.vitepress/dist，base=/openapi/）
npm run docs:build

# 预览构建产物（验证 /openapi/ 路径资源引用）
npm run docs:preview
# 访问 http://localhost:4173/openapi/
```

### 部署命令

```bash
# 完整部署
./deploy/scripts/deploy.sh

# 跳过构建 (快速重启)
./deploy/scripts/deploy.sh --skip-build

# 创建测试数据
./deploy/scripts/deploy.sh --test-data

# 验证部署
./deploy/scripts/verify-deployment.sh

# 数据库备份
./deploy/scripts/backup.sh

# 本地 PostgreSQL 部署 (macOS)
./deploy/scripts/local-deploy.sh
```

### Docker 命令

```bash
# 启动所有服务
docker-compose -f deploy/docker-compose.yml up -d

# 停止所有服务
docker-compose -f deploy/docker-compose.yml down

# 查看日志
docker-compose -f deploy/docker-compose.yml logs -f app

# 重启服务
docker-compose -f deploy/docker-compose.yml restart

# 清理资源 (包括数据卷)
docker-compose -f deploy/docker-compose.yml down -v

# 查看容器状态
docker-compose -f deploy/docker-compose.yml ps
```

---

## ⚙️ 配置说明

### 环境变量 (.env)

```bash
# 应用配置
APP_ENV=development  # development | production
DEBUG=true

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/customer_platform

# JWT 配置 (生产环境必须修改)
# 生成安全密钥：python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET=your-random-32-byte-secret-here

# Webhook 配置 (生产环境必须修改)
WEBHOOK_SECRET=your-random-32-byte-secret-here

# 邮件配置
SMTP_HOST=smtp.company.com
SMTP_PORT=587
SMTP_USERNAME=noreply@company.com
SMTP_PASSWORD=<你的 SMTP 密码>

# 外部 API 配置
EXTERNAL_API_BASE_URL=https://business-api.company.com
EXTERNAL_API_TOKEN=<你的外部 API Token>

# Redis 配置
REDIS_URL=redis://localhost:6379/0
```

### 安全要求

1. **生产环境必须修改**: `JWT_SECRET`, `WEBHOOK_SECRET`
2. **数据库事务**: 所有修改操作必须在事务中执行
3. **并发安全**: 余额扣款使用行级锁 (`FOR UPDATE`)
4. **Webhook 验证**: 验证时间戳窗口 + 签名去重
5. **权限校验**: 所有 API 端点必须添加 `@auth_required` 装饰器
6. **审计日志**: 关键操作必须记录到 `audit_logs` 表

---

## 📚 核心文档

完整文档导航请参考 [`docs/README.md`](docs/README.md)

| 文档            | 路径                                                          |
| --------------- | ------------------------------------------------------------- |
| **文档导航**        | `docs/README.md` (完整索引)                                     |
| **开放平台文档站**  | `openapi-docs/` (VitePress 开发者文档，构建与访问见下文)           |
| **Agent 开发指南**  | `docs/guides/agents-guide.md` (完整命令/env/git/工作流)         |
| **系统设计**        | `docs/superpowers/specs/2026-04-01-customer-platform-design.md` |
| **部署指南**        | `deploy/README.md`                                              |
| **Podman 部署**     | `deploy/PODMAN_MACOS.md`                                        |
| **数据库迁移**      | `docs/guides/database-migration-guide.md`                       |
| **CodeGraph**      | 代码知识图谱 (`.codegraph/codegraph.db`)                        |
| **代码审查报告**    | `docs/code-review/` (审查报告目录)                              |
| **技术债务**        | `docs/technical_debt/`                                          |

---

## 🔧 故障排查

### 常见问题

#### 0. 虚拟环境相关问题

```bash
# 问题：找不到 python 命令或包
# 解决：确保已激活虚拟环境
source .venv/bin/activate

# 验证虚拟环境已激活
which python  # 应显示 .venv 目录路径
pip list     # 应显示已安装的包

# 问题：虚拟环境损坏
# 解决：删除并重建
rm -rf .venv
python3 -m venv .venv  # ⚠️ 使用 python3 而非 python
source .venv/bin/activate
pip install -r requirements.txt
```

#### 1. 后端启动失败

```bash
# 检查 Python 版本（使用 python3 而非 python）
python3 --version  # 必须是 3.12.x

# ⚠️ 确保已激活虚拟环境
source .venv/bin/activate

# 检查依赖安装
pip install -r requirements.txt

# 检查数据库连接
psql -h localhost -U user -d customer_platform
```

#### 2. 前端构建失败

```bash
# 清理 node_modules
rm -rf node_modules package-lock.json
npm install

# 检查 Node.js 版本
node --version  # 建议 18+
```

#### 3. Docker 部署失败

```bash
# 查看容器日志
docker-compose -f deploy/docker-compose.yml logs app

# 检查容器状态
docker-compose -f deploy/docker-compose.yml ps

# 重新构建
docker-compose -f deploy/docker-compose.yml build --no-cache
```

#### 4. 数据库迁移失败

```bash
# 检查迁移状态
python -m alembic current

# 回滚迁移
python -m alembic downgrade -1

# 重新迁移
python -m alembic upgrade head
```

#### 5. 客户 API 报 500 错误

```bash
# 症状: GET /api/v1/customers 返回 500 Internal Server Error

# 原因 1: Redis 未启动
redis-server --daemonize yes
redis-cli ping  # 验证返回 PONG

# 原因 2: 数据库缺少新列 (模型与数据库不同步)
# 运行数据库迁移
python -m alembic upgrade head

# 原因 3: 数据库列缺失但 Alembic 无法处理
# 手动添加缺失列:
# psql -h localhost -U postgres -d customer_platform
# ALTER TABLE customers ADD COLUMN IF NOT EXISTS erp_system VARCHAR(100);
# ALTER TABLE customers ADD COLUMN IF NOT EXISTS cooperation_status VARCHAR(50) DEFAULT 'active';
# ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS monthly_avg_shots INTEGER;
```

#### 6. Playwright E2E 测试失败

```bash
# 症状: 测试报 "strict mode violation" 或 "element not visible"

# 确保所有 .first() 都已添加
# 例如: page.locator('button:has-text("新建客户")').first()

# 检查前端服务是否运行
curl -s http://localhost:5173 > /dev/null && echo "Frontend OK"

# 检查后端 API 是否正常
python3 -c "
import http.client
conn = http.client.HTTPConnection('localhost', 8000)
conn.request('GET', '/health')
print('Backend:', conn.getresponse().status)
"

# 调试单个测试
npx playwright test test_customer_crud.spec.ts --headed
```

---

## 📊 项目状态

- **当前版本**: v1.0.0
- **开发状态**: Phase 0-7 完成
- **测试覆盖率**: CI 门槛 ≥50% (核心模块 60%+)
- **后端测试**: 654 项（unit 447 + integration 207）
- **前端 E2E 测试**: 34 个 spec 文件
- **最后更新**: 2026-09-16

---

## 🧠 CodeGraph 代码知识图谱

本项目使用 CodeGraph 构建代码知识图谱，帮助快速理解代码架构和依赖关系。

- **图谱索引**: `.codegraph/codegraph.db`（文件监听自动同步）
- **使用方式**: 通过 codegraph MCP 工具查询符号定义、调用链和依赖关系
- **更新图谱**: 代码变更后由文件监听器自动同步索引

---

## 📄 许可证

MIT License

---

## 👥 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request
