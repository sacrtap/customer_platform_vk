"""InvoiceExcelService 单元测试 - Excel 生成逻辑

测试要点：
1. "合计" Sheet 不再包含"单价"列（10 列 A-J）
2. "计费明细" Sheet 正确生成，包含 additional_floor_price 和 multi_floor_pricing_type
3. subtotal 计算正确
"""

import os
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from openpyxl import load_workbook

from app.services.invoice_excel import InvoiceExcelService


@pytest.fixture
def excel_service():
    """创建 InvoiceExcelService 实例（db 和 external_engine 可为 None）"""
    return InvoiceExcelService(db=MagicMock(), external_engine=None)


@pytest.fixture
def cleanup_test_file():
    """清理测试生成的文件"""
    created_files = []
    yield created_files
    for f in created_files:
        if os.path.exists(f):
            os.remove(f)


class TestInvoiceExcel_SheetStructure:
    """Excel Sheet 结构测试"""

    def test_summary_sheet_has_no_unit_price_column(self, excel_service, cleanup_test_file):
        """合计 Sheet 不包含"单价"列"""
        file_path = excel_service._build_and_save_excel(
            invoice_id=99901,
            customer_name="测试客户",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            total_amount=Decimal("1000.00"),
            discount_amount=Decimal("100.00"),
            unit_price=None,
            order_details=[],
            balance_info=None,
            invoice_items=[],
        )

        abs_path = os.path.join(
            getattr(excel_service, "_settings_path", "./uploads"),
            file_path,
        )
        cleanup_test_file.append(abs_path)

        wb = load_workbook(abs_path)
        ws = wb["合计"]

        # 读取表头行（第 2 行）
        headers = [ws.cell(row=2, column=c).value for c in range(1, 11)]

        # 确认不包含"单价"
        assert "单价" not in headers
        # 确认 10 列
        assert len(headers) == 10
        # 确认关键列存在
        assert "结算周期" in headers
        assert "总金额（元）" in headers
        assert "减免金额（元）" in headers
        assert "实际结算金额（元）" in headers

    def test_billing_detail_sheet_exists_with_invoice_items(self, excel_service, cleanup_test_file):
        """提供 invoice_items 时生成"计费明细" Sheet"""
        invoice_items = [
            {
                "device_type": "L",
                "layer_type": "multi",
                "quantity": 3,
                "unit_price": Decimal("5.00"),
                "additional_floor_price": Decimal("6.00"),
                "multi_floor_pricing_type": "incremental",
                "subtotal": Decimal("17.00"),
            },
        ]

        file_path = excel_service._build_and_save_excel(
            invoice_id=99902,
            customer_name="测试客户",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            total_amount=Decimal("17.00"),
            discount_amount=Decimal("0.00"),
            unit_price=None,
            order_details=[],
            balance_info=None,
            invoice_items=invoice_items,
        )

        abs_path = os.path.join("./uploads", file_path)
        cleanup_test_file.append(abs_path)

        wb = load_workbook(abs_path)
        assert "计费明细" in wb.sheetnames

        ws = wb["计费明细"]
        # 表头
        headers = [ws.cell(row=1, column=c).value for c in range(1, 8)]
        assert headers == [
            "设备类型",
            "楼层",
            "数量",
            "单价（元）",
            "小计（元）",
            "多层计费类型",
            "其他层单价（元）",
        ]

        # 数据行
        assert ws.cell(row=2, column=1).value == "L"
        assert ws.cell(row=2, column=2).value == "多层"
        assert ws.cell(row=2, column=3).value == 3.0
        assert ws.cell(row=2, column=4).value == 5.0
        assert ws.cell(row=2, column=5).value == 15.0  # 3 * 5 = 15
        assert ws.cell(row=2, column=6).value == "递增"
        assert ws.cell(row=2, column=7).value == 6.0

    def test_billing_detail_sheet_not_created_without_items(self, excel_service, cleanup_test_file):
        """invoice_items 为空时不生成"计费明细" Sheet"""
        file_path = excel_service._build_and_save_excel(
            invoice_id=99903,
            customer_name="测试客户",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            total_amount=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            unit_price=None,
            order_details=[],
            balance_info=None,
            invoice_items=[],
        )

        abs_path = os.path.join("./uploads", file_path)
        cleanup_test_file.append(abs_path)

        wb = load_workbook(abs_path)
        assert "计费明细" not in wb.sheetnames

    def test_billing_detail_sheet_unified_pricing(self, excel_service, cleanup_test_file):
        """计费明细 Sheet - 统一模式"""
        invoice_items = [
            {
                "device_type": "L",
                "layer_type": "multi",
                "quantity": 2,
                "unit_price": Decimal("10.00"),
                "additional_floor_price": None,
                "multi_floor_pricing_type": "unified",
                "subtotal": Decimal("20.00"),
            },
        ]

        file_path = excel_service._build_and_save_excel(
            invoice_id=99904,
            customer_name="测试客户",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            total_amount=Decimal("20.00"),
            discount_amount=Decimal("0.00"),
            unit_price=None,
            order_details=[],
            balance_info=None,
            invoice_items=invoice_items,
        )

        abs_path = os.path.join("./uploads", file_path)
        cleanup_test_file.append(abs_path)

        wb = load_workbook(abs_path)
        ws = wb["计费明细"]
        assert ws.cell(row=2, column=6).value == "统一"
        # additional_floor_price 为 None 时 openpyxl 写入 None（空单元格）
        assert ws.cell(row=2, column=7).value in (None, "")

    def test_billing_detail_sheet_package_rule(self, excel_service, cleanup_test_file):
        """计费明细 Sheet - 包年规则"""
        invoice_items = [
            {
                "device_type": None,
                "layer_type": None,
                "quantity": 5,
                "unit_price": Decimal("0"),
                "additional_floor_price": None,
                "multi_floor_pricing_type": None,
                "subtotal": Decimal("500.00"),
            },
        ]

        file_path = excel_service._build_and_save_excel(
            invoice_id=99905,
            customer_name="测试客户",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            total_amount=Decimal("500.00"),
            discount_amount=Decimal("0.00"),
            unit_price=None,
            order_details=[],
            balance_info=None,
            invoice_items=invoice_items,
        )

        abs_path = os.path.join("./uploads", file_path)
        cleanup_test_file.append(abs_path)

        wb = load_workbook(abs_path)
        ws = wb["计费明细"]
        assert ws.cell(row=2, column=1).value == "包年"
        assert ws.cell(row=2, column=2).value == "-"


