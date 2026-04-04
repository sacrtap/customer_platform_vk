from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os
import secrets


class Settings(BaseSettings):
    """应用配置管理"""

    # 应用配置
    app_name: str = "customer_platform_api"
    app_display_name: str = "客户运营中台 API"
    app_env: str = Field(
        default="development", description="应用环境：development/production"
    )
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # 数据库配置
    database_url: str = "postgresql://user:password@localhost:5432/customer_platform"
    database_echo: bool = False

    # JWT 配置 - 生产环境必须从环境变量读取
    jwt_secret: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET") or secrets.token_urlsafe(32),
        description="JWT 签名密钥，生产环境必须设置 JWT_SECRET 环境变量",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 小时
    jwt_refresh_expire_days: int = 7

    # CORS 配置
    cors_origins: list = ["http://localhost:5173", "http://localhost:3000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["*"]
    cors_allow_headers: list = ["*"]

    # 文件存储配置
    file_storage_path: str = "./uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB

    # 邮件配置
    smtp_host: str = "smtp.company.com"
    smtp_port: int = 587
    smtp_username: str = "noreply@company.com"
    smtp_password: str = ""

    # 外部 API 配置
    external_api_base_url: str = "https://business-api.company.com"
    external_api_token: str = ""

    # Webhook 配置 - 生产环境必须从环境变量读取
    webhook_secret: str = Field(
        default_factory=lambda: (
            os.getenv("WEBHOOK_SECRET") or secrets.token_urlsafe(32)
        ),
        description="Webhook 签名密钥，生产环境必须设置 WEBHOOK_SECRET 环境变量",
    )

    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"

    # 缓存 TTL 配置 (秒)
    cache_ttl_dashboard_stats: int = 300  # 5 分钟
    cache_ttl_dashboard_chart: int = 900  # 15 分钟
    cache_ttl_analytics_health: int = 600  # 10 分钟
    cache_ttl_analytics_profile: int = 3600  # 1 小时
    cache_ttl_analytics_invoice: int = 300  # 5 分钟
    cache_ttl_analytics_warning: int = 180  # 3 分钟
    cache_ttl_analytics_prediction: int = 1800  # 30 分钟
    cache_ttl_pricing_rules: int = 3600  # 1 小时
    cache_ttl_analytics_trend: int = 900  # 15 分钟

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
