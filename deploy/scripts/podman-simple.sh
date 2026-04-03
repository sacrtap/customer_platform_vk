#!/bin/bash
# 简化的 Podman 部署脚本 - 只部署数据库和运行迁移

set -e

# 配置
DB_CONTAINER="customer-platform-db"
DB_NAME="customer_platform"
DB_USER="user"
DB_PASSWORD="password"
DB_PORT="5432"

echo "🚀 启动数据库容器..."

podman run -d \
  --name ${DB_CONTAINER} \
  -e POSTGRES_DB=${DB_NAME} \
  -e POSTGRES_USER=${DB_USER} \
  -e POSTGRES_PASSWORD=${DB_PASSWORD} \
  -p ${DB_PORT}:5432 \
  docker.io/library/postgres:18

echo "⏳ 等待数据库启动..."
sleep 5

echo "📊 创建测试数据库..."
podman exec ${DB_CONTAINER} createdb -U ${DB_USER} customer_platform_test

echo "🔧 运行迁移 (使用 Python)..."
cd backend
source .venv/bin/activate

# 使用 Python 直接创建表
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"

python << 'EOF'
from sqlalchemy import create_engine
from app.models.base import BaseModel

engine = create_engine(
    "postgresql://user:password@localhost:5432/customer_platform"
)
BaseModel.metadata.create_all(engine)
print("✅ 数据库表已创建")
EOF

deactivate
cd ..

echo "📝 创建测试数据..."
cd backend
source .venv/bin/activate
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"
python scripts/create_test_data.py
deactivate
cd ..

echo ""
echo "✅ 部署完成!"
echo ""
echo "访问地址:"
echo "  数据库：localhost:${DB_PORT}"
echo "  用户：${DB_USER}"
echo "  密码：${DB_PASSWORD}"
