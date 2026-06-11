"""客户管理服务"""

import math
import re
from datetime import date, datetime
from typing import Any, List, Optional, Tuple, Union

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from ..cache.base import cache_service
from ..models.billing import CustomerBalance
from ..models.customers import Customer, CustomerProfile
from ..utils.audit_helpers import build_batch_audit_summary, create_audit_entry

# 允许排序的字段白名单
ALLOWED_SORT_FIELDS = {
    "id",
    "company_id",
    "name",
    "created_at",
    "updated_at",
    "industry_type_id",
    "settlement_type",  # 结算方式 (Customer 表)
    "manager_id",  # 运营经理 (Customer 表)
    "sales_manager_id",  # 商务经理 (Customer 表)
    "is_key_customer",  # 重点客户 (Customer 表)
}
VALID_SORT_ORDERS = {"asc", "desc"}

# 账号类型映射：Excel 值 → 数据库存储值
ACCOUNT_TYPE_MAP = {
    "正式": "正式账号",
    "客户测试账号": "客户测试账号",
    "众趣内部": "内部账号",
}


def convert_account_type(value: Optional[str]) -> Optional[str]:
    """将 Excel 中的账号类型转换为数据库存储值"""
    if not value:
        return None
    return ACCOUNT_TYPE_MAP.get(str(value).strip(), str(value).strip())


