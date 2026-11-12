"""CRM 回款同步、客户推荐与原子充值导入

边界（见 docs/specs/2026-11-11-crm-recharge-management-plan.md）：
- 同步只写 crm_customers / crm_payments / crm_sync_runs，绝不触碰余额或充值记录。
- 唯一的资金写入点是 `import_payment`（调用 BalanceService.recharge 的事务内记账）。
- 读 HTTP 与写 PG 分离：每个镜像 upsert / 进度推进 / 状态转换都用独立短事务，
  HTTP 请求不在事务内。
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import CustomerBalance, RechargeRecord
from ..models.crm_recharge import CrmCustomer, CrmPayment, CrmSyncRun
from ..models.customers import Customer
from ..repository import BalanceRepository
from ..utils.audit_helpers import create_audit_entry
from ..utils.timezone import cst_now
from .billing import BalanceService
from .crm_client import (
    CrmClient,
    CrmError,
    CrmNotFoundError,
    CrmUpstreamError,
)
from .package_balance import batch_query_package_info

logger = logging.getLogger(__name__)

# 回款级行业分类字段名（官方 by_group 元数据实测值）
INDUSTRY_FIELD_NAME = "text_asset_3565dc"
INDUSTRY_ROOT_LABELS = ("房产经纪", "新房开发")
APPROVED_STATUS = "approved"

NUMERIC_12_2_MAX = Decimal("9999999999.99")
CST_OFFSET = timedelta(hours=8)

RECOMMEND_THRESHOLD = 0.35
RECOMMEND_LIMIT = 10
STALE_HEARTBEAT_MINUTES = 2


class CrmContractError(CrmError):
    """CRM 元数据契约变化（行业字段/根缺失或重名）"""

    is_config_error = False


def _cst_naive() -> datetime:
    """CRM 镜像表的时间列是 `timestamp without time zone`（CST 墙钟）。

    直接写 aware datetime 会让 asyncpg 抛「can't subtract offset-naive and
    offset-aware datetimes」，启动恢复任务与心跳全部失败。此处统一剥掉时区标注，
    保留 CST 墙钟数值。
    """
    return cst_now().replace(tzinfo=None)


# ---------------------------------------------------------------------------
# 纯函数：名称规范化、推荐评分、行业路径
# ---------------------------------------------------------------------------


def normalize_crm_name(value: str) -> str:
    """NFKC → casefold → 移除 Unicode 空白与标点，保留数字/汉字/字母

    不擅自剥除地域或公司后缀（那会破坏「上海XX」与「XX」的区分度）。
    """
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())


def score_crm_candidate(query: str, candidate: str) -> float:
    """候选匹配分：完全相等 1.0；包含 0.8~0.99；其余 difflib*0.79"""
    q = normalize_crm_name(query)
    c = normalize_crm_name(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    short, long = (q, c) if len(q) <= len(c) else (c, q)
    if short and short in long:
        return 0.8 + 0.19 * (len(short) / len(long))
    return difflib.SequenceMatcher(None, q, c, autojunk=False).ratio() * 0.79


def _walk_dicts(node: Any) -> list[dict]:
    """深度遍历收集所有 dict 节点（用于宽松解析上游元数据结构）

    不能按「已知键名白名单」下钻：上游的真实结构是
    `custom_field_groups[].custom_fields[].input_field_options.collection_options[]`，
    早期的 `children/options/sub_fields/values/items/list` 白名单拿不到任何字段节点，
    导致 `resolve_industry_paths` 误报「CRM 回款字段缺少行业分类」→ 同步必然 failed。
    元数据只是只读结构，全量遍历不会引入副作用，命中与否由 label/name 精确匹配决定。
    """
    out: list[dict] = []
    stack: list[Any] = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            out.append(cur)
            stack.extend(v for v in cur.values() if isinstance(v, (dict, list)))
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def _node_label(node: dict) -> str:
    for key in ("label", "title", "text", "display"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _collect_option_values(node: Any, out: set[str]) -> None:
    if isinstance(node, dict):
        for key in ("value", "id"):
            value = node.get(key)
            if isinstance(value, str) and value:
                out.add(value)
        for child in node.values():
            if isinstance(child, (dict, list)):
                _collect_option_values(child, out)
    elif isinstance(node, list):
        for item in node:
            _collect_option_values(item, out)


def resolve_industry_paths(metadata: dict) -> set[str]:
    """从回款字段元数据解析允许的行业根/后代值集合

    契约：label='行业分类' 的字段名必须等于 `text_asset_3565dc`；两个根标签
    必须存在。根缺失/重名/字段不可见 → 抛 CrmContractError（= sync failed），
    不改用客户 industry 猜测。
    """
    nodes = _walk_dicts(metadata)
    field_nodes = [n for n in nodes if _node_label(n) == "行业分类"]
    if not field_nodes:
        # 带上实际遍历结果，区分「上游没给」与「解析器看不见」：前者改上游/权限，
        # 后者是本地遍历逻辑问题，两者的处置完全不同。
        if isinstance(metadata, dict):
            top_keys = ", ".join(sorted(metadata.keys())[:8]) or "空对象"
        else:
            top_keys = type(metadata).__name__
        raise CrmContractError(
            "CRM 回款字段缺少「行业分类」，无法筛选可导入回款"
            f"（元数据顶层键：{top_keys}；遍历节点数：{len(nodes)}）"
        )
    names = {str(n.get("name") or "") for n in field_nodes}
    names.discard("")
    if names != {INDUSTRY_FIELD_NAME}:
        raise CrmContractError("CRM 回款「行业分类」字段名与配置不一致")

    allowed: set[str] = set()
    for label in INDUSTRY_ROOT_LABELS:
        roots = [n for n in nodes if _node_label(n) == label]
        if not roots:
            raise CrmContractError(f"CRM 回款字段缺少行业根「{label}」")
        for root in roots:
            _collect_option_values(root, allowed)
    if not allowed:
        raise CrmContractError("CRM 回款行业根没有可选值")
    return allowed


def parse_industry_path(value: object) -> list[str]:
    """解析行业路径：字符串按 `/` 分段；数组按元素展开；其他结构返回空"""
    if isinstance(value, str):
        return [seg.strip() for seg in value.split("/") if seg.strip()]
    if isinstance(value, (list, tuple)):
        segments: list[str] = []
        for item in value:
            segments.extend(parse_industry_path(item))
        return segments
    if isinstance(value, dict):
        for key in ("value", "path", "id"):
            if key in value:
                return parse_industry_path(value[key])
    return []


def _industry_allowed(value: object, allowed_paths: set[str]) -> bool:
    segments = parse_industry_path(value)
    if not segments:
        return False
    return segments[0] in allowed_paths


# ---------------------------------------------------------------------------
# 解析辅助
# ---------------------------------------------------------------------------


def _parse_amount(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite():
        return None
    if amount != amount.quantize(Decimal("0.01")):
        return None
    return amount


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _month_bounds(month: date) -> tuple[date, date]:
    start = month.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _extract_industry_value(details: dict) -> Any:
    for key in (INDUSTRY_FIELD_NAME, "industry_path", "industry"):
        if key in details:
            return details[key]
    custom = details.get("custom_fields")
    if isinstance(custom, dict):
        return custom.get(INDUSTRY_FIELD_NAME)
    if isinstance(custom, list):
        for item in custom:
            if isinstance(item, dict) and item.get("name") == INDUSTRY_FIELD_NAME:
                return item.get("value")
    return None


def _extract_industry_label(details: dict) -> Optional[str]:
    value = details.get(f"{INDUSTRY_FIELD_NAME}_display")
    if isinstance(value, str) and value:
        return value
    value = details.get("industry_label")
    return value if isinstance(value, str) and value else None


def _extract_amount(details: dict) -> Optional[Decimal]:
    for key in ("amount", "receive_amount", "received_amount"):
        if key in details:
            return _parse_amount(details.get(key))
    return None


SNAPSHOT_AMOUNT_QUANTUM = Decimal("0.01")


def _normalize_snapshot(snapshot: Optional[dict]) -> Optional[dict]:
    """快照规范化：金额统一两位小数

    上游详情金额是 `50000.0`，镜像列是 NUMERIC(12,2) 读回 `50000.00`——
    直接比较字符串会让**每一次**导入都报「CRM回款已变更」（必现，非偶发）。
    """
    if not snapshot:
        return snapshot
    normalized = dict(snapshot)
    amount = normalized.get("amount")
    if amount is not None:
        try:
            normalized["amount"] = str(Decimal(str(amount)).quantize(SNAPSHOT_AMOUNT_QUANTUM))
        except (InvalidOperation, ValueError):
            pass
    return normalized


def _snapshots_differ(old: Optional[dict], new: Optional[dict]) -> bool:
    """比较两份快照；旧快照缺失视为「无基线」，不判定变更"""
    if not old:
        return False
    return _normalize_snapshot(old) != _normalize_snapshot(new)


def _business_snapshot(
    *,
    customer_external_id: int,
    contract_external_id: int,
    amount: Optional[Decimal],
    receive_date: Optional[date],
    industry_path: Optional[str],
    approve_status: str,
) -> dict:
    """源值白名单快照（同步比较与导入记录共用同一构造，避免两处漂移）"""
    snapshot = {
        "customer_external_id": customer_external_id,
        "contract_external_id": contract_external_id,
        "amount": str(amount) if amount is not None else None,
        "receive_date": receive_date.isoformat() if receive_date else None,
        "industry_path": industry_path,
        "approve_status": approve_status,
    }
    return _normalize_snapshot(snapshot) or snapshot


# ---------------------------------------------------------------------------
# 服务
# ---------------------------------------------------------------------------


class CrmRechargeService:
    """CRM 回款镜像查询 + 同步编排 + 原子导入"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ 同步 run

    async def create_sync_run(
        self, month: date, trigger: str, operator_id: Optional[int], corp_id: str
    ) -> CrmSyncRun:
        """调用方负责事务；先恢复心跳超时的活跃 run，再插入 pending"""
        now = _cst_naive()
        stale_before = now - timedelta(minutes=STALE_HEARTBEAT_MINUTES)
        await self.db.execute(
            update(CrmSyncRun)
            .where(
                CrmSyncRun.corp_id == corp_id,
                CrmSyncRun.status.in_(("pending", "running")),
                CrmSyncRun.heartbeat_at < stale_before,
            )
            .values(
                status="failed",
                error_message="同步进程中断，请手动重新同步",
                finished_at=now,
            )
        )
        run = CrmSyncRun(
            corp_id=corp_id,
            month=month.replace(day=1),
            trigger=trigger,
            operator_id=operator_id,
            status="pending",
            phase="customers",
            heartbeat_at=now,
        )
        self.db.add(run)
        await self.db.flush()
        return run

    @staticmethod
    async def recover_stale_sync_runs(session_factory) -> int:
        """启动钩子：只恢复心跳超过 2 分钟的旧任务，不动刚启动的任务"""
        now = _cst_naive()
        async with session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    update(CrmSyncRun)
                    .where(
                        CrmSyncRun.status.in_(("pending", "running")),
                        CrmSyncRun.heartbeat_at < now - timedelta(minutes=STALE_HEARTBEAT_MINUTES),
                    )
                    .values(
                        status="failed",
                        error_message="同步进程中断，请手动重新同步",
                        finished_at=now,
                    )
                )
                return result.rowcount or 0

    @staticmethod
    async def execute_sync_run(run_id: int, session_factory) -> None:
        """后台执行入口：原子领取 → 心跳 → 全量枚举 → 终态

        `client_factory` 未显式传入时使用生产 CrmClient；测试可 monkeypatch
        `CrmRechargeService._client_factory`。
        """
        claimed = await _claim_run(session_factory, run_id)
        if claimed is None:
            logger.info("CRM 同步 run=%s 未被领取（已由其他 worker 执行）", run_id)
            return

        corp_id, month = claimed
        stop = asyncio.Event()
        heartbeat = asyncio.create_task(_heartbeat_loop(run_id, session_factory, stop))

        try:
            async with CrmRechargeService._client_factory() as client:
                counts = await _sync_month(client, run_id, session_factory, corp_id, month)
        except CrmError as e:
            logger.warning("CRM 同步失败 run=%s: %s", run_id, e)
            await _finish_run(session_factory, run_id, "failed", error_message=str(e)[:500])
        except Exception as e:  # pragma: no cover - 防御性兜底
            logger.exception("CRM 同步异常 run=%s", run_id)
            await _finish_run(
                session_factory,
                run_id,
                "failed",
                error_message=f"同步异常：{type(e).__name__}",
            )
        else:
            await _finish_run(session_factory, run_id, "succeeded", phase="completed", **counts)
        finally:
            stop.set()
            await heartbeat

    @staticmethod
    def _client_factory():
        return CrmClient()

    # ------------------------------------------------------------------ 列表/详情

    async def list_payments(
        self,
        *,
        corp_id: str,
        month: Optional[date],
        keyword: Optional[str],
        status: str,
        page: int,
        page_size: int,
        user_id: int,
        has_view_all: bool,
        bound_customer_id: Optional[int] = None,
    ) -> tuple[list[dict], int]:
        month_start = month.replace(day=1) if month else None
        month_end = _month_bounds(month_start)[1] if month_start else None

        imported_subq = (
            select(
                RechargeRecord.crm_payment_id.label("crm_payment_id"),
                RechargeRecord.id.label("recharge_record_id"),
                RechargeRecord.real_amount.label("real_amount"),
                RechargeRecord.bonus_amount.label("bonus_amount"),
                RechargeRecord.customer_id.label("recharge_customer_id"),
                RechargeRecord.recharge_date.label("recharge_date"),
                RechargeRecord.created_at.label("recharge_created_at"),
                RechargeRecord.operator_id.label("recharge_operator_id"),
            )
            .where(RechargeRecord.crm_payment_id.is_not(None))
            .subquery()
        )

        stmt = (
            select(
                CrmPayment,
                Customer,
                imported_subq.c.recharge_record_id,
                imported_subq.c.real_amount,
                imported_subq.c.bonus_amount,
                imported_subq.c.recharge_customer_id,
                imported_subq.c.recharge_date,
                imported_subq.c.recharge_created_at,
                imported_subq.c.recharge_operator_id,
            )
            .outerjoin(
                Customer,
                (Customer.crm_customer_id == CrmPayment.crm_customer_id)
                & (Customer.deleted_at.is_(None)),
            )
            .outerjoin(imported_subq, imported_subq.c.crm_payment_id == CrmPayment.id)
            .where(CrmPayment.corp_id == corp_id, CrmPayment.deleted_at.is_(None))
        )
        if month_start and month_end:
            stmt = stmt.where(
                CrmPayment.receive_date >= month_start, CrmPayment.receive_date < month_end
            )

        if not has_view_all:
            # 未绑定 / 他人客户的回款不可见；已导入行按充值归属客户判定
            stmt = stmt.where(
                or_(
                    Customer.id.is_not(None)
                    & ((Customer.manager_id == user_id) | (Customer.sales_manager_id == user_id)),
                    imported_subq.c.recharge_customer_id.in_(
                        select(Customer.id).where(
                            Customer.deleted_at.is_(None),
                            or_(
                                Customer.manager_id == user_id,
                                Customer.sales_manager_id == user_id,
                            ),
                        )
                    ),
                )
            )

        if bound_customer_id is not None:
            stmt = stmt.where(Customer.id == bound_customer_id)

        if keyword:
            kw = keyword.strip()
            like = f"%{kw}%"
            numeric = int(kw) if kw.isdigit() else None
            conditions: list[Any] = [
                CrmPayment.customer_name.ilike(like),
                CrmPayment.contract_title.ilike(like),
                Customer.name.ilike(like),
            ]
            if numeric is not None:
                conditions.append(CrmPayment.external_id == numeric)
            stmt = stmt.where(or_(*conditions))

        # 状态过滤依赖导入记录存在性 + eligible；在 SQL 层用 CASE 太重，
        # 这里先取满足基础条件的行，再在内存中做状态判定与分页（单月量级可接受）。
        rows = (
            await self.db.execute(
                stmt.order_by(CrmPayment.receive_date.desc(), CrmPayment.id.desc())
            )
        ).all()

        items: list[dict] = []
        for row in rows:
            payment, customer = row[0], row[1]
            # 导入记录是多列子查询：SQLAlchemy Row 会按列摊平，不能按 3 元解包
            imported = None
            if row[2] is not None:
                imported = SimpleNamespace(
                    recharge_record_id=row[2],
                    real_amount=row[3],
                    bonus_amount=row[4],
                    recharge_customer_id=row[5],
                    recharge_date=row[6],
                    recharge_created_at=row[7],
                    recharge_operator_id=row[8],
                )
            item = self._serialize_payment(payment, customer, imported)
            if status != "all" and item["status"] != status:
                continue
            items.append(item)

        total = len(items)
        offset = (page - 1) * page_size
        return items[offset : offset + page_size], total

    @staticmethod
    def _serialize_payment(payment: CrmPayment, customer: Optional[Customer], imported) -> dict:
        imported = imported if imported is not None else None
        if imported is not None:
            status = "imported"
        elif (
            payment.eligible and payment.crm_customer_id is not None and not payment.source_changed
        ):
            status = "pending"
        else:
            status = "blocked"

        blocked_reason = payment.blocked_reason
        if imported is None:
            if payment.crm_customer_id is None:
                blocked_reason = blocked_reason or "CRM客户不可见或已删除"
            elif customer is None:
                blocked_reason = blocked_reason or "回款尚未绑定中台客户"
            elif payment.source_changed:
                blocked_reason = "CRM回款已变更，请重新核对"

        data = {
            "id": payment.id,
            "external_id": payment.external_id,
            "crm_customer_id": payment.crm_customer_id,
            "crm_customer_name": payment.customer_name,
            "contract_external_id": payment.contract_external_id,
            "contract_title": payment.contract_title,
            "amount": str(payment.amount) if payment.amount is not None else None,
            "receive_date": payment.receive_date.isoformat() if payment.receive_date else None,
            "approve_status": payment.approve_status,
            "industry_path": payment.industry_path,
            "industry_label": payment.industry_label,
            "eligible": payment.eligible,
            "blocked_reason": blocked_reason,
            "source_changed": payment.source_changed,
            "status": status,
            "bound_customer_id": customer.id if customer else None,
            "bound_customer_name": customer.name if customer else None,
            "bound_company_id": customer.company_id if customer else None,
            "last_seen_at": payment.last_seen_at.isoformat() if payment.last_seen_at else None,
            "recharge_record_id": imported.recharge_record_id if imported else None,
            "real_amount": str(imported.real_amount)
            if imported and imported.real_amount is not None
            else None,
            "bonus_amount": str(imported.bonus_amount)
            if imported and imported.bonus_amount is not None
            else None,
            "total_amount": (
                str(
                    (imported.real_amount or Decimal("0")) + (imported.bonus_amount or Decimal("0"))
                )
                if imported
                else None
            ),
            "recharge_date": imported.recharge_date.isoformat()
            if imported and imported.recharge_date
            else None,
            "recharge_created_at": (
                imported.recharge_created_at.isoformat()
                if imported and imported.recharge_created_at
                else None
            ),
        }
        return data

    async def get_payment_detail(self, payment_id: int, corp_id: str) -> Optional[dict]:
        payment = await self.db.scalar(
            select(CrmPayment).where(
                CrmPayment.id == payment_id,
                CrmPayment.corp_id == corp_id,
                CrmPayment.deleted_at.is_(None),
            )
        )
        if payment is None:
            return None
        customer = await self.db.scalar(
            select(Customer).where(
                Customer.crm_customer_id == payment.crm_customer_id,
                Customer.deleted_at.is_(None),
            )
        )
        imported = await self.db.scalar(
            select(RechargeRecord).where(RechargeRecord.crm_payment_id == payment.id)
        )
        return self._serialize_payment(payment, customer, imported)

    async def latest_success_at(self, corp_id: str, month: date) -> Optional[datetime]:
        return await self.db.scalar(
            select(func.max(CrmSyncRun.finished_at)).where(
                CrmSyncRun.corp_id == corp_id,
                CrmSyncRun.month == month.replace(day=1),
                CrmSyncRun.status == "succeeded",
            )
        )


