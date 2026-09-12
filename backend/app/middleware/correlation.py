# -*- coding: utf-8 -*-
"""请求关联标识中间件

为每个请求注入稳定的 request id（关联标识）：
- 透传客户端提供的 ``X-Request-Id``（合法时），否则生成 uuid4 hex
- 写入响应头 ``X-Request-Id``，供调用方/前端回查
- 通过 contextvars 暴露给日志 Filter，使同一次请求的所有日志记录
  携带 ``request_id`` 字段，可借由同一标识串起完整调用链路

约定见 ``.trellis/spec/backend/logging-guidelines.md``。
"""

import logging
import re
import uuid
from contextvars import ContextVar, Token
from typing import Optional

from sanic import Sanic
from sanic.request import Request

REQUEST_ID_HEADER = "X-Request-Id"

# 合法 request id：1-64 位 ASCII 可见字符（字母数字与常见分隔符）
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")

# 当前请求的关联标识（无请求上下文时为 "-"）
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger(__name__)


class RequestIdFilter(logging.Filter):
    """把当前请求的关联标识附加到日志记录（``record.request_id``）"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def generate_request_id() -> str:
    """生成新的关联标识（32 位 hex，无连字符）"""
    return uuid.uuid4().hex


def normalize_request_id(value: Optional[str]) -> Optional[str]:
    """校验并规范化客户端传入的关联标识；非法值返回 None（应重新生成）"""
    if not value:
        return None
    value = value.strip()
    if not _VALID_REQUEST_ID.match(value):
        return None
    return value


def _ensure_filter(handler: logging.Handler) -> None:
    """幂等地给 handler 挂上 RequestIdFilter，并让 formatter 输出 request_id

    注意：必须**原地修改** formatter 的 ``_fmt``，不能重建为标准
    ``logging.Formatter`` —— uvicorn 的 ``ColourizedFormatter`` 等在
    ``formatMessage()`` 中动态注入 ``levelprefix`` 等字段，重建会丢失该
    行为导致 ``KeyError: 'levelprefix'``。
    """
    if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
        handler.addFilter(RequestIdFilter())

    fmt = handler.formatter
    if fmt is None:
        handler.formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [request_id=%(request_id)s] %(message)s"
        )
        return
    # 已有 request_id 字段则跳过
    current = getattr(fmt, "_fmt", "")
    if "%(request_id)s" in current:
        return
    # 在 %(message)s 前插入 [request_id=%(request_id)s]
    if "%(message)s" in current:
        new_fmt = current.replace("%(message)s", "[request_id=%(request_id)s] %(message)s", 1)
    else:
        new_fmt = current + " [request_id=%(request_id)s]"
    # 原地替换格式串：_fmt（旧式引用）与 _style._fmt（实际格式化源）都要更新
    fmt._fmt = new_fmt  # type: ignore[attr-defined]
    style = getattr(fmt, "_style", None)
    if style is not None:
        style._fmt = new_fmt  # type: ignore[attr-defined]


def install_request_id_filter() -> None:
    """幂等地把 RequestIdFilter 安装到所有已知 handler 与 lastResort。

    业务模块 logger（``app.*``）无 handler，记录传播到 root；root 无 handler
    时由 lastResort 兜底。因此需要覆盖 root handlers、各命名 logger 的
    handlers 以及 lastResort。
    """
    root = logging.getLogger()
    for handler in root.handlers:
        _ensure_filter(handler)

    for _name, lg in logging.Logger.manager.loggerDict.items():
        if isinstance(lg, logging.Logger):
            for handler in lg.handlers:
                _ensure_filter(handler)

    if logging.lastResort is not None:
        _ensure_filter(logging.lastResort)


def correlation_middleware(app: Sanic):
    """注册请求关联标识中间件

    Sanic 排序规则（order=(priority, -definition)）：
    - request 中间件按 order 降序执行 → priority 越大越先，用 1000 保证最先注入
    - response 中间件按 order 降序后反转 → priority 越小越先，用 -1000 保证最后复位
    """

    @app.middleware("request", priority=1000)
    async def inject_request_id(request: Request):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = normalize_request_id(incoming) or generate_request_id()
        request.ctx.request_id = request_id
        # token 存 ctx，response 阶段复位 contextvar，避免泄漏到其他任务
        request.ctx._request_id_token = request_id_var.set(request_id)

    @app.middleware("response", priority=-1000)
    async def attach_request_id(request: Request, response):
        request_id = getattr(request.ctx, "request_id", None)
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        token: Optional[Token] = getattr(request.ctx, "_request_id_token", None)
        if token is not None:
            request_id_var.reset(token)
            request.ctx._request_id_token = None
