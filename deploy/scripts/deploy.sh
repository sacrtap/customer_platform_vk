#!/bin/bash
# 客户运营中台 - Docker Compose 生产环境部署脚本

set -e

echo "🚀 开始部署客户运营中台..."

# 配置变量
PROJECT_NAME="customer_platform"
COMPOSE_FILE="deploy/docker-compose.yml"
VERSION=${1:-latest}

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查依赖
CONTAINER_RUNTIME=""

check_dependencies() {
    log_info "检查依赖..."
    
    # 非交互式 shell（如 SSH 远程执行）PATH 可能不完整
    # 扩展 PATH 包含容器运行时常见安装路径（含 Homebrew Apple Silicon 路径和自定义 podman 路径）
    export PATH="$PATH:/usr/bin:/usr/local/bin:/usr/libexec:/usr/libexec/podman:/opt/homebrew/bin:/opt/homebrew/sbin:/opt/podman/bin"
    
    # 检测容器运行时：不仅检查命令存在，还要验证 daemon 可用
    detect_runtime() {
        local runtime=$1
        local cmd_path
        
        # 查找命令路径
        cmd_path=$(command -v "$runtime" 2>/dev/null) || return 1
        
        # 验证 daemon 是否可用
        if [ "$runtime" = "podman" ]; then
            # Podman 无 daemon 模式，只需验证命令可执行
            if [ -x "$cmd_path" ]; then
                CONTAINER_RUNTIME="podman"
                return 0
            fi
        elif [ "$runtime" = "docker" ]; then
            # Docker 需要 daemon 运行
            if docker info &>/dev/null; then
                CONTAINER_RUNTIME="docker"
                return 0
            fi
        fi
        return 1
    }
    
    # Podman 优先
    if detect_runtime podman; then
        log_info "检测到 Podman"
        
        # 配置 Podman 使用文件式认证（避免 macOS keychain 问题）
        if [ "$(uname)" = "Darwin" ]; then
            export REGISTRY_AUTH_FILE="${HOME}/.config/containers/auth.json"
            mkdir -p "$(dirname "$REGISTRY_AUTH_FILE")"
            if [ ! -f "$REGISTRY_AUTH_FILE" ]; then
                echo '{"auths":{}}' > "$REGISTRY_AUTH_FILE"
            fi
            log_info "已配置 Podman 使用文件式认证"
        fi
    elif detect_runtime docker; then
        log_info "检测到 Docker"
    else
        log_error "Podman 或 Docker 未安装或 daemon 未运行，请先安装并启动"
        exit 1
    fi
    
    # 检查 compose 命令
    if [ "$CONTAINER_RUNTIME" = "podman" ]; then
        # Podman 优先使用 podman compose 或 podman-compose
        if podman compose version &>/dev/null; then
            COMPOSE_CMD="podman compose"
        elif command -v podman-compose &> /dev/null; then
            COMPOSE_CMD="podman-compose"
        else
            log_error "podman compose 或 podman-compose 未安装"
            log_error "请安装: dnf install podman-compose 或 pip install podman-compose"
            exit 1
        fi
    elif [ "$CONTAINER_RUNTIME" = "docker" ]; then
        # Docker 使用 docker-compose 或 docker compose
        if command -v docker-compose &> /dev/null; then
            COMPOSE_CMD="docker-compose"
        elif docker compose version &>/dev/null; then
            COMPOSE_CMD="docker compose"
        else
            log_error "docker-compose 未安装"
            exit 1
        fi
    fi
    
    log_info "使用 compose 命令：$COMPOSE_CMD"
    log_info "依赖检查通过"
}

# 检查配置文件
check_config() {
    log_info "检查配置文件..."
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "未找到 $COMPOSE_FILE"
        exit 1
    fi
    
    if [ ! -f "deploy/docker/Containerfile" ]; then
        log_error "未找到 deploy/docker/Containerfile"
        exit 1
    fi
    
    log_info "配置文件检查通过"
}

