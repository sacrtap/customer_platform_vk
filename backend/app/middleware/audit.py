# -*- coding: utf-8 -*-
"""审计日志中间件"""

import json
from sanic import Sanic
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.billing import AuditLog
from ..middleware.auth import get_current_user


def audit_middleware(app: Sanic):
    """注册审计日志中间件"""

    @app.middleware("response")
    async def log_write_operations(request: Request, response):
        """记录所有写操作（POST/PUT/DELETE）到审计日志"""
        try:
            # 只记录写操作
            if request.method not in ["POST", "PUT", "DELETE"]:
                return

            # 跳过不需要审计的路径
            skip_paths = [
                "/health",
                "/api/v1/auth/login",
                "/api/v1/auth/logout",
                "/api/v1/auth/refresh",
                "/api/v1/auth/me",
            ]

            if request.path in skip_paths:
                return

            # 获取当前用户
            user = get_current_user(request)
            user_id = user.get("user_id") if user else None

            # 获取 IP 地址
            ip_address = request.headers.get(
                "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
            )

            # 提取模块和操作信息
            module = extract_module_from_path(request.path)
            action = map_method_to_action(request.method, request.path)

            # 提取记录 ID 和类型
            record_id, record_type = extract_record_info(
                request.path, request.json, response
            )

            # 提取变更内容（仅 PUT 请求）
            changes = None
            if request.method == "PUT" and request.json:
                changes = {
                    "after": request.json,
                }

            # 记录审计日志
            db_session: AsyncSession = request.ctx.db_session
            audit_entry = AuditLog(
                user_id=user_id,
                action=action,
                module=module,
                record_id=record_id,
                record_type=record_type,
                changes=changes,
                ip_address=ip_address,
            )
            db_session.add(audit_entry)

            # 不等待 commit，让请求继续
            # 使用 on_commit 回调或让后续流程处理
        except Exception as e:
            # 审计日志失败不影响主流程
            app.logger.error(f"Audit log failed: {e}")


def extract_module_from_path(path: str) -> str:
    """从路径提取模块名"""
    # /api/v1/users -> users
    # /api/v1/customers/123 -> customers
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2]
    return "unknown"


def map_method_to_action(method: str, path: str) -> str:
    """映射 HTTP 方法到操作类型"""
    action_map = {
        "POST": "create",
        "PUT": "update",
        "DELETE": "delete",
    }
    return action_map.get(method, method.lower())


def extract_record_info(
    path: str, body: dict | None, response
) -> tuple[int | None, str | None]:
    """从请求/响应中提取记录 ID 和类型"""
    try:
        parts = path.strip("/").split("/")
        # /api/v1/users/123 -> record_id=123, record_type=user
        if len(parts) >= 4:
            try:
                record_id = int(parts[3])
                record_type = parts[2].rstrip("s")  # users -> user
                return record_id, record_type
            except ValueError:
                pass

        # 如果是创建操作，从响应中获取新 ID
        if response and hasattr(response, "body"):
            try:
                data = json.loads(response.body)
                if data.get("code") == 0 and data.get("data", {}).get("id"):
                    return data["data"]["id"], parts[2].rstrip("s")
            except Exception:
                pass

        return None, None
    except Exception:
        return None, None
