# GitHub Staging 环境配置指南

> 本文档指导如何在 GitHub 仓库中配置 staging 环境，用于自动化部署流程。

**最后更新**: 2026-05-07

---

## 1. 前置条件

- 拥有 GitHub 仓库的 **Admin** 权限
- 已准备好 staging 服务器信息（SSH 地址、用户名等）
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
| `STAGING_SSH_HOST`             | `staging.yourcompany.com` | staging 服务器 IP 或域名      |
| `STAGING_SSH_USER`             | `deploy`                    | SSH 登录用户名                |
| `STAGING_SSH_PRIVATE_KEY`      | `-----BEGIN OPENSSH...`   | SSH 私钥内容（完整粘贴）      |

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
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 生成 SSH 密钥对（如果没有）
ssh-keygen -t ed25519 -C "deploy@staging" -f ~/.ssh/staging_deploy_key
```

---

## 4. 配置服务器 SSH 服务

本节指导如何在 staging 服务器上配置 SSH 服务，用于 GitHub Actions 安全连接并执行部署。

### 4.1 安装并启动 SSH 服务

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable ssh
sudo systemctl start ssh

# RHEL/CentOS/Fedora
sudo dnf install -y openssh-server
sudo systemctl enable sshd
sudo systemctl start sshd
```

验证 SSH 服务状态：
```bash
sudo systemctl status ssh   # 或 sshd
```

### 4.2 创建专用部署用户

为安全起见，建议创建专用的部署用户，而非使用 root：

```bash
# 创建 deploy 用户
sudo useradd -m -s /bin/bash deploy

# 设置密码（可选，后续将禁用密码登录）
sudo passwd deploy

# 将用户加入 sudo 组（如需执行特权命令）
sudo usermod -aG sudo deploy        # Debian/Ubuntu
# 或
sudo usermod -aG wheel deploy       # RHEL/CentOS/Fedora
```

### 4.3 配置 SSH 密钥认证

#### 4.3.1 在本地生成 SSH 密钥对

```bash
# 生成 Ed25519 密钥（推荐）
ssh-keygen -t ed25519 -C "github-actions-deploy@staging" -f ~/.ssh/staging_deploy_key -N ""

# 或生成 RSA 密钥（兼容旧系统）
ssh-keygen -t rsa -b 4096 -C "github-actions-deploy@staging" -f ~/.ssh/staging_deploy_key -N ""
```

#### 4.3.2 查看公钥内容

```bash
cat ~/.ssh/staging_deploy_key.pub
```

输出类似：
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG... github-actions-deploy@staging
```

#### 4.3.3 在服务器上配置公钥

```bash
# 切换到 deploy 用户
sudo su - deploy

# 创建 .ssh 目录
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 添加公钥到 authorized_keys
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG... github-actions-deploy@staging" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 退出 deploy 用户
exit
```

### 4.4 配置 sshd_config 安全加固

编辑 SSH 服务端配置文件：

```bash
sudo vim /etc/ssh/sshd_config
```

推荐配置：

```bash
# 基础配置
Port 22                          # 可改为其他端口增强安全
Protocol 2                       # 仅使用 SSHv2

# 认证配置
PermitRootLogin no               # 禁止 root 登录
PasswordAuthentication no        # 禁用密码登录（仅允许密钥）
PubkeyAuthentication yes         # 启用公钥认证
AuthorizedKeysFile .ssh/authorized_keys

# 安全限制
MaxAuthTries 3                   # 最大认证尝试次数
LoginGraceTime 60                # 登录超时时间（秒）
PermitEmptyPasswords no          # 禁止空密码
X11Forwarding no                 # 禁用 X11 转发

# 允许的用户/组
AllowUsers deploy                # 仅允许 deploy 用户登录
# 或
AllowGroups sshusers             # 仅允许特定组登录
```

重启 SSH 服务使配置生效：

```bash
sudo systemctl restart ssh   # 或 sshd
```

> **⚠️ 警告**：在禁用密码登录前，务必先验证密钥登录成功，否则可能无法连接服务器！

### 4.5 配置防火墙

```bash
# UFW (Debian/Ubuntu)
sudo ufw allow 22/tcp
sudo ufw status

# firewalld (RHEL/CentOS/Fedora)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload

# 或使用 iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables-save
```

### 4.6 验证 SSH 连接

在本地机器测试连接：

```bash
ssh -i ~/.ssh/staging_deploy_key -o StrictHostKeyChecking=no deploy@<STAGING_SSH_HOST>
```

成功连接后，会显示服务器欢迎信息或 shell 提示符。

### 4.7 配置 sudo 免密码（可选）

如果部署脚本需要执行特权命令，配置 deploy 用户免密码 sudo：

```bash
# 创建 sudoers 配置
sudo visudo -f /etc/sudoers.d/deploy
```

添加以下内容：

```bash
deploy ALL=(ALL) NOPASSWD: ALL
```

保存并验证：

```bash
sudo su - deploy
sudo whoami   # 应输出 root，无需输入密码
```

---

## 5. 配置 SSH 部署密钥

### 5.1 在 staging 服务器上授权

> **注意**：如果已完成第 4 节配置，此步骤已完成，可跳过。

将生成的 SSH **公钥** 添加到 staging 服务器的 `authorized_keys`：

```bash
# 在 staging 服务器上执行
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "<公钥内容>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 5.2 验证 SSH 连接

