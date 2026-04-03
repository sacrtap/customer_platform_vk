# Podman 一键部署指南

## 概述

使用 Podman 一键部署客户运营中台应用和测试数据库。

---

## 前置要求

### macOS

```bash
# 安装 Podman
brew install podman

# 初始化 Podman 机器 (首次使用)
podman machine init

# 启动 Podman 机器
podman machine start
```

### Linux

```bash
# Fedora/RHEL
sudo dnf install podman

# Ubuntu/Debian
sudo apt install podman
```

---

## 快速部署

### 一键部署 (推荐)

```bash
# 运行部署脚本
./deploy/scripts/podman-deploy.sh
```

这将自动完成:
1. ✅ 部署 PostgreSQL 数据库
2. ✅ 创建测试数据库
3. ✅ 运行数据库迁移
4. ✅ 创建测试数据
5. ✅ 运行测试套件
6. ✅ 生成测试报告

---

## 分步部署

### 1. 只部署数据库

```bash
./deploy/scripts/podman-deploy.sh db
```

### 2. 只部署应用

```bash
./deploy/scripts/podman-deploy.sh app
```

### 3. 只运行测试

```bash
./deploy/scripts/podman-deploy.sh test
```

---

## 服务管理

### 查看状态

```bash
./deploy/scripts/podman-deploy.sh status
```

### 停止服务

```bash
./deploy/scripts/podman-deploy.sh stop
```

### 清理容器

```bash
./deploy/scripts/podman-deploy.sh clean
```

---

## 手动命令

### 数据库操作

```bash
# 启动数据库
podman start customer-platform-db

# 停止数据库
podman stop customer-platform-db

# 查看日志
podman logs customer-platform-db

# 进入数据库 shell
podman exec -it customer-platform-db psql -U user -d customer_platform
```

### 应用操作

```bash
# 启动应用
podman start customer-platform-app

# 停止应用
podman stop customer-platform-app

# 查看日志
podman logs customer-platform-app

# 进入容器 shell
podman exec -it customer-platform-app bash
```

---

## 访问服务

| 服务   | 地址                      | 说明       |
| ------ | ------------------------- | ---------- |
| API    | http://localhost:8000     | 应用 API   |
| 健康   | http://localhost:8000/health | 健康检查   |
| 数据库 | localhost:5432            | PostgreSQL |

---

## 测试数据

部署后自动创建以下测试数据:

### 管理员账户
- **用户名**: admin
- **密码**: admin123

### 测试客户
- **公司 ID**: TEST001
- **名称**: 测试客户公司
- **余额**: 实充 10000 + 赠费 1000

---

## 运行测试

### 单元测试

```bash
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/customer_platform"
export TEST_DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/customer_platform_test"

python -m pytest tests/unit/ -v
```

### API 集成测试

```bash
python -m pytest tests/integration/ -v
```

### 生成覆盖率报告

```bash
python -m pytest tests/unit/ \
    --cov=app \
    --cov-report=html:../docs/testing/coverage-reports/html
```

---

## 故障排查

### Podman 机器无法启动

```bash
# macOS: 重启 Podman 机器
podman machine stop
podman machine start

# 或重置
podman machine rm
podman machine init
podman machine start
```

### 端口被占用

```bash
# 检查端口占用
lsof -i :5432
lsof -i :8000

# 停止占用端口的进程
kill -9 <PID>
```

### 数据库连接失败

```bash
# 检查数据库容器状态
podman ps --filter "name=customer-platform-db"

# 查看数据库日志
podman logs customer-platform-db

# 测试数据库连接
podman exec customer-platform-db pg_isready -U user
```

### 权限问题 (Linux)

```bash
# 使用 rootless 模式
podman login docker.io

# 或添加用户到 podman 组
sudo usermod -aG podman $USER
```

---

## 环境变量

可以通过环境变量自定义配置:

```bash
# 自定义端口
export DB_PORT=5433
export APP_PORT=8001

# 自定义数据库配置
export DB_NAME=mydb
export DB_USER=myuser
export DB_PASSWORD=mypassword

# 运行部署
./deploy/scripts/podman-deploy.sh
```

---

## 生产部署

生产环境部署请参考:

1. 使用持久化存储卷
2. 配置环境变量密钥
3. 设置容器重启策略
4. 配置反向代理 (Nginx/Traefik)
5. 启用 HTTPS
6. 配置日志收集
7. 设置监控告警

示例生产部署配置:

```bash
podman run -d \
  --name customer-platform-db \
  -e POSTGRES_DB=customer_platform \
  -e POSTGRES_USER=${DB_USER} \
  -e POSTGRES_PASSWORD=${DB_PASSWORD} \
  -v db-data:/var/lib/postgresql/data \
  --restart=always \
  postgres:14

podman run -d \
  --name customer-platform-app \
  -p 8000:8000 \
  -e DATABASE_URL=${DATABASE_URL} \
  -e JWT_SECRET=${JWT_SECRET} \
  --restart=always \
  customer-platform-app:latest
```

---

## 参考文档

- [Podman 官方文档](https://podman.io/docs)
- [PostgreSQL 镜像](https://hub.docker.com/_/postgres)
- [测试数据库配置](./test-database-setup.md)
