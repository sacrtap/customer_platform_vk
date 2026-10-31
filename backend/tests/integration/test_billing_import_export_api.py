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
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import text

from app.utils.timezone import local_date_to_utc_start

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


@pytest.mark.asyncio
async def test_import_balances_accepts_export_file_columns(
    test_client, auth_token, db_session, import_customer
):
    """余额导出文件（中文展示列）可直接回灌导入，不再报「缺少必填列」

    回归防护 —— 导出列是中文展示名（客户ID/实充余额（元）/赠送余额（元）），
    导入期待英文列；此前导出文件回灌报 40003「Excel 缺少必填列：company_id,
    real_amount, bonus_amount」，用户误以为文件损坏。修复后列名自动归一，
    按同一校验路径处理（快照金额按本次充值入账；0 元充值 2026-10-13 起允许导入）。
    """
    # 模拟 /billing/balances/export 的导出文件结构（中文列名）
    body = _xlsx(
        [
            "客户ID",
            "客户名称",
            "行业",
            "账号类型",
            "结算方式",
            "余额（元）",
            "实充余额（元）",
            "赠送余额（元）",
            "已消耗（元）",
            "最新充值时间",
            "预计可支撑天数",
            "日均消耗（元）",
            "消耗天数",
        ],
        [
            [
                import_customer["company_id"],
                "测试客户",
                "项目",
                "正式账号",
                "prepaid",
                150,
                100,
                50,
                0,
                None,
                None,
                None,
                0,
            ],
            [
                999999999,
                "不存在的客户",
                "项目",
                "正式账号",
                "prepaid",
                0,
                0,
                0,
                0,
                None,
                None,
                None,
                0,
            ],
            # 余额为 0 的快照行：列名可识别；0 元充值允许导入（2026-10-13 起）
            [
                import_customer["company_id"],
                "测试客户",
                "项目",
                "正式账号",
                "prepaid",
                0,
                0,
                0,
                0,
                None,
                None,
                None,
                0,
            ],
            # 负实充快照行（后付费应收余额场景）：负金额允许导入（2026-10-13 起），
            # 按充值记录入账并扣减余额
            [
                import_customer["company_id"],
                "测试客户",
                "项目",
                "正式账号",
                "prepaid",
                -40,
                -50,
                10,
                0,
                None,
                None,
                None,
                0,
            ],
        ],
    )

    _request, response = await test_client.post(
        "/api/v1/billing/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )

    # 列级错误消失：不再报「缺少必填列」，进入行级校验
    assert response.status == 200
    assert response.json["code"] == 0
    data = response.json["data"]
    # 有效行 3（0 元、正金额 2026-10-13 起均可导入）、不存在客户 1 行报错
    assert data["success_count"] == 3, data
    assert data["error_count"] == 1, data
    assert any("客户编号 999999999 不存在" in e for e in data["errors"]), data["errors"]

    # 三行充值记录精确落库（含 0 元与负金额行）
    records = db_session.execute(
        text(
            "SELECT real_amount, bonus_amount FROM recharge_records "
            "WHERE customer_id = :cid ORDER BY id"
        ),
        {"cid": import_customer["id"]},
    ).all()
    assert [tuple(r) for r in records] == [
        (100.0, 50.0),
        (0.0, 0.0),
        (-50.0, 10.0),
    ], records

    # 余额按三行累加：real 8000+100+0-50=8050、bonus 2000+50+0+10=2060
    bal = db_session.execute(
        text("SELECT real_amount, bonus_amount FROM customer_balances WHERE customer_id = :cid"),
        {"cid": import_customer["id"]},
    ).one()
    assert (bal[0], bal[1]) == (8050.0, 2060.0), bal


@pytest.mark.asyncio
async def test_import_balances_dry_run_preview(
    test_client, auth_token, db_session, import_customer
):
    """余额导入预检查（dry_run=true）：完整行级校验但不落库

    与客户导入预检查同模式：返回可入库条数与错误明细（含行号），
    不生成充值记录、不写审计、不动缓存；确认后才真正导入。
    """
    body = _xlsx(
        ["company_id", "real_amount", "bonus_amount", "remark"],
        [
            [import_customer["company_id"], 100.0, 50.0, "预检测试"],
            [999999999, 10.0, 0.0, None],
        ],
    )

    # 预检查：合法行 1、错误行 1，且不落库
    _request, response = await test_client.post(
        "/api/v1/billing/import?dry_run=true",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )

    assert response.status == 200
    assert response.json["code"] == 0
    data = response.json["data"]
    assert data["dry_run"] is True
    assert data["success_count"] == 1, data
    assert data["error_count"] == 1, data
    assert data["errors"][0].startswith("第 3 行"), data["errors"]

    count = db_session.execute(
        text("SELECT COUNT(*) FROM recharge_records WHERE customer_id = :cid"),
        {"cid": import_customer["id"]},
    ).scalar()
    assert count == 0, f"预检查不应落库，实际 {count} 条"

    # 正式导入：同样文件真实落库 1 条
    _request, response = await test_client.post(
        "/api/v1/billing/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1, data

    count = db_session.execute(
        text("SELECT COUNT(*) FROM recharge_records WHERE customer_id = :cid"),
        {"cid": import_customer["id"]},
    ).scalar()
    assert count == 1


# ==================== 计费规则导入 / 导出 ====================


@pytest.mark.asyncio
async def test_import_pricing_rules_dry_run_preview(
    test_client, auth_token, db_session, import_customer
):
    """计费规则导入预检查（dry_run=true）：完整行级校验但不落库

    与余额/客户导入预检查同模式：返回可入库条数与错误明细（含行号），
    不创建定价规则、不写审计、不动缓存；确认后才真正导入。
    """
    headers = [
        "company_id",
        "pricing_type",
        "effective_date",
        "device_type",
        "layer_type",
        "unit_price",
    ]
    notes = ["必填"] * 6
    rows = [
        # 合法行 + 未知客户行（避开其他测试的 2026-04-01 账期）
        [import_customer["company_id"], "fixed", "2026-05-01", "X", "single", 12.5],
        [999999999, "fixed", "2026-05-01", "X", "single", 12.5],
    ]
    try:
        # 预检查：合法行 1、错误行 1，且不落库
        _request, response = await test_client.post(
            "/api/v1/billing/pricing-rules/import?dry_run=true",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows, notes)),
        )
        assert response.status == 200
        assert response.json["code"] == 0
        data = response.json["data"]
        assert data["dry_run"] is True
        assert data["success_count"] == 1, data
        assert data["error_count"] == 1, data
        # 带模板说明行（第 2 行）时非法行为 Excel 第 4 行：说明行被丢弃且行号仍
        # 指向真实 Excel 行
        assert data["errors"][0].startswith("第 4 行") and "不存在" in data["errors"][0]

        count = db_session.execute(
            text(
                "SELECT COUNT(*) FROM pricing_rules "
                "WHERE customer_id = :cid AND effective_date = :ed"
            ),
            {"cid": import_customer["id"], "ed": local_date_to_utc_start("2026-05-01")},
        ).scalar()
        assert count == 0, f"预检查不应落库，实际 {count} 条"

        # 正式导入：同样文件真实落库 1 条
        _request, response = await test_client.post(
            "/api/v1/billing/pricing-rules/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows, notes)),
        )
        assert response.status == 200
        assert response.json["data"]["success_count"] == 1

        count = db_session.execute(
            text(
                "SELECT COUNT(*) FROM pricing_rules "
                "WHERE customer_id = :cid AND effective_date = :ed"
            ),
            {"cid": import_customer["id"], "ed": local_date_to_utc_start("2026-05-01")},
        ).scalar()
        assert count == 1
    finally:
        db_session.execute(
            text("DELETE FROM pricing_rules WHERE customer_id = :cid AND effective_date = :ed"),
            {"cid": import_customer["id"], "ed": local_date_to_utc_start("2026-05-01")},
        )
        db_session.commit()


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
async def test_import_package_plans_dry_run_preview(test_client, auth_token, db_session):
    """包年套餐导入预检查（dry_run=true）：完整行级校验但不落库

    与计费规则/余额/客户导入预检查同模式：返回可入库条数与错误明细（含行号），
    不创建套餐、不写审计、不动缓存；确认后才真正导入。
    """
    suffix = uuid.uuid4().hex[:6].upper()
    ptype = f"DRY{suffix}"
    headers = ["name", "package_type", "base_fee", "is_unlimited"]
    notes = ["必填"] * 4
    rows = [
        [f"预检查测试套餐_{suffix}", ptype, 30000.0, "是"],
        [f"预检查非法套餐_{suffix}", f"DRYB{suffix}", -5.0, "是"],
    ]
    try:
        # 预检查：合法行 1、错误行 1（负数基础费用），且不落库
        _request, response = await test_client.post(
            "/api/v1/billing/package-plans/import?dry_run=true",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows, notes)),
        )
        assert response.status == 200
        assert response.json["code"] == 0
        data = response.json["data"]
        assert data["dry_run"] is True
        assert data["success_count"] == 1, data
        assert data["error_count"] == 1, data
        # 带模板说明行（第 2 行）时非法行为 Excel 第 4 行：验证说明行被丢弃且
        # 行号仍指向真实 Excel 行
        assert data["errors"][0].startswith("第 4 行") and "负数" in data["errors"][0]

        count = db_session.execute(
            text("SELECT COUNT(*) FROM package_plans WHERE package_type IN (:pt, :pb)"),
            {"pt": ptype, "pb": f"DRYB{suffix}"},
        ).scalar()
        assert count == 0, f"预检查不应落库，实际 {count} 条"

        # 正式导入：同样文件真实落库 1 条
        _request, response = await test_client.post(
            "/api/v1/billing/package-plans/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows, notes)),
        )
        assert response.status == 200
        assert response.json["data"]["success_count"] == 1

        count = db_session.execute(
            text("SELECT COUNT(*) FROM package_plans WHERE package_type = :pt"),
            {"pt": ptype},
        ).scalar()
        assert count == 1
    finally:
        db_session.execute(
            text("DELETE FROM package_plans WHERE package_type IN (:pt, :pb)"),
            {"pt": ptype, "pb": f"DRYB{suffix}"},
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
async def test_export_package_plans_reimport_round_trip(test_client, auth_token, db_session):
    """包年套餐导出文件可直接回灌导入（导出 ⊇ 模板列契约）

    回归防护：导出含 id/created_at/updated_at 展示列，导入解析须忽略多余列；
    若导出列与模板列错位（如新增列未入模板或解析漏读），回灌会整批失败。
    """
    suffix = uuid.uuid4().hex[:6].upper()
    ptype = f"RTT{suffix}"

    db_session.execute(
        text(
            """
            INSERT INTO package_plans (name, package_type, is_unlimited, base_fee,
                                       device_type, layer_type, limit_count,
                                       over_limit_unit_price, description, status,
                                       created_at, updated_at)
            VALUES (:name, :ptype, FALSE, 25000, 'X', 'multi', 500,
                    10.5, '回灌契约套餐', 'active', NOW(), NOW())
            """
        ),
        {"name": f"回灌套餐_{suffix}", "ptype": ptype},
    )
    db_session.commit()

    try:
        _request, exported = await test_client.get(
            "/api/v1/billing/package-plans/export",
            params={"keyword": ptype},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert exported.status == 200

        # 回灌前先删除原套餐：避免命中「package_type 已存在」去重
        db_session.execute(
            text("DELETE FROM package_plans WHERE package_type = :ptype"), {"ptype": ptype}
        )
        db_session.commit()

        _request, reimported = await test_client.post(
            "/api/v1/billing/package-plans/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(exported.body),
        )
        assert reimported.status == 200
        data = reimported.json["data"]
        assert data["success_count"] == 1, data["errors"]
        assert data["error_count"] == 0, data["errors"]

        # 回灌后字段完整落库（含模板列与展示列之外的处理）
        row = db_session.execute(
            text(
                "SELECT name, package_type, is_unlimited, base_fee, device_type, layer_type, "
                "limit_count, over_limit_unit_price, description, status "
                "FROM package_plans WHERE package_type = :ptype AND deleted_at IS NULL"
            ),
            {"ptype": ptype},
        ).first()
        assert row is not None, "回灌后套餐未落库"
        assert row[2] is False  # is_unlimited（导出 bool → 导入解析）
        assert float(row[3]) == 25000.0  # base_fee
        assert row[4] == "X"  # device_type
        assert row[5] == "multi"  # layer_type
        assert row[6] == 500  # limit_count
        assert float(row[7]) == 10.5  # over_limit_unit_price
        assert row[8] == "回灌契约套餐"  # description
        assert row[9] == "active"  # status
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
    assert notes[4] == "可选：减免金额（元），负值为加价", notes
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
async def test_import_invoices_negative_discount_allowed(
    test_client, auth_token, db_session, import_customer
):
    """结算单导入：减免金额允许为负值（加价）

    业务语义与 apply_discount / 前端 SubmitModal 一致：正数从总额扣除、负数加价，
    final_amount = total_amount - discount_amount。导入路径此前单独拒绝负值，
    导致「负减免=加价」的合法数据被预检查拦下（用户报障：导入提示「减免金额不能为负」）。
    """
    headers = [
        "company_id",
        "period_start",
        "period_end",
        "total_amount",
        "discount_amount",
        "invoice_no",
    ]
    notes = ["必填"] * 6
    suffix = uuid.uuid4().hex[:6].upper()
    invoice_no = f"NEG-DISC-{suffix}"
    # 负减免（加价 500）：final_amount 应为 10500
    rows = [[import_customer["company_id"], "2026-04-01", "2026-04-30", 10000, -500, invoice_no]]

    _request, response = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows, notes)),
    )

    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1, data
    assert data["errors"] == [], data

    row = db_session.execute(
        text("SELECT total_amount, discount_amount FROM invoices WHERE invoice_no = :no"),
        {"no": invoice_no},
    ).first()
    assert row is not None
    assert float(row[0]) == 10000
    assert float(row[1]) == -500


