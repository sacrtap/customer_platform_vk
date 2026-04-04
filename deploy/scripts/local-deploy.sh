#!/bin/bash
# 客户运营中台 - 本地 PostgreSQL 一键部署脚本
# 适用于 macOS 开发环境

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
DB_NAME="customer_platform"
DB_TEST_NAME="customer_platform_test"
POSTGRES_VERSION="18"

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

# 检查 Homebrew
check_brew() {
    if ! command -v brew &> /dev/null; then
        error "Homebrew 未安装"
        echo "请先安装 Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    success "Homebrew 已安装"
}

# 检查 PostgreSQL
check_postgres() {
    if command -v psql &> /dev/null; then
        local version=$(psql --version | grep -oE '[0-9]+(\.[0-9]+)?' | head -1)
        local major_version=$(psql --version | grep -oE '[0-9]+' | head -1)
        success "PostgreSQL 已安装 (版本：$version)"
        
        # 检查是否是 Postgres.app
        if pg_config --version 2>/dev/null | grep -q "Postgres.app"; then
            info "检测到 Postgres.app"
        fi
        
        return 0
    fi
    return 1
}

# 安装 PostgreSQL
install_postgres() {
    info "安装 PostgreSQL ${POSTGRES_VERSION}..."
    brew install postgresql@${POSTGRES_VERSION}
    success "PostgreSQL ${POSTGRES_VERSION} 安装完成"
}

# 启动 PostgreSQL 服务
start_postgres() {
    info "检查 PostgreSQL 服务状态..."
    
    # 检查是否已经在运行
    if pg_isready &>/dev/null; then
        success "PostgreSQL 服务已在运行"
        return 0
    fi
    
    # 检查是否是 Postgres.app
    if pg_config --version 2>/dev/null | grep -q "Postgres.app"; then
        info "Postgres.app 已安装，请确保应用已启动"
        if pg_isready &>/dev/null; then
            success "PostgreSQL 服务已启动"
            return 0
        else
            warning "Postgres.app 可能未启动，请打开 Postgres.app 应用"
            sleep 3
        fi
    else
        # Homebrew 安装
        info "启动 PostgreSQL 服务..."
        brew services start postgresql@${POSTGRES_VERSION} 2>/dev/null || \
        brew services start postgresql 2>/dev/null || \
        warning "无法通过 brew services 启动，请手动启动 PostgreSQL"
    fi
    
    # 等待服务启动
    info "等待数据库就绪..."
    for i in {1..10}; do
        if pg_isready &>/dev/null; then
            success "PostgreSQL 服务已就绪"
            return 0
        fi
        sleep 1
    done
    
    warning "数据库可能未就绪，但将继续尝试..."
}

# 创建数据库
create_databases() {
    info "创建数据库..."
    
    # 删除已存在的数据库
    dropdb ${DB_NAME} 2>/dev/null || true
    dropdb ${DB_TEST_NAME} 2>/dev/null || true
    
    # 创建新数据库
    createdb ${DB_NAME}
    createdb ${DB_TEST_NAME}
    
    success "数据库已创建：${DB_NAME}, ${DB_TEST_NAME}"
}

# 验证数据库连接
verify_connection() {
    info "验证数据库连接..."
    
    if psql -d ${DB_NAME} -c "SELECT version();" &>/dev/null; then
        success "数据库连接正常"
    else
        error "数据库连接失败"
        exit 1
    fi
}

# 运行数据库迁移
run_migrations() {
    info "运行数据库迁移 (Alembic)..."
    
    cd backend
    source .venv/bin/activate
    
    export DATABASE_URL="postgresql://localhost/${DB_NAME}"
    
    python -m alembic upgrade head
    
    deactivate
    cd ..
    
    success "数据库迁移完成"
}

# 创建测试数据
create_test_data() {
    info "创建测试数据..."
    
    cd backend
    source .venv/bin/activate
    
    export DATABASE_URL="postgresql://localhost/${DB_NAME}"
    
    python scripts/create_test_data.py
    
    deactivate
    cd ..
    
    success "测试数据已创建"
}

# 显示部署信息
show_info() {
    echo ""
    echo "======================================"
    echo "       ✅ 部署完成!"
    echo "======================================"
    echo ""
    echo "📌 数据库信息:"
    echo "   数据库：${DB_NAME}"
    echo "   测试库：${DB_TEST_NAME}"
    echo "   连接：postgresql://localhost/${DB_NAME}"
    echo ""
    echo "📌 测试数据:"
    echo "   管理员：admin / admin123"
    echo "   测试客户：TEST001 (余额：11000)"
    echo ""
    echo "📌 常用命令:"
    echo "   psql -d ${DB_NAME}              # 连接数据库"
    echo "   brew services stop postgresql@${POSTGRES_VERSION}  # 停止服务"
    echo "   brew services restart postgresql@${POSTGRES_VERSION} # 重启服务"
    echo ""
    echo "📌 下一步:"
    echo "   1. 启动后端服务：cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --reload"
    echo "   2. 启动前端服务：cd frontend && npm run dev"
    echo "   3. 访问应用：http://localhost:5173"
    echo ""
}

# 主函数
main() {
    echo ""
    echo "======================================"
    echo "   客户运营中台 - 本地部署"
    echo "======================================"
    echo ""
    
    # 检查 Homebrew
    check_brew
    
    # 检查/安装 PostgreSQL
    if check_postgres; then
        # PostgreSQL 已安装，检查版本
        local version=$(psql --version | grep -oE '[0-9]+' | head -1)
        if [ "$version" != "${POSTGRES_VERSION}" ]; then
            warning "当前版本为 $version，推荐版本为 ${POSTGRES_VERSION}"
            read -p "是否继续？(y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        install_postgres
    fi
    
    # 启动服务
    start_postgres
    
    # 创建数据库
    create_databases
    
    # 验证连接
    verify_connection
    
    # 运行迁移
    run_migrations
    
    # 创建测试数据
    create_test_data
    
    # 显示信息
    show_info
}

# 显示帮助
show_help() {
    echo "用法：$0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help, -h     显示帮助"
    echo "  --skip-migrate 跳过迁移 (只安装数据库)"
    echo "  --clean        清理数据库后重新部署"
    echo ""
    echo "示例:"
    echo "  $0                    # 完整部署"
    echo "  $0 --clean            # 清理后重新部署"
    echo "  $0 --skip-migrate     # 只安装数据库"
    echo ""
}

# 解析命令行参数
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --clean)
        info "清理数据库..."
        dropdb ${DB_NAME} 2>/dev/null || true
        dropdb ${DB_TEST_NAME} 2>/dev/null || true
        main
        ;;
    --skip-migrate)
        check_brew
        check_postgres || install_postgres
        start_postgres
        create_databases
        verify_connection
        success "数据库安装完成！运行 '$0' 完成迁移。"
        ;;
    *)
        main
        ;;
esac
