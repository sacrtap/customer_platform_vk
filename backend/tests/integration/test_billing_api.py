"""
Billing API 集成测试

测试覆盖：
1. GET /api/v1/billing/balances - 获取余额列表
2. GET /api/v1/billing/customers/:id/balance - 获取客户余额
3. POST /api/v1/billing/recharge - 充值
4. GET /api/v1/billing/invoices - 结算单列表
5. POST /api/v1/billing/invoices/generate - 生成结算单
6. POST /api/v1/billing/invoices/:id/submit - 提交结算单
7. POST /api/v1/billing/invoices/:id/confirm - 确认结算单
8. POST /api/v1/billing/invoices/:id/pay - 付款
9. POST /api/v1/billing/invoices/:id/complete - 完成结算
"""

import pytest
from sqlalchemy import text


@pytest.fixture
async def auth_token(test_client, test_user):
    """获取认证 Token"""
    login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert login_response.status == 200
    return login_response.json["data"]["access_token"]


@pytest.fixture
async def test_customer(db_session, test_user):
    """创建测试客户"""
    customer_id = 99999
    company_id = customer_id  # company_id 现在是 Integer 类型
    customer_name = f"测试客户_{customer_id}"

    db_session.execute(
        text("DELETE FROM customers WHERE id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text(
            """
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, :account_type,
                :cycle, :type, NOW(), NOW())
        """
        ),
        {
            "id": customer_id,
            "company_id": company_id,
            "name": customer_name,
            "account_type": "enterprise",
            "cycle": "monthly",
            "type": "prepaid",
        },
    )
    db_session.commit()

    yield {"id": customer_id, "name": customer_name}

    # 使用 CASCADE 删除所有关联记录（按外键依赖顺序）
    db_session.execute(
        text(
            "DELETE FROM invoice_items WHERE invoice_id IN (SELECT id FROM invoices WHERE customer_id = :id)"
        ),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM invoices WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM recharge_records WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.commit()


@pytest.fixture
async def test_customer_with_balance(db_session, test_customer):
    """创建有余额的测试客户"""
    customer_id = test_customer["id"]

    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :cid"),
        {"cid": customer_id},
    )
    db_session.execute(
        text(
            """
        INSERT INTO customer_balances
            (customer_id, total_amount, real_amount, bonus_amount,
             used_total, used_real, used_bonus, created_at, updated_at)
        VALUES (:cid, :total, :real, :bonus, :used_total, :used_real, :used_bonus, NOW(), NOW())
        """
        ),
        {
            "cid": customer_id,
            "total": 50000.00,
            "real": 40000.00,
            "bonus": 10000.00,
            "used_total": 5000.00,
            "used_real": 4000.00,
            "used_bonus": 1000.00,
        },
    )
    db_session.commit()

    yield test_customer

    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :cid"),
        {"cid": customer_id},
    )
    db_session.commit()


# ==================== 余额管理测试 ====================


@pytest.mark.asyncio
async def test_get_balances_list(test_client, auth_token, test_customer_with_balance):
    """测试获取余额列表 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/balances",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "list" in data["data"]
    assert "total" in data["data"]


@pytest.mark.asyncio
async def test_get_customer_balance_exists(test_client, auth_token, test_customer_with_balance):
    """测试获取客户余额 - 余额存在"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

    request, response = await test_client.get(
        f"/api/v1/billing/customers/{customer_id}/balance",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["real_amount"] == 40000.00
    assert data["data"]["bonus_amount"] == 10000.00
    assert data["data"]["total_amount"] == 50000.00


@pytest.mark.asyncio
async def test_get_customer_balance_not_exists(test_client, auth_token, test_customer):
    """测试获取客户余额 - 余额不存在（返回 0）"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.get(
        f"/api/v1/billing/customers/{customer_id}/balance",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["real_amount"] == 0
    assert data["data"]["bonus_amount"] == 0
    assert data["data"]["total_amount"] == 0


@pytest.mark.asyncio
async def test_recharge_success(test_client, auth_token, test_customer):
    """测试充值 API - 成功"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 10000.00,
            "bonus_amount": 2000.00,
            "remark": "测试充值",
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "充值成功"
    assert data["data"]["real_amount"] == 10000.00
    assert data["data"]["bonus_amount"] == 2000.00
    assert data["data"]["total_amount"] == 12000.00


@pytest.mark.asyncio
async def test_recharge_missing_customer_id(test_client, auth_token):
    """测试充值 API - 缺少客户 ID"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "real_amount": 10000.00,
        },
        headers=headers,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40001
    assert "客户 ID" in data["message"]


@pytest.mark.asyncio
async def test_recharge_zero_amount(test_client, auth_token, test_customer):
    """测试充值 API - 金额为 0"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 0,
        },
        headers=headers,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40001


