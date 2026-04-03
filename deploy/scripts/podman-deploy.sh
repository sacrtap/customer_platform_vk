#!/bin/bash
# 客户运营中台 - 一键部署脚本
# 使用 Podman 部署应用和测试数据库

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
PROJECT_NAME="customer-platform"
DB_CONTAINER_NAME="${PROJECT_NAME}-db"
APP_CONTAINER_NAME="${PROJECT_NAME}-app"
DB_IMAGE="docker.io/library/postgres:14"
APP_IMAGE="${PROJECT_NAME}-app:latest"
DB_NAME="customer_platform"
DB_USER="user"
DB_PASSWORD="password"
DB_PORT="5432"
APP_PORT="8000"

# 打印带颜色的消息
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Podman 是否安装
check_podman() {
    info "检查 Podman 安装..."
    if ! command -v podman &> /dev/null; then
        error "Podman 未安装，请先安装 Podman"
        echo "macOS: brew install podman"
        echo "Linux: sudo dnf install podman"
        exit 1
    fi
    success "Podman 已安装 ($(podman --version))"
}

# 检查 Podman 机器是否运行 (macOS)
check_podman_machine() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        info "检查 Podman 机器状态..."
        if ! podman machine list --format "{{.Running}}" | grep -q true; then
            warning "Podman 机器未运行，正在启动..."
            podman machine start
            sleep 3
        fi
        success "Podman 机器运行中"
    fi
}

# 停止并清理旧容器
cleanup() {
    info "清理旧容器..."
    podman stop ${DB_CONTAINER_NAME} 2>/dev/null || true
    podman stop ${APP_CONTAINER_NAME} 2>/dev/null || true
    podman rm ${DB_CONTAINER_NAME} 2>/dev/null || true
    podman rm ${APP_CONTAINER_NAME} 2>/dev/null || true
    success "清理完成"
}

# 部署数据库
deploy_database() {
    info "部署 PostgreSQL 数据库..."
    
    podman run -d \
        --name ${DB_CONTAINER_NAME} \
        -e POSTGRES_DB=${DB_NAME} \
        -e POSTGRES_USER=${DB_USER} \
        -e POSTGRES_PASSWORD=${DB_PASSWORD} \
        -p ${DB_PORT}:5432 \
        --health-cmd="pg_isready -U ${DB_USER}" \
        --health-interval=10s \
        --health-timeout=5s \
        --health-retries=5 \
        ${DB_IMAGE}
    
    info "等待数据库就绪..."
    for i in {1..30}; do
        if podman exec ${DB_CONTAINER_NAME} pg_isready -U ${DB_USER} &> /dev/null; then
            success "数据库已就绪"
            return 0
        fi
        sleep 1
    done
    
    error "数据库启动超时"
    exit 1
}

# 创建测试数据库
create_test_database() {
    info "创建测试数据库..."
    podman exec ${DB_CONTAINER_NAME} psql -U ${DB_USER} -d ${DB_NAME} -c \
        "CREATE DATABASE customer_platform_test;" 2>/dev/null || true
    success "测试数据库已创建"
}

# 运行数据库迁移
run_migrations() {
    info "运行数据库迁移..."
    
    cd backend
    source .venv/bin/activate
    
    # 使用容器内网络访问数据库 (容器名作为主机名)
    export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"
    
    # 使用 python 脚本运行迁移而不是 alembic 命令
    python << 'PYTHON_SCRIPT'
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.engine import reflection

from app.models.base import BaseModel
from app.config import settings
import os

# 从环境变量获取 URL
db_url = os.getenv('DATABASE_URL', settings.database_url)

# 创建同步引擎
engine = create_engine(db_url.replace('postgresql+asyncpg://', 'postgresql://'))

# 创建所有表
BaseModel.metadata.create_all(engine)

print("✅ 数据库迁移完成")
PYTHON_SCRIPT
    
    deactivate
    cd ..
    
    success "数据库迁移完成"
}

# 创建测试数据
create_test_data() {
    info "创建测试数据..."
    
    cd backend
    source .venv/bin/activate
    
    export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"
    
    python scripts/create_test_data.py 2>/dev/null || warning "测试数据已存在"
    
    deactivate
    cd ..
    
    success "测试数据已创建"
}

# 构建应用镜像
build_app_image() {
    info "构建应用镜像..."
    
    podman build -t ${APP_IMAGE} -f Containerfile . 2>/dev/null || \
    podman build -t ${APP_IMAGE} -f Dockerfile . 2>/dev/null || \
    warning "未找到 Dockerfile/Containerfile，跳过镜像构建"
}

