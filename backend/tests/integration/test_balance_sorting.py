"""余额列表排序集成测试

覆盖 2026-11-01 修复的两类缺陷：
1. 排序方向断裂：前端曾把 arco 的 'descend' 透传，被 useBalance.backendSortOrder()
   与路由层校验双重兜底成 'asc'，用户点「降序」实际拿到升序结果。本文件从 HTTP
   入口钉住 asc/desc 的真实语义（路由层对非法值兜底 asc 的契约一并钉住）。
2. 排序键与展示口径漂移：total_amount / days_remaining 的 SQL 排序表达式曾与
   _assemble_balance_rows / _compute_burn_down 的展示口径不一致——
   - total_amount：过期包年客户 CTE 不命中时退化为 CustomerBalance 旧值，
       展示层却显示 0，排序位置与展示值矛盾；
   - days_remaining：SQL 漏掉「过期包年记 0」分支且 postpaid 优先于包年，
       与展示层分支顺序相反。
3. 翻页稳定性：二级排序键缺失时，相同排序值（total_amount=0 占绝大多数）
   在翻页边界会重复/漏行。
"""

import uuid

import pytest
from sqlalchemy import text


def _unique_customer_id(base: int = 97000) -> int:
    """生成唯一的测试客户 ID，避免并行/重复执行冲突"""
    return base + abs(hash(uuid.uuid4().hex[:8])) % 2000


@pytest.fixture
def sort_customers(db_session):
    """构造 5 个排序场景客户

    - a / e：预付费，余额同为 3000（相同排序值，验证二级排序与翻页稳定性）
    - b：预付费，余额 1000
    - c：包年生效规则（base_fee=10000，无消耗 → 剩余 10000，60 天后到期）
    - d：包年规则已过期 + CustomerBalance.total_amount=5000 脏数据
      （展示口径为 0，排序键曾误用 5000）
    """
    specs = [
        ("a", "prepaid", None, 3000, "3000"),
        ("b", "prepaid", None, 1000, "1000"),
        ("c", "yearly", "active", None, None),
        ("d", "yearly", "expired", 5000, "0"),
        ("e", "prepaid", None, 3000, "3000"),
    ]
    created = []
    for tag, price_policy, pkg_state, balance_total, _ in specs:
        cid = _unique_customer_id()
        db_session.execute(
            text("DELETE FROM customers WHERE id = :id"),
            {"id": cid},
        )
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type, price_policy,
                                   settlement_cycle, settlement_type, created_at, updated_at)
            VALUES (:id, :company_id, :name, '正式账号', :price_policy,
                    'monthly', 'prepaid', NOW(), NOW())
            """),
            {
                "id": cid,
                "company_id": cid,
                "name": f"排序测试_{tag}_{cid}",
                "price_policy": price_policy,
            },
        )
        if balance_total is not None:
            db_session.execute(
                text("""
                INSERT INTO customer_balances
                    (customer_id, total_amount, real_amount, bonus_amount,
                     used_total, used_real, used_bonus, created_at, updated_at)
                VALUES (:cid, :total, :total, 0, 0, 0, 0, NOW(), NOW())
                """),
                {"cid": cid, "total": balance_total},
            )
        if pkg_state == "active":
            db_session.execute(
                text("""
                INSERT INTO pricing_rules
                    (customer_id, pricing_type, tiers, package_limits, effective_date,
                     expiry_date, created_at, updated_at)
                VALUES (:cid, 'package',
                        CAST('[]' AS json),
                        CAST(:limits AS json),
                        NOW() - INTERVAL '10 days', NOW() + INTERVAL '60 days',
                        NOW(), NOW())
                """),
                {"cid": cid, "limits": '{"base_fee": 10000, "is_unlimited": true}'},
            )
        elif pkg_state == "expired":
            db_session.execute(
                text("""
                INSERT INTO pricing_rules
                    (customer_id, pricing_type, tiers, package_limits, effective_date,
                     expiry_date, created_at, updated_at)
                VALUES (:cid, 'package',
                        CAST('[]' AS json),
                        CAST(:limits AS json),
                        NOW() - INTERVAL '100 days', NOW() - INTERVAL '1 day',
                        NOW(), NOW())
                """),
                {"cid": cid, "limits": '{"base_fee": 8000, "is_unlimited": true}'},
            )
        db_session.commit()
        created.append({"id": cid, "tag": tag})

    yield created

    # 按外键依赖顺序清理：先删引用 customers 的子表，再删 customers
    for c in created:
        db_session.execute(
            text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": c["id"]}
        )
        db_session.execute(
            text("DELETE FROM customer_balances WHERE customer_id = :id"), {"id": c["id"]}
        )
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": c["id"]})
        db_session.commit()


async def _fetch(test_client, auth_token, **params):
    """请求余额列表，返回 list"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    request, response = await test_client.get(
        "/api/v1/billing/balances", params=params, headers=headers
    )
    assert response.status == 200, response.json
    assert response.json["code"] == 0, response.json
    return response.json["data"]["list"]


