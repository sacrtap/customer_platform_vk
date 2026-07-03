# CI/CD 部署优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 CI/CD 部署流程，支持从 GHCR 拉取预构建镜像、首次部署初始化、可配置健康检查

**Architecture:** 在现有 `deploy.sh` 脚本中添加 `--use-remote-image` 和 `--init` 选项，修改 `docker-compose.yml` 使其支持已存在的镜像，更新 `deploy.yml` 传递必要的环境变量

**Tech Stack:** Bash, Docker Compose, GitHub Actions

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `deploy/scripts/deploy.sh` | 部署脚本，添加新功能选项 |
| `deploy/docker-compose.yml` | 添加 `image` 字段支持预构建镜像 |
| `.github/workflows/deploy.yml` | 传递 `IMAGE_TAG`、`GITHUB_REPOSITORY`、`HEALTH_URL` 到远程服务器 |

---

### Task 1: 修改 `deploy.sh` 添加 `--use-remote-image` 和健康检查可配置化

**Files:**
- Modify: `deploy/scripts/deploy.sh`

- [ ] **Step 1: 添加新的环境变量和参数解析**

在现有参数解析部分（第 252-285 行）添加 `USE_REMOTE_IMAGE` 变量：

```bash
# 在现有变量声明后添加（约第 256 行后）
USE_REMOTE_IMAGE=false

# 在 case 语句中添加（约第 276 行后，--cleanup 之后）
        --use-remote-image)
            USE_REMOTE_IMAGE=true
            shift
            ;;
```

- [ ] **Step 2: 添加 `pull_remote_image` 函数**

在 `build_images()` 函数后添加新函数（约第 113 行后）：

```bash
# 拉取远程镜像
pull_remote_image() {
    local image_tag=$1
    local image="ghcr.io/${GITHUB_REPOSITORY:-sacrtap/customer_platform_vk}:${image_tag}"
    log_step "从 GHCR 拉取镜像: ${image}"
    
    docker pull "$image" || {
        log_error "拉取远程镜像失败: ${image}"
        exit 1
    }
    
    # 重新打标签供 compose 使用
    docker tag "$image" "customer_platform_app:latest"
    log_info "远程镜像已拉取并标记为 customer_platform_app:latest"
}
```

- [ ] **Step 3: 修改健康检查函数为可配置**

替换 `health_check()` 函数（第 158-178 行）：

```bash
# 健康检查
health_check() {
    local health_url="${HEALTH_URL:-http://localhost:8000/health}"
    local max_retries="${HEALTH_MAX_RETRIES:-30}"
    local retry_interval="${HEALTH_RETRY_INTERVAL:-2}"
    
    log_info "健康检查: ${health_url}..."
    
    local retry_count=0
    while [ $retry_count -lt $max_retries ]; do
        if curl -sf "${health_url}" | grep -q '"healthy"'; then
            log_info "健康检查通过"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        log_warn "健康检查失败，重试 ${retry_count}/${max_retries}..."
        sleep "$retry_interval"
    done
    
    log_error "健康检查失败 (${health_url})"
    return 1
}
```

- [ ] **Step 4: 修改主流程支持远程镜像**

修改 `main()` 函数中的构建逻辑（约第 301-304 行）：

```bash
# 将原来的:
# if [ "$SKIP_BUILD" = false ]; then
#     pull_images
#     build_images
# fi

# 替换为:
    if [ "$USE_REMOTE_IMAGE" = true ]; then
        pull_remote_image "${IMAGE_TAG:-latest}"
    elif [ "$SKIP_BUILD" = false ]; then
        pull_images
        build_images
    fi
```

- [ ] **Step 5: 更新 `show_help` 函数**

在 `show_help()` 函数的选项列表中添加新选项（约第 241 行后）：

```bash
    echo "  --use-remote-image  从 GHCR 拉取预构建镜像 (跳过本地构建)"
    echo "  --init              初始化服务器环境 (首次部署)"
```

- [ ] **Step 6: 验证 deploy.sh 语法**

Run: `bash -n deploy/scripts/deploy.sh`
Expected: 无输出（语法正确）

- [ ] **Step 7: 验证帮助信息**

Run: `bash deploy/scripts/deploy.sh --help`
Expected: 输出中包含 `--use-remote-image` 和 `--init` 选项

- [ ] **Step 8: Commit**

```bash
git add deploy/scripts/deploy.sh
git commit -m "feat(deploy): add --use-remote-image and configurable health check"
```

---

### Task 2: 修改 `deploy.sh` 添加 `--init` 首次部署初始化

**Files:**
- Modify: `deploy/scripts/deploy.sh`

- [ ] **Step 1: 添加 `init_server` 函数**

