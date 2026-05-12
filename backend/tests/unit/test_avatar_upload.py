"""头像上传接口单元测试"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.routes.users import upload_avatar


@pytest.fixture
def mock_request():
    """模拟请求对象"""
    request = MagicMock()
    request.ctx = MagicMock()
    request.ctx.user = {"user_id": 1}
    request.ctx.db_session = AsyncMock()
    request.ctx.db_session.commit = AsyncMock()
    request.ip = "127.0.0.1"
    return request


@pytest.fixture
def temp_uploads(tmp_path):
    """创建临时上传目录"""
    avatars_dir = tmp_path / "uploads" / "avatars"
    avatars_dir.mkdir(parents=True)
    return avatars_dir


def create_test_image(width, height, format="JPEG"):
    """创建测试图片"""
    img = Image.new("RGB", (width, height), color="red")
    buffer = io.BytesIO()
    if format == "JPEG":
        img.save(buffer, format="JPEG")
        buffer.name = "test.jpg"
    else:
        img.save(buffer, format="PNG")
        buffer.name = "test.png"
    buffer.seek(0)
    return buffer


class TestUploadAvatar:
    """头像上传测试"""

    @pytest.mark.asyncio
    async def test_upload_success_small_image(self, mock_request, temp_uploads):
        """测试成功上传小尺寸图片"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            # Mock db_session.execute to return a user with no avatar
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(
                return_value=MagicMock(id=1, avatar_url=None)
            )
            mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_result)

            img_buffer = create_test_image(200, 200)
            mock_file = MagicMock()
            mock_file.name = "test.jpg"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            data = response.body
            import json

            json_data = json.loads(data)
            assert json_data["code"] == 0
            assert "avatar_url" in json_data["data"]
            assert json_data["data"]["avatar_url"].startswith("/uploads/avatars/")

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_extension(self, mock_request, temp_uploads):
        """测试拒绝非图片格式"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            mock_file = MagicMock()
            mock_file.name = "test.gif"
            mock_file.body = b"fake gif content"
            mock_file.type = "image/gif"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 400
            import json

            json_data = json.loads(response.body)
            assert json_data["code"] == 400

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, mock_request, temp_uploads):
        """测试拒绝超大文件"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            mock_file = MagicMock()
            mock_file.name = "test.jpg"
            mock_file.body = b"x" * (3 * 1024 * 1024)  # 3MB
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 400

    @pytest.mark.asyncio
    async def test_upload_compresses_large_image(self, mock_request, temp_uploads):
        """测试大尺寸图片自动压缩"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            # Mock db_session.execute to return a user with no avatar
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(
                return_value=MagicMock(id=1, avatar_url=None)
            )
            mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_result)

            # 创建 2000x1500 的图片（超过 1024 限制）
            img_buffer = create_test_image(2000, 1500)
            mock_file = MagicMock()
            mock_file.name = "large.jpg"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            # 验证保存的图片尺寸被压缩
            import json

            json_data = json.loads(response.body)
            avatar_url = json_data["data"]["avatar_url"]
            # avatar_url is /uploads/avatars/filename, extract filename
            filename = avatar_url.split("/")[-1]
            saved_path = temp_uploads / filename
            with Image.open(saved_path) as img:
                assert img.width <= 1024
                assert img.height <= 1024

    @pytest.mark.asyncio
    async def test_upload_png_format(self, mock_request, temp_uploads):
        """测试 PNG 格式上传"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            # Mock db_session.execute to return a user with no avatar
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(
                return_value=MagicMock(id=1, avatar_url=None)
            )
            mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_result)

            img_buffer = create_test_image(300, 300, format="PNG")
            mock_file = MagicMock()
            mock_file.name = "test.png"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/png"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            import json

            json_data = json.loads(response.body)
            assert json_data["data"]["avatar_url"].endswith(".png")

    @pytest.mark.asyncio
    async def test_upload_no_file(self, mock_request):
        """测试未上传文件"""
        mock_request.files = {}
        response = await upload_avatar(mock_request)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_upload_deletes_old_avatar(self, mock_request, temp_uploads):
        """测试上传新头像时删除旧头像文件"""
        # 创建旧头像文件（在实现代码期望的路径位置）
        old_file_path = temp_uploads.parent / "uploads" / "avatars"
        old_file_path.mkdir(parents=True, exist_ok=True)
        old_file = old_file_path / "1_old_avatar.jpg"
        old_file.write_bytes(b"old avatar data")

        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent)
            mock_settings.max_file_size = 2 * 1024 * 1024

            # 模拟用户已有旧头像
            mock_request.ctx.db_session.execute = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(
                return_value=MagicMock(id=1, avatar_url="/uploads/avatars/1_old_avatar.jpg")
            )
            mock_request.ctx.db_session.execute.return_value = mock_result

            img_buffer = create_test_image(200, 200)
            mock_file = MagicMock()
            mock_file.name = "new.jpg"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            assert not old_file.exists()  # 旧文件应被删除