def convert_bool_field(value: Optional[Union[str, bool, int]]) -> Optional[bool]:
    """将 Excel 中的是/否转换为布尔值"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    val = str(value).strip().lower()
    if val in ("是", "true", "1", "yes"):
        return True
    if val in ("否", "false", "0", "no"):
        return False
    return None


def convert_date_field(value: Optional[Any]) -> Optional[str]:
    """将 Excel 日期值转换为 YYYY-MM-DD 字符串"""
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    val = str(value).strip()
    if not val or val in ("#N/A", "None"):
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_date_to_object(value: Optional[Any]) -> Optional[date]:
    """将前端日期字符串转换为 datetime.date 对象"""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    val = str(value).strip()
    if not val or val in ("#N/A", "None"):
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        return None


def convert_settlement_type_to_storage(value: Optional[str]) -> Optional[str]:
    """将前端/导入的中文值转换为数据库存储的英文标识符"""
    if not value:
        return None
    if value in SETTLEMENT_TYPE_MAP:
        return value
    return SETTLEMENT_TYPE_REVERSE_MAP.get(value)


# 计费模式转换
PRICE_POLICY_MAP = {"定价": "pricing", "阶梯": "tiered", "包年": "yearly"}
PRICE_POLICY_REVERSE_MAP = {v: k for k, v in PRICE_POLICY_MAP.items()}

# 结算方式转换
SETTLEMENT_TYPE_MAP = {"预付费": "prepaid", "后付费": "postpaid"}
SETTLEMENT_TYPE_REVERSE_MAP = {v: k for k, v in SETTLEMENT_TYPE_MAP.items()}

# 结算周期转换
SETTLEMENT_CYCLE_MAP = {
    "日结": "daily",
    "周结": "weekly",
    "月结": "monthly",
    "季结": "quarterly",
    "年结": "yearly",
}
SETTLEMENT_CYCLE_REVERSE_MAP = {v: k for k, v in SETTLEMENT_CYCLE_MAP.items()}


def convert_price_policy_to_storage(value: str) -> str:
    return PRICE_POLICY_MAP.get(value, value)


def convert_price_policy_to_display(value: str) -> str:
    return PRICE_POLICY_REVERSE_MAP.get(value, value)


def convert_settlement_type_to_display(value: str) -> str:
    return SETTLEMENT_TYPE_REVERSE_MAP.get(value, value)


def convert_settlement_cycle_to_storage(value: Optional[str]) -> Optional[str]:
    """将导入的中文结算周期转换为数据库存储的英文标识符"""
    if not value:
        return None
    return SETTLEMENT_CYCLE_MAP.get(value, value)


def convert_settlement_cycle_to_display(value: str) -> str:
    """将数据库存储的英文结算周期转换为前端显示的中文"""
    return SETTLEMENT_CYCLE_REVERSE_MAP.get(value, value)


class CustomerService:
    """客户服务类

    支持同步和异步 Session
    """

    def __init__(self, db_session: Union[AsyncSession, Session]):
        self.db = db_session
        self._is_async = isinstance(db_session, AsyncSession)

    async def get_customer_by_id(self, customer_id: int) -> Optional[Customer]:
        """根据 ID 获取客户"""
        result = await self.db.execute(
            select(Customer)
            .options(
                selectinload(Customer.profile).selectinload(CustomerProfile.industry_type),
                selectinload(Customer.balance),
            )
            .where(Customer.id == customer_id, Customer.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_all_customers(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[dict] = None,
        sort_by: str = "id",
        sort_order: str = "asc",
    ) -> Tuple[List[Customer], int]:
        """
        获取客户列表（支持筛选和分页）

        Args:
            page: 页码
            page_size: 每页数量
            filters: 筛选条件字典
                - keyword: 公司名称/公司 ID 关键词
                - account_type: 账号类型
                - industry: 行业类型（筛选 customer_profiles.industry）
                - manager_id: 运营经理 ID
                - settlement_type: 结算方式
                - is_key_customer: 是否重点客户
            sort_by: 排序字段，可选值：id, company_id, name, created_at, updated_at（默认 id）
            sort_order: 排序方向，asc 或 desc（默认 asc）

        Returns:
            (customers, total)
        """
        filters = filters or {}

        # 构建基础查询
        stmt = select(Customer).where(Customer.deleted_at.is_(None))

        # 跟踪是否已 JOIN CustomerProfile（避免重复 JOIN）
        joined_profile = False

        # 应用筛选条件
        conditions = []

        # 关键词筛选（公司名称或公司 ID）
        if keyword := filters.get("keyword"):
            conditions.append(
                or_(
                    Customer.name.ilike(f"%{keyword}%"),
                    cast(Customer.company_id, String).ilike(f"%{keyword}%"),
                )
            )

        # 账号类型筛选
        if account_type := filters.get("account_type"):
            conditions.append(Customer.account_type == account_type)

        # 行业筛选（使用 profile.industry_type_id，JOIN IndustryType 表匹配名称）
        if industry := filters.get("industry"):
            from ..models.industry_type import IndustryType

            stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            stmt = stmt.outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
            joined_profile = True
            industry_list = [i.strip() for i in industry.split(",") if i.strip()]
            if len(industry_list) == 1:
                conditions.append(IndustryType.name == industry_list[0])
            else:
                conditions.append(IndustryType.name.in_(industry_list))

        # 运营经理筛选
        if manager_id := filters.get("manager_id"):
            conditions.append(Customer.manager_id == manager_id)

        # 商务经理筛选
        if sales_manager_id := filters.get("sales_manager_id"):
            conditions.append(Customer.sales_manager_id == sales_manager_id)

        # 结算方式筛选
        if settlement_type := filters.get("settlement_type"):
            conditions.append(Customer.settlement_type == settlement_type)

        # 重点客户筛选
        if (is_key_customer := filters.get("is_key_customer")) is not None:
            conditions.append(Customer.is_key_customer == is_key_customer)

        # 房产客户筛选
        if (is_real_estate := filters.get("is_real_estate")) is not None:
            conditions.append(Customer.is_real_estate == is_real_estate)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 获取总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        if self._is_async:
            total = (await self.db.execute(count_stmt)).scalar()
        else:
            total = self.db.execute(count_stmt).scalar()

        # 验证排序参数
        if sort_by not in ALLOWED_SORT_FIELDS:
            raise ValueError(f"Invalid sort field: {sort_by}")
        if sort_order not in VALID_SORT_ORDERS:
            raise ValueError(f"Invalid sort order: {sort_order}")

        # 动态排序
        if sort_by == "industry_type_id":
            if not joined_profile:
                stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            sort_column = CustomerProfile.industry_type_id
        else:
            sort_column = getattr(Customer, sort_by)

        if sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        # 加载关联数据
        stmt = stmt.options(
            selectinload(Customer.profile).selectinload(CustomerProfile.industry_type),
            selectinload(Customer.balance),
        )

        if self._is_async:
            result = await self.db.execute(stmt)
        else:
            result = self.db.execute(stmt)
        customers = result.scalars().all()

        return list(customers), total

    async def create_customer(self, data: dict) -> Customer:
        """创建客户"""
        customer = Customer(
            company_id=data["company_id"],
            name=data["name"],
            account_type=data.get("account_type"),
            price_policy=data.get("price_policy"),
            manager_id=data.get("manager_id"),
            settlement_cycle=data.get("settlement_cycle"),
            settlement_type=data.get("settlement_type"),
            is_key_customer=data.get("is_key_customer", False),
            email=data.get("email"),
        )

        self.db.add(customer)
        await self.db.flush()

        # 创建初始余额记录
        balance = CustomerBalance(customer_id=customer.id)
        self.db.add(balance)

        # 如果提供了 industry_type_id，创建 profile 记录
        if data.get("industry_type_id"):
            profile = CustomerProfile(
                customer_id=customer.id,
                industry_type_id=data["industry_type_id"],
            )
            self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(customer)

        # 方案 2: 数据变更时主动清除画像分析缓存
        await clear_analytics_cache()

        return customer

    async def update_customer(self, customer_id: int, data: dict) -> Optional[Customer]:
        """更新客户信息"""
        customer = await self.get_customer_by_id(customer_id)
        if not customer:
            return None

        # company_id 唯一性校验（如果修改了 company_id）
        new_company_id = data.get("company_id")
        if new_company_id and new_company_id != customer.company_id:
            existing = await self.db.execute(
                select(Customer.id).where(
                    Customer.company_id == new_company_id,
                    Customer.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError(f"公司 ID '{new_company_id}' 已被其他客户使用")

        # 可更新字段
        updatable_fields = [
            "company_id",
            "name",
            "account_type",
            "price_policy",
            "manager_id",
            "settlement_cycle",
            "settlement_type",
            "is_key_customer",
            "is_real_estate",
            "email",
            # 新增字段
            "erp_system",
            "first_payment_date",
            "onboarding_date",
            "sales_manager_id",
            "cooperation_status",
            "is_settlement_enabled",
            "is_disabled",
            "notes",
        ]

        # 日期字段转换：前端传 YYYY-MM-DD 字符串，需转换为 date 对象
        date_fields = ["first_payment_date", "onboarding_date"]
        for field in date_fields:
            if field in data and data[field]:
                data[field] = parse_date_to_object(data[field])

        for field in updatable_fields:
            if field in data:
                setattr(customer, field, data[field])

        # 如果提供了 industry_type_id，更新 profile
        if "industry_type_id" in data:
            profile = await self.get_customer_profile(customer.id)
            if profile:
                profile.industry_type_id = data["industry_type_id"]
            else:
                profile = CustomerProfile(
                    customer_id=customer.id, industry_type_id=data["industry_type_id"]
                )
                self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(customer)

        # 方案 2: 数据变更时主动清除画像分析缓存
        await clear_analytics_cache()

        return customer

    async def batch_update_customers(
        self, customer_ids: list[int], fields: dict, current_user: dict
    ) -> dict:
        """批量更新客户信息

        Args:
            customer_ids: 客户 ID 列表
            fields: 字段更新数据（键为字段名，值为新值）
            current_user: 当前用户信息（含 user_id）

        Returns:
            批量更新结果字典
        """
        # 参数校验
        if not customer_ids:
            raise ValueError("customer_ids 不能为空")
        if not fields:
            raise ValueError("fields 不能为空")

        # 可更新字段白名单
        updatable_fields = {
            "company_id",
            "name",
            "account_type",
            "price_policy",
            "manager_id",
            "settlement_cycle",
            "settlement_type",
            "is_key_customer",
            "is_real_estate",
            "email",
            "erp_system",
            "first_payment_date",
            "onboarding_date",
            "sales_manager_id",
            "cooperation_status",
            "is_settlement_enabled",
            "is_disabled",
            "notes",
            "industry_type_id",
            "scale_level",
            "consume_level",
        }

        # 校验字段白名单
        invalid_fields = [f for f in fields if f not in updatable_fields]
        if invalid_fields:
            raise ValueError(f"包含不在白名单内的字段: {', '.join(invalid_fields)}")

        # 上限校验
        if len(customer_ids) > 100:
            raise ValueError("批量更新上限为 100 个客户")

        success_list: list[int] = []
        failed_list: list[dict[str, Any]] = []

        for cid in customer_ids:
            try:
                customer = await self.get_customer_by_id(cid)
                if not customer:
                    failed_list.append({"customer_id": cid, "reason": "客户不存在"})
                    continue

                # email 格式校验
                if "email" in fields and fields["email"]:
                    if not re.match(
                        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                        str(fields["email"]),
                    ):
                        failed_list.append({"customer_id": cid, "reason": "邮箱格式错误"})
                        continue

                # industry_type_id 存在性校验
                if "industry_type_id" in fields and fields["industry_type_id"] is not None:
                    from ..models.industry_type import IndustryType

                    ind_result = await self.db.execute(
                        select(IndustryType).where(IndustryType.id == fields["industry_type_id"])
                    )
                    if not ind_result.scalar_one_or_none():
                        failed_list.append({"customer_id": cid, "reason": "行业类型不存在"})
                        continue

                # company_id 唯一性校验
                new_company_id = fields.get("company_id")
                if new_company_id and new_company_id != customer.company_id:
                    existing = await self.db.execute(
                        select(Customer.id).where(
                            Customer.company_id == new_company_id,
                            Customer.deleted_at.is_(None),
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        failed_list.append(
                            {"customer_id": cid, "reason": "公司 ID 已被其他客户使用"}
                        )
                        continue

                # 日期字段转换
                date_fields = {"first_payment_date", "onboarding_date"}
                fields_to_apply = fields.copy()
                for field in date_fields:
                    if field in fields_to_apply and fields_to_apply[field] is not None:
                        fields_to_apply[field] = parse_date_to_object(fields_to_apply[field])

                # 执行更新
                for field, value in fields_to_apply.items():
                    if field not in ("industry_type_id", "scale_level", "consume_level"):
                        setattr(customer, field, value)

                # Profile 更新
                profile_fields = {"industry_type_id", "scale_level", "consume_level"}
                if any(f in fields_to_apply for f in profile_fields):
                    profile = await self.get_customer_profile(customer.id)
                    if profile:
                        for pf in profile_fields:
                            if pf in fields_to_apply:
                                setattr(profile, pf, fields_to_apply[pf])
                    else:
                        profile_data: dict[str, Any] = {}
                        for pf in profile_fields:
                            if pf in fields_to_apply:
                                profile_data[pf] = fields_to_apply[pf]
                        profile_data["customer_id"] = customer.id
                        profile = CustomerProfile(**profile_data)
                        self.db.add(profile)

                await self.db.commit()
                await self.db.refresh(customer)
                success_list.append(cid)

            except Exception as e:  # pragma: no cover
                failed_list.append({"customer_id": cid, "reason": str(e)})

        # 审计日志
        if success_list or failed_list:
            summary = build_batch_audit_summary(
                operation="batch_update",
                total_count=len(customer_ids),
                success_count=len(success_list),
                failed_count=len(failed_list),
                details=failed_list[:10],
            )
            await create_audit_entry(
                db_session=self.db,
                user_id=current_user.get("user_id"),
                action="batch_update",
                module="customers",
                record_id=None,
                record_type="customer",
                changes={"fields": fields},
                operation_type="batch",
                extra_metadata=summary,
                auto_commit=False,
            )

        # 清理客户列表缓存
        await cache_service.invalidate_customer_cache(None)

        return {
            "total": len(customer_ids),
            "success_count": len(success_list),
            "failed_count": len(failed_list),
            "failed_list": failed_list,
        }

    async def delete_customer(self, customer_id: int) -> bool:
        """删除客户（软删除）"""
        customer = await self.get_customer_by_id(customer_id)
        if not customer:
            return False

        customer.deleted_at = func.now()
        await self.db.commit()

        return True

    async def get_customer_profile(self, customer_id: int) -> Optional[CustomerProfile]:
        """获取客户画像"""
        result = await self.db.execute(
            select(CustomerProfile).where(
                CustomerProfile.customer_id == customer_id,
                CustomerProfile.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create_or_update_profile(self, customer_id: int, data: dict) -> CustomerProfile:
        """创建或更新客户画像"""
        profile = await self.get_customer_profile(customer_id)

        # 处理 industry 字段：将行业类型名称转换为 industry_type_id
        industry_name = data.get("industry")
        if industry_name is not None:
            from sqlalchemy import select

            from ..models.industry_type import IndustryType

            result = await self.db.execute(
                select(IndustryType).where(IndustryType.name == industry_name)
            )
            industry_type = result.scalar_one_or_none()
            if industry_type:
                # 设置 industry_type_id
                data["industry_type_id"] = industry_type.id
                # 设置 industry_type 关联，避免懒加载问题
                if profile:
                    profile.industry_type = industry_type
                else:
                    # 如果 profile 不存在，创建新画像时设置 industry_type 关联
                    pass
            # 如果行业类型不存在，不设置 industry_type_id（保持为 None）

        if profile:
            # 更新现有画像
            updatable_fields = [
                "scale_level",
                "consume_level",
                "industry_type_id",
                "description",
                # 新增字段
                "monthly_avg_shots",
                "monthly_avg_shots_estimated",
                "estimated_annual_spend",
                "actual_annual_spend_2025",
            ]
            for field in updatable_fields:
                if field in data:
                    setattr(profile, field, data[field])
        else:
            # 创建新画像
            profile = CustomerProfile(
                customer_id=customer_id,
                scale_level=data.get("scale_level"),
                consume_level=data.get("consume_level"),
                industry_type_id=data.get("industry_type_id"),
                description=data.get("description"),
                monthly_avg_shots=data.get("monthly_avg_shots"),
                monthly_avg_shots_estimated=data.get("monthly_avg_shots_estimated"),
                estimated_annual_spend=data.get("estimated_annual_spend"),
                actual_annual_spend_2025=data.get("actual_annual_spend_2025"),
            )
            # 如果有 industry_type，设置关联（避免懒加载问题）
            if industry_name is not None and industry_type:
                profile.industry_type = industry_type
            self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(profile)

        return profile

    async def batch_create_customers(self, customers_data: List[dict]) -> Tuple[int, List[str]]:
        """
        批量创建客户（优化版：批量检查重复，减少 N+1 查询）

        Args:
            customers_data: 客户数据列表

        Returns:
            (success_count, errors)
        """
        # 批量获取已存在的 company_id，避免 N+1 查询
        existing_stmt = select(Customer.company_id)
        existing_result = await self.db.execute(existing_stmt)
        existing_company_ids = {row[0] for row in existing_result.all()}

        pending_profiles: list[dict] = []
        new_customers: list[Customer] = []
        success_count = 0
        errors = []

        for i, data in enumerate(customers_data):
            try:
                company_id = data.get("company_id")
                name = data.get("name")

                # Convert NaN to None (pandas uses NaN for missing values)
                if isinstance(company_id, float) and math.isnan(company_id):
                    company_id = None
                if isinstance(name, float) and math.isnan(name):
                    name = None

                # Convert NaN to None for all optional fields
                optional_fields = [
                    "account_type",
                    "industry_type_id",
                    "price_policy",
                    "settlement_cycle",
                    "settlement_type",
                    "email",
                    "erp_system",
                    "notes",
                    # 新增字段
                    "cooperation_status",
                    "is_settlement_enabled",
                    "is_disabled",
                    "first_payment_date",
                    "onboarding_date",
                    "consume_level",
                    "monthly_avg_shots",
                    "monthly_avg_shots_estimated",
                    "estimated_annual_spend",
                    "actual_annual_spend_2025",
                ]
                for field in optional_fields:
                    val = data.get(field)
                    if isinstance(val, float) and math.isnan(val):
                        data[field] = None
                    # 额外清洗 #N/A 和 #VALUE! 字符串
                    if isinstance(val, str) and val.strip() in ("#N/A", "#VALUE!"):
                        data[field] = None

                # consume_level: 0 不是有效值，转为 None
                if data.get("consume_level") in (0, "0"):
                    data["consume_level"] = None

                # Convert string company_id to int if needed (for import compatibility)
                if isinstance(company_id, str):
                    try:
                        company_id = int(company_id)
                    except (ValueError, TypeError):
                        errors.append(f"行{i + 1}: company_id '{company_id}' 不是有效的整数")
                        continue

                if not company_id:
                    errors.append(f"行{i + 1}: 缺少 company_id")
                    continue

                if not name:
                    errors.append(f"行{i + 1}: 缺少 name")
                    continue

                email = data.get("email")
                if email and not re.match(
                    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", str(email)
                ):
                    errors.append(f"行{i + 1}: 邮箱格式错误")
                    continue

                price_policy = data.get("price_policy")
                if price_policy:
                    # 转换为存储值（中文→英文）
                    storage_value = convert_price_policy_to_storage(price_policy)
                    if storage_value is None:
                        errors.append(
                            f"行{i + 1}: 无效的计费模式: {price_policy} (可选值：定价/阶梯/包年)"
                        )
                        continue
                else:
                    storage_value = None

                # 转换账号类型
                account_type = data.get("account_type")
                data["account_type"] = convert_account_type(account_type)

                # 转换布尔字段
                data["is_settlement_enabled"] = convert_bool_field(
                    data.get("is_settlement_enabled")
                )
                data["is_disabled"] = convert_bool_field(data.get("is_disabled"))

                # 转换 cooperation_status：支持 noused 值
                cooperation_status = data.get("cooperation_status")
                if cooperation_status:
                    valid_statuses = {"active", "suspended", "terminated", "noused"}
                    if cooperation_status not in valid_statuses:
                        # 尝试中文映射
                        status_map = {
                            "合作中": "active",
                            "暂停": "suspended",
                            "终止": "terminated",
                            "近一年未使用": "noused",
                        }
                        data["cooperation_status"] = status_map.get(cooperation_status)

                # 转换日期字段
                data["first_payment_date"] = convert_date_field(data.get("first_payment_date"))
                data["onboarding_date"] = convert_date_field(data.get("onboarding_date"))

                # 转换结算周期：中文→英文
                settlement_cycle = data.get("settlement_cycle")
                if settlement_cycle:
                    data["settlement_cycle"] = convert_settlement_cycle_to_storage(settlement_cycle)

                # 结算方式统一设为 prepaid
                if data.get("settlement_type") is None:
                    data["settlement_type"] = "prepaid"

                # 数值字段清洗（月均拍摄量等）
                for num_field in [
                    "monthly_avg_shots",
                    "monthly_avg_shots_estimated",
                ]:
                    val = data.get(num_field)
                    if val is not None and val != 0:
                        try:
                            data[num_field] = int(float(str(val).strip()))
                        except (ValueError, TypeError):
                            data[num_field] = None
                    elif val == 0:
                        data[num_field] = None

                # 金额字段清洗
                for money_field in [
                    "estimated_annual_spend",
                    "actual_annual_spend_2025",
                ]:
                    val = data.get(money_field)
                    if val is not None and val != 0:
                        try:
                            data[money_field] = float(str(val).strip())
                        except (ValueError, TypeError):
                            data[money_field] = None
                    elif val == 0:
                        data[money_field] = None

                # 检查是否已存在
                if company_id in existing_company_ids:
                    errors.append(f"行{i + 1}: 公司 ID {company_id} 已存在")
                    continue

                # 暂存 profile 数据（等待 flush 后设置 customer_id）
                profile_data = None
                profile_fields = {
                    "industry_type_id": data.get("industry_type_id"),
                    "consume_level": data.get("consume_level"),
                    "monthly_avg_shots": data.get("monthly_avg_shots"),
                    "monthly_avg_shots_estimated": data.get("monthly_avg_shots_estimated"),
                    "estimated_annual_spend": data.get("estimated_annual_spend"),
                    "actual_annual_spend_2025": data.get("actual_annual_spend_2025"),
                }
                if any(v is not None for v in profile_fields.values()):
                    profile_data = profile_fields

                customer = Customer(
                    company_id=company_id,
                    name=name,
                    account_type=data.get("account_type"),
                    price_policy=storage_value,
                    manager_id=data.get("manager_id"),
                    settlement_cycle=data.get("settlement_cycle"),
                    settlement_type=data.get("settlement_type"),
                    is_key_customer=data.get("is_key_customer", False),
                    email=data.get("email"),
                    # 新增字段
                    erp_system=data.get("erp_system"),
                    first_payment_date=data.get("first_payment_date"),
                    onboarding_date=data.get("onboarding_date"),
                    cooperation_status=data.get("cooperation_status"),
                    is_settlement_enabled=data.get("is_settlement_enabled"),
                    is_disabled=data.get("is_disabled"),
                    notes=data.get("notes"),
                )
                self.db.add(customer)
                new_customers.append(customer)
                # 暂存 profile 数据（等待 flush 后设置 customer_id）
                if profile_data:
                    pending_profiles.append(
                        {
                            "data": profile_data,
                            "company_id": company_id,
                        }
                    )
                existing_company_ids.add(company_id)  # 防止同批次重复

                success_count += 1
            except Exception as e:
                errors.append(f"行{i + 1}: {str(e)}")

        # 批量创建余额记录和 profile
        if success_count > 0:
            # flush 后 customer.id 可用
            await self.db.flush()
            balances = [CustomerBalance(customer_id=c.id) for c in new_customers]
            self.db.add_all(balances)

            # 创建 profile 记录
            if pending_profiles:
                company_id_to_id = {c.company_id: c.id for c in new_customers}
                for p_info in pending_profiles:
                    customer_id = company_id_to_id.get(p_info["company_id"])
                    if customer_id:
                        pd = p_info["data"]
                        profile = CustomerProfile(
                            customer_id=customer_id,
                            industry_type_id=pd.get("industry_type_id"),
                            consume_level=pd.get("consume_level"),
                            monthly_avg_shots=pd.get("monthly_avg_shots"),
                            monthly_avg_shots_estimated=pd.get("monthly_avg_shots_estimated"),
                            estimated_annual_spend=pd.get("estimated_annual_spend"),
                            actual_annual_spend_2025=pd.get("actual_annual_spend_2025"),
                        )
                        self.db.add(profile)

        await self.db.commit()
        return success_count, errors


async def clear_analytics_cache():
    """清除所有画像分析相关的缓存"""
    from ..cache.base import cache_service

    cache_keys = [
        ("analytics_profile", "industry"),
        ("analytics_profile", "scale"),
        ("analytics_profile", "consume_level"),
        ("analytics_profile", "real_estate"),
        ("analytics_profile", "real_estate_industry"),
    ]

    for key_ns, key_suffix in cache_keys:
        try:
            await cache_service.delete(key_ns, key_suffix)
        except Exception as e:
            print(f"[Cache Clear] 清除 {key_ns}:{key_suffix} 失败：{e}")
