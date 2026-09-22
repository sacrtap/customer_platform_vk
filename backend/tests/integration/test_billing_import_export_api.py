"""
Billing 导入导出 API 集成测试

覆盖新增端点：
1. POST /api/v1/billing/import                           (billing:balance_import)
   GET  /api/v1/billing/balances/export                  (billing:balance_export)
2. POST /api/v1/billing/pricing-rules/import             (billing:pricing_import)
   GET  /api/v1/billing/pricing-rules/import-template
   GET  /api/v1/billing/pricing-rules/export             (billing:pricing_export)
3. POST /api/v1/billing/package-plans/import             (billing:package_import)
   GET  /api/v1/billing/package-plans/import-template
   GET  /api/v1/billing/package-plans/export             (billing:package_export)
4. POST /api/v1/billing/invoices/import                  (billing:invoice_import)
   GET  /api/v1/billing/invoices/import-template
"""

import contextlib
import io
import uuid
from unittest.mock import AsyncMock

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import text

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(headers: list, rows: list, notes: list | None = None) -> bytes:
    """生成 xlsx 字节；notes 非空时写入第 2 行（模拟模板的中文说明行）"""
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    if notes:
        ws.append(notes)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(content: bytes, name: str = "import.xlsx") -> dict:
    return {"file": (name, content, XLSX_MIME)}


def _fill_template_example_row(
    template_body: bytes,
    values: dict[int, object],
    default_row: list | None = None,
    extra_rows: list | None = None,
) -> bytes:
    """把下载到的模板第 3 行改写为一整行真实数据，用于模板回灌验证

    各 ``import-template`` 端点已不再内嵌示例数据行（示例数据行会被
    ``read_import_dataframe`` 当作真实数据导入），因此这里先用 ``default_row``
    在第 3 行写入一整行合法数据，再用 ``values`` 按列号覆盖指定列，最后追加
    ``extra_rows``。
    """
    wb = load_workbook(io.BytesIO(template_body))
    ws = wb.active
    if default_row:
        for column, value in enumerate(default_row, start=1):
            ws.cell(row=3, column=column).value = value
    for column, value in values.items():
        ws.cell(row=3, column=column).value = value
    for row in extra_rows or []:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@contextlib.contextmanager
def _no_permissions():
    """临时清空权限缓存，用于验证权限拦截"""
    from app.cache import permissions as perm_module

    original = perm_module.permission_cache.get_permissions
    perm_module.permission_cache.get_permissions = AsyncMock(return_value=set())
    try:
        yield
    finally:
        perm_module.permission_cache.get_permissions = original


@pytest.fixture
async def import_customer(db_session):
    """创建导入测试客户，返回 {id, company_id}"""
    cid = 950000 + abs(hash(uuid.uuid4().hex[:8])) % 40000
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.execute(
        text(
            """
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :cid, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
            """
        ),
        {"id": cid, "cid": cid, "name": f"导入测试客户_{cid}"},
    )
    # 余额档案：真实业务路径（create_customer / batch_create_customers）会自动建档，
    # 这里用 raw SQL 造数据需显式补上，否则该客户在余额列表/导出中不可见
    db_session.execute(
        text(
            """
            INSERT INTO customer_balances (customer_id, total_amount, real_amount,
                                           bonus_amount, used_total, used_real, used_bonus,
                                           created_at, updated_at)
            VALUES (:cid, 10000, 8000, 2000, 0, 0, 0, NOW(), NOW())
            """
        ),
        {"cid": cid},
    )
    db_session.commit()

    try:
        yield {"id": cid, "company_id": cid}
    finally:
        for stmt in (
            "DELETE FROM pricing_rules WHERE customer_id = :cid",
            "DELETE FROM invoices WHERE customer_id = :cid",
            "DELETE FROM customer_balances WHERE customer_id = :cid",
            # 余额导入会创建 recharge_records（FK 指向 customers），须先于 customers 删除
            "DELETE FROM recharge_records WHERE customer_id = :cid",
            "DELETE FROM customers WHERE id = :cid",
        ):
            db_session.execute(text(stmt), {"cid": cid})
        db_session.commit()


# ==================== 余额导出 ====================


