"""用户管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.users import UserService
from ..middleware.auth import get_current_user, require_permission, auth_required
from ..cache.permissions import permission_cache
from ..models.billing import AuditLog
from ..models.users import Role
from sqlalchemy import select
import openpyxl
from io import BytesIO
from ..utils.audit_helpers import create_audit_entry, build_batch_audit_summary

users_bp = Blueprint("users", url_prefix="/api/v1/users")


@users_bp.get("")
@auth_required
@require_permission("users:view")
async def list_users(request: Request):
    """
    获取用户列表

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    - keyword: 搜索关键词 (可选)
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    keyword = request.args.get("keyword")

    # 限制 page_size 范围
    page_size = min(page_size, 100)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    users, total = await service.get_all_users(page=page, page_size=page_size, keyword=keyword)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "real_name": user.real_name,
                        "is_active": user.is_active,
                        "is_system": user.is_system,
                        "roles": [{"id": r.id, "name": r.name} for r in user.roles],
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                    }
                    for user in users
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@users_bp.get("/<user_id:int>")
@auth_required
@require_permission("users:view")
async def get_user(request: Request, user_id: int):
    """获取用户详情"""
    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    user = await service.get_user_by_id(user_id)

    if not user:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "real_name": user.real_name,
                "is_active": user.is_active,
                "is_system": user.is_system,
                "roles": [{"id": r.id, "name": r.name} for r in user.roles],
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
        }
    )


@users_bp.post("")
@auth_required
@require_permission("users:create")
async def create_user(request: Request):
    """
    创建用户

    Body:
    {
        "username": "string (required)",
        "password": "string (required)",
        "email": "string (optional)",
        "real_name": "string (optional)"
    }
    """
    data = request.json

    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    real_name = data.get("real_name")

    if not username or not password:
        return json({"code": 40001, "message": "用户名和密码不能为空"}, status=400)

    # 密码强度检查
    if len(password) < 6:
        return json({"code": 40002, "message": "密码长度不能少于 6 位"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    try:
        user = await service.create_user(
            username=username, password=password, email=email, real_name=real_name
        )
    except ValueError as e:
        return json({"code": 40003, "message": str(e)}, status=400)

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "real_name": user.real_name,
            },
        },
        status=201,
    )


@users_bp.put("/<user_id:int>")
@auth_required
@require_permission("users:edit")
async def update_user(request: Request, user_id: int):
    """
    更新用户信息

    Body:
    {
        "email": "string (optional)",
        "real_name": "string (optional)",
        "is_active": "boolean (optional)"
    }
    """
    data = request.json

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    user = await service.update_user(
        user_id=user_id,
        email=data.get("email"),
        real_name=data.get("real_name"),
        is_active=data.get("is_active"),
    )

    if not user:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "real_name": user.real_name,
                "is_active": user.is_active,
            },
        }
    )


@users_bp.delete("/<user_id:int>")
@auth_required
@require_permission("users:delete")
async def delete_user(request: Request, user_id: int):
    """删除用户（软删除）"""
    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    # 获取当前用户
    current_user = get_current_user(request)
    if current_user and user_id == current_user.get("user_id"):
        return json({"code": 40001, "message": "不能删除当前登录的用户"}, status=400)

    success = await service.delete_user(user_id)

    if not success:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    # 清除被删除用户的权限缓存
    await permission_cache.invalidate(user_id)

    return json({"code": 0, "message": "删除成功"})


