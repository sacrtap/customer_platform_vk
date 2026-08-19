"""检查包年客户的 daily_orders 是否存在"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models.billing import PricingRule
from app.models.daily_order import DailyOrder


async def check():
    url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url)
    async with AsyncSession(engine) as session:
        # 查询包年客户
        result = await session.execute(
            select(PricingRule.customer_id, PricingRule.package_limits).where(
                PricingRule.pricing_type == "package",
                PricingRule.deleted_at.is_(None),
            )
        )
        for row in result.all():
            print(f"客户 {row.customer_id}: limits={row.package_limits}")

            # 查询该客户的 daily_orders
            order_result = await session.execute(
                select(
                    DailyOrder.sync_date,
                    func.count(DailyOrder.id).label("order_count"),
                )
                .where(DailyOrder.customer_id == row.customer_id)
                .group_by(DailyOrder.sync_date)
                .order_by(DailyOrder.sync_date)
            )
            order_rows = order_result.all()
            if order_rows:
                print(f"  订单记录({len(order_rows)}天):")
                for o in order_rows[:5]:
                    print(f"    {o.sync_date} | 订单数={o.order_count}")
                if len(order_rows) > 5:
                    print(f"    ... 共 {len(order_rows)} 天")
            else:
                print("  ⚠️ 无订单记录 — 该客户在 daily_orders 表中没有数据")
            print()


asyncio.run(check())
