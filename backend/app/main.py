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
    )

    # 初始化数据库引擎
    is_async = True
    if database_engine is None:
        engine = create_async_engine(
            settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
            echo=settings.database_echo,
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
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # pyright: ignore[reportArgumentType]
        )
        # 存储到 app.ctx 供其他模块使用
        app.ctx.async_session_maker = async_session_maker
    else:
        sync_session_maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)  # pyright: ignore[reportCallIssue, reportArgumentType]
        app.ctx.sync_session_maker = sync_session_maker

    # 数据库会话中间件
    if is_async:

        @app.middleware("request")
        async def db_session_middleware(request):
            request.ctx.db_session = async_session_maker()

        @app.middleware("response")
        async def close_db_session(request, response):
            if hasattr(request.ctx, "db_session"):
                await request.ctx.db_session.close()

    else:

        @app.middleware("request")
        def db_session_middleware(request):
            request.ctx.db_session = sync_session_maker()

        @app.middleware("response")
        def close_db_session(request, response):
            if hasattr(request.ctx, "db_session"):
                request.ctx.db_session.close()

    # 注册认证中间件
    auth_middleware(app)

    # 注册审计日志中间件
    audit_middleware(app)

    # 注册静态文件服务（上传文件目录）
    app.static("/uploads/", settings.file_storage_path, name="uploads")

    # 注册路由蓝图
    from .routes.analytics import analytics
    from .routes.audit_logs import audit_logs_bp
    from .routes.auth import auth_bp
    from .routes.billing import billing_bp
    from .routes.customers import customers_bp
    from .routes.database_management import database_bp
    from .routes.dict_routes import dict_bp
    from .routes.files import files_bp
    from .routes.industry_type_routes import industry_type_bp
    from .routes.permissions import permissions_bp
    from .routes.roles import roles_bp
    from .routes.sync_logs import sync_logs_bp
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
    app.blueprint(audit_logs_bp)
    app.blueprint(roles_bp)
    app.blueprint(permissions_bp)
    app.blueprint(dict_bp)
    app.blueprint(industry_type_bp)
    app.blueprint(database_bp)

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

        # 恢复卡住的同步任务
        if is_async:
            try:
                from app.cache.base import cache_service
                from app.services.sync_task_service import SyncTaskService

                redis_client = await cache_service._get_redis()
                async with async_session_maker() as session:
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
