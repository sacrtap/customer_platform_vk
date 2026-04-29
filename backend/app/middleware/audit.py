# -*- coding: utf-8 -*-
"""审计日志中间件

增强版本：
1. PUT 请求：在路由处理前查询数据库获取 "before" 状态
2. POST 请求：记录 request body 作为 "after"
3. DELETE 请求：在路由处理前查询数据库获取 "before" 状态
4. 统一变更格式：{"before": {...}, "after": {...}}
"""

import json
from sanic import Sanic
from sanic.request import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.billing import AuditLog
from ..middleware.auth import get_current_user


def audit_middleware(app: Sanic):
    """注册审计日志中间件"""

    # ---- request middleware：在路由处理前捕获 "before" 状态 ----

    @app.middleware("request")
    async def capture_before_state(request: Request):
        """对 PUT/DELETE 请求，在修改前查询数据库获取当前状态"""
        if request.method not in ("PUT", "DELETE"):
            return

        module = extract_module_from_path(request.path)
        record_id = extract_record_id_from_path(request.path)

        if not module or not record_id:
            return

        model_class = get_model_for_module(module, request.path)
        if not model_class:
            return

        try:
            db_session: AsyncSession = request.ctx.db_session
            stmt = select(model_class).where(model_class.id == record_id)
            result = await db_session.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                before = serialize_record_for_audit(record)
                request.ctx._audit_before = before
                request.ctx._audit_record_type = model_class.__name__.lower()
        except Exception:
            pass  # 静默失败，不影响主流程

    # ---- response middleware：记录审计日志 ----

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
                # Webhook 外部回调（无认证用户，审计无意义）
                "/api/v1/webhooks/invoice-confirmation",
                "/api/v1/webhooks/payment-notify",
            ]

            if request.path in skip_paths:
                return

            # 跳过有手动审计日志的模块（files 路由内已自行记录）
            if request.path.startswith("/api/v1/files/"):
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

            # 安全获取 request body
            request_json = None
            try:
                request_json = request.json
            except Exception:
                pass

            # 提取记录 ID 和类型
            record_id, record_type = extract_record_info(request.path, request_json, response)

            # 根据请求类型构建变更数据
            changes = build_changes(
                request.method,
                request_json,
                getattr(request.ctx, "_audit_before", None),
                getattr(request.ctx, "_audit_record_type", None),
                record_type,
                record_id,
            )

            # 覆盖 record_type（优先使用 request middleware 获取的类型）
            if getattr(request.ctx, "_audit_record_type", None):
                record_type = request.ctx._audit_record_type

            # 检测敏感操作
            operation_type = "sensitive" if is_sensitive_operation(request.path) else "standard"

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
                operation_type=operation_type,
            )
            db_session.add(audit_entry)
            await db_session.commit()
        except Exception as e:
            app.logger.error(f"Audit log failed: {e}")


def build_changes(
    method, request_json, before, before_record_type, response_record_type, record_id
):
    """根据请求方法构建变更数据

    - POST → {"after": request_json}（新增记录）
    - PUT  → {"before": before, "after": request_json}（更新记录，含修改前后对比）
    - DELETE → {"before": before}（删除前的完整数据）
    """
    if method == "POST" and request_json:
        return {"after": request_json}

    if method == "DELETE" and before:
        return {"before": before}

    if method == "PUT":
        changes = {}
        if before:
            changes["before"] = before
        if request_json:
            changes["after"] = request_json
        return changes if changes else None

    return None


def serialize_record_for_audit(record) -> dict:
    """将 ORM 记录序列化为审计日志格式

    排除内部字段和敏感字段（如密码哈希）
    """
    exclude = {"_sa_instance_state", "password_hash", "deleted_at"}
    result = {}
    for col in record.__table__.columns:
        key = col.name
        if key in exclude:
            continue
        val = getattr(record, key, None)
        # 将 datetime 等不可 JSON 序列化的类型转为字符串
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        result[key] = val
    return result


# ---- module → model 映射表（延迟加载避免循环导入） ----

_MODULE_MODEL_MAP = None


