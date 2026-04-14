"""
邮件服务测试
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.email import EmailService, email_service, get_email_service


class TestEmailService:
    """邮件服务测试类"""

    @pytest.fixture
    def email_service_instance(self):
        """创建邮件服务实例"""
        with patch("app.services.email.settings") as mock_settings:
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_username = "test@test.com"
            mock_settings.smtp_password = "test-password"
            service = EmailService()
            yield service

    @pytest.fixture
    def sample_email_data(self):
        """示例邮件数据"""
        return {
            "to_emails": ["user1@example.com", "user2@example.com"],
            "subject": "测试邮件主题",
            "html_content": "<h1>测试内容</h1>",
            "text_content": "测试内容",
        }

    @pytest.mark.asyncio
    async def test_send_email_success(self, email_service_instance, sample_email_data):
        """测试邮件发送成功"""
        with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await email_service_instance.send_email(
                to_emails=sample_email_data["to_emails"],
                subject=sample_email_data["subject"],
                html_content=sample_email_data["html_content"],
                text_content=sample_email_data["text_content"],
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_with_attachments(
        self, email_service_instance, sample_email_data, tmp_path
    ):
        """测试带附件的邮件发送"""
        # 创建临时附件文件
        attachment_file = tmp_path / "test_attachment.txt"
        attachment_file.write_text("附件内容")

        with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await email_service_instance.send_email(
                to_emails=sample_email_data["to_emails"],
                subject=sample_email_data["subject"],
                html_content=sample_email_data["html_content"],
                attachments=[str(attachment_file)],
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_invalid_attachment_path(
        self, email_service_instance, sample_email_data
    ):
        """测试无效附件路径"""
        with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await email_service_instance.send_email(
                to_emails=sample_email_data["to_emails"],
                subject=sample_email_data["subject"],
                html_content=sample_email_data["html_content"],
                attachments=["/nonexistent/file.txt"],
            )

            # 应该仍然成功发送，只是忽略无效附件
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_smtp_error(self, email_service_instance, sample_email_data):
        """测试 SMTP 发送错误"""
        with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("SMTP 连接失败")

            result = await email_service_instance.send_email(
                to_emails=sample_email_data["to_emails"],
                subject=sample_email_data["subject"],
                html_content=sample_email_data["html_content"],
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_empty_to_emails(self, email_service_instance):
        """测试空收件人列表"""
        with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await email_service_instance.send_email(
                to_emails=[],
                subject="测试主题",
                html_content="测试内容",
            )

            # 空收件人列表应该仍然调用发送（由 SMTP 服务器处理错误）
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_only_html_content(self, email_service_instance):
        """测试仅 HTML 内容（无纯文本）"""
        with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await email_service_instance.send_email(
                to_emails=["user@example.com"],
                subject="测试主题",
                html_content="<h1>HTML 内容</h1>",
            )

            assert result is True
            mock_send.assert_called_once()

    def test_render_template_success(self, email_service_instance, tmp_path):
        """测试模板渲染成功"""
        # 创建临时模板文件
        template_dir = tmp_path / "emails"
        template_dir.mkdir()
        template_file = template_dir / "test_template.html"
        template_file.write_text("<h1>Hello {{ name }}!</h1>")

        # 重新创建服务使用临时模板目录
        with patch("app.services.email.template_dir", str(template_dir)):
            with patch("app.services.email.email_env") as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = "<h1>Hello World!</h1>"
                mock_env.get_template.return_value = mock_template

                result = email_service_instance.render_template("test_template.html", name="World")

                assert result == "<h1>Hello World!</h1>"
                mock_env.get_template.assert_called_once_with("test_template.html")
                mock_template.render.assert_called_once_with(name="World")

    def test_render_template_not_found(self, email_service_instance):
        """测试模板不存在"""
        with patch("app.services.email.email_env") as mock_env:
            mock_env.get_template.side_effect = Exception("模板不存在")

            result = email_service_instance.render_template("nonexistent.html")

            # 应该返回错误信息
            assert "模板渲染失败" in result or "Template" in result

    def test_get_email_service(self):
        """测试获取邮件服务实例"""
        service = get_email_service()

        assert isinstance(service, EmailService)
        assert service is email_service  # 应该是同一个全局实例

    def test_email_service_initialization(self):
        """测试邮件服务初始化"""
        with patch("app.services.email.settings") as mock_settings:
            mock_settings.smtp_host = "smtp.example.com"
            mock_settings.smtp_port = 465
            mock_settings.smtp_username = "admin@example.com"
            mock_settings.smtp_password = "secret"

            service = EmailService()

            assert service.smtp_host == "smtp.example.com"
            assert service.smtp_port == 465
            assert service.smtp_username == "admin@example.com"
            assert service.smtp_password == "secret"
            assert service.from_email == "admin@example.com"

    @pytest.mark.asyncio
    async def test_send_email_multiple_recipients(self, email_service_instance, sample_email_data):
        """测试发送给多个收件人"""
        with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await email_service_instance.send_email(
                to_emails=[
                    "user1@example.com",
                    "user2@example.com",
                    "user3@example.com",
                ],
                subject=sample_email_data["subject"],
                html_content=sample_email_data["html_content"],
            )

            assert result is True
            # 验证收件人列表
            call_args = mock_send.call_args
            msg = call_args[0][0]
            assert "user1@example.com" in msg["To"]
            assert "user2@example.com" in msg["To"]
            assert "user3@example.com" in msg["To"]

    @pytest.mark.asyncio
    async def test_send_email_special_characters(self, email_service_instance, sample_email_data):
        """测试包含特殊字符的邮件内容"""
        special_content = "<h1>测试中文 & 特殊字符 <>&\"'</h1>"

        with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await email_service_instance.send_email(
                to_emails=sample_email_data["to_emails"],
                subject="特殊字符测试",
                html_content=special_content,
            )

            assert result is True
            mock_send.assert_called_once()
