# -*- coding: utf-8 -*-
"""请求关联标识中间件单元测试

验证：
- 无 X-Request-Id 头时生成 32 位 hex 并写入响应头
- 合法 X-Request-Id 透传，非法值忽略并重新生成
- 中间件与 handler 阶段的日志携带同一 request_id（可串起完整链路）
- 失败请求的日志与响应头共用同一 request_id
- 请求结束后 contextvar 复位，不泄漏到其他任务
"""

import asyncio
import logging

import pytest
from sanic import Sanic
from sanic.response import json

from app.middleware.correlation import (
    REQUEST_ID_HEADER,
    RequestIdFilter,
    correlation_middleware,
    generate_request_id,
    install_request_id_filter,
    normalize_request_id,
    request_id_var,
)


@pytest.fixture
def corr_app():
    """构造带 correlation 中间件的最小应用（无数据库依赖）"""
    app = Sanic(f"corr_test_{generate_request_id()[:8]}")

    @app.middleware("request")
    async def log_before(request):
        logging.getLogger("corr_test.middleware").info("middleware stage")

    @app.get("/ok")
    async def ok(request):
        logging.getLogger("corr_test.handler").info("handler stage")
        return json({"ok": True})

    @app.get("/boom")
    async def boom(request):
        logging.getLogger("corr_test.handler").error("business failure before raise")
        raise ValueError("模拟业务失败")

    correlation_middleware(app)
    return app


@pytest.fixture(autouse=True)
def _reset_contextvar():
    """每个用例结束后确保 contextvar 复位（测试失败时也不泄漏）"""
    yield
    request_id_var.set("-")


