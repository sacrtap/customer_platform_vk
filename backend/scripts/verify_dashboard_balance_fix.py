"""
验证仪表盘总余额计算修复
对比修复前后的 SQL 查询结果
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from calendar import monthrange
from datetime import date, datetime

from sqlalchemy import and_, case, create_engine, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.billing import CustomerBalance, Invoice
from app.models.customers import Customer

# 使用同步引擎
sync_url = settings.database_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
engine = create_engine(sync_url)


def get_old_query_result(session: Session):
    """旧查询（有笛卡尔积问题）"""
    today = datetime.utcnow()
    current_month_start = date(today.year, today.month, 1)
    current_month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    stats_stmt = (
        select(
            func.count(
                case(
                    (
                        and_(
                            Customer.deleted_at.is_(None),
                        ),
                        Customer.id,
                    )
                )
            ).label("total_customers"),
            func.count(
                case(
                    (
                        and_(
                            Customer.deleted_at.is_(None),
                            Customer.is_key_customer,
                        ),
                        Customer.id,
                    )
                )
            ).label("key_customers"),
            func.sum(CustomerBalance.total_amount).label("total_balance"),
            func.sum(CustomerBalance.real_amount).label("real_balance"),
            func.sum(CustomerBalance.bonus_amount).label("bonus_balance"),
            func.count(
                case(
                    (
                        and_(
                            Invoice.period_start >= current_month_start,
                            Invoice.period_end <= current_month_end,
                        ),
                        Invoice.id,
                    )
                )
            ).label("month_invoice_count"),
            func.count(case((Invoice.status == "pending_customer", Invoice.id))).label(
                "pending_confirmation"
            ),
            func.sum(
                case(
                    (
                        and_(
                            Invoice.period_start >= current_month_start,
                            Invoice.period_end <= current_month_end,
                            Invoice.status != "cancelled",
                        ),
                        Invoice.total_amount,
                    )
                )
            ).label("month_consumption"),
        )
        .select_from(Customer)
        .outerjoin(
            CustomerBalance,
            and_(
                Customer.id == CustomerBalance.customer_id,
                CustomerBalance.deleted_at.is_(None),
            ),
        )
        .outerjoin(Invoice, Customer.id == Invoice.customer_id)
        .where(Customer.deleted_at.is_(None))
    )

    result = session.execute(stats_stmt).first()
    return {
        "total_customers": result.total_customers or 0,  # pyright: ignore[reportOptionalMemberAccess]
        "key_customers": result.key_customers or 0,  # pyright: ignore[reportOptionalMemberAccess]
        "total_balance": float(result.total_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
        "real_balance": float(result.real_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
        "bonus_balance": float(result.bonus_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
        "month_invoice_count": result.month_invoice_count or 0,  # pyright: ignore[reportOptionalMemberAccess]
        "pending_confirmation": result.pending_confirmation or 0,  # pyright: ignore[reportOptionalMemberAccess]
        "month_consumption": float(result.month_consumption or 0),  # pyright: ignore[reportOptionalMemberAccess]
    }


def get_new_query_result(session: Session):
    """新查询（修复笛卡尔积问题）"""
    today = datetime.utcnow()
    current_month_start = date(today.year, today.month, 1)
    current_month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    # 查询 1: 客户统计 + 余额
    balance_stmt = (
        select(
            func.count(Customer.id).label("total_customers"),
            func.count(
                case(
                    (Customer.is_key_customer, Customer.id),
                )
            ).label("key_customers"),
            func.sum(CustomerBalance.total_amount).label("total_balance"),
            func.sum(CustomerBalance.real_amount).label("real_balance"),
            func.sum(CustomerBalance.bonus_amount).label("bonus_balance"),
        )
        .select_from(Customer)
        .outerjoin(
            CustomerBalance,
            and_(
                Customer.id == CustomerBalance.customer_id,
                CustomerBalance.deleted_at.is_(None),
            ),
        )
        .where(Customer.deleted_at.is_(None))
    )
    balance_result = session.execute(balance_stmt).first()

    # 查询 2: 结算单统计
    invoice_stmt = (
        select(
            func.count(
                case(
                    (
                        and_(
                            Invoice.period_start >= current_month_start,
                            Invoice.period_end <= current_month_end,
                        ),
                        Invoice.id,
                    )
                )
            ).label("month_invoice_count"),
            func.count(case((Invoice.status == "pending_customer", Invoice.id))).label(
                "pending_confirmation"
            ),
            func.sum(
                case(
                    (
                        and_(
                            Invoice.period_start >= current_month_start,
                            Invoice.period_end <= current_month_end,
                            Invoice.status != "cancelled",
                        ),
                        Invoice.total_amount,
                    )
                )
            ).label("month_consumption"),
        )
        .select_from(Customer)
        .outerjoin(Invoice, Customer.id == Invoice.customer_id)
        .where(Customer.deleted_at.is_(None))
    )
    invoice_result = session.execute(invoice_stmt).first()

    return {
        "total_customers": balance_result.total_customers or 0,  # pyright: ignore[reportOptionalMemberAccess]
        "key_customers": balance_result.key_customers or 0,  # pyright: ignore[reportOptionalMemberAccess]
        "total_balance": float(balance_result.total_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
        "real_balance": float(balance_result.real_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
        "bonus_balance": float(balance_result.bonus_balance or 0),  # pyright: ignore[reportOptionalMemberAccess]
        "month_invoice_count": invoice_result.month_invoice_count or 0,  # pyright: ignore[reportOptionalMemberAccess]
        "pending_confirmation": invoice_result.pending_confirmation or 0,  # pyright: ignore[reportOptionalMemberAccess]
        "month_consumption": float(invoice_result.month_consumption or 0),  # pyright: ignore[reportOptionalMemberAccess]
    }


def main():
    print("=" * 80)
    print("仪表盘总余额计算修复验证")
    print("=" * 80)
    print()

    with Session(engine) as session:
        print("执行旧查询（有笛卡尔积问题）...")
        old_result = get_old_query_result(session)
        print("✓ 旧查询完成")
        print()

        print("执行新查询（修复后）...")
        new_result = get_new_query_result(session)
        print("✓ 新查询完成")
        print()

    print("=" * 80)
    print("结果对比")
    print("=" * 80)
    print()
    print(f"{'指标':<20} {'旧查询':>15} {'新查询':>15} {'差异':>15}")
    print("-" * 80)

    for key in old_result.keys():
        old_val = old_result[key]
        new_val = new_result[key]
        diff = old_val - new_val
        diff_pct = (diff / old_val * 100) if old_val != 0 else 0

        print(f"{key:<20} {old_val:>15.2f} {new_val:>15.2f} {diff:>+15.2f} ({diff_pct:>+.1f}%)")

    print()
    print("=" * 80)
    print("分析")
    print("=" * 80)
    print()

    if old_result["total_balance"] != new_result["total_balance"]:
        diff = old_result["total_balance"] - new_result["total_balance"]
        print(f"⚠️  发现差异：总余额相差 {diff:.2f} 元")
        print(f"   旧值（错误）：{old_result['total_balance']:.2f} 元")
        print(f"   新值（正确）：{new_result['total_balance']:.2f} 元")
        print()
        print("这说明数据库中存在多发票客户，旧查询产生了笛卡尔积效应。")
        print("新查询已修复此问题，显示的是正确的余额总和。")
    else:
        print("✓ 两个查询结果一致")
        print("说明当前数据库中没有多发票客户，或者笛卡尔积效应不明显。")

    print()


if __name__ == "__main__":
    main()
