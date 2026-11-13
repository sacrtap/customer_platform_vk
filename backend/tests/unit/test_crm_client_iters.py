"""CRM 客户端枚举行为单元测试（无真实网络，httpx MockTransport）

覆盖「同步顺序」这类会影响用户可见结果的契约：合同必须新签优先，
否则本月回款要等扫完所有历史合同才出现。
"""

import httpx
import pytest

from app.services.crm_client import CrmClient


class _FakeRedis:
    """CrmClient 只用 set(nx)/get/delete；让限流锁总是可用"""

    async def set(self, key, value, nx=False, px=None, ex=None):
        return True

    async def get(self, key):
        return None

    async def delete(self, key):
        return 1


def _factory(handler):
    def build() -> CrmClient:
        return CrmClient(
            redis=_FakeRedis(),
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            base_url="https://lxcrm.weiwenjia.com",
            corp_id="corp",
            phone="13800000000",
            password="secret",
        )

    return build


def _login() -> httpx.Response:
    return httpx.Response(200, json={"code": 0, "data": {"user_token": "stub", "corp_id": "corp"}})


class TestIterContracts:
    async def test_requests_newest_first(self):
        """合同枚举必须 created_at desc（实测 asc 会先扫上千个零回款历史合同）"""
        urls: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            urls.append(str(request.url))
            if "auth/login" in str(request.url):
                return _login()
            return httpx.Response(
                200,
                json={"code": 0, "data": {"contracts": [{"id": 34916658}], "total_count": 1}},
            )

        factory = _factory(handler)
        client = factory()
        items = [item async for item in client.iter_contracts()]

        assert items == [{"id": 34916658}]
        contract_urls = [u for u in urls if "/api/v2/contracts" in u]
        assert contract_urls, urls
        assert "order=desc" in contract_urls[0]
        assert "sort=created_at" in contract_urls[0]


class TestIterCustomers:
    async def test_keeps_ascending_pagination(self):
        """客户枚举顺序不影响业务结果，保持 asc（稳定分页）"""
        urls: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            urls.append(str(request.url))
            if "auth/login" in str(request.url):
                return _login()
            return httpx.Response(
                200,
                json={"code": 0, "data": {"customers": [{"id": 7}], "total_count": 1}},
            )

        client = _factory(handler)()
        items = [item async for item in client.iter_customers()]

        assert items == [{"id": 7}]
        customer_urls = [u for u in urls if "/api/v2/customers" in u]
        assert "order=asc" in customer_urls[0]


class TestIterPayments:
    """全局回款列表：`/received_payments` 上游 500，只有 `/list` 可用"""

    async def test_uses_list_path_and_approved_filter(self):
        urls: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            urls.append(str(request.url))
            if "auth/login" in str(request.url):
                return _login()
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "received_payments": [{"id": 14430502, "contract_id": 34916658}],
                        "total_count": 1,
                        "has_next_page": False,
                        "per_page": 100,
                        "page": 1,
                    },
                },
            )

        client = _factory(handler)()
        items = [item async for item in client.iter_payments()]

        assert items == [{"id": 14430502, "contract_id": 34916658}]
        payment_urls = [u for u in urls if "received_payments" in u]
        assert payment_urls, urls
        assert "/api/v2/received_payments/list" in payment_urls[0]
        assert "approve_status=approved" in payment_urls[0]
        assert "per_page=100" in payment_urls[0]


@pytest.mark.parametrize("path_method", ["iter_contracts", "iter_customers"])
async def test_pagination_closes_on_total_count(path_method: str):
    """total_count 达标即停止，不无限翻页"""
    calls = {"pages": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if "auth/login" in str(request.url):
            return _login()
        calls["pages"] += 1
        key = "contracts" if "contracts" in str(request.url) else "customers"
        return httpx.Response(
            200, json={"code": 0, "data": {key: [{"id": calls["pages"]}], "total_count": 1}}
        )

    client = _factory(handler)()
    items = [item async for item in getattr(client, path_method)()]
    assert len(items) == 1
    assert calls["pages"] == 1