@pytest.mark.asyncio
async def test_import_invoices_dry_run_preview(
    test_client, auth_token, db_session, import_customer
):
    """结算单导入预检查（dry_run=true）：完整行级校验但不落库

    与计费规则/套餐/余额/客户导入预检查同模式：返回可入库条数与错误明细（含行号），
    不创建结算单、不写审计、不动缓存；确认后才真正导入。
    """
    suffix = uuid.uuid4().hex[:6].upper()
    invoice_no = f"DRY-INV-{suffix}"
    headers = ["invoice_no", "company_id", "period_start", "period_end", "total_amount"]
    notes = ["必填"] * 5
    rows = [
        [invoice_no, import_customer["company_id"], "2026-05-01", "2026-05-31", 15800.5],
        ["", 999999999, "2026-05-01", "2026-05-31", 100.0],
    ]
    try:
        # 预检查：合法行 1、错误行 1（未知客户），且不落库
        _request, response = await test_client.post(
            "/api/v1/billing/invoices/import?dry_run=true",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows, notes)),
        )
        assert response.status == 200
        assert response.json["code"] == 0
        data = response.json["data"]
        assert data["dry_run"] is True
        assert data["success_count"] == 1, data
        assert data["error_count"] == 1, data
        # 带模板说明行（第 2 行）时非法行为 Excel 第 4 行：说明行被丢弃且行号仍
        # 指向真实 Excel 行
        assert data["errors"][0].startswith("第 4 行") and "不存在" in data["errors"][0]

        count = db_session.execute(
            text("SELECT COUNT(*) FROM invoices WHERE invoice_no = :no"),
            {"no": invoice_no},
        ).scalar()
        assert count == 0, f"预检查不应落库，实际 {count} 条"

        # 正式导入：同样文件真实落库 1 条
        _request, response = await test_client.post(
            "/api/v1/billing/invoices/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows, notes)),
        )
        assert response.status == 200
        assert response.json["data"]["success_count"] == 1

        row = db_session.execute(
            text("SELECT id, status FROM invoices WHERE invoice_no = :no"), {"no": invoice_no}
        ).first()
        assert row is not None and row[1] == "draft"
    finally:
        db_session.execute(text("DELETE FROM invoices WHERE invoice_no = :no"), {"no": invoice_no})
        db_session.commit()


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
                                  detail_file_status, created_at, updated_at)
            VALUES (:no, :cid, '2026-01-01', '2026-01-31', 100, 0, 'draft', FALSE,
                    'pending', NOW(), NOW())
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