# 加载环境变量
load_env() {
    log_info "加载环境变量..."
    
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
        log_info "已加载 .env 文件"
    else
        log_warn "未找到 .env 文件，使用默认配置"
    fi
}
# 部署前检查
pre_deploy_check() {
    log_step "部署前检查..."
    
    # 1. 检查磁盘空间（至少需要 2GB 可用空间）
    log_info "检查磁盘空间..."
    # 检查根目录磁盘空间（兼容 Docker 和 Podman）
    local available_space=$(df -h / 2>/dev/null | tail -1 | awk '{print $4}' | grep -oE '[0-9]+')
    if [ -z "$available_space" ]; then
        log_warn "无法检测磁盘空间，跳过检查"
    elif [ "$available_space" -lt 2 ]; then
        log_error "磁盘空间不足：${available_space}G（需要至少 2G）"
        return 1
    else
        log_info "磁盘空间充足：${available_space}G"
    fi
    
    # 2. 检查是否有其他部署进程在运行
    log_info "检查部署进程..."
    local current_pid=$$
    # 使用 [d]eploy.sh 避免 grep 匹配自身，排除 bash -s（SSH heredoc 进程）
    local deploy_pids=$(ps aux | grep "[d]eploy.sh" | grep -v "bash -s" | awk '{print $2}' | grep -v "^${current_pid}$" || true)
    if [ -n "$deploy_pids" ]; then
        log_warn "发现其他部署进程：$deploy_pids"
        log_info "尝试清理残留进程..."
        for pid in $deploy_pids; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                sleep 1
                # 如果进程还在，强制杀死
                if kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid" 2>/dev/null || true
                fi
            fi
        done
        log_info "残留进程已清理"
    fi
    log_info "无其他部署进程"
    
    # 3. 检查 Docker/Podman 服务状态
    log_info "检查容器运行时..."
    if ! $CONTAINER_RUNTIME info > /dev/null 2>&1; then
        log_error "$CONTAINER_RUNTIME 服务未运行或无法访问"
        return 1
    fi
    log_info "$CONTAINER_RUNTIME 服务正常"
    
    
    log_info "部署前检查完成"
}


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

JWT_SECRET=${JWT_SECRET}
WEBHOOK_SECRET=${WEBHOOK_SECRET:-dev-webhook-secret-change-in-production}
EXTERNAL_MYSQL_URL=${EXTERNAL_MYSQL_URL}
# EXTERNAL_API_BASE_URL=
# EXTERNAL_API_TOKEN=
ENVEOF
        log_warn "⚠️  请编辑 .env 文件，修改默认配置（特别是密码和密钥）"
        log_warn "生成随机密钥命令: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    fi
    
    log_info "服务器初始化完成"
    log_info "下一步: 编辑 .env 文件，然后运行 ./deploy/scripts/deploy.sh"
}

# 停止旧容器
stop_containers() {
    log_info "停止旧容器..."
    
    # 1. 先停止所有服务（优雅关闭，等待 10 秒）
    log_info "执行 compose stop..."
    $COMPOSE_CMD -f $COMPOSE_FILE stop -t 10 || true
    
    # 2. 等待容器完全停止
    sleep 3
    
    # 3. 移除所有容器（保留数据卷，避免数据丢失）
    log_info "执行 compose down..."
    down_output=$($COMPOSE_CMD -f $COMPOSE_FILE down --remove-orphans 2>&1) || {
        log_warn "compose down 返回非零退出码（可能无容器可停止）"
        log_warn "down 输出: ${down_output}"
    }
    
    # 4. 强制移除所有 customer-platform- 前缀的容器
    # 使用循环重试：每次尝试删除所有残留容器，直到全部清除或达到最大重试次数
    # 这样可以处理未知名称的孤儿容器和复杂的依赖关系
    log_info "检查并清理所有残留容器..."
    max_attempts=5
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        remaining=$($CONTAINER_RUNTIME ps -a --format "{{.Names}}" | grep "^customer-platform-" || true)
        if [ -z "$remaining" ]; then
            log_info "所有残留容器已清理"
            break
        fi
        
        attempt=$((attempt + 1))
        log_info "第 ${attempt}/${max_attempts} 轮清理，发现残留容器:"
        echo "$remaining" | while read -r c; do log_info "  - $c"; done
        
        # 尝试删除所有残留容器（忽略错误，继续下一轮）
        echo "$remaining" | while read -r c; do
            $CONTAINER_RUNTIME rm -f "$c" 2>&1 || true
        done
        
        sleep 2
    done
    
    # 最终检查
    final_remaining=$($CONTAINER_RUNTIME ps -a --format "{{.Names}}" | grep "^customer-platform-" || true)
    if [ -n "$final_remaining" ]; then
        log_error "经过 ${max_attempts} 轮尝试后仍有容器无法删除:"
        echo "$final_remaining"
        return 1
    fi
    
    log_info "旧容器已停止"
}

