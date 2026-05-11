"""行业类型外键关联测试"""

import pytest
from sqlalchemy import select
from app.models.customers import Customer, CustomerProfile
from app.models.industry_type import IndustryType
from app.services.customers import CustomerService


@pytest.mark.asyncio
class TestIndustryTypeForeignKey:
    """行业类型外键关联测试"""

    async def test_create_customer_with_industry_type(self, db_session):
        """测试创建客户时关联行业类型"""
        result = await db_session.execute(select(IndustryType).limit(1))
        industry_type = result.scalar_one_or_none()
        if not industry_type:
            industry_type = IndustryType(name="测试行业", sort_order=999)
            db_session.add(industry_type)
            await db_session.commit()
            await db_session.refresh(industry_type)

        service = CustomerService(db_session)
        customer = await service.create_customer({
            "company_id": 999999,
            "name": "测试客户",
            "industry_type_id": industry_type.id,
        })

        assert customer is not None
        assert customer.profile is not None
        assert customer.profile.industry_type_id == industry_type.id

    async def test_create_customer_without_industry_type(self, db_session):
        """测试创建客户时不指定行业类型"""
        service = CustomerService(db_session)
        customer = await service.create_customer({
            "company_id": 999998,
            "name": "测试客户无行业",
        })

        assert customer is not None
        profile = await service.get_customer_profile(customer.id)
        assert profile is None

    async def test_update_customer_industry_type(self, db_session):
        """测试更新客户行业类型"""
        it1 = IndustryType(name="行业A", sort_order=100)
        it2 = IndustryType(name="行业B", sort_order=101)
        db_session.add_all([it1, it2])
        await db_session.commit()
        await db_session.refresh(it1)
        await db_session.refresh(it2)

        service = CustomerService(db_session)
        customer = await service.create_customer({
            "company_id": 999997,
            "name": "测试更新行业",
            "industry_type_id": it1.id,
        })

        updated = await service.update_customer(customer.id, {
            "industry_type_id": it2.id,
        })

        assert updated is not None
        profile = await service.get_customer_profile(customer.id)
        assert profile.industry_type_id == it2.id

    async def test_delete_industry_type_sets_null(self, db_session):
        """测试删除行业类型后客户 industry_type_id 设为 NULL"""
        it = IndustryType(name="待删除行业", sort_order=102)
        db_session.add(it)
        await db_session.commit()
        await db_session.refresh(it)

        service = CustomerService(db_session)
        customer = await service.create_customer({
            "company_id": 999996,
            "name": "测试删除行业",
            "industry_type_id": it.id,
        })

        from app.services.industry_type_service import IndustryTypeService
        industry_service = IndustryTypeService(db_session)
        await industry_service.soft_delete(it.id)

        await db_session.refresh(customer)
        profile = await service.get_customer_profile(customer.id)
        assert profile.industry_type_id is None