# ---------------------------------------------------------------------------
# 同步执行辅助（短事务 + 心跳）
# ---------------------------------------------------------------------------


class _LostOwnership(Exception):
    """run 已被其他 worker 接管或标记失败，当前执行必须终止"""


async def _claim_run(session_factory, run_id: int) -> Optional[tuple[str, date]]:
    async with session_factory() as session:
        async with session.begin():
            now = _cst_naive()
            result = await session.execute(
                update(CrmSyncRun)
                .where(CrmSyncRun.id == run_id, CrmSyncRun.status == "pending")
                .values(status="running", started_at=now, heartbeat_at=now)
                .returning(CrmSyncRun.corp_id, CrmSyncRun.month)
            )
            row = result.first()
            return (row[0], row[1]) if row else None


async def _heartbeat_loop(run_id: int, session_factory, stop: asyncio.Event) -> None:
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
            return
        except asyncio.TimeoutError:
            try:
                async with session_factory() as session:
                    async with session.begin():
                        await session.execute(
                            update(CrmSyncRun)
                            .where(CrmSyncRun.id == run_id, CrmSyncRun.status == "running")
                            .values(heartbeat_at=_cst_naive())
                        )
            except Exception as e:  # pragma: no cover - 心跳失败不终止主流程
                logger.warning("CRM 同步心跳更新失败 run=%s: %s", run_id, e)


