"""CRM（weiwenjia）开放 API 只读客户端

约束（见 docs/specs/2026-11-11-crm-recharge-management-plan.md）：
- 只读：不向 CRM 创建/修改/审批任何业务记录。
- 企业级共享限流与 token 缓存走 Redis；Redis 不可用时拒绝发起外部请求，
  不退化为「各进程独立限流」。
- 只记录接口与错误摘要，绝不记录请求 body、token、Authorization 或完整响应。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlparse

import httpx
from redis.asyncio import Redis

from ..cache.base import cache_service

logger = logging.getLogger(__name__)

# 官方域名白名单：只允许 HTTPS 官方主机，请求体不能指定 host
ALLOWED_CRM_HOSTS = {"lxcrm.weiwenjia.com", "lxcrm-api.weiwenjia.com"}

# 官方限频：10 次/10 秒 → 每 1.25 秒最多启动一个请求
RATE_LIMIT_MS = 1250
RATE_WAIT_TIMEOUT = 30.0
REQUEST_TIMEOUT = 30.0
LOGIN_LOCK_TTL_MS = 60_000
LOGIN_LOCK_WAIT_TIMEOUT = 30.0
PAGE_SIZE = 100

TOKEN_TTL_PREFIX = "crm_token"


class CrmError(Exception):
    """CRM 集成错误基类"""

    #: HTTP 状态码映射由路由层使用：True → 503，False → 502
    is_config_error = False


class CrmConfigError(CrmError):
    """未启用 / 缺凭据 / 域名非法 / Redis 不可用（路由映射 503）"""

    is_config_error = True


class CrmUpstreamError(CrmError):
    """上游 HTTP / 业务 code / 分页契约失败（路由映射 502）"""

    is_config_error = False


class CrmNotFoundError(CrmUpstreamError):
    """上游明确 404（回款/客户不存在或不可见）"""


class CrmAuthError(CrmError):
    """登录凭据无效 / 企业ID不匹配（属于用户可修正的配置问题）"""

    is_config_error = False


def _validate_base_url(base_url: str) -> str:
    """只允许官方 HTTPS 域名"""
    parsed = urlparse(base_url or "")
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_CRM_HOSTS:
        raise CrmConfigError("CRM 地址配置非法，仅允许官方 HTTPS 域名")
    return f"https://{parsed.hostname}"


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


class CrmClient:
    """CRM 开放 API 客户端

    用法：
        async with CrmClient(redis=redis_client) as client:
            async for customer in client.iter_customers():
                ...

    `http_client` 仅供测试注入 `httpx.MockTransport`；生产路径自建连接池。
    """

    def __init__(
        self,
        *,
        redis: Optional[Redis] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        base_url: Optional[str] = None,
        corp_id: Optional[str] = None,
        phone: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._redis = redis
        self._http_client = http_client
        self._owns_http_client = http_client is None
        # 默认取「运行期生效配置」：页面保存过的值为准，否则回退环境变量
        from .crm_config import get_crm_config

        cfg = get_crm_config()
        self.base_url = _validate_base_url(base_url or cfg.base_url)
        self.corp_id = (corp_id if corp_id is not None else cfg.corp_id).strip()
        self.phone = (phone if phone is not None else cfg.phone).strip()
        self.password = password if password is not None else cfg.password

        if not self.corp_id or not self.phone or not self.password:
            raise CrmConfigError("CRM 未配置企业ID或登录凭据")

    # ------------------------------------------------------------------ 生命周期

    async def __aenter__(self) -> "CrmClient":
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    # ------------------------------------------------------------------ Redis

    @property
    def token_key(self) -> str:
        return f"crm:token:{self.corp_id}"

    def _login_lock_key(self) -> str:
        return f"crm:login:{self.corp_id}"

    def _rate_key(self) -> str:
        return f"crm:rate:{self.corp_id}"

    async def _get_redis(self) -> Redis:
        if self._redis is not None:
            return self._redis
        try:
            self._redis = await cache_service._get_redis()
        except Exception as e:  # pragma: no cover - 连接失败分支
            raise CrmConfigError("Redis 不可用，无法执行 CRM 请求") from e
        if self._redis is None:  # pragma: no cover - 防御
            raise CrmConfigError("Redis 不可用，无法执行 CRM 请求")
        return self._redis

    async def _rate_limit(self) -> None:
        redis = await self._get_redis()
        deadline = time.monotonic() + RATE_WAIT_TIMEOUT
        while True:
            try:
                acquired = await redis.set(self._rate_key(), "1", nx=True, px=RATE_LIMIT_MS)
            except Exception as e:
                raise CrmConfigError("Redis 不可用，无法执行 CRM 请求") from e
            if acquired:
                return
            if time.monotonic() >= deadline:
                raise CrmUpstreamError("CRM 请求排队超时，请稍后重试")
            await asyncio.sleep(0.2)

    # ------------------------------------------------------------------ 认证

    async def _get_cached_token(self) -> Optional[str]:
        redis = await self._get_redis()
        try:
            return await redis.get(self.token_key)
        except Exception as e:
            raise CrmConfigError("Redis 不可用，无法执行 CRM 请求") from e

    async def _invalidate_token(self, used_token: str) -> None:
        """只失效本次实际使用且仍相同的 token，避免误删其他 worker 刷新的结果"""
        redis = await self._get_redis()
        try:
            current = await redis.get(self.token_key)
            if current == used_token:
                await redis.delete(self.token_key)
        except Exception as e:
            logger.warning("CRM token 失效失败: %s", e)

    async def _login(self) -> str:
        redis = await self._get_redis()
        owner = uuid.uuid4().hex
        lock_key = self._login_lock_key()
        deadline = time.monotonic() + LOGIN_LOCK_WAIT_TIMEOUT

        while True:
            try:
                acquired = await redis.set(lock_key, owner, nx=True, px=LOGIN_LOCK_TTL_MS)
            except Exception as e:
                raise CrmConfigError("Redis 不可用，无法执行 CRM 请求") from e
            if acquired:
                break
            token = await self._get_cached_token()
            if token:
                return token
            if time.monotonic() >= deadline:
                raise CrmUpstreamError("CRM 登录排队超时，请稍后重试")
            await asyncio.sleep(0.2)

        try:
            # 双检：等锁期间可能已有其他 worker 完成登录
            token = await self._get_cached_token()
            if token:
                return token

            await self._rate_limit()
            assert self._http_client is not None
            resp = await self._http_client.post(
                f"{self.base_url}/api/v2/auth/login",
                json={
                    "device": "open_api",
                    "login": self.phone,
                    "password": self.password,
                    "corp_id": self.corp_id,
                },
                timeout=REQUEST_TIMEOUT,
            )
            try:
                data = self._parse_response(resp, "登录")
            except CrmUpstreamError as e:
                raise CrmAuthError("CRM 登录失败：账号或密码不正确") from e
            token = data.get("user_token")
            if not token:
                raise CrmAuthError("CRM 登录失败：响应缺少 user_token")
            if data.get("is_expired") is True:
                raise CrmAuthError("CRM 登录失败：账号已过期")
            returned_corp = data.get("corp_id")
            if returned_corp is not None and str(returned_corp) != self.corp_id:
                raise CrmAuthError("CRM 登录失败：企业ID与账号不匹配")

            try:
                await redis.set(self.token_key, token, ex=cache_service.ttl_for(TOKEN_TTL_PREFIX))
            except Exception as e:
                raise CrmConfigError("Redis 不可用，无法缓存 CRM token") from e
            return token
        finally:
            try:
                current = await redis.get(lock_key)
                if current == owner:
                    await redis.delete(lock_key)
            except Exception as e:  # pragma: no cover - 释放失败只影响 60s 后自动过期
                logger.warning("CRM 登录锁释放失败: %s", e)

    async def _get_token(self) -> str:
        token = await self._get_cached_token()
        if token:
            return token
        return await self._login()

    # ------------------------------------------------------------------ 请求

    @staticmethod
    def _parse_response(resp: httpx.Response, action: str) -> dict:
        """HTTP 200 但业务 code!=0 仍视为失败，不能当空列表成功"""
        try:
            payload = resp.json()
        except Exception as e:
            raise CrmUpstreamError(
                f"CRM {action}响应不是合法 JSON（HTTP {resp.status_code}）"
            ) from e

        code = payload.get("code") if isinstance(payload, dict) else None
        if resp.status_code >= 400:
            raise CrmUpstreamError(f"CRM {action}失败（HTTP {resp.status_code}, code={code}）")
        if code != 0:
            raise CrmUpstreamError(f"CRM {action}失败（业务 code={code}）")
        data = payload.get("data")
        if data is None:
            return {}
        if isinstance(data, list):
            return {"list": data}
        if not isinstance(data, dict):
            raise CrmUpstreamError(f"CRM {action}响应 data 结构异常")
        return data

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        *,
        retry_auth: bool = True,
    ) -> dict:
        token = await self._get_token()
        await self._rate_limit()
        assert self._http_client is not None
        headers = {
            "Authorization": f"Token token={token}, device=open_api, version_code=9.9.9",
        }
        try:
            resp = await self._http_client.request(
                method,
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as e:
            logger.warning("CRM 请求失败 path=%s error=%s", path, type(e).__name__)
            raise CrmUpstreamError(f"CRM 请求失败（{type(e).__name__}）") from e

        # token 失效：最多刷新并重放一次 GET
        business_code = None
        try:
            body = resp.json()
            if isinstance(body, dict):
                business_code = body.get("code")
        except Exception:
            business_code = None
        if retry_auth and (resp.status_code == 401 or business_code == 100401):
            await self._invalidate_token(token)
            return await self._request(method, path, params, retry_auth=False)

        if resp.status_code == 404:
            raise CrmNotFoundError(f"CRM 请求 {path} 返回 404")

        return self._parse_response(resp, f"请求 {path}")

    # ------------------------------------------------------------------ 分页

    @staticmethod
    def _extract_page(data: dict) -> tuple[list[dict], dict]:
        """兼容游离结构：list 可能在具名键（list/items/records/rows/results/
        customers/contracts/received_payments/data）；都没有时取唯一的数组值
        （上游各资源命名不统一，例如客户列表可能叫 customers）。

        meta 可能在 pagination/meta/page_info 或与 list 同级。
        无法识别就失败，不静默当空页。
        """
        items: Optional[list] = None
        for key in (
            "list",
            "items",
            "records",
            "rows",
            "results",
            "customers",
            "contracts",
            "received_payments",
            "data",
            "datas",
        ):
            value = data.get(key)
            if isinstance(value, list):
                items = value
                break
        if items is None:
            # 未知命名兜底：字典里恰好只有一个数组值时认作记录列表
            candidates = [value for value in data.values() if isinstance(value, list)]
            if len(candidates) == 1:
                items = candidates[0]
        if items is None:
            keys = ", ".join(sorted(data.keys())) or "空对象"
            raise CrmUpstreamError(f"CRM 分页响应缺少列表字段（data 键：{keys}）")

        meta: dict = {}
        for key in ("pagination", "meta", "page_info"):
            value = data.get(key)
            if isinstance(value, dict):
                meta = value
                break
        if not meta:
            meta = data
        return items, meta

    async def _iter_pages(self, path: str, params: Optional[dict] = None) -> AsyncIterator[dict]:
        page = 1
        seen: set[Any] = set()
        expected_total: Optional[int] = None

        while True:
            query = {**(params or {}), "page": page, "per_page": PAGE_SIZE}
            data = await self._request("GET", path, query)
            items, meta = self._extract_page(data)

            total_count = _as_int(meta.get("total_count"))
            if total_count is None:
                total_count = _as_int(data.get("total_count"))
            if total_count is not None:
                expected_total = total_count

            has_next = meta.get("has_next_page")
            if has_next is None:
                has_next = data.get("has_next_page")
            per_page = _as_int(meta.get("per_page")) or _as_int(data.get("per_page")) or PAGE_SIZE

            if not items:
                if expected_total is not None and len(seen) < expected_total:
                    raise CrmUpstreamError(
                        f"CRM 分页提前空页（已取 {len(seen)} / 声明 {expected_total}）"
                    )
                return

            page_ids = []
            new_count = 0
            for item in items:
                if not isinstance(item, dict):
                    raise CrmUpstreamError("CRM 分页返回了非对象记录")
                ext_id = _as_int(item.get("id"))
                if ext_id is None:
                    raise CrmUpstreamError("CRM 记录缺少 id")
                page_ids.append(ext_id)
                if ext_id not in seen:
                    seen.add(ext_id)
                    new_count += 1

            if new_count == 0:
                raise CrmUpstreamError("CRM 分页返回重复页，终止同步")

            for item in items:
                yield item

            if has_next is False:
                return
            if expected_total is not None and len(seen) >= expected_total:
                return
            if has_next is None and expected_total is None and len(items) < per_page:
                # 无元数据时以不满页作为最后一页
                return
            page += 1

    # ------------------------------------------------------------------ 只读接口

    async def get_customer_fields(self) -> dict:
        return await self._request("GET", "/api/v2/custom_fields/customer/by_group")

    async def get_payment_fields(self) -> dict:
        return await self._request("GET", "/api/v2/custom_fields/received_payment/by_group")

    async def iter_customers(self) -> AsyncIterator[dict]:
        async for item in self._iter_pages(
            "/api/v2/customers", {"sort": "created_at", "order": "asc"}
        ):
            yield item

    async def iter_contracts(self) -> AsyncIterator[dict]:
        """合同全量枚举（新签合同优先）

        顺序按 `created_at desc`：月度同步要扫完**全部**合同（不遗漏），但回款集中在
        近期合同上 —— 实测按 asc 扫 1100 个历史合同仍 `payment_count=0`（这些合同
        `received_payments_amount=0`），而 desc 的前 50 个里 36 个有回款。
        desc 让用户在同步早期就看到本月回款，且不改变全量语义。
        """
        async for item in self._iter_pages(
            "/api/v2/contracts", {"sort": "created_at", "order": "desc"}
        ):
            yield item

    async def iter_contract_payments(self, contract_id: int) -> AsyncIterator[dict]:
        async for item in self._iter_pages(f"/api/v2/contracts/{contract_id}/received_payments"):
            yield item

    async def iter_payments(self) -> AsyncIterator[dict]:
        """全量「已通过」回款（不逐合同枚举）

        `GET /api/v2/received_payments` 在 CRM 服务端抛 `no_method_error`
        （HTTP 200 + `code=500`，`original_message=undefined method ...`），上游 bug；
        `/filter_sort_group` 声明了 `receive_date` 筛选，但服务端**忽略**该参数
        （实测窄区间仍返回全量），所以这里只按 `approve_status=approved` 拉全量，
        由调用方按 `receive_date` 本地过滤当月。

        实测本租户 1536 条 / 16 页 ≈ 22s，而逐合同枚举 7118 个合同 ≈ 2.4h
        （限流 1.25s/请求）。列表项已含 contract_id/customer_id/receive_date/amount，
        但不含行业自定义字段，仍需对当月命中项调 `get_payment` 补详情。
        """
        async for item in self._iter_pages(
            "/api/v2/received_payments/list", {"approve_status": "approved"}
        ):
            yield item

    async def get_customer(self, customer_id: int) -> dict:
        return await self._request("GET", f"/api/v2/customers/{customer_id}")

    async def get_payment(self, contract_id: int, payment_id: int) -> dict:
        return await self._request(
            "GET", f"/api/v2/contracts/{contract_id}/received_payments/{payment_id}"
        )

    async def probe(self) -> dict:
        """凭据自检（只读、不落镜像）：登录 + 客户列表首页 1 条

        语义分层：
        - 登录失败（账号/密码/企业ID不对）→ 抛 CrmAuthError，验证整体不通过；
        - 登录成功但客户列表读不出来（分页结构变化、权限不足等）→ 降级为
          `warning`：凭据本身有效，不能让分页契约问题阻断管理员保存配置。

        返回值只暴露计数与告警文案，用于页面上「验证账号密码」的即时反馈；
        不写入 crm_customers / crm_payments，也不触发任何充值。
        """
        if not self.corp_id or not self.phone or not self.password:
            raise CrmConfigError("企业ID、登录手机号、登录密码必须全部填写")
        # 先显式登录，把「凭据错误」与「列表读取失败」区分开
        await self._get_token()
        try:
            data = await self._request("GET", "/api/v2/customers", {"page": 1, "per_page": 1})
            _, meta = self._extract_page(data)
            total = _as_int(meta.get("total_count"))
            if total is None:
                total = _as_int(data.get("total_count"))
            return {"customer_total": total, "corp_id": self.corp_id}
        except CrmAuthError:
            raise
        except CrmUpstreamError as e:
            logger.warning("CRM 客户列表读取失败（登录凭据有效）: %s", e)
            return {"customer_total": None, "corp_id": self.corp_id, "warning": str(e)}


def is_crm_enabled() -> bool:
    """开关 + 凭据完整才允许外部访问（页面保存的配置优先于环境变量）"""
    from .crm_config import get_crm_config

    return get_crm_config().active


async def probe_credentials(
    *,
    base_url: str | None = None,
    corp_id: str | None = None,
    phone: str | None = None,
    password: str | None = None,
) -> dict:
    """用指定的（未保存的）凭据做一次只读自检"""
    async with CrmClient(
        base_url=base_url, corp_id=corp_id, phone=phone, password=password
    ) as client:
        return await client.probe()
