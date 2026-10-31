# -*- coding: utf-8 -*-
"""角色管理路由"""

import asyncio
import logging

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..middleware.auth import auth_required, get_current_user, require_permission
from ..models.users import Role, role_permissions
from ..services.roles import RoleService
from ..utils.audit_helpers import build_batch_audit_summary, create_audit_entry
from ..utils.excel_export import excel_response
from ..utils.excel_import import read_import_dataframe
from ..utils.excel_template import template_response

logger = logging.getLogger(__name__)

roles_bp = Blueprint("roles", url_prefix="/api/v1/roles")


@roles_bp.get("")
@auth_required
@require_permission("roles:view")
async def list_roles(request: Request):
    """
    获取角色列表

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    # 限制 page_size 范围
    page_size = min(page_size, 100)

    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    roles, total = await service.get_all_roles(page=page, page_size=page_size)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": role.id,
                        "name": role.name,
                        "description": role.description,
                        "is_system": role.is_system,
                        "created_at": role.created_at.isoformat() if role.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                    }
                    for role in roles
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@roles_bp.get("/<role_id:int>")
@auth_required
@require_permission("roles:view")
async def get_role(request: Request, role_id: int):
    """获取角色详情"""
    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    role = await service.get_role_by_id(role_id)

    if not role:
        return json({"code": 40401, "message": "角色不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "permissions": [
                    {"id": p.id, "code": p.code, "name": p.name} for p in role.permissions
                ],
                "created_at": role.created_at.isoformat() if role.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            },
        }
    )


@roles_bp.post("")
@require_permission("roles:create")
async def create_role(request: Request):
    """
    创建角色

    Body:
    {
        "name": "string (required)",
        "description": "string (optional)",
        "permission_ids": [1, 2, 3] (optional)
    }
    """
    data = request.json

    name = data.get("name")
    description = data.get("description", "")
    permission_ids = data.get("permission_ids", [])

    if not name:
        return json({"code": 40001, "message": "角色名称不能为空"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    try:
        role = await service.create_role(
            name=name, description=description, permission_ids=permission_ids
        )
    except ValueError as e:
        return json({"code": 40002, "message": str(e)}, status=400)

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
            },
        },
        status=201,
    )


@roles_bp.put("/<role_id:int>")
@require_permission("roles:edit")
async def update_role(request: Request, role_id: int):
    """
    更新角色信息

    Body:
    {
        "name": "string (optional)",
        "description": "string (optional)",
        "permission_ids": [1, 2, 3] (optional)
    }
    """
    data = request.json

    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    try:
        role = await service.update_role(
            role_id=role_id,
            name=data.get("name"),
            description=data.get("description"),
            permission_ids=data.get("permission_ids"),
        )
    except ValueError as e:
        return json({"code": 40001, "message": str(e)}, status=400)

    if not role:
        return json({"code": 40401, "message": "角色不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
            },
        }
    )


@roles_bp.delete("/<role_id:int>")
@require_permission("roles:delete")
async def delete_role(request: Request, role_id: int):
    """删除角色（软删除）"""
    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    # 检查是否是系统角色
    role = await service.get_role_by_id(role_id)
    if role and role.is_system:  # pyright: ignore[reportGeneralTypeIssues]
        return json({"code": 40001, "message": "系统角色不能删除"}, status=400)

    success = await service.delete_role(role_id)

    if not success:
        return json({"code": 40401, "message": "角色不存在"}, status=404)

    return json({"code": 0, "message": "删除成功"})


@roles_bp.post("/<role_id:int>/permissions")
@require_permission("roles:assign")
async def assign_permissions(request: Request, role_id: int):
    """
    为角色分配权限

    Body:
    {
        "permission_ids": [1, 2, 3]
    }
    """
    data = request.json
    permission_ids = data.get("permission_ids", [])

    if not permission_ids:
        return json({"code": 40001, "message": "权限 ID 列表不能为空"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    success = await service.assign_permissions(role_id, permission_ids)

    if not success:
        return json({"code": 40401, "message": "角色不存在"}, status=404)

    # 失效该角色下所有用户的权限缓存，使权限变更立即生效
    # （权限缓存 TTL=600s，不失效则已登录用户最长 10 分钟才看到新权限）
    # import 与用户查询属于编程/数据错误面，不应被吞：仅在缓存失效这一可能
    # 失败的运行时操作上包裹 try，且失效失败需记 error 日志以暴露问题。
    from sqlalchemy import select

    from ..cache.permissions import permission_cache
    from ..models.users import User, user_roles

    user_ids = (
        (
            await db_session.execute(
                select(User.id)
                .join(user_roles, user_roles.c.user_id == User.id)
                .where(user_roles.c.role_id == role_id)
            )
        )
        .scalars()
        .all()
    )
    try:
        # 逐用户失效在用户较多时会串行拉长请求，改为并发失效
        await asyncio.gather(*(permission_cache.invalidate(uid) for uid in user_ids))
    except Exception as e:  # 缓存失效失败不应阻塞主流程
        import logging

        logging.getLogger(__name__).error(f"失效角色权限缓存失败 role_id={role_id}: {e}")

    return json({"code": 0, "message": "权限分配成功"})


# ==================== 角色导入导出 ====================


@roles_bp.get("/export")
@auth_required
@require_permission("roles:export")
async def export_roles(request: Request):
    """导出角色列表为 Excel（全量，上限 50000 条）

    RoleService.get_all_roles 未对 Role.permissions 做 eager load，导出端点访问
    role.permissions 关系会触发逐行懒加载（N+1）。这里用 selectinload 重新查询
    并展开权限，避免在事件循环中串行发起 N 次关联查询。
    """
    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    # service.get_all_roles 不带 selectinload，重新以 eager load 查询全量角色
    roles, total = await service.get_all_roles(page=1, page_size=50000)
    if roles:
        result = await db_session.execute(
            select(Role).options(selectinload(Role.permissions)).order_by(Role.id)
        )
        roles = list(result.scalars().all())

    records = [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "is_system": "是" if r.is_system else "否",
            "permissions": ",".join(p.code for p in r.permissions),
        }
        for r in roles
    ]
    return await asyncio.to_thread(excel_response, records, "角色", "roles", total)


@roles_bp.get("/import-template")
@auth_required
@require_permission("roles:import")
async def download_role_import_template(request: Request):
    """下载角色导入模板（英文表头 + 中文说明行）"""
    columns = [
        ("name", "必填：角色名（唯一），如 客户专员"),
        ("description", "可选：角色描述"),
        ("permissions", "可选：权限码，逗号分隔，如 customers:view,customers:edit"),
    ]
    return await asyncio.to_thread(template_response, columns, "角色导入模板.xlsx")


@roles_bp.post("/import")
@auth_required
@require_permission("roles:import")
async def import_roles(request: Request):
    """
    批量导入角色（从 Excel 文件，英文表头 + dry_run 预检查）

    请求:
    - multipart/form-data，字段名 file
    - ?dry_run=true：完整行级校验但不落库

    Excel 格式（第 1 行英文列名，第 2 行中文说明行由 read_import_dataframe 自动剥离）:
    - name: 角色名（必填，唯一）
    - description: 角色描述（可选）
    - permissions: 权限码，逗号分隔（可选）

    is_system 列即使存在也忽略：导入不可创建系统角色，强制 False。

    响应（dry_run 时 data 带 dry_run: true 且 errors 最多 50 条；正式导入 errors 最多 10 条）:
    {
        "code": 0,
        "message": "导入完成",
        "data": {
            "success_count": 3,
            "error_count": 1,
            "errors": ["第 4 行：角色 '客户专员' 已存在"]
        }
    }
    """
    import math

    from ..models.users import Permission

    files = request.files
    if "file" not in files:  # pyright: ignore[reportOperatorIssue]
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)
    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    current_user = get_current_user(request)
    service = RoleService(db_session)

    try:
        df = await asyncio.to_thread(read_import_dataframe, excel_file.body, "name")
        required_columns = ["name"]
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

        # 收集所有权限码，一条 select 批量查 where code.in_（避免逐行 N+1）
        perm_codes: set[str] = set()
        for r in records:
            perm_text = cell(r, "permissions")
            if perm_text:
                perm_codes.update(c.strip() for c in perm_text.split(",") if c.strip())

        existing_perms: dict[str, int] = {}
        if perm_codes:
            result = await db_session.execute(
                select(Permission.id, Permission.code).where(Permission.code.in_(perm_codes))
            )
            existing_perms = {code: pid for pid, code in result.all()}

        # 行级预检（只读，事务外）：行级错误不阻塞其他行
        valid_rows: list[dict] = []
        errors: list[str] = []
        seen_names: set[str] = set()
        for record in records:
            row_num = record["_row_num"]
            name = cell(record, "name")
            description = cell(record, "description")
            perm_text = cell(record, "permissions")

            if not name:
                errors.append(f"第 {row_num} 行：角色名不能为空")
                continue

            # get_role_by_name 不过滤软删（Role 为硬删除），与 create_role 查重口径一致
            existing = await service.get_role_by_name(name)
            if existing or name in seen_names:
                errors.append(f"第 {row_num} 行：角色 '{name}' 已存在")
                continue
            seen_names.add(name)

            # 权限码解析：逗号分隔，逐个校验是否存在；任一不存在整行报错
            perm_ids: list[int] = []
            perm_error: str | None = None
            if perm_text:
                for code in (c.strip() for c in perm_text.split(",")):
                    if not code:
                        continue
                    if code not in existing_perms:
                        perm_error = f"第 {row_num} 行：权限码 '{code}' 不存在"
                        break
                    perm_ids.append(existing_perms[code])
            if perm_error:
                errors.append(perm_error)
                continue

            valid_rows.append(
                {
                    "name": name,
                    "description": description or None,
                    "permission_ids": perm_ids,
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
        # 否则下方 begin() 抛 InvalidRequestError（SQLAlchemy 2.0 autobegin）
        await db_session.commit()

        # 正式落库：RoleService.create_role 内部会 commit，不可用于批量事务；
        # 在 db_session.begin() 内手动创建 Role + role_permissions 关联，统一提交
        async with db_session.begin():
            for row in valid_rows:
                role = Role(name=row["name"], description=row["description"], is_system=False)
                db_session.add(role)
                await db_session.flush()
                for pid in row["permission_ids"]:
                    await db_session.execute(
                        role_permissions.insert().values(role_id=role.id, permission_id=pid)
                    )

        # 批量导入汇总审计（与用户页导入模式一致）
        summary = build_batch_audit_summary(
            operation="role_import",
            total_count=len(valid_rows) + len(errors),
            success_count=len(valid_rows),
            failed_count=len(errors),
            details=errors[:10],
        )
        await create_audit_entry(
            db_session=db_session,
            user_id=current_user.get("user_id") if current_user else None,
            action="batch_create",
            module="roles",
            record_id=None,  # 批量操作
            record_type="role",
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
        logger.exception("角色导入失败")
        return json({"code": 50001, "message": "导入失败，请稍后重试"}, status=500)
