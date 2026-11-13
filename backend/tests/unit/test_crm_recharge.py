"""CRM 回款镜像的纯函数与导入前置校验单元测试

覆盖：名称规范化/推荐评分、行业契约解析、回款详情评估（合格与各阻止原因）、
金额校验、幂等响应与快照稳定性。资金写入路径由集成测试覆盖。
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.billing import CustomerBalance, RechargeRecord
from app.models.crm_recharge import CrmCustomer, CrmPayment
from app.models.customers import Customer
from app.services.crm_recharge import (
    APPROVED_STATUS,
    INDUSTRY_FIELD_NAME,
    CrmContractError,
    CrmCustomerBindingService,
    CrmImportError,
    CrmRechargeImportService,
    _business_snapshot,
    _evaluate_payment,
    _industry_allowed,
    _month_bounds,
    _parse_amount,
    _parse_date,
    _snapshots_differ,
    _validate_import_amounts,
    build_existing_import_response,
    normalize_crm_name,
    parse_industry_path,
    resolve_industry_paths,
    score_crm_candidate,
)

FIELD = INDUSTRY_FIELD_NAME

# 上游 `GET /api/v2/custom_fields/received_payment/by_group` 的**真实**结构（2026-11-12 实测）：
# data.custom_field_groups[].custom_fields[].input_field_options.collection_options[].children[]
# 以及镜像分支 .options.select_options[]。字段名与根值取自本租户实测值。
ROOT_REAL_ESTATE = "ba2503bf-06b0-4e90-80fe-fea73d3ef4e5"
ROOT_NEW_HOME = "bdb440d1-1be2-46ed-acfb-e919b5d245b4"


def _industry_options() -> list[dict]:
    return [
        {
            "label": "房产经纪",
            "value": ROOT_REAL_ESTATE,
            "children": [
                {
                    "label": "新业绩",
                    "value": "1b1ae256-e806-4417-8449-a2d6300093dd",
                    "children": [],
                },
                {
                    "label": "老业绩",
                    "value": "943a9513-8ff3-4f80-912a-c12a6ac11dc5",
                    "children": [],
                },
            ],
        },
        {"label": "新房开发", "value": ROOT_NEW_HOME, "children": []},
    ]


def _real_payment_metadata(
    *, field_name: str = FIELD, roots: bool = True, duplicate_field: bool = False
) -> dict:
    """真实 by_group 元数据的最小快照（含无关字段，防止解析误收）"""
    options = _industry_options() if roots else []
    custom_fields: list[dict] = [
        {"name": "contract", "label": "合同标题", "field_type": "text"},
        {"name": "received_payment_plan", "label": "回款期次", "field_type": "number"},
        {
            "name": field_name,
            "label": "行业分类",
            "field_type": "nested_select_field",
            "input_field_options": {"collection_options": options, "default_type": "none"},
            "options": {"select_options": options, "custom_column_name": field_name},
        },
    ]
    if duplicate_field:
        custom_fields.append({"name": "text_asset_ffff", "label": "行业分类", "field_type": "text"})
    return {
        "custom_field_groups": [
            {
                "id": "group-1",
                "label": "回款信息",
                "custom_fields": custom_fields,
            }
        ],
        "sensitive_on": False,
    }


class TestNormalizeCrmName:
    def test_fullwidth_case_and_punctuation_are_normalized(self):
        assert normalize_crm_name("上海 ＡＢＣ（集团）") == "上海abc集团"

    def test_empty_and_whitespace_only(self):
        assert normalize_crm_name("") == ""
        assert normalize_crm_name("   ") == ""

    def test_keeps_region_prefix_distinction(self):
        # 不剥地域/后缀：上海XX 与 XX 保留差异
        assert normalize_crm_name("上海某某") != normalize_crm_name("某某")


class TestScoreCrmCandidate:
    def test_exact_match_scores_one(self):
        assert score_crm_candidate("上海某某科技有限公司", "上海某某科技 有限公司") == 1.0

    def test_containment_scores_between_08_and_099(self):
        score = score_crm_candidate("某某科技", "上海某某科技有限公司")
        assert 0.8 <= score <= 0.99

    def test_loose_similarity_below_containment_band(self):
        score = score_crm_candidate("上海某某", "北京某某")
        assert score < 0.8

    def test_empty_side_scores_zero(self):
        assert score_crm_candidate("", "某某") == 0.0
        assert score_crm_candidate("某某", "") == 0.0


class TestResolveIndustryPaths:
    """元数据解析必须按真实结构工作

    回归：解析器曾按 `children/options/sub_fields/values/items/list` 键名白名单下钻，
    真实结构的 `custom_field_groups[].custom_fields[]` 不在白名单里 → 拿不到任何字段节点
    → 同步必然 failed（「CRM 回款字段缺少「行业分类」」）。
    """

    def test_collects_roots_and_descendants_from_real_structure(self):
        allowed = resolve_industry_paths(_real_payment_metadata())
        assert allowed == {
            ROOT_REAL_ESTATE,
            "1b1ae256-e806-4417-8449-a2d6300093dd",
            "943a9513-8ff3-4f80-912a-c12a6ac11dc5",
            ROOT_NEW_HOME,
        }

    def test_only_select_options_branch_still_parses(self):
        """真实响应同时带 input_field_options 与 options；只剩镜像分支也必须能解析"""
        metadata = _real_payment_metadata()
        field = metadata["custom_field_groups"][0]["custom_fields"][2]
        del field["input_field_options"]
        assert ROOT_REAL_ESTATE in resolve_industry_paths(metadata)

    def test_unrelated_fields_are_not_collected(self):
        allowed = resolve_industry_paths(_real_payment_metadata())
        assert "contract" not in allowed
        assert "received_payment_plan" not in allowed

    def test_missing_industry_field_raises_contract_error(self):
        metadata = _real_payment_metadata(field_name="other_field")
        with pytest.raises(CrmContractError):
            resolve_industry_paths(metadata)

    def test_duplicated_industry_label_raises_contract_error(self):
        with pytest.raises(CrmContractError):
            resolve_industry_paths(_real_payment_metadata(duplicate_field=True))

    def test_missing_root_raises_contract_error(self):
        with pytest.raises(CrmContractError, match="行业根"):
            resolve_industry_paths(_real_payment_metadata(roots=False))

    def test_missing_field_entirely_raises(self):
        with pytest.raises(CrmContractError):
            resolve_industry_paths({"custom_field_groups": []})

    def test_missing_field_error_reports_actual_shape(self):
        """错误信息必须能区分「上游没给」与「解析器看不见」"""
        with pytest.raises(CrmContractError) as excinfo:
            resolve_industry_paths({"custom_field_groups": [], "sensitive_on": False})
        message = str(excinfo.value)
        assert "custom_field_groups" in message
        assert "遍历节点数" in message


class TestParseIndustryPath:
    def test_string_path_splits_on_slash(self):
        assert parse_industry_path("房产经纪/二手房") == ["房产经纪", "二手房"]

    def test_list_items_are_flattened(self):
        assert parse_industry_path(["房产经纪", ["二手房", "租赁"]]) == [
            "房产经纪",
            "二手房",
            "租赁",
        ]

    def test_dict_prefers_value_then_path_then_id(self):
        assert parse_industry_path({"value": "房产经纪/二手房"}) == ["房产经纪", "二手房"]
        assert parse_industry_path({"path": "房产经纪"}) == ["房产经纪"]
        assert parse_industry_path({"id": "1001"}) == ["1001"]

    def test_unknown_shapes_return_empty(self):
        assert parse_industry_path(None) == []
        assert parse_industry_path(123) == []

    def test_industry_allowed_uses_first_segment(self):
        allowed = {"1001"}
        assert _industry_allowed("1001/二手房", allowed) is True
        assert _industry_allowed("1002/租赁", allowed) is False
        assert _industry_allowed(None, allowed) is False


class TestParseAmountAndDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("100.00", Decimal("100.00")),
            (100, Decimal("100")),
            ("100.005", None),
            ("abc", None),
            (None, None),
            (True, None),
            ("NaN", None),
        ],
    )
    def test_parse_amount(self, raw, expected):
        assert _parse_amount(raw) == expected

    def test_parse_date_accepts_iso_prefix_only(self):
        assert _parse_date("2026-11-11T10:00:00") == date(2026, 11, 11)
        assert _parse_date("2026-11-11") == date(2026, 11, 11)
        assert _parse_date("2026/11/11") is None
        assert _parse_date(None) is None


def test_month_bounds_handles_december_rollover():
    assert _month_bounds(date(2026, 12, 15)) == (date(2026, 12, 1), date(2027, 1, 1))
    assert _month_bounds(date(2026, 11, 11)) == (date(2026, 11, 1), date(2026, 12, 1))


def _details(**overrides) -> dict:
    data = {
        "id": 9001,
        "customer_id": 501,
        "contract_id": 7001,
        "contract_title": "年度框架合同",
        "amount": "1200.50",
        "receive_date": "2026-11-05",
        "approve_status": APPROVED_STATUS,
        FIELD: "1001/二手房",
        f"{FIELD}_display": "房产经纪/二手房",
    }
    data.update(overrides)
    return data


class TestEvaluatePayment:
    def _evaluate(self, details: dict, *, customer_map: dict[int, int] | None = None):
        return _evaluate_payment(
            details=details,
            fallback_date=None,
            fallback_status=APPROVED_STATUS,
            allowed_paths={"1001", "2001"},
            month_start=date(2026, 11, 1),
            month_end=date(2026, 12, 1),
            customer_map=customer_map or {},
            contract_external_id=7001,
        )

    def test_eligible_payment_is_mapped_and_snapshotted(self):
        result = self._evaluate(_details(), customer_map={501: 12})
        values = result["values"]
        assert result["eligible"] is True
        assert values["crm_customer_id"] == 12
        assert values["amount"] == Decimal("1200.50")
        assert values["industry_path"] == "1001/二手房"
        assert values["blocked_reason"] is None
        assert result["snapshot"] == {
            "customer_external_id": 501,
            "contract_external_id": 7001,
            "amount": "1200.50",
            "receive_date": "2026-11-05",
            "industry_path": "1001/二手房",
            "approve_status": APPROVED_STATUS,
        }

    def test_pending_approval_blocks_import(self):
        result = self._evaluate(_details(approve_status="applying"))
        assert result["eligible"] is False
        assert "CRM审批未通过" in result["values"]["blocked_reason"]

    def test_date_outside_month_blocks_import(self):
        result = self._evaluate(_details(receive_date="2026-10-31"))
        assert result["eligible"] is False
        assert "回款日期不在同步月份" in result["values"]["blocked_reason"]

    def test_invalid_amount_blocks_import(self):
        result = self._evaluate(_details(amount="0"))
        assert result["eligible"] is False
        assert "回款金额无效" in result["values"]["blocked_reason"]

    def test_industry_outside_whitelist_blocks_import(self):
        result = self._evaluate(_details(**{FIELD: "9999/其他"}))
        assert result["eligible"] is False
        assert "行业分类不在允许范围" in result["values"]["blocked_reason"]

    def test_industry_scope_flag_is_reported(self):
        """同步只录入允许行业：industry_ok 必须可直接判断，不靠 blocked_reason 字符串"""
        assert self._evaluate(_details())["industry_ok"] is True
        assert self._evaluate(_details(**{FIELD: "9999/其他"}))["industry_ok"] is False
        missing = _details()
        missing.pop(FIELD)
        missing.pop(f"{FIELD}_display", None)
        assert self._evaluate(missing)["industry_ok"] is False

    def test_unmapped_customer_leaves_crm_customer_id_none(self):
        result = self._evaluate(_details(), customer_map={})
        assert result["values"]["crm_customer_id"] is None

    def test_missing_contract_id_falls_back_to_argument(self):
        details = _details()
        details.pop("contract_id")
        result = self._evaluate(details)
        assert result["values"]["contract_external_id"] == 7001

    def test_source_updated_at_is_truncated_to_column_width(self):
        result = self._evaluate(_details(updated_at="2026-11-11T10:00:00" + "x" * 100))
        assert len(result["values"]["source_updated_at"]) == 64


class TestValidateImportAmounts:
    def test_matching_source_amount_passes(self):
        _validate_import_amounts(Decimal("100.00"), Decimal("10.00"), Decimal("100.00"))

    def test_missing_source_amount_rejected(self):
        with pytest.raises(CrmImportError):
            _validate_import_amounts(Decimal("100.00"), Decimal("0"), None)

    def test_real_amount_must_equal_source(self):
        with pytest.raises(CrmImportError):
            _validate_import_amounts(Decimal("99.99"), Decimal("0"), Decimal("100.00"))

    def test_bonus_must_be_non_negative(self):
        with pytest.raises(CrmImportError):
            _validate_import_amounts(Decimal("100.00"), Decimal("-1"), Decimal("100.00"))


def _record(**overrides) -> RechargeRecord:
    record = RechargeRecord(
        customer_id=12,
        real_amount=Decimal("1200.50"),
        bonus_amount=Decimal("100.00"),
        operator_id=1,
        recharge_date=date(2026, 11, 5),
        crm_payment_id=9001,
    )
    record.id = 88
    for key, value in overrides.items():
        setattr(record, key, value)
    return record


class TestExistingImportResponse:
    def test_same_target_and_amount_is_idempotent(self):
        result = build_existing_import_response(
            _record(),
            customer_id=12,
            real_amount=Decimal("1200.50"),
            bonus_amount=Decimal("100.00"),
            balance=None,
        )
        assert result["already_imported"] is True
        assert result["recharge_record_id"] == 88
        assert result["total_amount"] == "1300.50"
        assert result["recharge_date"] == "2026-11-05"
        assert result["balance"]["total_amount"] == "0.00"

    def test_different_customer_conflicts(self):
        with pytest.raises(CrmImportError):
            build_existing_import_response(
                _record(),
                customer_id=99,
                real_amount=Decimal("1200.50"),
                bonus_amount=Decimal("100.00"),
                balance=None,
            )

    def test_different_amount_conflicts(self):
        with pytest.raises(CrmImportError):
            build_existing_import_response(
                _record(),
                customer_id=12,
                real_amount=Decimal("1200.50"),
                bonus_amount=Decimal("0"),
                balance=None,
            )


def test_business_snapshot_is_stable_and_serializable():
    snapshot = _business_snapshot(
        customer_external_id=501,
        contract_external_id=7001,
        amount=Decimal("100.00"),
        receive_date=date(2026, 11, 5),
        industry_path="1001/二手房",
        approve_status=APPROVED_STATUS,
    )
    assert snapshot == {
        "customer_external_id": 501,
        "contract_external_id": 7001,
        "amount": "100.00",
        "receive_date": "2026-11-05",
        "industry_path": "1001/二手房",
        "approve_status": APPROVED_STATUS,
    }


def test_business_snapshot_quantizes_amount_to_two_decimals():
    """上游详情金额是 `50000.0`,镜像列 NUMERIC(12,2) 读回 `50000.00`;
    快照必须量化,否则每次导入都判定「已变更」(必现 409)。"""
    snapshot = _business_snapshot(
        customer_external_id=416367121,
        contract_external_id=34900815,
        amount=Decimal("50000.0"),
        receive_date=date(2026, 11, 6),
        industry_path="a/b",
        approve_status=APPROVED_STATUS,
    )
    assert snapshot["amount"] == "50000.00"


def test_snapshots_differ_ignores_amount_precision():
    """历史快照(未量化)与新快照必须判等,否则已导入记录会永久显示「已变更」"""
    live = {
        "customer_external_id": 416367121,
        "contract_external_id": 34900815,
        "amount": "50000.0",
        "receive_date": "2026-11-06",
        "industry_path": "a/b",
        "approve_status": APPROVED_STATUS,
    }
    stored = {**live, "amount": "50000.00"}
    assert _snapshots_differ(stored, live) is False
    assert _snapshots_differ({**stored, "amount": "50000.01"}, live) is True
    assert _snapshots_differ(None, live) is False


class TestCrmCustomerBindingService:
    """一对一绑定的冲突与幂等分支（严格一对一，先锁客户行）"""

    def _service(self, scalars):
        from unittest.mock import AsyncMock, MagicMock

        db = MagicMock()
        db.scalar = AsyncMock(side_effect=scalars)
        db.flush = AsyncMock()
        return CrmCustomerBindingService(db), db

    @pytest.mark.asyncio
    async def test_unbind_clears_binding(self):
        customer = Customer(id=1, company_id=1001, name="客户A", crm_customer_id=9)
        service, db = self._service([customer, 0])
        result = await service.bind(customer_id=1, crm_customer_id=None, corp_id="corp")
        assert customer.crm_customer_id is None
        assert result == {
            "crm_customer_id": None,
            "crm_customer_external_id": None,
            "crm_customer_name": None,
        }
        db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_missing_customer_raises(self):
        service, _ = self._service([None])
        with pytest.raises(CrmImportError) as exc:
            await service.bind(customer_id=1, crm_customer_id=9, corp_id="corp")
        assert exc.value.status == 400

    @pytest.mark.asyncio
    async def test_candidate_from_other_corp_raises(self):
        customer = Customer(id=1, company_id=1001, name="客户A")
        service, _ = self._service([customer, None])
        with pytest.raises(CrmImportError) as exc:
            await service.bind(customer_id=1, crm_customer_id=9, corp_id="corp")
        assert "CRM客户不存在" in exc.value.message

    @pytest.mark.asyncio
    async def test_already_bound_is_idempotent(self):
        candidate = CrmCustomer(
            id=9, corp_id="corp", external_id=501, name="CRM客户", normalized_name="crm客户"
        )
        customer = Customer(id=1, company_id=1001, name="客户A", crm_customer_id=9)
        service, _ = self._service([customer, candidate])
        result = await service.bind(customer_id=1, crm_customer_id=9, corp_id="corp")
        assert result["crm_customer_external_id"] == 501
        assert result["crm_customer_name"] == "CRM客户"

    @pytest.mark.asyncio
    async def test_occupied_by_other_customer_conflicts(self):
        candidate = CrmCustomer(
            id=9, corp_id="corp", external_id=501, name="CRM客户", normalized_name="crm客户"
        )
        customer = Customer(id=1, company_id=1001, name="客户A")
        service, _ = self._service([customer, candidate, 0, 77])
        with pytest.raises(CrmImportError) as exc:
            await service.bind(customer_id=1, crm_customer_id=9, corp_id="corp")
        assert exc.value.status == 409
        assert customer.crm_customer_id is None

    @pytest.mark.asyncio
    async def test_successful_bind_writes_customer(self):
        candidate = CrmCustomer(
            id=9, corp_id="corp", external_id=501, name="CRM客户", normalized_name="crm客户"
        )
        customer = Customer(id=1, company_id=1001, name="客户A")
        service, db = self._service([customer, candidate, 0, None])
        result = await service.bind(customer_id=1, crm_customer_id=9, corp_id="corp")
        assert customer.crm_customer_id == 9
        assert result["crm_customer_external_id"] == 501
        db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_unbind_blocked_when_customer_has_imported_recharge(self):
        """改绑不迁移资金：有导入记录时必须先撤销，否则旧记录永久挂在错客户"""
        customer = Customer(id=1, company_id=1001, name="客户A", crm_customer_id=9)
        service, db = self._service([customer, 1])
        with pytest.raises(CrmImportError) as exc:
            await service.bind(customer_id=1, crm_customer_id=None, corp_id="corp")
        assert exc.value.status == 409
        assert "请先撤销导入" in exc.value.message
        assert customer.crm_customer_id == 9

    @pytest.mark.asyncio
    async def test_rebind_blocked_when_customer_has_imported_recharge(self):
        candidate = CrmCustomer(
            id=10, corp_id="corp", external_id=502, name="CRM客户B", normalized_name="crm客户b"
        )
        customer = Customer(id=1, company_id=1001, name="客户A", crm_customer_id=9)
        service, db = self._service([customer, candidate, 2])
        with pytest.raises(CrmImportError) as exc:
            await service.bind(customer_id=1, crm_customer_id=10, corp_id="corp")
        assert exc.value.status == 409
        assert customer.crm_customer_id == 9
        db.flush.assert_not_awaited()


class TestCrmRechargeImportRevoke:
    """撤销导入：余额回退、释放回款、超管强制与线下核对标记"""

    def _service(self, scalars):
        from unittest.mock import AsyncMock, MagicMock

        db = MagicMock()
        db.scalar = AsyncMock(side_effect=scalars)
        db.execute = AsyncMock()
        db.delete = AsyncMock()
        db.flush = AsyncMock()
        return CrmRechargeImportService(db), db

    def _rows(
        self,
        *,
        balance_real: str = "50000.00",
        balance_bonus: str = "0.00",
        record_real: str = "50000.00",
        record_bonus: str = "0.00",
    ):
        customer = Customer(id=27647, company_id=1001, name="宿州诚信房产", crm_customer_id=2095)
        payment = CrmPayment(id=6, corp_id="corp", external_id=14427678)
        record = RechargeRecord(
            id=4662,
            customer_id=27647,
            real_amount=Decimal(record_real),
            bonus_amount=Decimal(record_bonus),
            crm_payment_id=6,
            recharge_date=date(2026, 11, 6),
        )
        balance = CustomerBalance(
            customer_id=27647,
            real_amount=Decimal(balance_real),
            bonus_amount=Decimal(balance_bonus),
            total_amount=Decimal(balance_real) + Decimal(balance_bonus),
        )
        return customer, payment, record, balance

    async def _revoke(self, service, **kwargs):
        params = {
            "payment_id": 6,
            "customer_id": 27647,
            "reason": "绑定CRM客户错误",
            "operator_id": 1,
            "corp_id": "corp",
            "is_super_admin": False,
            "force": False,
        }
        params.update(kwargs)
        return await service.revoke_import(**params)

    @pytest.mark.asyncio
    async def test_revoke_rolls_back_balance_and_releases_payment(self, monkeypatch):
        from unittest.mock import AsyncMock

        audit = AsyncMock()
        monkeypatch.setattr("app.services.crm_recharge.create_audit_entry", audit)

        customer, payment, record, balance = self._rows()
        payment.imported_snapshot = {"amount": "50000.00"}
        payment.source_changed = True
        service, db = self._service([customer, payment, record, balance])

        result = await self._revoke(service)

        assert result["balance"] == {
            "real_amount": "0.00",
            "bonus_amount": "0.00",
            "total_amount": "0.00",
        }
        assert result["needs_manual_reconciliation"] is False
        assert payment.imported_snapshot is None
        assert payment.source_changed is False
        db.delete.assert_awaited_once_with(record)
        assert audit.await_args.kwargs["changes"]["reason"] == "绑定CRM客户错误"

    @pytest.mark.asyncio
    async def test_missing_record_raises(self):
        customer, payment, _, balance = self._rows()
        service, _ = self._service([customer, payment, None, balance])
        with pytest.raises(CrmImportError) as exc:
            await self._revoke(service)
        assert exc.value.status == 400

    @pytest.mark.asyncio
    async def test_record_of_other_customer_raises(self):
        customer, payment, record, balance = self._rows()
        record.customer_id = 99999
        service, _ = self._service([customer, payment, record, balance])
        with pytest.raises(CrmImportError) as exc:
            await self._revoke(service)
        assert exc.value.status == 400

    @pytest.mark.asyncio
    async def test_insufficient_balance_requires_super_admin(self):
        customer, payment, record, balance = self._rows(balance_real="20000.00")
        service, db = self._service([customer, payment, record, balance])
        with pytest.raises(CrmImportError) as exc:
            await self._revoke(service)
        assert exc.value.status == 403
        assert "超级管理员" in exc.value.message
        db.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_super_admin_must_confirm_force(self):
        customer, payment, record, balance = self._rows(balance_real="20000.00")
        service, _ = self._service([customer, payment, record, balance])
        with pytest.raises(CrmImportError) as exc:
            await self._revoke(service, is_super_admin=True, force=False)
        assert exc.value.status == 409

    @pytest.mark.asyncio
    async def test_forced_revoke_marks_manual_reconciliation(self, monkeypatch):
        from unittest.mock import AsyncMock

        audit = AsyncMock()
        monkeypatch.setattr("app.services.crm_recharge.create_audit_entry", audit)

        customer, payment, record, balance = self._rows(balance_real="20000.00")
        service, db = self._service([customer, payment, record, balance])

        result = await self._revoke(service, is_super_admin=True, force=True)

        assert result["needs_manual_reconciliation"] is True
        assert result["shortfall_real"] == "30000.00"
        assert result["balance"]["real_amount"] == "-30000.00"
        assert audit.await_args.kwargs["changes"]["needs_manual_reconciliation"] is True
        db.delete.assert_awaited_once_with(record)
