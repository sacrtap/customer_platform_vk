#!/bin/bash
# pre-commit-check.sh - 提交前预验证脚本
# 对应 AGENTS.md §5 提交前完整验证清单
# 用法：
#   ./pre-commit-check.sh              # 后端 + 前端 + 部署配置检查
#   ./pre-commit-check.sh --backend-only
#   ./pre-commit-check.sh --frontend-only
#   ./pre-commit-check.sh --no-compose     # 跳过 compose 配置验证

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
NO_COMPOSE=false
for arg in "$@"; do
  case $arg in
    --backend-only)  BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    --no-compose)    NO_COMPOSE=true ;;
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
  echo -n "  [1/5] npm audit... "
  if npm audit --audit-level=high --quiet 2>/dev/null; then
    check_pass "npm audit 通过"
  else
    warn "npm audit 发现漏洞（非阻断，请人工确认）"
  fi

  # 2. ESLint
  echo -n "  [2/5] ESLint... "
  if npm run lint -- --max-warnings 0 2>&1; then
    check_pass "ESLint 通过"
  else
    check_fail "ESLint 失败，请修复后重试"
    EXIT_CODE=1
  fi

  # 3. type-check
  echo -n "  [3/5] vue-tsc type-check... "
  if npx vue-tsc --noEmit 2>&1 | grep -q "error TS"; then
    check_fail "TypeScript 类型检查失败"
    EXIT_CODE=1
  else
    check_pass "TypeScript 类型检查通过"
  fi

  # 4. Vitest 单元测试
  echo -n "  [4/5] Vitest unit tests... "
  if npx vitest run --reporter=verbose 2>&1; then
    check_pass "Vitest 单元测试通过"
  else
    check_fail "Vitest 单元测试失败"
    EXIT_CODE=1
  fi

  # 5. build
  echo -n "  [5/5] npm run build... "
  if npm run build > /dev/null 2>&1; then
    check_pass "前端构建通过"
  else
    check_fail "前端构建失败"
    EXIT_CODE=1
  fi

  cd "$ROOT_DIR"
  echo ""
fi

# ==================== 部署配置检查 ====================
if [ "$NO_COMPOSE" = false ]; then
  echo -e "${BOLD}━━━ 部署配置检查 ━━━${NC}"

  COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.yml"

  if [ ! -f "$COMPOSE_FILE" ]; then
    warn "未找到 deploy/docker-compose.yml，跳过 compose 配置验证"
  else
    # 检测可用的 compose 命令
    COMPOSE_CMD=""
    if command -v docker-compose &> /dev/null; then
      COMPOSE_CMD="docker-compose"
    elif command -v podman-compose &> /dev/null; then
      COMPOSE_CMD="podman-compose"
    elif docker compose version &> /dev/null 2>&1; then
      COMPOSE_CMD="docker compose"
    elif podman compose version &> /dev/null 2>&1; then
      COMPOSE_CMD="podman compose"
    fi

    if [ -z "$COMPOSE_CMD" ]; then
      warn "未检测到 docker-compose / podman-compose，跳过 compose config 验证"
    else
      echo -n "  [1/2] compose config... "
      # compose config 解析 YAML + 变量插值，不需要运行容器或 daemon
      if $COMPOSE_CMD -f "$COMPOSE_FILE" config --quiet 2>&1; then
        check_pass "compose config 验证通过"
      else
        check_fail "compose config 验证失败，请检查 YAML 语法和变量插值"
        EXIT_CODE=1
      fi
    fi

    # 补充检查：检测 ${VAR:?...} 必填变量
    # podman-compose 不强制此语法，但服务器上的 docker-compose 会因缺少值而报错
    # 这些变量可能是有意设为必填的（如 JWT_SECRET），仅需提醒开发者确认 deploy.yml 中已传递
    echo -n "  [2/2] required vars check... "
    required_vars=$(grep -oE '\$\{[A-Za-z_][A-Za-z_0-9]*:\?' "$COMPOSE_FILE" | sed 's/\${//;s/:?//' | sort -u || true)
    if [ -n "$required_vars" ]; then
      warn '发现 ${VAR:?...} 必填变量，请确认 deploy.yml 中已传递:'
      echo "$required_vars" | while read -r var; do
        echo "         - \${${var}:?...} → 部署时必须设置，否则 docker-compose 会报错"
      done
    else
      check_pass '无 ${VAR:?...} 必填变量风险'
    fi
  fi

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
