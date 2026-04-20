"""客户管理服务"""

import math
import re
from datetime import datetime
from typing import Optional, List, Tuple, Union, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, cast, String
from sqlalchemy.orm import selectinload
from ..models.customers import Customer, CustomerProfile
from ..models.billing import CustomerBalance


# 价格策略映射：中文 ↔ 英文标识符
PRICE_POLICY_MAP = {
    "定价": "pricing",
    "阶梯": "tiered",
    "包年": "yearly",
}

PRICE_POLICY_REVERSE_MAP = {v: k for k, v in PRICE_POLICY_MAP.items()}

VALID_PRICE_POLICIES = set(PRICE_POLICY_MAP.values())  # {"pricing", "tiered", "yearly"}


# 结算方式映射：英文标识符 ↔ 中文显示值
SETTLEMENT_TYPE_MAP = {
    "prepaid": "预付费",
    "postpaid": "后付费",
}

SETTLEMENT_TYPE_REVERSE_MAP = {v: k for k, v in SETTLEMENT_TYPE_MAP.items()}

VALID_SETTLEMENT_TYPES = set(SETTLEMENT_TYPE_MAP.values())


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


def convert_settlement_type_to_storage(value: Optional[str]) -> Optional[str]:
    """将前端/导入的中文值转换为数据库存储的英文标识符"""
    if not value:
        return None
    # 如果已经是英文标识符，直接返回
    if value in SETTLEMENT_TYPE_MAP:
        return value
    # 中文转英文
    return SETTLEMENT_TYPE_REVERSE_MAP.get(value)


def convert_settlement_type_to_display(value: Optional[str]) -> Optional[str]:
    """将数据库存储的英文标识符转换为前端展示的中文值"""
    if not value:
        return None
    # 如果已经是中文，直接返回（兼容旧数据）
    if value in SETTLEMENT_TYPE_REVERSE_MAP:
        return value
    # 英文转中文
    return SETTLEMENT_TYPE_MAP.get(value, value)


def convert_price_policy_to_storage(value: Optional[str]) -> Optional[str]:
    """将前端/导入的中文值转换为数据库存储的英文标识符"""
    if not value:
        return None
    # 如果已经是英文标识符，直接返回
    if value in VALID_PRICE_POLICIES:
        return value
    # 中文转英文
    return PRICE_POLICY_MAP.get(value)


def convert_price_policy_to_display(value: Optional[str]) -> Optional[str]:
    """将数据库存储的英文标识符转换为前端展示的中文值"""
    if not value:
        return None
    # 如果已经是中文，直接返回（兼容旧数据）
    if value in PRICE_POLICY_MAP:
        return value
    # 英文转中文
    return PRICE_POLICY_REVERSE_MAP.get(value, value)


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
            .options(selectinload(Customer.profile), selectinload(Customer.balance))
            .where(Customer.id == customer_id, Customer.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_all_customers(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[dict] = None,
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
                - customer_level: 客户等级
                - manager_id: 运营经理 ID
                - settlement_type: 结算方式
                - is_key_customer: 是否重点客户

        Returns:
            (customers, total)
        """
        filters = filters or {}

        # 构建基础查询
        stmt = select(Customer).where(Customer.deleted_at.is_(None))

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

        # 行业筛选（使用 profile.industry）
        if industry := filters.get("industry"):
            stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            conditions.append(CustomerProfile.industry == industry)

        # 客户等级筛选
        if customer_level := filters.get("customer_level"):
            conditions.append(Customer.customer_level == customer_level)

        # 运营经理筛选
        if manager_id := filters.get("manager_id"):
            conditions.append(Customer.manager_id == manager_id)

        # 结算方式筛选
        if settlement_type := filters.get("settlement_type"):
            conditions.append(Customer.settlement_type == settlement_type)

        # 重点客户筛选
        if (is_key_customer := filters.get("is_key_customer")) is not None:
            conditions.append(Customer.is_key_customer == is_key_customer)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 获取总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        if self._is_async:
            total = (await self.db.execute(count_stmt)).scalar()
        else:
            total = self.db.execute(count_stmt).scalar()

        # 分页排序
        stmt = stmt.order_by(Customer.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        # 加载关联数据
        stmt = stmt.options(selectinload(Customer.profile), selectinload(Customer.balance))

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
            customer_level=data.get("customer_level"),
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

        # 如果提供了 industry，创建 profile 记录
        if data.get("industry"):
            profile = CustomerProfile(
                customer_id=customer.id,
                industry=data["industry"],
            )
            self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(customer)

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
            "customer_level",
            "price_policy",
            "manager_id",
            "settlement_cycle",
            "settlement_type",
            "is_key_customer",
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

        for field in updatable_fields:
            if field in data:
                setattr(customer, field, data[field])

        # 如果提供了 industry，更新 profile
        if "industry" in data:
            profile = await self.get_customer_profile(customer.id)
            if profile:
                profile.industry = data["industry"]
            else:
                profile = CustomerProfile(customer_id=customer.id, industry=data["industry"])
                self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(customer)

        return customer

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

        if profile:
            # 更新现有画像
            updatable_fields = [
                "scale_level",
                "consume_level",
                "industry",
                "is_real_estate",
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
                industry=data.get("industry"),
                is_real_estate=data.get("is_real_estate", False),
                description=data.get("description"),
                monthly_avg_shots=data.get("monthly_avg_shots"),
                monthly_avg_shots_estimated=data.get("monthly_avg_shots_estimated"),
                estimated_annual_spend=data.get("estimated_annual_spend"),
                actual_annual_spend_2025=data.get("actual_annual_spend_2025"),
            )
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
                    "customer_level",
                    "industry",
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

                # 转换日期字段
                data["first_payment_date"] = convert_date_field(data.get("first_payment_date"))
                data["onboarding_date"] = convert_date_field(data.get("onboarding_date"))

                # 结算方式统一设为 prepaid
                if data.get("settlement_type") is None:
                    data["settlement_type"] = "prepaid"

                # 数值字段清洗（月均拍摄量等）
                for num_field in [
                    "monthly_avg_shots",
                    "monthly_avg_shots_estimated",
                ]:
                    val = data.get(num_field)
                    if val is not None:
                        try:
                            data[num_field] = int(float(str(val).strip()))
                        except (ValueError, TypeError):
                            data[num_field] = None

                # 金额字段清洗
                for money_field in [
                    "estimated_annual_spend",
                    "actual_annual_spend_2025",
                ]:
                    val = data.get(money_field)
                    if val is not None:
                        try:
                            data[money_field] = float(str(val).strip())
                        except (ValueError, TypeError):
                            data[money_field] = None

                # 检查是否已存在
                if company_id in existing_company_ids:
                    errors.append(f"行{i + 1}: 公司 ID {company_id} 已存在")
                    continue

                # 暂存 profile 数据（等待 flush 后设置 customer_id）
                profile_data = None
                profile_fields = {
                    "industry": data.get("industry"),
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
                    customer_level=data.get("customer_level"),
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
                            industry=pd.get("industry"),
                            consume_level=pd.get("consume_level"),
                            monthly_avg_shots=pd.get("monthly_avg_shots"),
                            monthly_avg_shots_estimated=pd.get("monthly_avg_shots_estimated"),
                            estimated_annual_spend=pd.get("estimated_annual_spend"),
                            actual_annual_spend_2025=pd.get("actual_annual_spend_2025"),
                        )
                        self.db.add(profile)

        await self.db.commit()
        return success_count, errors
