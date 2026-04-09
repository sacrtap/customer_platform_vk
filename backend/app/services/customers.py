"""客户管理服务"""

from typing import Optional, List, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from ..models.customers import Customer, CustomerProfile
from ..models.billing import CustomerBalance


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
                - business_type: 业务类型
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
                    Customer.company_id.ilike(f"%{keyword}%"),
                )
            )

        # 账号类型筛选
        if account_type := filters.get("account_type"):
            conditions.append(Customer.account_type == account_type)

        # 业务类型筛选
        if business_type := filters.get("business_type"):
            conditions.append(Customer.business_type == business_type)

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
            business_type=data.get("business_type"),
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

        await self.db.commit()
        await self.db.refresh(customer)

        return customer

    async def update_customer(self, customer_id: int, data: dict) -> Optional[Customer]:
        """更新客户信息"""
        customer = await self.get_customer_by_id(customer_id)
        if not customer:
            return None

        # 可更新字段
        updatable_fields = [
            "name",
            "account_type",
            "business_type",
            "customer_level",
            "price_policy",
            "manager_id",
            "settlement_cycle",
            "settlement_type",
            "is_key_customer",
            "email",
        ]

        for field in updatable_fields:
            if field in data:
                setattr(customer, field, data[field])

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

        success_count = 0
        errors = []

        for i, data in enumerate(customers_data):
            try:
                company_id = data.get("company_id")
                if not company_id:
                    errors.append(f"行{i + 1}: 缺少 company_id")
                    continue

                # 检查是否已存在
                if company_id in existing_company_ids:
                    errors.append(f"行{i + 1}: 公司 ID {company_id} 已存在")
                    continue

                customer = Customer(
                    company_id=company_id,
                    name=data.get("name"),
                    account_type=data.get("account_type"),
                    business_type=data.get("business_type"),
                    customer_level=data.get("customer_level"),
                    price_policy=data.get("price_policy"),
                    manager_id=data.get("manager_id"),
                    settlement_cycle=data.get("settlement_cycle"),
                    settlement_type=data.get("settlement_type"),
                    is_key_customer=data.get("is_key_customer", False),
                    email=data.get("email"),
                )
                self.db.add(customer)
                existing_company_ids.add(company_id)  # 防止同批次重复

                success_count += 1
            except Exception as e:
                errors.append(f"行{i + 1}: {str(e)}")

        # 批量创建余额记录
        if success_count > 0:
            # 获取刚创建的客户 ID
            await self.db.flush()
            new_customers = [c for c in self.db.new if isinstance(c, Customer)]
            balances = [CustomerBalance(customer_id=c.id) for c in new_customers]
            self.db.add_all(balances)

        await self.db.commit()
        return success_count, errors