class TestInvoiceExcel_FormatHelpers:
    """格式化辅助方法测试"""

    def test_fmt_dt_datetime(self, excel_service):
        """测试日期格式化"""
        from datetime import datetime

        dt = datetime(2026, 7, 15, 10, 30, 0)
        assert excel_service._fmt_dt(dt) == "2026-07-15 10:30:00"

    def test_fmt_dt_none(self, excel_service):
        """测试日期格式化 - None 值"""
        assert excel_service._fmt_dt(None) == ""

    def test_fmt_edit_status(self, excel_service):
        """测试编辑状态推断"""
        assert excel_service._fmt_edit_status("5", "1") == "待编辑"
        assert excel_service._fmt_edit_status("6", "3") == "已编辑户型图/已编辑VR讲房"
        assert excel_service._fmt_edit_status(None, None) == ""

    def test_fmt_review_status(self, excel_service):
        """测试复审状态格式化"""
        assert excel_service._fmt_review_status(0) == "--"
        assert excel_service._fmt_review_status(2) == "审核通过"
        assert excel_service._fmt_review_status(99) == "--"

    def test_fmt_model_fix_status(self, excel_service):
        """测试修模状态格式化"""
        assert excel_service._fmt_model_fix_status(0) == "--"
        assert excel_service._fmt_model_fix_status(3) == "修模完成"
        assert excel_service._fmt_model_fix_status(99) == "--"


