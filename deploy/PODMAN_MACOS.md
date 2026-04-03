# Podman 部署指南 (macOS)

## 概述

本文档说明如何在 macOS 上部署客户运营中台数据库环境。

**PostgreSQL 版本**: 18.x

---

## 前置要求

### 方案 1: 使用 Docker Desktop (推荐)

```bash
# 安装 Docker Desktop
brew install --cask docker

# 启动 Docker
open -a Docker
```

### 方案 2: 使用 Podman

```bash
# 安装 Podman
brew install podman

# 初始化并启动 Podman 机器
podman machine init
podman machine start
```

### 方案 3: 使用本地 PostgreSQL (最简单)

```bash
# 安装 PostgreSQL 18
brew install postgresql@18
brew services start postgresql@18

# 验证安装
psql --version
# 输出：psql (PostgreSQL) 18.x
```

---

## 快速部署 (推荐：本地 PostgreSQL 18)

```bash
# 1. 安装 PostgreSQL 18
brew install postgresql@18
brew services start postgresql@18

# 2. 创建数据库
createdb -U $(whoami) customer_platform
createdb -U $(whoami) customer_platform_test

# 3. 验证连接
psql -U $(whoami) -d customer_platform -c "SELECT version();"

# 4. 运行迁移
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://$(whoami)@localhost/customer_platform"

python -c "
from sqlalchemy import create_engine
from app.models.base import BaseModel
engine = create_engine('${DATABASE_URL}')
BaseModel.metadata.create_all(engine)
print('✅ 数据库表已创建')
"

# 5. 创建测试数据
python scripts/create_test_data.py

deactivate
cd ..

echo "✅ 部署完成!"
echo "管理员：admin / admin123"
echo "测试客户：TEST001 (余额：11000)"
```

---

## 方案 1: Docker Desktop 部署

```bash
# 运行 PostgreSQL 18 容器
docker run -d --name customer-platform-db \
  -e POSTGRES_DB=customer_platform \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  docker.io/library/postgres:18

# 等待数据库就绪
sleep 5

# 创建测试数据库
docker exec customer-platform-db createdb -U user customer_platform_test

# 运行迁移
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://user:password@localhost:5432/customer_platform"

python -c "
from sqlalchemy import create_engine
from app.models.base import BaseModel
engine = create_engine('${DATABASE_URL}')
BaseModel.metadata.create_all(engine)
print('✅ 数据库表已创建')
"

# 创建测试数据
python scripts/create_test_data.py

echo "✅ Docker 部署完成!"
```

---

## 方案 2: Podman 部署

```bash
# 运行 PostgreSQL 18 容器
podman run -d --name customer-platform-db \
  -e POSTGRES_DB=customer_platform \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  docker.io/library/postgres:18

# 等待数据库就绪
sleep 5

# 进入 Podman VM 运行迁移
podman machine ssh "
  podman exec customer-platform-db createdb -U user customer_platform_test
  
  podman run --rm --network container:customer-platform-db \
    python:3.14-slim \
    bash -c '
      pip install sqlalchemy psycopg2-binary bcrypt
      python -c \"
from sqlalchemy import create_engine
from app.models.base import BaseModel
engine = create_engine(\"postgresql://user:password@localhost:5432/customer_platform\")
BaseModel.metadata.create_all(engine)
print(\\\"✅ 数据库表已创建\\\")
\"
    '
"

echo "✅ Podman 部署完成!"
```

---

## 数据库配置

### 连接字符串

| 环境   | 连接字符串格式                                      |
| ------ | --------------------------------------------------- |
| 本地   | `postgresql://$(whoami)@localhost/customer_platform` |
| Docker | `postgresql://user:password@localhost:5432/customer_platform` |
| Podman | `postgresql://user:password@localhost:5432/customer_platform` |

### 环境变量

```bash
# .env 文件配置
DATABASE_URL=postgresql://user:password@localhost:5432/customer_platform
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/customer_platform_test
```

---

## 服务管理

### 本地 PostgreSQL

