"""
邮件服务 - SMTP 邮件发送
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os

from ..config import settings

# 初始化 Jinja2 模板引擎
template_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "emails")
email_env = Environment(
    loader=FileSystemLoader(template_dir, encoding="utf-8"),
    autoescape=select_autoescape(["html", "txt"]),
)


class EmailService:
    """邮件服务类"""

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.from_email = settings.smtp_username

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[List[str]] = None,
    ) -> bool:
        """
        发送邮件

        Args:
            to_emails: 收件人邮箱列表
            subject: 邮件主题
            html_content: HTML 内容
            text_content: 纯文本内容（可选）
            attachments: 附件文件路径列表（可选）

        Returns:
            bool: 发送是否成功
        """
        try:
            # 创建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = ", ".join(to_emails)

            # 添加纯文本内容
            if text_content:
                msg.attach(MIMEText(text_content, "plain", "utf-8"))

            # 添加 HTML 内容
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # 添加附件
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename={os.path.basename(file_path)}",
                            )
                            msg.attach(part)

            # 发送邮件
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                start_tls=True,
            )

            return True
        except Exception as e:
            import logging

            logging.error(f"邮件发送失败：{to_emails}, 主题：{subject}, 错误：{str(e)}")
            return False

    def render_template(self, template_name: str, **context) -> str:
        """
        渲染邮件模板

        Args:
            template_name: 模板文件名
            **context: 模板上下文变量

        Returns:
            str: 渲染后的 HTML 内容
        """
        try:
            template = email_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            import logging

            logging.error(f"邮件模板渲染失败：{template_name}, 错误：{str(e)}")
            # 返回错误信息作为邮件内容
            return f"<p>模板渲染失败：{str(e)}</p>"


# 全局邮件服务实例
email_service = EmailService()


def get_email_service() -> EmailService:
    """获取邮件服务实例"""
    return email_service
