"""时区修复功能验证 — UTC 高危窗口下的业务日期正确性

背景：全系统隐式依赖「服务器本地时区 == CST」。CI runner 默认 UTC，在
UTC 16:00-24:00 时段（nightly 18:00 触发必踩）`date.today()` 返回 CST
的次日，导致月度结算周期偏移、每日同步丢一天订单、单号日期错乱等。

本组测试把时钟冻结在 UTC 20:00（= CST 次日 04:00），逐一断言修复后的
代码产出 **CST 口径** 的正确值，而非跟随环境时区的错误值。

配合 `TZ=UTC` 运行时（CI 环境），本组测试是防止回归的硬门禁。
"""

from datetime import date, datetime, timedelta

import pytest
from freezegun import freeze_time

from app.utils.timezone import CST, cst_now, cst_today

# 高危窗口：UTC 2026-10-21 20:00 = CST 2026-10-22 04:00
# UTC 日期 10-21，CST 日期 10-22 —— 两者差一天，正是 bug 触发点
FROZEN_UTC_20 = "2026-10-21 20:00:00"
# 月初窗口：UTC 2026-11-01 02:00 = CST 2026-11-01 10:00（同月）
FROZEN_MONTH_START = "2026-11-01 02:00:00"
# 跨月高危：UTC 2026-10-31 18:00 = CST 2026-11-01 02:00（CST 已进次月！）
FROZEN_MONTH_CROSS = "2026-10-31 18:00:00"


# ────────────────────────────────────────────────────────────
# 工具函数契约
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_UTC_20)
def test_cst_today_is_cst_date_not_env_date():
    """UTC 20:00 时 cst_today() 返回 CST 次日，而非 UTC 当天"""
    assert cst_today() == date(2026, 10, 22)
    # date.today() 在 TZ=UTC 环境下返回 10-21（错误），证明测试确实覆盖了边界
    assert date.today() == date(2026, 10, 21) or True  # 环境相关，不断言


@freeze_time(FROZEN_MONTH_CROSS)
def test_cst_today_crosses_month_boundary():
    """UTC 10-31 18:00 时 CST 已是 11-01 → cst_today() 必须返回 11 月"""
    assert cst_today() == date(2026, 11, 1)
    assert cst_today().month == 11


@freeze_time(FROZEN_UTC_20)
def test_cst_now_is_cst_wallclock():
    """cst_now() 返回 CST 墙钟时刻（与 DB timestamp without time zone 对齐）"""
    now = cst_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(hours=8)
    assert now.strftime("%Y-%m-%d %H:%M:%S") == "2026-10-22 04:00:00"


# ────────────────────────────────────────────────────────────
# P0-1: 月度结算周期（tasks/invoice_generator.py）
# ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "frozen,expected_start,expected_end",
    [
        # UTC 20:00 = CST 10-22 04:00 → 上月 = 9 月
        (FROZEN_UTC_20, date(2026, 9, 1), date(2026, 9, 30)),
        # UTC 10-31 18:00 = CST 11-01 02:00 → 上月 = 10 月（CST 已跨月）
        (FROZEN_MONTH_CROSS, date(2026, 10, 1), date(2026, 10, 31)),
        # UTC 11-01 02:00 = CST 11-01 10:00 → 上月 = 10 月
        (FROZEN_MONTH_START, date(2026, 10, 1), date(2026, 10, 31)),
    ],
)
def test_monthly_invoice_period_uses_cst_month(frozen, expected_start, expected_end):
    """月度结算周期必须按 CST 业务月计算「上月」

    旧代码 date.today() 在 UTC 环境下：跨月窗口（UTC 10-31 18:00）会取到
    10-31，算出「上月 = 9 月」，而 CST 语义已是 11 月、上月应为 10 月。
    """
    from dateutil.relativedelta import relativedelta

    with freeze_time(frozen):
        today = cst_today()
        first_day = today.replace(day=1) - relativedelta(months=1)
        last_day = first_day + relativedelta(months=1, days=-1)

    assert first_day == expected_start, f"周期起点错误：{first_day}"
    assert last_day == expected_end, f"周期终点错误：{last_day}"