# ==================== 结算单管理测试 ====================


@pytest.mark.asyncio
async def test_get_invoices_list(test_client, auth_token):
    """测试获取结算单列表 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "list" in data["data"]
    assert "total" in data["data"]


@pytest.mark.asyncio
async def test_generate_invoice_success(test_client, auth_token, test_customer):
    """测试生成结算单 API - 成功"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 100,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "生成成功"
    assert "id" in data["data"]
    assert "invoice_no" in data["data"]
    assert data["data"]["total_amount"] == 1000.00

    return data["data"]["id"]


@pytest.mark.asyncio
async def test_generate_invoice_empty_items(test_client, auth_token, test_customer):
    """测试生成结算单 API - 结算项为空"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [],
        },
        headers=headers,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40001
    assert "结算项" in data["message"]


@pytest.mark.asyncio
async def test_invoice_workflow_full(test_client, auth_token, test_customer_with_balance):
    """测试结算单完整工作流：生成 -> 提交 -> 确认 -> 付款 -> 完成"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

    # 1. 生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 50,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    assert gen_res.status == 201
    invoice_id = gen_res.json["data"]["id"]

    # 2. 提交结算单
    submit_req, submit_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res.status == 200
    assert submit_res.json["code"] == 0

    # 3. 确认结算单
    confirm_req, confirm_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm",
        headers=headers,
    )
    assert confirm_res.status == 200
    assert confirm_res.json["code"] == 0

    # 4. 付款
    pay_req, pay_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay",
        json={"payment_proof": "/uploads/proof.png"},
        headers=headers,
    )
    assert pay_res.status == 200
    assert pay_res.json["code"] == 0

    # 5. 完成结算（扣款）
    complete_req, complete_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/complete",
        headers=headers,
    )
    assert complete_res.status == 200
    assert complete_res.json["code"] == 0
    assert complete_res.json["message"] == "结算完成"


@pytest.mark.asyncio
async def test_submit_invoice_invalid_state(test_client, auth_token, test_customer):
    """测试提交结算单 - 状态不允许"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 先生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 提交一次（成功）
    submit_req, submit_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res.status == 200

    # 再次提交（应该失败，因为状态已变更）
    submit_req2, submit_res2 = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res2.status == 400
    assert submit_res2.json["code"] == 40001


@pytest.mark.asyncio
async def test_confirm_invoice_invalid_state(test_client, auth_token, test_customer):
    """测试确认结算单 - 状态不允许"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单后直接确认（不先提交）
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 直接确认（应该失败，因为状态是 draft）
    confirm_req, confirm_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm",
        headers=headers,
    )
    assert confirm_res.status == 400
    assert confirm_res.json["code"] == 40001


@pytest.mark.asyncio
async def test_pay_invoice_invalid_state(test_client, auth_token, test_customer):
    """测试付款 - 状态不允许"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单后直接付款
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 直接付款（应该失败）
    pay_req, pay_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay",
        json={"payment_proof": "/uploads/proof.png"},
        headers=headers,
    )
    assert pay_res.status == 400
    assert pay_res.json["code"] == 40001


@pytest.mark.asyncio
async def test_complete_invoice_insufficient_balance(test_client, auth_token, test_customer):
    """测试完成结算 - 余额不足"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成一个金额很大的结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 100000,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 提交
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/submit", headers=headers)
    # 确认
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/confirm", headers=headers)
    # 付款
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/pay", headers=headers)

    # 完成结算（应该失败，因为客户没有余额）
    complete_req, complete_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/complete",
        headers=headers,
    )
    assert complete_res.status == 400
    assert complete_res.json["code"] == 40001
    assert "余额不足" in complete_res.json["message"]


