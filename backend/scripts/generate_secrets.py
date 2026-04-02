#!/usr/bin/env python3
"""
生成安全的随机密钥用于生产环境

使用方法:
    python scripts/generate_secrets.py

输出示例:
    JWT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
"""
import secrets

def generate_secret():
    """生成 32 字节的 URL 安全随机字符串"""
    return secrets.token_urlsafe(32)

if __name__ == "__main__":
    print("# 生产环境密钥配置")
    print("# 将这些值添加到 .env 文件中")
    print(f"JWT_SECRET={generate_secret()}")
    print(f"WEBHOOK_SECRET={generate_secret()}")
