#!/usr/bin/env python3
"""
密钥生成工具

用于生成应用所需的安全密钥，包括：
- JWT 密钥
- Webhook 密钥
- 数据库密码（可选）
- Redis 密码（可选）

使用方法：
    python backend/scripts/generate_secrets.py

输出：
    生成 .env.secrets 文件，包含所有生成的密钥
    同时输出可直接复制到 .env 文件的内容
"""

import secrets
import string
import os
import sys
from pathlib import Path
from datetime import datetime


def generate_secure_secret(length: int = 64) -> str:
    """生成安全随机密钥

    使用 secrets 模块生成密码学安全的随机字符串，
    包含大小写字母、数字和特殊字符。

    Args:
        length: 密钥长度，默认 64 字符

    Returns:
        随机生成的安全密钥
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_database_password(length: int = 32) -> str:
    """生成数据库密码

    生成适合 PostgreSQL 等数据库的密码，
    排除可能导致问题的特殊字符。

    Args:
        length: 密码长度，默认 32 字符

    Returns:
        随机生成的数据库密码
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_redis_password(length: int = 32) -> str:
    """生成 Redis 密码

    Args:
        length: 密码长度，默认 32 字符

    Returns:
        随机生成的 Redis 密码
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def print_section(title: str) -> None:
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def main():
    """主函数"""
    # 设置 UTF-8 输出编码
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    print_section("SECURITY KEY GENERATOR")

    # 生成密钥
    jwt_secret = generate_secure_secret(64)
    webhook_secret = generate_secure_secret(64)
    db_password = generate_database_password(32)
    redis_password = generate_redis_password(32)

    print("\nGenerated secure keys:\n")

    # 显示生成的密钥
    print(f"  JWT_SECRET (64 chars):")
    print(f"    {jwt_secret}\n")

    print(f"  WEBHOOK_SECRET (64 chars):")
    print(f"    {webhook_secret}\n")

    print(f"  Database Password (32 chars):")
    print(f"    {db_password}\n")

    print(f"  Redis Password (32 chars):")
    print(f"    {redis_password}\n")

    # 生成 .env 文件内容
    env_content = f"""# ============================================================
# Auto-generated security keys configuration
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# ============================================================
# Security reminders:
# 1. DO NOT commit this file to version control
# 2. Rotate keys regularly (recommended: every 90 days)
# 3. Use secrets management in production (e.g., AWS Secrets Manager)
# 4. Backup keys to a secure location
# ============================================================

# JWT authentication key
JWT_SECRET={jwt_secret}

# Webhook signature key
WEBHOOK_SECRET={webhook_secret}

# Database password (for building DATABASE_URL)
DATABASE_PASSWORD={db_password}

# Redis password (if using Redis)
REDIS_PASSWORD={redis_password}
"""

    # 确定输出文件路径
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    output_file = project_root / ".env.secrets"

    # 写入文件
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(env_content)

        print(f"[OK] Keys saved to: {output_file}")
        print(f"   Please add the following to your .env file:\n")

        # 显示 DATABASE_URL 示例
        print_section("DATABASE_URL Example")
        print(f"""
# Build connection string with generated database password:
DATABASE_URL=postgresql://user:{db_password}@localhost:5432/customer_platform

# If using Redis:
REDIS_URL=redis://:{redis_password}@localhost:6379/0
""")

        print_section("SECURITY REMINDERS")
        print("""
  [OK] .env.secrets is auto-added to .gitignore
  [!]  Please copy keys to .env file immediately
  [!]  Use secrets management in production
  [!]  Rotate keys every 90 days recommended
  [!]  Backup keys to secure location (password manager)
""")

        # 检查 .gitignore 是否包含 .env.secrets
        gitignore_path = project_root / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path, "r", encoding="utf-8") as f:
                gitignore_content = f.read()
            if ".env.secrets" not in gitignore_content:
                print("\n[WARN] .gitignore does not contain .env.secrets")
                print("   Please add the following line:")
                print("   .env.secrets")
        else:
            # 创建 .gitignore
            gitignore_content = """# Environment files
.env
.env.local
.env.*.local
.env.secrets

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Uploads
uploads/
*.log
"""
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(gitignore_content)
            print(f"\n[OK] Created .gitignore (includes .env.secrets)")

        print("\n" + "=" * 60)
        print("KEY GENERATION COMPLETED!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n[ERROR] Failed to save keys: {e}")
        print("\nPlease copy the keys above to a secure location.\n")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
