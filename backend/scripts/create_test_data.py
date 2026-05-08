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
    engine = create_engine(DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))

    # 导入模型
    from app.models.users import User
    from app.models.customers import Customer, CustomerProfile
    from app.models.billing import CustomerBalance

    # ---- 步骤 1: 创建 admin 用户（独立事务） ----
    with Session(engine) as session:
        result = session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()

        if admin:
            print("⚠️  admin 用户已存在，跳过创建")
        else:
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
            session.commit()
            print("✅ 管理员用户已创建 (admin/admin123)")

    # ---- 步骤 2: 创建测试客户（独立事务） ----
    with Session(engine) as session:
        # company_id 是 Integer 类型，使用数字 ID
        test_company_id = 100001
        result = session.execute(select(Customer).where(Customer.company_id == test_company_id))
        customer = result.scalar_one_or_none()

        if customer:
            print("⚠️  测试客户已存在，跳过创建")
        else:
            print("创建测试客户...")
            customer = Customer(
                company_id=test_company_id,
                name="测试客户公司",
                account_type="formal",
                email="test@customer.com",
                is_key_customer=True,
            )
            session.add(customer)
            session.flush()

            # 创建客户画像
            profile = CustomerProfile(
                customer_id=customer.id,
                industry="A",
            )
            session.add(profile)
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
            session.commit()
            print("✅ 客户余额已创建 (实充：10000, 赠费：1000)")

    print("\n✅ 测试数据创建成功!")


if __name__ == "__main__":
    try:
        create_test_data()
    except Exception as e:
        print(f"❌ 错误：{e}")
        sys.exit(1)
