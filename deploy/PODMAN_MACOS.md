# Podman 部署指南 (macOS)

## 问题说明

在 macOS 上，Podman 运行在 VM 中，这导致以下问题:
1. 主机上的 Python 无法直接连接容器内的数据库
2. 需要在 VM 内运行迁移脚本

## 解决方案

### 方案 1: 使用 Docker 代替 (推荐)

Docker Desktop for Mac 提供更好的网络集成:

```bash
# 安装 Docker Desktop
brew install --cask docker

# 启动 Docker
open -a Docker

# 运行部署
docker run -d --name customer-platform-db \
  -e POSTGRES_DB=customer_platform \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:14

# 在主机上运行迁移
cd backend
source .venv/bin/activate
export DATABASE_URL="postgresql://user:password@localhost:5432/customer_platform"
python -c "from sqlalchemy import create_engine; from app.models.base import BaseModel; e = create_engine('postgresql://user:password@localhost:5432/customer_platform'); BaseModel.metadata.create_all(e)"
```

### 方案 2: 使用 SSH 进入 Podman VM

```bash
# 进入 Podman VM
podman machine ssh

# 在 VM 内运行容器
podman run -d --name customer-platform-db \
  -e POSTGRES_DB=customer_platform \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:14

# 在 VM 内运行迁移
podman run --rm --network container:customer-platform-db \
  -v $(pwd)/backend:/app \
  python:3.14 \
  bash -c "cd /app && pip install -r requirements.txt && python -c 'from sqlalchemy import create_engine; from app.models.base import BaseModel; e = create_engine(\"postgresql://user:password@localhost:5432/customer_platform\"); BaseModel.metadata.create_all(e)'"
```

### 方案 3: 使用本地 PostgreSQL (最简单)

```bash
# 使用 Homebrew 安装 PostgreSQL
brew install postgresql@14
brew services start postgresql@14

# 创建数据库
createdb customer_platform
createdb customer_platform_test

# 运行迁移
cd backend
source .venv/bin/activate
export DATABASE_URL="postgresql://localhost/customer_platform"
python -c "from sqlalchemy import create_engine; from app.models.base import BaseModel; e = create_engine('postgresql://localhost/customer_platform'); BaseModel.metadata.create_all(e)"

# 创建测试数据
python scripts/create_test_data.py
```

## 快速测试 (无需迁移)

如果只想快速测试数据库连接:

```bash
# 使用 Podman 运行数据库
podman run -d --name test-db \
  -e POSTGRES_DB=test \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:14

# 测试连接 (在 Podman VM 内)
podman machine ssh "podman exec test-db psql -U user -d test -c 'SELECT 1'"

# 输出应为:
#  ?column? 
# ----------
#         1
```

## 推荐配置

对于开发和测试，推荐使用 **方案 3 (本地 PostgreSQL)**:

```bash
# 完整部署流程
brew install postgresql@14
brew services start postgresql@14

createdb customer_platform
createdb customer_platform_test

cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://localhost/customer_platform"

# 运行迁移
python -c "
from sqlalchemy import create_engine
from app.models.base import BaseModel
engine = create_engine('postgresql://localhost/customer_platform')
BaseModel.metadata.create_all(engine)
print('✅ 数据库表已创建')
"

# 创建测试数据
python scripts/create_test_data.py

echo "✅ 部署完成!"
echo "管理员：admin / admin123"
echo "测试客户：TEST001 (余额：11000)"
```

## 故障排查

### 问题：无法连接数据库

```bash
# 检查 PostgreSQL 是否运行
brew services list | grep postgresql

# 检查端口
lsof -i :5432

# 重启 PostgreSQL
brew services restart postgresql@14
```

### 问题：权限错误

```bash
# 创建用户
psql postgres -c "CREATE USER $(whoami) WITH SUPERUSER;"
```

### 问题：数据库不存在

```bash
# 重新创建数据库
dropdb customer_platform 2>/dev/null
createdb customer_platform
```
