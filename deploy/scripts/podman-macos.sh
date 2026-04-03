#!/bin/bash
# Podman 部署脚本 - macOS 优化版
# 在 Podman VM 内运行迁移以避免网络问题

set -e

# 配置
DB_CONTAINER="customer-platform-db"
DB_NAME="customer_platform"
DB_USER="user"
DB_PASSWORD="password"
DB_PORT="5432"
APP_IMAGE="customer-platform-migrate:latest"

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

# 在容器内运行迁移
echo "🔧 运行数据库迁移..."

# 创建临时迁移镜像
cat > /tmp/Containerfile.migrate << 'EOF'
FROM python:3.14-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev gcc 2>/dev/null || true
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary 2>/dev/null || true
COPY backend/ .
CMD ["python", "-c", "from sqlalchemy import create_engine; from app.models.base import BaseModel; e = create_engine('postgresql://user:password@customer-platform-db:5432/customer_platform'); BaseModel.metadata.create_all(e); print('✅ 迁移完成')"]
EOF

# 构建迁移镜像
echo "📦 构建迁移镜像..."
podman build -t ${APP_IMAGE} -f /tmp/Containerfile.migrate .

# 运行迁移
echo "🏃 执行迁移..."
podman run --rm \
  --network container:${DB_CONTAINER} \
  ${APP_IMAGE}

# 创建测试数据
echo "📝 创建测试数据..."
cat > /tmp/create_data.py << 'PYEOF'
import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
import bcrypt

async def main():
    engine = create_async_engine("postgresql+asyncpg://user:password@localhost:5432/customer_platform")
    async with AsyncSession(engine) as session:
        from app.models.users import User
        from app.models.customers import Customer, CustomerBalance
        
        # 创建管理员
        result = await session.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
            admin = User(username="admin", password_hash=hashed.decode(), email="admin@example.com", real_name="管理员", is_active=True, is_system=True)
            session.add(admin)
            print("✅ 管理员用户已创建 (admin/admin123)")
        
        # 创建测试客户
        result = await session.execute(select(Customer).where(Customer.company_id == "TEST001"))
        if not result.scalar_one_or_none():
            customer = Customer(company_id="TEST001", name="测试客户公司", account_type="formal", business_type="A", customer_level="KA", email="test@customer.com", is_key_customer=True)
            session.add(customer)
            await session.flush()
            balance = CustomerBalance(customer_id=customer.id, real_amount=10000.00, bonus_amount=1000.00, total_amount=11000.00)
            session.add(balance)
            print("✅ 测试客户已创建 (余额：11000)")
        
        await session.commit()
    await engine.dispose()
    print("✅ 测试数据创建完成!")

asyncio.run(main())
PYEOF

podman run --rm \
  --network container:${DB_CONTAINER} \
  -v /tmp/create_data.py:/app/create_data.py \
  ${APP_IMAGE} \
  python create_data.py

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
