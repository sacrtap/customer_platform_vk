# 开发指南 - 客户运营中台

> 本文档是 `AGENTS.md` 的详细参考扩展，包含完整的开发命令、环境配置、工作流说明。
> 核心规则请查看项目根目录的 `AGENTS.md`。

**最后更新**: 2026-04-29

---

## 1. 完整开发命令

### 1.1 后端命令

#### 启动开发服务器
```bash
cd backend && source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 测试命令 (Makefile)
```bash
cd backend

make test           # 运行所有测试（无覆盖率，快速反馈）
make test-fast      # 仅运行单元测试（最快 ~5-10s）
make test-parallel  # 并行运行所有测试（推荐 ~10-20s，需要 pytest-xdist）
make test-cov       # 运行测试 + 覆盖率报告（CI 使用，要求 ≥50%）
make test-unit      # 单元测试 + 覆盖率
make test-integration # 集成测试 + 覆盖率
make test-changed   # 增量测试（仅运行受影响测试 ~2-5s，需要 pytest-testmon）
make test-report    # 运行测试并打开 HTML 覆盖率报告
```

#### 传统测试命令（Makefile 不可用时）
```bash
cd backend && source .venv/bin/activate

# 并行测试
pytest tests/ -n auto

# CI 覆盖率检查
pytest tests/ --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=50
```

#### 代码质量
```bash
cd backend && source .venv/bin/activate

# 格式化 + 检查
black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
```

#### 数据库迁移
```bash
cd backend && source .venv/bin/activate

# 创建新迁移
python -m alembic revision --autogenerate -m "描述"

# 应用迁移
python -m alembic upgrade head

# 回滚一步
python -m alembic downgrade -1
```

#### 数据种子
```bash
cd backend && source .venv/bin/activate

python scripts/seed.py              # 基础种子数据
python scripts/create_test_data.py  # 测试数据
python scripts/generate_secrets.py  # 生成安全密钥
```

### 1.2 前端命令

#### 启动开发服务器
```bash
cd frontend && npm run dev  # http://localhost:5173
```

#### 代码质量
```bash
cd frontend

npm run lint              # ESLint 检查并自动修复
npm run format            # Prettier 格式化
npm run type-check        # TypeScript 类型检查（一次性）
npm run type-check:watch  # TypeScript 类型检查（持续监听）
```

#### 构建
```bash
cd frontend

npm run build     # 类型检查 + 生产构建
npm run preview   # 预览生产构建
```

#### 测试 (E2E)
```bash
cd frontend

npm run test:e2e          # 运行所有 E2E 测试
npm run test:e2e:ui       # Playwright UI 模式
npm run test:e2e:headed   # 有头模式（可见浏览器）
npm run test:e2e:report   # 查看测试报告
```

**注意**: 前端目前只有 E2E 测试（Playwright），无单元测试配置。

### 1.3 部署命令

```bash
# 完整部署
./deploy/scripts/deploy.sh

# 快速重启（跳过构建）
./deploy/scripts/deploy.sh --skip-build

# 验证部署
./deploy/scripts/verify-deployment.sh
```

---

## 2. 环境变量配置

### 2.1 必需变量

| 变量名           | 说明                                      | 示例值                                              |
| ---------------- | ----------------------------------------- | --------------------------------------------------- |
| `APP_ENV`        | 运行环境                                  | `development` / `production`                        |
| `DEBUG`          | 调试模式                                  | `true` / `false`                                    |
| `DATABASE_URL`   | PostgreSQL 连接串                         | `postgresql://user:password@localhost:5432/customer_platform` |
| `REDIS_URL`      | Redis 连接串                              | `redis://localhost:6379/0`                          |
| `JWT_SECRET`     | JWT 签名密钥（**生产环境必须 32+ 字符**） | `your-random-32-byte-secret-here`                   |
| `WEBHOOK_SECRET` | Webhook 验证密钥                          | `your-random-32-byte-secret-here`                   |

### 2.2 可选变量