def get_model_for_module(module: str, path: str = ""):
    """根据模块名和路径获取对应的 SQLAlchemy model 类

    对于 billing 等带子路径的模块，根据子路径精确匹配 model。
    """
    global _MODULE_MODEL_MAP
    if _MODULE_MODEL_MAP is None:
        from ..models.users import User, Role, Permission
        from ..models.customers import Customer, CustomerProfile
        from ..models.tags import Tag, CustomerTag, ProfileTag
        from ..models.groups import CustomerGroup
        from ..models.files import File
        from ..models.billing import PricingRule, Invoice, RechargeRecord, CustomerBalance
        from ..models.industry_type import IndustryType

        _MODULE_MODEL_MAP = {
            # 直接匹配
            "users": User,
            "roles": Role,
            "permissions": Permission,
            "customers": Customer,
            "tags": Tag,
            "customer-tags": CustomerTag,
            "profile-tags": ProfileTag,
            "groups": CustomerGroup,
            "files": File,
            "industry-types": IndustryType,
            # billing 子路径特殊处理
            "billing-pricing-rules": PricingRule,
            "billing-invoices": Invoice,
            "billing-recharge": RechargeRecord,
            "billing-balances": CustomerBalance,
            "billing": CustomerBalance,  # fallback
            # dict 子路径
            "dict-industry-types": IndustryType,
            "dict": IndustryType,  # fallback
            # customer profile 子路径
            "customers-profile": CustomerProfile,
            "profiles": CustomerProfile,  # 画像管理模块
        }

    # 对 billing 等带子路径的模块，尝试精确匹配
    sub_module = extract_sub_module(path)
    if sub_module:
        key = f"{module}-{sub_module}"
        model = _MODULE_MODEL_MAP.get(key)
        if model:
            return model

    return _MODULE_MODEL_MAP.get(module)


def extract_sub_module(path: str) -> str:
    """从路径提取子模块名（用于 billing 等复杂路由）

    /api/v1/billing/pricing-rules/123 -> pricing-rules
    /api/v1/billing/invoices/456/confirm -> invoices
    /api/v1/customers/123/profile -> profile
    /api/v1/customers/import -> (空，因为是动作不是子模块)
    """
    parts = path.strip("/").split("/")
    if len(parts) < 4:
        return ""

    module = parts[2]  # e.g. billing, customers

    if module in ("billing", "dict"):
        sub = parts[3]
        # 如果是数字 ID（如 /billing/123），不是子模块
        try:
            int(sub)
            return ""
        except ValueError:
            return sub

    if module == "customers":
        sub = parts[3]
        # /customers/123/profile -> profile（parts[3] 是 ID, parts[4] 是子模块）
        try:
            int(sub)
            if len(parts) >= 5:
                return parts[4]
            return ""
        except ValueError:
            # /customers/import -> 不是子模块
            return ""

    return ""


def extract_module_from_path(path: str) -> str:
    """从路径提取模块名"""
    # /api/v1/users -> users
    # /api/v1/customers/123 -> customers
    # /api/v1/customer-tags/5 -> customer-tags
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2]
    return "unknown"


def extract_record_id_from_path(path: str) -> int | None:
    """从路径提取记录 ID

    支持多种路径格式:
    - 标准路径: /api/v1/users/123
    - 嵌套路径: /api/v1/customers/123/tags/456
    - 动作路径: /api/v1/billing/invoices/123/submit
    """
    parts = path.strip("/").split("/")

    # 嵌套路径: /api/v1/customers/123/tags/456
    if len(parts) >= 6:
        try:
            return int(parts[5])
        except ValueError:
            pass

    # 动作路径: /api/v1/billing/invoices/123/submit
    if len(parts) >= 5:
        try:
            return int(parts[4])
        except ValueError:
            pass

    # 标准路径: /api/v1/users/123
    if len(parts) >= 4:
        try:
            return int(parts[3])
        except ValueError:
            pass

    return None


def map_method_to_action(method: str, path: str) -> str:
    """映射 HTTP 方法到操作类型"""
    action_map = {
        "POST": "create",
        "PUT": "update",
        "DELETE": "delete",
    }
    return action_map.get(method, method.lower())


def extract_record_info(path: str, body: dict | None, response) -> tuple[int | None, str | None]:
    """从请求/响应中提取记录 ID 和类型"""
    try:
        parts = path.strip("/").split("/")
        # /api/v1/users/123 -> record_id=123
        if len(parts) >= 4:
            try:
                record_id = int(parts[3])
                return record_id, parts[2].rstrip("s")
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


def is_sensitive_operation(path: str) -> bool:
    """检测是否为敏感操作（密码重置、权限变更等）"""
    sensitive_patterns = [
        "/reset-password",
        "/forgot-password",
    ]
    return any(pattern in path for pattern in sensitive_patterns)
