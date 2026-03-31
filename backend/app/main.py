from sanic import Sanic
from sanic.response import json
from sanic_cors import CORS
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from .config import settings
from .middleware.auth import auth_middleware


def create_app() -> Sanic:
    """创建 Sanic 应用实例"""

    app = Sanic(settings.app_name)

    # 配置 CORS
    CORS(
        app,
        origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # 初始化数据库引擎
    engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
        echo=settings.database_echo,
    )

    # 创建会话工厂
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # 数据库会话中间件
    @app.middleware("request")
    async def db_session_middleware(request):
        request.ctx.db_session = await async_session_maker()

    @app.middleware("response")
    async def close_db_session(request, response):
        if hasattr(request.ctx, "db_session"):
            await request.ctx.db_session.close()

    # 注册认证中间件
    auth_middleware(app)

    # 注册路由蓝图
    from .routes.auth import auth_bp
    from .routes.users import users_bp
    from .routes.customers import customers_bp

    app.blueprint(auth_bp)
    app.blueprint(users_bp)
    app.blueprint(customers_bp)

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
        app.logger.info(
            f"🚀 {settings.app_name} 启动在 {settings.host}:{settings.port}"
        )

    # 应用关闭事件
    @app.after_server_stop
    async def on_shutdown(app, loop):
        await engine.dispose()

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