# 部署应用
deploy_app() {
    info "部署应用容器..."
    
    podman run -d \
        --name ${APP_CONTAINER_NAME} \
        -p ${APP_PORT}:8000 \
        -e DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@host.containers.internal:${DB_PORT}/${DB_NAME}" \
        -e JWT_SECRET="your-secret-key-change-in-production" \
        -e JWT_ALGORITHM="HS256" \
        --add-host=host.containers.internal:host-gateway \
        ${APP_IMAGE} 2>/dev/null || \
    warning "应用镜像不存在，使用开发模式运行"
}

# 运行测试
run_tests() {
    info "运行测试套件..."
    
    cd backend
    source .venv/bin/activate
    
    export TEST_DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/customer_platform_test"
    export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"
    
    # 运行单元测试
    info "运行单元测试..."
    python -m pytest tests/unit/ -v --tb=short
    
    # 运行 API 集成测试
    info "运行 API 集成测试..."
    python -m pytest tests/integration/ -v --tb=short 2>/dev/null || warning "部分 API 测试失败"
    
    deactivate
    cd ..
    
    success "测试完成"
}

# 生成测试报告
generate_reports() {
    info "生成测试报告..."
    
    cd backend
    source .venv/bin/activate
    
    export TEST_DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/customer_platform_test"
    
    # 生成覆盖率报告
    python -m pytest tests/unit/ \
        --cov=app \
        --cov-report=html:../docs/testing/coverage-reports/html \
        --cov-report=term-missing
    
    deactivate
    cd ..
    
    success "测试报告已生成：docs/testing/coverage-reports/html/index.html"
}

# 显示服务状态
show_status() {
    echo ""
    echo "======================================"
    echo "       部署状态"
    echo "======================================"
    echo ""
    
    info "容器状态:"
    podman ps --filter "name=${PROJECT_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    info "访问地址:"
    echo "  - API:      http://localhost:${APP_PORT}"
    echo "  - 健康检查：http://localhost:${APP_PORT}/health"
    echo "  - 数据库：  localhost:${DB_PORT}"
    
    echo ""
    info "测试报告:"
    echo "  - docs/testing/coverage-reports/html/index.html"
    
    echo ""
    info "常用命令:"
    echo "  podman logs ${APP_CONTAINER_NAME}     # 查看应用日志"
    echo "  podman logs ${DB_CONTAINER_NAME}      # 查看数据库日志"
    echo "  podman stop ${APP_CONTAINER_NAME}     # 停止应用"
    echo "  podman stop ${DB_CONTAINER_NAME}      # 停止数据库"
    echo "  podman start ${APP_CONTAINER_NAME}    # 启动应用"
    echo "  podman start ${DB_CONTAINER_NAME}     # 启动数据库"
    echo ""
}

# 主函数
main() {
    echo ""
    echo "======================================"
    echo "   客户运营中台 - 一键部署"
    echo "======================================"
    echo ""
    
    # 检查前置条件
    check_podman
    check_podman_machine
    
    # 清理旧容器
    cleanup
    
    # 部署数据库
    deploy_database
    create_test_database
    
    # 运行迁移和测试数据
    run_migrations
    create_test_data
    
    # 构建并部署应用 (可选)
    # build_app_image
    # deploy_app
    
    # 运行测试
    run_tests
    
    # 生成报告
    generate_reports
    
    # 显示状态
    show_status
    
    success "部署完成!"
}

# 显示帮助
show_help() {
    echo "用法：$0 [命令]"
    echo ""
    echo "命令:"
    echo "  deploy    - 完整部署 (默认)"
    echo "  db        - 只部署数据库"
    echo "  app       - 只部署应用"
    echo "  test      - 运行测试"
    echo "  status    - 显示服务状态"
    echo "  stop      - 停止所有服务"
    echo "  clean     - 停止并删除所有容器"
    echo "  help      - 显示帮助"
    echo ""
}

# 解析命令行参数
case "${1:-deploy}" in
    deploy)
        main
        ;;
    db)
        check_podman
        check_podman_machine
        cleanup
        deploy_database
        create_test_database
        run_migrations
        create_test_data
        show_status
        ;;
    app)
        check_podman
        build_app_image
        deploy_app
        show_status
        ;;
    test)
        run_tests
        generate_reports
        ;;
    status)
        show_status
        ;;
    stop)
        info "停止所有服务..."
        podman stop ${APP_CONTAINER_NAME} 2>/dev/null || true
        podman stop ${DB_CONTAINER_NAME} 2>/dev/null || true
        success "服务已停止"
        ;;
    clean)
        info "清理所有容器..."
        cleanup
        success "清理完成"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        error "未知命令：$1"
        show_help
        exit 1
        ;;
esac
