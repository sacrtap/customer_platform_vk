"""头像上传接口单元测试"""

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.routes.users import upload_avatar


@pytest.fixture
def mock_request():
    """模拟请求对象"""
    request = MagicMock()
    request.ctx = MagicMock()
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
    else:
        img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def parse_response(response):
    """解析 Sanic 响应体"""
    return json.loads(response.body)


class TestUploadAvatar:
    """头像上传测试"""

    @pytest.mark.asyncio
    async def test_upload_success_small_image(self, mock_request, temp_uploads):
        """测试成功上传小尺寸图片"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent)

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
            data = parse_response(response)
            assert data["code"] == 0
            assert data["message"] == "success"
            assert "avatar_url" in data["data"]
            assert data["data"]["avatar_url"].startswith("/uploads/avatars/")

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_extension(self, mock_request, temp_uploads):
        """测试拒绝非图片格式"""
        mock_file = MagicMock()
        mock_file.name = "test.gif"
        mock_file.body = b"fake gif content"
        mock_file.type = "image/gif"
        mock_request.files = {"file": [mock_file]}

        response = await upload_avatar(mock_request)

        assert response.status == 400
        data = parse_response(response)
        assert data["code"] == 40003

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, mock_request, temp_uploads):
        """测试拒绝超大文件"""
        mock_file = MagicMock()
        mock_file.name = "test.jpg"
        mock_file.body = b"x" * (3 * 1024 * 1024)  # 3MB
        mock_file.type = "image/jpeg"
        mock_request.files = {"file": [mock_file]}

        response = await upload_avatar(mock_request)

        assert response.status == 400
        data = parse_response(response)
        assert data["code"] == 40004

    @pytest.mark.asyncio
    async def test_upload_compresses_large_image(self, mock_request, temp_uploads):
        """测试大尺寸图片自动压缩"""
        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(temp_uploads.parent)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(
                return_value=MagicMock(id=1, avatar_url=None)
            )
            mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_result)

            img_buffer = create_test_image(2000, 1500)
            mock_file = MagicMock()
            mock_file.name = "large.jpg"
            mock_file.body = img_buffer.getvalue()
            mock_file.type = "image/jpeg"
            mock_request.files = {"file": [mock_file]}

            response = await upload_avatar(mock_request)

            assert response.status == 200
            data = parse_response(response)
            avatar_url = data["data"]["avatar_url"]
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
            data = parse_response(response)
            assert data["data"]["avatar_url"].endswith(".png")

    @pytest.mark.asyncio
    async def test_upload_no_file(self, mock_request):
        """测试未上传文件"""
        mock_request.files = {}
        response = await upload_avatar(mock_request)
        assert response.status == 400
        data = parse_response(response)
        assert data["code"] == 40001

    @pytest.mark.asyncio
    async def test_upload_deletes_old_avatar(self, mock_request, tmp_path):
        """测试上传新头像时删除旧头像文件"""
        storage_root = tmp_path / "storage"
        avatars_dir = storage_root / "uploads" / "avatars"
        avatars_dir.mkdir(parents=True)

        # 创建旧头像文件
        old_file = avatars_dir / "1_old_avatar.jpg"
        old_file.write_bytes(b"old avatar data")

        with patch("app.routes.users.settings") as mock_settings:
            mock_settings.file_storage_path = str(storage_root)

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
            assert not old_file.exists()

    @pytest.mark.asyncio
    async def test_upload_rejects_mime_mismatch(self, mock_request, temp_uploads):
        """测试拒绝扩展名与 MIME 不匹配的文件"""
        mock_file = MagicMock()
        mock_file.name = "fake.jpg"
        mock_file.body = b"this is not a real jpeg, just plain text"
        mock_file.type = "text/plain"
        mock_request.files = {"file": [mock_file]}

        response = await upload_avatar(mock_request)

        assert response.status == 400
        data = parse_response(response)
        assert data["code"] == 40005