class TestInvoiceExcel_BalanceInfoTimezone:
    """_fetch_balance_info 时区契约测试

    recharge_records.created_at 是 timestamp WITHOUT TIME ZONE（naive），
    invoice.period_start/end 来自 timestamptz 列（aware UTC）。把 aware datetime
    直接传给 naive 列比较，asyncpg 抛 DataError；该异常曾被 except 吞掉仅记
    error，导致「当月充值」恒为 0 而 Excel 仍生成。
    """

    @pytest.mark.asyncio
    async def test_balance_info_strips_tzinfo_for_naive_column(self):
        """aware UTC 周期参数必须剥离 tzinfo 后才用于 created_at 比较"""
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, MagicMock

        service = InvoiceExcelService(db=MagicMock(), external_engine=None)

        captured: dict = {}

        async def fake_execute(stmt):
            # 记录 WHERE 条件中的绑定参数，校验无 aware datetime
            compiled = stmt.compile()
            params = compiled.params
            captured["params"] = params
            result = MagicMock()
            # 第一次查询 CustomerBalance（scalars().first()）：余额 0 的对象
            bal = MagicMock()
            bal.total_amount = Decimal("0")
            result.scalars.return_value.first.return_value = bal
            # 第二次查询充值合计
            result.fetchone.return_value = (0, 0)
            return result

        service.db = MagicMock()
        service.db.execute = AsyncMock(side_effect=fake_execute)

        period_start = datetime(2026, 8, 31, 16, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 9, 30, 15, 59, 59, tzinfo=timezone.utc)

        info = await service._fetch_balance_info(
            customer_id=1,
            period_start=period_start,
            period_end=period_end,
            total_amount=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            invoice_status="draft",
        )

        # 绑定参数中不得存在 aware datetime（asyncpg 对 naive 列会直接报 DataError）
        for value in captured["params"].values():
            assert not (isinstance(value, datetime) and value.tzinfo is not None), (
                f"_fetch_balance_info 仍向 naive 列传递 aware datetime: {value!r}"
            )

        assert info["opening_balance"] == Decimal("0")
        assert info["closing_balance"] == Decimal("-100.00")


class TestInvoiceExcel_IllegalCharacters:
    """外部数据控制字符清洗测试

    外部 MySQL 的项目名等字段可能含控制字符（如 "景发-怡景-12C\x0c"），
    openpyxl 写入时抛 IllegalCharacterError，整个明细文件生成失败、状态置
    failed。_row_to_dict / _clean_cell_text 必须剔除这些字符。
    """

    def test_clean_cell_text_strips_control_chars(self, excel_service):
        """C0 控制字符被剔除，合法字符（含 \\t \\n \\r）保留"""
        raw = "景发-怡景-12C\x0c"
        assert excel_service._clean_cell_text(raw) == "景发-怡景-12C"

        # 合法字符保留
        assert excel_service._clean_cell_text("a\tb\nc\rd") == "a\tb\nc\rd"
        # 中文/emoji 不受影响
        assert excel_service._clean_cell_text("北京-联众🏠") == "北京-联众🏠"
        # 其他控制字符
        assert excel_service._clean_cell_text("a\x00b\x1fc") == "abc"
        # 非字符串原样返回
        assert excel_service._clean_cell_text(123) == 123
        assert excel_service._clean_cell_text(None) is None

    def test_row_to_dict_cleans_string_fields(self, excel_service):
        """_row_to_dict 对所有字符串字段清洗，datetime/数值字段原样返回"""
        from datetime import datetime

        row = (
            "脏项目\x0c名",  # project_name
            "C1",  # custom_code
            "北京\x07",  # city
            "部门",  # department
            "OC-1",  # order_code
            "123",  # nest_id
            "创建人",  # creator_name
            datetime(2026, 9, 1, 10, 0, 0),  # create_date
            "联系人",  # personal_name
            "90",  # nest_area
            1,  # order_status
            2,  # produce_status
            0,  # produce_flag
            "备注\x0b",  # remarks
            "acc",  # editor_account
            "编辑",  # editor_name
            datetime(2026, 9, 2, 10, 0, 0),  # upload_date
            None,  # finish_date
            None,  # first_send_zb_date
            None,  # first_edit_time
            None,  # review_release_date
            "12",  # floor_count
            "设备",  # device_name
            None,  # customer_review_result
            "发布人",  # publisher_name
            None,  # model_fix_status
        )

        result = excel_service._row_to_dict(row)

        assert result["project_name"] == "脏项目名"
        assert result["city"] == "北京"
        assert result["remarks"] == "备注"
        # datetime 字段不被字符串清洗影响
        assert result["create_date"] == datetime(2026, 9, 1, 10, 0, 0)
        assert result["finish_date"] is None
        # 干净字符串原样
        assert result["custom_code"] == "C1"

    def test_build_excel_with_dirty_project_name(self, excel_service, cleanup_test_file):
        """端到端：含控制字符的订单数据能正常生成 Excel（不抛 IllegalCharacterError）"""
        from datetime import datetime

        from app.config import settings
        from app.services.invoice_excel import InvoiceExcelService

        service = InvoiceExcelService(db=MagicMock(), external_engine=None)

        dirty_order = {
            "project_name": "景发-怡景-12C\x0c",
            "custom_code": "C-001",
            "city": "北京",
            "department": "技术部",
            "order_code": "OC-001",
            "nest_id": "12345",
            "creator_name": "张三",
            "create_date": None,
            "personal_name": "李四",
            "nest_area": "90.5",
            "order_status": 1,
            "produce_status": 2,
            "produce_flag": 0,
            "remarks": "备注\x1f",
            "editor_account": "zhangsan",
            "editor_name": "张三",
            "upload_date": None,
            "finish_date": None,
            "first_send_zb_date": None,
            "first_edit_time": None,
            "review_release_date": None,
            "floor_count": "12",
            "device_name": "L",
            "customer_review_result": None,
            "publisher_name": "王五",
            "model_fix_status": None,
        }

        file_path = service._build_and_save_excel(
            invoice_id=999001,
            customer_name="测试客户\x0c",
            period_start=datetime(2026, 8, 31, 16, 0, 0),
            period_end=datetime(2026, 9, 30, 15, 59, 59),
            total_amount=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            unit_price=None,
            order_details=[dirty_order],
            balance_info={
                "opening_balance": Decimal("0"),
                "monthly_recharge": Decimal("0"),
                "closing_balance": Decimal("-100.00"),
            },
            invoice_items=[],
        )

        cleanup_test_file.append(file_path)
        abs_path = os.path.join(getattr(settings, "file_storage_path", "./uploads"), file_path)
        assert os.path.exists(abs_path)

        # 读回验证：控制字符已被剔除
        wb = load_workbook(abs_path)
        ws2 = wb[wb.sheetnames[1]]
        assert ws2.cell(row=2, column=1).value == "景发-怡景-12C"


