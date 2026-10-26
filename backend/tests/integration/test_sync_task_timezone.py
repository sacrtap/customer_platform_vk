"""同步任务 created_at 时区契约集成测试（真实 PG）

背景（2026-10-26 修复）：staging 同步日志「创建时间」比本地少 8 小时。

根因：`TimestampMixin.created_at` 是 `timestamp without time zone`，由
`server_default=func.now()` 在 **PG 会话时区** 写墙钟。`create_async_engine`
未设时区时，会话时区跟随 PG 服务端/容器 TZ——本地服务端恰好是
Asia/Shanghai 所以正确，staging 容器 TZ=UTC 写 UTC 墙钟；读出口
`naive_cst_datetime_str()` 假设列里已是 CST 墙钟，把 UTC 墙钟当 CST 输出
→ 少 8 小时（实测：CST 21:35 完成的任务显示成 13:35）。

修复：引擎 `connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}}`。

本文件是**唯一能在 DB 层证明会话时区锁定生效**的地方：
`tests/services/test_sync_task_service.py` 全程 mock db，`created_at` 是手写的
naive 值，与 PG 会话时区无关，无法证伪。此处走真实 create_task → list_tasks。

关于「反向校验」的诚实说明：本地 PG 服务端时区就是 Asia/Shanghai，因此
「移除 connect_args 后测试失败」在本地**不成立**（无锁定连接也返回 CST）。
真正能证伪的是 `test_lock_overrides_utc_server_timezone`：它连到服务端
时区为 UTC 的专用库（等同 staging 环境），无锁定时会话时区就是 UTC，
锁定后才被拉回 CST。该库由本文件的 session 级 fixture 自动创建。
"""

import os
import sys
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.sync_task_service import SyncTaskService
from app.utils.timezone import cst_now

# 数据库操作测试串行执行，避免与其它 xdist worker 的 TRUNCATE 竞态
pytestmark = pytest.mark.xdist_group("db_models")

# 同步一个早已过去的周期，避免与其它测试的真实同步任务撞日期
_PERIOD_START = date(2026, 1, 5)
_PERIOD_END = date(2026, 1, 6)

_TEST_DB_USER = os.environ.get("POSTGRES_USER", "postgres")
_TEST_DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
_TEST_DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
_TEST_DB_NAME = os.environ.get("POSTGRES_DB", "customer_platform_test")
_TEST_DB_URL = (
    f"postgresql+asyncpg://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:5432/{_TEST_DB_NAME}"
)

# 服务端时区为 UTC 的专用库：复现 staging 环境（容器 TZ=UTC）。
# 本地 PG 服务端是 Asia/Shanghai，无法用来证伪「锁定是否真的生效」。
_TZPROBE_DB_NAME = "customer_platform_tzprobe"
_TZPROBE_ADMIN_URL = (
    f"postgresql+asyncpg://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:5432/postgres"
)
_TZPROBE_DB_URL = f"postgresql+asyncpg://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:5432/{_TZPROBE_DB_NAME}"

# 与 tests/integration/conftest.py 保持一致：引擎锁定参数
_LOCKED_CONNECT_ARGS = {"server_settings": {"TimeZone": "Asia/Shanghai"}}


@pytest.fixture(scope="session")
async def tzprobe_database():
    """建一个 PG 服务端时区为 UTC 的专用库（等同 staging）

    session 级：整个测试会话只建一次。库名带固定前缀，测试结束后删除。
    若已存在（上次异常退出）则复用，避免重复 DDL。
    """
    admin_engine = create_async_engine(_TZPROBE_ADMIN_URL, echo=False, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            exists = (
                await conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _TZPROBE_DB_NAME}
                )
            ).scalar()
            if not exists:
                # CREATE DATABASE 不能在事务里执行，AUTOCOMMIT 下直接跑
                await conn.execute(text(f'CREATE DATABASE "{_TZPROBE_DB_NAME}"'))
            # 关键：把该库的服务端默认时区设为 UTC（staging 场景）
            await conn.execute(text(f"ALTER DATABASE \"{_TZPROBE_DB_NAME}\" SET timezone TO 'UTC'"))
        yield _TZPROBE_DB_URL
    finally:
        # 清理：断开连接后才能 DROP
        async with admin_engine.connect() as conn:
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :n AND pid <> pg_backend_pid()"
                ),
                {"n": _TZPROBE_DB_NAME},
            )
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{_TZPROBE_DB_NAME}"'))
        await admin_engine.dispose()


