# GitHub Staging 环境配置指南

> 本文档指导如何在 macOS 服务器上通过 Cloudflare Tunnel 配置 staging 环境，用于自动化部署流程。

**最后更新**: 2026-05-07

---

## 1. 前置条件

- 拥有 GitHub 仓库的 **Admin** 权限
- 一台 macOS 服务器（已安装 Homebrew）
- 一个已接入 Cloudflare 的域名（如 `yourdomain.com`）
- 已准备好数据库凭据

---

## 2. 创建 GitHub Environment

### 2.1 进入环境设置页面

1. 打开 GitHub 仓库页面
2. 点击顶部导航栏的 **Settings**
3. 在左侧边栏找到 **Code and automation** 部分
4. 点击 **Environments**

### 2.2 创建 staging 环境

1. 点击绿色按钮 **New environment**
2. 在输入框中输入环境名称：`staging`
3. 点击 **Configure environment**

### 2.3 配置保护规则（推荐）

在 staging 环境配置页面，可以设置以下规则：

| 规则               | 建议配置        | 说明                          |
| ------------------ | --------------- | ----------------------------- |
| **Required reviewers** | 0-1 人          | staging 可不设审批，production 建议设置 |
| **Wait timer**         | 0 分钟          | 无需等待                      |
| **Deployment branches** | `main` only     | 只允许 main 分支部署到 staging    |

> **提示**：如果不需要审批保护，保持默认设置即可。

---

## 3. 添加 Environment Secrets

在 staging 环境配置页面，向下滚动到 **Environment secrets** 部分，点击 **Add secret**，逐个添加以下密钥：

### 3.1 SSH 连接信息

| Secret 名称                  | 示例值                    | 说明                        |
| ---------------------------- | ------------------------- | --------------------------- |
| `STAGING_SSH_HOST`             | `staging.yourdomain.com`  | Cloudflare Tunnel 子域名    |
| `STAGING_SSH_USER`             | 当前 macOS 用户名           | SSH 登录用户名              |
| `STAGING_SSH_PRIVATE_KEY`      | `-----BEGIN OPENSSH...`   | SSH 私钥内容（完整粘贴）    |

### 3.2 数据库凭据

| Secret 名称                  | 示例值                              | 说明                  |
| ---------------------------- | ----------------------------------- | --------------------- |
| `STAGING_DB_USER`              | `app_user`                            | 数据库用户名          |
| `STAGING_DB_PASSWORD`          | `your-secure-password`                | 数据库密码            |

### 3.3 应用密钥

| Secret 名称                  | 示例值                              | 说明                  |
| ---------------------------- | ----------------------------------- | --------------------- |
| `STAGING_JWT_SECRET`           | `your-random-32-byte-secret-here`   | JWT 签名密钥（32+字符） |

### 3.4 生成安全密钥的方法

```bash
# 生成 JWT Secret（32 字节随机字符串）
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 生成 SSH 密钥对
ssh-keygen -t ed25519 -C "github-actions-deploy@staging" -f ~/.ssh/staging_deploy_key -N ""
```

---

## 4. 配置 macOS SSH 服务

macOS 已内置 SSH 服务（OpenSSH），只需启用远程登录。

### 4.1 启用远程登录

#### 方式一：系统设置（推荐）

1. 打开 **系统设置** → **通用** → **共享**
2. 打开 **远程登录** 开关
3. 记录显示的连接信息，如：`ssh username@Mac-IP`

#### 方式二：命令行

```bash
# 启用 SSH 服务
sudo systemsetup -setremotelogin on

# 验证状态
sudo systemsetup -getremotelogin
```

### 4.2 验证 SSH 服务

```bash
# 本地回环测试
ssh localhost

# 或检查服务状态
sudo launchctl list | grep ssh
```

应能看到 `com.openssh.sshd` 在运行。

### 4.3 配置 SSH 密钥认证

#### 4.3.1 在本地（GitHub Actions 运行环境）生成 SSH 密钥对

```bash
# 生成 Ed25519 密钥（推荐）
ssh-keygen -t ed25519 -C "github-actions-deploy@staging" -f ~/.ssh/staging_deploy_key -N ""
```

#### 4.3.2 查看公钥内容

```bash
cat ~/.ssh/staging_deploy_key.pub
```

输出类似：
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG... github-actions-deploy@staging
```

#### 4.3.3 在 macOS 服务器上配置公钥

```bash
# 在 macOS 服务器上执行
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 将公钥内容追加到 authorized_keys
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG... github-actions-deploy@staging" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### 4.3.4 验证密钥登录

```bash
# 从本地机器测试
ssh -i ~/.ssh/staging_deploy_key <macOS用户名>@localhost
```

### 4.4 SSH 安全加固（可选）

编辑 `/etc/ssh/sshd_config`：

