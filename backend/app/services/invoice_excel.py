"""结算单明细 Excel 生成服务

由调用方提供订单数据（daily_orders 本地快照，F9）与计费项快照
（invoice_items），生成包含"合计"和"月份明细"两个 Sheet 的 Excel 文件。

模板参照: 安溪如是VR房源模型消费2026年7月结算单.xlsx
"""

import asyncio
import logging
import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.timezone import CST, utc_to_cst_date_str

logger = logging.getLogger(__name__)

# Excel 单元格（XML 1.0）不允许的控制字符：openpyxl 写入时抛 IllegalCharacterError。
# 合法范围：\\t(0x09) \\n(0x0A) \\r(0x0D) 及 0x20 以上；剔除其余 C0 控制符。
_ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# ============================================================
# 明细 Sheet 表头（27 列：2026-11-10 移除恒空的 uv/pv 死列，
# 与模板完全对齐）
# ============================================================
DETAIL_HEADERS = [
    "房源名称",
    "房源id",
    "城市",
    "业务部门",
    "订单编号",
    "项目链接",
    "创建人",
    "创建时间",
    "所属人",
    "面积",
    "订单状态",
    "编辑状态",
    "备注",
    "编辑人账号",
    "编辑人姓名",
    "上传完成时间",
    "处理完成时间",
    "第一次分配时间",
    "户型图绘制时间",
    "户型图最新绘制人",
    "审核发布时间",
    "楼层层数",
    "设备编号",
    "接单时间",
    "复审状态",
    "发布人",
    "户型图修模状态",
]

# ============================================================
# 订单状态映射
# ============================================================
ORDER_STATUS_MAP = {
    0: "拍摄中",
    2: "已接单未上传",
    3: "已上传处理中",
    5: "待编辑",
    6: "有编辑",
    8: "已上线",
    9: "有编辑已上线",
    11: "已下线",
    12: "有编辑已下线",
    13: "已取消",
    14: "拒绝VR拍摄",
    15: "已作废",
}

# 编辑状态映射（基于 produce_status + produce_flag）
EDIT_STATUS_MAP = {
    ("5", "1"): "待编辑",
    ("6", "1"): "已编辑户型图",
    ("6", "2"): "已编辑VR讲房",
    ("6", "3"): "已编辑户型图/已编辑VR讲房",
}

# 复审状态映射
REVIEW_STATUS_MAP = {
    0: "--",
    1: "待审核",
    2: "审核通过",
    3: "审核驳回",
}

# 户型图修模状态映射
MODEL_FIX_STATUS_MAP = {
    0: "--",
    1: "待修模",
    2: "修模中",
    3: "修模完成",
}


