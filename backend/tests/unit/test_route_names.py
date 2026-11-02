"""路由名唯一性回归测试

Sanic 以 `{app_name}.{blueprint}.{handler函数名}` 派生路由名；同一蓝图内
两个同名 handler 即产生重复路由名。Sanic 24.12 仅在启动时抛
DeprecationWarning——本地 pytest 不报错，但 CI 的 uvicorn 进程
warnings-as-errors，启动直接失败（2026-11-03 VR 结算单 confirm_sales
与 invoices 同名 handler 实测撞名，E2E job 挂于 backend server 启动）。

集成测试的 app fixture 使用 unique app name 且不触发完整启动序列，
无法暴露该类问题；故在此直接 finalize 并断言路由名唯一。

注意：蓝图（billing_bp 等）是模块级单例，同一进程内创建第二个 app 并
finalize 会共享/消耗蓝图状态，故本文件只创建并检查一个 app 实例。
"""

import sys

import pytest


@pytest.mark.asyncio
async def test_route_names_unique_and_vr_routes_registered():
    """路由名全局唯一 + VR 结算单 13 个端点全部注册"""
    # tests/conftest.py 的 pytest_configure 会清掉所有 app* 模块缓存但不清
    # Sanic 注册表；app.main 未缓存时先清注册表，避免模块级 create_app()
    # 报 "already in use"（同 test_sync_task_timezone.py 的处理）。
    from sanic import Sanic

    if "app.main" not in sys.modules:
        Sanic._app_registry.clear()

    from app.main import create_app

    app = create_app(app_name="route_name_probe")
    app.finalize()

    routes = list(app.router.routes)
    names = [route.name for route in routes]
    assert names, "未收集到任何路由"

    # 1. 路由名唯一（handler 函数名不得跨模块撞名）
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"重复路由名（handler 函数名跨模块撞名）：{duplicates}"

    # 2. VR 结算单端点全部注册（路径集合覆盖 13 个端点去重后的 11 条路径；
    #    注意 Sanic route.path 不带前导斜杠）
    vr_paths = {route.path for route in routes if "vr-settlements" in route.path}
    expected = {
        "api/v1/billing/vr-settlements",
        "api/v1/billing/vr-settlements/<settlement_id:int>",
        "api/v1/billing/vr-settlements/<settlement_id:int>/submit",
        "api/v1/billing/vr-settlements/<settlement_id:int>/confirm-cs",
        "api/v1/billing/vr-settlements/<settlement_id:int>/confirm-sales",
        "api/v1/billing/vr-settlements/<settlement_id:int>/confirm-sales-supervisor",
        "api/v1/billing/vr-settlements/<settlement_id:int>/reject-sales-supervisor",
        "api/v1/billing/vr-settlements/<settlement_id:int>/discount",
        "api/v1/billing/vr-settlements/<settlement_id:int>/confirm",
        "api/v1/billing/vr-settlements/<settlement_id:int>/retry-deduction",
        "api/v1/billing/vr-settlements/<settlement_id:int>/cancel",
    }
    missing = expected - vr_paths
    assert not missing, f"缺失 VR 路由: {missing}"

    # 3. 关键 handler 名不与既有 invoices 路由撞名
    assert "route_name_probe.billing.confirm_vr_sales" in names
    assert "route_name_probe.billing.confirm_sales" in names  # invoices 的销售确认
    assert names.count("route_name_probe.billing.confirm_vr_sales") == 1
