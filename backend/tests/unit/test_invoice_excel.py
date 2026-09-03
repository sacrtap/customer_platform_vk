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
