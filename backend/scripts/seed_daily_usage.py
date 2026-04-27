#!/usr/bin/env python3
"""
生成模拟每日用量数据脚本

为指定客户在指定结算周期内生成模拟的 daily_usage 数据，
用于测试结算明细自动生成功能。

用法:
    python scripts/seed_daily_usage.py
    python scripts/seed_daily_usage.py --customer-id 2 --start 2026-02-01 --end 2026-02-28
"""

import sys
import os
import argparse
import random
from datetime import date, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env 文件
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.billing import DailyUsage, PricingRule
from app.models.customers import Customer

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost/customer_platform",
)


def generate_daily_usage(
    session: Session,
    customer_id: int,
    period_start: date,
    period_end: date,
    device_types: list[str] = None,
    layer_type: str = "single",
) -> int:
    """
    生成模拟每日用量数据

    Args:
        session: 数据库会话
        customer_id: 客户 ID
        period_start: 开始日期
        period_end: 结束日期
        device_types: 设备类型列表，默认 ['X', 'N', 'L']
        layer_type: 层级类型，默认 'single'

    Returns:
        生成的记录数量
    """
    if device_types is None:
        device_types = ["X", "N", "L"]

    # 检查客户是否存在
    customer = session.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        print(f"❌ 客户 ID={customer_id} 不存在")
        return 0

    print(f"📊 为客户 [{customer.name}] (ID={customer_id}) 生成模拟用量数据")
    print(f"   结算周期: {period_start} ~ {period_end}")
    print(f"   设备类型: {device_types}")
    print(f"   层级类型: {layer_type}")

    # 查询客户已有的定价规则
    pricing_rules = (
        session.query(PricingRule)
        .filter(
            PricingRule.customer_id == customer_id,
            PricingRule.effective_date <= period_end,
            (PricingRule.expiry_date.is_(None)) | (PricingRule.expiry_date >= period_start),
        )
        .all()
    )

    rule_device_types = {r.device_type for r in pricing_rules}
    if rule_device_types:
        print(f"   ⚙️  检测到已配置的定价规则设备类型: {rule_device_types}")
        # 只为已配置规则的设备类型生成用量
        device_types = [dt for dt in device_types if dt in rule_device_types]
        if not device_types:
            print(f"   ⚠️  结算周期内无匹配的定价规则，使用所有设备类型")
            device_types = ["X", "N", "L"]

    # 生成每日用量
    current_date = period_start
    count = 0

    while current_date <= period_end:
        for device_type in device_types:
            # 根据设备类型生成不同的用量范围
            if device_type == "X":
                quantity = round(random.uniform(100, 500), 0)
            elif device_type == "N":
                quantity = round(random.uniform(50, 300), 0)
            else:  # L
                quantity = round(random.uniform(30, 200), 0)

            # 周末用量减半
            if current_date.weekday() >= 5:
                quantity = round(quantity * 0.5)

            usage = DailyUsage(
                customer_id=customer_id,
                usage_date=current_date,
                device_type=device_type,
                layer_type=layer_type,
                quantity=quantity,
            )
            session.add(usage)
            count += 1

        current_date += timedelta(days=1)

    return count


def main():
    parser = argparse.ArgumentParser(description="生成模拟每日用量数据")
    parser.add_argument(
        "--customer-id", type=int, default=2, help="客户 ID (默认: 2)"
    )
    parser.add_argument(
        "--start", type=str, default="2026-02-01", help="开始日期 (默认: 2026-02-01)"
    )
    parser.add_argument(
        "--end", type=str, default="2026-02-28", help="结束日期 (默认: 2026-02-28)"
    )
    parser.add_argument(
        "--layer-type", type=str, default="single", help="层级类型 (默认: single)"
    )
    parser.add_argument(
        "--reset", action="store_true", help="删除已有数据后重新生成"
    )
    parser.add_argument(
        "--no-random-seed", action="store_true", help="不设置随机种子（每次结果不同）"
    )

    args = parser.parse_args()

    # 设置随机种子以便结果可复现
    if not args.no_random_seed:
        random.seed(42)
        print("🔒 使用固定随机种子 (seed=42)，结果可复现")

    period_start = date.fromisoformat(args.start)
    period_end = date.fromisoformat(args.end)

    engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"))

    with Session(engine) as session:
        # 如果需要重置，删除已有数据
        if args.reset:
            deleted = (
                session.query(DailyUsage)
                .filter(
                    DailyUsage.customer_id == args.customer_id,
                    DailyUsage.usage_date >= period_start,
                    DailyUsage.usage_date <= period_end,
                )
                .delete()
            )
            session.commit()
            print(f"🗑️  已删除 {deleted} 条已有用量数据")

        # 生成数据
        count = generate_daily_usage(
            session=session,
            customer_id=args.customer_id,
            period_start=period_start,
            period_end=period_end,
            layer_type=args.layer_type,
        )

        session.commit()
        print(f"✅ 已生成 {count} 条模拟用量数据")


if __name__ == "__main__":
    main()
