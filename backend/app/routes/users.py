"""用户管理路由"""

import asyncio
import logging
import math
import uuid
from io import BytesIO
from pathlib import Path

import magic
from PIL import Image
from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.permissions import permission_cache
from ..config import settings
from ..middleware.auth import auth_required, get_current_user, require_permission
from ..models.users import Role, User
from ..services.users import UserService
from ..utils.audit_helpers import build_batch_audit_summary, create_audit_entry
from ..utils.excel_export import excel_response
from ..utils.excel_import import read_import_dataframe
from ..utils.excel_template import template_response

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
                        "created_at": user.created_at.isoformat() if user.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                    }
                    for user in users
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@users_bp.get("/options")
@auth_required
async def list_user_options(request: Request):
    """获取用户下拉选项（id/username/real_name）

    提供给客户管理、分析、余额等业务的运营经理/销售经理下拉及姓名展示使用。
    仅需登录即可访问，不要求 users:view 权限——因为「查看客户经理姓名/下拉」
    是各业务模块的基础能力，不应受用户管理权限约束；否则非 admin 角色会因
    无 users:view 而无法显示经理姓名（曾出现选项为空、列表显示 #id 的问题）。
    返回结构与 GET /users 兼容（{list, total}），便于前端复用现有取列表逻辑。

    仅返回启用（is_active=True）用户，避免向普通业务用户暴露停用账号。
    支持 page/page_size 参数（page_size 上限 5000）；未显式传参时默认
    一次拉取全部（page_size=2000），total 与返回 list 长度一致，避免
    调用方误以为做了分页而实际拿到截断数据。
    """
    # 读取分页参数（上限保护，防止误传超大值拖垮查询）
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(int(request.args.get("page_size", 2000)), 5000)
        page_size = max(page_size, 1)
    except (ValueError, TypeError):
        page_size = 2000

    explicit_page_size = "page_size" in request.args

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)
    users, total = await service.get_all_users(page=page, page_size=page_size, active_only=True)
    # 下拉场景（未显式传 page_size）：total 与返回 list 一致，避免误导
    if not explicit_page_size:
        total = len(users)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": user.id,
                        "username": user.username,
                        "real_name": user.real_name,
                        "is_active": user.is_active,
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
                "created_at": user.created_at.isoformat() if user.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
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
        changes={
            "before": {"password_hash": "***MASKED***"},
            "after": {"password_hash": "***RESET***"},
        },
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
    current_user = get_current_user(request)

    success = await service.assign_roles(user_id, role_ids)

    if not success:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    # 失效该用户的权限缓存，使角色变更立即生效
    # （PermissionCache TTL=600s，不失效则已登录用户最长 10 分钟才看到新角色权限）
    await permission_cache.invalidate(user_id)

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
@require_permission("users:import")
async def import_users(request: Request):
    """
    批量导入用户（从 Excel 文件，英文表头 + dry_run 预检查）

    请求:
    - multipart/form-data，字段名 file
    - ?dry_run=true：完整行级校验但不落库

    Excel 格式（第 1 行英文列名，第 2 行中文说明行由 read_import_dataframe 自动剥离）:
    - username: 用户名（必填，唯一）
    - email: 邮箱（可选）
    - real_name: 真实姓名（可选）
    - role: 角色名（可选，多个用逗号分隔）
    - initial_password: 初始密码（必填，>=6 位）

    响应（dry_run 时 data 带 dry_run: true 且 errors 最多 50 条；正式导入 errors 最多 10 条）:
    {
        "code": 0,
        "message": "导入完成",
        "data": {
            "success_count": 3,
            "error_count": 1,
            "errors": ["第 4 行：用户名 'zhangsan' 已存在"]
        }
    }
    """
    files = request.files
    if "file" not in files:  # pyright: ignore[reportOperatorIssue]
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)
    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    current_user = get_current_user(request)
    service = UserService(db_session)

    try:
        df = await asyncio.to_thread(read_import_dataframe, excel_file.body, "username")
        required_columns = ["username", "initial_password"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {"code": 40003, "message": f"Excel 缺少必填列：{', '.join(missing_columns)}"},
                status=400,
            )
        records = df.to_dict(orient="records")
        # read_import_dataframe 保留索引标签（第 i 行数据 = Excel 第 i+2 行），
        # to_dict 丢弃索引，这里把真实行号写回每条记录供行级错误使用
        for idx, record in zip(df.index, records):
            record["_row_num"] = int(idx) + 2

        dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes", "on")

        def cell(record: dict, key: str) -> str:
            """取单元格并归一化：NaN/None -> 空串，其余 strip 后转字符串"""
            value = record.get(key)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return ""
            return str(value).strip()

        # 批量存在性查询（避免 N+1）：
        # - 用户名查重含软删记录（唯一索引对软删记录仍生效，漏查会在落库时撞约束 500）
        # - 角色按 name 解析（仅未删角色）
        usernames = {cell(r, "username") for r in records} - {""}
        role_names: set[str] = set()
        for r in records:
            role_text = cell(r, "role")
            if role_text:
                role_names.update(name.strip() for name in role_text.split(",") if name.strip())

        existing_usernames: set[str] = set()
        if usernames:
            result = await db_session.execute(
                select(User.username).where(User.username.in_(usernames))
            )
            existing_usernames = {row[0] for row in result.all()}

        existing_roles: dict[str, int] = {}
        if role_names:
            result = await db_session.execute(
                select(Role.id, Role.name).where(
                    Role.name.in_(role_names), Role.deleted_at.is_(None)
                )
            )
            existing_roles = {name: rid for rid, name in result.all()}

        # 行级预检（只读，事务外）：行级错误不阻塞其他行
        valid_rows: list[dict] = []
        errors: list[str] = []
        seen_usernames: set[str] = set()
        for record in records:
            row_num = record["_row_num"]
            username = cell(record, "username")
            email = cell(record, "email")
            real_name = cell(record, "real_name")
            role_text = cell(record, "role")
            password = cell(record, "initial_password")

            if not username:
                errors.append(f"第 {row_num} 行：用户名不能为空")
                continue
            if not password:
                errors.append(f"第 {row_num} 行：初始密码不能为空")
                continue
            if len(password) < 6:
                errors.append(f"第 {row_num} 行：密码长度不能少于 6 位")
                continue
            if email and "@" not in email:
                errors.append(f"第 {row_num} 行：邮箱格式不正确")
                continue
            # 查重含软删记录 + 同批次重复（create_user 落库时同样查重，提前行级报错避免整事务回滚）
            if username in existing_usernames or username in seen_usernames:
                errors.append(f"第 {row_num} 行：用户名 '{username}' 已存在")
                continue
            seen_usernames.add(username)

            # 角色解析：逗号分隔多角色，任一不存在整行报错
            role_ids: list[int] = []
            role_error: str | None = None
            if role_text:
                for name in (n.strip() for n in role_text.split(",")):
                    if not name:
                        continue
                    if name not in existing_roles:
                        role_error = f"第 {row_num} 行：角色 '{name}' 不存在"
                        break
                    role_ids.append(existing_roles[name])
            if role_error:
                errors.append(role_error)
                continue

            valid_rows.append(
                {
                    "username": username,
                    "password": password,
                    "email": email or None,
                    "real_name": real_name or None,
                    "role_ids": role_ids,
                }
            )

        if dry_run:
            return json(
                {
                    "code": 0,
                    "message": "预检查完成",
                    "data": {
                        "dry_run": True,
                        "success_count": len(valid_rows),
                        "error_count": len(errors),
                        "errors": errors[:50],  # 预检阶段展示更多错误便于确认
                    },
                }
            )

        # 预检阶段的只读查询已触发 autobegin 隐式事务，先 commit 断开，
        # 否则下方 begin() 抛 InvalidRequestError: A transaction is already begun
        # （SQLAlchemy 2.0 语义：首次 execute 即开启事务）
        await db_session.commit()

        # 正式落库：create_user/assign_roles 内部仅 flush，由事务统一提交
        async with db_session.begin():
            for row in valid_rows:
                user = await service.create_user(
                    username=row["username"],
                    password=row["password"],
                    email=row["email"],
                    real_name=row["real_name"],
                )
                if row["role_ids"]:
                    await service.assign_roles(user.id, row["role_ids"])

        # 批量导入汇总审计（与客户页导入模式一致）
        summary = build_batch_audit_summary(
            operation="user_import",
            total_count=len(valid_rows) + len(errors),
            success_count=len(valid_rows),
            failed_count=len(errors),
            details=errors[:10],
        )
        await create_audit_entry(
            db_session=db_session,
            user_id=current_user.get("user_id") if current_user else None,
            action="batch_create",
            module="users",
            record_id=None,  # 批量操作
            record_type="user",
            changes={"after": {"count": len(valid_rows)}},
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
                "message": "导入完成",
                "data": {
                    "success_count": len(valid_rows),
                    "error_count": len(errors),
                    "errors": errors[:10],  # 最多返回 10 条错误信息
                },
            }
        )

    except Exception:
        logger.exception("用户导入失败")
        return json({"code": 50001, "message": "导入失败，请稍后重试"}, status=500)


