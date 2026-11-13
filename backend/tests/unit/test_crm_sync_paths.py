"""CRM 同步路径选择的行为测试（DB helper 与上游全部桩掉）

回归重点：逐合同枚举在本租户要 7118 个合同 × 1.25s 限流 ≈ 2.4 小时，
必须优先走全局回款列表（`/api/v2/received_payments/list`，1536 条 / 16 页 ≈ 22s）；
上游列表不可用时才回退合同枚举（保底不遗漏）。

这些断言锁定三件影响用户可见结果的事：
1. 只有当月回款才调详情（否则请求数回到几千的量级）；
2. 列表项缺 contract_id 必须失败，不能猜；
3. 列表路径失败要回退而不是整体 failed。
"""

import logging
from datetime import date
from typing import cast
from unittest.mock import AsyncMock

import pytest

import app.services.crm_recharge as svc
from app.services.crm_client import CrmClient, CrmNotFoundError, CrmUpstreamError

MONTH_START = date(2026, 11, 1)
MONTH_END = date(2026, 12, 1)
FIELD = svc.INDUSTRY_FIELD_NAME


def _metadata() -> dict:
    """上游 by_group 的最小真实形状：两个行业根 + 行业分类字段名"""
    return {
        "custom_field_groups": [
            {
                "custom_fields": [
                    {
                        "name": FIELD,
                        "label": "行业分类",
                        "field_type": "nested_select_field",
                        "input_field_options": {
                            "collection_options": [
                                {
                                    "label": "房产经纪",
                                    "value": "1001",
                                    "children": [
                                        {"label": "二手房", "value": "1001-1", "children": []}
                                    ],
                                },
                                {"label": "新房开发", "value": "2001", "children": []},
                            ]
                        },
                    }
                ]
            }
        ]
    }


def _list_item(pid: int, receive_date: str, **extra) -> dict:
    item = {
        "id": pid,
        "contract_id": 7001,
        "customer_id": 501,
        "customer_name": "南宁江山地产",
        "contract_title": "年度框架合同",
        "receive_date": receive_date,
        "approve_status": svc.APPROVED_STATUS,
        "amount": "1200.50",
    }
    item.update(extra)
    return item


def _detail(pid: int, **overrides) -> dict:
    data = {
        "id": pid,
        "customer_id": 501,
        "contract_id": 7001,
        "contract_title": "年度框架合同",
        "amount": "1200.50",
        "receive_date": "2026-11-05",
        "approve_status": svc.APPROVED_STATUS,
        FIELD: "1001/二手房",
    }
    data.update(overrides)
    return data


class _FakeClient:
    def __init__(
        self,
        payments: list[dict],
        details: dict[int, object],
        *,
        list_error=None,
        customers: list[dict] | None = None,
    ):
        self._payments = payments
        self._details = details
        self._list_error = list_error
        self._customers = customers
        self.detail_calls: list[tuple[int, int]] = []

    async def get_payment_fields(self) -> dict:
        return _metadata()

    async def iter_payments(self):
        if self._list_error is not None:
            raise self._list_error
        for item in self._payments:
            yield item

    async def iter_customers(self):
        for item in self._customers or [{"id": 501, "name": "南宁江山地产", "user_name": "秦晓龙"}]:
            yield item

    async def iter_contracts(self):
        yield {"id": 7001, "title": "年度框架合同"}

    async def iter_contract_payments(self, contract_id: int):
        for item in self._payments:
            yield item

    async def get_payment(self, contract_id: int, payment_id: int) -> dict:
        self.detail_calls.append((contract_id, payment_id))
        value = self._details[payment_id]
        if isinstance(value, Exception):
            raise value
        return cast(dict, value)