在本地测试 SSH 连接：

```bash
ssh -i ~/.ssh/staging_deploy_key <STAGING_SSH_USER>@<STAGING_SSH_HOST>
```

---

## 6. 修改 deploy.yml 启用实际部署

### 6.1 取消注释 SSH 部署脚本

打开 `.github/workflows/deploy.yml`，找到 `deploy-staging` job 中的部署步骤，将注释的代码替换为实际执行逻辑：

```yaml
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
    
    # 远程执行部署
    ssh -i ~/.ssh/staging_key -o StrictHostKeyChecking=no ${SSH_USER}@${SSH_HOST} << EOF
      cd /opt/customer_platform
      export IMAGE_TAG=${IMAGE_TAG}
      export DB_USER=${DB_USER}
      export DB_PASSWORD=${DB_PASSWORD}
      export JWT_SECRET=${JWT_SECRET}
      ./deploy/scripts/deploy.sh ${IMAGE_TAG}
    EOF
    
    echo "✅ Staging 部署完成"
```

### 6.2 更新健康检查 URL

找到 `health-check` job，将示例 URL 替换为真实地址：

```yaml
- name: Run health check
  run: |
    echo "🔍 执行健康检查..."
    
    if [ "${{ needs.deploy-staging.result }}" == "success" ]; then
      HEALTH_URL="http://staging.yourcompany.com/health"
    else
      HEALTH_URL="http://production.yourcompany.com/health"
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
curl http://staging.yourcompany.com/health
```

预期返回：
```json
{"status": "ok"}
```

---

## 8. 常见问题

| 问题                                    | 解决方案                                                  |
| --------------------------------------- | --------------------------------------------------------- |
| SSH 连接失败                            | 检查私钥格式是否正确，服务器防火墙是否开放 22 端口        |
| Secret 未生效                           | 确认是在 Environment 级别添加的，不是 Repository 级别     |
| 部署卡在 "Waiting for approval"         | 检查 Environment 是否设置了 Required reviewers，移除或添加审批人 |
| Docker 镜像拉取失败                     | 确认 `ghcr.io` 登录成功，镜像 tag 正确                    |
| 健康检查返回 404                        | 确认 `/health` 端点在后端代码中已实现                     |

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

### 9.3 Production Secrets

在 production 环境的 **Environment secrets** 中添加：

| Secret 名称                  | 说明                        |
| ---------------------------- | --------------------------- |
| `PRODUCTION_SSH_HOST`          | Production 服务器 IP/域名   |
| `PRODUCTION_SSH_USER`          | SSH 登录用户名              |
| `PRODUCTION_SSH_PRIVATE_KEY`   | SSH 私钥内容                |
| `PRODUCTION_DB_USER`           | Production 数据库用户名     |
| `PRODUCTION_DB_PASSWORD`       | Production 数据库密码       |
| `PRODUCTION_JWT_SECRET`        | JWT 签名密钥（32+字符）     |

### 9.4 Production 与 Staging 对比

| 配置项       | staging              | production             |
| ------------ | -------------------- | ---------------------- |
| **环境名称**     | `staging`              | `production`             |
| **Secret 前缀**  | `STAGING_*`            | `PRODUCTION_*`           |
| **审批要求**     | 可选                   | **必须设置 Required reviewers** |
| **部署触发**     | CI 成功后自动 / 手动   | 仅手动触发（需审批）   |
| **Wait timer**   | 0 分钟                 | 建议 5-15 分钟           |

### 9.5 Production 部署流程

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

- [ ] 在 staging 服务器上安装并启动 SSH 服务
- [ ] 创建专用部署用户（deploy）
- [ ] 生成 SSH 密钥对并配置公钥授权
- [ ] 配置 sshd_config 安全加固（禁用 root 登录、密码登录等）
- [ ] 配置防火墙开放 22 端口
- [ ] 本地验证 SSH 连接成功
- [ ] 在 GitHub Settings → Environments 创建 `staging` 环境
- [ ] 添加所有必需的 Environment Secrets（SSH、数据库、JWT）
- [ ] 修改 `deploy.yml` 取消注释部署脚本
- [ ] 更新健康检查 URL 为真实地址
- [ ] 手动触发一次部署并验证成功
- [ ] 访问 staging URL 确认服务正常
