"""明细生成任务重启恢复单元测试

覆盖：
1. 启动恢复钩子（_recover_stuck_detail_tasks）：generating→failed 批量标记、
   pending 重新入队（trigger 调用次数与顺序）
2. 生成器原子 claim guard：非 pending（claim rowcount=0）时跳过 Excel 构建
3. 终态条件 UPDATE：仅当 generating 才写终态（resolve last-writer-wins）
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks.invoice_detail_generator import generate_invoice_detail


class _FakeSession:
    """fake AsyncSession：execute 按序返回 中断数结果 + pending 列表结果"""

    def __init__(self, interrupted_rowcount: int, pending_ids: list[int]):
        interrupted_result = MagicMock()
        interrupted_result.rowcount = interrupted_rowcount
        pending_result = MagicMock()
        pending_result.scalars.return_value.all.return_value = pending_ids
        self.execute = AsyncMock(side_effect=[interrupted_result, pending_result])
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncSessionMaker:
    """fake async_sessionmaker：__call__ 每次返回同一假会话"""

    def __init__(self, interrupted_rowcount: int, pending_ids: list[int]):
        self.session = _FakeSession(interrupted_rowcount, pending_ids)

    def __call__(self):
        return self.session


class TestStartupRecovery:
    """启动恢复钩子：generating→failed、pending 重新入队"""

    @pytest.mark.asyncio
    async def test_marks_generating_failed_and_requeues_pending(self):
        """generating 批量转 failed；pending 逐张重新入队（trigger 一次/张）"""
        from app.main import _recover_stuck_detail_tasks

        maker = _FakeAsyncSessionMaker(interrupted_rowcount=2, pending_ids=[11, 22, 33])
        trigger = AsyncMock()

        result = await _recover_stuck_detail_tasks(maker, trigger, app=None)

        assert result == {"interrupted": 2, "requeued": 3}
        # 重新入队：pending 每张触发一次（顺序保持）
        assert trigger.await_count == 3
        assert [c.args[1] for c in trigger.await_args_list] == [11, 22, 33]
        maker.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_pending_no_requeue(self):
        """无 pending 时不触发任何重新入队"""
        from app.main import _recover_stuck_detail_tasks

        maker = _FakeAsyncSessionMaker(interrupted_rowcount=0, pending_ids=[])
        trigger = AsyncMock()

        result = await _recover_stuck_detail_tasks(maker, trigger, app=None)

        assert result == {"interrupted": 0, "requeued": 0}
        trigger.assert_not_awaited()


class TestClaimGuard:
    """生成器原子 claim：仅 pending 才进入构建段"""

    @pytest.mark.asyncio
    async def test_skips_excel_build_when_claim_fails(self, monkeypatch):
        """claim rowcount=0（非 pending/另一实例在跑）时跳过 Excel 构建"""
        invoice = MagicMock()  # 不该被读取到构建段
        session = MagicMock()
        session.get = AsyncMock(return_value=invoice)
        session.commit = AsyncMock()
        session.close = AsyncMock()
        result = MagicMock()
        result.rowcount = 0
        session.execute = AsyncMock(return_value=result)

        from app.services import invoice_excel

        built = {"called": False}

        async def fake_generate(self, **kwargs):
            built["called"] = True
            return "x.xlsx"

        monkeypatch.setattr(
            invoice_excel.InvoiceExcelService, "generate_detail_file", fake_generate
        )

        await generate_invoice_detail(session, 7001)

        assert not built["called"], "claim 失败后不应进入 Excel 构建"
        session.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_builds_when_claim_succeeds(self, monkeypatch):
        """claim rowcount=1（pending）时进入 Excel 构建"""
        invoice = MagicMock()
        invoice.customer_id = 42
        invoice.status = "pending_customer"
        invoice.period_start = MagicMock()
        invoice.period_end = MagicMock()
        invoice.total_amount = MagicMock()
        invoice.discount_amount = MagicMock()
        invoice.detail_file_path = None
        customer = MagicMock()
        customer.company_id = 99
        customer.name = "测试客户"
        session = MagicMock()
        session.get = AsyncMock(
            side_effect=lambda model, _id: invoice if model.__name__ == "Invoice" else customer
        )
        session.commit = AsyncMock()
        session.close = AsyncMock()
        claim_result = MagicMock()
        claim_result.rowcount = 1
        # invoice_items 单实体查询：必须经 scalars() 解包（Row 直接属性访问会 KeyError，
        # 端到端实测回归）；多层计费两字段读 invoice_items 冻结列（不再 JOIN PricingRule）
        fake_item = MagicMock()
        fake_item.device_type = "L"
        fake_item.layer_type = "multi"
        fake_item.quantity = Decimal("78")
        fake_item.unit_price = Decimal("14")
        fake_item.subtotal = Decimal("966")
        fake_item.order_count = 36
        fake_item.multi_floor_pricing_type = "incremental"
        fake_item.additional_floor_price = Decimal("11")
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [fake_item]
        # 月份明细快照行查询（F9）：本地 daily_orders 实体，经 scalars() 解包
        fake_order = MagicMock()
        fake_order.project_name = "测试房源"
        fake_order.custom_code = "C-1"
        fake_order.city = "北京"
        fake_order.department = "技术部"
        fake_order.order_code = "OC-1"
        fake_order.nest_id = "12345"
        fake_order.creator_name = "张三"
        fake_order.create_date = None
        fake_order.personal_name = "李四"
        fake_order.nest_area = "90.5"
        fake_order.order_status = 1
        fake_order.produce_status = 2
        fake_order.produce_flag = 0
        fake_order.remarks = "备注"
        fake_order.editor_account = "zhangsan"
        fake_order.editor_name = "张三"
        fake_order.upload_date = None
        fake_order.finish_date = None
        fake_order.first_send_zb_date = None
        fake_order.first_edit_time = None
        fake_order.review_release_date = None
        fake_order.floor_count = "12"
        fake_order.device_name = "L"
        fake_order.customer_review_result = None
        fake_order.publisher_name = "王五"
        fake_order.model_fix_status = None
        fake_order.nest_created = None
        orders_result = MagicMock()
        orders_result.scalars.return_value.all.return_value = [fake_order]
        # claim → invoice_items 查询 → 月份明细快照行查询
        session.execute = AsyncMock(side_effect=[claim_result, rows_result, orders_result])

        from app.services import invoice_excel

        built = {"called": False}
        captured = {}

        async def fake_generate(self, **kwargs):
            built["called"] = True
            captured.update(kwargs)
            return "invoices/2026/09/invoice_7001.xlsx"

        monkeypatch.setattr(
            invoice_excel.InvoiceExcelService, "generate_detail_file", fake_generate
        )

        factory = MagicMock()
        factory_session = MagicMock()
        factory_session.__aenter__ = AsyncMock(return_value=factory_session)
        factory_session.__aexit__ = AsyncMock(return_value=False)
        factory_session.execute = AsyncMock(return_value=MagicMock(rowcount=1))
        factory_session.commit = AsyncMock()
        factory.__call__ = MagicMock(return_value=factory_session)

        await generate_invoice_detail(session, 7001, session_factory=factory)

        assert built["called"], "claim 成功后应进入 Excel 构建"
        session.get.assert_awaited()
        # 冻结列透传：scalars() 解包后的实体字段原样进入 invoice_items
        assert captured["invoice_items"] == [
            {
                "device_type": "L",
                "layer_type": "multi",
                "quantity": Decimal("78"),
                "unit_price": Decimal("14"),
                "subtotal": Decimal("966"),
                "order_count": 36,
                "multi_floor_pricing_type": "incremental",
                "additional_floor_price": Decimal("11"),
            }
        ]
        # 月份明细改传本地快照行（F9）：不再有 order_codes/group_type
        assert "order_codes" not in captured
        assert "group_type" not in captured
        assert captured["order_details"] == [
            {
                "project_name": "测试房源",
                "custom_code": "C-1",
                "city": "北京",
                "department": "技术部",
                "order_code": "OC-1",
                "nest_id": "12345",
                "creator_name": "张三",
                "create_date": None,
                "personal_name": "李四",
                "nest_area": "90.5",
                "order_status": 1,
                "produce_status": 2,
                "produce_flag": 0,
                "remarks": "备注",
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
                "nest_created": None,
            }
        ]


class TestOrderRowToDict:
    """_order_row_to_dict：DailyOrder → 月份明细 dict 的键完整性（F9）

    _build_and_save_excel 的「月份明细」sheet 逐列 order.get(<key>) 消费；
    键缺失 = 该列静默变空。快照列（模型/迁移）新增时必须同步补映射，
    此测试钉住完整键集合防漂移。
    """

    def test_maps_all_month_detail_keys(self):
        """27 键全量映射，None 字段原样透传（不清洗，清洗在 Excel 写入侧）"""
        from datetime import datetime

        from app.tasks.invoice_detail_generator import _order_row_to_dict

        order = MagicMock()
        order.project_name = "房源\x0c名"  # 控制字符不清洗（写入侧兜底）
        order.custom_code = "C-1"
        order.city = "北京"
        order.department = "技术部"
        order.order_code = "OC-1"
        order.nest_id = "12345"
        order.creator_name = "张三"
        order.create_date = datetime(2026, 9, 1, 10, 0, 0)
        order.personal_name = "李四"
        order.nest_area = "90.5"
        order.order_status = 5
        order.produce_status = 2
        order.produce_flag = 0
        order.remarks = "备注"
        order.editor_account = "zhangsan"
        order.editor_name = "张三"
        order.upload_date = datetime(2026, 9, 2, 10, 0, 0)
        order.finish_date = None
        order.first_send_zb_date = None
        order.first_edit_time = None
        order.review_release_date = None
        order.floor_count = "12"
        order.device_name = "L"
        order.customer_review_result = None
        order.publisher_name = "王五"
        order.model_fix_status = None
        order.nest_created = None

        result = _order_row_to_dict(order)

        assert set(result.keys()) == {
            "project_name",
            "custom_code",
            "city",
            "department",
            "order_code",
            "nest_id",
            "creator_name",
            "create_date",
            "personal_name",
            "nest_area",
            "order_status",
            "produce_status",
            "produce_flag",
            "remarks",
            "editor_account",
            "editor_name",
            "upload_date",
            "finish_date",
            "first_send_zb_date",
            "first_edit_time",
            "review_release_date",
            "floor_count",
            "device_name",
            "customer_review_result",
            "publisher_name",
            "model_fix_status",
            "nest_created",
        }
        # 原值透传（含脏字符串与 datetime），清洗交给 _build_and_save_excel
        assert result["project_name"] == "房源\x0c名"
        assert result["create_date"] == datetime(2026, 9, 1, 10, 0, 0)
        assert result["finish_date"] is None
        assert result["order_status"] == 5
