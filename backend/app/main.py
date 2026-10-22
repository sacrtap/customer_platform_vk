import logging
from pathlib import Path
from typing import Union

from sanic import Sanic
from sanic.response import json
from sanic_cors import CORS
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .middleware.audit import audit_middleware
from .middleware.auth import auth_middleware
from .middleware.correlation import correlation_middleware, install_request_id_filter

logger = logging.getLogger(__name__)


async def _check_schema_version(session_factory) -> None:
    """启动时校验运行库是否已升级到最新 Alembic 迁移（fail-open，仅告警不阻断）。

    背景（2026-10-13 事故）：模型新增列 + 迁移文件都已提交，但运行库未执行
    `alembic upgrade head` → `select(Customer)` 报 `UndefinedColumnError` → 所有
    客户相关请求 500。CI 的 `alembic upgrade head` 只作用于 CI 库，无法发现
    「本机/线上库落后于 head」。此处启动即比对版本号，把此类事故提前暴露。

    设计：任何异常都吞掉（库未建、alembic_version 缺失、离线环境等），
    只记日志，绝不阻断启动——避免把「检查器故障」变成新的可用性故障。
    """
    import logging

    log = logging.getLogger(__name__)
    try:
        from pathlib import Path

        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory
        from sqlalchemy import text

        backend_dir = Path(__file__).resolve().parents[1]
        cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        heads = set(ScriptDirectory.from_config(cfg).get_heads())

        async with session_factory() as session:
            row = (await session.execute(text("SELECT version_num FROM alembic_version"))).first()

        current = row[0] if row else None
        if current not in heads:
            log.error(
                "❌ 运行库迁移版本落后：当前 %s，最新 head %s。"
                "请执行 `cd backend && python -m alembic upgrade head`，"
                "否则引用新字段的查询会 500（column does not exist）。",
                current,
                sorted(heads),
            )
        else:
            log.info(f"✓ 数据库迁移版本已是最新：{current}")
    except Exception as e:  # noqa: BLE001 - fail-open，任何异常都不应影响启动
        log.debug(f"跳过迁移版本校验：{e}")