```bash
# 查看状态
brew services list | grep postgresql

# 重启服务
brew services restart postgresql@18

# 停止服务
brew services stop postgresql@18

# 启动服务
brew services start postgresql@18
```

### Docker 容器

```bash
# 查看状态
docker ps | grep customer-platform-db

# 重启容器
docker restart customer-platform-db

# 停止容器
docker stop customer-platform-db

# 启动容器
docker start customer-platform-db

# 查看日志
docker logs customer-platform-db
```

### Podman 容器

```bash
# 查看状态
podman ps | grep customer-platform-db

# 重启容器
podman restart customer-platform-db

# 停止容器
podman stop customer-platform-db

# 启动容器
podman start customer-platform-db

# 查看日志
podman logs customer-platform-db
```

---

## 数据库维护

### 备份

```bash
# 本地 PostgreSQL
pg_dump -U $(whoami) customer_platform > backup_$(date +%Y%m%d).sql

# Docker
docker exec customer-platform-db pg_dump -U user customer_platform > backup_$(date +%Y%m%d).sql

# Podman
podman exec customer-platform-db pg_dump -U user customer_platform > backup_$(date +%Y%m%d).sql
```

### 恢复

```bash
# 本地 PostgreSQL
psql -U $(whoami) customer_platform < backup_20260403.sql

# Docker
docker exec -i customer-platform-db psql -U user customer_platform < backup_20260403.sql

# Podman
podman exec -i customer-platform-db psql -U user customer_platform < backup_20260403.sql
```

### 清理

```bash
# 删除所有数据 (谨慎使用!)
# 本地 PostgreSQL
psql -U $(whoami) customer_platform -c "TRUNCATE TABLE users, customers, customer_profiles, customer_balances CASCADE;"

# Docker/容器
docker exec -i customer-platform-db psql -U user customer_platform -c "TRUNCATE TABLE users, customers, customer_profiles, customer_balances CASCADE;"
```

---

## 故障排查

### 问题 1: PostgreSQL 18 安装失败

```bash
# 清理旧版本
brew uninstall postgresql@14 postgresql@15 postgresql@16 postgresql@17 2>/dev/null || true
brew cleanup

# 重新安装
brew install postgresql@18
```

### 问题 2: 无法连接数据库

```bash
# 检查服务状态
brew services list | grep postgresql

# 检查端口
lsof -i :5432

# 重启服务
brew services restart postgresql@18
```

### 问题 3: 权限错误

```bash
# 创建用户 (如果需要)
psql postgres -c "CREATE USER $(whoami) WITH SUPERUSER;"

# 授权数据库
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE customer_platform TO $(whoami);"
```

### 问题 4: 数据库不存在

```bash
# 重新创建数据库
dropdb -U $(whoami) customer_platform 2>/dev/null || true
dropdb -U $(whoami) customer_platform_test 2>/dev/null || true
createdb -U $(whoami) customer_platform
createdb -U $(whoami) customer_platform_test
```

### 问题 5: Docker/Podman 容器无法启动

```bash
# 清理旧容器
docker stop customer-platform-db && docker rm customer-platform-db 2>/dev/null || true
podman stop customer-platform-db && podman rm customer-platform-db 2>/dev/null || true

# 重新创建
docker run -d --name customer-platform-db \
  -e POSTGRES_DB=customer_platform \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:18
```

---

## PostgreSQL 18 新特性

PostgreSQL 18 带来的主要改进:

1. **性能提升**: 查询优化器改进，并行查询增强
2. **SQL/JSON 增强**: 更强大的 JSON 处理功能
3. **安全性**: 增强的认证和加密选项
4. **可维护性**: 改进的监控和诊断工具

参考文档:
- [PostgreSQL 18 发布说明](https://www.postgresql.org/docs/18/release-18.html)
- [PostgreSQL 18 新特性](https://www.postgresql.org/docs/18/release-18-summary.html)

---

## 参考文档

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/18/)
- [Homebrew PostgreSQL](https://formulae.brew.sh/formula/postgresql@18)
- [PostgreSQL Docker 镜像](https://hub.docker.com/_/postgres)
- [测试数据库配置](./testing/test-database-setup.md)
