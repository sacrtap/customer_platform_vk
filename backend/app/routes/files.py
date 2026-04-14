"""
P6-9: 文件管理 API（安全增强版）
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
import hashlib
from datetime import datetime
from pathlib import Path
from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import auth_required, require_permission, get_current_user
from ..config import settings
from ..models.billing import AuditLog
from ..models.files import File

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
            # 特殊处理：.xls 可能检测为不同 MIME 类型
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

        # ========== 步骤 7: 计算文件哈希值（用于去重）==========
        file_hash = hashlib.sha256(file.body).hexdigest()

        # ========== 步骤 8: 保存到数据库 ==========
        db_session: AsyncSession = request.ctx.db_session
        current_user = get_current_user(request)
        user_id = current_user.get("user_id")

        file_record = File(
            filename=file.name,
            stored_filename=stored_filename,
            file_path=f"/uploads/{upload_subdir}/{stored_filename}",
            file_size=file_size,
            file_type=detected_mime,
            uploaded_by=user_id,
            file_hash=file_hash,
        )
        db_session.add(file_record)

        # 记录审计日志
        audit_log = AuditLog(
            user_id=user_id,
            action="FILE_UPLOAD",
            module="files",
            record_id=None,  # 将在 flush 后获取
            record_type="file",
            changes={
                "action": "upload",
                "filename": file.name,
                "file_size": file_size,
                "file_type": detected_mime,
            },
            ip_address=request.ip,
        )
        db_session.add(audit_log)

        # 提交事务以获取 file_record.id
        await db_session.commit()

        # ========== 步骤 9: 构建响应数据 ==========
        response_data = {
            "file_id": file_record.id,
            "filename": file.name,
            "stored_filename": stored_filename,
            "file_path": f"/uploads/{upload_subdir}/{stored_filename}",
            "file_size": file_size,
            "file_type": detected_mime,
            "uploaded_at": now.isoformat(),
        }

        logger.info(
            f"📁 文件上传成功：{file.name} -> {response_data['file_path']}, "
            f"大小：{file_size} 字节，MIME: {detected_mime}, 用户：{user_id}"
        )

        return json({"code": 0, "message": "success", "data": response_data}, status=201)

    except Exception as e:
        # 回滚事务
        if hasattr(request.ctx, "db_session"):
            await request.ctx.db_session.rollback()
        logger.error(f"❌ 文件上传失败：{str(e)}")
        return json(
            {"code": 500, "message": f"文件上传失败：{str(e)}", "data": None},
            status=500,
        )


@files_bp.get("")
@auth_required
@require_permission("files:view")
async def list_files(request: Request):
    """
    获取文件列表（支持分页和筛选）

    Query Parameters:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20, 最大 100)
    - file_type: 文件类型筛选 (可选)

    Response:
    {
        "code": 0,
        "message": "success",
        "data": {
            "items": [...],
            "total": 100,
            "page": 1,
            "page_size": 20
        }
    }
    """
    try:
        # 解析分页参数
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        page_size = min(page_size, 100)  # 限制最大每页数量

        # 获取筛选参数
        file_type = request.args.get("file_type")

        # 获取数据库会话
        db_session: AsyncSession = request.ctx.db_session
        current_user = get_current_user(request)

        # 构建查询条件
        conditions = [File.deleted_at.is_(None)]

        # 文件类型筛选
        if file_type:
            conditions.append(File.file_type == file_type)

        # 查询总数
        count_stmt = select(func.count()).select_from(File).where(and_(*conditions))
        result = await db_session.execute(count_stmt)
        total = result.scalar()

        # 分页查询
        offset = (page - 1) * page_size
        stmt = (
            select(File)
            .where(and_(*conditions))
            .order_by(File.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await db_session.execute(stmt)
        files = result.scalars().all()

        # 构建响应数据
        items = []
        for f in files:
            items.append(
                {
                    "id": f.id,
                    "filename": f.filename,
                    "stored_filename": f.stored_filename,
                    "file_path": f.file_path,
                    "file_size": f.file_size,
                    "file_type": f.file_type,
                    "uploaded_by": f.uploaded_by,
                    "business_type": f.business_type,
                    "business_id": f.business_id,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                    "updated_at": f.updated_at.isoformat() if f.updated_at else None,
                }
            )

        response_data = {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

        logger.info(
            f"📋 文件列表查询成功：用户 {current_user.get('user_id')}, "
            f"页码 {page}, 每页 {page_size}, 总数 {total}"
        )

        return json({"code": 0, "message": "success", "data": response_data})

    except ValueError as e:
        logger.error(f"❌ 文件列表查询参数错误：{str(e)}")
        return json({"code": 400, "message": f"参数错误：{str(e)}", "data": None}, status=400)
    except Exception as e:
        logger.error(f"❌ 文件列表查询失败：{str(e)}")
        return json({"code": 500, "message": f"查询失败：{str(e)}", "data": None}, status=500)


@files_bp.get("/<file_id:int>")
@auth_required
@require_permission("files:view")
async def get_file(file_id: int, request: Request):
    """
    获取文件详情

    Path Parameters:
    - file_id: 文件 ID

    Response:
    {
        "code": 0,
        "message": "success",
        "data": {
            "id": 1,
            "filename": "original.xlsx",
            "stored_filename": "uuid.xlsx",
            "file_path": "/uploads/2024/01/uuid.xlsx",
            "file_size": 1024,
            "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "uploaded_by": 1,
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:00:00"
        }
    }
    """
    try:
        db_session: AsyncSession = request.ctx.db_session
        current_user = get_current_user(request)

        # 查询文件
        stmt = select(File).where(and_(File.id == file_id, File.deleted_at.is_(None)))
        result = await db_session.execute(stmt)
        file_record = result.scalar_one_or_none()

        if not file_record:
            logger.warning(f"⚠️ 文件未找到：ID={file_id}, 用户={current_user.get('user_id')}")
            return json({"code": 404, "message": "文件未找到", "data": None}, status=404)

        # 构建响应数据
        file_data = {
            "id": file_record.id,
            "filename": file_record.filename,
            "stored_filename": file_record.stored_filename,
            "file_path": file_record.file_path,
            "file_size": file_record.file_size,
            "file_type": file_record.file_type,
            "uploaded_by": file_record.uploaded_by,
            "business_type": file_record.business_type,
            "business_id": file_record.business_id,
            "file_hash": file_record.file_hash,
            "created_at": file_record.created_at.isoformat() if file_record.created_at else None,
            "updated_at": file_record.updated_at.isoformat() if file_record.updated_at else None,
        }

        logger.info(f"📄 文件详情查询成功：ID={file_id}, 用户={current_user.get('user_id')}")

        return json({"code": 0, "message": "success", "data": file_data})

    except Exception as e:
        logger.error(f"❌ 文件详情查询失败：ID={file_id}, 错误={str(e)}")
        return json({"code": 500, "message": f"查询失败：{str(e)}", "data": None}, status=500)


@files_bp.delete("/<file_id:int>")
@auth_required
@require_permission("files:delete")
async def delete_file(file_id: int, request: Request):
    """
    删除文件

    删除流程：
    1. 查询文件记录
    2. 删除物理文件
    3. 软删除数据库记录
    4. 记录审计日志

    Path Parameters:
    - file_id: 文件 ID
    """
    try:
        db_session: AsyncSession = request.ctx.db_session
        current_user = get_current_user(request)
        user_id = current_user.get("user_id")

        # 查询文件
        stmt = select(File).where(and_(File.id == file_id, File.deleted_at.is_(None)))
        result = await db_session.execute(stmt)
        file_record = result.scalar_one_or_none()

        if not file_record:
            logger.warning(f"⚠️ 文件未找到：ID={file_id}, 用户={user_id}")
            return json({"code": 404, "message": "文件未找到", "data": None}, status=404)

        # 删除物理文件
        file_path = Path(settings.file_storage_path) / file_record.file_path.lstrip("/uploads/")
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"🗑️ 物理文件已删除：{file_path}")
            else:
                logger.warning(f"⚠️ 物理文件不存在：{file_path}")
        except Exception as e:
            logger.error(f"❌ 删除物理文件失败：{file_path}, 错误={str(e)}")
            # 继续删除数据库记录，但记录警告

        # 软删除数据库记录
        file_record.deleted_at = datetime.utcnow()
        await db_session.merge(file_record)

        # 记录审计日志
        audit_log = AuditLog(
            user_id=user_id,
            action="FILE_DELETE",
            module="files",
            record_id=file_id,
            record_type="file",
            changes={
                "action": "delete",
                "filename": file_record.filename,
                "file_path": file_record.file_path,
                "file_size": file_record.file_size,
            },
            ip_address=request.ip,
        )
        db_session.add(audit_log)

        # 提交事务
        await db_session.commit()

        logger.info(f"✅ 文件删除成功：ID={file_id}, 文件名={file_record.filename}, 用户={user_id}")

        return json({"code": 0, "message": "success", "data": {"deleted_id": file_id}})

    except Exception as e:
        # 回滚事务
        await db_session.rollback()
        logger.error(f"❌ 文件删除失败：ID={file_id}, 错误={str(e)}")
        return json({"code": 500, "message": f"删除失败：{str(e)}", "data": None}, status=500)
