#!/bin/bash
# better-harness-inspector.sh - Better Harness Inspector 运行脚本（OMP 会话感知）
# 作用：以 pi adapter 读取 OMP(~/.omp/agent) 会话证据，生成 Harness Inspector 页面并自动打开
# 前置：@qoder-ai/better-harness >= 0.7.0-alpha1（含 OMP 支持；官方 npm latest=0.6.6 不含）
# 用法：
#   ./scripts/better-harness-inspector.sh     # 当前仓库根目录，最近 15 天（含今天），全部宿主
# 说明：
#   - --workspace 自动探测为当前仓库根目录，无需指定
#   - --platform all 扫描全部支持宿主（pi/codex/claude/qwen 等），无数据的宿主显示 no-evidence 属正常
#   - 输出到 docs/better-harness/better-harness-inspector/inspector.html 并自动打开

set -euo pipefail

# 项目根目录（优先 git 根，回退到脚本所在目录的上一级）
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT_DIR" ]; then
  ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
fi

# OMP agent 目录：优先尊重外部已设置的变量，否则默认 ~/.omp/agent
# 注意：必须为绝对路径（shell 前缀赋值中 ~ 不展开，pi adapter 无法解析）
export PI_CODING_AGENT_DIR="${PI_CODING_AGENT_DIR:-$HOME/.omp/agent}"

# 输出目录与文件：docs/better-harness/better-harness-inspector/（目录不存在时 CLI 会自动创建）
OUT_DIR="$ROOT_DIR/docs/better-harness/better-harness-inspector"
OUT_FILE="$OUT_DIR/inspector.html"

# 时间窗口：最近 15 天（含今天），即 since = 今天 - 14 天
if date -v-1d +%Y-%m-%d >/dev/null 2>&1; then
  SINCE="$(date -v-14d +%Y-%m-%d)"                # BSD date (macOS)
else
  SINCE="$(date -d '14 days ago' +%Y-%m-%d)"      # GNU date (Linux)
fi
UNTIL="$(date +%Y-%m-%d)"

# Better Harness CLI：优先本地 omp 插件包，其次 npx 拉取
BETTER_HARNESS_BIN="$HOME/.omp/plugins/node_modules/@qoder-ai/better-harness/scripts/better-harness.mjs"

echo "Harness Inspector (OMP-aware)"
echo "  workspace   : $ROOT_DIR"
echo "  platform    : all"
echo "  window      : $SINCE ~ $UNTIL (15 days)"
echo "  agent dir   : $PI_CODING_AGENT_DIR"
echo "  output      : $OUT_FILE"

if [ -f "$BETTER_HARNESS_BIN" ]; then
  node "$BETTER_HARNESS_BIN" inspector \
    --workspace "$ROOT_DIR" \
    --platform all \
    --since "$SINCE" \
    --until "$UNTIL" \
    --max-sessions 300 \
    --commits 300 \
    --out "$OUT_FILE" \
    --open
else
  npx -y @qoder-ai/better-harness@0.7.0-alpha1 inspector \
    --workspace "$ROOT_DIR" \
    --platform all \
    --since "$SINCE" \
    --until "$UNTIL" \
    --max-sessions 300 \
    --commits 300 \
    --out "$OUT_FILE" \
    --open
fi
