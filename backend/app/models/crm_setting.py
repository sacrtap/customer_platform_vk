"""CRM 集成配置模型

页面可维护的 CRM 同步开关与凭据（单行 `default`）：
- 环境变量（CRM_ENABLED/CRM_BASE_URL/CRM_CORP_ID/CRM_PHONE/CRM_PASSWORD）
  作为未保存过页面配置时的出厂默认值；
- 一旦页面保存过，运行时以本表为准，支持随时更换企业ID/手机号/密码。

密码只存 Fernet 密文（见 `app/utils/crypto.py`），接口永不返回明文。
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class CrmSetting(Base, TimestampMixin):
    """CRM 集成配置（单行）"""

    __tablename__ = "crm_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="配置名，固定 default"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", comment="是否启用 CRM 同步"
    )
    base_url: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="CRM 开放 API 基址（仅官方 HTTPS 域名）"
    )
    corp_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="企业ID")
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="登录手机号")
    password_cipher: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="登录密码 Fernet 密文，绝不存明文"
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="最后修改人"
    )

    def __repr__(self):
        return f"<CrmSetting {self.name} enabled={self.enabled} corp={self.corp_id}>"
