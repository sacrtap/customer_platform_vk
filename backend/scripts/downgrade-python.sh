#!/bin/bash
set -e

echo "🔄 Python 版本降级脚本"
echo "================================"

# 检查 Python 3.12
if ! command -v python3.12 &> /dev/null; then
    echo "❌ Python 3.12 未安装"
    echo "请先运行：brew install python@3.12"
    exit 1
fi

echo "✅ Python 3.12 已安装：$(python3.12 --version)"

# 切换到 backend 目录
cd "$(dirname "$0")/.."

# 备份当前环境
if [ -d ".venv" ]; then
    echo "📦 备份当前环境..."
    mv .venv .venv.py3.14.backup
    echo "✅ 备份完成：.venv.py3.14.backup"
else
    echo "⚠️ 未找到现有虚拟环境，跳过备份"
fi

# 创建新环境
echo "🔧 创建 Python 3.12 虚拟环境..."
python3.12 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

echo "✅ 虚拟环境创建成功"
echo "   Python 版本：$(python --version)"

# 升级 pip 和构建工具
echo "📥 升级 pip 和构建工具..."
pip install --upgrade pip setuptools wheel --quiet

# 安装依赖
echo "📥 安装项目依赖 (这可能需要几分钟)..."
pip install -r requirements.txt --quiet

# 验证关键包
echo ""
echo "✅ 验证关键包安装..."
python -c "import sanic; print(f'   Sanic: {sanic.__version__}')"
python -c "import sqlalchemy; print(f'   SQLAlchemy: {sqlalchemy.__version__}')"
python -c "import alembic; print(f'   Alembic: {alembic.__version__}')"

echo ""
echo "================================"
echo "🎉 Python 降级完成！"
echo "================================"
echo ""
echo "下一步操作："
echo "1. 运行测试验证：pytest tests/unit/ -v"
echo "2. 启动开发服务器：python -m uvicorn app.main:app --reload"
echo ""
echo "如需回滚到 Python 3.14："
echo "  rm -rf .venv && mv .venv.py3.14.backup .venv"
echo ""