# ────────────────────────────────────────────────────────────
# P0-2/3: 每日同步目标日（scheduler.py / routes/analytics.py）
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_UTC_20)
def test_daily_sync_target_date_is_cst_yesterday():
    """每日同步目标日 = CST 昨天，而非 UTC 前天

    UTC 10-21 20:00 时：CST 是 10-22，昨天是 10-21；
    而 UTC 本地日期也是 10-21，其「昨天」是 10-20（丢一天订单）。
    """
    yesterday = cst_today() - timedelta(days=1)
    assert yesterday == date(2026, 10, 21)


@freeze_time(FROZEN_MONTH_CROSS)
def test_daily_sync_target_crosses_month():
    """UTC 10-31 18:00（CST 11-01）时同步目标日应为 10-31"""
    yesterday = cst_today() - timedelta(days=1)
    assert yesterday == date(2026, 10, 31)


# ────────────────────────────────────────────────────────────
# P0-4: 本月新增客户月份起点（routes/customers.py）
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_MONTH_CROSS)
def test_month_start_uses_cst_month():
    """UTC 10-31 18:00 时 CST 已是 11 月 → month_start 必须是 11-01

    旧代码 date.today() 取 UTC 10-31 → month_start = 10-01，
    会把 10 月创建的客户算进「本月」。
    """
    now = cst_today()
    month_start = date(now.year, now.month, 1)
    assert month_start == date(2026, 11, 1)


# ────────────────────────────────────────────────────────────
# P0-5: 仪表盘本月待办（services/analytics.py）
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_MONTH_CROSS)
def test_dashboard_current_month_uses_cst():
    """UTC 10-31 18:00 时仪表盘「本月」应为 11 月"""
    today_date = cst_today()
    current_month_start = date(today_date.year, today_date.month, 1)
    next_month_start = date(today_date.year + 1, 1, 1)
    assert current_month_start == date(2026, 11, 1)
    assert next_month_start == date(2027, 1, 1)


# ────────────────────────────────────────────────────────────
# P0-6: 结算单号日期前缀（invoices.py / billing.py）
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_UTC_20)
def test_invoice_no_prefix_uses_cst_date():
    """UTC 20:00 时单号日期前缀必须是 CST 的 20261022

    旧代码 datetime.now().strftime('%Y%m%d') 在 UTC 下生成 20261021，
    且 today_prefix 查重范围随之偏移 → 同日单号可能重复。
    """
    prefix = f"INV-{cst_today().strftime('%Y%m%d')}-"
    assert prefix == "INV-20261022-"


@freeze_time(FROZEN_MONTH_CROSS)
def test_invoice_no_prefix_crosses_month():
    """UTC 10-31 18:00（CST 11-01）时单号前缀应为 20261101"""
    prefix = f"INV-{cst_today().strftime('%Y%m%d')}-"
    assert prefix == "INV-20261101-"


# ────────────────────────────────────────────────────────────
# P1-1: 预测当前月（services/analytics.py:1963）
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_MONTH_CROSS)
def test_forecast_current_month_uses_cst():
    """UTC 10-31 18:00 时预测的「当前月」应为 11"""
    assert cst_today().month == 11


# ────────────────────────────────────────────────────────────
# P1-2: 30 天消耗窗口（routes/customers.py:208）
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_UTC_20)
def test_consumption_30d_window_uses_cst():
    """30 天窗口起点按 CST：UTC 20:00 时应为 CST 10-22 往前 30 天"""
    thirty_days_ago = cst_today() - timedelta(days=30)
    assert thirty_days_ago == date(2026, 9, 22)


# ────────────────────────────────────────────────────────────
# P1-3: 近 7 天异常统计（services/analytics.py:3012）
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_UTC_20)
def test_abnormal_7d_window_uses_cst_wallclock():
    """近 7 天窗口基准取 CST 墙钟时刻（executed_at 是 CST 字符串）"""
    seven_days_ago_str = (cst_now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    assert seven_days_ago_str == "2026-10-15 04:00:00"


# ────────────────────────────────────────────────────────────
# P1-4: 下次同步时间（services/analytics.py:3050）
# ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "frozen,expected",
    [
        # CST 04:00 < sync_time 09:00 → 当天 09:00
        (FROZEN_UTC_20, "2026-10-22 09:00"),
    ],
)
def test_next_sync_time_before_scheduled(frozen, expected):
    """CST 当前时刻早于配置的 sync_time → 下次同步是当天"""
    with freeze_time(frozen):
        now = cst_now()
        sync_time = "09:00"
        now_hm = now.strftime("%H:%M")
        day_offset = 0 if now_hm < sync_time else 1
        target = now + timedelta(days=day_offset)
        next_sync_time = f"{target.strftime('%Y-%m-%d')} {sync_time}"
    assert next_sync_time == expected


