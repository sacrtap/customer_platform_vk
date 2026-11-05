"""结算单生成前一致性校验（F1）

比对「本地冻结快照（daily_orders）」与「外部 MySQL 实时可结算订单」的逐日数量，
不一致时拒绝生成结算单，报错文案直接给出客户名 + 差异日期清单 + 修复动作。

口径契约（与 OrderSyncService / InvoiceExcelService._fetch_order_details 严格对齐）：
- 外部侧：nest_model_order.upload_date ∈ [period_start, period_end + 1s)（UTC 墙钟），
  可结算状态 ((order_status >= 3 AND order_status <= 12) OR order_status = 15)，
  按 DATE(upload_date + INTERVAL 8 HOUR) 折算 CST 日历日分桶；
- 本地侧：daily_orders.sync_date ∈ 同窗口、customer_id 匹配，
  Python 侧 utc_to_cst_date_str() 分桶（避免 PG 会话时区差异）。
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ..models.daily_order import DailyOrder
from ..utils.timezone import utc_to_cst_date_str

logger = logging.getLogger(__name__)

# 外部可结算订单状态口径（与 invoice_excel.DETAIL_SQL 一致）
_EXTERNAL_COUNT_SQL = """
SELECT DATE(D.upload_date + INTERVAL 8 HOUR) AS d, COUNT(*) AS c
FROM nest_model_order D
WHERE D.group_type = :group_type
  AND D.upload_date >= :start_dt AND D.upload_date < :end_dt
  AND ((D.order_status >= 3 AND D.order_status <= 12) OR D.order_status = 15)
GROUP BY DATE(D.upload_date + INTERVAL 8 HOUR)
"""


@dataclass(frozen=True)
class DayDiff:
    """单个 CST 日的快照与外部实时量差异"""

    day: str  # CST 日期 'YYYY-MM-DD'
    external: int  # 外部可结算订单数
    local: int  # daily_orders 行数


def _build_diff_message(customer_label: str, period_label: str, diffs: list[DayDiff]) -> str:
    lines = [f"客户「{customer_label}」{period_label} 账期数据不一致，已拒绝生成结算单："]
    for diff in diffs:
        delta = diff.external - diff.local
        if delta > 0:
            lines.append(
                f"  {diff.day} 外部可结算订单 {diff.external} 笔，"
                f"本地已同步 {diff.local} 笔（缺 {delta} 笔）"
            )
        else:
            lines.append(
                f"  {diff.day} 外部可结算订单 {diff.external} 笔，"
                f"本地已同步 {diff.local} 笔（多 {-delta} 笔）"
            )
    lines.append("请对上述日期执行「强制覆盖」模式同步后重新生成。")
    return "\n".join(lines)


class InvoiceConsistencyError(ValueError):
    """快照与外部实时数据不一致（拒绝生成结算单）

    继承 ValueError：与项目「业务错误用 ValueError」约定一致；路由层先捕获本类
    转 40001 可执行文案，其余 ValueError 维持既有处理。
    """

    def __init__(self, customer_name: str, diffs: list[DayDiff], period_label: str):
        self.customer_name = customer_name
        self.diffs = diffs
        self.period_label = period_label
        super().__init__(_build_diff_message(customer_name, period_label, diffs))


def period_label_of(period_start: datetime) -> str:
    """账期标签：period_start 的 CST 年月，如 2026-10"""
    day_str = utc_to_cst_date_str(period_start)
    return day_str[:7] if day_str else "未知"


async def diff_period(
    customer_id: int,
    company_id: Optional[int],
    period_start: datetime,
    period_end: datetime,
    external_engine: Optional[AsyncEngine],
    db_session: AsyncSession,
) -> Optional[list[DayDiff]]:
    """逐日比对本地快照与外部实时可结算订单数。

    Args:
        customer_id: 本地客户 ID（daily_orders.customer_id）
        company_id: 外部客户 ID（nest_model_order.group_type = Customer.company_id）
        period_start / period_end: 账期起止（aware UTC datetime，与
            InvoiceExcelService._fetch_order_details 同窗）
        external_engine: 外部 MySQL 异步引擎；None = 未配置
        db_session: 本地 PG 会话

    Returns:
        差异日列表（外部多/本地多两个方向均含）；无差异返回空列表。
        无法校验（外部引擎未配置或查询异常）时返回 None，调用方记 warning 放行——
        不因基础设施故障阻塞业务。
    """
    if external_engine is None:
        logger.warning(
            "外部 MySQL 引擎未配置，跳过结算单一致性校验（customer_id=%s，放行）", customer_id
        )
        return None

    # 外部侧：一条 SQL 按 CST 日分桶（naive UTC 墙钟 + 8h 折算，与逐日同步窗口一致）
    start_dt = period_start
    end_dt = period_end + timedelta(seconds=1)  # 包含结束时刻，与 _fetch_order_details 同窗
    try:
        async with external_engine.connect() as conn:
            result = await conn.execute(
                text(_EXTERNAL_COUNT_SQL),
                {
                    "group_type": company_id,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                },
            )
            external_rows = result.fetchall()
    except Exception as e:
        logger.warning(
            "查询外部 MySQL 失败，跳过结算单一致性校验（customer_id=%s，放行）: %s",
            customer_id,
            e,
        )
        return None

    external_counts: dict[str, int] = {}
    for row in external_rows:
        external_counts[str(row[0])] = int(row[1])

    # 本地侧：daily_orders 快照，Python 侧 CST 分桶（避免 PG 会话时区差异）
    local_result = await db_session.execute(
        select(DailyOrder.sync_date).where(
            DailyOrder.customer_id == customer_id,
            DailyOrder.sync_date >= period_start,
            DailyOrder.sync_date < end_dt,
            DailyOrder.deleted_at.is_(None),
        )
    )
    local_counts: dict[str, int] = {}
    for (sync_date,) in local_result:
        day_str = utc_to_cst_date_str(sync_date)
        if day_str is not None:
            local_counts[day_str] = local_counts.get(day_str, 0) + 1

    # 差异日（含外部有本地无、本地有外部无两个方向）
    diffs: list[DayDiff] = []
    for day in sorted(set(external_counts) | set(local_counts)):
        external_count = external_counts.get(day, 0)
        local_count = local_counts.get(day, 0)
        if external_count != local_count:
            diffs.append(DayDiff(day=day, external=external_count, local=local_count))
    return diffs
