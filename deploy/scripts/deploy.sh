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
    
    if command -v podman &> /dev/null; then
        CONTAINER_RUNTIME="podman"
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
    elif command -v docker &> /dev/null; then
        CONTAINER_RUNTIME="docker"
        log_info "检测到 Docker"
    else
        log_error "Podman 或 Docker 未安装，请先安装"
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

# 停止旧容器
stop_containers() {
    log_info "停止旧容器..."
    
    $COMPOSE_CMD -f $COMPOSE_FILE down 2>/dev/null || true
    
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
    local image="ghcr.io/${GITHUB_REPOSITORY:-sacrtap/customer_platform_vk}:${image_tag}"
    log_step "从 GHCR 拉取镜像: ${image}"
    
    $CONTAINER_RUNTIME pull "$image" || {
        log_error "拉取远程镜像失败: ${image}"
        exit 1
    }
    
    # 重新打标签供 compose 使用
    $CONTAINER_RUNTIME tag "$image" "customer_platform_app:latest"
    log_info "远程镜像已拉取并标记为 customer_platform_app:latest"
    
    # 预拉取基础镜像（避免 compose 使用 keychain）
    log_info "预拉取基础镜像..."
    $CONTAINER_RUNTIME pull postgres:18-alpine 2>/dev/null || true
    $CONTAINER_RUNTIME pull redis:7-alpine 2>/dev/null || true
    log_info "基础镜像预拉取完成"
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
    
    # 先单独启动数据库，捕获错误日志
    log_info "启动数据库容器..."
    $COMPOSE_CMD -f $COMPOSE_FILE up -d db 2>&1 || {
        log_error "启动数据库容器失败"
        $COMPOSE_CMD -f $COMPOSE_FILE logs db 2>&1 | tail -30
        exit 1
    }
    
    # 等待数据库初始化
    sleep 5
    
    # 检查容器是否还在运行
    if $COMPOSE_CMD -f $COMPOSE_FILE ps 2>&1 | grep "customer-platform-db" | grep -q "Exit\|Exited"; then
        log_error "数据库容器已退出，打印日志:"
        $COMPOSE_CMD -f $COMPOSE_FILE logs db 2>&1 | tail -50
        exit 1
    fi
    
    log_info "数据库容器运行中，启动迁移服务..."
    
    # 运行迁移服务（compose 会自动等待 db healthcheck 通过）
    $COMPOSE_CMD -f $COMPOSE_FILE up migrate
    
    log_info "数据库迁移完成"
}

# 创建测试数据 (可选)
create_test_data() {
    if [ "${CREATE_TEST_DATA:-false}" = "true" ]; then
        log_step "创建测试数据..."
        $COMPOSE_CMD -f $COMPOSE_FILE up seed
        log_info "测试数据创建完成"
    fi
}

# 启动所有服务
start_services() {
    log_step "启动所有服务..."
    
    $COMPOSE_CMD -f $COMPOSE_FILE up -d app
    
    log_info "服务启动完成"
}

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
    echo "   应用 API: http://localhost:8000"
    echo "   健康检查：http://localhost:8000/health"
    echo "   PostgreSQL: localhost:5432"
    echo "   Redis: localhost:6379"
    echo ""
    echo "📌 测试数据:"
    if [ "${CREATE_TEST_DATA:-false}" = "true" ]; then
        echo "   管理员：admin / admin123"
        echo "   测试客户：TEST001 (余额：11000)"
    else
        echo "   未创建测试数据 (设置 CREATE_TEST_DATA=true 启用)"
    fi
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
    echo "  --test-data      创建测试数据"
    echo "  --cleanup        部署后清理未使用资源"
    echo "  --use-remote-image  从 GHCR 拉取预构建镜像 (跳过本地构建)"
    echo "  --init              初始化服务器环境 (首次部署)"
    echo ""
    echo "示例:"
    echo "  $0                    # 完整部署最新版本"
    echo "  $0 v1.0.0             # 部署指定版本"
    echo "  $0 --test-data        # 部署并创建测试数据"
    echo "  $0 --skip-build       # 跳过构建 (快速部署)"
    echo "  $0 --cleanup v1.0.0   # 部署并清理"
    echo ""
}

# 解析命令行参数
SKIP_BUILD=false
SKIP_MIGRATE=false
CREATE_TEST_DATA=false
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
        --test-data)
            CREATE_TEST_DATA=true
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
export CREATE_TEST_DATA

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
    stop_containers
    
    if [ "$USE_REMOTE_IMAGE" = true ]; then
        pull_remote_image "${VERSION}"
    elif [ "$SKIP_BUILD" = false ]; then
        pull_images
        build_images
    fi
    
    if [ "$SKIP_MIGRATE" = false ]; then
        run_migrations
        create_test_data
    fi
    
    start_services
    health_check
    cleanup
    show_status
    show_info
    
    log_info "🎉 部署成功！"
}

# 执行主函数
main
