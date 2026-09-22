"""时区转换工具

数据库存储 UTC 时间，前端输入为 CST（UTC+8）时间。
所有日期在写入/查询前需转为 UTC datetime。

时间流转示意图:
    用户选择 "2026-07-01 ~ 2026-07-31"
    → 前端 a-range-picker 输出 "YYYY-MM-DD" 字符串
    → 后端 local_date_range_to_utc() 转换
    → period_start = 2026-06-30T16:00:00Z (CST 7/1 00:00 → UTC)
    → period_end   = 2026-07-31T15:59:59Z (CST 7/31 23:59 → UTC)
    → SQL 查询: WHERE consumption_date >= '2026-06-30 16:00:00+00'
    → 序列化: isoformat() → "2026-06-30T16:00:00+00:00"
    → 前端 new Date(isoString) → 自动按浏览器时区格式化 → "2026/07/01"
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, overload

CST = timezone(timedelta(hours=8))  # 中国标准时间 UTC+8
UTC = timezone.utc


def local_date_range_to_utc(start_str: str, end_str: str) -> tuple[datetime, datetime]:
    """将前端传入的日期范围转为 UTC datetime 范围。

    输入: "2026-07-01", "2026-07-31"
    语义: CST 7/1 00:00:00 ~ CST 7/31 23:59:59
    输出: (2026-06-30T16:00:00Z, 2026-07-31T15:59:59Z)

    Args:
        start_str: 开始日期字符串，格式 "YYYY-MM-DD"
        end_str: 结束日期字符串，格式 "YYYY-MM-DD"

    Returns:
        (start_utc, end_utc) 两个带时区的 UTC datetime
    """
    start_date = date.fromisoformat(start_str)
    end_date = date.fromisoformat(end_str)
    start_local = datetime.combine(start_date, time(0, 0, 0), tzinfo=CST)
    end_local = datetime.combine(end_date, time(23, 59, 59), tzinfo=CST)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def local_date_to_utc_start(date_str: str) -> datetime:
    """单个日期 → UTC 当天开始时刻（CST 00:00:00 → UTC）。

    输入: "2026-07-01"
    输出: 2026-06-30T16:00:00Z (即 CST 7/1 00:00:00)
    """
    d = date.fromisoformat(date_str)
    return datetime.combine(d, time(0, 0, 0), tzinfo=CST).astimezone(UTC)


def local_date_to_utc_end(date_str: str) -> datetime:
    """单个日期 → UTC 当天结束时刻（CST 23:59:59 → UTC）。

    输入: "2026-07-01"
    输出: 2026-07-01T15:59:59Z (即 CST 7/1 23:59:59)
    """
    d = date.fromisoformat(date_str)
    return datetime.combine(d, time(23, 59, 59), tzinfo=CST).astimezone(UTC)


def local_date_to_utc_day_range(date_str: str) -> tuple[datetime, datetime]:
    """单个日期 → UTC 全天范围 [start, end]。

    输入: "2026-07-01"
    输出: (2026-06-30T16:00:00Z, 2026-07-01T15:59:59Z)
    """
    return local_date_to_utc_start(date_str), local_date_to_utc_end(date_str)


def utc_now() -> datetime:
    """获取当前 UTC datetime（带时区）。"""
    return datetime.now(UTC)


def local_today_utc_start() -> datetime:
    """今天（本地日期）对应的 UTC 开始时刻。"""
    today = date.today()
    return local_date_to_utc_start(today.isoformat())


def local_yesterday_utc_start() -> datetime:
    """昨天（本地日期）对应的 UTC 开始时刻。"""
    yesterday = date.today() - timedelta(days=1)
    return local_date_to_utc_start(yesterday.isoformat())


@overload
def utc_to_cst_date_str(dt: datetime) -> str: ...


@overload
def utc_to_cst_date_str(dt: None) -> None: ...


def utc_to_cst_date_str(dt: Optional[datetime]) -> Optional[str]:
    """UTC datetime → CST 日期字符串（用于 Excel 格式化等）。

    输入: 2026-06-30T16:00:00+00:00
    输出: "2026-07-01"

    兼容 date 对象：如果传入的是 date 而非 datetime，
    直接返回其 isoformat（已是无时区的本地日期）。

    Args:
        dt: 带时区的 datetime 对象、date 对象、或 None

    Returns:
        "YYYY-MM-DD" 格式的本地日期字符串，或 None
    """
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        # 纯 date 对象（无时间/时区），直接返回日期字符串
        return dt.isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CST).strftime("%Y-%m-%d")


def utc_to_cst_datetime_str(dt: Optional[datetime]) -> Optional[str]:
    """UTC datetime → CST 日期时间字符串（用于 Excel 格式化等）。

    输入: 2026-06-30T16:00:00+00:00
    输出: "2026-07-01 00:00:00"

    Args:
        dt: 带时区的 datetime 对象，或 None

    Returns:
        "YYYY-MM-DD HH:MM:SS" 格式的本地日期时间字符串，或 None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