# 构建镜像
build_images() {
    log_step "构建 Docker 镜像..."
    
    $COMPOSE_CMD -f $COMPOSE_FILE build --no-cache
    
    log_info "镜像构建完成"
}

# 拉取远程镜像
pull_remote_image() {
    local image_tag=$1
    local backend_image="ghcr.io/${GITHUB_REPOSITORY:-sacrtap/customer_platform_vk}:${image_tag}"
    local frontend_image="ghcr.io/${GITHUB_REPOSITORY:-sacrtap/customer_platform_vk}-frontend:${image_tag}"
    
    log_step "从 GHCR 拉取后端镜像: ${backend_image}"
    
    $CONTAINER_RUNTIME pull "$backend_image" || {
        log_error "拉取后端镜像失败: ${backend_image}"
        exit 1
    }
    
    # 重新打标签供 compose 使用
    $CONTAINER_RUNTIME tag "$backend_image" "customer_platform_app:latest"
    log_info "后端镜像已拉取并标记为 customer_platform_app:latest"
    
    log_step "从 GHCR 拉取前端镜像: ${frontend_image}"
    
    $CONTAINER_RUNTIME pull "$frontend_image" || {
        log_error "拉取前端镜像失败: ${frontend_image}"
        exit 1
    }
    
    # 重新打标签供 compose 使用
    $CONTAINER_RUNTIME tag "$frontend_image" "customer_platform_frontend:latest"
    log_info "前端镜像已拉取并标记为 customer_platform_frontend:latest"
}

# 拉取基础镜像
pull_images() {
    log_info "拉取基础镜像..."
    
    $COMPOSE_CMD -f $COMPOSE_FILE pull db redis
    
    log_info "基础镜像拉取完成"
}

