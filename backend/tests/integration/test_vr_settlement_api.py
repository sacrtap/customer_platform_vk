"""
VR编辑费用结算 API 集成测试

测试覆盖：
1. POST /api/v1/billing/vr-settlements - 手动创建（草稿）
2. 全流程：submit → confirm-cs → confirm-sales → confirm-sales-supervisor → confirm
3. 客户确认自动扣款：余额扣减 + consumption_records 关联 vr_settlement_id
4. 减免：编辑窗口、销售主管一并审批、驳回回流
5. 非法状态流转 / 销售身份校验 / 提交前置校验 / 取消 / 删除
"""

import uuid

import pytest
from sqlalchemy import text


def _unique_customer_id(base: int = 80000) -> int:
    """生成唯一的测试客户 ID，避免并行测试冲突"""
    return base + abs(hash(uuid.uuid4().hex[:8])) % 10000


@pytest.fixture
async def admin_user_id(db_session):
    """测试管理员用户 ID（测试客户默认指定其为销售）"""
    result = db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))
    return result.scalar_one()


async def _create_customer(db_session, customer_id: int, sales_manager_id=None):
    """raw SQL 造客户（照抄 test_billing_api.py 模式，扩展 sales_manager_id）"""
    db_session.execute(
        text("DELETE FROM customers WHERE id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type, sales_manager_id,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, :account_type,
                :cycle, :type, :sales_manager_id, NOW(), NOW())
        """),
        {
            "id": customer_id,
            "company_id": customer_id,
            "name": f"VR测试客户_{customer_id}",
            "account_type": "enterprise",
            "cycle": "monthly",
            "type": "prepaid",
            "sales_manager_id": sales_manager_id,
        },
    )
    db_session.commit()


@pytest.fixture
async def test_customer(db_session, admin_user_id):
    """创建测试客户（默认指定 admin 为销售，供销售审批身份校验正值用例）"""
    customer_id = _unique_customer_id()
    await _create_customer(db_session, customer_id, sales_manager_id=admin_user_id)

    yield {"id": customer_id, "name": f"VR测试客户_{customer_id}"}

    # 清理（CASCADE 顺序：先删引用本客户的业务数据）
    for stmt in (
        "DELETE FROM consumption_records WHERE customer_id = :id",
        "DELETE FROM vr_settlement_discount_histories WHERE settlement_id IN "
        "(SELECT id FROM vr_settlements WHERE customer_id = :id)",
        "DELETE FROM vr_settlements WHERE customer_id = :id",
        "DELETE FROM customer_balances WHERE customer_id = :id",
        "DELETE FROM customers WHERE id = :id",
    ):
        db_session.execute(text(stmt), {"id": customer_id})
    db_session.commit()


@pytest.fixture
async def test_customer_with_balance(db_session, test_customer):
    """创建有余额的测试客户：可用余额 1000（real=1000, bonus=0）"""
    customer_id = test_customer["id"]

    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :cid"),
        {"cid": customer_id},
    )
    db_session.execute(
        text("""
        INSERT INTO customer_balances
            (customer_id, total_amount, real_amount, bonus_amount,
             used_total, used_real, used_bonus, created_at, updated_at)
        VALUES (:cid, 1000, 1000, 0, 0, 0, 0, NOW(), NOW())
        """),
        {"cid": customer_id},
    )
    db_session.commit()

    yield test_customer

    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :cid"),
        {"cid": customer_id},
    )
    db_session.commit()


def _create_payload(customer_id: int, total_amount=500.0, remark: str | None = None) -> dict:
    """创建接口请求体（明细文件路径为静态 URL，不解析内容）"""
    payload = {
        "customer_id": customer_id,
        "period_start": "2026-11-01",
        "period_end": "2026-11-30",
        "total_amount": total_amount,
        "detail_file_path": "/uploads/2026/11/test.xlsx",
        "detail_file_name": "test.xlsx",
    }
    if remark is not None:
        payload["remark"] = remark
    return payload


async def _create_settlement(
    test_client, auth_token, customer_id: int, total_amount=500.0, remark: str | None = None
) -> int:
    """创建结算单并返回 id"""
    request, response = await test_client.post(
        "/api/v1/billing/vr-settlements",
        json=_create_payload(customer_id, total_amount, remark),
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 201, response.json
    return response.json["data"]["id"]


async def _get_detail(test_client, auth_token, settlement_id: int) -> dict:
    request, response = await test_client.get(
        f"/api/v1/billing/vr-settlements/{settlement_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200, response.json
    return response.json["data"]


async def _post_action(test_client, auth_token, path: str, json: dict | None = None):
    return await test_client.post(
        f"/api/v1/billing/vr-settlements{path}",
        json=json or {},
        headers={"Authorization": f"Bearer {auth_token}"},
    )


# ==================== 创建与全流程 ====================


@pytest.mark.asyncio
async def test_create_and_full_approval_flow(
    test_client, auth_token, test_customer_with_balance, db_session
):
    """AC1/AC2/AC3：创建 → 六级审批 → 客户确认自动扣款，余额与消耗记录正确"""
    customer_id = test_customer_with_balance["id"]

    # 1. 创建
    settlement_id = await _create_settlement(test_client, auth_token, customer_id)
    detail = await _get_detail(test_client, auth_token, settlement_id)
    assert detail["settlement_no"].startswith("VR-")
    assert detail["status"] == "draft"
    assert detail["final_amount"] == 500

    # 2. 提交 → 待客服主管审批
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == (
        "pending_cs_supervisor"
    )

    # 3. 客服主管审批 → 待销售审批
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == "pending_sales"

    # 4. 销售审批（admin 为该客户指定销售）→ 待销售主管审批
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-sales")
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == (
        "pending_sales_supervisor"
    )

    # 5. 销售主管审批通过（带意见）→ 待客户确认
    _, response = await _post_action(
        test_client,
        auth_token,
        f"/{settlement_id}/confirm-sales-supervisor",
        {"comment": "同意"},
    )
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == (
        "pending_customer"
    )

    # 6. 客户确认 → 自动扣款 → completed
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/confirm")
    assert response.status == 200, response.json
    detail = await _get_detail(test_client, auth_token, settlement_id)
    assert detail["status"] == "completed"

    # 断言余额：used_total=500，可用余额 total_amount=500（1000-500）
    balance = db_session.execute(
        text("SELECT used_total, total_amount FROM customer_balances WHERE customer_id = :cid"),
        {"cid": customer_id},
    ).fetchone()
    assert float(balance[0]) == 500
    assert float(balance[1]) == 500

    # 断言消耗记录：amount=500、vr_settlement_id 指向本单、balance_after=500
    record = db_session.execute(
        text("""
        SELECT amount, vr_settlement_id, balance_after, invoice_id
        FROM consumption_records WHERE customer_id = :cid
        """),
        {"cid": customer_id},
    ).fetchone()
    assert float(record[0]) == 500
    assert record[1] == settlement_id
    assert float(record[2]) == 500
    assert record[3] is None  # VR 消耗记录不关联 invoice

    # 接口层断言：消耗记录列表必须下发 vr_settlement_id/vr_settlement_no，
    # 否则前端「关联结算单」列对 VR 记录显示空（2026-11-03 修复的回归守护）
    _, cr_response = await test_client.get(
        f"/api/v1/billing/consumption-records?customer_id={customer_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert cr_response.status == 200, cr_response.json
    vr_records = [
        item
        for item in cr_response.json["data"]["list"]
        if item["vr_settlement_id"] == settlement_id
    ]
    assert len(vr_records) == 1
    assert vr_records[0]["vr_settlement_no"] == detail["settlement_no"]
    assert vr_records[0]["invoice_no"] is None


@pytest.mark.asyncio
async def test_discount_approved_together_at_sales_supervisor(
    test_client, auth_token, test_customer_with_balance, db_session
):
    """AC4：待销售节点设置减免 100，销售主管一并审批通过后扣款 900"""
    customer_id = test_customer_with_balance["id"]
    settlement_id = await _create_settlement(
        test_client, auth_token, customer_id, total_amount=1000.0
    )

    # draft 时提交减免 100
    request, response = await test_client.put(
        f"/api/v1/billing/vr-settlements/{settlement_id}/discount",
        json={
            "discount_amount": 100,
            "discount_reason": "大客户优惠",
            "discount_attachment": "/uploads/proof.pdf",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200, response.json

    # 历史表多一行
    history_count = db_session.execute(
        text("SELECT COUNT(*) FROM vr_settlement_discount_histories WHERE settlement_id = :sid"),
        {"sid": settlement_id},
    ).scalar()
    assert history_count == 1

    # 走完审批流
    await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-sales")
    _, response = await _post_action(
        test_client,
        auth_token,
        f"/{settlement_id}/confirm-sales-supervisor",
        {"comment": "同意减免"},
    )
    assert response.status == 200, response.json

    # 断言减免一并审批字段落库
    detail = await _get_detail(test_client, auth_token, settlement_id)
    assert detail["discount_approver_id"] is not None
    assert detail["discount_approved_at"] is not None
    assert detail["discount_approval_comment"] == "同意减免"
    assert detail["final_amount"] == 900

    # 客户确认 → 扣款 900
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/confirm")
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == "completed"

    balance = db_session.execute(
        text("SELECT used_total, total_amount FROM customer_balances WHERE customer_id = :cid"),
        {"cid": customer_id},
    ).fetchone()
    assert float(balance[0]) == 900
    assert float(balance[1]) == 100

    record = db_session.execute(
        text("""
        SELECT amount, vr_settlement_id, balance_after
        FROM consumption_records WHERE customer_id = :cid
        """),
        {"cid": customer_id},
    ).fetchone()
    assert float(record[0]) == 900
    assert record[1] == settlement_id
    assert float(record[2]) == 100


@pytest.mark.asyncio
async def test_discount_edit_window(test_client, auth_token, test_customer_with_balance):
    """AC5：销售主管审批通过前（含 pending_sales_supervisor）可改减免；pending_customer 起锁定；金额 0 拒绝"""
    customer_id = test_customer_with_balance["id"]
    settlement_id = await _create_settlement(test_client, auth_token, customer_id)
    headers = {"Authorization": f"Bearer {auth_token}"}
    discount_url = f"/api/v1/billing/vr-settlements/{settlement_id}/discount"

    async def put_discount(amount: float):
        return await test_client.put(
            discount_url,
            json={"discount_amount": amount, "discount_reason": "测试"},
            headers=headers,
        )

    # draft 可改
    _, response = await put_discount(50)
    assert response.status == 200, response.json

    # 金额 0 拒绝
    _, response = await put_discount(0)
    assert response.status == 400
    assert response.json["message"] == "减免金额不能为 0"

    # 提交 → 待客服主管，仍可改
    await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
    _, response = await put_discount(60)
    assert response.status == 200, response.json

    # 客服主管审批 → 待销售，仍可改
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")
    _, response = await put_discount(70)
    assert response.status == 200, response.json

    # 销售审批 → 待销售主管（审批通过前最后节点），仍可改
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-sales")
    _, response = await put_discount(80)
    assert response.status == 200, response.json

    # 销售主管审批通过 → 待客户确认，锁定不可改
    await _post_action(
        test_client, auth_token, f"/{settlement_id}/confirm-sales-supervisor", {"comment": "同意"}
    )
    _, response = await put_discount(90)
    assert response.status == 400


@pytest.mark.asyncio
async def test_reject_requires_comment_and_reverts(
    test_client, auth_token, test_customer_with_balance
):
    """AC6：驳回必须填理由；带理由驳回到待销售；销售可重新确认再次进入主管审批"""
    customer_id = test_customer_with_balance["id"]
    settlement_id = await _create_settlement(test_client, auth_token, customer_id)

    await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-sales")

    # 无 comment 驳回 → 400
    _, response = await _post_action(
        test_client, auth_token, f"/{settlement_id}/reject-sales-supervisor", {}
    )
    assert response.status == 400
    assert response.json["message"] == "驳回必须填写理由"

    # 带 comment 驳回 → 回退待销售
    _, response = await _post_action(
        test_client,
        auth_token,
        f"/{settlement_id}/reject-sales-supervisor",
        {"comment": "金额有误"},
    )
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == "pending_sales"

    # 销售重新确认 → 再次进入待销售主管审批
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-sales")
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == (
        "pending_sales_supervisor"
    )


@pytest.mark.asyncio
async def test_rollback_to_previous_step(test_client, auth_token, test_customer_with_balance):
    """回退至上一步：pending_sales → pending_cs_supervisor → draft；draft/空理由 → 400"""
    customer_id = test_customer_with_balance["id"]
    settlement_id = await _create_settlement(test_client, auth_token, customer_id)

    # 提交 → 客服主管审批 → 待销售审批
    await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == "pending_sales"

    # 待销售节点回退 → 待客服主管
    _, response = await _post_action(
        test_client, auth_token, f"/{settlement_id}/rollback", {"comment": "信息有误"}
    )
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == (
        "pending_cs_supervisor"
    )

    # 待客服主管节点回退 → 草稿
    _, response = await _post_action(
        test_client, auth_token, f"/{settlement_id}/rollback", {"comment": "信息有误"}
    )
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == "draft"

    # 草稿不支持回退 → 400
    _, response = await _post_action(
        test_client, auth_token, f"/{settlement_id}/rollback", {"comment": "信息有误"}
    )
    assert response.status == 400
    assert "不支持回退" in response.json["message"]

    # 空理由 → 400（必填校验先于状态校验）
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/rollback", {})
    assert response.status == 400
    assert response.json["message"] == "回退必须填写理由"


@pytest.mark.asyncio
async def test_invalid_state_transitions(test_client, auth_token, test_customer_with_balance):
    """AC7：非法状态流转一律 400"""
    customer_id = test_customer_with_balance["id"]
    settlement_id = await _create_settlement(test_client, auth_token, customer_id)

    # draft 直接 confirm-cs → 400
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")
    assert response.status == 400

    # 走到 completed
    await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-sales")
    await _post_action(
        test_client, auth_token, f"/{settlement_id}/confirm-sales-supervisor", {"comment": "同意"}
    )
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm")

    # completed 后 cancel → 400
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/cancel")
    assert response.status == 400


@pytest.mark.asyncio
async def test_sales_identity_check(test_client, auth_token, db_session):
    """AC8：非客户指定销售 confirm-sales → 400 身份校验消息"""
    # 造一个真实第二用户（FK 约束要求 sales_manager_id 必须存在）；
    # mock 权限缓存对所有用户返回全量权限，故该用户可正常通过鉴权。
    other_username = f"vr_other_{uuid.uuid4().hex[:8]}"
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, real_name, is_active,
                           created_at, updated_at)
        VALUES (:username, 'x', '其他销售', true, NOW(), NOW())
        """),
        {"username": other_username},
    )
    other_user_id = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"), {"username": other_username}
    ).scalar_one()
    db_session.commit()

    customer_id = _unique_customer_id()
    await _create_customer(db_session, customer_id, sales_manager_id=other_user_id)
    try:
        settlement_id = await _create_settlement(test_client, auth_token, customer_id)
        await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
        await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")

        # admin 不是该客户指定销售 → 400
        _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-sales")
        assert response.status == 400
        assert response.json["message"] == "您不是该客户指定的销售，无权确认"
    finally:
        for stmt in (
            "DELETE FROM vr_settlement_discount_histories WHERE settlement_id IN "
            "(SELECT id FROM vr_settlements WHERE customer_id = :id)",
            "DELETE FROM vr_settlements WHERE customer_id = :id",
            "DELETE FROM customers WHERE id = :id",
            "DELETE FROM users WHERE id = :uid",
        ):
            db_session.execute(text(stmt), {"id": customer_id, "uid": other_user_id})
        db_session.commit()