@pytest.mark.asyncio
async def test_get_invoice_detail(test_client, auth_token, test_customer):
    """测试获取结算单详情 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 先生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 获取详情
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )

    assert detail_res.status == 200
    data = detail_res.json
    assert data["code"] == 0
    assert "data" in data
    assert data["data"]["id"] == invoice_id
    assert "items" in data["data"]
    assert len(data["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_get_invoice_not_found(test_client, auth_token):
    """测试获取结算单详情 - 不存在"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices/999999",
        headers=headers,
    )

    assert response.status == 404
    data = response.json
    assert data["code"] == 40401
    assert "不存在" in data["message"]


@pytest.mark.asyncio
async def test_apply_discount(test_client, auth_token, test_customer):
    """测试应用减免 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 100,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 应用减免
    discount_req, discount_res = await test_client.put(
        f"/api/v1/billing/invoices/{invoice_id}/discount",
        json={
            "discount_amount": 100.00,
            "discount_reason": "大客户优惠",
        },
        headers=headers,
    )

    assert discount_res.status == 200
    assert discount_res.json["code"] == 0
    assert discount_res.json["message"] == "减免应用成功"


@pytest.mark.asyncio
async def test_delete_invoice(test_client, auth_token, test_customer):
    """测试删除结算单 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 删除
    del_req, del_res = await test_client.delete(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )

    assert del_res.status == 200
    assert del_res.json["code"] == 0
    assert del_res.json["message"] == "删除成功"


@pytest.mark.asyncio
async def test_cancel_invoice_success(test_client, auth_token, test_customer):
    """测试取消结算单 API - 成功"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单（草稿状态）
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 提交到 pending_customer 状态
    await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )

    # 取消
    cancel_req, cancel_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/cancel",
        headers=headers,
    )

    assert cancel_res.status == 200
    assert cancel_res.json["code"] == 0
    assert "取消成功" in cancel_res.json["message"]

    # 验证状态已更新
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )
    assert detail_res.json["data"]["status"] == "cancelled"
    assert detail_res.json["data"]["cancelled_at"] is not None


@pytest.mark.asyncio
async def test_cancel_invoice_wrong_state(test_client, auth_token, test_customer):
    """测试取消结算单 API - 错误状态"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 提交并确认，使其进入 customer_confirmed 状态
    submit_req, submit_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res.status == 200, f"Submit failed: {submit_res.json}"

    confirm_req, confirm_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm",
        headers=headers,
    )
    assert confirm_res.status == 200, f"Confirm failed: {confirm_res.json}"

    # 验证状态已变为 customer_confirmed
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )
    assert detail_res.json["data"]["status"] == "customer_confirmed"

    # 尝试取消（应该失败）
    cancel_req, cancel_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/cancel",
        headers=headers,
    )

    assert cancel_res.status == 400
    assert cancel_res.json["code"] == 40001
    assert "不能取消" in cancel_res.json["message"]


@pytest.mark.asyncio
async def test_get_recharge_records(test_client, auth_token, test_customer_with_balance):
    """测试获取充值记录 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

    request, response = await test_client.get(
        f"/api/v1/billing/recharge-records?customer_id={customer_id}",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "list" in data["data"]


@pytest.mark.asyncio
async def test_get_consumption_records(test_client, auth_token):
    """测试获取消费记录 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/consumption-records",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "list" in data["data"]