@users_bp.get("/import-template")
@auth_required
@require_permission("users:import")
async def download_user_import_template(request: Request):
    """下载用户导入模板（英文表头 + 中文说明行）"""
    columns = [
        ("username", "必填：用户名（唯一），如 zhangsan"),
        ("email", "可选：邮箱"),
        ("real_name", "可选：真实姓名"),
        ("role", "可选：角色名（多个用逗号分隔）"),
        ("initial_password", "必填：初始密码（>=6 位）"),
    ]
    return await asyncio.to_thread(template_response, columns, "用户导入模板.xlsx")


@users_bp.get("/export")
@auth_required
@require_permission("users:export")
async def export_users(request: Request):
    """
    导出用户列表为 Excel

    Query:
    - keyword: 搜索关键词（可选，匹配用户名/姓名/邮箱）

    按当前筛选条件全量导出（上限 50000 条，与列表页口径一致）。
    """
    keyword = request.args.get("keyword")

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    users, total = await service.get_all_users(page=1, page_size=50000, keyword=keyword)

    records = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "real_name": u.real_name,
            "is_active": "是" if u.is_active else "否",
            "roles": ",".join(r.name for r in u.roles),
            "phone": u.phone,
            "created_at": u.created_at.isoformat() if u.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
        for u in users
    ]
    return await asyncio.to_thread(excel_response, records, "用户列表", "users", total)


