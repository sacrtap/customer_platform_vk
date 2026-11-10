"""每日订单数据模型"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class DailyOrder(BaseModel):
    """每日订单数据模型"""

    __tablename__ = "daily_orders"

    order_code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="订单 ID（外部系统）"
    )
    custom_code: Mapped[str | None] = mapped_column(String(50), comment="房源编号")
    nest_id: Mapped[str | None] = mapped_column(String(50), comment="模型编号")
    company_name: Mapped[str | None] = mapped_column(String(200), comment="公司名称")
    group_type: Mapped[str | None] = mapped_column(String(50), comment="客户 ID（外部系统）")
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id"), comment="系统客户 ID"
    )
    create_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="订单创建时间（外部系统）"
    )
    upload_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="订单上传日期（外部系统）"
    )
    order_status: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="订单状态（外部系统）"
    )
    floor_count: Mapped[int | None] = mapped_column(Integer, comment="楼层数")
    device_type: Mapped[str | None] = mapped_column(String(10), comment="设备类型（X/N/L）")
    sync_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="同步日期"
    )

    # ===== 月份明细展示列快照（nest_model_order 全量，F9）=====
    # 「月份明细」sheet 的 29 列数据源。此前该 sheet 实时查外部 MySQL，与本地
    # 冻结计费口径存在时点漂移（外部删单/改期即行数对不上），且重生成历史单
    # 会拿到「当前」外部状态。改为读本快照后三表严格同源；create_date/
    # upload_date 同步层由 DATE() 改为原值 datetime（此前时刻丢失，月份明细
    # 显示 00:00:00）。历史行这些列为 NULL → 月份明细对应格为空（不回填：
    # 外部可能已删单取不回，且已生成文件是交付物）。
    project_name: Mapped[str | None] = mapped_column(String(200), comment="房源名称")
    city: Mapped[str | None] = mapped_column(String(50), comment="城市")
    department: Mapped[str | None] = mapped_column(String(100), comment="业务部门")
    creator_name: Mapped[str | None] = mapped_column(String(100), comment="创建人")
    personal_name: Mapped[str | None] = mapped_column(String(100), comment="所属人")
    nest_area: Mapped[str | None] = mapped_column(String(50), comment="面积")
    produce_status: Mapped[str | None] = mapped_column(String(20), comment="编辑状态码")
    produce_flag: Mapped[str | None] = mapped_column(String(20), comment="编辑标志码")
    remarks: Mapped[str | None] = mapped_column(Text, comment="备注")
    editor_account: Mapped[str | None] = mapped_column(String(100), comment="编辑人账号")
    editor_name: Mapped[str | None] = mapped_column(String(100), comment="编辑人姓名")
    finish_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="上传完成时间"
    )
    first_send_zb_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="第一次分配时间"
    )
    first_edit_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="户型图绘制时间"
    )
    review_release_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="审核发布时间"
    )
    device_name: Mapped[str | None] = mapped_column(String(100), comment="设备编号")
    customer_review_result: Mapped[int | None] = mapped_column(Integer, comment="复审状态码")
    publisher_name: Mapped[str | None] = mapped_column(String(100), comment="发布人")
    model_fix_status: Mapped[int | None] = mapped_column(Integer, comment="户型图修模状态码")

    # 关系
    customer = relationship("Customer", backref="daily_orders")

    # 索引
    __table_args__ = (
        Index("idx_daily_orders_customer_date", "customer_id", "sync_date"),
        Index("idx_daily_orders_sync_date", "sync_date"),
        # 唯一键含 custom_code（房源编号，F8）：同一订单号被外部派给多个房源时
        # 各自成行、各自计费（一号两房源 = 两笔业务）；custom_code 为空（外部无
        # 房源编号）时 COALESCE 归一为空串，保持「订单号即唯一」的原语义
        # （PG 唯一索引不约束 NULL，故用表达式索引而非直接含列）
        Index(
            "uq_order_custom_sync_date",
            "order_code",
            text("COALESCE(custom_code, '')"),
            "sync_date",
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<DailyOrder(order_code={self.order_code}, sync_date={self.sync_date})>"
