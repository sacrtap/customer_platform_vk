"""订单同步服务"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

import aiomysql
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.billing import PricingRule
from app.models.customers import Customer
from app.models.daily_order import DailyOrder
from app.services.dto import CustomerCalcResult, SyncResult

logger = logging.getLogger(__name__)


class OrderSyncService:
    """订单同步服务"""

    def __init__(self, db: AsyncSession, external_engine: AsyncEngine):
        self.db = db
        self.external_engine = external_engine

    @property
    def external_db_config(self) -> Dict[str, Any]:
        """外部 MySQL 连接配置"""
        from app.config import settings

        url = settings.external_mysql_url
        if not url:
            return {}
        # mysql://user:password@host:port/dbname
        parts = url.replace("mysql://", "").split("@")
        user_pass = parts[0].split(":")
        host_port_db = parts[1].split("/")
        host_port = host_port_db[0].split(":")
        return {
            "host": host_port[0],
            "port": int(host_port[1]) if len(host_port) > 1 else 3306,
            "user": user_pass[0],
            "password": user_pass[1] if len(user_pass) > 1 else "",
            "db": host_port_db[1] if len(host_port_db) > 1 else "",
        }

    async def sync_orders(self, sync_date: date) -> SyncResult:
        """同步指定日期的订单"""
        try:
            orders = await self._fetch_orders(sync_date)
            if not orders:
                return SyncResult(
                    success=0, failed=0, skipped=0, unmatched=0, message="没有新订单需要同步"
                )
            return await self._match_and_save(orders=orders, sync_date=sync_date)
        except Exception as e:
            logger.error("订单同步失败: %s", e)
            return SyncResult(success=0, failed=0, skipped=0, unmatched=0, message=str(e))

    async def _fetch_orders(self, sync_date: date) -> List[Dict]:
        """从外部 MySQL 获取订单"""
        config = self.external_db_config
        conn = await aiomysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            db=config["db"],
        )
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT order_code, custom_code, nest_id, company_name, "
                    "group_type, create_date, floor_count, device_type "
                    "FROM erp_orders WHERE create_date = %s",
                    (sync_date,),
                )
                rows = await cursor.fetchall()
                return [
                    {
                        "order_code": row[0],
                        "custom_code": row[1],
                        "nest_id": row[2],
                        "company_name": row[3],
                        "group_type": row[4],
                        "create_date": row[5],
                        "floor_count": row[6],
                        "device_type": row[7],
                    }
                    for row in rows
                ]
        finally:
            conn.close()

    async def _match_and_save(self, orders: List[Dict], sync_date: date) -> SyncResult:
        """匹配客户并保存订单"""
        result = SyncResult()

        for order in orders:
            order_code = order.get("order_code")
            try:
                # 匹配客户：通过 group_type（外部客户 ID）
                group_type = order.get("group_type")
                customer = None
                if group_type:
                    stmt = select(Customer).where(Customer.company_id == group_type)
                    db_customer_result = await self.db.execute(stmt)
                    customer = db_customer_result.scalar_one_or_none()

                # 匹配客户：通过公司名称
                if customer is None:
                    company_name = order.get("company_name")
                    if company_name:
                        stmt = select(Customer).where(Customer.name == company_name)
                        db_name_result = await self.db.execute(stmt)
                        customer = db_name_result.scalar_one_or_none()

                if customer is None:
                    result.unmatched += 1
                    continue

                # 检查重复订单
                stmt = select(DailyOrder).where(
                    and_(
                        DailyOrder.order_code == order_code,
                        DailyOrder.create_date == order.get("create_date"),
                    )
                )
                db_existing = await self.db.execute(stmt)
                existing = db_existing.scalar_one_or_none()
                if existing is not None:
                    result.skipped += 1
                    continue

                # 创建并保存订单记录
                daily_order = DailyOrder(
                    order_code=order_code,
                    custom_code=order.get("custom_code"),
                    nest_id=order.get("nest_id"),
                    company_name=order.get("company_name"),
                    group_type=order.get("group_type"),
                    customer_id=customer.id,
                    create_date=order.get("create_date"),
                    floor_count=order.get("floor_count"),
                    device_type=order.get("device_type"),
                    sync_date=sync_date,
                )
                self.db.add(daily_order)
                await self.db.commit()
                result.success += 1

            except IntegrityError:
                await self.db.rollback()
                logger.warning("订单重复跳过: %s", order_code)
                result.skipped += 1
            except Exception as e:
                await self.db.rollback()
                logger.error("保存订单失败: %s", e)
                result.failed += 1

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

    async def _calculate_cost(
        self,
        customer_id: int,
        floor_count: int,
        pricing_rule: Optional[PricingRule] = None,
    ) -> CustomerCalcResult:
        """计算订单费用"""
        if pricing_rule is None:
            return CustomerCalcResult(
                customer_id=customer_id,
                customer_name="",
                has_rule=False,
                order_count=0,
                total_cost=Decimal("0.00"),
                message="no_rule",
            )

        total_cost = pricing_rule.price

        return CustomerCalcResult(
            customer_id=customer_id,
            customer_name="",
            has_rule=True,
            order_count=1,
            total_cost=total_cost,
            message="",
        )
