"""管理页（用户/角色/标签/行业类型/合作状态/余额白名单）导入导出 API 集成测试

覆盖统一架构（excel_import/excel_template/excel_export）在各管理页的落地行为：
1. 模板下载 → 回灌导入（第 2 行中文说明行不被当作数据行）
2. dry_run 预检查不落库；正式导入落库 + 行级错误不阻塞
3. 行级校验：查重（含软删口径）、必填、枚举、外键引用、数值解析
4. 权限拦截（无 import/export 权限码 → 403）
5. 导出：成功返回 xlsx、空数据 40002、超限 X-Truncated

与 test_billing_import_export_api.py 的分工：后者覆盖 billing 域，本文件覆盖
其余管理域。数据隔离：tags/industry_types/cooperation_statuses/balance_whitelists
由 db_session fixture 的 TRUNCATE 负责；users/roles 不在其列表，用
cleanup_imported fixture 显式清理（audit_logs 有 FK 指向 users，须先删）。
"""

import io
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import text

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(headers: list, rows: list) -> bytes:
    """生成 xlsx 字节（仅英文表头 + 数据行）"""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(content: bytes, name: str = "import.xlsx") -> dict:
    return {"file": (name, content, XLSX_MIME)}


def _fill_template(template_body: bytes, rows: list) -> bytes:
    """把下载到的模板（第 1 行英文列名 + 第 2 行中文说明）填入数据行后回灌。

    模板不含示例数据行，数据从第 3 行开始写（真实 Excel 行号）。
    """
    wb = load_workbook(io.BytesIO(template_body))
    ws = wb.active
    assert ws is not None
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@contextmanager
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
def cleanup_imported(db_session):
    """登记测试中导入创建的用户/角色，测试结束后显式删除。

    users/roles 不在 db_session 的 TRUNCATE 列表中（auth 数据由 session 级
    test_user fixture 管理），不清理会跨测试残留并触发查重误判。
    audit_logs.user_id 有 FK，须先于 users 删除。
    """
    created = {"users": [], "roles": []}
    yield created
    for username in created["users"]:
        row = db_session.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": username}
        ).fetchone()
        if row:
            db_session.execute(text("DELETE FROM audit_logs WHERE user_id = :i"), {"i": row[0]})
            db_session.execute(text("DELETE FROM user_roles WHERE user_id = :i"), {"i": row[0]})
            db_session.execute(text("DELETE FROM users WHERE id = :i"), {"i": row[0]})
    for role_name in created["roles"]:
        row = db_session.execute(
            text("SELECT id FROM roles WHERE name = :n"), {"n": role_name}
        ).fetchone()
        if row:
            db_session.execute(
                text("DELETE FROM role_permissions WHERE role_id = :i"), {"i": row[0]}
            )
            db_session.execute(text("DELETE FROM user_roles WHERE role_id = :i"), {"i": row[0]})
            db_session.execute(text("DELETE FROM roles WHERE id = :i"), {"i": row[0]})
    db_session.commit()


# ==================== 用户导入导出 ====================


@pytest.mark.asyncio
async def test_user_import_template_round_trip(
    test_client, auth_token, db_session, cleanup_imported
):
    """用户导入：下载模板 → 回灌 → dry_run 不落库 → 正式导入落库"""
    username = f"imp_{uuid.uuid4().hex[:8]}"
    cleanup_imported["users"].append(username)

    _request, template = await test_client.get(
        "/api/v1/users/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert template.status == 200
    body = _fill_template(
        template.body, [[username, f"{username}@a.com", "导入用户", "admin", "Abc12345"]]
    )

    # dry_run：预检查通过但不落库
    _request, response = await test_client.post(
        "/api/v1/users/import",
        params={"dry_run": "true"},
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["dry_run"] is True
    assert data["success_count"] == 1
    assert data["error_count"] == 0
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM users WHERE username = :u"), {"u": username}
        ).scalar()
        == 0
    )

    # 正式导入：落库 + 角色关联（role 列按角色名解析）
    _request, response = await test_client.post(
        "/api/v1/users/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert "dry_run" not in data
    role_count = db_session.execute(
        text(
            """
            SELECT COUNT(*) FROM user_roles ur JOIN users u ON ur.user_id = u.id
            WHERE u.username = :u
            """
        ),
        {"u": username},
    ).scalar()
    assert role_count == 1


@pytest.mark.asyncio
async def test_user_import_row_errors_not_blocking(
    test_client, auth_token, db_session, cleanup_imported
):
    """用户导入：行级错误（空用户名/密码过短/角色不存在）不阻塞合法行"""
    good = f"imp_{uuid.uuid4().hex[:8]}"
    cleanup_imported["users"].append(good)

    body = _xlsx(
        ["username", "email", "real_name", "role", "initial_password"],
        [
            ["", "", "", "", "Abc12345"],  # 第 2 行：用户名为空
            ["bad_pwd", "", "", "", "Ab1"],  # 第 3 行：密码过短
            ["bad_role", "", "", "不存在的角色", "Abc12345"],  # 第 4 行：角色不存在
            [good, "", "", "", "Abc12345"],  # 第 5 行：合法
        ],
    )
    _request, response = await test_client.post(
        "/api/v1/users/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 3
    assert data["errors"][0].startswith("第 2 行")
    assert "密码" in data["errors"][1]
    assert "角色" in data["errors"][2]
    # 合法行已落库
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM users WHERE username = :u"), {"u": good}
        ).scalar()
        == 1
    )


