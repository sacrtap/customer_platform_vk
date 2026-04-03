#!/usr/bin/env python3
"""
创建测试数据脚本
用于 Podman 部署环境
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
import bcrypt

# 从环境变量读取数据库 URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost:5432/customer_platform",
)


async def create_test_data():
    """创建测试数据"""
    print(f"连接到数据库：{DATABASE_URL}")

    engine = create_async_engine(DATABASE_URL)

    async with AsyncSession(engine) as session:
        # 导入模型 (延迟导入以避免循环依赖)
        from app.models.users import User
        from app.models.customers import Customer, CustomerBalance

        # 检查是否已存在测试用户
        result = await session.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("⚠️  测试用户已存在，跳过创建")
        else:
            # 创建管理员用户
            print("创建管理员用户...")
            hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
            admin = User(
                username="admin",
                password_hash=hashed.decode(),
                email="admin@example.com",
                real_name="管理员",
                is_active=True,
                is_system=True,
            )
            session.add(admin)
            print("✅ 管理员用户已创建 (admin/admin123)")

        # 检查是否已存在测试客户
        result = await session.execute(
            select(Customer).where(Customer.company_id == "TEST001")
        )
        if result.scalar_one_or_none():
            print("⚠️  测试客户已存在，跳过创建")
        else:
            # 创建测试客户
            print("创建测试客户...")
            customer = Customer(
                company_id="TEST001",
                name="测试客户公司",
                account_type="formal",
                business_type="A",
                customer_level="KA",
                email="test@customer.com",
                is_key_customer=True,
            )
            session.add(customer)
            await session.flush()
            print("✅ 测试客户已创建")

            # 创建客户余额
            print("创建客户余额...")
            balance = CustomerBalance(
                customer_id=customer.id,
                real_amount=10000.00,
                bonus_amount=1000.00,
                total_amount=11000.00,
            )
            session.add(balance)
            print("✅ 客户余额已创建 (实充：10000, 赠费：1000)")

        await session.commit()
        print("\n✅ 测试数据创建成功!")

    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(create_test_data())
    except Exception as e:
        print(f"❌ 错误：{e}")
        sys.exit(1)