def create_app(
    app_name: str | None = None,
    database_engine: Union[AsyncEngine, Engine, None] = None,
) -> Sanic:
    """创建 Sanic 应用实例

    Args:
        app_name: 应用名称，默认使用 settings.app_name
        database_engine: 数据库引擎，默认使用 settings.database_url 创建
                      可以是异步引擎 (AsyncEngine) 或同步引擎 (Engine)
    """

    app = Sanic(app_name or settings.app_name)

    # 配置 CORS
    CORS(
        app,
        origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        expose_headers=settings.cors_expose_headers,
    )

    # 初始化数据库引擎
    is_async = True
    if database_engine is None:
        engine = create_async_engine(
            settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
            echo=settings.database_echo,
            # asyncpg 默认 pool_size=5/overflow=10（共 15）：批量生成结算单时
            # 每张单的明细任务 + 接口请求同时抢连接，超过 15 即 30s 超时报
            # QueuePool limit 错误。明细任务已有信号量限流（并发 5），这里放大
            # 池容量兜底其他并发请求。
            pool_size=20,
            max_overflow=10,
        )
    elif isinstance(database_engine, AsyncEngine):
        engine = database_engine
    else:
        # 同步引擎
        engine = database_engine
        is_async = False

    # 创建会话工厂
    if is_async:
        async_session_maker = async_sessionmaker(  # pyright: ignore[reportCallIssue]
            engine,  # pyright: ignore[reportArgumentType]  # SQLAlchemy stub：AsyncEngine|Engine 联合绑定
            class_=AsyncSession,
            expire_on_commit=False,  # pyright: ignore[reportArgumentType]
        )
        # 存储到 app.ctx 供其他模块使用
        app.ctx.async_session_maker = async_session_maker
    else:
        sync_session_maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)  # pyright: ignore[reportCallIssue, reportArgumentType]
        app.ctx.sync_session_maker = sync_session_maker

    # 注册请求关联标识中间件（最先注册：request 阶段最先注入 request_id，
    # response 阶段最后复位，保证全链路日志可借由同一标识串起）
    install_request_id_filter()
    correlation_middleware(app)

    # 数据库会话中间件
    # 注意：会话工厂的创建与使用分处两个 `if is_async` 分支，二者由同一常量支配；
    # pyright 无法跨 if 追踪条件相关性，故使用处带 reportPossiblyUnboundVariable 抑制。
    if is_async:

        @app.middleware("request")
        async def db_session_middleware(request):
            request.ctx.db_session = async_session_maker()  # pyright: ignore[reportPossiblyUnboundVariable]

        @app.middleware("response")
        async def close_db_session(request, response):
            if hasattr(request.ctx, "db_session"):
                await request.ctx.db_session.close()

    else:

        @app.middleware("request")
        def db_session_middleware(request):
            request.ctx.db_session = sync_session_maker()  # pyright: ignore[reportPossiblyUnboundVariable]

        @app.middleware("response")
        def close_db_session(request, response):
            if hasattr(request.ctx, "db_session"):
                request.ctx.db_session.close()

    # 注册认证中间件
    auth_middleware(app)

    # 注册审计日志中间件
    audit_middleware(app)

    # 注册静态文件服务（上传文件目录）
    # FILE_STORAGE_PATH 相对路径告警：相对路径将相对进程 cwd 解析，
    # 从不同目录启动会导致文件写入不同位置；生产环境请设为绝对路径。
    if not Path(settings.file_storage_path).is_absolute():
        logger.warning(
            "FILE_STORAGE_PATH 为相对路径（%s），将相对进程 cwd（%s）解析。"
            "生产环境请设置为绝对路径，否则从不同目录启动会导致文件写入不同位置。",
            settings.file_storage_path,
            Path.cwd(),
        )

    app.static("/uploads/", settings.file_storage_path, name="uploads")

    # 注册路由蓝图
    from .routes.analytics import analytics
    from .routes.api_keys import api_keys_bp
    from .routes.audit_logs import audit_logs_bp
    from .routes.auth import auth_bp
    from .routes.balance_whitelist_routes import balance_whitelist_bp
    from .routes.billing import billing_bp
    from .routes.cooperation_status_routes import cooperation_status_bp
    from .routes.customers import customers_bp
    from .routes.database_management import database_bp
    from .routes.dict_routes import dict_bp
    from .routes.erp_system_routes import erp_system_bp
    from .routes.files import files_bp
    from .routes.industry_type_routes import industry_type_bp
    from .routes.openapi import openapi_bp, openapi_customer_bp
    from .routes.permissions import permissions_bp
    from .routes.roles import roles_bp
    from .routes.sync_logs import sync_logs_bp
    from .routes.sync_schedule import sync_schedule_bp
    from .routes.sync_tasks import sync_tasks_bp
    from .routes.tags import customer_tags_bp, profile_tags_bp, tags_bp
    from .routes.users import users_bp

    app.blueprint(auth_bp)
    app.blueprint(users_bp)
    app.blueprint(customers_bp)
    app.blueprint(billing_bp)
    app.blueprint(tags_bp)
    app.blueprint(customer_tags_bp)
    app.blueprint(profile_tags_bp)
    app.blueprint(analytics)
    app.blueprint(files_bp)
    app.blueprint(sync_logs_bp)
    app.blueprint(sync_tasks_bp)
    app.blueprint(sync_schedule_bp)
    app.blueprint(audit_logs_bp)
    app.blueprint(roles_bp)
    app.blueprint(permissions_bp)
    app.blueprint(dict_bp)
    app.blueprint(industry_type_bp)
    app.blueprint(cooperation_status_bp)
    app.blueprint(database_bp)
    app.blueprint(erp_system_bp)
    app.blueprint(balance_whitelist_bp)
    app.blueprint(api_keys_bp)
    app.blueprint(openapi_bp)
    app.blueprint(openapi_customer_bp)

    # 创建外部 MySQL 引擎（订单同步用）

    external_engine = None
    if settings.external_mysql_url:
        external_engine = create_async_engine(
            settings.external_mysql_url.replace("mysql://", "mysql+aiomysql://"),
            pool_size=5,
            pool_recycle=3600,
            echo=settings.database_echo,
        )
        app.ctx.external_mysql_engine = external_engine

    # 初始化任务调度器
    from .tasks.scheduler import init_scheduler

    init_scheduler(app)

    # 注册路由
    @app.get("/health")
    async def health_check(request):
        """健康检查接口"""
        return json(
            {
                "code": 0,
                "message": "success",
                "data": {"status": "healthy", "version": "1.0.0"},
            }
        )

    @app.get("/")
    async def index(request):
        """根路径"""
        return json(
            {
                "code": 0,
                "message": "欢迎来到客户运营中台 API",
                "data": {"docs": "/docs", "health": "/health"},
            }
        )

    # 应用启动事件
    @app.before_server_start
    async def on_start(app, loop):
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"🚀 {settings.app_name} 启动在 {settings.host}:{settings.port}")

        # 校验运行库迁移版本是否最新（fail-open）：防止「模型改了但库没升级」导致
        # 的 UndefinedColumnError 500（2026-10-13 balance_warning_level 事故）。
        if is_async:
            await _check_schema_version(async_session_maker)  # pyright: ignore[reportPossiblyUnboundVariable]

        # 恢复卡住的同步任务
        if is_async:
            try:
                from app.cache.base import cache_service
                from app.services.sync_task_service import SyncTaskService

                redis_client = await cache_service._get_redis()
                async with async_session_maker() as session:  # pyright: ignore[reportPossiblyUnboundVariable]
                    service = SyncTaskService(db=session, redis_client=redis_client)
                    recovered = await service.recover_stuck_tasks()
                    if recovered > 0:
                        logger.info(f"✓ 已恢复 {recovered} 个卡住的同步任务")
                    else:
                        logger.info("✓ 无卡住的同步任务")
            except Exception as e:
                logger.error(f"恢复卡住任务失败: {e}")

    # 应用关闭事件
    @app.after_server_stop
    async def on_shutdown(app, loop):
        if is_async:
            await engine.dispose()  # pyright: ignore[reportGeneralTypeIssues]
        else:
            engine.dispose()
        # 关闭外部 MySQL 引擎
        if hasattr(app.ctx, "external_mysql_engine") and app.ctx.external_mysql_engine:
            await app.ctx.external_mysql_engine.dispose()

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    app.run(
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        access_log=settings.debug,
    )