```bash
sudo vim /etc/ssh/sshd_config
```

推荐配置：

```bash
# 禁止 root 登录
PermitRootLogin no

# 仅允许密钥认证
PasswordAuthentication no
PubkeyAuthentication yes

# 安全限制
MaxAuthTries 3
LoginGraceTime 60
PermitEmptyPasswords no
```

重启 SSH 服务：

```bash
sudo launchctl stop com.openssh.sshd
sudo launchctl start com.openssh.sshd
```

> **⚠️ 警告**：在禁用密码登录前，务必先验证密钥登录成功！

---

## 5. 配置 Cloudflare Tunnel

通过 Cloudflare Tunnel 将 SSH 服务安全暴露到公网，无需开放服务器端口。

### 5.1 安装 cloudflared

```bash
# 使用 Homebrew 安装
brew install cloudflared

# 验证安装
cloudflared --version
```

### 5.2 登录 Cloudflare

```bash
cloudflared tunnel login
```

此命令会：
1. 打开浏览器，跳转到 Cloudflare 授权页面
2. 选择你的域名（如 `yourdomain.com`）
3. 授权成功后，在 `~/.cloudflared/` 目录下生成 `cert.pem`

### 5.3 创建 Tunnel

```bash
cloudflared tunnel create staging-tunnel
```

输出示例：
```
Tunnel credentials written to /Users/username/.cloudflared/<TUNNEL_ID>.json
Created tunnel staging-tunnel with id abc12345-6789-def0-1234-567890abcdef
```

**记录 Tunnel ID**（如 `abc12345-6789-def0-1234-567890abcdef`），后续配置需要用到。

### 5.4 配置 DNS 路由

```bash
cloudflared tunnel route dns staging-tunnel staging.yourdomain.com
```

此命令会在 Cloudflare DNS 中创建一条 CNAME 记录，将 `staging.yourdomain.com` 指向 Tunnel。

验证 DNS 记录：
```bash
# 在 Cloudflare Dashboard → DNS → Records 中确认
# Type: CNAME, Name: staging, Target: <TUNNEL_ID>.cfargotunnel.com, Proxy: 已代理
```

### 5.5 创建 Tunnel 配置文件

```bash
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <TUNNEL_ID>
credentials-file: /Users/<你的用户名>/.cloudflared/<TUNNEL_ID>.json

ingress:
  # SSH 流量代理到本地 22 端口
  - hostname: staging.yourdomain.com
    service: ssh://localhost:22
  # 默认拒绝其他流量
  - service: http_status:404
EOF
```

**替换以下内容**：
- `<TUNNEL_ID>`：第 5.3 步创建的 Tunnel ID
- `<你的用户名>`：macOS 当前登录用户名（可用 `whoami` 查看）

### 5.6 验证配置

```bash
cloudflared tunnel ingress validate
```

输出 `OK` 表示配置正确。

### 5.7 启动 Tunnel

#### 测试运行（前台）

```bash
cloudflared tunnel --config ~/.cloudflared/config.yml run staging-tunnel
```

看到 `Route propagator has started` 表示 Tunnel 已连接。

按 `Ctrl+C` 停止。

#### 安装为系统服务（后台自启动）

```bash
cloudflared service install
```

此命令会自动创建 macOS launchd plist 文件，确保 Tunnel 开机自启。

验证服务状态：

```bash
# 检查 launchd 服务
launchctl list | grep cloudflared

# 查看日志
tail -f /var/log/com.cloudflare.cloudflared.log
```

### 5.8 验证 Tunnel 连接

⚠️ **重要**：Cloudflare Tunnel 不支持直接 SSH 连接，必须使用 `cloudflared access ssh` 作为代理。

#### 方式一：使用 cloudflared access 代理（推荐）

```bash
# 在本地机器测试
ssh -i ~/.ssh/staging_deploy_key \
    -o StrictHostKeyChecking=no \
    -o ProxyCommand="cloudflared access ssh --hostname staging.yourdomain.com" \
    <macOS用户名>@staging.yourdomain.com
```

#### 方式二：配置 SSH Config（更方便）

编辑 `~/.ssh/config`，添加以下配置：

```bash
Host staging.yourdomain.com
    HostName staging.yourdomain.com
    User <macOS用户名>
    IdentityFile ~/.ssh/staging_deploy_key
    ProxyCommand cloudflared access ssh --hostname %h
    StrictHostKeyChecking no
```

配置后可以直接使用：
```bash
ssh staging.yourdomain.com
```

成功连接表示 Tunnel 配置完成。

### 5.9 常用 Tunnel 管理命令

```bash
# 查看 Tunnel 状态
cloudflared tunnel info staging-tunnel

# 停止 Tunnel
cloudflared tunnel cleanup staging-tunnel

# 删除 Tunnel（需要重新创建）
cloudflared tunnel delete staging-tunnel

# 查看日志
cloudflared tunnel --config ~/.cloudflared/config.yml run staging-tunnel 2>&1 | tee /tmp/cloudflared.log
```