@pytest.mark.asyncio
async def test_export_invoices_time_columns_use_cst_wallclock(
    test_client, auth_token, db_session, import_customer
):
    """结算单导出：时间列必须是 CST 墙钟，不得出现 ISO/UTC 形式

    回归：导出曾直接 ``isoformat()``——
    - ``period_start/end``（timestamptz，DB 存 UTC）输出
      ``2026-08-31T16:00:00+00:00``，用户看到的日期比 CST 少一天；
    - ``created_at``（timestamp without time zone，PG 会话时区写入的 CST 墙钟）
      输出 ``2026-10-22T17:13:20.535487``（ISO T 分隔 + 微秒），不可读。
    """
    # 通过导入端点造一条周期确定的结算单（period 按 CST 日期落库为 UTC 时刻）
    headers = [
        "company_id",
        "period_start",
        "period_end",
        "total_amount",
        "discount_amount",
        "invoice_no",
    ]
    rows = [[import_customer["company_id"], "2026-04-01", "2026-04-30", 100.0, 0, None]]
    _request, imported = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows, ["必填"] * 6)),
    )
    assert imported.status == 200
    assert imported.json["data"]["success_count"] == 1

    _request, response = await test_client.get(
        "/api/v1/billing/invoices/export",
        params={"customer_id": import_customer["id"]},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200

    ws = load_workbook(io.BytesIO(response.body)).active
    columns = [cell.value for cell in ws[1]]
    assert columns == [
        "结算单号",
        "company_id",
        "客户名称",
        "周期开始",
        "周期结束",
        "总金额",
        "减免金额",
        "最终金额",
        "状态",
        "创建时间",
    ]
    # 导入的结算单是唯一一条（customer 维度隔离），取第 2 行数据
    period_start = ws.cell(row=2, column=columns.index("周期开始") + 1).value
    period_end = ws.cell(row=2, column=columns.index("周期结束") + 1).value
    created_at = ws.cell(row=2, column=columns.index("创建时间") + 1).value

    # 周期即用户导入的 CST 日期本身，不带时间/时区后缀
    assert period_start == "2026-04-01"
    assert period_end == "2026-04-30"

    # 创建时间是 CST 墙钟的秒级字符串：可解析、无微秒、无 T 分隔
    assert isinstance(created_at, str)
    parsed = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
    assert parsed.microsecond == 0
    assert created_at == parsed.strftime("%Y-%m-%d %H:%M:%S")


@pytest.mark.asyncio
async def test_export_package_plans_time_columns_use_cst_wallclock(
    test_client, auth_token, db_session
):
    """包年套餐导出：created_at/updated_at 是 CST 墙钟的秒级字符串

    ``created_at`` 由 PG server_default=now() 在会话时区（Asia/Shanghai）写入，
    值本身即 CST 墙钟；若按 UTC 解释再转 CST 会整体 +8 小时。
    """
    suffix = uuid.uuid4().hex[:6].upper()
    ptype = f"EXP{suffix}"
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
    rows = [
        [f"导出测试套餐_{suffix}", ptype, 30000.0, "X", "single", "否", 5000, 6.0, "测试", "active"]
    ]

    try:
        _request, imported = await test_client.post(
            "/api/v1/billing/package-plans/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows, ["必填"] * 10)),
        )
        assert imported.status == 200
        assert imported.json["data"]["success_count"] == 1

        _request, response = await test_client.get(
            "/api/v1/billing/package-plans/export",
            params={"keyword": ptype},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status == 200

        ws = load_workbook(io.BytesIO(response.body)).active
        columns = [cell.value for cell in ws[1]]
        created_at = ws.cell(row=2, column=columns.index("created_at") + 1).value
        updated_at = ws.cell(row=2, column=columns.index("updated_at") + 1).value

        for value in (created_at, updated_at):
            assert isinstance(value, str)
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            assert parsed.microsecond == 0
    finally:
        db_session.execute(
            text("DELETE FROM package_plans WHERE package_type = :pt"), {"pt": ptype}
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_export_invoices_contains_company_id_column(
    test_client, auth_token, db_session, import_customer
):
    """结算单导出必须含 company_id 列（回灌主键列）

    回归防护 —— 导出曾只有中文列（结算单号/客户名称/…），用户拿导出文件回灌
    必然报「缺少必填列：company_id, period_start, period_end, total_amount」，
    文件其实没问题却让用户以为损坏。company_id 与 balances/pricing-rules
    导出的约定保持一致。
    """
    headers = [
        "company_id",
        "period_start",
        "period_end",
        "total_amount",
        "discount_amount",
        "invoice_no",
    ]
    rows = [[import_customer["company_id"], "2026-04-01", "2026-04-30", 100.0, 0, None]]
    _request, imported = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows, ["必填"] * 6)),
    )
    assert imported.json["data"]["success_count"] == 1

    _request, response = await test_client.get(
        "/api/v1/billing/invoices/export",
        params={"customer_id": import_customer["id"]},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200

    ws = load_workbook(io.BytesIO(response.body)).active
    columns = [cell.value for cell in ws[1]]
    assert "company_id" in columns, f"导出缺 company_id 列：{columns}"

    # company_id 值必须是该客户的编号（导入主键），且数据行可取到
    col_idx = columns.index("company_id") + 1
    assert ws.cell(row=2, column=col_idx).value == import_customer["company_id"]

    # 统计行列号须随新列右移：总金额/最终总额仍落在 总金额/最终金额 列下
    assert columns.index("总金额") + 1 == 6
    assert columns.index("最终金额") + 1 == 8


@pytest.mark.asyncio
async def test_import_invoices_accepts_export_file_columns(
    test_client, auth_token, db_session, import_customer
):
    """结算单导出文件（中文展示列）可直接回灌导入，不再报「缺少必填列」

    回归防护 —— 导出列是中文展示名（周期开始/周期结束/总金额/减免金额），
    导入期待英文存储列（period_start/period_end/total_amount/discount_amount）。
    修复后列名自动归一，按同一校验路径处理（状态固定 draft、单号缺省自动生成）。
    """
    # 模拟 /billing/invoices/export 的导出文件结构（中文列名 + 统计行）
    headers = [
        "结算单号",
        "company_id",
        "客户名称",
        "周期开始",
        "周期结束",
        "总金额",
        "减免金额",
        "最终金额",
        "状态",
        "创建时间",
    ]
    rows = [
        [
            None,
            import_customer["company_id"],
            "测试客户",
            "2026-04-01",
            "2026-04-30",
            12500.50,
            0,
            12500.50,
            "草稿",
            "2026-10-25 09:00:00",
        ],
        [
            None,
            999999999,
            "不存在的客户",
            "2026-05-01",
            "2026-05-31",
            100.0,
            0,
            100.0,
            "草稿",
            "2026-10-25 09:00:00",
        ],
    ]

    _request, response = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    # 列级错误消失：不再报「缺少必填列」，进入行级校验
    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["success_count"] == 1, data
    assert data["error_count"] == 1, data
    assert any("客户编号 999999999 不存在" in e for e in data["errors"]), data["errors"]

    # 落库的结算单：状态 draft、账期/金额与导出文件一致
    row = db_session.execute(
        text(
            "SELECT status, period_start, total_amount FROM invoices "
            "WHERE customer_id = :cid ORDER BY id"
        ),
        {"cid": import_customer["id"]},
    ).first()
    assert row is not None
    assert row[0] == "draft"
    assert row[2] == 12500.50


@pytest.mark.asyncio
async def test_import_invoices_accepts_legacy_export_file_without_company_id(
    test_client, auth_token, db_session, import_customer
):
    """旧版导出文件（无 company_id 列 + 统计行）仍可回灌

    回归防护 —— 2026-10-25 前的导出文件只有中文列且缺导入主键列 company_id，
    用户手里已有的文件不能因为升级就被判「缺少必填列」而作废。回灌路径：
    按「客户名称」解析客户 → 丢弃导出追加的统计行 → 行级校验落库。
    """
    # 模拟旧版导出结构（9 中文列，无 company_id，末行统计）
    headers = [
        "结算单号",
        "客户名称",
        "周期开始",
        "周期结束",
        "总金额",
        "减免金额",
        "最终金额",
        "状态",
        "创建时间",
    ]
    rows = [
        [
            None,
            f"导入测试客户_{import_customer['company_id']}",
            "2026-04-01",
            "2026-04-30",
            12500.50,
            0,
            12500.50,
            "草稿",
            "2026-10-25 09:00:00",
        ],
        # 统计行：结算单号列填统计文案、其余 NaN/统计金额
        [
            "共 1 条记录",
            None,
            None,
            None,
            "总金额：12500.50",
            None,
            "最终总额：12500.50",
            None,
            None,
        ],
    ]

    _request, response = await test_client.post(
        "/api/v1/billing/invoices/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(_xlsx(headers, rows)),
    )

    # 列级错误消失（company_id 缺列不再拦截），统计行不计入错误
    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["success_count"] == 1, data
    assert data["error_count"] == 0, data["errors"]

    count = db_session.execute(
        text("SELECT COUNT(*) FROM invoices WHERE customer_id = :cid"),
        {"cid": import_customer["id"]},
    ).scalar()
    assert count == 1, count


@pytest.mark.asyncio
async def test_import_invoices_ambiguous_customer_name_rejected(
    test_client, auth_token, db_session, import_customer
):
    """旧版导出文件按客户名称解析：重名客户报行级错误，不静默挂错人

    回归防护 —— 名称解析若对重名静默取任意一条，会把结算单挂到错误客户名下
    （扣款/归属全错）。必须报「对应多个客户，请改用 company_id」并整行剔除。
    """
    dup_name = f"重名客户_{uuid.uuid4().hex[:6]}"
    # 造两个同名客户（import_customer 之外）
    for _ in range(2):
        db_session.execute(
            text(
                "INSERT INTO customers (company_id, name, account_type, settlement_cycle, "
                "settlement_type, created_at, updated_at) "
                "VALUES (:cid, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())"
            ),
            {"cid": 960000 + abs(hash(uuid.uuid4().hex[:8])) % 30000, "name": dup_name},
        )
    db_session.commit()

    headers = ["结算单号", "客户名称", "周期开始", "周期结束", "总金额", "减免金额"]
    rows = [[None, dup_name, "2026-04-01", "2026-04-30", 100.0, 0]]

    try:
        _request, response = await test_client.post(
            "/api/v1/billing/invoices/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(headers, rows)),
        )
        assert response.status == 200, response.json
        data = response.json["data"]
        assert data["success_count"] == 0, data
        assert data["error_count"] == 1, data
        assert "对应多个客户" in data["errors"][0], data["errors"]
    finally:
        db_session.execute(text("DELETE FROM customers WHERE name = :n"), {"n": dup_name})
        db_session.commit()
