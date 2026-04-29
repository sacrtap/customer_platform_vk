"""审计日志辅助函数

提供统一的审计记录创建、批量操作摘要构建、敏感数据脱敏等功能。
"""

from sqlalchemy.ext.asyncio import AsyncSession
from ..models.billing import AuditLog


async def create_audit_entry(
    db_session: AsyncSession,
    user_id: int,
    action: str,
    module: str,
    record_id: int | None = None,
    record_type: str | None = None,
    changes: dict | None = None,
    ip_address: str | None = None,
    operation_type: str = "standard",
    extra_metadata: dict | None = None,
    auto_commit: bool = False,
) -> AuditLog:
    """统一审计记录创建函数"""
    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        module=module,
        record_id=record_id,
        record_type=record_type,
        changes=changes,
        ip_address=ip_address,
        operation_type=operation_type,
        extra_metadata=extra_metadata,
    )
    db_session.add(audit_entry)
    if auto_commit:
        await db_session.commit()
    return audit_entry


def build_batch_audit_summary(
    operation: str,
    total_count: int,
    success_count: int,
    failed_count: int | None = None,
    details: list | None = None,
) -> dict:
    """构建批量操作审计摘要"""
    if failed_count is None:
        failed_count = total_count - success_count

    return {
        "operation": operation,
        "total_count": total_count,
        "success_count": success_count,
        "failed_count": failed_count,
        "details": details or [],
    }


def mask_sensitive_data(data: dict, fields: list | None = None) -> dict:
    """敏感数据脱敏"""
    if fields is None:
        fields = ["password", "password_hash", "token", "secret"]

    masked = data.copy()
    for field in fields:
        if field in masked:
            masked[field] = "***MASKED***"
    return masked