# 运行数据库迁移
run_migrations() {
    log_step "运行数据库迁移..."
    
    # 迁移前强制清理所有相关容器（避免名称冲突）
    # 注意：只删除容器，不删除数据卷，数据不会丢失
    log_info "清理所有相关容器..."
    # 按依赖逆序删除：先删除依赖者，再删除被依赖者
    # 依赖链：nginx→app→db,redis；seed→migrate→app
    # 删除顺序：nginx → seed → migrate → app → db → redis
    local containers_in_order=(
        "customer-platform-nginx"
        "customer-platform-seed"
        "customer-platform-migrate"
        "customer-platform-app"
        "customer-platform-db"
        "customer-platform-redis"
    )
    for container_name in "${containers_in_order[@]}"; do
        if $CONTAINER_RUNTIME ps -a --format "{{.Names}}" | grep -q "^${container_name}$"; then
            log_info "移除容器 ${container_name}..."
            # 先尝试 stop
            $CONTAINER_RUNTIME stop "$container_name" 2>&1 || true
            sleep 1
            # 再尝试 rm（用 if 避免 set -e 导致脚本退出）
            if ! $CONTAINER_RUNTIME rm -f "$container_name" 2>&1; then
                log_warn "容器 ${container_name} 删除失败，等待 3 秒后重试..."
                sleep 3
                if ! $CONTAINER_RUNTIME rm -f "$container_name" 2>&1; then
                    log_error "容器 ${container_name} 仍然无法删除"
                    log_error "请手动登录服务器执行: podman rm -f ${container_name}"
                    return 1
                fi
            fi
            log_info "容器 ${container_name} 已移除"
        fi
    done
    
    # 清理残留网络（避免 label 不匹配导致 compose up 失败）
    # docker-compose 会按 <project>_<network> 命名网络，若旧网络 label 不匹配会报错
    local network_name="customer_platform_vk_customer-platform-network"
    if $CONTAINER_RUNTIME network ls --format "{{.Name}}" | grep -q "^${network_name}$"; then
        log_info "移除残留网络 ${network_name}..."
        if ! $CONTAINER_RUNTIME network rm "$network_name" 2>&1; then
            log_warn "网络 ${network_name} 删除失败，可能被其他容器占用"
            log_warn "尝试强制删除..."
            # 强制删除（如果有容器连接会失败，但上面已清理所有容器）
            $CONTAINER_RUNTIME network rm -f "$network_name" 2>&1 || true
        fi
        log_info "残留网络已清理"
    fi
    
    
    # 运行迁移服务（compose 会自动启动依赖的 db 服务并等待 healthcheck）
    if ! $COMPOSE_CMD -f $COMPOSE_FILE up migrate; then
        log_error "数据库迁移失败！"
        return 1
    fi
    
    log_info "数据库迁移完成"
    
    # 运行种子数据（幂等，已存在则跳过）
    log_step "初始化种子数据..."
    if ! $COMPOSE_CMD -f $COMPOSE_FILE up seed; then
        log_error "种子数据初始化失败！"
        return 1
    fi
    log_info "种子数据初始化完成"
}

# 启动所有服务
start_services() {
    log_step "启动所有服务..."
    
    $COMPOSE_CMD -f $COMPOSE_FILE up -d app nginx
    
    log_info "服务启动完成"
}