async def _progress(run_id: int, session_factory, **values) -> None:
    """推进进度；不再处于 running 说明失去所有权 → 中止"""
    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(
                update(CrmSyncRun)
                .where(CrmSyncRun.id == run_id, CrmSyncRun.status == "running")
                .values(heartbeat_at=_cst_naive(), **values)
            )
            if not result.rowcount:
                raise _LostOwnership()


async def _finish_run(
    session_factory,
    run_id: int,
    status: str,
    *,
    phase: Optional[str] = None,
    error_message: Optional[str] = None,
    **counts,
) -> None:
    values = {
        "status": status,
        "finished_at": _cst_naive(),
        "heartbeat_at": _cst_naive(),
        **counts,
    }
    if phase:
        values["phase"] = phase
    if error_message is not None:
        values["error_message"] = error_message
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                update(CrmSyncRun).where(CrmSyncRun.id == run_id).values(**values)
            )


async def _upsert_customers(session_factory, corp_id: str, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = pg_insert(CrmCustomer).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_crm_customers_corp_external",
        set_={
            "name": stmt.excluded.name,
            "normalized_name": stmt.excluded.normalized_name,
            "owner_name": stmt.excluded.owner_name,
            "last_seen_at": stmt.excluded.last_seen_at,
            "deleted_at": None,
            "updated_at": func.now(),
        },
    )
    async with session_factory() as session:
        async with session.begin():
            await session.execute(stmt)


