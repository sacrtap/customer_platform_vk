"""时区工具（app/utils/timezone.py）单元测试

重点覆盖 `cst_today()`：业务口径「今天」的唯一来源。
`date.today()` 跟随运行环境时区（CI/容器默认 UTC），在 UTC 16:00-24:00
时段返回 CST 的次日，曾导致余额列表包年燃尽天数多算一天（nightly CI
assert 46 == 45 失败）。本组测试用 freezegun 冻结 UTC 边界时刻，
验证 cst_today() 始终返回 CST 日期、且不随 TZ 环境变量变化。
"""

from datetime import date, datetime, timedelta

from freezegun import freeze_time

from app.utils.timezone import (
    CST,
    UTC,
    cst_today,
    naive_cst_datetime_str,
    utc_now,
    utc_to_cst_date_str,
    utc_to_cst_datetime_str,
)

CST_OFFSET = timedelta(hours=8)


@freeze_time("2026-10-21 20:00:00")  # UTC 20:00 = CST 10-22 04:00（跨日边界）
def test_cst_today_returns_cst_date_when_utc_past_midnight_cst():
    """UTC 已过 16:00（CST 次日）→ cst_today() 返回 CST 的次日，而非 UTC 当天"""
    assert utc_now() == datetime(2026, 10, 21, 20, 0, tzinfo=UTC)
    # date.today() 在 UTC 容器下会返回 10-21（错误）；cst_today() 必须是 10-22
    assert cst_today() == date(2026, 10, 22)


@freeze_time("2026-10-21 10:00:00")  # UTC 10:00 = CST 18:00（同一天）
def test_cst_today_same_day_when_both_before_utc_midnight():
    """UTC 未过 16:00 → CST 与 UTC 同日，两者一致"""
    assert cst_today() == date(2026, 10, 21)


@freeze_time("2026-10-21 15:59:59")  # UTC 15:59:59 = CST 23:59:59（CST 当日最后一秒）
def test_cst_today_last_second_before_cst_midnight():
    """CST 23:59:59 → 仍是 CST 当天（临界前 1 秒）"""
    assert cst_today() == date(2026, 10, 21)


@freeze_time("2026-10-21 16:00:00")  # UTC 16:00 = CST 10-22 00:00（CST 跨日瞬间）
def test_cst_today_exact_cst_midnight_rolls_over():
    """CST 00:00:00 整 → 已翻到 CST 次日（临界后第 1 秒）"""
    assert cst_today() == date(2026, 10, 22)


@freeze_time("2026-10-22 00:00:00")  # CST 10-22 08:00
def test_cst_today_at_cst_eight_am():
    """CST 08:00 → CST 当天（与 UTC 日期在此之后同步）"""
    assert cst_today() == date(2026, 10, 22)


@freeze_time("2026-01-01 00:30:00")  # CST 01-01 08:30
def test_cst_today_crosses_year_boundary():
    """跨年边界：UTC 12-31 → CST 01-01"""
    assert cst_today() == date(2026, 1, 1)


def test_cst_today_matches_explicit_conversion():
    """与 datetime.now(CST).date() 等价（实现契约）"""
    assert cst_today() == datetime.now(CST).date()
    # 且不等于裸 date.today() 的时区语义（UTC 环境下会不同，此处只验证类型）
    assert isinstance(cst_today(), date)


def test_cst_constant_is_utc_plus_8():
    """CST 常量保持 UTC+8（业务硬约定）"""
    probe = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    assert probe.astimezone(CST).utcoffset() == CST_OFFSET


# ==================== naive 墙钟时间格式化（Excel 导出口径） ====================
#
# 背景：`TimestampMixin.created_at/updated_at` 是 timestamp without time zone，
# 由 PG server_default=now() 在会话时区（Asia/Shanghai）写入，值本身即 CST 墙钟。
# 导出曾直接 isoformat()，得到 "2026-10-22T17:13:20.535487"（ISO T 分隔 + 微秒），
# 用户不可读；若误用 utc_to_cst_datetime_str（内部 replace(tzinfo=UTC)）则再偏 8 小时。


def test_naive_cst_datetime_str_formats_without_shifting():
    """naive 墙钟时间按原值格式化，不做时区偏移"""
    dt = datetime(2026, 10, 22, 17, 13, 20, 535487)
    assert naive_cst_datetime_str(dt) == "2026-10-22 17:13:20"


def test_naive_cst_datetime_str_none_returns_none():
    """None 原样返回（导出列空值）"""
    assert naive_cst_datetime_str(None) is None


def test_naive_cst_datetime_str_does_not_equal_utc_to_cst():
    """与 utc_to_cst_datetime_str 结果相差 8 小时（防止误用）"""
    dt = datetime(2026, 10, 22, 17, 13, 20)
    assert naive_cst_datetime_str(dt) == "2026-10-22 17:13:20"
    # 误用路径：把墙钟当 UTC 再转 CST 会 +8 小时变成次日凌晨
    assert utc_to_cst_datetime_str(dt) == "2026-10-23 01:13:20"


def test_utc_to_cst_date_str_shifts_timestamptz_to_local_date():
    """timestamptz 列（period_start 等）必须转 CST 后取日期"""
    # DB 存 UTC 2026-08-31 16:00 = CST 2026-09-01 00:00
    dt = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)
    assert utc_to_cst_date_str(dt) == "2026-09-01"


def test_utc_to_cst_date_str_none_returns_none():
    """None 原样返回"""
    assert utc_to_cst_date_str(None) is None
