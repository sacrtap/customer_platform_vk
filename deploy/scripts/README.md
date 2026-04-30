# 部署脚本指南

## 概述

本目录包含客户运营中台的部署脚本。

---

## 可用脚本

### 1. local-deploy.sh (推荐 - macOS 本地部署)

一键部署到本地 PostgreSQL 数据库。

```bash
# 完整部署
./deploy/scripts/local-deploy.sh

# 清理后重新部署
./deploy/scripts/local-deploy.sh --clean

# 只安装数据库 (跳过迁移)
./deploy/scripts/local-deploy.sh --skip-migrate

# 显示帮助
./deploy/scripts/local-deploy.sh --help
```

### 2. deploy.sh (生产环境 Docker 部署)

生产环境部署脚本，使用 Podman/Docker 容器化部署。

```bash
# 部署最新版本
./deploy/scripts/deploy.sh

# 部署指定版本
./deploy/scripts/deploy.sh v1.0.0
```

### 3. backup.sh (数据库备份)

备份 PostgreSQL 数据库。

```bash
# 执行备份
./deploy/scripts/backup.sh
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
docker ps | grep customer-platform

# 停止服务
docker-compose -f deploy/docker-compose.yml down

# 启动服务
docker-compose -f deploy/docker-compose.yml up -d
```

---

## 访问服务

| 服务   | 地址                      | 说明       |
| ------ | ------------------------- | ---------- |
| API    | http://localhost:8000     | 应用 API   |
| 健康   | http://localhost:8000/health | 健康检查   |
| 数据库 | localhost:5432            | PostgreSQL |
| 前端   | http://localhost:5173     | Vue3 前端  |

---

## 测试数据

部署后自动创建以下测试数据:

### 管理员账户
- **用户名**: admin
- **密码**: admin123

### 测试客户
- **公司 ID**: TEST001
- **名称**: 测试客户公司
- **余额**: 实充 10000 + 赠费 1000 = 11000

---

## 运行测试

### 单元测试

```bash
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://localhost/customer_platform"
export TEST_DATABASE_URL="postgresql://localhost/customer_platform_test"

pytest tests/unit/ -v
```

### 集成测试

```bash
pytest tests/integration/ -v
```

### 生成覆盖率报告

```bash
pytest tests/ \
    --cov=app \
    --cov-report=html:../docs/testing/coverage-reports/html
```

---

## 故障排查

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
# 检查数据库服务状态
brew services list | grep postgresql

# 查看数据库日志
brew services restart postgresql@18

# 测试数据库连接
pg_isready
```

---

## 环境变量

可以通过环境变量自定义配置:

```bash
# 本地部署
export DATABASE_URL="postgresql://localhost/customer_platform"
export TEST_DATABASE_URL="postgresql://localhost/customer_platform_test"

# 生产部署
export JWT_SECRET=your-secret-key
export SMTP_PASSWORD=your-smtp-password
```

---

## 生产部署

生产环境部署注意事项:

1. 使用持久化存储卷
2. 配置环境变量密钥 (不要硬编码密码)
3. 设置容器重启策略
4. 配置反向代理 (Nginx/Traefik)
5. 启用 HTTPS
6. 配置日志收集
7. 设置监控告警

---

## 参考文档

- [部署指南](../README.md) - 完整部署指南
- [Podman 部署](../PODMAN_MACOS.md) - Podman 详细说明
- [测试数据库配置](../../docs/testing/test-database-setup.md) - 测试环境配置