async def _upsert_payment(session_factory, values: dict) -> None:
    stmt = pg_insert(CrmPayment).values(**values)
    update_cols = {
        key: getattr(stmt.excluded, key)
        for key in values
        if key not in ("corp_id", "external_id", "imported_snapshot")
    }
    update_cols["updated_at"] = func.now()
    stmt = stmt.on_conflict_do_update(constraint="uq_crm_payments_corp_external", set_=update_cols)
    async with session_factory() as session:
        async with session.begin():
            await session.execute(stmt)


async def _fetch_customer_map(session_factory, corp_id: str) -> dict[int, int]:
    async with session_factory() as session:
        rows = await session.execute(
            select(CrmCustomer.external_id, CrmCustomer.id).where(
                CrmCustomer.corp_id == corp_id, CrmCustomer.deleted_at.is_(None)
            )
        )
        return {int(ext): int(local) for ext, local in rows.all()}


async def _load_month_payments(
    session_factory, corp_id: str, month_start: date, month_end: date
) -> dict[int, dict]:
    async with session_factory() as session:
        rows = await session.execute(
            select(
                CrmPayment.external_id,
                CrmPayment.contract_external_id,
                CrmPayment.imported_snapshot,
            ).where(
                CrmPayment.corp_id == corp_id,
                CrmPayment.deleted_at.is_(None),
                CrmPayment.receive_date >= month_start,
                CrmPayment.receive_date < month_end,
            )
        )
        return {
            int(ext): {
                "external_id": int(ext),
                "contract_external_id": int(contract_ext),
                "imported_snapshot": snapshot,
            }
            for ext, contract_ext, snapshot in rows.all()
        }


async def _load_imported_ids(session_factory) -> set[int]:
    async with session_factory() as session:
        rows = await session.scalars(
            select(RechargeRecord.crm_payment_id).where(RechargeRecord.crm_payment_id.is_not(None))
        )
        return {int(pid) for pid in rows.all() if pid is not None}


async def _demote_payments(session_factory, corp_id: str, external_ids: list[int]) -> None:
    if not external_ids:
        return
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                update(CrmPayment)
                .where(
                    CrmPayment.corp_id == corp_id,
                    CrmPayment.external_id.in_(external_ids),
                )
                .values(
                    eligible=False,
                    blocked_reason="CRM审批未通过或回款日期不在同步月份",
                    updated_at=_cst_naive(),
                )
            )


def _as_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_id(details: dict, *keys: str) -> Optional[int]:
    for key in keys:
        value = details.get(key)
        if isinstance(value, dict):
            value = value.get("id")
        parsed = _as_int(value)
        if parsed is not None:
            return parsed
    return None


def _evaluate_payment(
    *,
    details: dict,
    fallback_date: Optional[date],
    fallback_status: str,
    allowed_paths: set[str],
    month_start: date,
    month_end: date,
    customer_map: dict[int, int],
    contract_external_id: int,
) -> dict:
    """把回款详情解析为镜像写入值 + 快照（同步与复核共用）"""
    amount = _extract_amount(details)
    receive_date = _parse_date(details.get("receive_date")) or fallback_date
    approve_status = str(details.get("approve_status") or fallback_status)

    industry_value = _extract_industry_value(details)
    segments = parse_industry_path(industry_value)
    industry_path = "/".join(segments) if segments else None
    industry_label = _extract_industry_label(details)

    customer_external_id = _extract_id(details, "customer_id", "customer") or 0
    contract_id = _extract_id(details, "contract_id", "contract") or contract_external_id

    reasons: list[str] = []
    if approve_status != APPROVED_STATUS:
        reasons.append("CRM审批未通过")
    if receive_date is None or not (month_start <= receive_date < month_end):
        reasons.append("回款日期不在同步月份")
    if amount is None or amount <= 0:
        reasons.append("回款金额无效")
    elif amount > NUMERIC_12_2_MAX:
        reasons.append("回款金额超出可入账上限")
    industry_ok = _industry_allowed(industry_value, allowed_paths)
    if not industry_ok:
        reasons.append("行业分类不在允许范围")

    eligible = not reasons
    snapshot = _business_snapshot(
        customer_external_id=customer_external_id,
        contract_external_id=contract_id,
        amount=amount,
        receive_date=receive_date,
        industry_path=industry_path,
        approve_status=approve_status,
    )
    values = {
        "crm_customer_id": customer_map.get(customer_external_id),
        "contract_external_id": contract_id,
        "contract_title": str(details.get("contract_title") or "")[:255] or None,
        "customer_external_id": customer_external_id,
        "customer_name": str(details.get("customer_name") or "")[:255],
        "amount": amount,
        "receive_date": receive_date,
        "approve_status": approve_status[:32],
        "industry_path": industry_path,
        "industry_label": industry_label,
        "source_updated_at": (
            str(details.get("updated_at"))[:64] if details.get("updated_at") else None
        ),
        "eligible": eligible,
        "blocked_reason": "；".join(reasons) or None,
        "last_seen_at": _cst_naive(),
    }
    return {
        "values": values,
        "snapshot": snapshot,
        "eligible": eligible,
        "industry_ok": industry_ok,
    }


