# 部署指南

## 推荐方案：本地 PostgreSQL (macOS)

由于 macOS 上 Podman 运行在 VM 中，存在网络隔离问题，**推荐使用本地 PostgreSQL**。

### 快速部署 (5 分钟)

```bash
# 1. 安装 PostgreSQL 18
brew install postgresql@18
brew services start postgresql@18

# 2. 创建数据库
createdb customer_platform
createdb customer_platform_test

# 3. 验证连接
psql -d customer_platform -c "SELECT version();"

# 4. 运行迁移
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://localhost/customer_platform"

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

## 备选方案：Docker Desktop

如果不想安装本地 PostgreSQL，可以使用 Docker Desktop：

```bash
# 1. 安装 Docker Desktop
brew install --cask docker
open -a Docker

# 2. 运行数据库容器
docker run -d --name customer-platform-db \
  -e POSTGRES_DB=customer_platform \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:18

# 3. 等待数据库就绪
sleep 5

# 4. 运行迁移
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

# 5. 创建测试数据
python scripts/create_test_data.py

echo "✅ Docker 部署完成!"
```

---

## 不推荐：Podman (macOS)

Podman 在 macOS 上运行在 VM 中，存在网络隔离问题：
- 容器端口转发到 VM，不是直接到主机
- 主机上的 Python 无法直接连接容器内数据库
- 需要在 VM 内运行迁移，配置复杂

如果必须使用 Podman，请参考 `deploy/PODMAN_MACOS.md` 了解详细配置。

---

## 服务管理

### 本地 PostgreSQL

```bash
# 查看状态
brew services list | grep postgresql

# 重启
brew services restart postgresql@18

# 停止
brew services stop postgresql@18

# 启动
brew services start postgresql@18
```

### Docker 容器

```bash
# 查看状态
docker ps | grep customer-platform-db

# 重启
docker restart customer-platform-db

# 停止/启动
docker stop customer-platform-db
docker start customer-platform-db

# 查看日志
docker logs customer-platform-db
```

---

## 故障排查

### 问题：brew install postgresql@18 失败

```bash
# 清理旧版本
brew uninstall postgresql@14 postgresql@15 postgresql@16 postgresql@17 2>/dev/null || true
brew cleanup

# 重新安装
brew install postgresql@18
```

### 问题：无法连接数据库

```bash
# 检查服务状态
brew services list | grep postgresql

# 检查端口
lsof -i :5432

# 重启服务
brew services restart postgresql@18
```

### 问题：数据库已存在

```bash
# 删除并重新创建
dropdb customer_platform
dropdb customer_platform_test
createdb customer_platform
createdb customer_platform_test
```

---

## 参考文档

- [PODMAN_MACOS.md](./PODMAN_MACOS.md) - Podman 部署指南
- [test-database-setup.md](../docs/testing/test-database-setup.md) - 测试数据库配置
- [test-summary.md](../docs/testing/test-summary.md) - 测试总结报告
