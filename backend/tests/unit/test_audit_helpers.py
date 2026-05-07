"""审计辅助函数单元测试（无数据库依赖）"""

import pytest
from app.utils.audit_helpers import (
    build_batch_audit_summary,
    mask_sensitive_data,
)


class TestBuildBatchAuditSummary:
    """批量操作审计摘要构建单元测试"""

    def test_basic_summary(self):
        result = build_batch_audit_summary(
            operation="customer_import",
            total_count=10,
            success_count=8,
        )
        assert result["operation"] == "customer_import"
        assert result["total_count"] == 10
        assert result["success_count"] == 8
        assert result["failed_count"] == 2
        assert result["details"] == []

    def test_custom_failed_count(self):
        result = build_batch_audit_summary(
            operation="user_import",
            total_count=5,
            success_count=3,
            failed_count=1,
        )
        assert result["failed_count"] == 1

    def test_with_details(self):
        details = [
            {"row": 3, "error": "用户名已存在"},
            {"row": 5, "error": "邮箱格式错误"},
        ]
        result = build_batch_audit_summary(
            operation="user_import",
            total_count=5,
            success_count=3,
            details=details,
        )
        assert len(result["details"]) == 2
        assert result["details"][0]["row"] == 3


class TestMaskSensitiveData:
    """敏感数据脱敏单元测试"""

    def test_default_fields(self):
        data = {
            "username": "test",
            "password": "secret123",
            "password_hash": "abc123",
            "email": "test@example.com",
        }
        result = mask_sensitive_data(data)
        assert result["username"] == "test"
        assert result["password"] == "***MASKED***"
        assert result["password_hash"] == "***MASKED***"
        assert result["email"] == "test@example.com"

    def test_custom_fields(self):
        data = {
            "api_key": "key123",
            "token": "tok_abc",
            "name": "Test",
        }
        result = mask_sensitive_data(data, fields=["api_key", "token"])
        assert result["api_key"] == "***MASKED***"
        assert result["token"] == "***MASKED***"
        assert result["name"] == "Test"

    def test_missing_fields(self):
        data = {"username": "test"}
        result = mask_sensitive_data(data)
        assert result["username"] == "test"

    def test_does_not_modify_original(self):
        data = {"password": "secret"}
        original = data.copy()
        mask_sensitive_data(data)
        assert data == original
