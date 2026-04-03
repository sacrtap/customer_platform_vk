#!/usr/bin/env python3
"""
创建测试数据脚本
用于本地部署环境
"""

import sys
import os
import bcrypt

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# 从环境变量读取数据库 URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/customer_platform")


def create_test_data():
    """创建测试数据"""
    print(f"连接到数据库：{DATABASE_URL}")

    # 使用同步引擎
    engine = create_engine(
        DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    )

    with Session(engine) as session:
        # 导入模型
        from app.models.users import User
        from app.models.customers import Customer
        from app.models.billing import CustomerBalance

        # 检查是否已存在测试用户
        result = session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()

        if admin:
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
        result = session.execute(
            select(Customer).where(Customer.company_id == "TEST001")
        )
        customer = result.scalar_one_or_none()

        if customer:
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
            session.flush()
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

        session.commit()
        print("\n✅ 测试数据创建成功!")


if __name__ == "__main__":
    try:
        create_test_data()
    except Exception as e:
        print(f"❌ 错误：{e}")
        sys.exit(1)
