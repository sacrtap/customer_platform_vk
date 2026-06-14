"""生成测试数据用于验证消耗分析功能"""

import asyncio
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.billing import PricingRule
from app.models.customers import Customer
from app.models.daily_consumption import DailyConsumption


async def generate_test_data():
    """生成测试数据"""
    # 创建异步数据库连接
    db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. 检查是否已有客户数据
        result = await db.execute(select(Customer).limit(5))
        customers = result.scalars().all()

        if not customers:
            print("❌ 数据库中没有客户数据，请先创建客户")
            return

        print(f"✅ 找到 {len(customers)} 个客户")

        # 2. 为每个客户创建计费规则
        pricing_rules = []
        for customer in customers:
            # 检查是否已有计费规则
            result = await db.execute(
                select(PricingRule).where(PricingRule.customer_id == customer.id)
            )
            existing_rule = result.scalar_one_or_none()

            if existing_rule:
                print(f"  - 客户 {customer.name} 已有计费规则")
                pricing_rules.append(existing_rule)
                continue

            # 创建新的计费规则
            rule = PricingRule(
                customer_id=customer.id,
                device_type="X",  # 默认设备类型
                layer_type="single",  # 默认楼层类型
                pricing_type="tiered",  # 阶梯定价
                unit_price=Decimal("100.00"),
                tiers=[
                    {"min": 0, "max": 100, "price": 10.00},
                    {"min": 100, "max": 500, "price": 8.00},
                    {"min": 500, "max": None, "price": 6.00},
                ],
                effective_date=date.today() - timedelta(days=365),
                expiry_date=None,
            )
            db.add(rule)
            pricing_rules.append(rule)
            print(f"  ✓ 为客户 {customer.name} 创建计费规则")

        await db.commit()

        # 3. 生成过去 30 天的消耗数据
        print("\n生成消耗数据...")
        start_date = date.today() - timedelta(days=30)
        device_types = ["X", "N", "L"]
        layer_types = ["single", "multi"]

        total_records = 0
        for customer in customers:
            for days_ago in range(30):
                consumption_date = start_date + timedelta(days=days_ago)

                # 随机生成 1-3 条记录（不同设备类型和楼层类型）
                num_records = random.randint(1, 3)
                for _ in range(num_records):
                    device_type = random.choice(device_types)
                    layer_type = random.choice(layer_types)

                    # 随机生成订单数量和费用
                    order_count = random.randint(10, 200)
                    total_cost = Decimal(str(round(random.uniform(500, 5000), 2)))

                    # 检查是否已存在
                    result = await db.execute(
                        select(DailyConsumption).where(
                            DailyConsumption.customer_id == customer.id,
                            DailyConsumption.consumption_date == consumption_date,
                            DailyConsumption.device_type == device_type,
                            DailyConsumption.layer_type == layer_type,
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        continue

                    # 创建消耗记录
                    consumption = DailyConsumption(
                        customer_id=customer.id,
                        consumption_date=consumption_date,
                        device_type=device_type,
                        layer_type=layer_type,
                        order_count=order_count,
                        total_cost=total_cost,
                        pricing_rule_id=pricing_rules[0].id if pricing_rules else None,
                        has_pricing_rule=True,
                    )
                    db.add(consumption)
                    total_records += 1

            print(f"  ✓ 为客户 {customer.name} 生成消耗数据")

        await db.commit()

        print(f"\n✅ 成功生成 {total_records} 条消耗记录")
        print(f"   时间范围: {start_date} 至 {date.today()}")
        print(f"   客户数量: {len(customers)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(generate_test_data())