def _extract_owner_name(customer: dict) -> Optional[str]:
    """客户负责人姓名

    上游 `GET /api/v2/customers` 实测字段是 `user_name`（同时有 `user_id`、
    `assist_users[]` 协办人），**没有** `owner_name` / `owner.name`
    （5032 个客户曾因此全部落到空值，绑定页负责人显示「-」）。
    这里优先 `user_name`，并保留旧假设的兜底，避免上游换回旧字段时静默变空。
    """
    for key in ("user_name", "owner_name"):
        value = customer.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    owner = customer.get("owner")
    if isinstance(owner, dict):
        value = owner.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def _sync_month(
    client: CrmClient, run_id: int, session_factory, corp_id: str, month: date
) -> dict:
    month_start, month_end = _month_bounds(month)

    payment_fields = await client.get_payment_fields()
    allowed_paths = resolve_industry_paths(payment_fields)

    # ---- 客户全量 ----
    await _progress(run_id, session_factory, phase="customers")
    customer_count = 0
    owner_count = 0
    batch: list[dict] = []
    async for customer in client.iter_customers():
        external_id = _as_int(customer.get("id"))
        if external_id is None:
            raise CrmUpstreamError("CRM 客户记录缺少 id")
        name = str(customer.get("name") or "")
        owner_name = _extract_owner_name(customer)
        if owner_name:
            owner_count += 1
        batch.append(
            {
                "corp_id": corp_id,
                "external_id": external_id,
                "name": name[:255],
                "normalized_name": normalize_crm_name(name)[:255],
                "owner_name": owner_name[:255] if owner_name else None,
                "last_seen_at": _cst_naive(),
            }
        )
        if len(batch) >= 200:
            await _upsert_customers(session_factory, corp_id, batch)
            customer_count += len(batch)
            batch = []
            await _progress(run_id, session_factory, customer_count=customer_count)
    if batch:
        await _upsert_customers(session_factory, corp_id, batch)
        customer_count += len(batch)

    if customer_count and not owner_count:
        # 字段映射错误在运行时唯一的证据是「填充率为 0」：同步仍会 succeeded，
        # 页面负责人列会长期显示「-」。留一条可检索的告警，避免再静默一个月。
        logger.warning(
            "CRM 客户负责人姓名全部为空（%s 个客户）：核对上游字段名，实测为 user_name",
            customer_count,
        )

    customer_map = await _fetch_customer_map(session_factory, corp_id)
    await _progress(run_id, session_factory, customer_count=customer_count)

    # ---- 回款全量：优先「全局回款列表」，上游不可用时回退逐合同枚举 ----
    try:
        return {
            "customer_count": customer_count,
            **await _scan_via_payment_list(
                client=client,
                run_id=run_id,
                session_factory=session_factory,
                corp_id=corp_id,
                month_start=month_start,
                month_end=month_end,
                allowed_paths=allowed_paths,
                customer_map=customer_map,
            ),
        }
    except CrmUpstreamError as exc:
        logger.warning("CRM 全局回款列表不可用（%s），回退逐合同枚举（7118 个合同约 2.4h）", exc)
        await _progress(run_id, session_factory, phase="contracts", scanned_payment_count=0)

    existing = await _load_month_payments(session_factory, corp_id, month_start, month_end)
    imported_ids = await _load_imported_ids(session_factory)
    seen: set[int] = set()
    demote_batch: list[int] = []
    out_of_scope: list[int] = []
    contract_count = 0
    payment_count = 0
    eligible_count = 0

    async for contract in client.iter_contracts():
        contract_id = _as_int(contract.get("id"))
        if contract_id is None:
            raise CrmUpstreamError("CRM 合同记录缺少 id")
        contract_count += 1
        contract_title = str(contract.get("title") or contract.get("name") or "")

        async for item in client.iter_contract_payments(contract_id):
            payment_id = _as_int(item.get("id"))
            if payment_id is None:
                raise CrmUpstreamError("CRM 回款记录缺少 id")
            if payment_id in seen:
                continue
            seen.add(payment_id)

            receive_date = _parse_date(item.get("receive_date"))
            approve_status = str(item.get("approve_status") or "")
            in_month = receive_date is not None and month_start <= receive_date < month_end
            if not in_month or approve_status != APPROVED_STATUS:
                if payment_id in existing:
                    demote_batch.append(payment_id)
                continue

            details = await client.get_payment(contract_id, payment_id)
            resolved_id = _as_int(details.get("id"))
            if resolved_id is not None and resolved_id != payment_id:
                raise CrmUpstreamError("CRM 回款详情ID与列表不一致")
            if not details.get("contract_title"):
                details["contract_title"] = contract_title

            evaluated = _evaluate_payment(
                details=details,
                fallback_date=receive_date,
                fallback_status=approve_status,
                allowed_paths=allowed_paths,
                month_start=month_start,
                month_end=month_end,
                customer_map=customer_map,
                contract_external_id=contract_id,
            )
            if not evaluated["industry_ok"]:
                # 业务口径：只镜像「房产经纪 / 新房开发」类别（含子级），其他行业不入库、不保留
                out_of_scope.append(payment_id)
                continue
            await _write_evaluated_payment(
                session_factory, corp_id, payment_id, evaluated, existing
            )
            payment_count += 1
            if evaluated["eligible"]:
                eligible_count += 1

        if demote_batch and contract_count % 50 == 0:
            await _demote_payments(session_factory, corp_id, demote_batch)
            demote_batch = []
        if contract_count % 50 == 0:
            await _progress(
                run_id,
                session_factory,
                contract_count=contract_count,
                scanned_contract_count=contract_count,
                payment_count=payment_count,
                eligible_count=eligible_count,
            )

    if demote_batch:
        await _demote_payments(session_factory, corp_id, demote_batch)

    # ---- 本次未再见到的既有镜像：复核，不因一次未列出就认定删除 ----
    await _recheck_missing_payments(
        client=client,
        session_factory=session_factory,
        corp_id=corp_id,
        existing=existing,
        seen=seen,
        allowed_paths=allowed_paths,
        month_start=month_start,
        month_end=month_end,
        customer_map=customer_map,
        imported_ids=imported_ids,
    )
    if out_of_scope:
        await _delete_out_of_scope_payments(session_factory, corp_id, out_of_scope, imported_ids)

    return {
        "customer_count": customer_count,
        "contract_count": contract_count,
        "scanned_contract_count": contract_count,
        "payment_count": payment_count,
        "eligible_count": eligible_count,
    }


async def _scan_via_payment_list(
    *,
    client: CrmClient,
    run_id: int,
    session_factory,
    corp_id: str,
    month_start: date,
    month_end: date,
    allowed_paths: set[str],
    customer_map: dict[int, int],
) -> dict:
    """全局回款列表路径：拉全量 approved 回款，本地按当月过滤

    上游 `receive_date` 筛选参数被服务端忽略，只能本地过滤；列表项不含行业
    自定义字段，故仅对当月命中项调详情。实测 1536 条 / 16 页 ≈ 22s，
    相比逐合同枚举（7118 合同 × 1.25s ≈ 2.4h）快两个数量级。
    """
    await _progress(run_id, session_factory, phase="payments")

    scanned = 0
    in_month: dict[int, dict] = {}
    async for item in client.iter_payments():
        scanned += 1
        payment_id = _as_int(item.get("id"))
        if payment_id is None:
            raise CrmUpstreamError("CRM 回款记录缺少 id")
        receive_date = _parse_date(item.get("receive_date"))
        if receive_date is not None and month_start <= receive_date < month_end:
            in_month[payment_id] = item
        if scanned % 200 == 0:
            await _progress(run_id, session_factory, scanned_payment_count=scanned)

    existing = await _load_month_payments(session_factory, corp_id, month_start, month_end)

    payment_count = 0
    eligible_count = 0
    seen: set[int] = set()
    out_of_scope: list[int] = []
    for payment_id, item in in_month.items():
        contract_id = _as_int(item.get("contract_id"))
        if contract_id is None:
            raise CrmUpstreamError("CRM 回款记录缺少 contract_id")
        seen.add(payment_id)
        try:
            details = await client.get_payment(contract_id, payment_id)
        except CrmNotFoundError:
            # 列表刚给过、详情却 404：不据此认定删除，交给复核段统一处理
            continue
        resolved_id = _as_int(details.get("id"))
        if resolved_id is not None and resolved_id != payment_id:
            raise CrmUpstreamError("CRM 回款详情ID与列表不一致")
        if not details.get("contract_title"):
            details["contract_title"] = item.get("contract_title")

        evaluated = _evaluate_payment(
            details=details,
            fallback_date=_parse_date(item.get("receive_date")),
            fallback_status=str(item.get("approve_status") or ""),
            allowed_paths=allowed_paths,
            month_start=month_start,
            month_end=month_end,
            customer_map=customer_map,
            contract_external_id=contract_id,
        )
        if not evaluated["industry_ok"]:
            # 业务口径：只镜像「房产经纪 / 新房开发」类别（含子级），其他行业不入库、不保留
            out_of_scope.append(payment_id)
            continue
        await _write_evaluated_payment(session_factory, corp_id, payment_id, evaluated, existing)
        payment_count += 1
        if evaluated["eligible"]:
            eligible_count += 1
        if payment_count % 20 == 0:
            await _progress(
                run_id,
                session_factory,
                payment_count=payment_count,
                eligible_count=eligible_count,
            )

    imported_ids = await _load_imported_ids(session_factory)
    await _recheck_missing_payments(
        client=client,
        session_factory=session_factory,
        corp_id=corp_id,
        existing=existing,
        seen=seen,
        allowed_paths=allowed_paths,
        month_start=month_start,
        month_end=month_end,
        customer_map=customer_map,
        imported_ids=imported_ids,
    )
    if out_of_scope:
        await _delete_out_of_scope_payments(session_factory, corp_id, out_of_scope, imported_ids)

    await _progress(
        run_id,
        session_factory,
        scanned_payment_count=scanned,
        payment_count=payment_count,
        eligible_count=eligible_count,
    )
    return {
        "contract_count": 0,
        "scanned_contract_count": 0,
        "scanned_payment_count": scanned,
        "payment_count": payment_count,
        "eligible_count": eligible_count,
    }