@users_bp.get("/profile")
@auth_required
async def get_profile(request: Request):
    """获取当前登录用户的个人信息"""
    current_user = get_current_user(request)
    if not current_user:
        return json({"code": 40101, "message": "未登录"}, status=401)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    profile = await service.get_profile(current_user["user_id"])
    if not profile:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json({"code": 0, "message": "success", "data": profile})


@users_bp.put("/profile")
@auth_required
async def update_profile(request: Request):
    """更新当前登录用户的个人信息"""
    current_user = get_current_user(request)
    if not current_user:
        return json({"code": 40101, "message": "未登录"}, status=401)

    data = request.json
    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    # 邮箱格式验证
    email = data.get("email")
    if email and "@" not in email:
        return json({"code": 40001, "message": "邮箱格式不正确"}, status=400)

    # 手机号格式验证
    phone = data.get("phone")
    if phone and (not phone.isdigit() or len(phone) != 11):
        return json({"code": 40002, "message": "手机号格式不正确"}, status=400)

    profile = await service.update_profile(
        current_user["user_id"],
        email=email,
        phone=phone,
        avatar_url=data.get("avatar_url"),
        real_name=data.get("real_name"),
    )
    if not profile:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    await db_session.commit()
    return json({"code": 0, "message": "更新成功", "data": profile})


