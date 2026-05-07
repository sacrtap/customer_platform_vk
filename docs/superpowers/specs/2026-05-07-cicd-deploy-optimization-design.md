# CI/CD 部署优化设计文档

**日期**: 2026-05-07
**状态**: 已批准
**方案**: 方案 A（轻量修复）

---

## 1. 问题概述

| # | 问题 | 影响 |
|---|------|------|
| 1 | `deploy.sh` 始终本地 build，忽略 CI 构建的 GHCR 镜像 | CI 构建浪费，部署时间长，镜像不一致 |
| 2 | 首次部署时服务器上无代码/无 `.env` | 部署失败 |
| 3 | 健康检查硬编码 `localhost:8000` | 端口变更时检查失败 |
| 4 | `docker-compose.yml` 的 app 服务无 `image` 字段 | compose build 会覆盖已存在的镜像 |

## 2. 环境信息

- **Staging SSH_HOST**: `staging.jiazoushi.com`
- **应用端口**: `8000`
- **首次部署**: 服务器上无代码仓库，需要初始化
- **Cloudflare Tunnel**: 已配置

## 3. 设计方案

### 3.1 `deploy.sh` 镜像逻辑

**新增参数**:
- `--use-remote-image`: 从 GHCR 拉取预构建镜像，跳过本地 build
- `--init`: 首次部署时初始化服务器环境（创建 `.env`）

**镜像拉取逻辑**:
```bash
pull_remote_image() {
    local image_tag=$1
    local image="ghcr.io/${GITHUB_REPOSITORY:-sacrtap/customer_platform_vk}:${image_tag}"
    docker pull "$image"
    docker tag "$image" "customer_platform_app:latest"
}
```

**主流程调整**:
- 如果 `USE_REMOTE_IMAGE=true`，调用 `pull_remote_image`
- 否则保持原有 `build_images` 逻辑（向后兼容）

### 3.2 首次部署初始化

**`--init` 行为**:
1. 检查项目目录是否已存在（`deploy/docker-compose.yml`）
2. 如果不存在，创建 `.env` 文件（含默认值 + 警告提示）
3. 不执行部署流程，仅初始化环境

**.env 模板内容**:
```
DB_USER=customer_platform
DB_PASSWORD=CHANGE_ME_IN_PRODUCTION
POSTGRES_DB=customer_platform
JWT_SECRET=CHANGE_ME_IN_PRODUCTION
WEBHOOK_SECRET=CHANGE_ME_IN_PRODUCTION
APP_ENV=production
DEBUG=false
```

### 3.3 健康检查可配置化

**新增环境变量**:
- `HEALTH_URL`: 默认 `http://localhost:8000/health`
- `HEALTH_MAX_RETRIES`: 默认 `30`
- `HEALTH_RETRY_INTERVAL`: 默认 `2`（秒）

**函数调整**:
- 使用 `curl -sf`（silent + fail on error）
- 循环中使用配置的重试参数

### 3.4 `docker-compose.yml` 调整

**app 服务**:
- 添加 `image: customer_platform_app:latest`
- 保留 `build` 配置（本地开发仍可用）
- compose 行为：如果镜像已存在且无 `--build` 标志，直接使用镜像

### 3.5 `deploy.yml` 调整

**deploy-staging job**:
- SSH 远程命令中传递 `IMAGE_TAG` 环境变量
- 使用 `--use-remote-image` 标志调用 deploy.sh
- 传递 `HEALTH_URL` 环境变量

## 4. 改动文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `deploy/scripts/deploy.sh` | 修改 | 添加 `--use-remote-image`、`--init`、可配置健康检查 |
| `deploy/docker-compose.yml` | 修改 | app 服务添加 `image` 字段 |
| `.github/workflows/deploy.yml` | 修改 | deploy-staging job 传递 `IMAGE_TAG` 和 `HEALTH_URL` |

## 5. 向后兼容性

| 现有用法 | 是否受影响 |
|----------|------------|
| `./deploy/scripts/deploy.sh` | ❌ 不变 |
| `./deploy/scripts/deploy.sh v1.0.0` | ❌ 不变 |
| `./deploy/scripts/deploy.sh --test-data` | ❌ 不变 |
| **新增**: `--use-remote-image` | ✅ 新功能 |
| **新增**: `--init` | ✅ 新功能 |

## 6. 测试策略

1. **本地验证**: `deploy.sh --help` 确认新参数可用
2. **首次部署**: 在 staging 服务器执行 `deploy.sh --init` 确认 `.env` 创建
3. **远程镜像部署**: CI 触发后确认 GHCR 镜像被拉取而非重新构建
4. **健康检查**: 确认环境变量可覆盖默认 URL