@pytest.fixture
def db_calls(monkeypatch):
    """把所有 DB 侧副作用换成记录器：测试只关心「写什么/调几次」"""
    calls: dict[str, list] = {
        "upsert": [],
        "progress": [],
        "demote": [],
        "customers": [],
        "retire": [],
    }

    async def progress(run_id, session_factory, **values):
        calls["progress"].append(values)

    async def upsert_payment(session_factory, values):
        calls["upsert"].append(values)

    async def upsert_customers(session_factory, corp_id, rows):
        calls["customers"].extend(rows)

    async def demote(session_factory, corp_id, external_ids):
        calls["demote"].append(list(external_ids))

    async def delete_rows(session_factory, corp_id, external_ids, imported_ids):
        calls["retire"].append(list(external_ids))

    monkeypatch.setattr(svc, "_progress", progress)
    monkeypatch.setattr(svc, "_upsert_payment", upsert_payment)
    monkeypatch.setattr(svc, "_upsert_customers", upsert_customers)
    monkeypatch.setattr(svc, "_demote_payments", demote)
    monkeypatch.setattr(svc, "_delete_out_of_scope_payments", delete_rows)
    monkeypatch.setattr(svc, "_load_imported_ids", AsyncMock(return_value=set()))
    monkeypatch.setattr(svc, "_load_month_payments", AsyncMock(return_value={}))
    monkeypatch.setattr(svc, "_fetch_customer_map", AsyncMock(return_value={501: 12}))
    return calls


async def test_only_month_payments_get_details(db_calls):
    """非当月回款不调详情：否则请求数回到「每条回款一次」的量级"""
    client = _FakeClient(
        payments=[
            _list_item(14430502, "2026-11-03"),
            _list_item(14300001, "2026-10-15"),
        ],
        details={14430502: _detail(14430502)},
    )

    result = await svc._scan_via_payment_list(
        client=cast(CrmClient, client),
        run_id=1,
        session_factory=object(),
        corp_id="corp",
        month_start=MONTH_START,
        month_end=MONTH_END,
        allowed_paths={"1001", "2001"},
        customer_map={501: 12},
    )

    assert client.detail_calls == [(7001, 14430502)]
    assert result["scanned_payment_count"] == 2
    assert result["payment_count"] == 1
    assert result["eligible_count"] == 1
    assert [row["external_id"] for row in db_calls["upsert"]] == [14430502]
    assert db_calls["upsert"][0]["eligible"] is True
    assert db_calls["upsert"][0]["crm_customer_id"] == 12


async def test_list_item_without_contract_id_fails_loudly(db_calls):
    client = _FakeClient(
        payments=[_list_item(14430502, "2026-11-03", contract_id=None)],
        details={},
    )

    with pytest.raises(CrmUpstreamError, match="contract_id"):
        await svc._scan_via_payment_list(
            client=cast(CrmClient, client),
            run_id=1,
            session_factory=object(),
            corp_id="corp",
            month_start=MONTH_START,
            month_end=MONTH_END,
            allowed_paths={"1001"},
            customer_map={},
        )
    assert db_calls["upsert"] == []


async def test_detail_not_found_does_not_write(db_calls):
    """列表刚给过、详情 404：不写入、不据此认定删除"""
    client = _FakeClient(
        payments=[_list_item(14430502, "2026-11-03")],
        details={14430502: CrmNotFoundError("not found")},
    )

    result = await svc._scan_via_payment_list(
        client=cast(CrmClient, client),
        run_id=1,
        session_factory=object(),
        corp_id="corp",
        month_start=MONTH_START,
        month_end=MONTH_END,
        allowed_paths={"1001"},
        customer_map={},
    )

    assert result["payment_count"] == 0
    assert db_calls["upsert"] == []


async def test_missing_mirror_is_rechecked_not_deleted(db_calls, monkeypatch):
    """既有镜像未在列表出现 → 复核（可能改期/撤审），不直接认定删除"""
    monkeypatch.setattr(
        svc,
        "_load_month_payments",
        AsyncMock(
            return_value={
                14420000: {
                    "external_id": 14420000,
                    "contract_external_id": 7001,
                    "imported_snapshot": None,
                }
            }
        ),
    )
    client = _FakeClient(payments=[], details={14420000: _detail(14420000)})

    await svc._scan_via_payment_list(
        client=cast(CrmClient, client),
        run_id=1,
        session_factory=object(),
        corp_id="corp",
        month_start=MONTH_START,
        month_end=MONTH_END,
        allowed_paths={"1001"},
        customer_map={},
    )

    assert client.detail_calls == [(7001, 14420000)]
    assert [row["external_id"] for row in db_calls["upsert"]] == [14420000]


