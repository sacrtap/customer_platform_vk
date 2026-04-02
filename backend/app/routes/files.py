"""
P6-9: 文件上传 API
支持 xlsx/png/jpg 等文件格式
"""

import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from sanic import Blueprint
from sanic.response import json
from sanic.request import File

from ..middleware.auth import auth_required
from ..config import settings

logger = logging.getLogger(__name__)

files_bp = Blueprint("files", url_prefix="/api/v1/files")

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    # Excel
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    # 图片
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    # PDF
    ".pdf": "application/pdf",
    # 其他
    ".csv": "text/csv",
    ".txt": "text/plain",
}

# 最大文件大小 (10MB)
MAX_FILE_SIZE = settings.max_file_size


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def generate_unique_filename(original_filename: str) -> str:
    """生成唯一文件名"""
    ext = Path(original_filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return unique_name


@files_bp.post("/upload")
@auth_required
async def upload_file(request):
    """
    上传文件

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
        # 检查是否有文件
        if not request.files or "file" not in request.files:
            return json(
                {"code": 400, "message": "未找到上传文件", "data": None}, status=400
            )

        file: File = request.files["file"]

        # 检查文件名
        if not file.name:
            return json(
                {"code": 400, "message": "文件名不能为空", "data": None}, status=400
            )

        # 检查文件扩展名
        if not allowed_file(file.name):
            ext = Path(file.name).suffix.lower()
            return json(
                {
                    "code": 400,
                    "message": f"不支持的文件类型：{ext}",
                    "data": {"allowed_extensions": list(ALLOWED_EXTENSIONS.keys())},
                },
                status=400,
            )

        # 检查文件大小
        if len(file.body) > MAX_FILE_SIZE:
            return json(
                {
                    "code": 400,
                    "message": f"文件大小超过限制 ({MAX_FILE_SIZE / 1024 / 1024}MB)",
                    "data": None,
                },
                status=400,
            )

        # 创建上传目录（按日期分目录）
        now = datetime.utcnow()
        upload_subdir = f"{now.year}/{now.month:02d}"
        upload_dir = Path(settings.file_storage_path) / upload_subdir
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        stored_filename = generate_unique_filename(file.name)
        file_path = upload_dir / stored_filename

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file.body)

        # 构建响应数据
        relative_path = f"/uploads/{upload_subdir}/{stored_filename}"

        response_data = {
            "file_id": str(uuid.uuid4()),
            "filename": file.name,
            "stored_filename": stored_filename,
            "file_path": relative_path,
            "file_size": len(file.body),
            "file_type": ALLOWED_EXTENSIONS.get(
                Path(file.name).suffix.lower(), "application/octet-stream"
            ),
            "uploaded_at": now.isoformat(),
        }

        logger.info(f"📁 文件上传成功：{file.name} -> {relative_path}")

        return json(
            {"code": 0, "message": "success", "data": response_data}, status=201
        )

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
