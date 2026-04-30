# 本地环境搭建指南

> 本指南详细说明如何在本地 macOS 环境搭建客户运营中台开发环境。

---

## 环境总览

| 组件 | 版本 | 安装方式 |
|------|------|----------|
| Python | 3.12.x | pyenv |
| Node.js | 18+ | Homebrew/nvm |
| PostgreSQL | 18 | Postgres.app 或 Homebrew |
| Redis | 7+ | Homebrew |

---

## 1. 安装依赖

### 1.1 Python 3.12

```bash
# 使用 pyenv 管理 Python 版本
brew install pyenv

# 安装 Python 3.12
pyenv install 3.12.12

# 设置为全局默认版本
pyenv global 3.12.12

# 验证
python3 --version  # Python 3.12.12
```

### 1.2 Node.js

```bash
# 使用 Homebrew 安装
brew install node

# 或使用 nvm (推荐)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18

# 验证
node --version  # v18.x.x
npm --version   # 9.x.x+
```

### 1.3 PostgreSQL

#### 方式 A: Postgres.app (推荐)

```bash
# 下载并安装
# 访问 https://postgresapp.com/
# 拖拽到 Applications 文件夹

# 添加命令行工具到 PATH
echo 'export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 验证
psql --version  # psql (PostgreSQL) 18.x.x
```

#### 方式 B: Homebrew

```bash
brew install postgresql@18
brew services start postgresql@18

# 验证
psql --version
```

### 1.4 Redis

```bash
# 安装
brew install redis

# 启动 (守护进程模式)
redis-server --daemonize yes

# 验证
redis-cli ping  # 应返回 PONG

# 停止 Redis
redis-cli shutdown

# 开机自启 (可选)
brew services start redis
```

---

## 2. 初始化数据库

### 2.1 创建数据库

```bash
# 方法 1: 使用 createdb
createdb -U postgres customer_platform

# 方法 2: 使用 psql
psql -U postgres -c "CREATE DATABASE customer_platform;"

# 验证数据库创建成功
psql -U postgres -d customer_platform -c "SELECT version();"
```

### 2.2 验证服务状态

```bash
# PostgreSQL 检查
psql -U postgres -c "SELECT 1;"
# 预期输出:
#  ?column? 
# ----------
#         1
# (1 row)

# Redis 检查
redis-cli ping
# 预期输出: PONG
```

---

## 3. 后端环境搭建

### 3.1 创建虚拟环境

```bash
cd backend

# 创建虚拟环境 (必须使用 python3)
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 验证
which python  # 应指向 .venv 目录
python --version  # Python 3.12.x
```

### 3.2 安装依赖

```bash
# 升级 pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

### 3.3 配置环境变量

```bash
# 复制环境配置
cp .env.example .env

# 编辑 .env 文件
# 至少确保以下配置正确:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/customer_platform
# REDIS_URL=redis://localhost:6379/0
# JWT_SECRET=<生成的随机密钥>
```

### 3.4 数据库迁移

```bash
# 运行数据库迁移
python -m alembic upgrade head

# 检查迁移状态
python -m alembic current
```

### 3.5 初始化种子数据

```bash
# 创建管理员账号和权限
python scripts/seed.py

# (可选) 创建测试数据
python scripts/create_test_data.py
```

### 3.6 启动后端服务

```bash
# 启动开发服务器 (热重载)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 验证后端运行正常
curl http://localhost:8000/health
# 预期: {"status": "ok"}
```

---

## 4. 前端环境搭建

### 4.1 安装依赖

```bash
cd frontend

# 安装 Node.js 依赖
npm install

# (首次) 安装 Playwright 浏览器
npx playwright install chromium
```

### 4.2 启动前端服务

```bash
# 启动开发服务器
npm run dev

# 访问 http://localhost:5173
```

---

## 5. 验证完整环境

### 5.1 服务检查清单

```bash
# 检查所有服务状态
echo "=== 服务状态检查 ==="

# PostgreSQL
psql -U postgres -c "SELECT 1;" > /dev/null 2>&1 && echo "✅ PostgreSQL: OK" || echo "❌ PostgreSQL: FAILED"