# 健康检查
health_check() {
    local health_url="${HEALTH_URL:-http://localhost:8082/health}"
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
# 部署后验证
post_deploy_verify() {
    log_step "部署后验证..."
    
    # 1. 验证所有服务都在运行
    log_info "检查服务运行状态..."
    local services=("customer-platform-db" "customer-platform-redis" "customer-platform-app" "customer-platform-nginx")
    for service in "${services[@]}"; do
        if ! $CONTAINER_RUNTIME ps --format "{{.Names}}" | grep -q "^${service}$"; then
            log_error "服务 ${service} 未运行"
            return 1
        fi
        log_info "✓ ${service} 运行正常"
    done
    
    # 2. 验证数据库连接
    log_info "检查数据库连接..."
    if ! $CONTAINER_RUNTIME exec customer-platform-db pg_isready -U ${DB_USER:-user} > /dev/null 2>&1; then
        log_error "数据库连接失败"
        return 1
    fi
    log_info "✓ 数据库连接正常"
    
    # 3. 验证应用健康端点
    log_info "检查应用健康端点..."
    local max_retries=10
    local retry=0
    while [ $retry -lt $max_retries ]; do
        if curl -f -s http://localhost:8082/health > /dev/null 2>&1; then
            log_info "✓ 应用健康端点响应正常"
            break
        fi
        retry=$((retry + 1))
        if [ $retry -eq $max_retries ]; then
            log_error "应用健康端点无响应（重试 ${max_retries} 次）"
            return 1
        fi
        sleep 3
    done
    
    # 4. 验证前端可访问
    log_info "检查前端访问..."
    if ! curl -f -s http://localhost:8082 > /dev/null 2>&1; then
        log_error "前端无法访问"
        return 1
    fi
    log_info "✓ 前端访问正常"
    
    log_info "部署后验证完成"
}


# 显示服务状态
show_status() {
    echo ""
    echo "========================================"
    log_info "服务状态:"
    echo "========================================"
    $COMPOSE_CMD -f $COMPOSE_FILE ps
    echo ""
}

# 显示部署信息
show_info() {
    echo ""
    echo "========================================"
    log_info "✅ 部署完成！"
    echo "========================================"
    echo ""
    echo "📌 服务地址:"
    echo "   应用前端: http://localhost:8082"
    echo "   应用 API: http://localhost:8082/api"
    echo "   健康检查：http://localhost:8082/health"
    echo "   PostgreSQL: localhost:5432"
    echo "   Redis: localhost:6379"
    echo ""
    echo "📌 种子数据:"
    echo "   首次部署后自动创建 admin 账号 (admin/admin123)"
    echo "   如需重置：SSH 运行 python scripts/seed.py --reset"
    echo ""
    echo "📌 常用命令:"
    echo "   查看日志：$COMPOSE_CMD -f $COMPOSE_FILE logs -f app"
    echo "   查看状态：$COMPOSE_CMD -f $COMPOSE_FILE ps"
    echo "   重启服务：$COMPOSE_CMD -f $COMPOSE_FILE restart"
    echo "   停止服务：$COMPOSE_CMD -f $COMPOSE_FILE down"
    echo "   清理资源：$COMPOSE_CMD -f $COMPOSE_FILE down -v"
    echo ""
}

# 清理未使用的资源
cleanup() {
    if [ "${CLEANUP:-false}" = "true" ]; then
        log_info "清理未使用的资源..."
        
        docker image prune -f 2>/dev/null || podman image prune -f 2>/dev/null || true
        docker volume prune -f 2>/dev/null || podman volume prune -f 2>/dev/null || true
        
        log_info "清理完成"
    fi
}

# 显示帮助
show_help() {
    echo "用法：$0 [选项] [版本]"
    echo ""
    echo "选项:"
    echo "  --help, -h       显示帮助"
    echo "  --skip-build     跳过镜像构建 (使用已有镜像)"
    echo "  --skip-migrate   跳过数据库迁移"
    echo "  --cleanup        部署后清理未使用资源"
    echo "  --use-remote-image  从 GHCR 拉取预构建镜像 (跳过本地构建)"
    echo "  --init              初始化服务器环境 (首次部署)"
    echo ""
    echo "示例:"
    echo "  $0                    # 完整部署最新版本"
    echo "  $0 v1.0.0             # 部署指定版本"
    echo "  $0 --skip-build       # 跳过构建 (快速部署)"
    echo "  $0 --cleanup v1.0.0   # 部署并清理"
    echo ""
}

# 解析命令行参数
SKIP_BUILD=false
SKIP_MIGRATE=false
CLEANUP=false
USE_REMOTE_IMAGE=false
INIT_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-migrate)
            SKIP_MIGRATE=true
            shift
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --use-remote-image)
            USE_REMOTE_IMAGE=true
            shift
            ;;
        --init)
            INIT_MODE=true
            shift
            ;;
        *)
            VERSION=$1
            shift
            ;;
    esac
done

# 导出环境变量供 compose 使用
export VERSION

# 主函数
main() {
    # 如果是初始化模式，只运行 init_server 然后退出
    if [ "$INIT_MODE" = true ]; then
        init_server
        exit 0
    fi
    
    log_info "开始部署流程..."
    log_info "部署版本：$VERSION"
    
    check_dependencies
    check_config
    load_env
    pre_deploy_check
    stop_containers
    
    if [ "$USE_REMOTE_IMAGE" = true ]; then
        pull_remote_image "${VERSION}"
    elif [ "$SKIP_BUILD" = false ]; then
        pull_images
        build_images
    fi
    
    if [ "$SKIP_MIGRATE" = false ]; then
        run_migrations
    fi
    
    start_services
    health_check
    post_deploy_verify
    cleanup
    show_status
    show_info
    
    log_info "🎉 部署成功！"
}

# 执行主函数
main
