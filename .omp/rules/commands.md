## Development Commands

### 快速开始

#### 后端开发环境

```bash
cd backend

# 创建虚拟环境（必需）
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 配置环境变量
cp ../.env.example .env
# 编辑 .env，至少配置 DATABASE_URL

# 创建数据库
createdb -U postgres customer_platform

# 运行迁移
python -m alembic upgrade head

# 初始化种子数据（首次启动必需）
python scripts/seed.py

# 启动开发服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端开发环境

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（热重载）
npm run dev  # http://localhost:5173
```

### 测试命令

#### 后端测试

```bash
cd backend
source .venv/bin/activate

# 默认：单元 + 集成测试
make test

# 仅单元测试（最快）
make test-fast          # pytest tests/unit/ -v

# 并行测试
make test-parallel      # pytest-xdist 并行单元 + 串行集成

# 覆盖率测试（CI 使用，要求 ≥50%）
make test-cov           # pytest --cov=app --cov-fail-under=50

# 直接运行 pytest
pytest tests/unit/ -v --tb=short
pytest tests/integration/ -v --tb=short
```

#### 前端测试

```bash
cd frontend

# Vitest 单元测试
npx vitest

# Playwright E2E 测试
npx playwright test

# 自动启停前后端的 E2E 测试脚本
./scripts/run-e2e-tests.sh
```

### 代码质量检查

#### 后端

```bash
cd backend

# Ruff 格式化
ruff format app/ tests/

# Ruff 检查
ruff check app/ tests/

# 修复可自动修复的问题
ruff check --fix app/ tests/
```

#### 前端

```bash
cd frontend

# ESLint 检查
npm run lint

# Prettier 格式化
npx prettier --write src/

# TypeScript 类型检查
npx vue-tsc --noEmit
```

### 其他常用命令

见根目录 `Makefile` 和 `backend/scripts/`。
