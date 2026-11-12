"""CRM 分页响应解析单元测试（无网络/无数据库）

上游各资源的分页键名并不统一（客户可能叫 customers、合同可能叫 contracts），
`_extract_page` 必须先按具名键匹配，再对未知命名做「唯一数组」兜底，
且无法识别时给出可诊断的键名，不能静默当空页。
"""

import pytest

from app.services.crm_client import (
    CrmAuthError,
    CrmClient,
    CrmConfigError,
    CrmUpstreamError,
)

extract = CrmClient._extract_page


class TestNamedKeys:
    def test_list_with_pagination(self):
        items, meta = extract({"list": [{"id": 1}], "pagination": {"total_count": 5032}})
        assert items == [{"id": 1}]
        assert meta == {"total_count": 5032}

    def test_data_key(self):
        items, _ = extract({"data": [{"id": 2}]})
        assert items == [{"id": 2}]

    def test_customers_key(self):
        items, meta = extract({"customers": [{"id": 3}], "total_count": 7117})
        assert items == [{"id": 3}]
        assert meta.get("total_count") == 7117

    def test_received_payments_key(self):
        items, _ = extract({"received_payments": [{"id": 4}]})
        assert items == [{"id": 4}]

    def test_empty_list_is_valid(self):
        items, _ = extract({"list": [], "total_count": 0})
        assert items == []


class TestUnknownKeys:
    def test_single_array_of_unknown_name(self):
        """上游换名（如 customer_list）时仍能解析"""
        items, _ = extract({"customer_list": [{"id": 5}], "page": 1})
        assert items == [{"id": 5}]

    def test_two_unknown_arrays_is_ambiguous(self):
        with pytest.raises(CrmUpstreamError) as excinfo:
            extract({"record_list": [{"id": 6}], "tag_list": ["a"]})
        assert "缺少列表字段" in str(excinfo.value)
        assert "record_list" in str(excinfo.value)
        assert "tag_list" in str(excinfo.value)

    def test_no_array_reports_keys(self):
        with pytest.raises(CrmUpstreamError) as excinfo:
            extract({"total_count": 10, "message": "ok"})
        assert "total_count" in str(excinfo.value)

    def test_empty_object_reports_empty(self):
        with pytest.raises(CrmUpstreamError) as excinfo:
            extract({})
        assert "空对象" in str(excinfo.value)


class TestProbeValidation:
    def test_incomplete_credentials_rejected_before_any_request(self):
        # 缺密码时必须在构造阶段失败，不能带着空凭据打上游
        with pytest.raises(CrmConfigError) as excinfo:
            CrmClient(corp_id="corp", phone="13800000000", password="")
        assert "未配置" in str(excinfo.value)


class TestProbeDegradation:
    async def test_credentials_valid_but_list_unreadable_returns_warning(self, monkeypatch):
        """登录成功、列表读不出：验证仍算通过，只带降级说明

        否则分页契约变化会锁死管理员保存配置的路径。
        """
        client = CrmClient(corp_id="corp", phone="13800000000", password="secret")

        async def _fake_token() -> str:
            return "token"

        async def _fake_request(*args, **kwargs) -> dict:
            return {"total_count": 5032}  # 没有任何数组字段

        monkeypatch.setattr(client, "_get_token", _fake_token)
        monkeypatch.setattr(client, "_request", _fake_request)

        result = await client.probe()
        assert result["customer_total"] is None
        assert result["corp_id"] == "corp"
        assert "缺少列表字段" in result["warning"]
        assert "total_count" in result["warning"]

    async def test_auth_error_still_fails(self, monkeypatch):
        client = CrmClient(corp_id="corp", phone="13800000000", password="secret")

        async def _bad_token() -> str:
            raise CrmAuthError("CRM 登录失败：账号或密码不正确")

        monkeypatch.setattr(client, "_get_token", _bad_token)
        with pytest.raises(CrmAuthError):
            await client.probe()