# Redis
redis-cli ping > /dev/null 2>&1 && echo "✅ Redis: OK" || echo "❌ Redis: FAILED"

# Backend
curl -s http://localhost:8000/health > /dev/null 2>&1 && echo "✅ Backend: OK" || echo "❌ Backend: FAILED"

# Frontend
curl -s http://localhost:5173 > /dev/null 2>&1 && echo "✅ Frontend: OK" || echo "❌ Frontend: FAILED"
```

### 5.2 登录验证

打开浏览器访问 http://localhost:5173/login

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | 超级管理员 |
| operator | operator123 | 运营经理 (需创建测试数据) |
| sales | sales123 | 销售 (需创建测试数据) |

### 5.3 API 验证

```bash
# 获取 Token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 测试客户列表 API
curl -s http://localhost:8000/api/v1/customers?page=1&page_size=1 \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 6. 运行测试

### 6.1 后端测试

```bash
cd backend
source .venv/bin/activate

# 运行所有测试
pytest

# 运行单个测试
pytest tests/unit/test_auth_service.py -v

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

### 6.2 前端 E2E 测试

```bash
cd frontend

# 运行所有 E2E 测试
npm run test:e2e

# 运行客户管理测试
npx playwright test test_customer_crud.spec.ts customer-detail.spec.ts test_customer_filters.spec.ts test_customer_import_export.spec.ts test_customer_edge_cases.spec.ts test_customer_permissions.spec.ts

# UI 模式调试
npx playwright test --ui

# 查看测试报告
npx playwright show-report
```

---

## 7. 常见问题排查

### Q: Redis 连接失败

```bash
# 检查 Redis 是否运行
redis-cli ping

# 如果未运行，启动 Redis
redis-server --daemonize yes

# 如果未安装
brew install redis
```

### Q: 数据库连接失败

```bash
# 检查 PostgreSQL 是否运行
pg_isready

# 检查数据库是否存在
psql -U postgres -l | grep customer_platform

# 如果数据库不存在，创建它
createdb -U postgres customer_platform
```

### Q: 客户 API 报 500 错误

```bash
# 1. 检查 Redis 是否运行
redis-cli ping

# 2. 检查数据库迁移是否完整
python -m alembic upgrade head

# 3. 检查后端日志
# 查看终端输出或日志文件
```

### Q: Alembic 迁移链损坏

```bash
# 如果迁移文件有重复编号或分支问题
# 检查当前版本
python -m alembic current

# 如果报错，可能需要手动修复迁移文件
# 或删除 alembic_version 表重新迁移
# psql -U postgres -d customer_platform -c "DROP TABLE alembic_version;"
# python -m alembic upgrade head
```

### Q: 前端编译错误

```bash
# 清理 node_modules
rm -rf node_modules package-lock.json

# 重新安装
npm install

# 清除缓存
npm cache clean --force
```

---

## 8. 开发工作流

### 日常开发流程

```bash
# 1. 启动基础服务 (首次或重启后)
redis-server --daemonize yes
# PostgreSQL 通过 Postgres.app 或 brew services 启动

# 2. 启动后端
cd backend && source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. 新开终端，启动前端
cd frontend && npm run dev

# 4. 访问 http://localhost:5173
```

### 停止服务

```bash
# 停止后端 (Ctrl+C 在终端中)

# 停止前端 (Ctrl+C 在终端中)

# 停止 Redis (可选)
redis-cli shutdown

# 停止 PostgreSQL (如使用 Homebrew)
brew services stop postgresql@18
```

---

## 9. 性能优化建议

### 后端
- 使用 `--reload` 仅在开发时启用，生产环境关闭
- PostgreSQL 连接池大小根据负载调整
- Redis 缓存 TTL 根据业务需求调整

### 前端
- 使用 `npm run dev` 开发模式享受热重载
- 生产构建使用 `npm run build`
- 类型检查使用 `npm run type-check`

---

**最后更新**: 2026-04-15  
**适用平台**: macOS  
**维护者**: 开发团队
