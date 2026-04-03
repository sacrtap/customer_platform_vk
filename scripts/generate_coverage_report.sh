#!/bin/bash
# 测试覆盖率报告生成脚本

set -e

echo "📊 生成测试覆盖率报告..."

cd backend

# 激活虚拟环境
source .venv/bin/activate

# 运行所有测试并生成覆盖率
python -m pytest \
    tests/unit/ \
    --cov=app \
    --cov-report=html:../docs/testing/coverage-reports/html \
    --cov-report=xml:../docs/testing/coverage-reports/coverage.xml \
    --cov-report=term-missing \
    -v

echo ""
echo "✅ 报告已生成:"
echo "  - HTML: docs/testing/coverage-reports/html/index.html"
echo "  - XML: docs/testing/coverage-reports/coverage.xml"

# 在 macOS 上打开 HTML 报告
if [[ "$OSTYPE" == "darwin"* ]]; then
    open docs/testing/coverage-reports/html/index.html
fi