---

## 6. 修改 deploy.yml 启用实际部署

### 6.1 取消注释 SSH 部署脚本

打开 `.github/workflows/deploy.yml`，找到 `deploy-staging` job 中的部署步骤，将注释的代码替换为实际执行逻辑：

```yaml
- name: Install cloudflared
  run: |
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
    cloudflared --version

- name: Deploy to staging server
  env:
    SSH_PRIVATE_KEY: ${{ secrets.STAGING_SSH_PRIVATE_KEY }}
    SSH_HOST: ${{ secrets.STAGING_SSH_HOST }}
    SSH_USER: ${{ secrets.STAGING_SSH_USER }}
    IMAGE_TAG: ${{ needs.build-and-push.outputs.image_tag }}
    DB_USER: ${{ secrets.STAGING_DB_USER }}
    DB_PASSWORD: ${{ secrets.STAGING_DB_PASSWORD }}
    JWT_SECRET: ${{ secrets.STAGING_JWT_SECRET }}
  run: |
    echo "🚀 部署到 Staging 环境..."
    echo "镜像标签: ${IMAGE_TAG}"

    # 设置 SSH 密钥
    mkdir -p ~/.ssh
    echo "$SSH_PRIVATE_KEY" > ~/.ssh/staging_key
    chmod 600 ~/.ssh/staging_key

    # 通过 Cloudflare Tunnel 远程执行部署
    # ⚠️ 必须使用 cloudflared access 作为 SSH 代理
    ssh -i ~/.ssh/staging_key \
        -o StrictHostKeyChecking=no \
        -o ProxyCommand="cloudflared access ssh --hostname ${SSH_HOST}" \
        ${SSH_USER}@${SSH_HOST} << EOF
      cd ~/customer_platform_vk
      export IMAGE_TAG=${IMAGE_TAG}
      export DB_USER=${DB_USER}
      export DB_PASSWORD=${DB_PASSWORD}
      export JWT_SECRET=${JWT_SECRET}
      ./deploy/scripts/deploy.sh ${IMAGE_TAG}
    EOF

    echo "✅ Staging 部署完成"
```

> **注意**：
> 1. `cd ~/customer_platform_vk` 路径请根据实际项目部署目录调整
> 2. **必须使用 `cloudflared access ssh` 作为代理**，直接 SSH 连接会失败

### 6.2 更新健康检查 URL

找到 `health-check` job，将示例 URL 替换为真实地址：

```yaml
- name: Run health check
  run: |
    echo "🔍 执行健康检查..."

    if [ "${{ needs.deploy-staging.result }}" == "success" ]; then
      HEALTH_URL="http://staging.yourdomain.com/health"
    else
      HEALTH_URL="http://production.yourdomain.com/health"
    fi

    echo "检查地址: ${HEALTH_URL}"

    response=$(curl -s -o /dev/null -w "%{http_code}" ${HEALTH_URL})
    if [ "$response" == "200" ]; then
      echo "✅ 健康检查通过"
    else
      echo "❌ 健康检查失败 (HTTP ${response})"
      exit 1
    fi
```

---

## 7. 验证配置

### 7.1 手动触发部署

1. 进入 GitHub 仓库 → **Actions** 标签
2. 左侧选择 **Deploy** workflow
3. 点击 **Run workflow** 按钮
4. 选择环境：`staging`
5. 点击绿色 **Run workflow** 按钮

### 7.2 检查部署日志

- 在 Actions 页面中点击运行中的 workflow
- 查看 `build-and-push` → `deploy-staging` → `health-check` 各步骤日志
- 确认所有步骤显示 ✅

### 7.3 验证服务状态

部署完成后，访问 staging URL 确认服务正常运行：

```bash
curl http://staging.yourdomain.com/health
```

预期返回：
```json
{"status": "ok"}
```

---

## 8. 常见问题

| 问题                                    | 解决方案                                                  |
| --------------------------------------- | --------------------------------------------------------- |
| `cloudflared tunnel login` 无法打开浏览器 | macOS 无头服务器：使用 `cloudflared login` 手动复制 URL 到本地浏览器 |
| SSH 连接失败（Connection refused）      | 确认 Tunnel 正在运行：`cloudflared tunnel info staging-tunnel` |
| **SSH 连接超时或 `kex_exchange_identification` 错误** | **必须使用 `cloudflared access ssh` 作为代理，不能直接 SSH 连接** |
| Tunnel 启动后立即退出                   | 检查 config.yml 格式，运行 `cloudflared tunnel ingress validate` 验证 |
| Secret 未生效                           | 确认是在 Environment 级别添加的，不是 Repository 级别     |
| 部署卡在 "Waiting for approval"         | 检查 Environment 是否设置了 Required reviewers，移除或添加审批人 |
| Docker 镜像拉取失败                     | 确认 `ghcr.io` 登录成功，镜像 tag 正确                    |
| 健康检查返回 404                        | 确认 `/health` 端点在后端代码中已实现                     |
| cloudflared 服务未自启动                | 检查 launchd plist：`ls ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist` |