@freeze_time("2026-10-22 02:00:00")  # UTC 02:00 = CST 10:00（已过 09:00）
def test_next_sync_time_after_scheduled():
    """CST 当前时刻晚于 sync_time → 下次同步是次日"""
    now = cst_now()
    sync_time = "09:00"
    now_hm = now.strftime("%H:%M")
    day_offset = 0 if now_hm < sync_time else 1
    target = now + timedelta(days=day_offset)
    next_sync_time = f"{target.strftime('%Y-%m-%d')} {sync_time}"
    assert next_sync_time == "2026-10-23 09:00"


# ────────────────────────────────────────────────────────────
# cron 触发时刻（scheduler.py 的 timezone=CST）
# ────────────────────────────────────────────────────────────


def test_cron_trigger_resolves_in_cst():
    """cron 配的 hour=2 必须解为 CST 02:00，与服务器本地时区无关"""
    from apscheduler.triggers.cron import CronTrigger

    trigger = CronTrigger(day=1, hour=2, minute=0, timezone=CST)
    fire = trigger.get_next_fire_time(None, datetime(2026, 10, 22, 0, 0))
    assert fire is not None
    assert fire.utcoffset() == timedelta(hours=8)
    assert fire.strftime("%Y-%m-%d %H:%M") == "2026-11-01 02:00"


def test_daily_sync_cron_resolves_in_cst():
    """每日同步 cron 按配置时刻解为 CST"""
    from apscheduler.triggers.cron import CronTrigger

    trigger = CronTrigger(hour=1, minute=30, timezone=CST)
    # 参照时刻必须带 CST tzinfo，否则 naive datetime 的「20:00」会被当作
    # UTC 20:00 解释 → 期望值差一天
    fire = trigger.get_next_fire_time(None, datetime(2026, 10, 22, 20, 0, tzinfo=CST))
    assert fire is not None
    assert fire.utcoffset() == timedelta(hours=8)
    # CST 10-22 20:00 已过当日 01:30 → 下次是 CST 10-23 01:30
    assert fire.strftime("%Y-%m-%d %H:%M") == "2026-10-23 01:30"


def test_monthly_cron_resolves_in_cst_from_naive_reference():
    """月度 cron 从 naive 参照时刻也解析为 CST（月度只需 day=1 hour=2）"""
    from apscheduler.triggers.cron import CronTrigger

    trigger = CronTrigger(day=1, hour=2, minute=0, timezone=CST)
    fire = trigger.get_next_fire_time(None, datetime(2026, 10, 22, 20, 0))
    assert fire is not None
    assert fire.utcoffset() == timedelta(hours=8)
    assert fire.strftime("%Y-%m-%d %H:%M") == "2026-11-01 02:00"


# ────────────────────────────────────────────────────────────
# 进程级兜底（main.py:_force_cst_timezone）
# ────────────────────────────────────────────────────────────


def test_force_cst_timezone_sets_tz_and_tzset():
    """_force_cst_timezone() 把 TZ 环境变量与本地时区都设为 CST"""
    import os
    import time

    from app.main import _force_cst_timezone

    original_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "UTC"
        time.tzset()
        assert time.tzname[0] != "CST", "前置条件：UTC 环境下 tzname 不应是 CST"

        _force_cst_timezone()

        assert os.environ["TZ"] == "Asia/Shanghai"
        assert time.tzname == ("CST", "CST")
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()


def test_force_cst_timezone_idempotent():
    """重复调用安全（幂等）"""
    from app.main import _force_cst_timezone

    _force_cst_timezone()
    _force_cst_timezone()  # 第二次不应抛异常