@users_bp.put("/password")
@auth_required
async def change_password(request: Request):
    """修改当前登录用户的密码"""
    current_user = get_current_user(request)
    if not current_user:
        return json({"code": 40101, "message": "未登录"}, status=401)

    data = request.json
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return json({"code": 40001, "message": "当前密码和新密码不能为空"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    success, message = await service.change_password(
        current_user["user_id"], current_password, new_password
    )

    if not success:
        status_code = 400 if "密码" in message else 404
        return json({"code": 40002, "message": message}, status=status_code)

    await db_session.commit()

    # 记录敏感操作审计日志
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id"),
        action="change_password",
        module="users",
        record_id=current_user["user_id"],
        record_type="user",
        operation_type="sensitive",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


# 头像专用配置
AVATAR_MAX_SIZE = 2 * 1024 * 1024  # 2MB
AVATAR_MAX_DIMENSION = 1024  # 最大宽高
AVATAR_SUBDIR = "avatars"

ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_AVATAR_MIME_TYPES = {"image/jpeg", "image/png"}

logger = logging.getLogger(__name__)


@users_bp.post("/avatar")
@auth_required
async def upload_avatar(request: Request):
    """
    上传用户头像

    Request:
        multipart/form-data with field 'file'

    Response:
        {
            "code": 0,
            "data": {
                "avatar_url": "/uploads/avatars/1_uuid.jpg"
            }
        }
    """
    # 步骤 1: 检查文件是否存在
    if not request.files or "file" not in request.files:
        return json({"code": 40001, "message": "未找到上传文件"}, status=400)

    file_list = request.files["file"]
    file = file_list[0] if isinstance(file_list, list) else file_list

    # 步骤 2: 检查文件名
    if not file.name:
        return json({"code": 40002, "message": "文件名不能为空"}, status=400)

    # 步骤 3: 扩展名白名单
    ext = Path(file.name).suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        return json(
            {
                "code": 40003,
                "message": f"不支持的文件类型：{ext}，仅支持 .jpg/.jpeg/.png",
            },
            status=400,
        )

    # 步骤 4: 文件大小检查
    file_size = len(file.body)
    if file_size > AVATAR_MAX_SIZE:
        return json(
            {
                "code": 40004,
                "message": f"文件大小超过限制 ({AVATAR_MAX_SIZE / 1024 / 1024}MB)",
            },
            status=400,
        )

    # 步骤 5: MIME 类型验证
    try:
        detected_mime = magic.from_buffer(file.body, mime=True)
        if detected_mime not in ALLOWED_AVATAR_MIME_TYPES:
            return json(
                {"code": 40005, "message": f"不允许的文件类型：{detected_mime}"},
                status=400,
            )
    except Exception as e:
        logger.error(f"MIME 类型检测失败：{str(e)}")
        return json({"code": 50001, "message": "文件类型检测失败"}, status=500)

    # 步骤 6: 使用 Pillow 处理图片（验证 + 压缩）
    try:
        img = Image.open(BytesIO(file.body))
        img.verify()
        # 重新打开（verify 后图片已消耗）
        img = Image.open(BytesIO(file.body))

        # 转换为 RGB（处理 RGBA/P 模式）
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
            ext = ".jpg"  # 转换后使用 JPEG 格式

        # 等比缩放：最大边不超过 AVATAR_MAX_DIMENSION
        width, height = img.size
        if width > AVATAR_MAX_DIMENSION or height > AVATAR_MAX_DIMENSION:
            ratio = AVATAR_MAX_DIMENSION / max(width, height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)  # pyright: ignore[reportAttributeAccessIssue]

        # 保存到内存 buffer
        output_buffer = BytesIO()
        if ext == ".png":
            img.save(output_buffer, format="PNG", optimize=True)
        else:
            img.save(output_buffer, format="JPEG", quality=85, optimize=True)
        processed_data = output_buffer.getvalue()

    except Exception as e:
        logger.error(f"图片处理失败：{str(e)}")
        return json(
            {"code": 40006, "message": "图片处理失败，请上传有效的图片文件"},
            status=400,
        )

    # 步骤 7: 删除旧头像文件
    current_user = get_current_user(request)
    user_id = current_user.get("user_id")  # pyright: ignore[reportOptionalMemberAccess]

    db_session = request.ctx.db_session
    user_result = await db_session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if user and user.avatar_url:
        old_path = (Path(settings.file_storage_path) / user.avatar_url.lstrip("/")).resolve()
        storage_root = Path(settings.file_storage_path).resolve()
        if str(old_path).startswith(str(storage_root)):
            try:
                if old_path.exists():
                    old_path.unlink()
                    logger.info(f"旧头像已删除：{old_path}")
            except Exception as e:
                logger.warning(f"删除旧头像失败：{str(e)}")
        else:
            logger.warning(f"旧头像路径非法：{old_path}")

    # 步骤 8: 生成文件名并保存
    avatar_dir = Path(settings.file_storage_path) / AVATAR_SUBDIR
    avatar_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = avatar_dir / stored_filename

    with open(file_path, "wb") as f:
        f.write(processed_data)

    # 步骤 9: 更新用户 avatar_url
    avatar_url = f"/uploads/{AVATAR_SUBDIR}/{stored_filename}"
    user.avatar_url = avatar_url
    await db_session.commit()

    logger.info(f"头像上传成功：用户 {user_id}, 路径 {avatar_url}")

    return json({"code": 0, "message": "success", "data": {"avatar_url": avatar_url}})


# ==================== 偏好设置 ====================


@users_bp.get("/me/preferences")
@auth_required
async def get_user_preferences(request: Request):
    """获取当前用户偏好设置"""
    user_id = request.ctx.user["user_id"]
    db: AsyncSession = request.ctx.db_session

    user = await db.get(User, user_id)
    if not user:
        return json({"code": 404, "message": "User not found"}, status=404)

    # 从用户扩展字段获取偏好设置
    import json as json_mod

    prefs_raw = getattr(user, "preferences", None)
    if prefs_raw:
        try:
            prefs = json_mod.loads(prefs_raw) if isinstance(prefs_raw, str) else prefs_raw
        except (json_mod.JSONDecodeError, TypeError):
            prefs = {}
    else:
        prefs = {}

    # 默认偏好
    defaults = {
        "theme": "light",
        "language": "zh-CN",
        "notifications": {
            "email": True,
            "low_balance": True,
            "sync_error": True,
        },
    }
    # 合并默认值
    for k, v in defaults.items():
        if k not in prefs:
            prefs[k] = v

    return json({"code": 0, "data": prefs})


@users_bp.put("/me/preferences")
@auth_required
async def update_user_preferences(request: Request):
    """更新当前用户偏好设置"""
    import json as json_mod

    user_id = request.ctx.user["user_id"]
    db: AsyncSession = request.ctx.db_session

    user = await db.get(User, user_id)
    if not user:
        return json({"code": 404, "message": "User not found"}, status=404)

    data = request.json or {}

    # 获取现有偏好
    prefs_raw = getattr(user, "preferences", None)
    if prefs_raw:
        try:
            prefs = json_mod.loads(prefs_raw) if isinstance(prefs_raw, str) else prefs_raw
        except (json_mod.JSONDecodeError, TypeError):
            prefs = {}
    else:
        prefs = {}

    # 合并新偏好
    prefs.update(data)

    # 保存
    setattr(user, "preferences", json_mod.dumps(prefs, ensure_ascii=False))
    async with db.begin():
        pass  # user already modified

    return json({"code": 0, "message": "偏好设置已更新", "data": prefs})