在 `load_env()` 函数后添加（约第 95 行后）：

```bash
# 初始化服务器环境
init_server() {
    log_step "初始化服务器环境..."
    
    # 检查是否已有项目目录
    if [ -f "deploy/docker-compose.yml" ]; then
        log_warn "项目目录已存在，跳过初始化"
        return 0
    fi
    
    # 检查是否在项目根目录
    if [ ! -d "deploy" ]; then
        log_error "请在项目根目录运行此脚本"
        exit 1
    fi
    
    # 创建 .env 文件
    if [ ! -f ".env" ]; then
        log_info "创建 .env 配置文件..."
        cat > .env << 'ENVEOF'
# 数据库配置
DB_USER=customer_platform
DB_PASSWORD=CHANGE_ME_IN_PRODUCTION
POSTGRES_DB=customer_platform

# 安全密钥 (请生成随机密钥)
JWT_SECRET=CHANGE_ME_IN_PRODUCTION
WEBHOOK_SECRET=CHANGE_ME_IN_PRODUCTION

# 应用配置
APP_ENV=production
DEBUG=false

# 可选: SMTP 配置
# SMTP_HOST=smtp.company.com
# SMTP_PORT=587
# SMTP_USERNAME=noreply@company.com
# SMTP_PASSWORD=

# 可选: 外部 API
# EXTERNAL_API_BASE_URL=
# EXTERNAL_API_TOKEN=
ENVEOF
        log_warn "⚠️  请编辑 .env 文件，修改默认配置（特别是密码和密钥）"
        log_warn "生成随机密钥命令: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    fi
    
    log_info "服务器初始化完成"
    log_info "下一步: 编辑 .env 文件，然后运行 ./deploy/scripts/deploy.sh"
}
```

- [ ] **Step 2: 添加 `--init` 参数解析**

在 `case` 语句中添加（在 `--use-remote-image` 之后）：

```bash
        --init)
            init_server
            exit 0
            ;;
```

- [ ] **Step 3: 验证语法和帮助信息**

Run: `bash -n deploy/scripts/deploy.sh`
Expected: 无输出

Run: `bash deploy/scripts/deploy.sh --help`
Expected: 输出中包含 `--init` 选项

- [ ] **Step 4: Commit**

```bash
git add deploy/scripts/deploy.sh
git commit -m "feat(deploy): add --init for first-time server setup"
```

---

### Task 3: 修改 `docker-compose.yml` 添加 `image` 字段

**Files:**
- Modify: `deploy/docker-compose.yml`

- [ ] **Step 1: 为 app 服务添加 `image` 字段**

修改 app 服务配置（在第 44-45 行，`build:` 之前添加）：

```yaml
  # 应用服务
  app:
    image: customer_platform_app:latest
    build:
      context: ../../backend
      dockerfile: ../deploy/docker/Containerfile
```

**说明**: 添加 `image` 字段后，如果镜像已存在，`docker compose up` 会直接使用它而不重新构建。本地开发时仍可运行 `docker compose build` 重新构建。

- [ ] **Step 2: 验证 docker-compose.yml 语法**

Run: `docker compose -f deploy/docker-compose.yml config > /dev/null 2>&1 && echo "OK" || echo "FAIL"`
Expected: `OK`（如果 docker compose 不可用，跳过此步骤）

- [ ] **Step 3: Commit**

```bash
git add deploy/docker-compose.yml
git commit -m "feat(deploy): add image field to app service for pre-built image support"
```

---

### Task 4: 修改 `deploy.yml` 传递必要的环境变量

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: 修改 deploy-staging job 的 SSH 远程命令**

替换第 112-144 行的 `Deploy to staging server` step：

```yaml
      - name: Deploy to staging server
        env:
          SSH_PRIVATE_KEY: ${{ secrets.STAGING_SSH_PRIVATE_KEY }}
          SSH_HOST: ${{ secrets.STAGING_SSH_HOST }}
          SSH_USER: ${{ secrets.STAGING_SSH_USER }}
          IMAGE_TAG: ${{ needs.build-and-push.outputs.image_tag }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          DB_USER: ${{ secrets.STAGING_DB_USER }}
          DB_PASSWORD: ${{ secrets.STAGING_DB_PASSWORD }}
          JWT_SECRET: ${{ secrets.STAGING_JWT_SECRET }}
          HEALTH_URL: "http://localhost:8000/health"
        run: |
          echo "🚀 部署到 Staging 环境..."
          echo "镜像标签: ${IMAGE_TAG}"

          # 设置 SSH 密钥
          mkdir -p ~/.ssh
          echo "$SSH_PRIVATE_KEY" > ~/.ssh/staging_key
          chmod 600 ~/.ssh/staging_key

          # 通过 Cloudflare Tunnel 远程执行部署
          # 使用 cloudflared access 作为 SSH 代理
          ssh -i ~/.ssh/staging_key \
              -o StrictHostKeyChecking=no \
              -o ProxyCommand="cloudflared access ssh --hostname ${SSH_HOST}" \
              ${SSH_USER}@${SSH_HOST} << EOF
            cd ~/customer_platform_vk
            export IMAGE_TAG=${IMAGE_TAG}
            export GITHUB_REPOSITORY=${GITHUB_REPOSITORY}
            export DB_USER=${DB_USER}
            export DB_PASSWORD=${DB_PASSWORD}
            export JWT_SECRET=${JWT_SECRET}
            export HEALTH_URL=${HEALTH_URL}
            ./deploy/scripts/deploy.sh --use-remote-image ${IMAGE_TAG}
          EOF

          echo "✅ Staging 部署完成"
```

