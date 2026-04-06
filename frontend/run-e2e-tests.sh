#!/bin/bash
# E2E 测试执行脚本

set -e

FRONTEND_DIR="/Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend"
BACKEND_DIR="/Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend"

echo "=========================================="
echo "客户运营中台 E2E 测试执行"
echo "=========================================="

# 1. 检查并启动后端
echo ""
echo "[1/4] 检查后端服务..."
if ! lsof -ti:8000 > /dev/null; then
    echo "启动后端服务..."
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
    BACKEND_PID=$!
    echo "后端 PID: $BACKEND_PID"
    sleep 5
else
    echo "后端已在运行"
fi

# 2. 检查并启动前端
echo ""
echo "[2/4] 检查前端服务..."
if ! lsof -ti:5173 > /dev/null; then
    echo "启动前端服务..."
    cd "$FRONTEND_DIR"
    npm run dev > frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "前端 PID: $FRONTEND_PID"
    sleep 5
else
    echo "前端已在运行"
fi

# 3. 运行 E2E 测试
echo ""
echo "[3/4] 运行 Playwright E2E 测试..."
cd "$FRONTEND_DIR"

# 检查浏览器是否已安装
if [ ! -d "node_modules/playwright/.local-browsers" ]; then
    echo "安装 Playwright 浏览器..."
    npx playwright install chromium
fi

# 运行所有测试
echo "执行 E2E 测试..."
npx playwright test --reporter=list,html

# 4. 生成测试报告
echo ""
echo "[4/4] 生成测试报告..."
echo ""
echo "=========================================="
echo "测试执行完成！"
echo "=========================================="
echo ""
echo "HTML 报告位置: $FRONTEND_DIR/tests/e2e/playwright-report"
echo "查看报告命令: npx playwright show-report tests/e2e/playwright-report"
echo ""
echo "清理服务..."
if [ -n "$BACKEND_PID" ]; then
    kill $BACKEND_PID 2>/dev/null || true
fi
if [ -n "$FRONTEND_PID" ]; then
    kill $FRONTEND_PID 2>/dev/null || true
fi
echo "完成！"
