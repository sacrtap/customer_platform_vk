"""验证脚本：检查包年客户的 daily_consumptions 是否正确生成"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models.billing import PricingRule
from app.models.daily_consumption import DailyConsumption


async def check():
    url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url)
    async with AsyncSession(engine) as session:
        # 查询所有包年客户
        result = await session.execute(
            select(
                PricingRule.customer_id,
                PricingRule.id,
                PricingRule.package_type,
                PricingRule.package_limits,
            ).where(
                PricingRule.pricing_type == "package",
                PricingRule.deleted_at.is_(None),
            )
        )
        for row in result.all():
            print(f"客户 {row.customer_id}: 规则ID={row.id}, 套餐={row.package_type}")
            print(f"  package_limits={row.package_limits}")

            # 查询该客户的 daily_consumptions
            dc_result = await session.execute(
                select(
                    DailyConsumption.consumption_date,
                    DailyConsumption.device_type,
                    DailyConsumption.order_count,
                    DailyConsumption.total_cost,
                )
                .where(DailyConsumption.customer_id == row.customer_id)
                .order_by(DailyConsumption.consumption_date)
            )
            dc_rows = dc_result.all()
            if dc_rows:
                print(f"  消耗记录({len(dc_rows)}条):")
                for dc in dc_rows[:5]:
                    print(
                        f"    {dc.consumption_date} | 设备={dc.device_type} | 订单={dc.order_count} | 费用={dc.total_cost}"
                    )
                if len(dc_rows) > 5:
                    print(f"    ... 共 {len(dc_rows)} 条")
                total = sum(float(dc.total_cost or 0) for dc in dc_rows)
                print(f"  总费用: ¥{total:.2f}")
            else:
                print("  ⚠️ 无消耗记录")
            print()


asyncio.run(check())
