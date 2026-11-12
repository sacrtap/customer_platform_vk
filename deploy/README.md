# 部署指南

## 推荐方案：本地 PostgreSQL (macOS)

由于 macOS 上 Podman 运行在 VM 中，存在网络隔离问题，**推荐使用本地 PostgreSQL**。

### 一键部署 (推荐)

```bash
# 运行一键部署脚本
./deploy/scripts/local-deploy.sh
```

这将自动完成:
1. ✅ 检查/安装 PostgreSQL 18
2. ✅ 启动 PostgreSQL 服务
3. ✅ 创建数据库
4. ✅ 运行数据库迁移 (Alembic)
5. ✅ 创建测试数据

### 手动部署 (5 分钟)

```bash
# 1. 安装 PostgreSQL 18
brew install postgresql@18
brew services start postgresql@18

# 2. 创建数据库
createdb customer_platform
createdb customer_platform_test

# 3. 验证连接
psql -d customer_platform -c "SELECT version();"

# 4. 运行迁移 (使用 Alembic)
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://localhost/customer_platform"
python -m alembic upgrade head

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

# 4. 运行迁移 (使用 Alembic)
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://user:password@localhost:5432/customer_platform"
python -m alembic upgrade head

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

## 服务器部署：机密注入

### 变量如何进入容器

```
GitHub Actions Secrets → deploy.yml 的 env → ssh 参数（VAR=value bash -s）
                                              └─ 远端 shell 环境
                                                    ↓
服务器 .env（deploy.sh 里 `set -a; source .env`，全部 export）
                                                    ↓
deploy/docker-compose.yml 的 ${VAR} 插值
                                                    ↓
services.app.environment 白名单（只列出的变量才进容器）
```

`environment` 是**白名单**：新变量必须在 `deploy/docker-compose.yml` 里显式列一行，否则 `.env` 或 CI 里写了也进不了容器。

### `.env` 与 CI Secret 的覆盖规则

`source .env` 后执行，**同名变量以 `.env` 为准**。因此：

- 不要把同一个变量同时维护在服务器 `.env` 和 GitHub Secrets（两边不一致时会静默用 `.env` 的旧值）；
- 更新 `.env` 时用「先删后加」而不是直接追加，避免留下两行历史值（`source` 取最后一次赋值）；
- 若 `.env` 是 `deploy.sh init` 自动生成的，检查是否残留 `${...}` 字面量（会把 CI 传入的真值覆盖掉）：
  ```bash
  grep -n '\${' .env
  ```

### CRM 凭据加密密钥 `CRM_CREDENTIAL_KEY`

页面「CRM充值管理 → CRM 配置」保存的 CRM 登录密码用 Fernet 对称加密后落库，密钥只在部署环境：

| 项 | 位置 | 说明 |
|---|---|---|
| 密文 | PG `crm_settings.password_cipher` | 单独泄露无法还原密码 |
| 密钥 | 服务器 `.env` → 容器环境变量 | 不入库、不进镜像、不写日志 |

```bash
# 1. 生成（每个环境一个，staging 与 production 必须不同）
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. 写入服务器 .env（先删旧行再追加；deploy 不会覆盖已存在的 .env）
cd <DEPLOY_DIR>
sed -i '/^CRM_CREDENTIAL_KEY=/d' .env
printf 'CRM_CREDENTIAL_KEY=%s\n' '<生成的密钥>' >> .env
chmod 600 .env

# 3. 重新部署，确认容器内已注入（不打印密钥值）
docker exec customer-platform-app python -c "import os;print('set:', bool(os.environ.get('CRM_CREDENTIAL_KEY')))"
docker compose -f deploy/docker-compose.yml logs app | grep "CRM 运行期配置已加载"
```

注意：

- 未注入时页面仍可保存开关/企业ID/手机号，但**保存密码会被拒绝**（提示未配置 `CRM_CREDENTIAL_KEY`）；
- 更换密钥后旧密文无法解密，配置自动降级为「无密码」并告警，需在页面重新填写一次密码；
- 密钥与数据库备份分开放置，放在同一份备份里等同于未加密；
- 多副本/多 worker 必须使用同一密钥。

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
