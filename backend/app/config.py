import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置管理"""

    # 应用配置
    app_name: str = "customer_platform_api"
    app_display_name: str = "客户运营中台 API"
    app_env: str = Field(default="development", description="应用环境：development/production")
    debug: bool = False  # 默认关闭 debug 模式，开发环境通过环境变量 DEBUG=true 开启
    host: str = "0.0.0.0"  # nosec B104 -- 开发环境默认值，生产环境通过环境变量覆盖
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
    cors_allow_methods: list = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    cors_allow_headers: list = [
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "X-Request-Id",
    ]
    cors_expose_headers: list = ["X-Request-Id", "X-Truncated", "X-Total-Count"]

    # 文件存储配置
    file_storage_path: str = "./uploads"
    max_file_size: int = 20 * 1024 * 1024  # 20MB

    # 邮件配置
    smtp_host: str = "smtp.company.com"
    smtp_port: int = 587
    smtp_username: str = "noreply@company.com"
    smtp_password: str = ""

    # 前端应用 URL（用于邮件中的链接）
    app_url: str = "http://localhost:5173"

    # 外部 API 配置
    external_api_base_url: str = "https://business-api.company.com"
    external_api_token: str = ""

    # GitHub 部署公告配置（读取 Deploy workflow 成功运行生成系统升级公告）
    github_repo: str = "sacrtap/customer_platform_vk"  # 读取部署更新的仓库
    github_token: str = ""  # 可选；留空走匿名请求（60/h，靠 Redis 缓存兜底）
    github_workflow_file: str = "deploy.yml"  # 部署 workflow 文件名

    # Webhook 配置 - 生产环境必须从环境变量读取
    webhook_secret: str = Field(
        default_factory=lambda: os.getenv("WEBHOOK_SECRET") or secrets.token_urlsafe(32),
        description="Webhook 签名密钥，生产环境必须设置 WEBHOOK_SECRET 环境变量",
    )

    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"

    # 数据备份配置
    backup_dir: str = "/app/uploads/backups"  # 备份文件目录（挂载于 app_uploads 命名卷）
    backup_retention_days: int = 5  # 备份保留天数（超过即清理）
    backup_cleanup_interval_days: int = 5  # 清理任务执行间隔（天）
    backup_task_timeout_minutes: int = 30  # 备份/恢复任务卡死判定阈值（分钟），与同步任务一致

    # 外部 MySQL 配置（用于订单同步）
    external_mysql_url: str = ""
    external_mysql_pool_size: int = 5
    external_mysql_pool_recycle: int = 3600

    # CRM（weiwenjia 开放 API）只读集成
    # 仅读取客户/合同/回款，不向 CRM 写入任何业务数据。
    # 环境变量提供的是「出厂默认值」：页面保存过的配置（crm_settings 表）优先，
    # 因此部署后可由管理员在「CRM充值管理 → CRM 配置」直接维护与更换凭据。
    crm_enabled: bool = False
    crm_base_url: str = "https://lxcrm.weiwenjia.com"
    crm_corp_id: str = ""
    crm_phone: str = ""
    crm_password: str = ""
    # 页面保存的 CRM 登录密码用 Fernet 对称加密后落库，密钥必须由部署密钥注入：
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # 未配置时仍可读取/保存非密码字段，但保存密码会被拒绝。
    crm_credential_key: str = ""

    # 消费预测单价矩阵（元/套）
    consumption_forecast_unit_prices: dict = {
        "L": 14.5,
        "N": 30.0,
        "X": 30.0,
    }

    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
