#!/bin/bash
# Podman 部署脚本 - macOS 简化版
# 使用本地 Python 运行迁移

set -e

# 配置
DB_CONTAINER="customer-platform-db"
DB_NAME="customer_platform"
DB_USER="user"
DB_PASSWORD="password"
DB_PORT="5432"

echo "======================================"
echo "   客户运营中台 - Podman 部署 (macOS)"
echo "======================================"
echo ""

# 清理旧容器
echo "🧹 清理旧容器..."
podman stop ${DB_CONTAINER} 2>/dev/null || true
podman rm ${DB_CONTAINER} 2>/dev/null || true

# 启动数据库
echo "🚀 启动数据库容器..."
podman run -d \
  --name ${DB_CONTAINER} \
  -e POSTGRES_DB=${DB_NAME} \
  -e POSTGRES_USER=${DB_USER} \
  -e POSTGRES_PASSWORD=${DB_PASSWORD} \
  -p ${DB_PORT}:5432 \
  --health-cmd="pg_isready -U ${DB_USER}" \
  --health-interval=5s \
  --health-timeout=3s \
  --health-retries=3 \
  docker.io/library/postgres:18

echo "⏳ 等待数据库启动..."
for i in {1..30}; do
  if podman exec ${DB_CONTAINER} pg_isready -U ${DB_USER} &>/dev/null; then
    echo "✅ 数据库已就绪"
    break
  fi
  sleep 1
done

# 创建测试数据库
echo "📊 创建测试数据库..."
podman exec ${DB_CONTAINER} createdb -U ${DB_USER} customer_platform_test

# 在主机上运行迁移 (通过 localhost 连接容器)
echo "🔧 运行数据库迁移..."

cd backend
source .venv/bin/activate

# 使用 localhost 连接 (Podman 会转发端口)
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"

echo "使用数据库：${DATABASE_URL}"

# 运行迁移
python << 'PYTHON_SCRIPT'
import os
from sqlalchemy import create_engine
from app.models.base import BaseModel

db_url = os.getenv('DATABASE_URL')
print(f"连接数据库：{db_url}")

try:
    engine = create_engine(db_url)
    BaseModel.metadata.create_all(engine)
    print("✅ 数据库表已创建")
except Exception as e:
    print(f"❌ 迁移失败：{e}")
    print("\n提示：如果连接失败，请尝试使用本地 PostgreSQL:")
    print("  brew install postgresql@18")
    print("  brew services start postgresql@18")
    exit(1)
PYTHON_SCRIPT

# 创建测试数据
echo "📝 创建测试数据..."
python scripts/create_test_data.py

deactivate
cd ..

# 清理
rm -f /tmp/Containerfile.migrate /tmp/create_data.py

echo ""
echo "======================================"
echo "       ✅ 部署完成!"
echo "======================================"
echo ""
echo "📌 访问信息:"
echo "   数据库：localhost:${DB_PORT}"
echo "   用户：${DB_USER}"
echo "   密码：${DB_PASSWORD}"
echo ""
echo "📌 测试数据:"
echo "   管理员：admin / admin123"
echo "   测试客户：TEST001 (余额：11000)"
echo ""
echo "📌 常用命令:"
echo "   podman logs ${DB_CONTAINER}     # 查看数据库日志"
echo "   podman stop ${DB_CONTAINER}     # 停止数据库"
echo "   podman start ${DB_CONTAINER}    # 启动数据库"
echo ""