async def _write_evaluated_payment(
    session_factory, corp_id: str, payment_id: int, evaluated: dict, existing: dict[int, dict]
) -> None:
    """写入单笔镜像并同步内存视图（两条同步路径共用）"""
    old = existing.get(payment_id)
    await _upsert_payment(
        session_factory,
        {
            "corp_id": corp_id,
            "external_id": payment_id,
            **evaluated["values"],
            "source_changed": bool(
                old
                and old.get("imported_snapshot")
                and old["imported_snapshot"] != evaluated["snapshot"]
            ),
        },
    )
    existing[payment_id] = {
        "external_id": payment_id,
        "contract_external_id": evaluated["values"]["contract_external_id"],
        "imported_snapshot": old.get("imported_snapshot") if old else None,
    }


async def _recheck_missing_payments(
    *,
    client: CrmClient,
    session_factory,
    corp_id: str,
    existing: dict[int, dict],
    seen: set[int],
    allowed_paths: set[str],
    month_start: date,
    month_end: date,
    customer_map: dict[int, int],
    imported_ids: set[int],
) -> None:
    """本轮未再见到的既有镜像：逐笔复核，不因一次未列出就认定删除"""
    for external_id, row in existing.items():
        if external_id in seen:
            continue
        try:
            details = await client.get_payment(row["contract_external_id"], external_id)
        except CrmNotFoundError:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        update(CrmPayment)
                        .where(
                            CrmPayment.corp_id == corp_id,
                            CrmPayment.external_id == external_id,
                        )
                        .values(
                            eligible=False,
                            blocked_reason="CRM回款不存在或不可见",
                            source_changed=external_id in imported_ids
                            or bool(row.get("imported_snapshot")),
                            updated_at=_cst_naive(),
                        )
                    )
            continue

        evaluated = _evaluate_payment(
            details=details,
            fallback_date=None,
            fallback_status=APPROVED_STATUS,
            allowed_paths=allowed_paths,
            month_start=month_start,
            month_end=month_end,
            customer_map=customer_map,
            contract_external_id=row["contract_external_id"],
        )
        old_snapshot = row.get("imported_snapshot")
        if not evaluated["industry_ok"]:
            # 行业改为非允许范围：已导入的保留镜像（审计链），未导入的直接删除
            if external_id in imported_ids:
                await _upsert_payment(
                    session_factory,
                    {
                        "corp_id": corp_id,
                        "external_id": external_id,
                        **evaluated["values"],
                        "source_changed": _snapshots_differ(old_snapshot, evaluated["snapshot"]),
                    },
                )
            else:
                await _delete_out_of_scope_payments(
                    session_factory, corp_id, [external_id], imported_ids
                )
            continue
        await _upsert_payment(
            session_factory,
            {
                "corp_id": corp_id,
                "external_id": external_id,
                **evaluated["values"],
                "source_changed": _snapshots_differ(old_snapshot, evaluated["snapshot"]),
            },
        )


async def _delete_out_of_scope_payments(
    session_factory, corp_id: str, external_ids: list[int], imported_ids: set[int]
) -> None:
    """行业分类不属于允许范围 → 直接删除镜像行

    业务口径：只录入「房产经纪 / 新房开发」类别（含子级），其他行业不入库、不保留。
    例外：已被导入（存在充值记录）的回款**不删除**，只标 `eligible=False` ——
    删除会让已入账资金失去来源凭据。
    """
    if not external_ids:
        return
    now = _cst_naive()
    drop = [pid for pid in external_ids if pid not in imported_ids]
    keep = [pid for pid in external_ids if pid in imported_ids]
    async with session_factory() as session:
        async with session.begin():
            if drop:
                await session.execute(
                    delete(CrmPayment).where(
                        CrmPayment.corp_id == corp_id,
                        CrmPayment.external_id.in_(drop),
                    )
                )
            if keep:
                await session.execute(
                    update(CrmPayment)
                    .where(
                        CrmPayment.corp_id == corp_id,
                        CrmPayment.external_id.in_(keep),
                    )
                    .values(
                        eligible=False,
                        blocked_reason="行业分类不在允许范围",
                        updated_at=now,
                    )
                )


# ---------------------------------------------------------------------------
# 推荐 / 绑定
# ---------------------------------------------------------------------------