@pytest.mark.asyncio
async def test_customer_confirm_identity_check(test_client, auth_token, test_customer, db_session):
    """客户确认节点同样限该客户指定销售：更换销售后原销售 confirm → 400"""
    customer_id = test_customer["id"]

    # 推进到 pending_customer（admin 为该客户默认指定销售）
    settlement_id = await _create_settlement(test_client, auth_token, customer_id)
    await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-cs")
    await _post_action(test_client, auth_token, f"/{settlement_id}/confirm-sales")
    _, response = await _post_action(
        test_client,
        auth_token,
        f"/{settlement_id}/confirm-sales-supervisor",
        {"comment": "同意"},
    )
    assert response.status == 200, response.json

    # 更换客户指定销售为另一用户 → admin 失去客户确认资格
    other_username = f"vr_confirm_other_{uuid.uuid4().hex[:8]}"
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, real_name, is_active,
                           created_at, updated_at)
        VALUES (:username, 'x', '新任销售', true, NOW(), NOW())
        """),
        {"username": other_username},
    )
    other_user_id = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"), {"username": other_username}
    ).scalar_one()
    db_session.execute(
        text("UPDATE customers SET sales_manager_id = :uid WHERE id = :id"),
        {"uid": other_user_id, "id": customer_id},
    )
    db_session.commit()

    try:
        _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/confirm")
        assert response.status == 400
        assert response.json["message"] == "您不是该客户指定的销售经理，无权确认"
        # 状态不变，仍停留在 pending_customer
        assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == (
            "pending_customer"
        )
    finally:
        # 先解除 customers 对 other_user 的 FK 引用，再删用户（fixture teardown 随后删客户）
        db_session.execute(
            text("UPDATE customers SET sales_manager_id = NULL WHERE id = :id"),
            {"id": customer_id},
        )
        db_session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": other_user_id})
        db_session.commit()


@pytest.mark.asyncio
async def test_submit_requires_customer_sales_manager(test_client, auth_token, db_session):
    """AC9：客户未指定销售 → submit → 400"""
    customer_id = _unique_customer_id()
    await _create_customer(db_session, customer_id, sales_manager_id=None)
    try:
        settlement_id = await _create_settlement(test_client, auth_token, customer_id)
        _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/submit")
        assert response.status == 400
        assert response.json["message"] == "该客户未指定销售经理，无法提交审批"
    finally:
        for stmt in (
            "DELETE FROM vr_settlement_discount_histories WHERE settlement_id IN "
            "(SELECT id FROM vr_settlements WHERE customer_id = :id)",
            "DELETE FROM vr_settlements WHERE customer_id = :id",
            "DELETE FROM customers WHERE id = :id",
        ):
            db_session.execute(text(stmt), {"id": customer_id})
        db_session.commit()


@pytest.mark.asyncio
async def test_cancel_and_delete(test_client, auth_token, test_customer):
    """AC10：非终态可取消（再取消 400）；草稿可删除（软删除后 404）"""
    customer_id = test_customer["id"]

    # 取消
    settlement_id = await _create_settlement(test_client, auth_token, customer_id)
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/cancel")
    assert response.status == 200, response.json
    assert (await _get_detail(test_client, auth_token, settlement_id))["status"] == "cancelled"

    # 已取消再取消 → 400
    _, response = await _post_action(test_client, auth_token, f"/{settlement_id}/cancel")
    assert response.status == 400

    # 删除（软删除）
    settlement_id2 = await _create_settlement(test_client, auth_token, customer_id)
    request, response = await test_client.delete(
        f"/api/v1/billing/vr-settlements/{settlement_id2}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200, response.json

    # 软删除后详情 404
    request, response = await test_client.get(
        f"/api/v1/billing/vr-settlements/{settlement_id2}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 404


@pytest.mark.asyncio
async def test_create_validation_errors(test_client, auth_token, test_customer):
    """AC1 补充：创建参数校验（缺文件/金额非正数/日期格式）"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 缺 detail_file_path
    _, response = await test_client.post(
        "/api/v1/billing/vr-settlements",
        json={
            "customer_id": customer_id,
            "period_start": "2026-11-01",
            "period_end": "2026-11-30",
            "total_amount": 500,
        },
        headers=headers,
    )
    assert response.status == 400
    assert response.json["message"] == "请上传结算明细文件"

    # total_amount <= 0
    _, response = await test_client.post(
        "/api/v1/billing/vr-settlements",
        json=_create_payload(customer_id, total_amount=0),
        headers=headers,
    )
    assert response.status == 400
    assert response.json["message"] == "结算金额必须大于 0"

    # 日期格式错误
    _, response = await test_client.post(
        "/api/v1/billing/vr-settlements",
        json={
            "customer_id": customer_id,
            "period_start": "2026/11/01",
            "period_end": "2026-11-30",
            "total_amount": 500,
            "detail_file_path": "/uploads/test.xlsx",
        },
        headers=headers,
    )
    assert response.status == 400
    assert response.json["message"] == "日期格式错误，应为 YYYY-MM-DD"


