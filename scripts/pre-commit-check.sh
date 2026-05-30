#!/bin/bash
# pre-commit-check.sh - 提交前预验证脚本
# 对应 AGENTS.md §5 提交前完整验证清单
# 用法：
#   ./pre-commit-check.sh              # 后端 + 前端检查
#   ./pre-commit-check.sh --backend-only
#   ./pre-commit-check.sh --frontend-only

set -e

# 获取项目根目录（兼容 pre-commit 环境）
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$GIT_ROOT" ]; then
  ROOT_DIR="$GIT_ROOT"
else
  ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

check_pass() { echo -e "${GREEN}✅ $1${NC}"; }
check_fail() { echo -e "${RED}❌ $1${NC}"; }
warn()     { echo -e "${YELLOW}⚠️  $1${NC}"; }

# 参数解析
BACKEND_ONLY=false
FRONTEND_ONLY=false
for arg in "$@"; do
  case $arg in
    --backend-only)  BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
  esac
done

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  提交前预验证 (pre-commit-check)${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""

EXIT_CODE=0

# ==================== 后端检查 ====================
if [ "$FRONTEND_ONLY" = false ]; then
  echo -e "${BOLD}━━━ 后端检查 ━━━${NC}"

  # 0. 环境检查
  if [ ! -d "$BACKEND_DIR/.venv" ]; then
    check_fail "backend/.venv 不存在，请先运行: python -m venv backend/.venv"
    exit 1
  fi

  cd "$BACKEND_DIR"
  source .venv/bin/activate

  # 1. ruff check
  echo -n "  [1/4] ruff check... "
  if ruff check app/ tests/ --quiet 2>&1; then
    check_pass "ruff check 通过"
  else
    check_fail "ruff check 失败，请修复后重试"
    EXIT_CODE=1
  fi

  # 2. ruff format --check
  echo -n "  [2/4] ruff format... "
  if ruff format app/ tests/ --check --quiet 2>/dev/null; then
    check_pass "ruff format 通过"
  else
    check_fail "ruff format 失败，请运行: ruff format app/ tests/"
    EXIT_CODE=1
  fi

  # 3. safety check（可选，非阻断）
  echo -n "  [3/4] safety check... "
  if command -v safety &> /dev/null; then
    if safety check -r requirements.txt --quiet 2>/dev/null; then
      check_pass "safety check 通过"
    else
      warn "safety check 发现漏洞（非阻断，请人工确认）"
    fi
  else
    warn "safety 未安装，跳过（pip install safety）"
  fi

  # 4. pytest
  echo -n "  [4/4] pytest unit tests... "
  if pytest tests/unit/ -n auto --tb=short -q 2>&1; then
    check_pass "单元测试通过"
  else
    check_fail "单元测试失败"
    EXIT_CODE=1
  fi

  cd "$ROOT_DIR"
  echo ""
fi

# ==================== 前端检查 ====================
if [ "$BACKEND_ONLY" = false ]; then
  echo -e "${BOLD}━━━ 前端检查 ━━━${NC}"

  # 0. 环境检查
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    check_fail "frontend/node_modules 不存在，请先运行: cd frontend && npm install"
    exit 1
  fi

  cd "$FRONTEND_DIR"

  # 1. npm audit（非阻断）
  echo -n "  [1/3] npm audit... "
  if npm audit --audit-level=high --quiet 2>/dev/null; then
    check_pass "npm audit 通过"
  else
    warn "npm audit 发现漏洞（非阻断，请人工确认）"
  fi

  # 2. type-check
  echo -n "  [2/3] vue-tsc type-check... "
  if npx vue-tsc --noEmit 2>&1 | grep -q "error TS"; then
    check_fail "TypeScript 类型检查失败"
    EXIT_CODE=1
  else
    check_pass "TypeScript 类型检查通过"
  fi

  # 3. build
  echo -n "  [3/3] npm run build... "
  if npm run build > /dev/null 2>&1; then
    check_pass "前端构建通过"
  else
    check_fail "前端构建失败"
    EXIT_CODE=1
  fi

  cd "$ROOT_DIR"
  echo ""
fi

# ==================== 总结 ====================
if [ $EXIT_CODE -eq 0 ]; then
  echo -e "${GREEN}${BOLD}========================================${NC}"
  echo -e "${GREEN}${BOLD}  ✅ 全部检查通过，可以安全提交！${NC}"
  echo -e "${GREEN}${BOLD}========================================${NC}"
else
  echo -e "${RED}${BOLD}========================================${NC}"
  echo -e "${RED}${BOLD}  ❌ 部分检查失败，请修复后再提交！${NC}"
  echo -e "${RED}${BOLD}========================================${NC}"
fi

exit $EXIT_CODE