async def test_sync_month_falls_back_to_contract_scan(db_calls):
    """全局列表不可用 → 回退逐合同枚举，而不是整体 failed"""
    client = _FakeClient(
        payments=[_list_item(14430502, "2026-11-03")],
        details={14430502: _detail(14430502)},
        list_error=CrmUpstreamError("CRM 请求 /api/v2/received_payments失败（业务 code=500）"),
    )

    result = await svc._sync_month(cast(CrmClient, client), 1, object(), "corp", date(2026, 11, 15))

    assert result["contract_count"] == 1
    assert result["payment_count"] == 1
    assert result["eligible_count"] == 1
    assert any(p.get("phase") == "contracts" for p in db_calls["progress"])
    # 负责人来自上游 user_name（曾误用 owner_name，导致 5032 个客户全空）
    assert db_calls["customers"][0]["owner_name"] == "秦晓龙"


async def test_out_of_scope_industry_is_not_mirrored(db_calls):
    """业务口径：只录入「房产经纪 / 新房开发」类别，其他行业不进镜像列表"""
    client = _FakeClient(
        payments=[
            _list_item(14430502, "2026-11-03"),
            _list_item(14421562, "2026-11-03"),
        ],
        details={
            14430502: _detail(14430502),
            14421562: _detail(14421562, **{FIELD: "酒店民宿租房"}),
        },
    )

    result = await svc._scan_via_payment_list(
        client=cast(CrmClient, client),
        run_id=1,
        session_factory=object(),
        corp_id="corp",
        month_start=MONTH_START,
        month_end=MONTH_END,
        allowed_paths={"1001", "2001"},
        customer_map={},
    )

    assert [row["external_id"] for row in db_calls["upsert"]] == [14430502]
    assert db_calls["retire"] == [[14421562]]
    assert result["payment_count"] == 1
    assert result["eligible_count"] == 1


async def test_recheck_retires_mirror_whose_industry_left_scope(db_calls, monkeypatch):
    """既有镜像行业改为非允许范围且未导入 → 删除；已导入的保留镜像"""
    monkeypatch.setattr(
        svc,
        "_load_month_payments",
        AsyncMock(
            return_value={
                14420000: {
                    "external_id": 14420000,
                    "contract_external_id": 7001,
                    "imported_snapshot": None,
                }
            }
        ),
    )
    client = _FakeClient(
        payments=[],
        details={14420000: _detail(14420000, **{FIELD: "高校教育"})},
    )

    await svc._scan_via_payment_list(
        client=cast(CrmClient, client),
        run_id=1,
        session_factory=object(),
        corp_id="corp",
        month_start=MONTH_START,
        month_end=MONTH_END,
        allowed_paths={"1001"},
        customer_map={},
    )

    assert db_calls["upsert"] == []
    assert db_calls["retire"] == [[14420000]]


class TestExtractOwnerName:
    """上游客户项的负责人字段是 `user_name`（实测），不是 `owner_name`"""

    def test_uses_user_name(self):
        assert svc._extract_owner_name({"user_name": "秦晓龙"}) == "秦晓龙"

    def test_trims_and_skips_blank(self):
        assert svc._extract_owner_name({"user_name": "  高朝义  "}) == "高朝义"
        assert svc._extract_owner_name({"user_name": "  ", "owner_name": "邰方程"}) == "邰方程"

    def test_falls_back_to_legacy_shapes(self):
        assert svc._extract_owner_name({"owner_name": "旧字段"}) == "旧字段"
        assert svc._extract_owner_name({"owner": {"name": "嵌套字段"}}) == "嵌套字段"

    def test_absent_owner_is_none(self):
        assert svc._extract_owner_name({"name": "上海鹰真安防器材有限公司"}) is None
        assert svc._extract_owner_name({"user_name": None, "owner": None}) is None


async def test_warns_when_owner_names_all_empty(db_calls, caplog):
    """字段映射错误的唯一运行时证据是填充率为 0：必须留下可检索的告警"""
    client = _FakeClient(
        payments=[],
        details={},
        customers=[{"id": 501, "name": "上海鹰真安防器材有限公司"}],
    )

    with caplog.at_level(logging.WARNING):
        await svc._sync_month(cast(CrmClient, client), 1, object(), "corp", date(2026, 11, 15))

    assert "负责人姓名全部为空" in caplog.text
