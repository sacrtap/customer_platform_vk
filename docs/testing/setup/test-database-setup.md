# 测试数据库配置指南

## 概述

本文档说明如何配置用于 API 集成测试的 PostgreSQL 测试数据库。

---

## 前置要求

- PostgreSQL 18+ 已安装
- 具有创建数据库权限的用户
- 网络连接正常

---

## 步骤 1: 检查 PostgreSQL 安装

```bash
# 检查 PostgreSQL 是否运行
brew services list | grep postgresql

# 如果没有安装，使用 Homebrew 安装
brew install postgresql@18
brew services start postgresql@18
```

---

## 步骤 2: 创建测试数据库用户

```bash
# 连接到 PostgreSQL
psql -U postgres

# 创建测试用户 (如果不存在)
CREATE USER user WITH PASSWORD 'password' CREATEDB;

# 授权
GRANT ALL PRIVILEGES ON DATABASE postgres TO user;
\q
```

---

## 步骤 3: 创建测试数据库

```bash
# 方法 1: 使用 psql
psql -U postgres -c "CREATE DATABASE customer_platform_test OWNER user;"

# 方法 2: 使用 createdb
createdb -U postgres -O user customer_platform_test
```

---

## 步骤 4: 配置测试环境变量

创建 `.env.test` 文件在 `backend/` 目录:

```bash
# backend/.env.test
TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/customer_platform_test
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/customer_platform_test
JWT_SECRET=test-secret-key-for-testing-only
JWT_ALGORITHM=HS256
```

---

## 步骤 5: 运行数据库迁移

```bash
cd backend
source .venv/bin/activate

# 运行 Alembic 迁移创建所有表
python -m alembic upgrade head

# 验证表已创建
psql -U user -d customer_platform_test -c "\dt"
```

预期输出应包含以下 22 张表:

```
              List of relations
 Schema |          Name           | Type  |  Owner   
--------+-------------------------+-------+----------
 public | users                   | table | user
 public | roles                   | table | user
 public | permissions             | table | user
 public | user_roles              | table | user
 public | role_permissions        | table | user
 public | customers               | table | user
 public | customer_profiles       | table | user
 public | customer_balances       | table | user
 public | tags                    | table | user
 public | customer_tags           | table | user
 public | profile_tags            | table | user
 public | invoices                | table | user
 public | invoice_items           | table | user
 public | pricing_rules           | table | user
 public | recharge_records        | table | user
 public | consumption_records     | table | user
 public | daily_usage             | table | user
 public | sync_task_logs          | table | user
 public | audit_logs              | table | user
 public | webhook_signatures      | table | user
 public | customer_groups         | table | user
 public | customer_group_members  | table | user
```

---

## 步骤 6: 创建测试数据

使用已有的测试数据创建脚本:

```bash
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://user:password@localhost:5432/customer_platform_test"
python scripts/create_test_data.py
```

自动创建以下测试数据:

### 管理员账户
- **用户名**: admin
- **密码**: admin123

### 测试客户
- **公司 ID**: TEST001
- **名称**: 测试客户公司
- **余额**: 实充 10000 + 赠费 1000 = 11000

---

## 步骤 7: 配置测试设置

测试配置通过环境变量传递，参考 `backend/tests/conftest.py` 和 `backend/.env.example`:

```bash
# 测试环境变量
export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/customer_platform"
export TEST_DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/customer_platform_test"
export JWT_SECRET=test-secret-key-for-testing-only
```

---

## 步骤 8: 运行 API 集成测试

```bash
cd backend
source .venv/bin/activate

# 运行所有测试
pytest tests/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行单元测试
pytest tests/unit/ -v

# 运行并生成覆盖率
pytest tests/ --cov=app --cov-report=html
```

---

## 步骤 9: 清理测试数据 (可选)

```bash
# 删除所有测试数据但保留表结构
psql -U user -d customer_platform_test << EOF
TRUNCATE TABLE 
    consumption_records,
    invoice_items,
    invoices,
    recharge_records,
    pricing_rules,
    profile_tags,
    customer_tags,
    customer_balances,
    customer_profiles,
    customers,
    audit_logs,
    sync_task_logs,
    user_roles,
    role_permissions,
    permissions,
    roles,
    users
CASCADE;
EOF

# 或者删除整个测试数据库
dropdb -U postgres customer_platform_test
```

---

## 故障排查

### 问题 1: 无法连接到数据库

```bash
# 检查 PostgreSQL 是否运行
brew services list

# 重启 PostgreSQL
brew services restart postgresql@18

# 检查端口
lsof -i :5432
```

### 问题 2: 认证失败

```bash
# 重置用户密码
psql -U postgres -c "ALTER USER user WITH PASSWORD 'password';"
```

### 问题 3: 数据库不存在

```bash
# 重新创建数据库
dropdb -U postgres customer_platform_test 2>/dev/null
createdb -U postgres -O user customer_platform_test
```

### 问题 4: asyncpg 驱动问题

```bash
cd backend
source .venv/bin/activate
pip install --upgrade asyncpg
```

---

## Docker 方式 (可选)

使用 Docker 运行测试数据库:

```bash
# 启动测试数据库容器
docker run -d \
  --name customer-platform-test-db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=customer_platform_test \
  -p 5432:5432 \
  postgres:18

# 等待数据库就绪
sleep 5

# 运行迁移
cd backend && source .venv/bin/activate
export DATABASE_URL="postgresql://user:password@localhost:5432/customer_platform_test"
python -m alembic upgrade head

# 运行测试
pytest tests/integration/ -v

# 清理
docker stop customer-platform-test-db
docker rm customer-platform-test-db
```

---

## 验证配置

运行以下命令验证配置正确:

```bash
cd backend
source .venv/bin/activate

# 运行单个测试验证
pytest tests/integration/test_api.py -v -k login

# 预期输出: PASSED
```

---

## 参考文档

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [asyncpg 文档](https://magicstack.github.io/asyncpg/current/)
- [Alembic 文档](https://alembic.sqlalchemy.org/)