| 变量名                    | 说明           | 默认值                |
| ------------------------- | -------------- | --------------------- |
| `SMTP_HOST`               | SMTP 服务器    | `smtp.company.com`    |
| `SMTP_PORT`               | SMTP 端口      | `587`                 |
| `SMTP_USERNAME`           | SMTP 用户名    | `noreply@company.com` |
| `SMTP_PASSWORD`           | SMTP 密码      | -                     |
| `EXTERNAL_API_BASE_URL`   | 外部 API 地址  | -                     |
| `EXTERNAL_API_TOKEN`      | 外部 API 令牌  | -                     |

### 2.3 配置文件

**开发环境**:
```bash
cd backend
cp .env.example .env
# 编辑 .env 文件，修改必需变量
```

**生成安全密钥**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**生产环境**: 通过 Docker Compose 环境变量注入，见 `deploy/docker-compose.yml`。

---

## 3. 虚拟环境初始化

### 3.1 Python 后端

```bash
cd backend

# 创建虚拟环境 (Python 3.12.x 独占，不支持 3.13+)
python -m venv .venv

# 激活虚拟环境
source .venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 验证 Python 版本
python --version  # 应显示 3.12.x
```

### 3.2 依赖管理

```bash
# 添加新依赖
pip install package-name
pip freeze > requirements.txt

# 或使用 pip-tools（如项目配置）
pip-compile requirements.in
pip-sync
```

---

## 4. Git 工作流

### 4.1 分支策略

| 分支        | 用途               | 保护规则           |
| ----------- | ------------------ | ------------------ |
| `main`      | 生产环境代码       | 禁止直接 push      |
| `develop`   | 开发集成分支       | 禁止直接 push      |
| `feature/*` | 功能开发           | 开发者自主管理     |
| `fix/*`     | 紧急修复           | 开发者自主管理     |
| `release/*` | 发布准备           | 仅允许 bug 修复    |

### 4.2 分支工作流

```
main (生产)
  ↑ merge
develop (开发集成)
  ↑ merge
feature/xxx (功能开发) → 完成后 PR 到 develop
```

### 4.3 Commit 规范 (Conventional Commits)

格式: `<type>(<scope>): <description>`

| Type        | 说明               | 示例                                  |
| ----------- | ------------------ | ------------------------------------- |
| `feat`      | 新功能             | `feat(settlement): add invoice export` |
| `fix`       | 修复 bug           | `fix(auth): resolve JWT expiration`   |
| `refactor`  | 代码重构           | `refactor(api): simplify user service` |
| `test`      | 测试相关           | `test(auth): add JWT validation tests` |
| `docs`      | 文档更新           | `docs: update API reference`          |
| `chore`     | 构建/工具链        | `chore: update dependencies`          |
| `style`     | 代码格式（不影响逻辑） | `style: fix indentation`           |
| `perf`      | 性能优化           | `perf: optimize customer query`       |

**Scope 建议**: 使用业务模块名 (`auth`, `customer`, `settlement`, `profile`, `analysis`)

### 4.4 PR 流程

1. **创建功能分支**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **开发并通过测试**
   ```bash
   # 后端
   make test-parallel
   black app/ tests/ && flake8 app/ tests/
   
   # 前端
   npm run type-check
   npm run lint
   ```

3. **创建 PR**
   - 目标分支: `develop`
   - 标题: 使用 Conventional Commits 格式
   - 描述: 包含变更说明、测试截图（如有 UI 变更）

4. **Code Review → 合并**
   - 至少 1 人 approve
   - CI 全部通过
   - 使用 Squash Merge 保持历史清晰

---

## 5. 文档目录规范

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

## 6. 业务模块详情

### 6.1 账号治理

- **RBAC 权限模型**: 角色-权限-资源三层模型
- **自定义角色**: 支持用户创建自定义角色并分配权限
- **细粒度权限**: 支持资源级别的 CRUD 权限控制
- **权限校验**: 所有 API 端点必须添加 `@auth_required` 装饰器

