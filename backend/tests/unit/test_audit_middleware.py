"""审计中间件单元测试"""

import pytest
from app.middleware.audit import (
    extract_record_id_from_path,
    extract_module_from_path,
    is_sensitive_operation,
    get_model_for_module,
    map_method_to_action,
)


class TestMapMethodToAction:
    """测试 HTTP 方法到操作类型的映射"""

    def test_post_creates_action(self):
        """POST 到集合路径应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/users") == "create"

    def test_put_updates_action(self):
        """PUT 应映射为 update"""
        assert map_method_to_action("PUT", "/api/v1/users/123") == "update"

    def test_delete_action(self):
        """DELETE 应映射为 delete"""
        assert map_method_to_action("DELETE", "/api/v1/users/123") == "delete"

    def test_post_reset_password(self):
        """POST 重置密码不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/users/123/reset-password") == "reset_password"

    def test_post_assign_roles(self):
        """POST 分配角色不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/users/123/roles") == "assign_roles"

    def test_post_assign_permissions(self):
        """POST 分配权限不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/roles/1/permissions") == "assign_permissions"

    def test_post_submit_invoice(self):
        """POST 提交发票不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/billing/invoices/123/submit") == "submit"

    def test_post_confirm_invoice(self):
        """POST 确认发票不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/billing/invoices/123/confirm") == "confirm"

    def test_post_pay_invoice(self):
        """POST 支付发票不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/billing/invoices/123/pay") == "pay"

    def test_post_complete_invoice(self):
        """POST 完成发票不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/billing/invoices/123/complete") == "complete"

    def test_post_cancel_invoice(self):
        """POST 取消发票不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/billing/invoices/123/cancel") == "cancel"

    def test_post_add_customer_tag(self):
        """POST 添加客户标签不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/customers/1/tags/5") == "add_tag"

    def test_post_add_profile_tag(self):
        """POST 添加画像标签不应映射为 create"""
        assert map_method_to_action("POST", "/api/v1/profiles/1/tags/5") == "add_tag"

    def test_get_method(self):
        """GET 方法应返回小写"""
        assert map_method_to_action("GET", "/api/v1/users") == "get"

    def test_patch_method(self):
        """PATCH 方法应返回小写"""
        assert map_method_to_action("PATCH", "/api/v1/users/123") == "patch"


class TestExtractRecordIdFromPath:
    def test_standard_path(self):
        assert extract_record_id_from_path("/api/v1/users/123") == 123

    def test_nested_path(self):
        assert extract_record_id_from_path("/api/v1/customers/123/tags/456") == 456

    def test_action_path(self):
        assert extract_record_id_from_path("/api/v1/billing/invoices/123/submit") == 123

    def test_no_id_path(self):
        assert extract_record_id_from_path("/api/v1/billing/recharge") is None

    def test_import_path(self):
        assert extract_record_id_from_path("/api/v1/customers/import") is None


class TestExtractModuleFromPath:
    def test_users_module(self):
        assert extract_module_from_path("/api/v1/users/123") == "users"

    def test_customers_module(self):
        assert extract_module_from_path("/api/v1/customers/123") == "customers"

    def test_billing_module(self):
        assert extract_module_from_path("/api/v1/billing/recharge") == "billing"

    def test_profiles_module(self):
        assert extract_module_from_path("/api/v1/profiles/123") == "profiles"


class TestIsSensitiveOperation:
    def test_reset_password(self):
        assert is_sensitive_operation("/api/v1/users/123/reset-password") is True

    def test_forgot_password(self):
        assert is_sensitive_operation("/api/v1/auth/forgot-password") is True

    def test_normal_update(self):
        assert is_sensitive_operation("/api/v1/users/123") is False

    def test_create_customer(self):
        assert is_sensitive_operation("/api/v1/customers") is False


class TestModuleMapping:
    def test_profiles_mapping(self):
        from app.models.customers import CustomerProfile

        model = get_model_for_module("profiles")
        assert model == CustomerProfile

    def test_billing_invoices_mapping(self):
        from app.models.billing import Invoice

        model = get_model_for_module("billing", "/api/v1/billing/invoices/123")
        assert model == Invoice