@pytest.mark.asyncio
async def test_sort_total_amount_desc_is_really_descending(test_client, auth_token, sort_customers):
    """回归：点「余额」降序必须拿到降序结果（曾恒返回升序）"""
    rows = await _fetch(
        test_client, auth_token, sort_by="total_amount", sort_order="desc", page_size=50
    )
    values = [r["total_amount"] for r in rows]
    assert values == sorted(values, reverse=True), f"展示值非降序: {values}"

    # 口径回归：过期包年客户 d 展示 0，必须排在所有正值之后
    d = next(r for r in rows if r["id"] == next(c["id"] for c in sort_customers if c["tag"] == "d"))
    assert d["total_amount"] == 0
    assert values[-1] == 0
    # 其 CustomerBalance 脏数据 5000 不得把排序位置抬到正值区
    assert values.count(5000) == 0


@pytest.mark.asyncio
async def test_sort_total_amount_asc_is_really_ascending(test_client, auth_token, sort_customers):
    """升序方向必须真实生效（负值在前、0 在后）"""
    rows = await _fetch(
        test_client, auth_token, sort_by="total_amount", sort_order="asc", page_size=50
    )
    values = [r["total_amount"] for r in rows]
    assert values == sorted(values), f"展示值非升序: {values}"


@pytest.mark.asyncio
async def test_sort_days_remaining_asc_expired_package_first(
    test_client, auth_token, sort_customers
):
    """回归：过期包年燃尽天数展示 0，排序必须排最前（SQL 曾漏该分支排到末尾）"""
    rows = await _fetch(
        test_client, auth_token, sort_by="days_remaining", sort_order="asc", page_size=50
    )
    d_id = next(c["id"] for c in sort_customers if c["tag"] == "d")
    d_row = next(r for r in rows if r["id"] == d_id)
    assert d_row["days_remaining"] == 0
    non_null = [r["days_remaining"] for r in rows if r["days_remaining"] is not None]
    assert non_null == sorted(non_null), f"燃尽天数非升序: {non_null}"
    assert non_null[0] == 0, "过期包年（0 天）应排在所有非空值最前"


@pytest.mark.asyncio
async def test_sort_pagination_stable_with_equal_keys(test_client, auth_token, sort_customers):
    """翻页稳定性：相同排序值不得跨页重复/丢失（二级排序键回归）"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    _, response = await test_client.get(
        "/api/v1/billing/balances",
        params={"sort_by": "total_amount", "sort_order": "desc", "page_size": 50},
        headers=headers,
    )
    total = response.json["data"]["total"]

    seen: list[int] = []
    page = 1
    while True:
        rows = await _fetch(
            test_client,
            auth_token,
            sort_by="total_amount",
            sort_order="desc",
            page=page,
            page_size=2,
        )
        if not rows:
            break
        seen.extend(r["id"] for r in rows)
        page += 1
        if page > 20:  # 防御性上限，避免数据异常时死循环
            break

    assert len(seen) == len(set(seen)), "翻页出现重复行（二级排序键缺失）"
    assert len(seen) == total, f"翻页丢失行: 扫描 {len(seen)} != 总数 {total}"


@pytest.mark.asyncio
async def test_sort_order_invalid_value_falls_back_to_asc(test_client, auth_token, sort_customers):
    """契约钉住：路由层对非法 sort_order 兜底为 asc（前端修复后不应再传 descend）"""
    rows = await _fetch(
        test_client, auth_token, sort_by="total_amount", sort_order="descend", page_size=50
    )
    values = [r["total_amount"] for r in rows]
    assert values == sorted(values), f"非法 sort_order 应兜底为升序: {values}"
