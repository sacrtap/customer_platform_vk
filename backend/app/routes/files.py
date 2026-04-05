"""
P6-9: 文件上传 API（安全增强版）
支持 xlsx/xls/pdf/png/jpg/jpeg 文件格式
安全特性：
- 扩展名白名单验证
- MIME 类型验证（python-magic）
- 文件大小限制（10MB）
- 随机文件名存储
"""

import uuid
import logging
import magic
from datetime import datetime
from pathlib import Path
from sanic import Blueprint
from sanic.response import json
from sanic.request import File

from ..middleware.auth import auth_required
from ..config import settings

logger = logging.getLogger(__name__)

files_bp = Blueprint("files", url_prefix="/api/v1/files")

# 允许的扩展名与 MIME 类型映射（严格白名单）
ALLOWED_EXTENSIONS = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

# 允许的 MIME 类型白名单
ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/pdf",
    "image/png",
    "image/jpeg",
}

# 最大文件大小 (10MB)
MAX_FILE_SIZE = settings.max_file_size


def get_file_extension(filename: str) -> str:
    """安全获取文件扩展名（小写）"""
    return Path(filename).suffix.lower()


def allowed_extension(filename: str) -> bool:
    """检查文件扩展名是否在白名单中"""
    ext = get_file_extension(filename)
    return ext in ALLOWED_EXTENSIONS


def validate_mime_type(file_content: bytes, filename: str) -> tuple[bool, str, str]:
    """
    使用 python-magic 验证文件真实 MIME 类型

    Returns:
        tuple: (is_valid, detected_mime, error_message)
    """
    try:
        # 检测真实 MIME 类型
        detected_mime = magic.from_buffer(file_content, mime=True)
        logger.debug(f"文件 {filename} 检测到的 MIME 类型：{detected_mime}")

        # 检查是否在白名单中
        if detected_mime not in ALLOWED_MIME_TYPES:
            return False, detected_mime, f"不允许的文件类型：{detected_mime}"

        # 验证扩展名与 MIME 类型是否匹配
        ext = get_file_extension(filename)
        expected_mime = ALLOWED_EXTENSIONS.get(ext)

        if expected_mime and detected_mime != expected_mime:
            # 特殊处理：.xls 可能检测为 application/vnd.ms-excel 或 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
            if ext == ".xls" and detected_mime in ALLOWED_MIME_TYPES:
                pass  # 允许
            elif ext == ".jpg" and detected_mime == "image/jpeg":
                pass  # 允许，.jpg 和 .jpeg 都是 image/jpeg
            elif ext == ".jpeg" and detected_mime == "image/jpeg":
                pass  # 允许
            else:
                return (
                    False,
                    detected_mime,
                    f"文件扩展名 ({ext}) 与内容类型 ({detected_mime}) 不匹配",
                )

        return True, detected_mime, ""

    except Exception as e:
        logger.error(f"MIME 类型检测失败：{str(e)}")
        return False, "unknown", f"MIME 类型检测失败：{str(e)}"


def generate_secure_filename(original_filename: str) -> tuple[str, str]:
    """
    生成安全的随机文件名

    Returns:
        tuple: (stored_filename, extension)
    """
    ext = get_file_extension(original_filename)
    # 使用 UUID4 生成不可预测的随机文件名
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return unique_name, ext


