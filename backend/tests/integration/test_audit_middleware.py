"""审计中间件集成测试"""

import pytest
from app.middleware.audit import (
    extract_record_id_from_path,
    extract_module_from_path,
    is_sensitive_operation,
    get_model_for_module,
)


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
