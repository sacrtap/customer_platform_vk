"""一次性脚本：批量更新已有包年 PricingRule 的 unit_price 和 package_limits

执行方式：
    cd backend && python -m scripts.migrate_package_pricing_rules

逻辑：
    1. 查询所有 pricing_type='package' 且 deleted_at IS NULL 的 PricingRule
    2. 对每条规则，根据 package_type 查询对应的 PackagePlan
    3. 从 PackagePlan 填充 unit_price（日费 = base_fee / 365）和 package_limits
    4. 如果已存在 package_limits 且非空，跳过（除非 --force 参数）
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# 将 backend 目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models.billing import PackagePlan, PricingRule


async def migrate(force: bool = False):
    """执行批量迁移"""
    # 创建异步引擎
    db_url = settings.database_url
    if not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(db_url, echo=False)

    async with AsyncSession(engine) as session:
        # 1. 查询所有包年定价规则
        result = await session.execute(
            select(PricingRule).where(
                PricingRule.pricing_type == "package",
                PricingRule.deleted_at.is_(None),
            )
        )
        package_rules = result.scalars().all()

        if not package_rules:
            print("✅ 没有找到包年定价规则，无需迁移")
            return

        print(f"📋 找到 {len(package_rules)} 条包年定价规则")

        # 2. 查询所有活跃的 PackagePlan
        plan_result = await session.execute(
            select(PackagePlan).where(
                PackagePlan.deleted_at.is_(None),
                PackagePlan.status == "active",
            )
        )
        plans = {p.package_type: p for p in plan_result.scalars().all()}

        if not plans:
            print("⚠️  没有找到活跃的包年套餐（PackagePlan），无法填充数据")
            return

        print(f"📦 找到 {len(plans)} 个活跃套餐: {', '.join(plans.keys())}")

        # 3. 逐条更新
        updated = 0
        skipped = 0
        not_found = 0

        for rule in package_rules:
            package_type = rule.package_type
            if not package_type:
                print(f"  ⚠️  规则 ID={rule.id} 没有 package_type，跳过")
                not_found += 1
                continue

            plan = plans.get(package_type)
            if not plan:
                print(
                    f"  ⚠️  规则 ID={rule.id} 的 package_type='{package_type}' 未找到对应套餐，跳过"
                )
                not_found += 1
                continue

            # 检查是否已有 package_limits
            if rule.package_limits and not force:
                print(f"  ℹ️  规则 ID={rule.id} 已有 package_limits，跳过（使用 --force 覆盖）")
                skipped += 1
                continue

            # 计算填充数据
            base_fee = Decimal(str(plan.base_fee))
            is_unlimited = bool(plan.is_unlimited)
            limit_count = plan.limit_count

            # 超额单价
            if plan.over_limit_unit_price:
                over_limit_unit_price = Decimal(str(plan.over_limit_unit_price))
            elif limit_count:
                over_limit_unit_price = (base_fee / Decimal(limit_count)).quantize(Decimal("0.01"))
            else:
                over_limit_unit_price = None

            # 日费
            daily_fee = (base_fee / Decimal(365)).quantize(Decimal("0.01"))

            # package_limits
            package_limits = {
                "base_fee": float(base_fee),
                "is_unlimited": is_unlimited,
                "limit_count": limit_count,
                "over_limit_unit_price": float(over_limit_unit_price)
                if over_limit_unit_price
                else None,
            }

            # 执行更新
            rule.unit_price = daily_fee
            rule.package_limits = package_limits

            print(
                f"  ✅ 规则 ID={rule.id} (customer_id={rule.customer_id}, "
                f"package_type={package_type}): "
                f"日费={daily_fee}, 不限量={is_unlimited}, "
                f"限量={limit_count}, 超额单价={over_limit_unit_price}"
            )
            updated += 1

        await session.commit()

        print(f"\n📊 迁移完成: 更新={updated}, 跳过={skipped}, 未找到套餐={not_found}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        print("🔧 强制模式：已存在的 package_limits 也将被覆盖")
    asyncio.run(migrate(force=force))