@files_bp.post("/upload")
@auth_required
async def upload_file(request):
    """
    上传文件（安全增强版）

    安全验证流程：
    1. 扩展名白名单验证
    2. 文件大小限制验证
    3. MIME 类型验证（python-magic）
    4. 随机文件名存储

    Request:
        multipart/form-data with field 'file'

    Response:
        {
            "code": 0,
            "message": "success",
            "data": {
                "file_id": "uuid",
                "filename": "original.xlsx",
                "stored_filename": "uuid.xlsx",
                "file_path": "/uploads/2024/01/uuid.xlsx",
                "file_size": 1024,
                "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "uploaded_at": "2024-01-01T12:00:00"
            }
        }
    """
    try:
        # ========== 步骤 1: 检查文件是否存在 ==========
        if not request.files or "file" not in request.files:
            return json({"code": 400, "message": "未找到上传文件", "data": None}, status=400)

        file: File = request.files["file"]

        # ========== 步骤 2: 检查文件名 ==========
        if not file.name:
            return json({"code": 400, "message": "文件名不能为空", "data": None}, status=400)

        # ========== 步骤 3: 扩展名白名单验证 ==========
        if not allowed_extension(file.name):
            ext = get_file_extension(file.name)
            logger.warning(
                f"安全拦截：拒绝不允许的扩展名 {ext}, 原始文件名：{file.name}, 用户：{request.get('auth_user', 'unknown')}"
            )
            return json(
                {
                    "code": 400,
                    "message": f"不支持的文件类型：{ext}",
                    "data": {
                        "allowed_extensions": list(ALLOWED_EXTENSIONS.keys()),
                        "hint": "仅支持：.xlsx, .xls, .pdf, .png, .jpg, .jpeg",
                    },
                },
                status=400,
            )

        # ========== 步骤 4: 文件大小限制验证 ==========
        file_size = len(file.body)
        if file_size > MAX_FILE_SIZE:
            logger.warning(
                f"安全拦截：文件大小超限 {file_size} 字节，限制：{MAX_FILE_SIZE} 字节，用户：{request.get('auth_user', 'unknown')}"
            )
            return json(
                {
                    "code": 400,
                    "message": f"文件大小超过限制 ({MAX_FILE_SIZE / 1024 / 1024}MB)",
                    "data": {
                        "max_size_mb": MAX_FILE_SIZE / 1024 / 1024,
                        "actual_size": file_size,
                    },
                },
                status=400,
            )

        # ========== 步骤 5: MIME 类型验证（python-magic）==========
        is_valid_mime, detected_mime, mime_error = validate_mime_type(file.body, file.name)
        if not is_valid_mime:
            logger.warning(
                f"安全拦截：MIME 类型验证失败 - {mime_error}, 原始文件名：{file.name}, 用户：{request.get('auth_user', 'unknown')}"
            )
            return json(
                {
                    "code": 400,
                    "message": f"文件类型验证失败：{mime_error}",
                    "data": {
                        "detected_mime": detected_mime,
                        "allowed_mime_types": list(ALLOWED_MIME_TYPES),
                    },
                },
                status=400,
            )

        # ========== 步骤 6: 生成随机文件名并保存 ==========
        stored_filename, file_ext = generate_secure_filename(file.name)

        # 创建上传目录（按日期分目录）
        now = datetime.utcnow()
        upload_subdir = f"{now.year}/{now.month:02d}"
        upload_dir = Path(settings.file_storage_path) / upload_subdir
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / stored_filename

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file.body)

        # ========== 步骤 7: 构建响应数据 ==========
        relative_path = f"/uploads/{upload_subdir}/{stored_filename}"

        response_data = {
            "file_id": str(uuid.uuid4()),
            "filename": file.name,  # 保留原始文件名用于显示
            "stored_filename": stored_filename,  # 随机文件名用于存储
            "file_path": relative_path,
            "file_size": file_size,
            "file_type": detected_mime,  # 使用检测到的真实 MIME 类型
            "uploaded_at": now.isoformat(),
        }

        logger.info(
            f"📁 文件上传成功：{file.name} -> {relative_path}, "
            f"大小：{file_size} 字节，MIME: {detected_mime}"
        )

        return json({"code": 0, "message": "success", "data": response_data}, status=201)

    except Exception as e:
        logger.error(f"❌ 文件上传失败：{str(e)}")
        return json(
            {"code": 500, "message": f"文件上传失败：{str(e)}", "data": None},
            status=500,
        )


@files_bp.get("/<file_id:str>")
@auth_required
async def get_file_info(request, file_id: str):
    """
    获取文件信息

    注：实际项目中需要根据 file_id 查询数据库获取文件记录
    这里简化处理，仅作为示例
    """
    # TODO: 实现从数据库查询文件记录
    return json({"code": 404, "message": "文件未找到", "data": None}, status=404)


@files_bp.delete("/<file_id:str>")
@auth_required
async def delete_file(request, file_id: str):
    """
    删除文件

    注：实际项目中需要：
    1. 从数据库查询文件记录
    2. 检查权限
    3. 删除物理文件
    4. 删除数据库记录
    """
    # TODO: 实现完整的删除逻辑
    return json({"code": 404, "message": "文件未找到", "data": None}, status=404)
