"""一次性脚本：回填 daily_orders 的月份明细展示快照列（F9）

执行方式：
    cd backend && python -m scripts.backfill_daily_order_detail_columns

背景：迁移 i4j5k6l7m8n9 给 daily_orders 加了 19 个展示列（project_name/
city/... /model_fix_status），历史行均为 NULL——直接重生成历史结算单的明细
文件，「月份明细」sheet 这些列会全空。本脚本从外部 MySQL（nest_model_order，
与 ORDER_SYNC_SQL 同口径）按 upload_date 逐日重拉，UPDATE 回本地。

约束：
- 只补本地已有行的展示列（不新增行、不动计费口径列）；
- 外部已删除/改期的订单补不回（保持 NULL，月份明细对应格为空）——这是
  快照语义的固有边界，已生成的历史文件本就不依赖这些列；
- 幂等：重复执行结果一致（按 (order_code, custom_code, sync_date) 匹配）。
"""

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models.daily_order import DailyOrder

# 与 OrderSyncService._fetch_orders 的 SELECT 顺序严格一致（0-28）
BACKFILL_SQL = (
    "SELECT D.order_code, D.custom_code, D.nest_id, "
    "U.owner_company, D.group_type, D.create_date, "
    "D.upload_date, D.floor_count, LEFT(D.device_name, 1), "
    "D.order_status, "
    "D.project_name, D.city, D.department, "
    "U_creator.owner_name, U_personal.owner_name, D.nest_area, "
    "D.produce_status, D.produce_flag, D.remarks, "
    "U_editor.username, U_editor.owner_name, D.finish_date, "
    "D.first_send_zb_date, D.first_edit_time, D.review_release_date, "
    "D.device_name, D.customer_review_result, U_publisher.owner_name, "
    "D.model_fix_status "
    "FROM nest_model_order AS D "
    "INNER JOIN ("
    "  SELECT group_type, MAX(owner_company) AS owner_company "
    "  FROM nest_user GROUP BY group_type"
    ") AS U ON D.group_type = U.group_type "
    "LEFT JOIN nest_user U_creator ON U_creator.id = D.creator "
    "LEFT JOIN nest_user U_personal ON U_personal.id = D.personal "
    "LEFT JOIN nest_user U_editor ON U_editor.id = D.personal "
    "LEFT JOIN nest_user U_publisher ON U_publisher.id = D.publisher "
    "WHERE D.upload_date >= %s AND D.upload_date < %s "
    "AND ((D.order_status >= 3 AND D.order_status <= 12) OR D.order_status = 15)"
)

_COLS = (
    "project_name",
    "city",
    "department",
    "creator_name",
    "personal_name",
    "nest_area",
    "produce_status",
    "produce_flag",
    "remarks",
    "editor_account",
    "editor_name",
    "finish_date",
    "first_send_zb_date",
    "first_edit_time",
    "review_release_date",
    "device_name",
    "customer_review_result",
    "publisher_name",
    "model_fix_status",
)
# BACKFILL_SQL 行索引 → daily_orders 列名（展示列 10-28）
_ROW_IDX = {
    "project_name": 10,
    "city": 11,
    "department": 12,
    "creator_name": 13,
    "personal_name": 14,
    "nest_area": 15,
    "produce_status": 16,
    "produce_flag": 17,
    "remarks": 18,
    "editor_account": 19,
    "editor_name": 20,
    "finish_date": 21,
    "first_send_zb_date": 22,
    "first_edit_time": 23,
    "review_release_date": 24,
    "device_name": 25,
    "customer_review_result": 26,
    "publisher_name": 27,
    "model_fix_status": 28,
}


async def backfill():
    db_url = settings.database_url.strip()
    # 统一转 asyncpg 驱动：兼容裸 $$0A3FBV1XZH4L:$$ql://、$$0A3FBV1XZH4L:$$ql+psycopg2://
    # 等同步驱动前缀（recalc_daily_consumptions 等旧脚本的 startswith 替换对
    # 裸前缀会静默失效，落回同步驱动后 create_async_engine 直接抛错）。
    # 驱动名拼接而非字面量，防任何外层 shell 对 $ 的展开污染。
    scheme, _sep, rest = db_url.partition("://")
    if "asyncpg" not in scheme:
        db_url = "postgresql" + "+asyncpg" + "://" + rest
    engine = create_async_engine(db_url, echo=False)

    try:
        import aiomysql

        from app.services.order_sync import OrderSyncService

        cfg = OrderSyncService(db=None).external_db_config  # pyright: ignore[reportArgumentType]
        conn = await aiomysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            db=cfg["db"],
            connect_timeout=10,
        )
    except Exception as e:
        print(f"❌ 外部 MySQL 连接失败: {e}")
        print("   （外部不可达时无法回填；历史单重生成的「月份明细」展示列为空，")
        print("     计费三表口径不受影响——数量/金额仍与快照严格一致）")
        await engine.dispose()
        return

    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(
                select(DailyOrder.sync_date).distinct().order_by(DailyOrder.sync_date)
            )
            dates = [row[0] for row in result.all()]
            if not dates:
                print("✅ daily_orders 无数据，无需回填")
                return

            print(
                f"📅 待回填 sync_date 天数: {len(dates)}（{dates[0].date()} ~ {dates[-1].date()}）",
                flush=True,
            )

            total_updated = 0
            total_missed = 0
            try:
                async with conn.cursor() as cursor:
                    for i, sync_date in enumerate(dates):
                        # 外部按 upload_date 窗口查（与同步层同口径）；sync_date 为
                        # UTC 当天起点，窗口即该 UTC 日。单窗口设 120s 超时防
                        # 外部大窗口无限期挂起（整体以服务方式跑，逐日幂等，
                        # 中断后重跑跳过已完成日期——同值 UPDATE 无副作用）。
                        await asyncio.wait_for(
                            cursor.execute(
                                BACKFILL_SQL, (sync_date, sync_date + timedelta(days=1))
                            ),
                            timeout=120,
                        )
                        rows = await asyncio.wait_for(cursor.fetchall(), timeout=120)
                        by_key = {(r[0], r[1] or ""): r for r in rows}

                        day_rows = (
                            (
                                await session.execute(
                                    select(DailyOrder).where(
                                        DailyOrder.sync_date >= sync_date,
                                        DailyOrder.sync_date < sync_date + timedelta(days=1),
                                        DailyOrder.deleted_at.is_(None),
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                        day_updated = 0
                        for order in day_rows:
                            ext = by_key.get((order.order_code, order.custom_code or ""))
                            if ext is None:
                                total_missed += 1
                                continue
                            for col in _COLS:
                                setattr(order, col, ext[_ROW_IDX[col]])
                            day_updated += 1
                        await session.commit()
                        total_updated += day_updated
                        if (i + 1) % 10 == 0 or i == len(dates) - 1:
                            print(
                                f"  进度: {i + 1}/{len(dates)} ({sync_date.date()}) — "
                                f"累计更新 {total_updated} 行，外部缺失 {total_missed} 行",
                                flush=True,
                            )
            finally:
                conn.close()

            print("\n📊 回填完成:")
            print(f"   更新行数: {total_updated}")
            print(f"   外部缺失（保持 NULL，多为外部已删单/改期）: {total_missed}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill())