---

## 9. 配置 Production 环境

Production 环境配置步骤与 staging **完全相同**，只需注意以下差异：

### 9.1 创建 Production Environment

1. Settings → Environments → **New environment**
2. 命名为：`production`
3. 点击 **Configure environment**

### 9.2 保护规则（必须设置）

| 规则               | 建议配置                  | 说明                          |
| ------------------ | ------------------------- | ----------------------------- |
| **Required reviewers** | **2 人**                    | 部署前需要 2 人审批             |
| **Wait timer**         | 5-15 分钟                 | 审批后等待一段时间再执行        |
| **Deployment branches** | `main` only               | 只允许 main 分支部署            |

### 9.3 Production Tunnel

为 production 创建独立的 Tunnel：

```bash
# 创建 Tunnel
cloudflared tunnel create production-tunnel

# 配置 DNS
cloudflared tunnel route dns production-tunnel production.yourdomain.com
```

配置文件 `~/.cloudflared/production-config.yml`：

```yaml
tunnel: <PRODUCTION_TUNNEL_ID>
credentials-file: /Users/<你的用户名>/.cloudflared/<PRODUCTION_TUNNEL_ID>.json

ingress:
  - hostname: production.yourdomain.com
    service: ssh://localhost:22
  - service: http_status:404
```

### 9.4 Production Secrets

在 production 环境的 **Environment secrets** 中添加：

| Secret 名称                  | 说明                        |
| ---------------------------- | --------------------------- |
| `PRODUCTION_SSH_HOST`          | `production.yourdomain.com` |
| `PRODUCTION_SSH_USER`          | SSH 登录用户名              |
| `PRODUCTION_SSH_PRIVATE_KEY`   | SSH 私钥内容                |
| `PRODUCTION_DB_USER`           | Production 数据库用户名     |
| `PRODUCTION_DB_PASSWORD`       | Production 数据库密码       |
| `PRODUCTION_JWT_SECRET`        | JWT 签名密钥（32+字符）     |

### 9.5 Production 与 Staging 对比

| 配置项       | staging              | production             |
| ------------ | -------------------- | ---------------------- |
| **环境名称**     | `staging`              | `production`             |
| **Tunnel 名称**  | `staging-tunnel`       | `production-tunnel`      |
| **子域名**       | `staging.yourdomain.com` | `production.yourdomain.com` |
| **Secret 前缀**  | `STAGING_*`            | `PRODUCTION_*`           |
| **审批要求**     | 可选                   | **必须设置 Required reviewers** |
| **部署触发**     | CI 成功后自动 / 手动   | 仅手动触发（需审批）   |
| **Wait timer**   | 0 分钟                 | 建议 5-15 分钟           |

### 9.6 Production 部署流程

1. 进入 **Actions** → **Deploy** workflow
2. 点击 **Run workflow**
3. 选择环境：`production`
4. 点击 **Run workflow**
5. workflow 会进入 **"Waiting for approval"** 状态
6. 审批人收到通知后，点击 **Review deployments** → **Approve and deploy**
7. 等待 Wait timer（如配置）后开始部署

---

## 10. 检查清单

完成以下所有步骤后，staging 环境配置完成：

### 服务器端

- [ ] 启用 macOS 远程登录（系统设置 → 共享 → 远程登录）
- [ ] 生成 SSH 密钥对并在服务器上配置公钥
- [ ] 验证 SSH 密钥登录成功（localhost）
- [ ] 安装 cloudflared（`brew install cloudflared`）
- [ ] 登录 Cloudflare（`cloudflared tunnel login`）
- [ ] 创建 Tunnel `staging-tunnel`
- [ ] 配置 DNS 路由 `staging.yourdomain.com`
- [ ] 创建并验证 Tunnel 配置文件（`config.yml`）
- [ ] 安装 cloudflared 系统服务（`cloudflared service install`）
- [ ] 验证 Tunnel 连接成功（使用 `cloudflared access ssh` 代理）

### GitHub 端

- [ ] 在 GitHub Settings → Environments 创建 `staging` 环境
- [ ] 添加所有必需的 Environment Secrets（SSH、数据库、JWT）
- [ ] 修改 `deploy.yml` 取消注释部署脚本
- [ ] 更新健康检查 URL 为真实地址

### 验证

- [ ] 手动触发一次部署并验证成功
- [ ] 访问 staging URL 确认服务正常