@pytest.mark.asyncio
async def test_create_with_remark(test_client, auth_token, test_customer):
    """备注说明：创建时携带多行备注 → 详情/列表均回显；不传时为 None"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]
    remark_text = "第一行备注\n第二行备注\n第三行"

    # 带备注创建
    settlement_id = await _create_settlement(
        test_client, auth_token, customer_id, remark=remark_text
    )
    detail = await _get_detail(test_client, auth_token, settlement_id)
    assert detail["remark"] == remark_text

    # 列表同样回显 remark
    _, response = await test_client.get(
        f"/api/v1/billing/vr-settlements?keyword={detail['settlement_no']}", headers=headers
    )
    assert response.status == 200
    item = next(i for i in response.json["data"]["list"] if i["id"] == settlement_id)
    assert item["remark"] == remark_text

    # 不传 remark → None
    settlement_id_2 = await _create_settlement(test_client, auth_token, customer_id)
    detail_2 = await _get_detail(test_client, auth_token, settlement_id_2)
    assert detail_2["remark"] is None


@pytest.mark.asyncio
async def test_list_filter_by_status_and_keyword(test_client, auth_token, test_customer):
    """AC12 列表筛选：status 非法值 400；keyword 可按结算单号命中"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # status 非法值 → 400 且消息含有效值清单
    _, response = await test_client.get(
        "/api/v1/billing/vr-settlements?status=bogus", headers=headers
    )
    assert response.status == 400
    assert "无效的状态值" in response.json["message"]

    # 创建一单后用结算单号关键词命中
    settlement_id = await _create_settlement(test_client, auth_token, test_customer["id"])
    detail = await _get_detail(test_client, auth_token, settlement_id)
    _, response = await test_client.get(
        f"/api/v1/billing/vr-settlements?keyword={detail['settlement_no']}", headers=headers
    )
    assert response.status == 200
    ids = [item["id"] for item in response.json["data"]["list"]]
    assert settlement_id in ids
