"""重算 daily_consumptions 表中所有 multi+unified 模式的历史数据

用法:
    cd backend && python -m scripts.recalc_unified_costs
"""

import asyncio
import sys
from pathlib import Path

# 确保能导入 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.cost_calc import CostCalcService


async def main():
    # 1. 先用同步引擎查需要重算的日期
    sync_url = settings.database_url
    sync_engine = create_engine(sync_url)
    with sync_engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT DISTINCT dc.consumption_date
                FROM daily_consumptions dc
                JOIN pricing_rules pr ON dc.pricing_rule_id = pr.id
                WHERE dc.layer_type = 'multi'
                  AND pr.multi_floor_pricing_type = 'unified'
                  AND pr.deleted_at IS NULL
                ORDER BY dc.consumption_date
                """
            )
        )
        dates_to_recalc = [row[0] for row in result]
    sync_engine.dispose()

    if not dates_to_recalc:
        print("没有需要重算的 multi+unified 记录")
        return

    print(f"共 {len(dates_to_recalc)} 个日期需要重算:")
    for d in dates_to_recalc:
        print(f"  - {d}")

    # 2. 用异步引擎重算
    async_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    async_engine = create_async_engine(async_url)
    session_maker = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    service = CostCalcService(None)  # 先占位，后面逐个 session 赋值

    total_calculated = 0
    for d in dates_to_recalc:
        async with session_maker() as session:
            service.db = session
            result = await service.calculate_daily_cost(consumption_date=d)
            print(
                f"  {d}: total={result['total_customers']}, "
                f"calculated={result['calculated']}, no_rule={result['no_rule']}"
            )
            total_calculated += result["calculated"]

    await async_engine.dispose()
    print(f"\n完成！共重算 {total_calculated} 条记录")


if __name__ == "__main__":
    asyncio.run(main())