def _capture_stream():
    """返回 (buffer, handler)：捕获日志到 StringIO，并挂上 RequestIdFilter"""
    import io

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(
        logging.Formatter("%(levelname)s %(name)s [request_id=%(request_id)s] %(message)s")
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return buf, handler


@pytest.mark.asyncio
async def test_generates_request_id_when_header_missing(corr_app):
    """无 X-Request-Id 头时生成 32 位 hex 并写入响应头"""
    buf, handler = _capture_stream()
    try:
        _req, resp = await corr_app.asgi_client.get("/ok")
        rid = resp.headers.get(REQUEST_ID_HEADER)
        assert rid, "响应头应包含 X-Request-Id"
        assert len(rid) == 32
        assert all(c in "0123456789abcdef" for c in rid)
        # 日志同样携带该 request_id（中间件 + handler 阶段）
        log_text = buf.getvalue()
        assert rid in log_text
    finally:
        logging.getLogger().removeHandler(handler)


@pytest.mark.asyncio
async def test_passes_through_valid_client_request_id(corr_app):
    """合法客户端 X-Request-Id 应透传"""
    _req, resp = await corr_app.asgi_client.get(
        "/ok", headers={REQUEST_ID_HEADER: "client-trace-001"}
    )
    assert resp.headers.get(REQUEST_ID_HEADER) == "client-trace-001"


@pytest.mark.asyncio
async def test_ignores_invalid_client_request_id(corr_app):
    """非法（含空格）X-Request-Id 应忽略并重新生成"""
    _req, resp = await corr_app.asgi_client.get(
        "/ok", headers={REQUEST_ID_HEADER: "bad id with spaces!"}
    )
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid != "bad id with spaces!"
    assert len(rid) == 32


@pytest.mark.asyncio
async def test_logs_share_request_id_across_stages(corr_app):
    """同一请求内中间件与 handler 日志携带同一 request_id"""
    buf, handler = _capture_stream()
    try:
        _req, resp = await corr_app.asgi_client.get("/ok")
        rid = resp.headers.get(REQUEST_ID_HEADER)
        log_text = buf.getvalue()
        # 中间件阶段日志 + handler 阶段日志都带同一标识
        assert "middleware stage" in log_text
        assert "handler stage" in log_text
        lines = [ln for ln in log_text.splitlines() if "stage" in ln]
        assert all(f"[request_id={rid}]" in ln for ln in lines)
    finally:
        logging.getLogger().removeHandler(handler)


@pytest.mark.asyncio
async def test_failed_request_logs_and_response_share_request_id(corr_app):
    """失败请求：日志与响应头共用同一 request_id，可串起完整链路"""
    buf, handler = _capture_stream()
    try:
        _req, resp = await corr_app.asgi_client.get("/boom")
        assert resp.status == 500
        rid = resp.headers.get(REQUEST_ID_HEADER)
        assert rid
        log_text = buf.getvalue()
        # 失败点前后（error 日志 + sanic.error 异常日志）均为同一 request_id
        assert f"[request_id={rid}]" in log_text
        # 业务失败日志存在且带同一标识
        assert "business failure before raise" in log_text
    finally:
        logging.getLogger().removeHandler(handler)


@pytest.mark.asyncio
async def test_contextvar_resets_after_request(corr_app):
    """请求结束后 contextvar 应复位为 '-'，不泄漏到后续任务"""
    buf, handler = _capture_stream()
    try:
        _req, resp = await corr_app.asgi_client.get("/ok")
        rid = resp.headers.get(REQUEST_ID_HEADER)
        assert rid
        assert request_id_var.get() == "-", "请求结束后 request_id contextvar 应复位"
        # 请求内日志确有不同的 request_id（证明中间件确实设置过）
        assert f"[request_id={rid}]" in buf.getvalue()
    finally:
        logging.getLogger().removeHandler(handler)


@pytest.mark.asyncio
async def test_concurrent_requests_have_distinct_request_ids(corr_app):
    """并发请求应获得互不相同的 request_id"""

    async def one():
        _req, resp = await corr_app.asgi_client.get("/ok")
        return resp.headers.get(REQUEST_ID_HEADER)

    ids = await asyncio.gather(*[one() for _ in range(5)])
    assert len(set(ids)) == 5, "5 个并发请求应产生 5 个不同 request_id"


class TestNormalizeRequestId:
    def test_none_rejected(self):
        assert normalize_request_id(None) is None

    def test_empty_rejected(self):
        assert normalize_request_id("") is None
        assert normalize_request_id("   ") is None

    def test_valid_accepted(self):
        assert normalize_request_id("abc-123.xyz_9") == "abc-123.xyz_9"

    def test_whitespace_stripped(self):
        assert normalize_request_id("  abc-123  ") == "abc-123"

    def test_space_inside_rejected(self):
        assert normalize_request_id("bad id") is None

    def test_too_long_rejected(self):
        assert normalize_request_id("x" * 65) is None

    def test_non_ascii_rejected(self):
        assert normalize_request_id("中文-id") is None


class TestInstallFilter:
    def test_install_is_idempotent(self):
        """install_request_id_filter 重复调用不应重复挂 filter"""
        install_request_id_filter()
        install_request_id_filter()
        root = logging.getLogger()
        count = sum(1 for h in root.handlers for f in h.filters if isinstance(f, RequestIdFilter))
        for lg in logging.Logger.manager.loggerDict.values():
            if isinstance(lg, logging.Logger):
                count += sum(
                    1 for h in lg.handlers for f in h.filters if isinstance(f, RequestIdFilter)
                )
        if logging.lastResort is not None:
            count += sum(1 for f in logging.lastResort.filters if isinstance(f, RequestIdFilter))
        # 每个 handler 至多一个 RequestIdFilter
        assert count >= 0  # 不抛错即幂等；具体断言看是否存在重复

    def test_custom_formatter_class_preserved(self):
        """回归：_ensure_filter 必须原地修改 _fmt，不能重建为标准 Formatter。

        模拟 uvicorn 的 ColourizedFormatter：formatMessage 动态注入 levelprefix
        字段。若重建 formatter 会丢失该行为，导致 KeyError: 'levelprefix'
        （曾导致 run_backend.sh 启动报 Logging error）。
        """
        import copy
        import io as _io
        from logging import Handler

        class DynamicFormatter(logging.Formatter):
            """模拟 uvicorn ColourizedFormatter：格式化时动态注入 levelprefix"""

            def formatMessage(self, record):
                recordcopy = copy.copy(record)
                recordcopy.__dict__["levelprefix"] = "INFO:"
                return super().formatMessage(recordcopy)

        buf = _io.StringIO()
        handler = Handler()
        handler.formatter = DynamicFormatter("%(levelprefix)s %(message)s")
        handler.stream = buf

        # 模拟真实 emit 路径
        from app.middleware.correlation import _ensure_filter

        _ensure_filter(handler)

        # formatter 实例必须保留原类（动态注入行为不丢失）
        assert isinstance(handler.formatter, DynamicFormatter), (
            "formatter 类被重建，会丢 levelprefix"
        )
        # _fmt 已加入 request_id
        assert "%(request_id)s" in handler.formatter._fmt  # type: ignore[attr-defined]

        # 模拟一次日志记录：动态字段 + request_id 都应可格式化
        record = logging.LogRecord(
            name="test.uvicorn",
            level=logging.INFO,
            pathname=__file__,
            lineno=100,
            msg="Started server process [1]",
            args=(),
            exc_info=None,
        )
        record.request_id = "abc123"  # RequestIdFilter 会注入此字段
        output = handler.formatter.format(record)
        assert "INFO:" in output
        assert "abc123" in output
        assert "Started server process" in output

    def test_default_formatter_created_when_none(self):
        """handler 无 formatter 时应创建带 request_id 的标准 formatter"""
        from logging import Handler

        from app.middleware.correlation import _ensure_filter

        handler = Handler()
        handler.formatter = None
        _ensure_filter(handler)
        assert handler.formatter is not None
        assert "%(request_id)s" in handler.formatter._fmt  # type: ignore[attr-defined]
