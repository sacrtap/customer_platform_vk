"""订单同步服务"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

import aiomysql
from sqlalchemy import CursorResult, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.customers import Customer
from app.models.daily_order import DailyOrder
from app.services.dto import SyncDetail, SyncResult
from app.utils.timezone import CST, external_naive_to_utc

logger = logging.getLogger(__name__)


class OrderSyncService:
    """订单同步服务"""

    def __init__(self, db: AsyncSession, external_engine: Optional[AsyncEngine] = None):
        self.db = db
        self.external_engine = external_engine

    @property
    def external_db_config(self) -> Dict[str, Any]:
        """外部 MySQL 连接配置"""
        from app.config import settings

        url = settings.external_mysql_url
        if not url:
            raise ValueError("外部 MySQL 配置缺失：EXTERNAL_MYSQL_URL 未设置")

        # mysql://user:password@host:port/dbname
        parts = url.replace("mysql://", "").split("@")
        user_pass = parts[0].split(":")
        host_port_db = parts[1].split("/")
        host_port = host_port_db[0].split(":")

        config = {
            "host": host_port[0],
            "port": int(host_port[1]) if len(host_port) > 1 else 3306,
            "user": user_pass[0],
            "password": user_pass[1] if len(user_pass) > 1 else "",
            "db": host_port_db[1] if len(host_port_db) > 1 else "",
        }

        # 验证必需字段（使用 key 存在性检查，避免空密码误判）
        required_keys = ["host", "port", "user", "db"]
        missing = [k for k in required_keys if k not in config]
        if missing:
            raise ValueError(f"外部 MySQL 配置缺失：{', '.join(missing)}")

        return config

    async def sync_orders(
        self, sync_date: datetime, detail_collector: Optional[List[SyncDetail]] = None
    ) -> SyncResult:
        """同步指定日期的订单

        如果外部数据源连接失败，异常会向上传播，由调用方（execute_task）的
        逐天异常处理器捕获并记录 failed_count。

        Args:
            sync_date: 同步日期（UTC datetime）
            detail_collector: 可选执行明细收集器（注入后记录同步过程明细，
                默认 None 不记录，行为与旧版一致）
        """
        # 1. 获取订单（异常时向上传播，不吞掉错误）
        try:
            orders = await self._fetch_orders(sync_date)
        except Exception as e:
            if detail_collector is not None:
                detail_collector.append(
                    SyncDetail(
                        sync_date=sync_date.astimezone(CST).date(),
                        level="error",
                        category="order_fetch",
                        message=f"外部数据源拉取订单失败: {type(e).__name__}: {e}",
                    )
                )
            raise

        if not orders:
            return SyncResult(
                success=0, failed=0, skipped=0, unmatched=0, message="没有新订单需要同步"
            )

        # 2. 清空该日期的所有旧订单
        await self._clear_orders(sync_date)

        # 3. 匹配客户并保存
        return await self._match_and_save(
            orders=orders, sync_date=sync_date, detail_collector=detail_collector
        )

    async def _fetch_orders(self, sync_date: datetime) -> List[Dict]:
        """从外部 MySQL 获取订单

        通过 JOIN nest_user 获取公司名称，使用 upload_date 范围匹配日期
        （避免 DATE() 函数包裹导致索引失效），通过 order_status 条件过滤
        需要结算的订单，使用 LEFT(device_name, 1) 提取设备类型首字符。
        """
        # 计算 upload_date 的日期范围（避免 DATE() 函数导致全表扫描）
        # sync_date 已经是 UTC datetime 的当天开始时刻
        start_dt = sync_date  # UTC 当天开始
        end_dt = sync_date + timedelta(days=1)  # UTC 次日开始

        # 统一 SQL（两条路径共用）
        # SELECT 字段顺序（F9：新增 19 列月份明细展示快照 + create_date/
        # upload_date 由 DATE() 改为原值 datetime，时刻不再丢失；
        # 2026-11-10：新增 nest.created 作为「处理完成时间」数据源——
        # 原取 D.finish_date 恒为 NULL，示例表口径为房源主表 created）：
        #   0: order_code, 1: custom_code, 2: nest_id, 3: owner_company,
        #   4: group_type, 5: create_date, 6: upload_date, 7: floor_count,
        #   8: device_type, 9: order_status,
        #   10: project_name, 11: city, 12: department, 13: creator_name,
        #   14: personal_name, 15: nest_area, 16: produce_status,
        #   17: produce_flag, 18: remarks, 19: editor_account,
        #   20: editor_name, 21: finish_date, 22: first_send_zb_date,
        #   23: first_edit_time, 24: review_release_date, 25: device_name,
        #   26: customer_review_result, 27: publisher_name, 28: model_fix_status,
        #   29: nest_created
        # 结算范围：order_status >= 3 AND order_status <= 12, OR = 15
        # 不再过滤 nest_id（空 nest_id 的订单也纳入结算）
        STATUS_COND = "((D.order_status >= 3 AND D.order_status <= 12) OR D.order_status = 15)"
        DETAIL_SELECT = (
            "D.order_code, D.custom_code, D.nest_id, "
            "U.owner_company, D.group_type, D.create_date, "
            "D.upload_date, D.floor_count, LEFT(D.device_name, 1), "
            "D.order_status, "
            "D.project_name, D.city, D.department, "
            "U_creator.owner_name, U_personal.owner_name, D.nest_area, "
            "D.produce_status, D.produce_flag, D.remarks, "
            "U_editor.username, U_editor.owner_name, D.finish_date, "
            "D.first_send_zb_date, D.first_edit_time, D.review_release_date, "
            "D.device_name, D.customer_review_result, U_publisher.owner_name, "
            "D.model_fix_status, "
            "N.created AS nest_created "
        )
        # 4 个人名/账号 JOIN（与月份明细 DETAIL_SQL 同口径）：creator / personal
        # （personal 同时充当 editor，与月度明细的两个别名一致）/ publisher
        # + nest 房源主表（2026-11-10：「处理完成时间」= nest.created 原值；
        #   nest_id 为空或 nest 表无对应行时 LEFT JOIN 留空，属正常语义）
        USER_JOINS = (
            "LEFT JOIN nest_user U_creator ON U_creator.id = D.creator "
            "LEFT JOIN nest_user U_personal ON U_personal.id = D.personal "
            "LEFT JOIN nest_user U_editor ON U_editor.id = D.personal "
            "LEFT JOIN nest_user U_publisher ON U_publisher.id = D.publisher "
            "LEFT JOIN nest N ON N.nest_id = D.nest_id "
        )
        SQL_ENGINE = (
            f"SELECT {DETAIL_SELECT} "
            "FROM nest_model_order AS D "
            "INNER JOIN ("
            "  SELECT group_type, MAX(owner_company) AS owner_company "
            "  FROM nest_user GROUP BY group_type"
            ") AS U ON D.group_type = U.group_type "
            f"{USER_JOINS}"
            f"WHERE D.upload_date >= :start AND D.upload_date < :end "
            f"AND {STATUS_COND}"
        )
        SQL_AIOMYSQL = (
            f"SELECT {DETAIL_SELECT} "
            "FROM nest_model_order AS D "
            "INNER JOIN ("
            "  SELECT group_type, MAX(owner_company) AS owner_company "
            "  FROM nest_user GROUP BY group_type"
            ") AS U ON D.group_type = U.group_type "
            f"{USER_JOINS}"
            f"WHERE D.upload_date >= %s AND D.upload_date < %s "
            f"AND {STATUS_COND}"
        )

        def _as_utc(value):
            """外部 naive datetime（UTC 墙钟）→ aware UTC（共享工具）。

            外部 MySQL datetime 列实测为 UTC 墙钟（SZZY_1794137638
            upload_date 02:10:28 naive ↔ 业务示例表 CST 10:10:28，
            2026-11-10 对照实证）。naive 直落 timestamptz 会被 PG 服务端
            按 Asia/Shanghai 解释，绝对时刻少 8 小时，叠加显示层未转 CST
            共差 16 小时——读取侧显式标注 UTC。sync_date 由
            local_date_to_utc_start 生成，本就 aware，不走此路径。
            """
            return external_naive_to_utc(value)

        def _rows_to_dicts(rows):
            return [
                {
                    "order_code": row[0],
                    "custom_code": row[1],
                    "nest_id": row[2],
                    "company_name": row[3],
                    "group_type": row[4],  # Keep as int for customer matching
                    "create_date": _as_utc(row[5]),
                    "upload_date": _as_utc(row[6]),
                    "floor_count": row[7],
                    "device_type": row[8],
                    "order_status": row[9],
                    # F9 月份明细展示列快照（原值落库，清洗在 Excel 写入侧）
                    "project_name": row[10],
                    "city": row[11],
                    "department": row[12],
                    "creator_name": row[13],
                    "personal_name": row[14],
                    "nest_area": row[15],
                    "produce_status": row[16],
                    "produce_flag": row[17],
                    "remarks": row[18],
                    "editor_account": row[19],
                    "editor_name": row[20],
                    "finish_date": _as_utc(row[21]),
                    "first_send_zb_date": _as_utc(row[22]),
                    "first_edit_time": _as_utc(row[23]),
                    "review_release_date": _as_utc(row[24]),
                    "device_name": row[25],
                    "customer_review_result": row[26],
                    "publisher_name": row[27],
                    "model_fix_status": row[28],
                    # 「处理完成时间」= 房源主表 created（2026-11-10；原
                    # finish_date 恒 NULL，示例表口径即此列）
                    "nest_created": _as_utc(row[29]),
                }
                for row in rows
            ]

        if self.external_engine:
            from sqlalchemy.sql import text

            async with self.external_engine.connect() as conn:
                result = await conn.execute(text(SQL_ENGINE), {"start": start_dt, "end": end_dt})
                return _rows_to_dicts(result.fetchall())
        else:
            config = self.external_db_config
            conn = await asyncio.wait_for(
                aiomysql.connect(
                    host=config["host"],
                    port=config["port"],
                    user=config["user"],
                    password=config["password"],
                    db=config["db"],
                    connect_timeout=10,
                ),
                timeout=15,
            )
            try:
                async with conn.cursor() as cursor:
                    await asyncio.wait_for(
                        cursor.execute(SQL_AIOMYSQL, (start_dt, end_dt)),
                        timeout=30,
                    )
                    rows = await asyncio.wait_for(
                        cursor.fetchall(),
                        timeout=30,
                    )
                    return _rows_to_dicts(rows)
            finally:
                if conn:
                    conn.close()

    async def _clear_orders(self, sync_date: datetime) -> None:
        """清空指定日期的所有订单（按 sync_date 范围删除，与唯一约束一致）"""
        from sqlalchemy import delete

        day_end = sync_date + timedelta(days=1)
        result = await self.db.execute(
            delete(DailyOrder).where(
                DailyOrder.sync_date >= sync_date,
                DailyOrder.sync_date < day_end,
            )
        )
        await self.db.commit()
        logger.info(f"已清空 {sync_date} 的 {cast(CursorResult[Any], result).rowcount} 条订单记录")

    async def _match_and_save(
        self,
        orders: List[Dict],
        sync_date: datetime,
        detail_collector: Optional[List[SyncDetail]] = None,
    ) -> SyncResult:
        """匹配客户并保存订单"""
        result = SyncResult()
        saved_orders = []  # 收集成功保存的订单
        seen_keys = set()  # 内存级去重，防止同一 (order_code, sync_date) 重复插入
        # 成功明细按客户聚合：customer_id -> {"customer_name", "count"}
        success_by_customer: Dict[int, Dict[str, Any]] = {}

        # 注意：清空逻辑已移至 sync_orders 入口

        def _emit(level: str, category: str, message: str, **kwargs) -> None:
            if detail_collector is not None:
                detail_collector.append(
                    SyncDetail(
                        # sync_date 为 UTC datetime（本地日期的 UTC 起点），
                        # 须转回 CST 本地日期与任务级明细（task.start_date 本地 date）保持一致
                        sync_date=sync_date.astimezone(CST).date(),
                        level=level,
                        category=category,
                        message=message,
                        **kwargs,
                    )
                )

        for order in orders:
            order_code = order.get("order_code")
            try:
                # 检查本批次是否已处理过相同的 (order_code, custom_code, sync_date)
                # （F8：同一订单号派给多个房源时各自成行、各自计费；
                # custom_code 为空时按订单号语义归一，与唯一索引 COALESCE 一致）
                dedup_key = (order_code, order.get("custom_code") or "", sync_date)
                if dedup_key in seen_keys:
                    result.skipped += 1
                    continue

                # 匹配客户（使用独立方法）
                customer = await self._match_customer(order)
                if customer is None:
                    result.unmatched += 1
                    _emit(
                        "warning",
                        "order_match",
                        "订单未匹配到内部客户（外部客户ID={}，公司名={}）".format(
                            order.get("group_type") or "未知",
                            order.get("company_name") or "未知",
                        ),
                        external_customer_id=str(order.get("group_type"))
                        if order.get("group_type") is not None
                        else None,
                        company_name=order.get("company_name"),
                        order_code=order_code,
                    )
                    continue

                # 检查订单是否已存在（键与唯一索引 uq_order_custom_sync_date 一致：
                # order_code + COALESCE(custom_code, '') + 当天窗口。F8：同一订单号
                # 的不同房源行不是重复订单，各自入库）
                existing = await self.db.execute(
                    select(DailyOrder).where(
                        DailyOrder.order_code == order_code,
                        func.coalesce(DailyOrder.custom_code, "")
                        == (order.get("custom_code") or ""),
                        DailyOrder.sync_date >= sync_date,
                        DailyOrder.sync_date < sync_date + timedelta(days=1),
                    )
                )
                if existing.scalar_one_or_none():
                    result.skipped += 1
                    continue

                # 创建订单记录但不立即提交
                daily_order = DailyOrder(
                    order_code=order_code,
                    custom_code=order.get("custom_code"),
                    nest_id=order.get("nest_id"),
                    company_name=order.get("company_name"),
                    group_type=str(order.get("group_type"))
                    if order.get("group_type") is not None
                    else None,
                    customer_id=customer.id,
                    create_date=order.get("create_date"),
                    upload_date=order.get("upload_date"),
                    order_status=order.get("order_status"),
                    floor_count=order.get("floor_count"),
                    device_type=order.get("device_type"),
                    sync_date=sync_date,
                    # F9 月份明细展示列快照（原值落库，清洗在 Excel 写入侧）
                    project_name=order.get("project_name"),
                    city=order.get("city"),
                    department=order.get("department"),
                    creator_name=order.get("creator_name"),
                    personal_name=order.get("personal_name"),
                    nest_area=order.get("nest_area"),
                    produce_status=order.get("produce_status"),
                    produce_flag=order.get("produce_flag"),
                    remarks=order.get("remarks"),
                    editor_account=order.get("editor_account"),
                    editor_name=order.get("editor_name"),
                    finish_date=order.get("finish_date"),
                    first_send_zb_date=order.get("first_send_zb_date"),
                    first_edit_time=order.get("first_edit_time"),
                    review_release_date=order.get("review_release_date"),
                    device_name=order.get("device_name"),
                    customer_review_result=order.get("customer_review_result"),
                    publisher_name=order.get("publisher_name"),
                    model_fix_status=order.get("model_fix_status"),
                    # 「处理完成时间」数据源（2026-11-10）：外部 nest.created，
                    # 原取 finish_date 恒 NULL
                    nest_created=order.get("nest_created"),
                )
                seen_keys.add(dedup_key)
                saved_orders.append(daily_order)
                result.success += 1

                # 成功明细按客户聚合
                if customer.id in success_by_customer:
                    success_by_customer[customer.id]["count"] += 1
                else:
                    success_by_customer[customer.id] = {
                        "customer_name": customer.name,
                        "count": 1,
                    }

            except Exception as e:
                # 捕获匹配客户时的异常
                logger.error("处理订单失败 %s: %s", order_code, e)
                result.failed += 1
                _emit(
                    "error",
                    "order_save",
                    f"订单处理失败: {type(e).__name__}: {e}",
                    company_name=order.get("company_name"),
                    order_code=order_code,
                )

        # 统一提交所有成功的订单
        if saved_orders:
            for order_obj in saved_orders:
                self.db.add(order_obj)
            try:
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                logger.error("批量提交订单失败: %s", e)
                # 将已成功的订单标记为失败
                result.failed += len(saved_orders)
                result.success -= len(saved_orders)
                _emit(
                    "error",
                    "order_save",
                    f"批量提交 {len(saved_orders)} 条订单失败: {type(e).__name__}: {e}",
                )
                success_by_customer.clear()

        # 成功明细按客户生成 info 记录
        for customer_id, agg in success_by_customer.items():
            _emit(
                "info",
                "order_save",
                f"成功同步 {agg['count']} 条订单",
                customer_id=customer_id,
                customer_name=agg["customer_name"],
                record_count=agg["count"],
            )

        # 跨日迁移清理（F6+F8）：订单 upload_date 跨日后，其 daily_orders 行仍留在旧
        # sync_date（唯一索引 (order_code, custom_code, sync_date) 允许同一订单码的
        # 不同房源行存在于不同日期）。本批订单（订单号+房源）若在「非当天窗口」
        # 存在旧行，即发生了跨日迁移——删除旧行并重算受影响旧日消耗
        # （cost_calc 先删后建，幂等）。
        if saved_orders:
            await self._migrate_cross_day_orders(
                sync_date=sync_date,
                saved_orders=saved_orders,
                detail_collector=detail_collector,
                emit=_emit,
            )

        # 设置结果消息
        if result.failed > 0 and result.success > 0:
            result.message = "部分同步失败"
        elif result.failed > 0:
            result.message = "同步失败"
        else:
            result.message = "同步完成"

        return result

    async def _migrate_cross_day_orders(
        self,
        sync_date: datetime,
        saved_orders: List[DailyOrder],
        detail_collector: Optional[List[SyncDetail]],
        emit,
    ) -> None:
        """跨日迁移清理（F6+F8）

        订单 upload_date 跨日后，同一 (order_code, custom_code) 会出现在新日期的
        同步批次中，而旧日期的 daily_orders 行仍在（唯一索引不禁跨日期重复）。
        残留行会让旧日消耗统计多计。

        动作：删除本批订单（订单号+房源键）在「非当天窗口 [sync_date, sync_date+1d)」
        的残留行 → 按 (customer_id, 旧日) 聚合 → 逐旧日重算消耗（先删后建，幂等）。
        同订单号的其他房源行不属于本批订单，不删（F8）。
        异常上抛（sync_orders 不吞错误，execute_task 按天记 failed）。
        """
        from sqlalchemy import delete

        day_end = sync_date + timedelta(days=1)
        # 删除键与唯一索引一致（F8）：(order_code, COALESCE(custom_code, ''))。
        # 同订单号的其他房源行不属于本批订单，不得互删——旧实现按 order_code
        # 一把删，会把同号第二房源行误删（该笔业务不计费，三表数量差 1）。
        batch_keys = [(o.order_code, o.custom_code or "") for o in saved_orders]
        if not batch_keys:
            return

        stale_rows = (
            (
                await self.db.execute(
                    select(DailyOrder).where(
                        tuple_(
                            DailyOrder.order_code, func.coalesce(DailyOrder.custom_code, "")
                        ).in_(batch_keys),
                        (DailyOrder.sync_date < sync_date) | (DailyOrder.sync_date >= day_end),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not stale_rows:
            return

        new_day_str = sync_date.astimezone(CST).date().isoformat()
        # 按 (customer_id, 旧日 UTC datetime) 聚合受影响旧日
        affected: Dict[Any, List[str]] = {}
        for row in stale_rows:
            old_day_str = row.sync_date.astimezone(CST).date().isoformat()
            emit(
                "warning",
                "order_move",
                f"订单 {row.order_code} 上传日期由 {old_day_str} 变更为 {new_day_str}，"
                f"已迁移并重算 {old_day_str} 消耗",
                customer_id=row.customer_id,
                order_code=row.order_code,
            )
            affected.setdefault((row.customer_id, row.sync_date), []).append(row.order_code)

        await self.db.execute(
            delete(DailyOrder).where(DailyOrder.id.in_([r.id for r in stale_rows]))
        )
        await self.db.commit()
        logger.info(
            f"跨日迁移清理：删除 {len(stale_rows)} 条残留订单，待重算 {len(affected)} 个旧日"
        )

        # 重算受影响旧日消耗（幂等：清空 + 重建）
        from app.services.cost_calc import CostCalcService

        for customer_id, old_day in affected:
            await CostCalcService(self.db).calculate_daily_cost(old_day)

    async def _match_customer(self, order: Dict) -> Optional[Customer]:
        """匹配内部客户（通过 external_id 或 group_type）"""
        # 通过 group_type（外部客户 ID）匹配
        group_type = order.get("group_type")
        if group_type:
            stmt = select(Customer).where(Customer.company_id == group_type)
            result = await self.db.execute(stmt)
            customer = result.scalar_one_or_none()
            if customer is not None:
                return customer

        # 通过公司名称匹配
        company_name = order.get("company_name")
        if company_name:
            stmt = select(Customer).where(Customer.name == company_name)
            result = await self.db.execute(stmt)
            customer = result.scalar_one_or_none()
            if customer is not None:
                return customer

        return None