class TestInvoiceExcel_NonBlockingBuild:
    """generate_detail_file 必须把同步 Excel 构建丢线程池（事件循环防冻结）

    明细 job 跑在 AsyncIOScheduler 的 AsyncIOExecutor 上（与 Web 服务同一
    事件循环）。_build_and_save_excel 纯同步、零 await，直接调用会独占循环
    数秒，导致批量生成期间详情/轮询请求排队（实测 13ms → 17.16s）。
    必须经 asyncio.to_thread 执行。
    """

    @pytest.mark.asyncio
    async def test_generate_detail_file_builds_in_thread(self):
        """generate_detail_file 通过 asyncio.to_thread 调用 _build_and_save_excel"""
        import asyncio
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        service = InvoiceExcelService(db=MagicMock(), external_engine=None)

        # 短路两个数据查询
        service._fetch_order_details = AsyncMock(return_value=[{"project_name": "P"}])
        service._fetch_balance_info = AsyncMock(return_value={"opening_balance": Decimal("0")})

        with patch.object(
            asyncio, "to_thread", new=AsyncMock(return_value="invoices/2026/09/invoice_888001.xlsx")
        ) as mock_to_thread:
            service._build_and_save_excel = MagicMock(return_value="direct-call-not-allowed")

            result = await service.generate_detail_file(
                invoice_id=888001,
                customer_id=1,
                customer_name="测试客户",
                period_start=datetime(2026, 8, 31, 16, 0, 0),
                period_end=datetime(2026, 9, 30, 15, 59, 59),
                total_amount=Decimal("100.00"),
                discount_amount=Decimal("0.00"),
                group_type=100,
                invoice_items=[{"device_type": "L"}],
            )

        # 必须经 to_thread 分发，且透传同步构建函数
        assert mock_to_thread.await_count == 1
        called_fn = mock_to_thread.await_args.args[0]
        assert called_fn == service._build_and_save_excel
        # order_details 经 kwargs 透传
        assert mock_to_thread.await_args.kwargs["order_details"] == [{"project_name": "P"}]
        # 返回值来自 to_thread 结果
        assert result == "invoices/2026/09/invoice_888001.xlsx"
        # 同步构建函数本身未被直接调用（直调用=阻塞事件循环的回归）
        assert service._build_and_save_excel.call_count == 0