@pytest.mark.asyncio
async def test_export_balances_success(test_client, auth_token, import_customer):
    """余额导出：返回 xlsx 文件"""
    _request, response = await test_client.get(
        "/api/v1/billing/balances/export",
        params={"customer_id": import_customer["id"]},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status == 200
    assert "spreadsheetml" in response.headers.get("content-type", "")
    assert len(response.body) > 0
    # xlsx 为 zip 容器，魔数为 PK\x03\x04
    assert response.body[:2] == b"PK"


@pytest.mark.asyncio
async def test_export_balances_no_matching_data(test_client, auth_token):
    """余额导出：无匹配数据返回 40002"""
    _request, response = await test_client.get(
        "/api/v1/billing/balances/export",
        params={"customer_id": 999999999},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status == 400
    assert response.json["code"] == 40002


@pytest.mark.asyncio
async def test_export_balances_forbidden_without_permission(test_client, auth_token):
    """余额导出：缺少 billing:balance_export 权限返回 403"""
    with _no_permissions():
        _request, response = await test_client.get(
            "/api/v1/billing/balances/export",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert response.status == 403


# ==================== 余额导入 ====================


@pytest.mark.asyncio
async def test_import_balances_forbidden_without_permission(test_client, auth_token):
    """余额导入：缺少 billing:balance_import 权限返回 403"""
    with _no_permissions():
        _request, response = await test_client.post(
            "/api/v1/billing/import",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert response.status == 403


@pytest.mark.asyncio
async def test_import_balances_from_downloaded_template(
    test_client, auth_token, db_session, import_customer
):
    """下载的余额导入模板可直接导入：第 2 行中文说明行不被当作数据行"""
    _request, template = await test_client.get(
        "/api/v1/billing/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = _fill_template_example_row(
        template.body,
        {1: import_customer["company_id"]},
        # 模板已不含示例行，先补一整行合法数据，再用 values 覆盖 company_id
        default_row=[100001, 100.0, 50.0, None],
        # 追加一条未知客户的行，位于 Excel 第 4 行
        extra_rows=[[999999999, 10.0, 0.0, None]],
    )

    _request, response = await test_client.post(
        "/api/v1/billing/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    assert data["errors"][0].startswith("第 4 行")

    count = db_session.execute(
        text("SELECT COUNT(*) FROM recharge_records WHERE customer_id = :cid"),
        {"cid": import_customer["id"]},
    ).scalar()
    assert count == 1


# ==================== 计费规则导入 / 导出 ====================


@pytest.mark.asyncio
async def test_pricing_rule_import_template_download(test_client, auth_token):
    """计费规则导入模板可下载"""
    _request, response = await test_client.get(
        "/api/v1/billing/pricing-rules/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status == 200
    assert "spreadsheetml" in response.headers.get("content-type", "")
    assert response.body[:2] == b"PK"


@pytest.mark.asyncio
async def test_import_pricing_rules_from_downloaded_template(
    test_client, auth_token, db_session, import_customer
):
    """下载的模板可直接导入：说明行不被当作数据行，错误行号指向真实 Excel 行"""
    _request, template = await test_client.get(
        "/api/v1/billing/pricing-rules/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = _fill_template_example_row(
        template.body,
        {1: import_customer["company_id"]},
        # 模板已不含示例行，先补一整行合法数据，再用 values 覆盖 company_id
        default_row=[
            100001,
            "fixed",
            "2026-04-01",
            "X",
            "single",
            10.00,
            None,
            None,
            None,
            None,
            "2026-12-31",
        ],
        # 追加一条未知客户的行，位于 Excel 第 4 行
        extra_rows=[
            [999999999, "fixed", "2026-04-01", "X", "single", 12.5, None, None, None, None, None]
        ],
    )

    _request, response = await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    assert data["errors"][0].startswith("第 4 行")

    count = db_session.execute(
        text("SELECT COUNT(*) FROM pricing_rules WHERE customer_id = :cid AND deleted_at IS NULL"),
        {"cid": import_customer["id"]},
    ).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_import_pricing_rules_success_and_row_error(
    test_client, auth_token, db_session, import_customer
):
    """计费规则导入：有效行创建成功，未知客户行报错且不影响其他行"""
    headers = [
        "company_id",
        "pricing_type",
        "effective_date",
        "device_type",
        "layer_type",
        "unit_price",
        "additional_floor_price",
        "multi_floor_pricing_type",
        "tiers",
        "package_type",
        "expiry_date",
    ]
    notes = ["必填"] * 11
    rows = [
        [
            import_customer["company_id"],
            "fixed",
            "2026-04-01",
            "X",
            "single",
            12.5,
            None,
            None,
            None,
            None,
            None,
        ],
        [999999999, "fixed", "2026-04-01", "X", "single", 12.5, None, None, None, None, None],
    ]

    _request, response = await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows, notes)),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    assert "不存在" in data["errors"][0]

    # 成功行确实落库
    count = db_session.execute(
        text("SELECT COUNT(*) FROM pricing_rules WHERE customer_id = :cid AND deleted_at IS NULL"),
        {"cid": import_customer["id"]},
    ).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_import_pricing_rules_tiered(test_client, auth_token, db_session, import_customer):
    """计费规则导入：阶梯类型（tiers JSON）正确解析"""
    headers = [
        "company_id",
        "pricing_type",
        "effective_date",
        "device_type",
        "layer_type",
        "unit_price",
        "additional_floor_price",
        "multi_floor_pricing_type",
        "tiers",
        "package_type",
        "expiry_date",
    ]
    rows = [
        [
            import_customer["company_id"],
            "tiered",
            "2026-05-01",
            "N",
            "single",
            8.0,
            None,
            None,
            '[{"min": 0, "max": 100, "price": 8}, {"min": 101, "max": null, "price": 6}]',
            None,
            None,
        ]
    ]

    _request, response = await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    assert response.status == 200
    assert response.json["data"]["success_count"] == 1

    tiers = db_session.execute(
        text(
            "SELECT tiers FROM pricing_rules WHERE customer_id = :cid AND pricing_type = 'tiered'"
        ),
        {"cid": import_customer["id"]},
    ).scalar()
    assert tiers is not None


@pytest.mark.asyncio
async def test_import_pricing_rules_missing_required_column(test_client, auth_token):
    """计费规则导入：缺少必填列返回 40003"""
    _request, response = await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(["company_id", "unit_price"], [[100001, 10.0]])),
    )

    assert response.status == 400
    assert response.json["code"] == 40003
    assert "pricing_type" in response.json["message"]


@pytest.mark.asyncio
async def test_import_pricing_rules_invalid_tiers_json(test_client, auth_token, import_customer):
    """计费规则导入：非法 tiers JSON 产生行级错误"""
    headers = ["company_id", "pricing_type", "effective_date", "tiers"]
    rows = [[import_customer["company_id"], "tiered", "2026-06-01", "not-a-json"]]

    _request, response = await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    assert response.status == 200
    assert response.json["data"]["error_count"] == 1
    assert "阶梯配置" in response.json["data"]["errors"][0]


@pytest.mark.asyncio
async def test_import_pricing_rules_rejects_non_zero_first_tier_min(
    test_client, auth_token, import_customer
):
    """计费规则导入：首档 min 非 0 产生行级错误并拒绝落库

    `cost_calc._calc_tiered` 不减去首档 min 偏移，首档 min>0 时超档用量会落到更便宜的
    下一档（静默少收）、单档无上界时 min 完全不参与计算，故写入侧必须拒绝。
    """
    headers = [
        "company_id",
        "pricing_type",
        "effective_date",
        "device_type",
        "layer_type",
        "unit_price",
        "tiers",
    ]
    rows = [
        # 首档 min=5 → 不合法
        [
            import_customer["company_id"],
            "tiered",
            "2026-06-01",
            "X",
            "single",
            None,
            '[{"min": 5, "max": 100, "price": 10}, {"min": 101, "max": null, "price": 8}]',
        ],
        # 首档 min=0 → 合法
        [
            import_customer["company_id"],
            "tiered",
            "2026-06-01",
            "X",
            "single",
            None,
            '[{"min": 0, "max": 100, "price": 10}, {"min": 101, "max": null, "price": 8}]',
        ],
    ]

    _request, response = await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    error = data["errors"][0]
    assert "首档阶梯 min 必须为 0" in error
    assert error.startswith("第 2 行：")  # 第 1 行是说明行，数据行号为 Excel 行号


@pytest.mark.asyncio
async def test_import_pricing_rules_forbidden_without_permission(test_client, auth_token):
    """计费规则导入：缺少 billing:pricing_import 权限返回 403"""
    headers = ["company_id", "pricing_type", "effective_date"]
    rows = [[100001, "fixed", "2026-04-01"]]

    with _no_permissions():
        _request, response = await test_client.post(
            "/api/v1/billing/pricing-rules/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows)),
        )
    assert response.status == 403


@pytest.mark.asyncio
async def test_export_pricing_rules_success(test_client, auth_token, import_customer):
    """计费规则导出：返回 xlsx 文件"""
    # 先建一条规则保证有数据
    db_session_headers = [
        "company_id",
        "pricing_type",
        "effective_date",
        "device_type",
        "layer_type",
        "unit_price",
    ]
    await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(
            _xlsx(
                db_session_headers,
                [[import_customer["company_id"], "fixed", "2026-07-01", "L", "single", 9.9]],
            )
        ),
    )

    _request, response = await test_client.get(
        "/api/v1/billing/pricing-rules/export",
        params={"customer_id": import_customer["id"]},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status == 200
    assert response.body[:2] == b"PK"


@pytest.mark.asyncio
async def test_export_pricing_rules_date_round_trip(
    test_client, auth_token, db_session, import_customer
):
    """生效日期导出后再导入不得漂移（导出必须是 CST 日期本身）

    回归：导出曾直接 ``isoformat()`` 输出 UTC 时刻（CST 2026-07-01 存为
    2026-06-30T16:00:00+00:00），导入端按 ``str(...)[:10]`` 取到 2026-06-30
    再按 CST 解析，导出→导入整体提前一天。
    """
    headers = [
        "company_id",
        "pricing_type",
        "effective_date",
        "device_type",
        "layer_type",
        "unit_price",
    ]
    await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(
            _xlsx(
                headers,
                [[import_customer["company_id"], "fixed", "2026-07-01", "L", "single", 9.9]],
            )
        ),
    )

    async def _export() -> bytes:
        _req, resp = await test_client.get(
            "/api/v1/billing/pricing-rules/export",
            params={"customer_id": import_customer["id"]},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status == 200
        return resp.body

    def _effective_date_cell(body: bytes) -> object:
        ws = load_workbook(io.BytesIO(body)).active
        columns = [cell.value for cell in ws[1]]
        return ws.cell(row=2, column=columns.index("effective_date") + 1).value

    exported = await _export()
    # 导出的日期就是用户填写的 CST 日期，不带时间与时区
    assert _effective_date_cell(exported) == "2026-07-01"

    # 删除原规则后回灌导出的文件（否则会命中「有效期存在重叠」校验）
    rule_id = db_session.execute(
        text("SELECT id FROM pricing_rules WHERE customer_id = :cid AND deleted_at IS NULL"),
        {"cid": import_customer["id"]},
    ).scalar()
    _request, deleted = await test_client.delete(
        f"/api/v1/billing/pricing-rules/{rule_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert deleted.status == 200

    _request, reimported = await test_client.post(
        "/api/v1/billing/pricing-rules/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(exported),
    )
    assert reimported.status == 200
    assert reimported.json["data"]["success_count"] == 1

    # 回灌后再次导出，日期仍是 2026-07-01（未提前一天）
    assert _effective_date_cell(await _export()) == "2026-07-01"


@pytest.mark.asyncio
async def test_export_pricing_rules_forbidden_without_permission(test_client, auth_token):
    """计费规则导出：缺少权限返回 403"""
    with _no_permissions():
        _request, response = await test_client.get(
            "/api/v1/billing/pricing-rules/export",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert response.status == 403


# ==================== 包年套餐导入 / 导出 ====================


@pytest.mark.asyncio
async def test_package_plan_import_template_download(test_client, auth_token):
    """包年套餐导入模板可下载"""
    _request, response = await test_client.get(
        "/api/v1/billing/package-plans/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status == 200
    assert response.body[:2] == b"PK"


@pytest.mark.asyncio
async def test_import_package_plans_from_downloaded_template(test_client, auth_token, db_session):
    """下载的模板可直接导入：第 2 行中文说明行不被当作数据行"""
    suffix = uuid.uuid4().hex[:6].upper()
    ptype = f"TPL{suffix}"

    _request, template = await test_client.get(
        "/api/v1/billing/package-plans/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = _fill_template_example_row(
        template.body,
        {1: f"模板套餐_{suffix}", 2: ptype},
        # 模板已不含示例行，先补一整行合法数据，再用 values 覆盖 name/package_type
        default_row=[
            "A 套餐",
            "A",
            50000.00,
            "X",
            "single",
            "否",
            10000,
            5.00,
            "示例套餐",
            "active",
        ],
    )

    try:
        _request, response = await test_client.post(
            "/api/v1/billing/package-plans/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(body),
        )

        assert response.status == 200
        data = response.json["data"]
        assert data["errors"] == []
        assert data["success_count"] == 1

        exists = db_session.execute(
            text("SELECT COUNT(*) FROM package_plans WHERE package_type = :pt"), {"pt": ptype}
        ).scalar()
        assert exists == 1
    finally:
        db_session.execute(
            text("DELETE FROM package_plans WHERE package_type = :pt"), {"pt": ptype}
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_import_package_plans_success(test_client, auth_token, db_session):
    """包年套餐导入：成功创建"""
    suffix = uuid.uuid4().hex[:6].upper()
    headers = [
        "name",
        "package_type",
        "base_fee",
        "device_type",
        "layer_type",
        "is_unlimited",
        "limit_count",
        "over_limit_unit_price",
        "description",
        "status",
    ]
    notes = ["必填"] * 10
    rows = [
        [
            f"导入测试套餐_{suffix}",
            f"IMP{suffix}",
            30000.0,
            "X",
            "single",
            "否",
            5000,
            6.0,
            "测试",
            "active",
        ]
    ]

    try:
        _request, response = await test_client.post(
            "/api/v1/billing/package-plans/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows, notes)),
        )

        assert response.status == 200
        assert response.json["data"]["success_count"] == 1

        plan_type = db_session.execute(
            text("SELECT package_type FROM package_plans WHERE package_type = :pt"),
            {"pt": f"IMP{suffix}"},
        ).scalar()
        assert plan_type == f"IMP{suffix}"
    finally:
        db_session.execute(
            text("DELETE FROM package_plans WHERE package_type = :pt"), {"pt": f"IMP{suffix}"}
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_import_package_plans_duplicate_type(test_client, auth_token, db_session):
    """包年套餐导入：package_type 重复产生行级错误"""
    suffix = uuid.uuid4().hex[:6].upper()
    ptype = f"DUP{suffix}"
    db_session.execute(
        text(
            """
            INSERT INTO package_plans (name, package_type, is_unlimited, base_fee, status, created_at, updated_at)
            VALUES (:name, :ptype, FALSE, 10000, 'active', NOW(), NOW())
            """
        ),
        {"name": f"已存在套餐_{suffix}", "ptype": ptype},
    )
    db_session.commit()

    headers = ["name", "package_type", "base_fee"]
    rows = [[f"重复套餐_{suffix}", ptype, 20000.0]]

    try:
        _request, response = await test_client.post(
            "/api/v1/billing/package-plans/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows)),
        )

        assert response.status == 200
        data = response.json["data"]
        assert data["success_count"] == 0
        assert data["error_count"] == 1
        assert "已存在" in data["errors"][0]
    finally:
        db_session.execute(
            text("DELETE FROM package_plans WHERE package_type = :ptype"), {"ptype": ptype}
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_import_package_plans_missing_required_column(test_client, auth_token):
    """包年套餐导入：缺少必填列返回 40003"""
    _request, response = await test_client.post(
        "/api/v1/billing/package-plans/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(["name", "base_fee"], [["套餐A", 1000.0]])),
    )

    assert response.status == 400
    assert response.json["code"] == 40003
    assert "package_type" in response.json["message"]


@pytest.mark.asyncio
async def test_import_package_plans_invalid_base_fee(test_client, auth_token):
    """包年套餐导入：基础费用非数字时给出可读的行级错误"""
    headers = ["name", "package_type", "base_fee"]
    rows = [["非法费用套餐", f"BAD{uuid.uuid4().hex[:6].upper()}", "待确认"]]

    _request, response = await test_client.post(
        "/api/v1/billing/package-plans/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 0
    assert data["error_count"] == 1
    assert "基础费用格式错误" in data["errors"][0]


@pytest.mark.asyncio
async def test_export_package_plans_success(test_client, auth_token, db_session):
    """包年套餐导出：无匹配数据返回 40002；有数据时返回包含该行的 xlsx"""
    suffix = uuid.uuid4().hex[:6].upper()
    ptype = f"EXP{suffix}"

    _request, empty_response = await test_client.get(
        "/api/v1/billing/package-plans/export",
        params={"keyword": "不存在的套餐关键字_zzz"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert empty_response.status == 400
    assert empty_response.json["code"] == 40002

    db_session.execute(
        text(
            """
            INSERT INTO package_plans (name, package_type, is_unlimited, base_fee, status, created_at, updated_at)
            VALUES (:name, :ptype, FALSE, 12000, 'active', NOW(), NOW())
            """
        ),
        {"name": f"导出测试套餐_{suffix}", "ptype": ptype},
    )
    db_session.commit()

    try:
        _request, response = await test_client.get(
            "/api/v1/billing/package-plans/export",
            params={"keyword": ptype},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        assert response.body[:2] == b"PK"

        ws = load_workbook(io.BytesIO(response.body)).active
        header_row = [cell.value for cell in ws[1]]
        exported_types = [
            row[header_row.index("package_type")]
            for row in ws.iter_rows(min_row=2, values_only=True)
        ]
        assert exported_types == [ptype]
    finally:
        db_session.execute(
            text("DELETE FROM package_plans WHERE package_type = :ptype"), {"ptype": ptype}
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_import_package_plans_forbidden_without_permission(test_client, auth_token):
    """包年套餐导入：缺少 billing:package_import 权限返回 403"""
    headers = ["name", "package_type", "base_fee"]
    rows = [["权限测试套餐", "PERM_TEST", 1000.0]]

    with _no_permissions():
        _request, response = await test_client.post(
            "/api/v1/billing/package-plans/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows)),
        )
    assert response.status == 403


@pytest.mark.asyncio
async def test_export_package_plans_forbidden_without_permission(test_client, auth_token):
    """包年套餐导出：缺少权限返回 403"""
    with _no_permissions():
        _request, response = await test_client.get(
            "/api/v1/billing/package-plans/export",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert response.status == 403


# ==================== 结算单导入 ====================


@pytest.mark.asyncio
async def test_invoice_import_template_download(test_client, auth_token):
    """结算单导入模板可下载，且列名/列序与术语契约保持稳定"""
    _request, response = await test_client.get(
        "/api/v1/billing/invoices/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status == 200
    assert response.body[:2] == b"PK"

    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active
    header = [c.value for c in ws[1]]
    notes = [c.value for c in ws[2]]

    # 列名与列顺序：改动会使已下载模板的存量导入错列
    assert header == [
        "company_id",
        "period_start",
        "period_end",
        "total_amount",
        "discount_amount",
        "invoice_no",
    ], header
    # 第 2 行说明行前缀契约：excel_import._is_template_note_row 依赖「必填」/「可选」开头
    assert all(str(v).startswith(("必填：", "可选：")) for v in notes if v), notes
    assert len(notes) == len(header), (notes, header)
    # 用户可见文案统一为「减免」，不得回退为「折扣」
    assert notes[4] == "可选：减免金额（元）", notes
    assert "折扣" not in "".join(str(v) for v in header + notes), (header, notes)
    # 说明行不被当作数据行（导入无虚假行级错误）由 test_import_invoices_from_downloaded_template 覆盖


@pytest.mark.asyncio
async def test_import_invoices_from_downloaded_template(
    test_client, auth_token, db_session, import_customer
):
    """下载的模板可直接导入：第 2 行中文说明行不被当作数据行"""
    _request, template = await test_client.get(
        "/api/v1/billing/invoices/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    # 模板不再内嵌示例数据行，在返回的 workbook 上追加一行真实数据后上传
    wb = load_workbook(io.BytesIO(template.body))
    wb.active.append([import_customer["company_id"], "2026-04-01", "2026-04-30", 12500.50, 0, None])
    buf = io.BytesIO()
    wb.save(buf)
    body = buf.getvalue()

    _request, response = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["errors"] == []
    assert data["success_count"] == 1

    status = db_session.execute(
        text("SELECT status FROM invoices WHERE customer_id = :cid"),
        {"cid": import_customer["id"]},
    ).scalar()
    assert status == "draft"


@pytest.mark.asyncio
async def test_import_invoices_success_as_draft(
    test_client, auth_token, db_session, import_customer
):
    """结算单导入：创建成功、状态为 draft、invoice_no 自动生成"""
    headers = [
        "company_id",
        "period_start",
        "period_end",
        "total_amount",
        "discount_amount",
        "invoice_no",
    ]
    notes = ["必填"] * 6
    rows = [[import_customer["company_id"], "2026-04-01", "2026-04-30", 15800.5, 0, None]]

    _request, response = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows, notes)),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 0

    row = db_session.execute(
        text("SELECT invoice_no, status, is_auto_generated FROM invoices WHERE customer_id = :cid"),
        {"cid": import_customer["id"]},
    ).first()
    assert row is not None
    assert row[1] == "draft"
    assert row[2] is False
    assert row[0].startswith("INV-")


@pytest.mark.asyncio
async def test_import_invoices_row_errors(test_client, auth_token, import_customer):
    """结算单导入：未知客户、负金额与非数字金额均产生可读的行级错误"""
    headers = ["company_id", "period_start", "period_end", "total_amount"]
    rows = [
        [999999998, "2026-04-01", "2026-04-30", 100.0],
        [import_customer["company_id"], "2026-04-01", "2026-04-30", -50.0],
        [import_customer["company_id"], "2026-04-01", "2026-04-30", "待确认"],
    ]

    _request, response = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 0
    assert data["error_count"] == 3
    assert any("不存在" in e for e in data["errors"])
    assert any("负数" in e for e in data["errors"])
    assert any("结算金额格式错误" in e for e in data["errors"])


@pytest.mark.asyncio
async def test_import_invoices_duplicate_invoice_no(
    test_client, auth_token, db_session, import_customer
):
    """结算单导入：重复结算单号产生行级错误"""
    dup_no = f"INV-DUP-{uuid.uuid4().hex[:8]}"
    db_session.execute(
        text(
            """
            INSERT INTO invoices (invoice_no, customer_id, period_start, period_end,
                                  total_amount, discount_amount, status, is_auto_generated,
                                  created_at, updated_at)
            VALUES (:no, :cid, '2026-01-01', '2026-01-31', 100, 0, 'draft', FALSE, NOW(), NOW())
            """
        ),
        {"no": dup_no, "cid": import_customer["id"]},
    )
    db_session.commit()

    headers = ["company_id", "period_start", "period_end", "total_amount", "invoice_no"]
    rows = [[import_customer["company_id"], "2026-05-01", "2026-05-31", 200.0, dup_no]]

    _request, response = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 0
    assert data["error_count"] == 1
    assert "已存在" in data["errors"][0]


@pytest.mark.asyncio
async def test_import_invoices_row_db_error_isolation(
    test_client, auth_token, db_session, import_customer
):
    """结算单导入：单行的 DB 级失败（单号超长）不得拖垮整批

    回归防护 —— 行级错误若只记录而不回滚会话，SQLAlchemy 会话会进入
    PendingRollback，后续行的 flush 与最终 commit 全部失败，整批（含已 flush
    成功的行）一并落空，接口退化为 500。
    """
    headers = ["company_id", "period_start", "period_end", "total_amount", "invoice_no"]
    rows = [
        [import_customer["company_id"], "2026-04-01", "2026-04-30", 100.0, None],
        # invoice_no 列定义 String(50)：60 字符触发 DB 级 flush 错误
        [import_customer["company_id"], "2026-05-01", "2026-05-31", 200.0, "X" * 60],
        [import_customer["company_id"], "2026-06-01", "2026-06-30", 300.0, None],
    ]

    _request, response = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["success_count"] == 2, data
    assert data["error_count"] == 1, data

    count = db_session.execute(
        text("SELECT COUNT(*) FROM invoices WHERE customer_id = :cid"),
        {"cid": import_customer["id"]},
    ).scalar()
    assert count == 2, count


@pytest.mark.asyncio
async def test_import_invoices_forbidden_without_permission(test_client, auth_token):
    """结算单导入：缺少 billing:invoice_import 权限返回 403"""
    headers = ["company_id", "period_start", "period_end", "total_amount"]
    rows = [[100001, "2026-04-01", "2026-04-30", 100.0]]

    with _no_permissions():
        _request, response = await test_client.post(
            "/api/v1/billing/invoices/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows)),
        )
    assert response.status == 403


@pytest.mark.asyncio
async def test_import_pricing_rules_requires_device_and_layer_for_non_package(
    test_client, auth_token, db_session, import_customer
):
    """计费规则导入：非包年结算的设备类型/楼层类型必填且限值域，包年行不受约束"""
    # 包年行须引用存在且 status='active' 的套餐：套餐不存在/已停用时按行级错误拒绝，
    # 避免静默创建 unit_price=None 的规则并在结算时按 0 元少计费。
    ptype = f"PLAN{uuid.uuid4().hex[:6].upper()}"
    db_session.execute(
        text(
            """
            INSERT INTO package_plans (name, package_type, is_unlimited, base_fee, status, created_at, updated_at)
            VALUES (:name, :ptype, FALSE, 10000, 'active', NOW(), NOW())
            """
        ),
        {"name": f"规则导入套餐_{ptype}", "ptype": ptype},
    )
    db_session.commit()

    headers = [
        "company_id",
        "pricing_type",
        "effective_date",
        "device_type",
        "layer_type",
        "unit_price",
        "additional_floor_price",
        "multi_floor_pricing_type",
        "tiers",
        "package_type",
        "expiry_date",
    ]
    rows = [
        # 设备类型与楼层类型均缺失 → 报首个缺失字段（设备类型）
        [
            import_customer["company_id"],
            "fixed",
            "2026-04-01",
            None,
            None,
            12.5,
            None,
            None,
            None,
            None,
            None,
        ],
        # 设备类型取值非法 → 行级错误
        [
            import_customer["company_id"],
            "tiered",
            "2026-04-01",
            "abc",
            "single",
            None,
            None,
            None,
            '[{"min":0,"max":null,"price":5}]',
            None,
            None,
        ],
        # 设备类型合法但楼层类型缺失 → 行级错误
        [
            import_customer["company_id"],
            "fixed",
            "2026-04-01",
            "X",
            None,
            8.8,
            None,
            None,
            None,
            None,
            None,
        ],
        # 楼层类型取值非法 → 行级错误
        [
            import_customer["company_id"],
            "fixed",
            "2026-04-01",
            "X",
            "floor-9",
            9.9,
            None,
            None,
            None,
            None,
            None,
        ],
        # 包年结算：设备类型/楼层类型允许为空 → 成功导入
        [
            import_customer["company_id"],
            "package",
            "2026-06-01",
            None,
            None,
            None,
            None,
            None,
            None,
            ptype,
            None,
        ],
    ]

    try:
        _request, response = await test_client.post(
            "/api/v1/billing/pricing-rules/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows)),
        )

        assert response.status == 200
        data = response.json["data"]
        assert data["success_count"] == 1
        assert data["error_count"] == 4
        joined = " ".join(data["errors"])
        assert "设备类型不能为空" in joined
        assert "楼层类型不能为空" in joined
        assert "设备类型必须为 X/N/L" in joined
        assert "楼层类型必须为 single/multi/single_and_multi" in joined
    finally:
        db_session.execute(
            text("DELETE FROM package_plans WHERE package_type = :ptype"), {"ptype": ptype}
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_balances_list_excludes_customer_without_archive(test_client, auth_token, db_session):
    """余额列表：无余额档案的客户不入结果，total 与 list 一致，且不触发建档写入"""
    cid = 930000 + abs(hash(uuid.uuid4().hex[:8])) % 40000
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.execute(
        text(
            """
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :cid, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
            """
        ),
        {"id": cid, "cid": cid, "name": f"无余额档案客户_{cid}"},
    )
    db_session.commit()

    try:
        _request, response = await test_client.get(
            "/api/v1/billing/balances",
            params={"customer_id": cid},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status == 200
        data = response.json["data"]
        # 无档案客户不可见；total 与实际返回行数保持一致（不得出现 total=0 却带数据行）
        assert data["total"] == 0
        assert data["list"] == []

        # 查询过程不得写入（旧实现的惰性补建在同请求内可见但会被回滚）
        db_session.expire_all()
        archived = db_session.execute(
            text("SELECT COUNT(*) FROM customer_balances WHERE customer_id = :cid"),
            {"cid": cid},
        ).scalar()
        assert archived == 0
    finally:
        for stmt in (
            "DELETE FROM customer_balances WHERE customer_id = :cid",
            "DELETE FROM customers WHERE id = :cid",
        ):
            db_session.execute(text(stmt), {"cid": cid})
        db_session.commit()
