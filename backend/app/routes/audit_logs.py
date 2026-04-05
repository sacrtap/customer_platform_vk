"""审计日志路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from ..models.billing import AuditLog
from ..models.users import User
from datetime import datetime

audit_logs_bp = Blueprint("audit_logs", url_prefix="/api/v1/audit-logs")


@audit_logs_bp.get("")
async def list_audit_logs(request: Request):
    """
    获取审计日志列表（支持筛选和分页）

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    - user_id: 用户 ID
    - action: 操作类型
    - module: 模块
    - start_date: 开始日期 (ISO 格式)
    - end_date: 结束日期 (ISO 格式)
    """
    page = request.args.get("page", 1, int)
    page_size = request.args.get("page_size", 20, int)
    page_size = min(page_size, 100)

    # 构建筛选条件
    conditions = [AuditLog.deleted_at.is_(None)]

    if user_id := request.args.get("user_id", type=int):
        conditions.append(AuditLog.user_id == user_id)

    if action := request.args.get("action"):
        conditions.append(AuditLog.action == action)

    if module := request.args.get("module"):
        conditions.append(AuditLog.module == module)

    if start_date := request.args.get("start_date"):
        try:
            start = datetime.fromisoformat(start_date)
            conditions.append(AuditLog.created_at >= start)
        except ValueError:
            pass

    if end_date := request.args.get("end_date"):
        try:
            end = datetime.fromisoformat(end_date)
            conditions.append(AuditLog.created_at <= end)
        except ValueError:
            pass

    db_session: AsyncSession = request.ctx.db_session

    # 总数
    count_stmt = select(func.count()).select_from(AuditLog).where(and_(*conditions))
    total = (await db_session.execute(count_stmt)).scalar() or 0

    # 分页查询，关联用户信息
    stmt = (
        select(AuditLog, User.username)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(and_(*conditions))
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db_session.execute(stmt)
    rows = result.all()

    logs = [
        {
            "id": row.AuditLog.id,
            "user_id": row.AuditLog.user_id,
            "username": row.username or "未知用户",
            "action": row.AuditLog.action,
            "module": row.AuditLog.module,
            "record_id": row.AuditLog.record_id,
            "record_type": row.AuditLog.record_type,
            "changes": row.AuditLog.changes,
            "ip_address": row.AuditLog.ip_address,
            "created_at": row.AuditLog.created_at.isoformat() if row.AuditLog.created_at else None,
        }
        for row in rows
    ]

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": logs,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@audit_logs_bp.get("/actions")
async def get_audit_actions(request: Request):
    """获取所有操作类型（用于筛选下拉框）"""
    db_session: AsyncSession = request.ctx.db_session

    stmt = (
        select(AuditLog.action.distinct())
        .where(AuditLog.deleted_at.is_(None))
        .order_by(AuditLog.action)
    )

    result = await db_session.execute(stmt)
    actions = [row[0] for row in result.all() if row[0]]

    return json({"code": 0, "message": "success", "data": actions})


@audit_logs_bp.get("/modules")
async def get_audit_modules(request: Request):
    """获取所有模块（用于筛选下拉框）"""
    db_session: AsyncSession = request.ctx.db_session

    stmt = (
        select(AuditLog.module.distinct())
        .where(AuditLog.deleted_at.is_(None))
        .order_by(AuditLog.module)
    )

    result = await db_session.execute(stmt)
    modules = [row[0] for row in result.all() if row[0]]

    return json({"code": 0, "message": "success", "data": modules})