@pytest.fixture
def mock_redis():
    """Redis mock：create_task 只用到 set/exists/delete/hset/expire"""
    client = MagicMock()
    client.set = AsyncMock(return_value=True)
    client.exists = AsyncMock(return_value=False)
    client.delete = AsyncMock(return_value=True)
    client.hset = AsyncMock(return_value=True)
    client.expire = AsyncMock(return_value=True)
    return client


@pytest.fixture
async def async_engine():
    """异步测试引擎——必须带与生产一致的会话时区锁定"""
    engine = create_async_engine(
        _TEST_DB_URL,
        echo=False,
        pool_pre_ping=True,
        connect_args=_LOCKED_CONNECT_ARGS,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    """异步会话 + 测试后清理 sync_tasks / sync_task_logs"""
    session_maker = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        # 只清理本文件写入的表，避免影响其它测试的数据
        try:
            await session.execute(
                text(
                    "DELETE FROM sync_task_logs WHERE task_id IN "
                    "(SELECT id FROM sync_tasks WHERE start_date = :sd)"
                ),
                {"sd": _PERIOD_START},
            )
            await session.execute(
                text("DELETE FROM sync_tasks WHERE start_date = :sd"),
                {"sd": _PERIOD_START},
            )
            await session.commit()
        except Exception:
            await session.rollback()


@pytest.fixture
async def service(db_session, mock_redis):
    """绑定真实异步会话 + mock Redis 的 SyncTaskService"""
    return SyncTaskService(db=db_session, redis_client=mock_redis)


@pytest.fixture
async def created_task(service):
    """走真实 create_task 落库一个 pending 任务（created_at 由 DB 侧 func.now() 写）"""
    task = await service.create_task(
        start_date=_PERIOD_START,
        end_date=_PERIOD_END,
        sync_mode="skip_existing",
        operator_id=None,
    )
    assert task.id is not None
    return task


# ============================================================
# 会话时区锁定（核心：证伪修复本身）
# ============================================================


async def test_engine_session_timezone_is_cst(async_engine):
    """测试引擎的 PG 会话时区必须是 Asia/Shanghai

    这是所有后续断言的前提：会话时区没锁定时，func.now() 写 naive 列取的是
    服务端/容器 TZ 墙钟，created_at 的语义随部署环境漂移。
    """
    async with async_engine.connect() as conn:
        tz = (await conn.execute(text("SHOW timezone"))).scalar()

    assert tz == "Asia/Shanghai"


async def test_lock_overrides_utc_server_timezone(tzprobe_database):
    """引擎锁定必须覆盖 UTC 的 PG 服务端时区（staging 场景，可证伪）

    这是本修复的**决定性断言**。专用库的服务端时区被设为 UTC（等同 staging），
    于是：
    - 无锁定的引擎 → 会话时区 UTC，`func.now()` 写 UTC 墙钟（staging 症状）
    - 带锁定的引擎 → 会话时区被拉回 Asia/Shanghai，写 CST 墙钟（修复后）

    本地 PG 服务端是 Asia/Shanghai，测不出区别；只有把服务端时区也改成 UTC
    才能真正证伪。移除引擎的 connect_args 后，本测试的 locked 侧断言会失败。
    """
    # 对照：无锁定引擎（修复前状态）
    unlocked = create_async_engine(tzprobe_database, echo=False)
    try:
        async with unlocked.connect() as conn:
            unlocked_tz = (await conn.execute(text("SHOW timezone"))).scalar()
            unlocked_now = (await conn.execute(text("SELECT now()::text"))).scalar()
    finally:
        await unlocked.dispose()

    assert unlocked_tz == "UTC", (
        f"专用库服务端时区应为 UTC（staging 复现环境），实得 {unlocked_tz}；"
        "若不为 UTC，本测试失去证伪能力"
    )

    # 被测：带锁定的引擎（修复后状态）
    locked = create_async_engine(tzprobe_database, echo=False, connect_args=_LOCKED_CONNECT_ARGS)
    try:
        async with locked.connect() as conn:
            locked_tz = (await conn.execute(text("SHOW timezone"))).scalar()
            locked_now = (await conn.execute(text("SELECT now()::text"))).scalar()
    finally:
        await locked.dispose()

    assert locked_tz == "Asia/Shanghai", (
        f"引擎未锁定会话时区（实得 {locked_tz}，同库无锁定会话为 {unlocked_tz}）："
        "staging 的 PG 为 UTC 时 created_at 会写 UTC 墙钟，读出口 "
        "naive_cst_datetime_str() 把它当 CST 输出 → 显示少 8 小时"
    )
    assert locked_now.endswith("+08"), f"now() 应为 CST 墙钟（+08），实得 {locked_now}"
    # 同一瞬间在两种墙钟基准下应相差 8 小时
    assert unlocked_now.split("+")[0].strip() != locked_now.split("+")[0].strip(), (
        f"墙钟基准未被锁定改变：unlocked={unlocked_now} locked={locked_now}"
    )


async def test_func_now_writes_cst_wallclock_on_utc_server(tzprobe_database):
    """UTC 服务端 + 锁定 → func.now() 写 naive 列必须是 CST 墙钟

    直接复现事故链：同一 PG 服务端（UTC）下，锁定前后 naive 列的写入值。
    """
    engine = create_async_engine(tzprobe_database, echo=False, connect_args=_LOCKED_CONNECT_ARGS)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS tz_wallclock_probe"))
            await conn.execute(
                text(
                    "CREATE TABLE tz_wallclock_probe "
                    "(id int primary key, naive_col timestamp, tz_col timestamptz)"
                )
            )
            await conn.execute(text("INSERT INTO tz_wallclock_probe VALUES (1, now(), now())"))
            row = (
                await conn.execute(
                    text("SELECT naive_col::text, tz_col::text FROM tz_wallclock_probe")
                )
            ).one()
            await conn.execute(text("DROP TABLE tz_wallclock_probe"))
    finally:
        await engine.dispose()

    naive_text, tz_text = row[0], row[1]
    assert naive_text == tz_text.split("+")[0].strip(), (
        f"naive 列应与 timestamptz 列的 CST 墙钟一致：naive={naive_text} tz={tz_text}"
    )
    assert tz_text.endswith("+08"), f"timestamptz 列应为 CST 表示（+08），实得 {tz_text}"


async def test_session_timezone_lock_survives_pool_recycle(async_engine):
    """连接池回收后新连接仍带锁定后的会话时区

    asyncpg 在每条连接建立时执行 SET TIME ZONE，故 recycle / 重连都保持一致。
    防止有人把锁定改成「只在首次连接生效」的一次性 hack。
    """
    await async_engine.dispose()  # 强制关闭池中全部连接，下次 connect 必建新连接

    async with async_engine.connect() as conn:
        tz = (await conn.execute(text("SHOW timezone"))).scalar()
    assert tz == "Asia/Shanghai"


async def test_main_app_engine_locks_session_timezone():
    """主应用引擎（create_app 自身创建路径）必须锁定会话时区为 Asia/Shanghai

    这是本修复唯一的线上行为改动点：`app/main.py` 的 `create_async_engine`
    带 `connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}}`。

    上面其它 DB 测试用的是测试自建引擎（fixture 传入 create_app），
    即使 main.py 的锁定被误删也照样通过。此处取模块级 `app.main:app`
    （由 `create_app()` 无参创建，走 `database_engine is None` 分支），
    即真实线上引擎，才能真正证伪该改动点。
    """
    # tests/conftest.py 的 pytest_configure 会清掉所有 app* 模块缓存，
    # integration/conftest.py 已 import app.main 并 clear 过 Sanic 注册表。
    # 此处若 app.main 未导入需自行导入，先清注册表避免 "already in use"。
    from sanic import Sanic

    if "app.main" not in sys.modules:
        Sanic._app_registry.clear()

    from app.main import app as main_app  # noqa: PLC0415

    engine = main_app.ctx.async_session_maker.kw["bind"]
    async with engine.connect() as conn:
        tz = (await conn.execute(text("SHOW timezone"))).scalar()

    assert tz == "Asia/Shanghai", (
        "主应用引擎未锁定 PG 会话时区：naive 时间列会跟随容器 TZ 写入，"
        "staging（TZ=UTC）的 created_at 将比 CST 少 8 小时"
    )


# ============================================================
# 读出口契约（真实 create_task → list_tasks）
# ============================================================


async def test_created_at_is_cst_wallclock(db_session, created_task):
    """created_at 必须写 CST 墙钟，与 cst_now() 同一基准（差值仅测试耗时）

    反向护栏：若引擎未锁定时区，且 PG 服务端为 UTC（staging），DB 写的是
    UTC 墙钟，与 cst_now() 差约 8 小时 → 本断言失败。
    """
    # 重新从 DB 读，确保拿到的是 server_default=func.now() 写入的值，
    # 而非 ORM 会话缓存里 Python 侧的旧对象
    row = (
        await db_session.execute(
            text("SELECT created_at FROM sync_tasks WHERE id = :tid"),
            {"tid": str(created_task.id)},
        )
    ).one()
    db_created_at = row[0]

    # PG 侧 timestamp without time zone → asyncpg 读出 naive datetime
    assert db_created_at.tzinfo is None, (
        f"created_at 应为 naive（timestamp without time zone），实得 {db_created_at!r}"
    )

    wallclock_now = cst_now().replace(tzinfo=None)
    drift = abs((wallclock_now - db_created_at).total_seconds())
    assert drift < 120, (
        f"created_at={db_created_at} 与 CST 墙钟 {wallclock_now} 相差 {drift:.0f}s；"
        "会话时区未锁定 Asia/Shanghai 时会差约 8 小时"
    )


async def test_list_tasks_serializes_created_at_as_cst_wallclock(service, created_task):
    """读出口 list_tasks → _task_to_dict 必须给出 CST 墙钟字符串

    断言形如 "YYYY-MM-DD HH:MM:SS"（无 T / 无时区后缀），且与 DB 中的
    created_at 墙钟一致（读出口不得再 astimezone）。
    """
    result = await service.list_tasks(page=1, page_size=50)

    matched = [t for t in result["list"] if t["task_id"] == str(created_task.id)]
    assert matched, f"list_tasks 未返回新建任务 {created_task.id}"

    serialized = matched[0]["created_at"]
    assert serialized is not None
    assert "T" not in serialized
    assert "+" not in serialized
    assert "Z" not in serialized
    assert len(serialized) == 19

    # 与 DB 墙钟逐秒对齐（去掉微秒）
    assert serialized == created_task.created_at.strftime("%Y-%m-%d %H:%M:%S")


async def test_completed_at_not_before_created_at(service, db_session, created_task):
    """终态任务：completed_at 不得早于 created_at

    任务创建后立即完成是正常业务语义。时区串味会让 completed_at 显示成
    UTC 时刻（比 created_at 早 8 小时），用户看到「先完成后创建」。
    """
    # 直接置终态：completed_at 写 aware UTC（与 execute_task 的真实写入口径一致）
    await db_session.execute(
        text("UPDATE sync_tasks SET status = 'completed', completed_at = :now WHERE id = :tid"),
        {"now": datetime.now(), "tid": str(created_task.id)},
    )
    await db_session.commit()
    # 让 ORM 会话丢弃缓存，list_tasks 才会从 DB 重新读出终态
    db_session.expire_all()

    result = await service.list_tasks(page=1, page_size=50)
    matched = [t for t in result["list"] if t["task_id"] == str(created_task.id)]
    assert matched, f"list_tasks 未返回任务 {created_task.id}"

    item = matched[0]
    assert item["status"] == "completed"
    assert item["completed_at"] is not None
    assert item["completed_at"] >= item["created_at"], (
        f"completed_at={item['completed_at']} 早于 created_at={item['created_at']}"
    )


async def test_stuck_task_running_duration_uses_cst_wallclock(service, db_session):
    """卡死判定的运行时长必须按 CST 墙钟算，不受进程 TZ 影响

    create_task 的活跃任务检测用 `cst_now() - created_at`。若误用
    datetime.now()，进程 TZ=UTC 时会把时长少算 8 小时，45 分钟前创建的
    卡死任务被判为「未超 30 分钟」→ 永远不恢复、新任务被拒。
    """
    # Redis 进度 key 必须「存在」，才会走到「运行时长超时」这一分支
    # （key 消失会直接判进程终止，与时长无关，测不到墙钟基准）
    service.redis_client.exists = AsyncMock(return_value=True)

    stale_at = (cst_now() - timedelta(minutes=45)).replace(tzinfo=None)

    row = (
        await db_session.execute(
            text(
                "INSERT INTO sync_tasks "
                "(id, start_date, end_date, sync_mode, status, total_days, created_at) "
                "VALUES (gen_random_uuid(), :sd, :ed, 'skip_existing', 'running', 2, :ca) "
                "RETURNING id, created_at"
            ),
            {"sd": _PERIOD_START, "ed": _PERIOD_END, "ca": stale_at},
        )
    ).one()
    await db_session.commit()
    assert abs((row[1] - stale_at).total_seconds()) < 1

    # 以同一周期创建任务：create_task 应检出这条 running 任务已超时并标记 failed，
    # 超时任务不算「真正活跃」，故新任务可正常创建（不会抛 DuplicateSyncTaskError）
    task = await service.create_task(
        start_date=_PERIOD_START,
        end_date=_PERIOD_END,
        sync_mode="skip_existing",
        operator_id=None,
    )
    assert task is not None

    status = (
        await db_session.execute(
            text("SELECT status, error_message FROM sync_tasks WHERE id = :tid"),
            {"tid": row[0]},
        )
    ).one()
    assert status[0] == "failed"
    assert "30 分钟" in (status[1] or ""), (
        f"45 分钟前的卡死任务应被判超时，实得 status={status[0]} msg={status[1]!r}"
    )