@pytest.mark.asyncio
async def test_get_pricing_rules(test_client, auth_token):
    """测试获取定价规则 API（分页格式）"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/pricing-rules",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert "list" in data["data"]
    assert "total" in data["data"]
    assert isinstance(data["data"]["list"], list)


@pytest.mark.asyncio
async def test_create_pricing_rule(test_client, auth_token):
    """测试创建定价规则 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.post(
        "/api/v1/billing/pricing-rules",
        json={
            "device_type": "X",
            "pricing_type": "fixed",
            "unit_price": 10.00,
            "effective_date": "2026-04-01",
            "expiry_date": "2026-12-31",
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "创建成功"
    assert data["data"]["device_type"] == "X"
    assert data["data"]["pricing_type"] == "fixed"


@pytest.mark.asyncio
async def test_unauthorized_access(test_client):
    """测试未授权访问"""
    request, response = await test_client.get("/api/v1/billing/balances")

    assert response.status in [401, 403]


@pytest.mark.asyncio
async def test_invalid_token(test_client):
    """测试无效 Token"""
    headers = {"Authorization": "Bearer invalid_token_xyz123"}

    request, response = await test_client.get(
        "/api/v1/billing/balances",
        headers=headers,
    )

    assert response.status == 401


# ==================== 定价规则冲突检查测试 ====================


@pytest.mark.asyncio
async def test_check_pricing_rule_conflict_has_conflict(test_client, auth_token, db_session):
    """测试冲突检查 API — 有冲突"""
    # 先创建一个客户（使用子查询获取 manager_id）
    from sqlalchemy import text
    
    # 获取第一个用户的 ID
    result = db_session.execute(text("SELECT id FROM users LIMIT 1"))
    user_row = result.fetchone()
    manager_id = user_row[0] if user_row else 1
    
    customer_id = 99998
    company_id = 99998
    
    # 清理旧数据
    db_session.execute(text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id})
    db_session.execute(text("DELETE FROM customer_balances WHERE customer_id = :id"), {"id": customer_id})
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.commit()
    
    # 创建客户
    db_session.execute(
        text(
            """
        INSERT INTO customers (id, company_id, name, account_type,
                               manager_id, settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, :account_type,
                :manager_id, :cycle, :type, NOW(), NOW())
        """
        ),
        {
            "id": customer_id,
            "company_id": company_id,
            "name": "测试客户_99998",
            "account_type": "enterprise",
            "manager_id": manager_id,
            "cycle": "monthly",
            "type": "prepaid",
        },
    )
    db_session.commit()
    
    # 先创建一条规则（指定 customer_id）
    create_req, create_resp = await test_client.post(
        "/api/v1/billing/pricing-rules",
        json={
            "customer_id": customer_id,
            "device_type": "X",
            "layer_type": "single",
            "pricing_type": "fixed",
            "unit_price": 10.0,
            "effective_date": "2026-01-01",
            "expiry_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert create_resp.status == 201, f"创建规则失败: {create_resp.json}"

    # 检查冲突（使用相同的 customer_id, device_type 和 layer_type，但不同时间段）
    check_req, check_resp = await test_client.get(
        "/api/v1/billing/pricing-rules/check-conflict",
        params={
            "customer_id": customer_id,
            "device_type": "X",
            "layer_type": "single",
            "effective_date": "2026-06-01",
            "expiry_date": "2026-09-30",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert check_resp.status == 200
    data = check_resp.json
    assert data["code"] == 0
    assert data["data"]["has_conflict"] is True
    assert len(data["data"]["conflicting_rules"]) > 0
    
    # 清理
    db_session.execute(text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id})
    db_session.commit()


@pytest.mark.asyncio
async def test_check_pricing_rule_conflict_no_conflict(test_client, auth_token, db_session):
    """测试冲突检查 API — 无冲突"""
    # 先创建一个客户（使用子查询获取 manager_id）
    from sqlalchemy import text
    
    # 获取第一个用户的 ID
    result = db_session.execute(text("SELECT id FROM users LIMIT 1"))
    user_row = result.fetchone()
    manager_id = user_row[0] if user_row else 1
    
    customer_id = 99997
    company_id = 99997
    
    # 清理旧数据
    db_session.execute(text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id})
    db_session.execute(text("DELETE FROM customer_balances WHERE customer_id = :id"), {"id": customer_id})
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.commit()
    
    # 创建客户
    db_session.execute(
        text(
            """
        INSERT INTO customers (id, company_id, name, account_type,
                               manager_id, settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, :account_type,
                :manager_id, :cycle, :type, NOW(), NOW())
        """
        ),
        {
            "id": customer_id,
            "company_id": company_id,
            "name": "测试客户_99997",
            "account_type": "enterprise",
            "manager_id": manager_id,
            "cycle": "monthly",
            "type": "prepaid",
        },
    )
    db_session.commit()
    
    response_req, response_resp = await test_client.get(
        "/api/v1/billing/pricing-rules/check-conflict",
        params={
            "customer_id": customer_id,
            "device_type": "Y",  # 使用不同的 device_type，确保无冲突
            "layer_type": "single",
            "effective_date": "2027-01-01",
            "expiry_date": "2027-12-31",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response_resp.status == 200
    data = response_resp.json
    assert data["code"] == 0
    assert data["data"]["has_conflict"] is False
    assert len(data["data"]["conflicting_rules"]) == 0
    
    # 清理
    db_session.execute(text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id})
    db_session.execute(text("DELETE FROM customer_balances WHERE customer_id = :id"), {"id": customer_id})
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.commit()