class CrmImportError(Exception):
    """导入/绑定类业务错误（路由映射 400/409）"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


async def _get_customer_for_scope(
    db: AsyncSession, customer_id: int, scope_user_id: Optional[int]
) -> Optional[Customer]:
    stmt = select(Customer).where(Customer.id == customer_id, Customer.deleted_at.is_(None))
    if scope_user_id is not None:
        stmt = stmt.where(
            or_(
                Customer.manager_id == scope_user_id,
                Customer.sales_manager_id == scope_user_id,
            )
        )
    return await db.scalar(stmt)


class CrmCustomerBindingService:
    """CRM 客户推荐与一对一绑定"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_candidates(
        self,
        *,
        customer: Customer,
        corp_id: str,
        query: Optional[str],
        page: int,
        page_size: int,
    ) -> dict:
        rows = await self.db.execute(
            select(CrmCustomer).where(
                CrmCustomer.corp_id == corp_id, CrmCustomer.deleted_at.is_(None)
            )
        )
        directory = rows.scalars().all()
        directory_updated_at = None
        if directory:
            directory_updated_at = await self.db.scalar(
                select(func.max(CrmCustomer.last_seen_at)).where(
                    CrmCustomer.corp_id == corp_id, CrmCustomer.deleted_at.is_(None)
                )
            )

        occupant_map: dict[int, int] = {}
        bound_rows = await self.db.execute(
            select(Customer.crm_customer_id, Customer.id).where(
                Customer.crm_customer_id.is_not(None),
                Customer.deleted_at.is_(None),
            )
        )
        for crm_id, middle_id in bound_rows.all():
            occupant_map[int(crm_id)] = int(middle_id)

        query_text = (query or "").strip() or customer.name
        scored: list[tuple[float, CrmCustomer]] = []
        for candidate in directory:
            score = score_crm_candidate(query_text, candidate.name)
            if score < RECOMMEND_THRESHOLD:
                continue
            scored.append((score, candidate))

        scored.sort(key=lambda item: (-item[0], item[1].external_id))

        items = []
        for score, candidate in scored:
            occupant = occupant_map.get(candidate.id)
            items.append(
                {
                    "id": candidate.id,
                    "external_id": candidate.external_id,
                    "name": candidate.name,
                    "owner_name": candidate.owner_name,
                    "score": round(score, 4),
                    "bound_to_current": occupant == customer.id,
                    "unavailable": occupant is not None and occupant != customer.id,
                }
            )

        total = len(items)
        if not query and total > RECOMMEND_LIMIT:
            items = items[:RECOMMEND_LIMIT]
            total = len(items)
        offset = (page - 1) * page_size
        return {
            "list": items[offset : offset + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "directory_updated_at": (
                directory_updated_at.isoformat() if directory_updated_at else None
            ),
            "directory_synced": bool(directory),
        }

    async def _assert_no_imported_recharge(self, customer_id: int) -> None:
        """已有 CRM 充值导入的客户禁止改绑/解绑

        改绑只改绑定关系，不会迁移已入账资金与充值凭据；先改绑会让旧记录
        永久挂在错误客户上，因此必须硬阻断，要求先撤销导入。
        """
        imported = await self.db.scalar(
            select(func.count())
            .select_from(RechargeRecord)
            .where(
                RechargeRecord.customer_id == customer_id,
                RechargeRecord.crm_payment_id.is_not(None),
            )
        )
        if imported:
            raise CrmImportError("该客户已有CRM充值导入记录，请先撤销导入再修改绑定", 409)

    async def bind(self, *, customer_id: int, crm_customer_id: Optional[int], corp_id: str) -> dict:
        """事务内调用：锁客户行 → 校验候选 → 复查唯一占用 → 写入"""
        customer = await self.db.scalar(
            select(Customer)
            .where(Customer.id == customer_id, Customer.deleted_at.is_(None))
            .with_for_update()
        )
        if customer is None:
            raise CrmImportError("客户不存在", 400)

        if crm_customer_id is None:
            await self._assert_no_imported_recharge(customer_id)
            customer.crm_customer_id = None
            await self.db.flush()
            return {
                "crm_customer_id": None,
                "crm_customer_external_id": None,
                "crm_customer_name": None,
            }

        candidate = await self.db.scalar(
            select(CrmCustomer).where(
                CrmCustomer.id == crm_customer_id,
                CrmCustomer.corp_id == corp_id,
                CrmCustomer.deleted_at.is_(None),
            )
        )
        if candidate is None:
            raise CrmImportError("CRM客户不存在或不属于当前企业", 400)

        if customer.crm_customer_id == crm_customer_id:
            return {
                "crm_customer_id": candidate.id,
                "crm_customer_external_id": candidate.external_id,
                "crm_customer_name": candidate.name,
            }

        await self._assert_no_imported_recharge(customer_id)

        occupant = await self.db.scalar(
            select(Customer.id).where(
                Customer.crm_customer_id == crm_customer_id,
                Customer.deleted_at.is_(None),
                Customer.id != customer_id,
            )
        )
        if occupant is not None:
            raise CrmImportError("该CRM客户已绑定其他中台客户", 409)

        customer.crm_customer_id = crm_customer_id
        await self.db.flush()
        return {
            "crm_customer_id": candidate.id,
            "crm_customer_external_id": candidate.external_id,
            "crm_customer_name": candidate.name,
        }


# ---------------------------------------------------------------------------
# 原子导入
# ---------------------------------------------------------------------------


def _validate_import_amounts(
    real_amount: Decimal, bonus_amount: Decimal, source_amount: Optional[Decimal]
) -> None:
    if source_amount is None:
        raise CrmImportError("CRM回款金额无效，不能导入")
    if real_amount != source_amount:
        raise CrmImportError("实充金额必须等于CRM回款金额")
    if real_amount <= 0:
        raise CrmImportError("实充金额必须大于0")
    if bonus_amount < 0:
        raise CrmImportError("赠送金额不能为负数")
    if real_amount == 0 and bonus_amount == 0:
        raise CrmImportError("实充与赠送金额不能同时为0")


async def find_imported_recharge(db: AsyncSession, payment_id: int) -> Optional[RechargeRecord]:
    """含软删除行：唯一约束覆盖软删，凭据不能被软删记录绕过"""
    return await db.scalar(
        select(RechargeRecord).where(RechargeRecord.crm_payment_id == payment_id)
    )


def build_existing_import_response(
    record: RechargeRecord,
    *,
    customer_id: int,
    real_amount: Decimal,
    bonus_amount: Decimal,
    balance: Any,
) -> dict:
    if (
        record.customer_id != customer_id
        or Decimal(record.real_amount) != real_amount
        or Decimal(record.bonus_amount or 0) != bonus_amount
    ):
        raise CrmImportError("该回款已导入，不能更改客户或充值金额", 409)
    total = Decimal(record.real_amount) + Decimal(record.bonus_amount or 0)
    return {
        "recharge_record_id": record.id,
        "customer_id": record.customer_id,
        "real_amount": f"{Decimal(record.real_amount):.2f}",
        "bonus_amount": f"{Decimal(record.bonus_amount or 0):.2f}",
        "total_amount": f"{total:.2f}",
        "recharge_date": record.recharge_date.isoformat() if record.recharge_date else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "already_imported": True,
        "balance": _serialize_balance(balance),
    }


def _serialize_balance(balance: Any) -> dict:
    if balance is None:
        return {"real_amount": "0.00", "bonus_amount": "0.00", "total_amount": "0.00"}
    real = Decimal(balance.real_amount or 0)
    bonus = Decimal(balance.bonus_amount or 0)
    return {
        "real_amount": f"{real:.2f}",
        "bonus_amount": f"{bonus:.2f}",
        "total_amount": f"{(balance.total_amount if balance.total_amount is not None else real + bonus):.2f}",
    }


class CrmRechargeImportService:
    """事务内的 CRM 回款原子导入

    调用方必须在 `async with db_session.begin():` 内调用 `import_payment`；
    路由负责事务外的 HTTP 实时复核并把白名单快照传进来。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.balance_service = BalanceService(BalanceRepository(db))

    async def import_payment(
        self,
        *,
        payment_id: int,
        customer_id: int,
        real_amount: Decimal,
        bonus_amount: Decimal,
        operator_id: int,
        corp_id: str,
        source_snapshot: Optional[dict],
        ip_address: Optional[str] = None,
        scope_user_id: Optional[int] = None,
    ) -> dict:
        # 锁序固定：Customer → CrmPayment → 余额行（由 BalanceService.recharge 负责）
        customer = await self.db.scalar(
            select(Customer)
            .where(Customer.id == customer_id, Customer.deleted_at.is_(None))
            .with_for_update()
        )
        if customer is None:
            raise CrmImportError("客户不存在", 400)
        if scope_user_id is not None and not (
            customer.manager_id == scope_user_id or customer.sales_manager_id == scope_user_id
        ):
            raise CrmImportError("无权操作该客户", 403)
        if customer.is_disabled:
            raise CrmImportError("客户已停用，不能导入充值", 400)

        payment = await self.db.scalar(
            select(CrmPayment)
            .where(
                CrmPayment.id == payment_id,
                CrmPayment.corp_id == corp_id,
                CrmPayment.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if payment is None:
            raise CrmImportError("CRM回款不存在", 404)

        # 已导入（含软删凭据）：同目标 + 同金额幂等返回，否则 409
        existing = await find_imported_recharge(self.db, payment_id)
        balance = await self.balance_service.get_balance_by_customer_id(customer_id)
        if existing is not None:
            return build_existing_import_response(
                existing,
                customer_id=customer_id,
                real_amount=real_amount,
                bonus_amount=bonus_amount,
                balance=balance,
            )

        if payment.crm_customer_id != customer.crm_customer_id or customer.crm_customer_id is None:
            raise CrmImportError("该客户未绑定本笔回款的CRM客户", 400)
        if not payment.eligible:
            raise CrmImportError(payment.blocked_reason or "该回款不满足导入条件", 400)
        if payment.source_changed:
            raise CrmImportError("CRM回款已变更，请重新同步并确认", 409)

        _validate_import_amounts(real_amount, bonus_amount, payment.amount)

        # 锁内再次比较：HTTP 复核快照 vs 当前锁定镜像
        current_snapshot = _business_snapshot(
            customer_external_id=payment.customer_external_id,
            contract_external_id=payment.contract_external_id,
            amount=payment.amount,
            receive_date=payment.receive_date,
            industry_path=payment.industry_path,
            approve_status=payment.approve_status,
        )
        if _snapshots_differ(source_snapshot, current_snapshot):
            raise CrmImportError("CRM回款已变更，请同步并重新确认", 409)

        package_info = await batch_query_package_info(self.db, [customer_id])
        if customer.price_policy == "yearly" or customer_id in package_info:
            raise CrmImportError("包年客户不支持CRM回款充值", 400)

        incoming = real_amount + bonus_amount
        if incoming > NUMERIC_12_2_MAX:
            raise CrmImportError("充值金额超出可入账上限", 400)
        if balance is not None:
            new_real = Decimal(balance.real_amount or 0) + real_amount
            new_bonus = Decimal(balance.bonus_amount or 0) + bonus_amount
            if new_real > NUMERIC_12_2_MAX or new_bonus > NUMERIC_12_2_MAX:
                raise CrmImportError("充值后余额超出可入账上限", 400)

        record = await self.balance_service.recharge(
            customer_id=customer_id,
            real_amount=real_amount,
            bonus_amount=bonus_amount,
            operator_id=operator_id,
            payment_proof=None,
            remark=f"CRM回款 {payment.external_id}",
            recharge_date=payment.receive_date,
            crm_payment_id=payment.id,
        )

        payment.imported_snapshot = current_snapshot
        payment.source_changed = False

        new_balance = await self.balance_service.get_balance_by_customer_id(customer_id)
        total = real_amount + bonus_amount
        await create_audit_entry(
            self.db,
            operator_id,
            "crm_recharge_import",
            "crm_recharge",
            record.id,
            "recharge_record",
            changes={
                "crm_payment_external_id": payment.external_id,
                "source_amount": str(payment.amount),
                "real_amount": str(real_amount),
                "bonus_amount": str(bonus_amount),
                "total_amount": str(total),
                "customer_id": customer_id,
                "recharge_date": payment.receive_date.isoformat() if payment.receive_date else None,
                "balance_after": _serialize_balance(new_balance),
            },
            ip_address=ip_address,
        )

        return {
            "recharge_record_id": record.id,
            "customer_id": customer_id,
            "real_amount": f"{real_amount:.2f}",
            "bonus_amount": f"{bonus_amount:.2f}",
            "total_amount": f"{total:.2f}",
            "recharge_date": record.recharge_date.isoformat() if record.recharge_date else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "already_imported": False,
            "balance": _serialize_balance(new_balance),
        }

    async def revoke_import(
        self,
        *,
        payment_id: int,
        customer_id: int,
        reason: str,
        operator_id: int,
        corp_id: str,
        is_super_admin: bool,
        force: bool = False,
        ip_address: Optional[str] = None,
        scope_user_id: Optional[int] = None,
    ) -> dict:
        """撤销一笔 CRM 充值导入（事务内调用）

        锁序与导入一致：客户 → 回款 → 充值记录 → 余额行。
        `recharge_records.crm_payment_id` 是**覆盖软删**的唯一键，因此撤销只能物理删除
        记录；资金凭据的留痕由 `audit_logs` 的 before 快照承担。

        余额不足（资金已被消耗）时仅超级管理员可 `force` 撤销，并标记线下核对；
        扣减后余额可能为负，表示客户欠款。
        """
        customer = await self.db.scalar(
            select(Customer)
            .where(Customer.id == customer_id, Customer.deleted_at.is_(None))
            .with_for_update()
        )
        if customer is None:
            raise CrmImportError("客户不存在", 400)
        if scope_user_id is not None and not (
            customer.manager_id == scope_user_id or customer.sales_manager_id == scope_user_id
        ):
            raise CrmImportError("无权操作该客户", 403)

        payment = await self.db.scalar(
            select(CrmPayment)
            .where(
                CrmPayment.id == payment_id,
                CrmPayment.corp_id == corp_id,
                CrmPayment.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if payment is None:
            raise CrmImportError("CRM回款不存在", 404)

        record = await self.db.scalar(
            select(RechargeRecord)
            .where(RechargeRecord.crm_payment_id == payment_id)
            .with_for_update()
        )
        if record is None:
            raise CrmImportError("该回款尚未导入CRM充值", 400)
        if record.customer_id != customer_id:
            raise CrmImportError("充值记录不属于该客户，不能撤销", 400)

        await self.db.execute(
            pg_insert(CustomerBalance)
            .values(customer_id=customer_id)
            .on_conflict_do_nothing(index_elements=["customer_id"])
        )
        balance = await self.db.scalar(
            select(CustomerBalance)
            .where(CustomerBalance.customer_id == customer_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if balance is None:  # pragma: no cover - INSERT 后必然存在
            raise CrmImportError("客户余额行不存在", 400)

        real_amount = Decimal(record.real_amount or 0)
        bonus_amount = Decimal(record.bonus_amount or 0)
        current_real = Decimal(balance.real_amount or 0)
        current_bonus = Decimal(balance.bonus_amount or 0)
        shortfall_real = max(Decimal("0"), real_amount - current_real)
        shortfall_bonus = max(Decimal("0"), bonus_amount - current_bonus)
        needs_manual = shortfall_real > 0 or shortfall_bonus > 0

        if needs_manual and not is_super_admin:
            raise CrmImportError("该笔资金已被消耗，只有超级管理员可强制撤销（需线下核对）", 403)
        if needs_manual and not force:
            raise CrmImportError("余额不足以回退，请确认强制撤销并线下核对欠款", 409)

        new_real = current_real - real_amount
        new_bonus = current_bonus - bonus_amount
        if abs(new_real) > NUMERIC_12_2_MAX or abs(new_bonus) > NUMERIC_12_2_MAX:
            raise CrmImportError("撤销后余额超出可入账范围", 400)

        before_balance = _serialize_balance(balance)
        balance.real_amount = new_real
        balance.bonus_amount = new_bonus
        balance.total_amount = new_real + new_bonus

        record_id = record.id
        recharge_date = record.recharge_date.isoformat() if record.recharge_date else None
        await create_audit_entry(
            self.db,
            operator_id,
            "crm_recharge_import_revoke",
            "crm_recharge",
            record_id,
            "recharge_record",
            changes={
                "reason": reason,
                "crm_payment_id": payment_id,
                "crm_payment_external_id": payment.external_id,
                "customer_id": customer_id,
                "real_amount": f"{real_amount:.2f}",
                "bonus_amount": f"{bonus_amount:.2f}",
                "recharge_date": recharge_date,
                "forced": needs_manual,
                "needs_manual_reconciliation": needs_manual,
                "shortfall_real": f"{shortfall_real:.2f}",
                "shortfall_bonus": f"{shortfall_bonus:.2f}",
                "balance_before": before_balance,
                "balance_after": _serialize_balance(balance),
            },
            ip_address=ip_address,
        )

        await self.db.delete(record)
        payment.imported_snapshot = None
        payment.source_changed = False
        await self.db.flush()

        return {
            "payment_id": payment.id,
            "payment_external_id": payment.external_id,
            "customer_id": customer_id,
            "recharge_record_id": record_id,
            "real_amount": f"{real_amount:.2f}",
            "bonus_amount": f"{bonus_amount:.2f}",
            "recharge_date": recharge_date,
            "needs_manual_reconciliation": needs_manual,
            "shortfall_real": f"{shortfall_real:.2f}",
            "shortfall_bonus": f"{shortfall_bonus:.2f}",
            "balance": _serialize_balance(balance),
        }