**关键变更**:
1. 添加 `GITHUB_REPOSITORY` 环境变量
2. 添加 `HEALTH_URL` 环境变量
3. 在 SSH 命令中 export 这些变量
4. 使用 `--use-remote-image` 标志调用 deploy.sh

- [ ] **Step 2: 同样修改 deploy-production job（可选，保持一致性）**

替换第 168-199 行的 `Deploy to production server` step：

```yaml
      - name: Deploy to production server
        env:
          SSH_PRIVATE_KEY: ${{ secrets.PRODUCTION_SSH_PRIVATE_KEY }}
          SSH_HOST: ${{ secrets.PRODUCTION_SSH_HOST }}
          SSH_USER: ${{ secrets.PRODUCTION_SSH_USER }}
          IMAGE_TAG: ${{ needs.build-and-push.outputs.image_tag }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          DB_USER: ${{ secrets.PRODUCTION_DB_USER }}
          DB_PASSWORD: ${{ secrets.PRODUCTION_DB_PASSWORD }}
          JWT_SECRET: ${{ secrets.PRODUCTION_JWT_SECRET }}
          HEALTH_URL: "http://localhost:8000/health"
        run: |
          echo "🚀 部署到 Production 环境..."
          echo "镜像标签: ${IMAGE_TAG}"

          # 设置 SSH 密钥
          mkdir -p ~/.ssh
          echo "$SSH_PRIVATE_KEY" > ~/.ssh/production_key
          chmod 600 ~/.ssh/production_key

          # 通过 Cloudflare Tunnel 远程执行部署
          ssh -i ~/.ssh/production_key \
              -o StrictHostKeyChecking=no \
              -o ProxyCommand="cloudflared access ssh --hostname ${SSH_HOST}" \
              ${SSH_USER}@${SSH_HOST} << EOF
            cd ~/customer_platform_vk
            export IMAGE_TAG=${IMAGE_TAG}
            export GITHUB_REPOSITORY=${GITHUB_REPOSITORY}
            export DB_USER=${DB_USER}
            export DB_PASSWORD=${DB_PASSWORD}
            export JWT_SECRET=${JWT_SECRET}
            export HEALTH_URL=${HEALTH_URL}
            ./deploy/scripts/deploy.sh --use-remote-image ${IMAGE_TAG}
          EOF

          echo "✅ Production 部署完成"
```

- [ ] **Step 3: 验证 YAML 语法**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && echo "YAML OK"`
Expected: `YAML OK`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat(deploy): pass IMAGE_TAG, GITHUB_REPOSITORY, HEALTH_URL to remote server"
```

---

## 验证清单

完成所有 Task 后，运行以下验证：

```bash
# 1. 验证 deploy.sh 语法
bash -n deploy/scripts/deploy.sh

# 2. 验证帮助信息包含新选项
bash deploy/scripts/deploy.sh --help | grep -E "use-remote-image|init"

# 3. 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && echo "YAML OK"

# 4. 运行 lint 检查
cd backend && flake8 ../deploy/scripts/ --max-line-length=120 2>/dev/null || true  # shell 脚本跳过

# 5. 检查 git 状态
git status
```

## 测试策略

| 测试项 | 方法 | 预期结果 |
|--------|------|----------|
| `--help` 输出 | 本地运行 `deploy.sh --help` | 显示 `--use-remote-image` 和 `--init` |
| `--init` 功能 | 在临时目录运行 `deploy.sh --init` | 创建 `.env` 文件 |
| `--use-remote-image` 语法 | `bash -n deploy.sh` | 无语法错误 |
| docker-compose 配置 | `docker compose config` | 解析成功 |
| deploy.yml YAML | Python yaml.safe_load | 解析成功 |
