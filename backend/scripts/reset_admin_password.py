#!/usr/bin/env python3
"""
重置 admin 用户密码脚本

用法:
    python scripts/reset_admin_password.py
"""

import sys
import os
import bcrypt

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env 文件
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.users import User

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/customer_platform")


def reset_admin_password(new_password: str = "admin123"):
    """重置 admin 用户密码"""
    print(f"连接到数据库：{DATABASE_URL}")

    engine = create_engine(
        DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    )

    with Session(engine) as session:
        user = session.execute(
            select(User).where(User.username == "admin")
        ).scalar_one_or_none()

        if not user:
            print("❌ admin 用户不存在")
            return False

        print(f"找到用户：{user.username} ({user.email})")

        hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
        user.password_hash = hashed.decode()

        session.commit()
        print(f"✅ admin 用户密码已重置为：{new_password}")
        return True


if __name__ == "__main__":
    try:
        reset_admin_password()
    except Exception as e:
        print(f"❌ 错误：{e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