class InvoiceExcelService:
    """结算单明细 Excel 生成服务"""

    def __init__(
        self,
        db: AsyncSession,
        session_factory: Optional[Any] = None,
    ):
        self.db = db
        # 可选会话工厂：提供时余额查询改用短会话（查完即还），
        # 调用方可在构建 Excel 前提前关闭长事务会话（见
        # tasks/invoice_detail_generator.py 的事务缩短）。
        self.session_factory = session_factory

    async def generate_detail_file(
        self,
        invoice_id: int,
        customer_id: int,
        customer_name: str,
        period_start: datetime,
        period_end: datetime,
        total_amount: Decimal,
        discount_amount: Decimal,
        unit_price: Optional[Decimal] = None,
        invoice_status: str = "draft",
        invoice_items: Optional[List[Dict[str, Any]]] = None,
        order_details: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """生成结算单明细 Excel 文件

        Args:
            order_details: 「月份明细」订单数据（调用方从 daily_orders 本地快照
                查询，F9）；None 视为查询失败，返回 None。

        Returns:
            文件路径（成功）或 None（失败）
        """
        logger.info(f"开始生成结算单 {invoice_id} 的明细文件")

        if order_details is None:
            logger.warning(f"结算单 {invoice_id} 缺少订单明细数据")
            return None

        logger.info(f"结算单 {invoice_id} 共 {len(order_details)} 条订单明细（本地快照）")

        # 查询客户余额和当月充值
        balance_info = await self._fetch_balance_info(
            customer_id,
            period_start,
            period_end,
            total_amount,
            discount_amount,
            invoice_status,
        )

        # 3. 生成 Excel
        # _build_and_save_excel 是纯同步函数（openpyxl 逐格写样式 + wb.save zip
        # 序列化，零 await 点），其输入 order_details/balance_info 均为已取回的
        # 纯内存数据、函数内不碰 DB，线程安全。明细 job 跑在 AsyncIOScheduler
        # 的 AsyncIOExecutor 上（与 Web 服务同一事件循环），直接同步调用会独占
        # 循环数秒，导致批量生成期间列表/轮询/详情请求全部排队（实测详情 13ms
        # 被阻塞到 17s）。故丢默认线程池执行，事件循环保持响应。
        file_path = await asyncio.to_thread(
            self._build_and_save_excel,
            invoice_id=invoice_id,
            customer_name=customer_name,
            period_start=period_start,
            period_end=period_end,
            total_amount=total_amount,
            discount_amount=discount_amount,
            unit_price=unit_price,
            order_details=order_details,
            balance_info=balance_info,
            invoice_items=invoice_items or [],
        )

        logger.info(f"结算单 {invoice_id} 明细文件已生成: {file_path}")
        return file_path

    async def _fetch_balance_info(
        self,
        customer_id: int,
        period_start: datetime,
        period_end: datetime,
        total_amount: Decimal,
        discount_amount: Decimal,
        invoice_status: str,
    ) -> Dict[str, Any]:
        """查询客户余额和当月充值信息

        当前余额（CustomerBalance.total_amount）已包含当月充值（充值为即时入账），
        因此期初余额需先扣除当月充值；结算后余额 = 期初 + 当月充值 - 最终结算金额，
        保证当月充值只计入一次。

        期初余额 = 当前余额 - 当月充值 + 本结算单最终金额（如已扣款则需加回）
        当月充值 = 结算周期内充值记录总和
        结算后余额 = 期初余额 + 当月充值 - 最终结算金额
        """
        # 有会话工厂时用短会话查完即还：调用方（明细任务）在查询计费项后
        # 即关闭长事务会话，余额查询不应再依赖它
        if self.session_factory is not None:
            async with self.session_factory() as short_session:
                return await self._query_balance_info(
                    short_session,
                    customer_id,
                    period_start,
                    period_end,
                    total_amount,
                    discount_amount,
                    invoice_status,
                )

        return await self._query_balance_info(
            self.db,
            customer_id,
            period_start,
            period_end,
            total_amount,
            discount_amount,
            invoice_status,
        )

    async def _query_balance_info(
        self,
        db: AsyncSession,
        customer_id: int,
        period_start: datetime,
        period_end: datetime,
        total_amount: Decimal,
        discount_amount: Decimal,
        invoice_status: str,
    ) -> Dict[str, Any]:
        """余额/充值查询实现（db 为调用方提供的会话，由 _fetch_balance_info 分流）"""
        from sqlalchemy import func, select

        from ..models.billing import CustomerBalance, RechargeRecord

        result: Dict[str, Any] = {
            "opening_balance": Decimal(0),
            "monthly_recharge": Decimal(0),
            "closing_balance": Decimal(0),
        }

        try:
            # 查询当前余额
            balance = await db.execute(
                select(CustomerBalance).where(CustomerBalance.customer_id == customer_id)
            )
            bal = balance.scalars().first()

            current_balance = bal.total_amount if bal and bal.total_amount else Decimal(0)
            final_amount = total_amount - discount_amount

            # 查询当月充值记录总额：按业务归期 recharge_date（实际回款日）与
            # CST 业务日窗口统计。period_start/end 来自 timestamptz 列（aware UTC
            # datetime），先转 CST 再取自然日；结束为 end 的 CST 日期 +1 天，
            # 使用半开区间（包含结束日、不偏移 8 小时）。
            def _cst_date(value: datetime) -> date:
                if value.tzinfo is not None:
                    return value.astimezone(CST).date()
                # naive 列按既有 CST 墙钟约定取日期，不直接剥 tzinfo 当 UTC
                return value.date()

            start_date = _cst_date(period_start)
            end_date_exclusive = _cst_date(period_end) + timedelta(days=1)
            recharge_result = await db.execute(
                select(
                    func.coalesce(func.sum(RechargeRecord.real_amount), 0),
                    func.coalesce(func.sum(RechargeRecord.bonus_amount), 0),
                ).where(
                    RechargeRecord.customer_id == customer_id,
                    # 已撤销（软删）充值不计入结算期充值额，否则与余额口径矛盾
                    RechargeRecord.deleted_at.is_(None),
                    RechargeRecord.recharge_date >= start_date,
                    RechargeRecord.recharge_date < end_date_exclusive,
                )
            )
            recharge_row = recharge_result.fetchone()
            monthly_recharge = Decimal(0)
            if recharge_row:
                monthly_recharge = (recharge_row[0] or 0) + (recharge_row[1] or 0)

            # 期初余额：当前余额已包含当月充值（充值为即时入账），需先扣除；
            # 结算单已完成（已扣款）时再加回最终金额，还原扣款前的期初
            if invoice_status in ("completed",):
                opening_balance = current_balance - monthly_recharge + final_amount
            else:
                opening_balance = current_balance - monthly_recharge

            # 结算后余额 = 期初 + 当月充值 - 最终结算金额
            # draft/pending: → current_balance - final_amount（充值只算一次）
            # completed:     → current_balance（扣款已发生，余额即当前值）
            closing_balance = opening_balance + monthly_recharge - final_amount

            result["opening_balance"] = opening_balance
            result["monthly_recharge"] = monthly_recharge
            result["closing_balance"] = closing_balance

        except Exception as e:
            logger.error(f"查询客户余额失败: {e}")

        return result

    @staticmethod
    def _clean_cell_text(val: Any) -> Any:
        """清洗单元格文本：移除 openpyxl 拒绝的控制字符（IllegalCharacterError）

        Excel 单元格合法字符为 XML 1.0 允许范围（含 \\t \\n \\r）；外部数据里的
        \\x00-\\x08 / \\x0b / \\x0c / \\x0e-\\x1f 等控制字符会让 openpyxl 在写入时
        抛 IllegalCharacterError，整个明细文件生成失败。此处统一剔除，其余原样保留。
        F9 起亦为月份明细快照数据的唯一清洗出口（快照原值落库）。
        """
        if not isinstance(val, str):
            return val
        return _ILLEGAL_XML_CHARS_RE.sub("", val)

    @staticmethod
    def _fmt_dt(val: Any) -> str:
        """将 datetime 对象格式化为 CST 字符串 'YYYY-MM-DD HH:MM:SS'

        2026-11-10 时区修复：daily_orders 时间列为 timestamptz，读取出来是
        aware UTC（如 02:10:28+00:00）。此前直接 strftime 按墙钟渲染，
        未换算时区，展示比真实 CST 少 8 小时。此处统一转 CST 后渲染；
        naive 值（历史数据/测试夹具）按原样渲染，行为不变。
        """
        if val is None:
            return ""
        if isinstance(val, datetime):
            if val.tzinfo is not None:
                val = val.astimezone(CST)
            return val.strftime("%Y-%m-%d %H:%M:%S")
        return str(val)

    @staticmethod
    def _fmt_edit_status(produce_status: Any, produce_flag: Any) -> str:
        """推断编辑状态"""
        key = (str(produce_status or ""), str(produce_flag or ""))
        return EDIT_STATUS_MAP.get(key, "")

    @staticmethod
    def _fmt_review_status(val: Any) -> str:
        return REVIEW_STATUS_MAP.get(val, "--")

    @staticmethod
    def _fmt_model_fix_status(val: Any) -> str:
        return MODEL_FIX_STATUS_MAP.get(val, "--")

    def _build_and_save_excel(
        self,
        invoice_id: int,
        customer_name: str,
        period_start: datetime,
        period_end: datetime,
        total_amount: Decimal,
        discount_amount: Decimal,
        unit_price: Optional[Decimal],
        order_details: List[Dict[str, Any]],
        balance_info: Optional[Dict[str, Any]] = None,
        invoice_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """生成 Excel 并保存到文件

        Returns:
            文件相对路径
        """
        wb = Workbook()

        # 通用样式
        header_font = Font(bold=True)
        header_fill = PatternFill("solid", start_color="D9E1F2")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # ============================================================
        # Sheet 1: 合计（10 列 A-J，与模板对齐）
        # ============================================================
        # types-openpyxl 将 cell(value) 声明为 str | None，但 openpyxl 运行时接受
        # int/float/Decimal；本函数大量写入数值列，标注 Any 统一豁免该误报。
        ws1: Any = wb.active
        assert ws1 is not None  # 新建 Workbook 必有活动工作表
        ws1.title = "合计"

        # 标题行
        ws1.merge_cells("A1:J1")
        ws1.cell(
            row=1,
            column=1,
            value=f"{self._clean_cell_text(customer_name)}VR房源模型消费结算汇总",
        )
        ws1.cell(row=1, column=1).font = Font(bold=True, size=14)
        ws1.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")

        # 表头（10 列，移除了"单价"列）
        headers_1 = [
            "结算周期",
            "模型总数量（套）",
            "计费模型数量（套）",
            "总金额（元）",
            "减免金额（元）",
            "实际结算金额（元）",
            "期初余额（元）",
            "当月充值金额（元）",
            "结算后余额（元）",
            "备注",
        ]
        for col, h in enumerate(headers_1, 1):
            cell = ws1.cell(row=2, column=col, value=h)
            cell.font = header_font
            cell.alignment = header_align
            cell.fill = header_fill

        # 数据行
        # 模型总数量/计费模型数量口径统一为 invoice_items.order_count 之和（F2）：
        # 与「计费明细」sheet 同源（冻结快照），不再取外部实时 len(order_details)
        model_count = sum(
            Decimal(str(item.get("order_count") or 0)) for item in (invoice_items or [])
        )
        final_amount = total_amount - discount_amount
        period_str = f"{utc_to_cst_date_str(period_start)} - {utc_to_cst_date_str(period_end)}"
        ws1.cell(row=3, column=1, value=period_str)
        ws1.cell(row=3, column=2, value=model_count)
        ws1.cell(row=3, column=3, value=model_count)
        ws1.cell(row=3, column=4, value=float(total_amount))
        ws1.cell(row=3, column=5, value=float(discount_amount))
        ws1.cell(row=3, column=6, value=float(final_amount))
        # 期初余额 / 当月充值 / 结算后余额
        if balance_info:
            ws1.cell(row=3, column=7, value=float(balance_info.get("opening_balance", 0)))
            ws1.cell(row=3, column=8, value=float(balance_info.get("monthly_recharge", 0)))
            ws1.cell(
                row=3, column=9, value=float(balance_info.get("closing_balance", final_amount))
            )
        else:
            ws1.cell(row=3, column=7, value="")
            ws1.cell(row=3, column=8, value="")
            ws1.cell(row=3, column=9, value=float(final_amount))
        # 备注列兜底（F9）：月份明细行数与本单计费量不一致时显式暴露差异。
        # 两者现同源（daily_orders 快照 vs invoice_items 冻结快照），正常恒等；
        # 保留为纯展示层防御：覆盖出账后订单被跨日迁移清理/周期窗口修调等
        # 导致快照行数变化的场景，提示用户核对，不阻塞任何流程
        external_count = len(order_details or [])
        if external_count != int(model_count):
            ws1.cell(
                row=3,
                column=10,
                value=(
                    f"订单明细 {external_count} 笔，本单计费 {int(model_count)} 笔，"
                    f"差异 {external_count - int(model_count)} 笔（请核对同步完整性）"
                ),
            )
        else:
            ws1.cell(row=3, column=10, value="")

        # 列宽
        for col in range(1, 11):
            ws1.column_dimensions[get_column_letter(col)].width = 18

        # ============================================================
        # Sheet 2: 月份明细（29 列，与模板对齐）
        # ============================================================
        ws2 = wb.create_sheet(title=f"{utc_to_cst_date_str(period_start)[:7]}")

        # 表头
        for col, h in enumerate(DETAIL_HEADERS, 1):
            cell = ws2.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.alignment = header_align
            cell.fill = header_fill

        # 数据行
        for row_idx, order in enumerate(order_details, 2):
            nest_id = order.get("nest_id", "")
            project_link = f"https://beyond.3dnest.cn/house/?m={nest_id}" if nest_id else ""
            status_val = order.get("order_status")
            status_str = (
                ORDER_STATUS_MAP.get(status_val, str(status_val)) if status_val is not None else ""
            )

            row_data = [
                order.get("project_name", ""),
                order.get("custom_code", ""),
                order.get("city", ""),
                order.get("department", ""),
                order.get("order_code", ""),
                project_link,
                order.get("creator_name", ""),
                self._fmt_dt(order.get("create_date")),
                order.get("personal_name", ""),
                order.get("nest_area", ""),
                status_str,
                self._fmt_edit_status(order.get("produce_status"), order.get("produce_flag")),
                order.get("remarks", ""),
                order.get("editor_account", ""),
                order.get("editor_name", ""),
                self._fmt_dt(order.get("upload_date")),
                # 处理完成时间 = 外部 nest.created（2026-11-10）：原取 finish_date
                # 恒为 NULL，示例表真实口径是房源主表 created
                self._fmt_dt(order.get("nest_created")),
                self._fmt_dt(order.get("first_send_zb_date")),
                self._fmt_dt(order.get("first_edit_time")),
                "",  # 户型图最新绘制人（需额外关联，暂留空）
                self._fmt_dt(order.get("review_release_date")),
                order.get("floor_count", ""),
                order.get("device_name", ""),
                "",  # 接单时间（需额外查询，暂留空）
                self._fmt_review_status(order.get("customer_review_result")),
                order.get("publisher_name", ""),
                self._fmt_model_fix_status(order.get("model_fix_status")),
            ]

            for col, val in enumerate(row_data, 1):
                # 兜底清洗：即使调用方传入未清洗的 order dict（含控制字符），
                # openpyxl 也不会抛 IllegalCharacterError。正常链路 _row_to_dict
                # 出口已清洗，这里防御其他构造来源。
                cell = ws2.cell(row=row_idx, column=col, value=self._clean_cell_text(val))
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")

        # 列宽
        col_widths = {
            1: 22,
            2: 12,
            3: 16,
            4: 12,
            5: 22,
            6: 50,
            7: 12,
            8: 22,
            9: 12,
            10: 10,
        }
        for col, w in col_widths.items():
            ws2.column_dimensions[get_column_letter(col)].width = w
        for col in range(11, len(DETAIL_HEADERS) + 1):
            if col not in col_widths:
                ws2.column_dimensions[get_column_letter(col)].width = 16

        # ============================================================
        # Sheet 3: 计费明细（InvoiceItem 列表）
        # ============================================================
        if invoice_items:
            ws3 = wb.create_sheet(title="计费明细")

            # 计费明细表头（8 列：订单数 + 楼层数双口径——订单数与「合计」「月份
            # 明细」一致，楼层数保留使 incremental 金额可验算）
            billing_headers = [
                "设备类型",
                "楼层",
                "订单数",
                "楼层数",
                "单价（元）",
                "小计（元）",
                "多层计费类型",
                "其他层单价（元）",
            ]
            for col, h in enumerate(billing_headers, 1):
                cell = ws3.cell(row=1, column=col, value=h)
                cell.font = header_font
                cell.alignment = header_align
                cell.fill = header_fill

            # 数据行
            for row_idx, item in enumerate(invoice_items, 2):
                # 设备类型映射
                dt = item.get("device_type") or ""
                dt_str = {"X": "X", "N": "N", "L": "L"}.get(dt, dt or "包年")

                # 楼层映射
                lt = item.get("layer_type", "")
                lt_str = {"single": "单层", "multi": "多层"}.get(lt, lt or "-")

                quantity = float(item.get("quantity", 0))
                # 订单数口径（与「合计」数量列、「月份明细」行数一致）：优先
                # order_count，历史/显式 items 无该键时回退 quantity
                # （前端 InvoiceDetailDrawer 同款 order_count ?? quantity 兜底）
                item_order_count = item.get("order_count")
                order_cnt_val = (
                    float(item_order_count) if item_order_count is not None else quantity
                )
                unit_p = float(item.get("unit_price", 0))
                # 小计口径（F3）：优先 item["subtotal"]（多层递增/阶梯/包年下的真实
                # 小计，与 invoices.total_amount 同源）；历史/显式 items 无该键时
                # 回退 quantity × unit_price
                item_subtotal = item.get("subtotal")
                subtotal = float(item_subtotal) if item_subtotal is not None else quantity * unit_p

                mfp_type = item.get("multi_floor_pricing_type") or ""
                mfp_str = {"incremental": "递增", "unified": "统一"}.get(mfp_type, mfp_type or "-")

                afp = item.get("additional_floor_price")
                afp_val = float(afp) if afp is not None else ""

                row_data = [
                    dt_str,
                    lt_str,
                    order_cnt_val,
                    quantity,
                    unit_p,
                    subtotal,
                    mfp_str,
                    afp_val,
                ]
                for col, val in enumerate(row_data, 1):
                    cell = ws3.cell(row=row_idx, column=col, value=val)
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="center")

            # 列宽
            billing_widths = {1: 12, 2: 10, 3: 10, 4: 10, 5: 12, 6: 12, 7: 14, 8: 16}
            for col, w in billing_widths.items():
                ws3.column_dimensions[get_column_letter(col)].width = w

        # ============================================================
        # 保存文件
        # ============================================================
        year = utc_to_cst_date_str(period_start)[:4]
        month = utc_to_cst_date_str(period_start)[5:7]
        rel_dir = os.path.join("invoices", year, month)
        base_dir = getattr(settings, "file_storage_path", "./uploads")
        abs_dir = os.path.join(base_dir, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        filename = f"invoice_{invoice_id}.xlsx"
        abs_path = os.path.join(abs_dir, filename)
        wb.save(abs_path)

        # 落盘后二次确认：文件必须存在且非空，状态才可置 completed
        # 若文件写入异常（磁盘满、权限等），抛出异常让调用方置 failed
        if not os.path.exists(abs_path) or os.path.getsize(abs_path) == 0:
            raise IOError(f"明细文件写入后验证失败（不存在或为空）: {abs_path}")

        return os.path.join(rel_dir, filename)
