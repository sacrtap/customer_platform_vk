"""用户批量导入/导出端点单元测试（英文表头 + dry_run 预检查模式）

覆盖 import_users / download_user_import_template / export_users 三个端点的
真实行为：dry_run 不落库、行级错误不阻塞、同批次/含软删查重、角色解析、
模板 3 行结构、导出列与内容。
"""

import io
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import openpyxl
import pytest

from app.routes.users import download_user_import_template, export_users, import_users

HEADERS = ["username", "email", "real_name", "role", "initial_password"]


def build_xlsx(rows: list[list], headers: list | None = None, with_note_row: bool = False):
    """构造上传用 xlsx 字节。

    with_note_row=True 时插入模板第 2 行中文说明行（模拟从模板填写后上传）。
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None  # 新建 Workbook 必有活动工作表
    ws.append(headers or HEADERS)
    if with_note_row:
        ws.append(
            [
                "必填：用户名（唯一）",
                "可选：邮箱",
                "可选：真实姓名",
                "可选：角色名",
                "必填：初始密码（>=6 位）",
            ]
        )
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def parse_response(response):
    """解析 Sanic 响应体"""
    return json.loads(response.body)


@pytest.fixture
def mock_request():
    request = MagicMock()
    request.ctx = MagicMock()
    request.ctx.user = {"user_id": 1}
    request.ip = "127.0.0.1"
    request.headers = {}
    return request


@pytest.fixture(autouse=True)
def mock_permission_cache():
    """mock 权限缓存：端点带 @require_permission，真实装饰器会查 Redis/DB"""
    with patch("app.cache.permissions.permission_cache") as cache:
        cache.get_permissions = AsyncMock(
            return_value={"users:import", "users:export", "users:create"}
        )
        cache.set_permissions = AsyncMock(return_value=True)
        yield cache


def make_session(execute_side_effect=None):
    """构造 mock 的 AsyncSession（含 begin() 异步上下文）"""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_side_effect or [])
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=cm)
    return session, cm


def query_result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


def set_file(request, body, name="users.xlsx"):
    mock_file = MagicMock()
    mock_file.name = name
    mock_file.body = body
    mock_file.type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    request.files = {"file": [mock_file]}


class TestImportUsersDryRun:
    """dry_run 预检查：完整行级校验但不落库"""

    @pytest.mark.asyncio
    async def test_valid_row_passes_without_persisting(self, mock_request):
        """合法行预检查通过；dry_run 不进入事务、不创建用户"""
        body = build_xlsx(
            [["zhangsan", "z@a.com", "张三", "运营经理", "Abc12345"]], with_note_row=True
        )
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        session, begin_cm = make_session([query_result([]), query_result([(7, "运营经理")])])
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["code"] == 0
        assert data["data"]["dry_run"] is True
        assert data["data"]["success_count"] == 1
        assert data["data"]["error_count"] == 0
        assert data["data"]["errors"] == []
        # 预检查零副作用：不开事务、不落库
        begin_cm.__aenter__.assert_not_called()

    @pytest.mark.asyncio
    async def test_template_note_row_stripped_and_row_number_aligned(self, mock_request):
        """模板说明行被剥离；行号对齐真实 Excel 行（表头 1 + 说明 2 → 数据从第 3 行起）"""
        body = build_xlsx([["zhangsan", "", "", "", "Abc12345"]], with_note_row=True)
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        session, _ = make_session([query_result([("zhangsan",)]), query_result([])])
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["data"]["error_count"] == 1
        assert data["data"]["errors"] == ["第 3 行：用户名 'zhangsan' 已存在"]

    @pytest.mark.asyncio
    async def test_row_errors_do_not_block_valid_rows(self, mock_request):
        """行级错误不阻塞其他行：1 合法 + 1 非法 → success 1 / error 1"""
        body = build_xlsx(
            [
                ["zhangsan", "", "", "", "Abc12345"],
                ["", "", "", "", "Abc12345"],  # 用户名为空
            ]
        )
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        session, _ = make_session([query_result([]), query_result([])])
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["data"]["success_count"] == 1
        assert data["data"]["error_count"] == 1
        assert data["data"]["errors"] == ["第 3 行：用户名不能为空"]

    @pytest.mark.asyncio
    async def test_duplicate_username_in_same_batch_rejected(self, mock_request):
        """同批次重复用户名：第二行行级报错（落库时 create_user 同样查重，需提前拦截）"""
        body = build_xlsx(
            [
                ["zhangsan", "", "", "", "Abc12345"],
                ["zhangsan", "", "", "", "Abc12345"],
            ]
        )
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        session, _ = make_session([query_result([]), query_result([])])
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["data"]["success_count"] == 1
        assert data["data"]["error_count"] == 1
        assert data["data"]["errors"] == ["第 3 行：用户名 'zhangsan' 已存在"]

    @pytest.mark.asyncio
    async def test_short_password_rejected(self, mock_request):
        body = build_xlsx([["zhangsan", "", "", "", "Ab1"]])
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        session, _ = make_session([query_result([]), query_result([])])
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["data"]["error_count"] == 1
        assert data["data"]["errors"] == ["第 2 行：密码长度不能少于 6 位"]

    @pytest.mark.asyncio
    async def test_invalid_email_rejected(self, mock_request):
        body = build_xlsx([["zhangsan", "not-an-email", "", "", "Abc12345"]])
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        session, _ = make_session([query_result([]), query_result([])])
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["data"]["errors"] == ["第 2 行：邮箱格式不正确"]

    @pytest.mark.asyncio
    async def test_unknown_role_rejected(self, mock_request):
        """角色按 name 解析，不存在 → 行级错误"""
        body = build_xlsx([["zhangsan", "", "", "不存在的角色", "Abc12345"]])
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        session, _ = make_session([query_result([]), query_result([])])
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["data"]["errors"] == ["第 2 行：角色 '不存在的角色' 不存在"]

    @pytest.mark.asyncio
    async def test_multi_role_comma_separated(self, mock_request):
        """role 列逗号分隔多角色，全部解析成功才入库"""
        body = build_xlsx([["zhangsan", "", "", "运营经理,销售经理", "Abc12345"]])
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        session, _ = make_session(
            [query_result([]), query_result([(7, "运营经理"), (8, "销售经理")])]
        )
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["data"]["success_count"] == 1
        assert data["data"]["error_count"] == 0


class TestImportUsersPersist:
    """正式导入：落库 + 审计"""

    @pytest.mark.asyncio
    async def test_import_creates_users_and_assigns_roles(self, mock_request):
        body = build_xlsx([["zhangsan", "z@a.com", "张三", "运营经理", "Abc12345"]])
        set_file(mock_request, body)
        mock_request.args = {}
        session, begin_cm = make_session([query_result([]), query_result([(7, "运营经理")])])
        mock_request.ctx.db_session = session

        with (
            patch("app.routes.users.UserService") as service_cls,
            patch("app.routes.users.create_audit_entry", new=AsyncMock()) as audit_mock,
        ):
            service = service_cls.return_value
            service.create_user = AsyncMock(return_value=MagicMock(id=99))
            service.assign_roles = AsyncMock()

            response = await import_users(mock_request)
            data = parse_response(response)

            assert data["code"] == 0
            assert data["data"]["success_count"] == 1
            assert data["data"]["error_count"] == 0
            # 正式导入不开 dry_run 字段，errors 截断到 10 条以内
            assert "dry_run" not in data["data"]
            begin_cm.__aenter__.assert_awaited_once()
            service.create_user.assert_awaited_once_with(
                username="zhangsan", password="Abc12345", email="z@a.com", real_name="张三"
            )
            service.assign_roles.assert_awaited_once_with(99, [7])
            audit_mock.assert_awaited_once()


class TestImportUsersValidation:
    """文件与列级校验"""

    @pytest.mark.asyncio
    async def test_missing_required_columns(self, mock_request):
        body = build_xlsx([["zhangsan", "Abc12345"]], headers=["username", "password"])
        set_file(mock_request, body)
        mock_request.args = {"dry_run": "true"}
        mock_request.ctx.db_session = AsyncMock()

        response = await import_users(mock_request)
        data = parse_response(response)

        assert response.status == 400
        assert data["code"] == 40003
        assert data["message"] == "Excel 缺少必填列：initial_password"

    @pytest.mark.asyncio
    async def test_rejects_non_xlsx(self, mock_request):
        set_file(mock_request, b"not-a-real-xlsx", name="users.xls")
        mock_request.args = {}
        mock_request.ctx.db_session = AsyncMock()

        response = await import_users(mock_request)
        data = parse_response(response)

        assert response.status == 400
        assert data["code"] == 40002

    @pytest.mark.asyncio
    async def test_missing_file(self, mock_request):
        mock_request.files = {}
        mock_request.args = {}
        mock_request.ctx.db_session = AsyncMock()

        response = await import_users(mock_request)
        data = parse_response(response)

        assert response.status == 400
        assert data["code"] == 40001


class TestUserImportTemplate:
    """模板端点：2 行结构（英文列名 / 中文说明必填-可选前缀），无示例数据行"""

    @pytest.mark.asyncio
    async def test_template_structure(self, mock_request):
        response = await download_user_import_template(mock_request)
        assert response.status == 200
        assert response.content_type == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        ws = openpyxl.load_workbook(io.BytesIO(response.body)).active
        assert ws is not None
        assert [c.value for c in ws[1]] == HEADERS
        # 说明行必须以「必填：」/「可选：」开头（read_import_dataframe 的剥离依据）
        assert str(ws.cell(row=2, column=1).value).startswith("必填：")
        assert str(ws.cell(row=2, column=2).value).startswith("可选：")
        # 无示例数据行：第 3 行会被 read_import_dataframe 当真实数据导入
        assert ws.max_row == 2

    @pytest.mark.asyncio
    async def test_template_round_trip_through_import(self, mock_request):
        """下载模板 → 第 3 行起填写真实数据 → dry_run 上传：说明行不产生虚假错误"""
        template = await download_user_import_template(mock_request)
        wb = openpyxl.load_workbook(io.BytesIO(template.body))
        ws = wb.active
        assert ws is not None
        ws.append(["lisi", "lisi@a.com", "李四", "", "Abc12345"])
        buffer = io.BytesIO()
        wb.save(buffer)

        set_file(mock_request, buffer.getvalue())
        mock_request.args = {"dry_run": "true"}
        session, _ = make_session([query_result([]), query_result([])])
        mock_request.ctx.db_session = session

        response = await import_users(mock_request)
        data = parse_response(response)

        assert data["data"]["success_count"] == 1
        assert data["data"]["error_count"] == 0


class TestExportUsers:
    """导出端点"""

    @pytest.mark.asyncio
    async def test_export_columns_and_values(self, mock_request):
        mock_request.args = {}
        session, _ = make_session()
        mock_request.ctx.db_session = session

        role = MagicMock()
        role.name = "运营经理"
        user = MagicMock()
        user.id = 1
        user.username = "zhangsan"
        user.email = "z@a.com"
        user.real_name = "张三"
        user.is_active = True
        user.roles = [role]
        user.phone = "22644212509"
        user.created_at = datetime(2026, 10, 31, 12, 0, 0)

        with patch("app.routes.users.UserService") as service_cls:
            service_cls.return_value.get_all_users = AsyncMock(return_value=([user], 1))
            response = await export_users(mock_request)

        assert response.status == 200
        assert response.headers["X-Truncated"] == "false"
        ws = openpyxl.load_workbook(io.BytesIO(response.body)).active
        headers = [c.value for c in ws[1]]
        assert headers == [
            "id",
            "username",
            "email",
            "real_name",
            "is_active",
            "roles",
            "phone",
            "created_at",
        ]
        row2 = [c.value for c in ws[2]]
        assert row2[1] == "zhangsan"
        assert row2[4] == "是"
        assert row2[5] == "运营经理"

    @pytest.mark.asyncio
    async def test_export_empty_returns_40002(self, mock_request):
        mock_request.args = {}
        session, _ = make_session()
        mock_request.ctx.db_session = session

        with patch("app.routes.users.UserService") as service_cls:
            service_cls.return_value.get_all_users = AsyncMock(return_value=([], 0))
            response = await export_users(mock_request)

        data = parse_response(response)
        assert response.status == 400
        assert data["code"] == 40002
