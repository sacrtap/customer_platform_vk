"""审计中间件单元测试"""

import json
import uuid
from datetime import datetime
from decimal import Decimal

from app.middleware.audit import (
    extract_module_from_path,
    extract_record_id_from_path,
    extract_record_info,
    get_model_for_module,
    is_sensitive_operation,
    map_method_to_action,
    serialize_record_for_audit,
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


class _FakeColumn:
    """仅需 .name 的列桩"""

    def __init__(self, name):
        self.name = name


class _FakeTable:
    def __init__(self, names):
        self.columns = [_FakeColumn(n) for n in names]


class _FakeRecord:
    """带 __table__.columns 与对应属性的记录桩"""

    def __init__(self, **fields):
        self.__table__ = _FakeTable(fields.keys())
        for k, v in fields.items():
            setattr(self, k, v)


class TestSerializeRecordForAudit:
    """before 快照必须产出 JSON 原生值

    回归 2026-11-10 结算单删除事故：Invoice 的 DECIMAL 列原样进 changes，
    flush 时 json.dumps 抛 TypeError，审计被中间件 except 吞掉 → 静默丢失。
    """

    def test_decimal_becomes_string(self):
        record = _FakeRecord(total_amount=Decimal("1234.56"), discount_amount=Decimal("0.00"))
        result = serialize_record_for_audit(record)
        # str 保留精确十进制文本；float 会引入二进制误差
        assert result == {"total_amount": "1234.56", "discount_amount": "0.00"}

    def test_datetime_becomes_isoformat(self):
        record = _FakeRecord(created_at=datetime(2026, 11, 10, 10, 59, 18))
        result = serialize_record_for_audit(record)
        assert result["created_at"] == "2026-11-10T10:59:18"

    def test_uuid_becomes_string(self):
        value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        record = _FakeRecord(id=value)
        result = serialize_record_for_audit(record)
        assert result["id"] == "12345678-1234-5678-1234-567812345678"

    def test_none_and_native_values_pass_through(self):
        record = _FakeRecord(name="行业", sort_order=3, is_active=True, remark=None)
        result = serialize_record_for_audit(record)
        assert result == {"name": "行业", "sort_order": 3, "is_active": True, "remark": None}

    def test_excludes_internal_and_sensitive_fields(self):
        record = _FakeRecord(
            username="alice",
            password_hash="$2b$12$secret",
            deleted_at=datetime(2026, 11, 10),
            _sa_instance_state=object(),
        )
        result = serialize_record_for_audit(record)
        assert result == {"username": "alice"}

    def test_result_is_json_serializable(self):
        """整快照必须能过 json.dumps（修复前 Decimal 在此抛 TypeError）"""
        record = _FakeRecord(
            invoice_no="INV-20261110-0001",
            total_amount=Decimal("100.00"),
            discount_amount=Decimal("10.00"),
            created_at=datetime(2026, 11, 10, 10, 59, 18),
        )
        json.dumps(serialize_record_for_audit(record))  # 不抛即通过


class TestExtractRecordInfo:
    """record_id/record_type 提取（含嵌套路径回退）"""

    def test_standard_path(self):
        assert extract_record_info("/api/v1/users/123", None, None) == (123, "user")

    def test_nested_billing_invoice_path(self):
        """回归：/api/v1/billing/invoices/1671 的 parts[3] 是资源名，
        旧实现只试 parts[3] → record_id 落 NULL，审计关联不到单据"""
        assert extract_record_info("/api/v1/billing/invoices/1671", None, None) == (1671, "billing")

    def test_action_path(self):
        assert extract_record_info("/api/v1/billing/invoices/1671/submit", None, None) == (
            1671,
            "billing",
        )

    def test_collection_path_has_no_id(self):
        assert extract_record_info("/api/v1/billing/invoices", None, None) == (None, None)

    def test_create_reads_id_from_response(self):
        class _Resp:
            body = json.dumps({"code": 0, "data": {"id": 42}}).encode()

        assert extract_record_info("/api/v1/industry-types", None, _Resp()) == (42, "industry-type")