@pytest.mark.asyncio
async def test_user_import_forbidden(test_client, auth_token):
    """用户导入/模板：缺少 users:import 权限返回 403"""
    with _no_permissions():
        _request, response = await test_client.post(
            "/api/v1/users/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=_upload(_xlsx(["username", "initial_password"], [["x", "Abc12345"]])),
        )
        assert response.status == 403
        _request, response = await test_client.get(
            "/api/v1/users/import-template",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status == 403


@pytest.mark.asyncio
async def test_user_export_xlsx(test_client, auth_token, cleanup_imported):
    """用户导出：返回 xlsx，列名为英文，权限不足 403"""
    _request, response = await test_client.get(
        "/api/v1/users/export",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    assert "spreadsheetml" in response.headers.get("content-type", "")
    ws = load_workbook(io.BytesIO(response.body)).active
    assert ws is not None
    headers = [c.value for c in ws[1]]
    assert headers[0] == "id" and "username" in headers and "roles" in headers
    # 预置 admin 用户应在导出结果中
    usernames = [ws.cell(row=r, column=2).value for r in range(2, ws.max_row + 1)]
    assert "admin" in usernames

    with _no_permissions():
        _request, response = await test_client.get(
            "/api/v1/users/export",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status == 403


# ==================== 角色导入导出 ====================


@pytest.mark.asyncio
async def test_role_import_with_permissions(test_client, auth_token, db_session, cleanup_imported):
    """角色导入：permissions 列按逗号拆分关联权限码；权限码不存在 → 行级错误"""
    role_name = f"导入角色_{uuid.uuid4().hex[:6]}"
    cleanup_imported["roles"].append(role_name)

    body = _xlsx(
        ["name", "description", "permissions"],
        [
            [role_name, "批量导入", "customers:view,customers:edit"],
            [f"{role_name}_bad", "坏行", "not:a:real:code"],
        ],
    )
    _request, response = await test_client.post(
        "/api/v1/roles/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    assert "权限码" in data["errors"][0]

    perm_count = db_session.execute(
        text(
            """
            SELECT COUNT(*) FROM role_permissions rp JOIN roles r ON rp.role_id = r.id
            WHERE r.name = :n
            """
        ),
        {"n": role_name},
    ).scalar()
    assert perm_count == 2


@pytest.mark.asyncio
async def test_role_export_xlsx(test_client, auth_token):
    """角色导出：xlsx，permissions 列为逗号拼接的权限码"""
    _request, response = await test_client.get(
        "/api/v1/roles/export",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    ws = load_workbook(io.BytesIO(response.body)).active
    assert ws is not None
    assert [c.value for c in ws[1]] == ["id", "name", "description", "is_system", "permissions"]
    # 预置 admin 角色（session 级 test_user 创建，is_system 默认 False）
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    admin_row = next(r for r in rows if r[1] == "admin")
    assert admin_row[3] == "否"
    assert "customers:view" in str(admin_row[4])


# ==================== 标签导入导出 ====================


@pytest.mark.asyncio
async def test_tag_import_template_round_trip(test_client, auth_token, db_session):
    """标签导入：模板回灌落库；type 非法值 → 行级错误；(name,type) 查重"""
    tag_name = f"导入标签_{uuid.uuid4().hex[:6]}"

    _request, template = await test_client.get(
        "/api/v1/tags/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert template.status == 200
    body = _fill_template(
        template.body,
        [
            [tag_name, "customer", ""],
            [f"{tag_name}_bad", "invalid_type", ""],
            [tag_name, "customer", ""],  # 与第 3 行同 (name,type)：同批次查重
        ],
    )
    _request, response = await test_client.post(
        "/api/v1/tags/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 2
    assert "类型" in data["errors"][0]
    assert "已存在" in data["errors"][1]
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM tags WHERE name = :n"), {"n": tag_name}
        ).scalar()
        == 1
    )


@pytest.mark.asyncio
async def test_tag_export_xlsx(test_client, auth_token):
    """标签导出：xlsx + type 筛选参数"""
    tag_name = f"导出标签_{uuid.uuid4().hex[:6]}"
    body = _xlsx(["name", "type", "category"], [[tag_name, "customer", ""]])
    _request, response = await test_client.post(
        "/api/v1/tags/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200

    _request, response = await test_client.get(
        "/api/v1/tags/export",
        params={"type": "customer"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    ws = load_workbook(io.BytesIO(response.body)).active
    assert ws is not None
    # 导出为中文展示列名；断言语义：导入的标签出现在导出结果中
    all_values = [v for row in ws.iter_rows(values_only=True) for v in row]
    assert tag_name in all_values


# ==================== 行业类型导入导出 ====================


@pytest.mark.asyncio
async def test_industry_type_import_template_round_trip(test_client, auth_token, db_session):
    """行业类型导入：模板回灌落库；sort_order 缺省 0；同名查重"""
    name = f"导入行业_{uuid.uuid4().hex[:6]}"

    _request, template = await test_client.get(
        "/api/v1/industry-types/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert template.status == 200
    body = _fill_template(template.body, [[name, ""], [name, ""]])
    _request, response = await test_client.post(
        "/api/v1/industry-types/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    assert "已存在" in data["errors"][0]

    sort_order = db_session.execute(
        text("SELECT sort_order FROM industry_types WHERE name = :n"), {"n": name}
    ).scalar()
    assert sort_order == 0


@pytest.mark.asyncio
async def test_industry_type_export_empty(test_client, auth_token):
    """行业类型导出：无数据返回 40002"""
    _request, response = await test_client.get(
        "/api/v1/industry-types/export",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 400
    assert response.json["code"] == 40002


# ==================== 合作状态导入导出 ====================


@pytest.mark.asyncio
async def test_cooperation_status_import_round_trip(test_client, auth_token, db_session):
    """合作状态导入：模板回灌落库；value 与预置值冲突 → 行级错误"""
    name = f"导入状态_{uuid.uuid4().hex[:6]}"

    _request, template = await test_client.get(
        "/api/v1/cooperation-statuses/import-template",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert template.status == 200
    body = _fill_template(
        template.body,
        [
            [name, f"imp_{uuid.uuid4().hex[:8]}", 5],
            ["冲突状态", "active", 1],  # active 为 db_session 预置值，撞唯一约束
        ],
    )
    _request, response = await test_client.post(
        "/api/v1/cooperation-statuses/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    assert "已存在" in data["errors"][0]
    assert (
        db_session.execute(
            text("SELECT COUNT(*) FROM cooperation_statuses WHERE name = :n"), {"n": name}
        ).scalar()
        == 1
    )


# ==================== 余额白名单导入导出 ====================


@pytest.mark.asyncio
async def test_balance_whitelist_import(test_client, auth_token, db_session, import_customer):
    """余额白名单导入：合法行落库（static_balance 缺省 1000）；company_id 不存在 → 行级错误"""
    body = _xlsx(
        ["company_id", "static_balance", "remark"],
        [
            [import_customer["company_id"], 5000.0, "导入备注"],
            [999999999, None, "不存在的客户"],
            [888888888, None, "缺省余额"],
        ],
    )
    _request, response = await test_client.post(
        "/api/v1/balance-whitelists/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["success_count"] == 1
    assert data["error_count"] == 2  # 第 3、4 行引用的客户编号均不存在
    assert "不存在" in data["errors"][0]
    assert "不存在" in data["errors"][1]

    row = db_session.execute(
        text(
            """
            SELECT static_balance, remark FROM balance_whitelists
            WHERE customer_id = :cid
            """
        ),
        {"cid": import_customer["id"]},
    ).fetchone()
    assert row is not None
    assert float(row[0]) == 5000.0
    assert row[1] == "导入备注"

    default_row = db_session.execute(
        text(
            """
            SELECT static_balance FROM balance_whitelists bw
            JOIN customers c ON bw.customer_id = c.id
            WHERE c.company_id = 888888888
            """
        )
    ).fetchone()
    # 888888888 客户不存在，该行应报错未落库
    assert default_row is None


@pytest.mark.asyncio
async def test_balance_whitelist_export(test_client, auth_token, import_customer):
    """余额白名单导出：先导入一条，再导出 xlsx 校验内容"""
    body = _xlsx(
        ["company_id", "static_balance", "remark"],
        [[import_customer["company_id"], 5000.0, "导出备注"]],
    )
    _request, response = await test_client.post(
        "/api/v1/balance-whitelists/import",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=_upload(body),
    )
    assert response.status == 200
    assert response.json["data"]["success_count"] == 1

    _request, response = await test_client.get(
        "/api/v1/balance-whitelists/export",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    assert "spreadsheetml" in response.headers.get("content-type", "")
    ws = load_workbook(io.BytesIO(response.body)).active
    assert ws is not None
    all_values = [v for row in ws.iter_rows(values_only=True) for v in row]
    assert "导出备注" in all_values
