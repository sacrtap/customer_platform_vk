#!/bin/bash

# E2E 测试运行脚本
# 自动启动前端和后端服务，运行 Playwright 测试，然后清理服务

set -e

echo "========================================"
echo "  客户运营中台 - E2E 测试运行脚本"
echo "========================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 日志文件
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend-test.log"
FRONTEND_LOG="$LOG_DIR/frontend-test.log"

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}[清理] 停止服务...${NC}"
    
    # 停止前端服务
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        echo "  ✓ 前端服务已停止"
    fi
    
    # 停止后端服务
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        echo "  ✓ 后端服务已停止"
    fi
    
    # 清理端口
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    
    echo -e "${GREEN}[完成] 清理完成${NC}"
}

# 注册清理陷阱
trap cleanup EXIT INT TERM

# 步骤 1: 检查依赖
echo -e "${YELLOW}[步骤 1] 检查依赖...${NC}"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误：Node.js 未安装${NC}"
    exit 1
fi
echo "  ✓ Node.js: $(node --version)"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误：Python3 未安装${NC}"
    exit 1
fi
echo "  ✓ Python: $(python3 --version)"

# 检查 Playwright
if [ ! -f "$FRONTEND_DIR/node_modules/.bin/playwright" ]; then
    echo -e "${YELLOW}  安装 Playwright...${NC}"
    cd "$FRONTEND_DIR"
    npm install
fi
echo "  ✓ Playwright 已安装"

# 步骤 2: 启动后端服务
echo ""
echo -e "${YELLOW}[步骤 2] 启动后端服务...${NC}"

cd "$BACKEND_DIR"

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "  ✓ 虚拟环境已激活"
else
    echo -e "${RED}错误：后端虚拟环境不存在${NC}"
    exit 1
fi

# 启动后端
echo "  启动 Uvicorn 服务器 (端口 8000)..."
python -m uvicorn app.main:app --host=0.0.0.0 --port=8000 > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# 等待后端启动
echo "  等待后端服务启动..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}  后端服务启动超时，查看日志：$BACKEND_LOG${NC}"
        exit 1
    fi
    sleep 1
done

# 步骤 3: 启动前端服务
echo ""
echo -e "${YELLOW}[步骤 3] 启动前端服务...${NC}"

cd "$FRONTEND_DIR"

# 启动前端
echo "  启动 Vite 开发服务器 (端口 5173)..."
npm run dev > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

# 等待前端启动
echo "  等待前端服务启动..."
for i in {1..30}; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ 前端服务已启动 (PID: $FRONTEND_PID)${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}  前端服务启动超时，查看日志：$FRONTEND_LOG${NC}"
        exit 1
    fi
    sleep 1
done

# 步骤 4: 运行 E2E 测试
echo ""
echo -e "${YELLOW}[步骤 4] 运行 E2E 测试...${NC}"
echo ""

cd "$FRONTEND_DIR"

# 运行 Playwright 测试
npx playwright test \
    --project=chromium \
    --reporter=list,html \
    --timeout=30000 \
    --retries=0 \
    --workers=1 \
    "$@"

TEST_EXIT_CODE=$?

# 步骤 5: 显示测试结果
echo ""
echo "========================================"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}  ✓ E2E 测试全部通过${NC}"
else
    echo -e "${RED}  ✗ E2E 测试失败${NC}"
fi
echo "========================================"
echo ""

# 显示报告路径
echo -e "${YELLOW}测试报告:${NC}"
echo "  HTML 报告：$FRONTEND_DIR/playwright-report/index.html"
echo ""
echo "查看报告命令:"
echo "  npx playwright show-report"
echo ""

# 退出码
exit $TEST_EXIT_CODE
