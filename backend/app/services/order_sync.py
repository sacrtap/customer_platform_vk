"""订单同步服务"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, cast

import aiomysql
from sqlalchemy import CursorResult, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.customers import Customer
from app.models.daily_order import DailyOrder
from app.services.dto import SyncDetail, SyncResult
from app.utils.timezone import CST

logger = logging.getLogger(__name__)


class OrderSyncService:
    """订单同步服务"""

    def __init__(self, db: AsyncSession, external_engine: Optional[AsyncEngine] = None):
        self.db = db
        self.external_engine = external_engine

    @property
    def external_db_config(self) -> Dict[str, Any]:
        """外部 MySQL 连接配置"""
        from app.config import settings

        url = settings.external_mysql_url
        if not url:
            raise ValueError("外部 MySQL 配置缺失：EXTERNAL_MYSQL_URL 未设置")

        # mysql://user:password@host:port/dbname
        parts = url.replace("mysql://", "").split("@")
        user_pass = parts[0].split(":")
        host_port_db = parts[1].split("/")
        host_port = host_port_db[0].split(":")

        config = {
            "host": host_port[0],
            "port": int(host_port[1]) if len(host_port) > 1 else 3306,
            "user": user_pass[0],
            "password": user_pass[1] if len(user_pass) > 1 else "",
            "db": host_port_db[1] if len(host_port_db) > 1 else "",
        }

        # 验证必需字段（使用 key 存在性检查，避免空密码误判）
        required_keys = ["host", "port", "user", "db"]
        missing = [k for k in required_keys if k not in config]
        if missing:
            raise ValueError(f"外部 MySQL 配置缺失：{', '.join(missing)}")

        return config

    async def sync_orders(
        self, sync_date: datetime, detail_collector: Optional[List[SyncDetail]] = None
    ) -> SyncResult:
        """同步指定日期的订单

        如果外部数据源连接失败，异常会向上传播，由调用方（execute_task）的
        逐天异常处理器捕获并记录 failed_count。

        Args:
            sync_date: 同步日期（UTC datetime）
            detail_collector: 可选执行明细收集器（注入后记录同步过程明细，
                默认 None 不记录，行为与旧版一致）
        """
        # 1. 获取订单（异常时向上传播，不吞掉错误）
        try:
            orders = await self._fetch_orders(sync_date)
        except Exception as e:
            if detail_collector is not None:
                detail_collector.append(
                    SyncDetail(
                        sync_date=sync_date.astimezone(CST).date(),
                        level="error",
                        category="order_fetch",
                        message=f"外部数据源拉取订单失败: {type(e).__name__}: {e}",
                    )
                )
            raise

        if not orders:
            return SyncResult(
                success=0, failed=0, skipped=0, unmatched=0, message="没有新订单需要同步"
            )

        # 2. 清空该日期的所有旧订单
        await self._clear_orders(sync_date)

        # 3. 匹配客户并保存
        return await self._match_and_save(
            orders=orders, sync_date=sync_date, detail_collector=detail_collector
        )

    async def _fetch_orders(self, sync_date: datetime) -> List[Dict]:
        """从外部 MySQL 获取订单

        通过 JOIN nest_user 获取公司名称，使用 upload_date 范围匹配日期
        （避免 DATE() 函数包裹导致索引失效），通过 order_status 条件过滤
        需要结算的订单，使用 LEFT(device_name, 1) 提取设备类型首字符。
        """
        # 计算 upload_date 的日期范围（避免 DATE() 函数导致全表扫描）
        # sync_date 已经是 UTC datetime 的当天开始时刻
        start_dt = sync_date  # UTC 当天开始
        end_dt = sync_date + timedelta(days=1)  # UTC 次日开始

        # 统一 SQL（两条路径共用）
        # SELECT 字段顺序：
        #   0: order_code, 1: custom_code, 2: nest_id, 3: owner_company,
        #   4: group_type, 5: create_date, 6: upload_date, 7: floor_count,
        #   8: device_type, 9: order_status
        # 结算范围：order_status >= 3 AND <= 12, OR = 15
        # 不再过滤 nest_id（空 nest_id 的订单也纳入结算）
        STATUS_COND = "((D.order_status >= 3 AND D.order_status <= 12) OR D.order_status = 15)"
        SQL_ENGINE = (
            "SELECT D.order_code, D.custom_code, D.nest_id, "
            "U.owner_company, D.group_type, DATE(D.create_date), "
            "DATE(D.upload_date), D.floor_count, LEFT(D.device_name, 1), "
            "D.order_status "
            "FROM nest_model_order AS D "
            "INNER JOIN ("
            "  SELECT group_type, MAX(owner_company) AS owner_company "
            "  FROM nest_user GROUP BY group_type"
            ") AS U ON D.group_type = U.group_type "
            f"WHERE D.upload_date >= :start AND D.upload_date < :end "
            f"AND {STATUS_COND}"
        )
        SQL_AIOMYSQL = (
            "SELECT D.order_code, D.custom_code, D.nest_id, "
            "U.owner_company, D.group_type, DATE(D.create_date), "
            "DATE(D.upload_date), D.floor_count, LEFT(D.device_name, 1), "
            "D.order_status "
            "FROM nest_model_order AS D "
            "INNER JOIN ("
            "  SELECT group_type, MAX(owner_company) AS owner_company "
            "  FROM nest_user GROUP BY group_type"
            ") AS U ON D.group_type = U.group_type "
            "WHERE D.upload_date >= %s AND D.upload_date < %s "
            f"AND {STATUS_COND}"
        )

        def _rows_to_dicts(rows):
            return [
                {
                    "order_code": row[0],
                    "custom_code": row[1],
                    "nest_id": row[2],
                    "company_name": row[3],
                    "group_type": row[4],  # Keep as int for customer matching
                    "create_date": self._normalize_date(row[5]),
                    "upload_date": self._normalize_date(row[6]),
                    "floor_count": row[7],
                    "device_type": row[8],
                    "order_status": row[9],
                }
                for row in rows
            ]

        if self.external_engine:
            from sqlalchemy.sql import text

            async with self.external_engine.connect() as conn:
                result = await conn.execute(text(SQL_ENGINE), {"start": start_dt, "end": end_dt})
                return _rows_to_dicts(result.fetchall())
        else:
            config = self.external_db_config
            conn = await asyncio.wait_for(
                aiomysql.connect(
                    host=config["host"],
                    port=config["port"],
                    user=config["user"],
                    password=config["password"],
                    db=config["db"],
                    connect_timeout=10,
                ),
                timeout=15,
            )
            try:
                async with conn.cursor() as cursor:
                    await asyncio.wait_for(
                        cursor.execute(SQL_AIOMYSQL, (start_dt, end_dt)),
                        timeout=30,
                    )
                    rows = await asyncio.wait_for(
                        cursor.fetchall(),
                        timeout=30,
                    )
                    return _rows_to_dicts(rows)
            finally:
                if conn:
                    conn.close()

    def _normalize_date(self, value) -> date:
        """将各种日期类型转换为 datetime.date

        外部 MySQL 的 DATE 字段可能返回 datetime.date、datetime.datetime 或 str。
        """
        if isinstance(value, datetime):
            return value.date()
        elif isinstance(value, date):
            return value
        elif isinstance(value, str):
            # 尝试解析常见格式
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"无法解析日期: {value}")
        else:
            raise TypeError(f"不支持的日期类型: {type(value)}")

    async def _clear_orders(self, sync_date: datetime) -> None:
        """清空指定日期的所有订单（按 sync_date 范围删除，与唯一约束一致）"""
        from sqlalchemy import delete

        day_end = sync_date + timedelta(days=1)
        result = await self.db.execute(
            delete(DailyOrder).where(
                DailyOrder.sync_date >= sync_date,
                DailyOrder.sync_date < day_end,
            )
        )
        await self.db.commit()
        logger.info(f"已清空 {sync_date} 的 {cast(CursorResult[Any], result).rowcount} 条订单记录")

    async def _match_and_save(
        self,
        orders: List[Dict],
        sync_date: datetime,
        detail_collector: Optional[List[SyncDetail]] = None,
    ) -> SyncResult:
        """匹配客户并保存订单"""
        result = SyncResult()
        saved_orders = []  # 收集成功保存的订单
        seen_keys = set()  # 内存级去重，防止同一 (order_code, sync_date) 重复插入
        # 成功明细按客户聚合：customer_id -> {"customer_name", "count"}
        success_by_customer: Dict[int, Dict[str, Any]] = {}

        # 注意：清空逻辑已移至 sync_orders 入口

        def _emit(level: str, category: str, message: str, **kwargs) -> None:
            if detail_collector is not None:
                detail_collector.append(
                    SyncDetail(
                        # sync_date 为 UTC datetime（本地日期的 UTC 起点），
                        # 须转回 CST 本地日期与任务级明细（task.start_date 本地 date）保持一致
                        sync_date=sync_date.astimezone(CST).date(),
                        level=level,
                        category=category,
                        message=message,
                        **kwargs,
                    )
                )

        for order in orders:
            order_code = order.get("order_code")
            try:
                # 检查本批次是否已处理过相同的 (order_code, sync_date)
                dedup_key = (order_code, sync_date)
                if dedup_key in seen_keys:
                    result.skipped += 1
                    continue

                # 匹配客户（使用独立方法）
                customer = await self._match_customer(order)
                if customer is None:
                    result.unmatched += 1
                    _emit(
                        "warning",
                        "order_match",
                        "订单未匹配到内部客户（外部客户ID={}，公司名={}）".format(
                            order.get("group_type") or "未知",
                            order.get("company_name") or "未知",
                        ),
                        external_customer_id=str(order.get("group_type"))
                        if order.get("group_type") is not None
                        else None,
                        company_name=order.get("company_name"),
                        order_code=order_code,
                    )
                    continue

                # 检查订单是否已存在（使用与唯一约束一致的字段）
                existing = await self.db.execute(
                    select(DailyOrder).where(
                        DailyOrder.order_code == order_code,
                        DailyOrder.sync_date >= sync_date,
                        DailyOrder.sync_date < sync_date + timedelta(days=1),
                    )
                )
                if existing.scalar_one_or_none():
                    result.skipped += 1
                    continue

                # 创建订单记录但不立即提交
                daily_order = DailyOrder(
                    order_code=order_code,
                    custom_code=order.get("custom_code"),
                    nest_id=order.get("nest_id"),
                    company_name=order.get("company_name"),
                    group_type=str(order.get("group_type"))
                    if order.get("group_type") is not None
                    else None,
                    customer_id=customer.id,
                    create_date=order.get("create_date"),
                    upload_date=order.get("upload_date"),
                    order_status=order.get("order_status"),
                    floor_count=order.get("floor_count"),
                    device_type=order.get("device_type"),
                    sync_date=sync_date,
                )
                seen_keys.add(dedup_key)
                saved_orders.append(daily_order)
                result.success += 1

                # 成功明细按客户聚合
                if customer.id in success_by_customer:
                    success_by_customer[customer.id]["count"] += 1
                else:
                    success_by_customer[customer.id] = {
                        "customer_name": customer.name,
                        "count": 1,
                    }

            except Exception as e:
                # 捕获匹配客户时的异常
                logger.error("处理订单失败 %s: %s", order_code, e)
                result.failed += 1
                _emit(
                    "error",
                    "order_save",
                    f"订单处理失败: {type(e).__name__}: {e}",
                    company_name=order.get("company_name"),
                    order_code=order_code,
                )

        # 统一提交所有成功的订单
        if saved_orders:
            for order_obj in saved_orders:
                self.db.add(order_obj)
            try:
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                logger.error("批量提交订单失败: %s", e)
                # 将已成功的订单标记为失败
                result.failed += len(saved_orders)
                result.success -= len(saved_orders)
                _emit(
                    "error",
                    "order_save",
                    f"批量提交 {len(saved_orders)} 条订单失败: {type(e).__name__}: {e}",
                )
                success_by_customer.clear()

        # 成功明细按客户生成 info 记录
        for customer_id, agg in success_by_customer.items():
            _emit(
                "info",
                "order_save",
                f"成功同步 {agg['count']} 条订单",
                customer_id=customer_id,
                customer_name=agg["customer_name"],
                record_count=agg["count"],
            )

        # 设置结果消息
        if result.failed > 0 and result.success > 0:
            result.message = "部分同步失败"
        elif result.failed > 0:
            result.message = "同步失败"
        else:
            result.message = "同步完成"

        return result

    async def _match_customer(self, order: Dict) -> Optional[Customer]:
        """匹配内部客户（通过 external_id 或 group_type）"""
        # 通过 group_type（外部客户 ID）匹配
        group_type = order.get("group_type")
        if group_type:
            stmt = select(Customer).where(Customer.company_id == group_type)
            result = await self.db.execute(stmt)
            customer = result.scalar_one_or_none()
            if customer is not None:
                return customer

        # 通过公司名称匹配
        company_name = order.get("company_name")
        if company_name:
            stmt = select(Customer).where(Customer.name == company_name)
            result = await self.db.execute(stmt)
            customer = result.scalar_one_or_none()
            if customer is not None:
                return customer

        return None
