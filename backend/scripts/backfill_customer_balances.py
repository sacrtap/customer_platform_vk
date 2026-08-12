"""
回填客户余额记录 + 清理指向已软删客户的余额脏数据

背景：余额管理页只显示 9 个客户，而客户管理页默认条件下显示 362 个。
根因：
1. 存量客户在余额功能启用前创建，从未建立 customer_balances 记录
2. 8/7-8/8 批量创建的测试客户余额记录，其客户被软删后余额记录未同步清理

本脚本：
1. 物理删除指向已软删客户（customers.deleted_at IS NOT NULL）的余额记录
2. 为符合默认条件（正式账号 + 房产经纪/房产ERP/房产平台）的活跃客户
   回填 customer_balances 记录（余额 0，幂等 ON CONFLICT DO NOTHING）

用法：
    cd backend && .venv/bin/python scripts/backfill_customer_balances.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models.billing import CustomerBalance
from app.models.customers import Customer, CustomerProfile
from app.models.industry_type import IndustryType

# 与前端 useBalance.ts / useCustomerList.ts 默认条件保持一致
DEFAULT_ACCOUNT_TYPE = "正式账号"
DEFAULT_INDUSTRIES = ("房产经纪", "房产ERP", "房产平台")

# 使用同步引擎
sync_url = settings.database_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")


def _target_filter():
    """符合默认条件的活跃客户过滤条件（与余额/客户列表页一致）"""
    return [
        Customer.deleted_at.is_(None),
        Customer.account_type == DEFAULT_ACCOUNT_TYPE,
        IndustryType.name.in_(DEFAULT_INDUSTRIES),
    ]


def _target_stmt():
    """符合默认条件的活跃客户查询（JOIN profile + industry_type）"""
    return (
        select(Customer.id)
        .join(CustomerProfile, Customer.id == CustomerProfile.customer_id)
        .join(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="回填客户余额记录并清理脏数据")
    parser.add_argument("--dry-run", action="store_true", help="只统计不执行")
    args = parser.parse_args()

    engine = create_engine(sync_url)
    with Session(engine) as session:
        # 脏数据统计：指向已软删客户的余额记录
        dirty = (
            session.execute(
                select(func.count(CustomerBalance.id))
                .join(Customer, CustomerBalance.customer_id == Customer.id)
                .where(Customer.deleted_at.is_not(None))
            ).scalar()
            or 0
        )

        # 符合默认条件的活跃客户总数
        target_total = (
            session.execute(
                select(func.count()).select_from(_target_stmt().where(*_target_filter()).subquery())
            ).scalar()
            or 0
        )

        # 现有有效余额记录数
        existing = (
            session.execute(
                select(func.count(CustomerBalance.id)).where(CustomerBalance.deleted_at.is_(None))
            ).scalar()
            or 0
        )

        # 需回填的客户 ID 列表（排除已有余额记录者）
        backfill_ids = [
            row[0]
            for row in session.execute(
                _target_stmt().where(
                    *_target_filter(),
                    ~Customer.id.in_(
                        select(CustomerBalance.customer_id).where(
                            CustomerBalance.deleted_at.is_(None)
                        )
                    ),
                )
            ).all()
        ]

        print("=" * 70)
        print("客户余额回填与清理" + ("（dry-run 模式）" if args.dry_run else ""))
        print("=" * 70)
        print(f"符合默认条件的活跃客户数:          {target_total}")
        print(f"现有有效余额记录数:                {existing}")
        print(f"需回填数:                          {len(backfill_ids)}")
        print(f"指向已软删客户的脏数据:            {dirty}")

        if args.dry_run:
            if backfill_ids:
                print(f"\n将回填的客户 ID 范围: {min(backfill_ids)} ~ {max(backfill_ids)}")
            print("\n[dry-run] 未执行任何修改。")
            return

        # 1. 物理删除脏数据（指向已软删客户的余额记录）
        if dirty:
            deleted = session.execute(
                delete(CustomerBalance).where(
                    CustomerBalance.customer_id.in_(
                        select(Customer.id).where(Customer.deleted_at.is_not(None))
                    )
                )
            )
            print(f"\n删除脏数据: {deleted.rowcount} 条")

        # 2. 回填余额记录（幂等：ON CONFLICT DO NOTHING）
        if backfill_ids:
            stmt = pg_insert(CustomerBalance).values([{"customer_id": cid} for cid in backfill_ids])
            stmt = stmt.on_conflict_do_nothing(index_elements=["customer_id"])
            session.execute(stmt)
            print(f"回填余额记录: {len(backfill_ids)} 条")

        session.commit()

        # 验证：回填后符合条件客户数
        after = (
            session.execute(
                select(func.count(Customer.id))
                .select_from(CustomerBalance)
                .join(Customer, CustomerBalance.customer_id == Customer.id)
                .where(
                    CustomerBalance.deleted_at.is_(None),
                    Customer.deleted_at.is_(None),
                    Customer.account_type == DEFAULT_ACCOUNT_TYPE,
                    Customer.id.in_(
                        select(CustomerProfile.customer_id)
                        .join(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
                        .where(IndustryType.name.in_(DEFAULT_INDUSTRIES))
                    ),
                )
            ).scalar()
            or 0
        )
        print(f"验证: 余额页默认条件应显示 {after} 个客户（预期 {target_total}）")


if __name__ == "__main__":
    main()
