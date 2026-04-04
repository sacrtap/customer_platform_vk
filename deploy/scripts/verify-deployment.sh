#!/bin/bash
# 客户运营中台 - Docker 部署验证脚本
# 用于验证部署是否成功

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_FILE="deploy/docker-compose.yml"

# 检测 compose 命令
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose &>/dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}错误：未找到 docker-compose 命令${NC}"
    exit 1
fi

log_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

log_fail() {
    echo -e "${RED}✗${NC} $1"
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 计数器
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# 检查容器状态
check_containers() {
    echo ""
    echo "========================================"
    echo "  1. 检查容器状态"
    echo "========================================"
    
    local containers=$($COMPOSE_CMD -f $COMPOSE_FILE ps --format json 2>/dev/null)
    
    if [ -z "$containers" ]; then
        log_fail "未找到运行的容器"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi
    
    # 检查数据库容器
    if $COMPOSE_CMD -f $COMPOSE_FILE ps db 2>/dev/null | grep -q "running"; then
        log_pass "数据库容器运行中"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        log_fail "数据库容器未运行"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # 检查 Redis 容器
    if $COMPOSE_CMD -f $COMPOSE_FILE ps redis 2>/dev/null | grep -q "running"; then
        log_pass "Redis 容器运行中"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        log_fail "Redis 容器未运行"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # 检查应用容器
    if $COMPOSE_CMD -f $COMPOSE_FILE ps app 2>/dev/null | grep -q "running"; then
        log_pass "应用容器运行中"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        log_fail "应用容器未运行"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# 检查健康端点
check_health_endpoint() {
    echo ""
    echo "========================================"
    echo "  2. 检查健康端点"
    echo "========================================"
    
    local response
    response=$(curl -s -w "\n%{http_code}" http://localhost:8000/health 2>/dev/null)
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ]; then
        log_pass "健康端点响应正常 (HTTP 200)"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        log_fail "健康端点响应异常 (HTTP $http_code)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi
    
    # 检查响应内容
    if echo "$body" | grep -q '"healthy"'; then
        log_pass "健康状态正确"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        log_fail "健康状态异常"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # 显示响应
    echo ""
    log_info "响应内容:"
    echo "$body" | python -m json.tool 2>/dev/null || echo "$body"
}

# 检查数据库连接
check_database() {
    echo ""
    echo "========================================"
    echo "  3. 检查数据库连接"
    echo "========================================"
    
    # 尝试连接数据库
    if command -v psql &> /dev/null; then
        if psql -h localhost -U user -d customer_platform -c "SELECT 1" &>/dev/null; then
            log_pass "数据库连接正常"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            log_fail "数据库连接失败"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            return 1
        fi
        
        # 检查表是否存在
        local table_count=$(psql -h localhost -U user -d customer_platform -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" 2>/dev/null | tr -d ' ')
        
        if [ "$table_count" -gt 10 ]; then
            log_pass "数据库表数量正常 ($table_count 张表)"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            log_warn "数据库表数量异常 ($table_count 张表)"
            WARN_COUNT=$((WARN_COUNT + 1))
        fi
    else
        log_warn "未安装 psql，跳过数据库检查"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi
}

# 检查 Redis 连接
check_redis() {
    echo ""
    echo "========================================"
    echo "  4. 检查 Redis 连接"
    echo "========================================"
    
    if command -v redis-cli &> /dev/null; then
        if redis-cli -h localhost ping 2>/dev/null | grep -q "PONG"; then
            log_pass "Redis 连接正常"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            log_fail "Redis 连接失败"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            return 1
        fi
    else
        log_warn "未安装 redis-cli，跳过 Redis 检查"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi
}

# 检查 API 端点
check_api_endpoints() {
    echo ""
    echo "========================================"
    echo "  5. 检查 API 端点"
    echo "========================================"
    
    # 检查根路径
    local response=$(curl -s http://localhost:8000/ 2>/dev/null)
    if echo "$response" | grep -q "客户运营中台"; then
        log_pass "根路径响应正常"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        log_fail "根路径响应异常"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # 检查 CORS
    local cors=$(curl -s -I -X OPTIONS http://localhost:8000/ \
        -H "Origin: http://localhost:5173" \
        -H "Access-Control-Request-Method: GET" 2>/dev/null)
    if echo "$cors" | grep -qi "Access-Control-Allow"; then
        log_pass "CORS 配置正常"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        log_warn "CORS 配置可能异常"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi
}

# 检查容器日志
check_logs() {
    echo ""
    echo "========================================"
    echo "  6. 检查容器日志"
    echo "========================================"
    
    # 检查应用日志是否有错误
    local error_count=$($COMPOSE_CMD -f $COMPOSE_FILE logs app 2>&1 | grep -ci "error" || echo "0")
    
    if [ "$error_count" -gt 0 ]; then
        log_warn "应用日志中发现 $error_count 个错误"
        WARN_COUNT=$((WARN_COUNT + 1))
    else
        log_pass "应用日志无明显错误"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi
    
    # 检查数据库日志
    local db_errors=$($COMPOSE_CMD -f $COMPOSE_FILE logs db 2>&1 | grep -ci "error" || echo "0")
    
    if [ "$db_errors" -gt 0 ]; then
        log_warn "数据库日志中发现 $db_errors 个错误"
        WARN_COUNT=$((WARN_COUNT + 1))
    else
        log_pass "数据库日志无明显错误"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi
}

# 显示总结
show_summary() {
    echo ""
    echo "========================================"
    echo "  验证总结"
    echo "========================================"
    echo ""
    echo -e "  ${GREEN}通过${NC}: $PASS_COUNT"
    echo -e "  ${RED}失败${NC}: $FAIL_COUNT"
    echo -e "  ${YELLOW}警告${NC}: $WARN_COUNT"
    echo ""
    
    if [ $FAIL_COUNT -gt 0 ]; then
        echo -e "${RED}❌ 验证失败，请检查上述错误${NC}"
        echo ""
        echo "建议操作:"
        echo "  1. 查看应用日志：$COMPOSE_CMD -f $COMPOSE_FILE logs -f app"
        echo "  2. 查看数据库日志：$COMPOSE_CMD -f $COMPOSE_FILE logs -f db"
        echo "  3. 重启服务：$COMPOSE_CMD -f $COMPOSE_FILE restart"
        echo ""
        exit 1
    elif [ $WARN_COUNT -gt 0 ]; then
        echo -e "${YELLOW}⚠️  验证通过但有警告${NC}"
        echo ""
    else
        echo -e "${GREEN}✅ 所有验证通过！${NC}"
        echo ""
    fi
}

# 显示帮助
show_help() {
    echo "用法：$0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help, -h     显示帮助"
    echo "  --quick        快速检查 (只检查容器状态和健康端点)"
    echo "  --verbose      显示详细信息"
    echo ""
    echo "示例:"
    echo "  $0             # 完整验证"
    echo "  $0 --quick     # 快速检查"
    echo ""
}

# 解析参数
QUICK_CHECK=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --quick)
            QUICK_CHECK=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# 主流程
echo ""
echo "========================================"
echo "   客户运营中台 - 部署验证"
echo "========================================"

check_containers
check_health_endpoint

if [ "$QUICK_CHECK" = false ]; then
    check_database
    check_redis
    check_api_endpoints
    check_logs
fi

show_summary