@users_bp.post("/<user_id:int>/reset-password")
@auth_required
@require_permission("users:edit")
async def reset_password(request: Request, user_id: int):
    """
    重置用户密码

    Body:
    {
        "new_password": "string (required)"
    }
    """
    data = request.json
    new_password = data.get("new_password")

    if not new_password:
        return json({"code": 40001, "message": "新密码不能为空"}, status=400)

    if len(new_password) < 6:
        return json({"code": 40002, "message": "密码长度不能少于 6 位"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)
    current_user = get_current_user(request)

    success = await service.reset_password(user_id, new_password)

    if not success:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    # 记录敏感操作审计日志
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="reset_password",
        module="users",
        record_id=user_id,
        record_type="user",
        operation_type="sensitive",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": "密码重置成功"})


@users_bp.post("/<user_id:int>/roles")
@auth_required
@require_permission("users:role_assign")
async def assign_roles(request: Request, user_id: int):
    """
    为用户分配角色

    Body:
    {
        "role_ids": [1, 2, 3]
    }
    """
    data = request.json
    role_ids = data.get("role_ids", [])

    if not role_ids:
        return json({"code": 40001, "message": "角色 ID 列表不能为空"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    success = await service.assign_roles(user_id, role_ids)

    if not success:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    # 记录审计日志
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="assign_role",
        module="users",
        record_id=user_id,
        record_type="user-role",
        changes={"role_id": role_ids},
        operation_type="relation",
        extra_metadata={"role_ids": role_ids},
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": "角色分配成功"})


@users_bp.get("/<user_id:int>/roles")
@auth_required
@require_permission("users:view")
async def get_user_roles(request: Request, user_id: int):
    """获取用户角色"""
    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    roles = await service.get_user_roles(user_id)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [{"id": r.id, "name": r.name, "description": r.description} for r in roles],
        }
    )


@users_bp.post("/import")
@auth_required
@require_permission("users:create")
async def import_users(
    request: Request,
    db: AsyncSession = None,
    current_user: dict = None,
):
    """
    批量导入用户（从 Excel 文件）

    请求:
    - multipart/form-data
    - file: Excel 文件

    Excel 格式:
    - 列：用户名，邮箱，角色，初始密码

    响应:
    {
        "code": 0,
        "message": "成功导入 5 个用户",
        "data": {
            "imported_count": 5,
            "failed_count": 2,
            "errors": [
                {"row": 3, "username": "test", "error": "用户名已存在"},
                {"row": 5, "username": "", "error": "用户名不能为空"}
            ]
        }
    }
    """
    # 获取数据库会话和当前用户
    db_session: AsyncSession = request.ctx.db_session
    current_user = get_current_user(request)

    # 获取上传的文件
    file = request.files.get("file")
    if not file:
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)

    # 验证文件类型
    allowed_types = [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]
    if file.type not in allowed_types and not file.name.endswith((".xlsx", ".xls")):
        return json({"code": 40002, "message": "仅支持 Excel 文件 (.xlsx, .xls)"}, status=400)

    try:
        # 读取 Excel 文件
        workbook = openpyxl.load_workbook(BytesIO(file.body), read_only=True, data_only=True)
        sheet = workbook.active

        # 读取表头
        headers = []
        for cell in sheet[1]:
            headers.append(str(cell.value).strip() if cell.value else "")

        # 验证必需的列
        required_columns = ["用户名", "邮箱", "角色", "初始密码"]
        missing_columns = [col for col in required_columns if col not in headers]
        if missing_columns:
            return json(
                {
                    "code": 40003,
                    "message": f"Excel 缺少必需的列：{', '.join(missing_columns)}",
                },
                status=400,
            )

        # 获取列索引
        col_username = headers.index("用户名")
        col_email = headers.index("邮箱")
        col_role = headers.index("角色")
        col_password = headers.index("初始密码")

        # 导入结果统计
        imported_count = 0
        failed_count = 0
        errors = []

        # 批量验证和导入
        service = UserService(db_session)

        # 开始事务处理
        async with db_session.begin():
            for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                # 跳过空行
                if not any(cell for cell in row):
                    continue

                try:
                    # 提取数据
                    username = str(row[col_username]).strip() if row[col_username] else ""
                    email = str(row[col_email]).strip() if row[col_email] else ""
                    role_name = str(row[col_role]).strip() if row[col_role] else ""
                    password = str(row[col_password]).strip() if row[col_password] else ""

                    # 验证数据
                    if not username:
                        raise ValueError("用户名不能为空")

                    if not password:
                        raise ValueError("密码不能为空")

                    if len(password) < 6:
                        raise ValueError("密码长度不能少于 6 位")

                    if email and "@" not in email:
                        raise ValueError("邮箱格式不正确")

                    # 检查用户名是否已存在
                    existing_user = await service.get_user_by_username(username)
                    if existing_user:
                        raise ValueError("用户名已存在")

                    # 验证角色是否存在（如果指定了角色）
                    role_id = None
                    if role_name:
                        role_result = await db_session.execute(
                            select(Role).where(Role.name == role_name, Role.deleted_at.is_(None))
                        )
                        role = role_result.scalar_one_or_none()
                        if not role:
                            raise ValueError(f"角色 '{role_name}' 不存在")
                        role_id = role.id

                    # 创建用户
                    user = await service.create_user(
                        username=username,
                        password=password,
                        email=email,
                        real_name=None,
                    )

                    # 分配角色（如果指定了角色）
                    if role_id:
                        await service.assign_roles(user.id, [role_id])

                    # 记录审计日志
                    audit_log = AuditLog(
                        user_id=current_user["user_id"],
                        action="create",
                        module="users",
                        record_id=user.id,
                        record_type="user",
                        changes={
                            "after": {
                                "username": username,
                                "email": email,
                            },
                        },
                        ip_address=request.ip,
                    )
                    db_session.add(audit_log)

                    imported_count += 1

                except ValueError as e:
                    # 记录错误
                    failed_count += 1
                    username_val = str(row[col_username]).strip() if row[col_username] else "(空)"
                    errors.append({"row": row_idx, "username": username_val, "error": str(e)})
                except Exception as e:
                    # 记录未知错误
                    failed_count += 1
                    username_val = str(row[col_username]).strip() if row[col_username] else "(空)"
                    errors.append(
                        {
                            "row": row_idx,
                            "username": username_val,
                            "error": f"系统错误：{str(e)}",
                        }
                    )

            # 提交事务
            await db_session.commit()

        # 构建响应消息
        if imported_count > 0 and failed_count > 0:
            message = f"成功导入 {imported_count} 个用户，{failed_count} 个失败"
        elif imported_count > 0:
            message = f"成功导入 {imported_count} 个用户"
        else:
            message = f"导入失败，共 {failed_count} 个用户导入失败"

        # 记录批量导入汇总审计日志（与逐条审计并存）
        summary = build_batch_audit_summary(
            operation="user_import",
            total_count=imported_count + failed_count,
            success_count=imported_count,
            failed_count=failed_count,
            details=errors[:10],
        )

        await create_audit_entry(
            db_session=db_session,
            user_id=current_user.get("user_id") if current_user else None,
            action="batch_create",
            module="users",
            operation_type="batch",
            extra_metadata=summary,
            ip_address=request.headers.get(
                "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
            ),
            auto_commit=False,
        )

        return json(
            {
                "code": 0,
                "message": message,
                "data": {
                    "imported_count": imported_count,
                    "failed_count": failed_count,
                    "errors": errors,
                },
            }
        )

    except openpyxl.utils.exceptions.InvalidFileException:
        return json({"code": 40004, "message": "无效的 Excel 文件格式"}, status=400)
    except Exception as e:
        # 回滚事务（如果有的话）
        await db_session.rollback()
        return json({"code": 50001, "message": f"导入失败：{str(e)}"}, status=500)
