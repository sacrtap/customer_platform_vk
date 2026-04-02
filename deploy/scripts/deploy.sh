#!/bin/bash
# 生产环境部署脚本

set -e

echo "🚀 开始部署客户运营中台..."

# 配置变量
PROJECT_NAME="customer_platform"
IMAGE_NAME="${PROJECT_NAME}-app"
CONTAINER_NAME="${PROJECT_NAME}-app"
DB_CONTAINER_NAME="${PROJECT_NAME}-db"
REDIS_CONTAINER_NAME="${PROJECT_NAME}-redis"
NETWORK_NAME="${PROJECT_NAME}_network"
VERSION=${1:-latest}

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v podman &> /dev/null; then
        log_error "Podman 未安装，请先安装 Podman"
        exit 1
    fi
    
    if ! command -v podman-compose &> /dev/null; then
        log_error "podman-compose 未安装，请先安装"
        exit 1
    fi
    
    log_info "依赖检查通过"
}

# 停止旧容器
stop_containers() {
    log_info "停止旧容器..."
    
    podman-compose -f deploy/podman/podman-compose.yaml down 2>/dev/null || true
    
    log_info "旧容器已停止"
}

# 构建镜像
build_images() {
    log_info "构建 Docker 镜像..."
    
    cd backend
    podman build -t ${IMAGE_NAME}:${VERSION} -f ../deploy/podman/Containerfile .
    cd ..
    
    log_info "镜像构建完成：${IMAGE_NAME}:${VERSION}"
}

# 创建网络
create_network() {
    log_info "创建网络..."
    
    podman network inspect ${NETWORK_NAME} &>/dev/null || \
        podman network create ${NETWORK_NAME}
    
    log_info "网络创建完成"
}

# 启动数据库
start_database() {
    log_info "启动数据库..."
    
    podman run -d \
        --name ${DB_CONTAINER_NAME} \
        --network ${NETWORK_NAME} \
        -e POSTGRES_DB=${PROJECT_NAME} \
        -e POSTGRES_USER=${DB_USER:-user} \
        -e POSTGRES_PASSWORD=${DB_PASSWORD:-password} \
        -v ${PROJECT_NAME}_data:/var/lib/postgresql/data \
        -p 5432:5432 \
        --restart unless-stopped \
        postgres:15-alpine
    
    # 等待数据库启动
    log_info "等待数据库启动..."
    sleep 5
    
    log_info "数据库启动完成"
}

# 启动 Redis
start_redis() {
    log_info "启动 Redis..."
    
    podman run -d \
        --name ${REDIS_CONTAINER_NAME} \
        --network ${NETWORK_NAME} \
        -v ${PROJECT_NAME}_redis:/data \
        -p 6379:6379 \
        --restart unless-stopped \
        redis:7-alpine
    
    log_info "Redis 启动完成"
}

# 启动应用
start_app() {
    log_info "启动应用..."
    
    podman run -d \
        --name ${CONTAINER_NAME} \
        --network ${NETWORK_NAME} \
        -e DATABASE_URL=postgresql://${DB_USER:-user}:${DB_PASSWORD:-password}@${DB_CONTAINER_NAME}:5432/${PROJECT_NAME} \
        -e JWT_SECRET=${JWT_SECRET} \
        -e SMTP_PASSWORD=${SMTP_PASSWORD} \
        -v ${PROJECT_NAME}_uploads:/app/uploads \
        -p 8000:8000 \
        --restart unless-stopped \
        ${IMAGE_NAME}:${VERSION}
    
    log_info "应用启动完成"
}

# 运行数据库迁移
run_migrations() {
    log_info "运行数据库迁移..."
    
    podman run --rm \
        --network ${NETWORK_NAME} \
        -e DATABASE_URL=postgresql://${DB_USER:-user}:${DB_PASSWORD:-password}@${DB_CONTAINER_NAME}:5432/${PROJECT_NAME} \
        ${IMAGE_NAME}:${VERSION} \
        python -m alembic upgrade head
    
    log_info "数据库迁移完成"
}

# 健康检查
health_check() {
    log_info "健康检查..."
    
    max_retries=30
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -s http://localhost:8000/health | grep -q '"status":"healthy"'; then
            log_info "健康检查通过"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        log_warn "健康检查失败，重试 ${retry_count}/${max_retries}..."
        sleep 2
    done
    
    log_error "健康检查失败"
    return 1
}

# 清理未使用的资源
cleanup() {
    log_info "清理未使用的资源..."
    
    podman image prune -f
    podman volume prune -f
    
    log_info "清理完成"
}

# 显示部署信息
show_info() {
    echo ""
    echo "========================================"
    log_info "部署完成！"
    echo "========================================"
    echo ""
    echo "应用地址：http://localhost:8000"
    echo "健康检查：http://localhost:8000/health"
    echo ""
    echo "容器状态:"
    podman ps --filter "name=${PROJECT_NAME}"
    echo ""
    echo "查看日志：podman logs -f ${CONTAINER_NAME}"
    echo "停止服务：podman-compose -f deploy/podman/podman-compose.yaml down"
    echo ""
}

# 主函数
main() {
    log_info "开始部署流程..."
    
    check_dependencies
    stop_containers
    build_images
    create_network
    start_database
    start_redis
    run_migrations
    start_app
    health_check
    cleanup
    show_info
    
    log_info "部署成功！"
}

# 执行主函数
main