### 6.2 客户信息管理

- **统一客户基础信息**: 客户名称、联系人、行业、规模等
- **客户画像**: 关联画像数据，支持双等级体系
- **Excel 导入/导出**: 支持批量导入客户数据，模板校验
- **客户搜索与筛选**: 支持多条件组合搜索

### 6.3 结算管理

- **3 种计费模式**:
  - 定价模式: 固定价格
  - 阶梯模式: 按用量阶梯计价
  - 包年模式: 年度订阅
- **余额管理**: 先赠后实扣款策略，支持余额充值/扣减
- **发票管理**: 发票申请、审核、开具流程

### 6.4 画像管理

- **双等级体系**:
  - 规模等级: 基于客户规模评定
  - 消费等级: 基于历史消费评定
- **自定义标签**: 支持用户创建和管理客户标签
- **标签自动打标**: 基于规则自动给客户打标签

### 6.5 客户分析

- **消耗分析**: 客户资源消耗趋势统计
- **回款分析**: 回款进度与预测
- **健康度分析**: 客户健康度评分模型
- **画像分析**: 客户画像维度交叉分析
- **预测回款**: 基于历史数据的回款预测

---

## 8. 测试数据库

### 8.1 测试数据库配置

- **数据库名**: `customer_platform_test`
- **创建命令**: `createdb -U postgres customer_platform_test`
- **删除命令**: `dropdb -U postgres customer_platform_test`
- **重置命令**: `dropdb -U postgres customer_platform_test && createdb -U postgres customer_platform_test`

### 8.2 测试环境

- **测试配置**: 见 `backend/tests/conftest.py`
- **测试数据**: 运行 `python scripts/create_test_data.py` 创建测试数据
- **测试隔离**: 每个测试用例在独立事务中运行，测试后自动回滚

### 8.3 常见问题

| 问题                      | 解决方案                                          |
| ------------------------- | ------------------------------------------------- |
| 测试数据库不存在          | 运行 `createdb -U postgres customer_platform_test` |
| 测试连接失败              | 检查 PostgreSQL 是否运行，用户权限是否正确        |
| 测试数据冲突              | 重置测试数据库并重新创建测试数据                  |
| 并行测试失败              | 确保 pytest-xdist 已安装，尝试减少并行数 `-n 2`   |

---

## 9. 依赖版本

### 9.1 后端依赖

| 依赖           | 版本要求          | 说明                          |
| -------------- | ----------------- | ----------------------------- |
| Python         | 3.12.x (严格)     | 不支持 3.13+                  |
| Sanic          | 22.12             | ASGI 框架                     |
| SQLAlchemy     | 2.0               | ORM                           |
| PostgreSQL     | 18 (Docker)       | 生产/开发数据库               |
| Redis          | 7 (Docker)        | 缓存/会话存储                 |

### 9.2 前端依赖

| 依赖             | 版本    | 说明               |
| ---------------- | ------- | ------------------ |
| Vue              | 3.4     | 前端框架           |
| TypeScript       | 5.3     | 类型系统           |
| Arco Design      | 2.54    | UI 组件库          |
| Vite             | 5.0     | 构建工具           |
| Playwright       | 1.59+   | E2E 测试框架       |

---

## 10. 快速参考卡片

### 日常开发
```bash
# 1. 启动后端
cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. 启动前端（新终端）
cd frontend && npm run dev

# 3. 运行测试
cd backend && make test-parallel

# 4. 代码检查
cd backend && black app/ tests/ && flake8 app/ tests/
cd frontend && npm run lint && npm run type-check
```

### 提交前检查
```bash
# 1. 运行测试
cd backend && make test-parallel
cd frontend && npm run test:e2e

# 2. 代码质量
cd backend && black app/ tests/ && flake8 app/ tests/
cd frontend && npm run lint && npm run format && npm run type-check

# 3. 提交
git add .
git commit -m "feat(scope): description"
```
