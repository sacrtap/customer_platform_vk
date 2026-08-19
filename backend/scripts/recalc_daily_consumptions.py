"""一次性脚本：重新计算所有历史日期的 daily_consumptions

执行方式：
    cd backend && python -m scripts.recalc_daily_consumptions

逻辑：
    1. 查询 daily_orders 表中所有不同的 sync_date
    2. 对每个日期，调用 CostCalcService.calculate_daily_cost 重新计算费用
    3. CostCalcService 会先清空该日期的 daily_consumptions 再重新写入
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models.daily_order import DailyOrder
from app.services.cost_calc import CostCalcService


async def recalc():
    """重新计算所有历史日期的消耗费用"""
    db_url = settings.database_url
    if not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(db_url, echo=False)

    async with AsyncSession(engine) as session:
        # 1. 查询所有有订单的日期
        result = await session.execute(
            select(DailyOrder.sync_date).distinct().order_by(DailyOrder.sync_date)
        )
        dates = [row[0] for row in result.all()]

        if not dates:
            print("✅ 没有找到任何订单日期，无需重新计算")
            return

        print(f"📅 找到 {len(dates)} 个日期需要重新计算")
        print(f"   日期范围: {dates[0]} ~ {dates[-1]}")

        cost_service = CostCalcService(session)

        total_calculated = 0
        total_no_rule = 0
        total_customers = 0

        for i, sync_date in enumerate(dates):
            result = await cost_service.calculate_daily_cost(consumption_date=sync_date)
            total_customers += result["total_customers"]
            total_calculated += result["calculated"]
            total_no_rule += result["no_rule"]

            # 每 30 天输出一次进度
            if (i + 1) % 30 == 0 or i == len(dates) - 1:
                print(
                    f"  进度: {i + 1}/{len(dates)} ({sync_date}) — "
                    f"累计: 客户={total_customers}, 已计算={total_calculated}, 无规则={total_no_rule}"
                )

        print("\n📊 重新计算完成:")
        print(f"   总日期数: {len(dates)}")
        print(f"   总客户数: {total_customers}")
        print(f"   已计算费用: {total_calculated}")
        print(f"   无计费规则: {total_no_rule}")


if __name__ == "__main__":
    asyncio.run(recalc())
