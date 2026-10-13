"""余额白名单路由集成测试

覆盖:
1. GET /api/v1/balance-whitelists — 未认证 / 列表 / keyword 过滤
2. POST /api/v1/balance-whitelists — 单独添加（默认余额 / 指定余额 / 客户不存在 / 重复添加 / 软删恢复）
3. POST /api/v1/balance-whitelists/batch-import — ERP 批量导入（计数 / 幂等跳过 / 软删恢复 / 停用删除客户排除）
4. PUT /api/v1/balance-whitelists/<id> — 编辑余额（含备注：提交/去空白/清空/不传保持/超长拒绝）
5. DELETE /api/v1/balance-whitelists/<id> — 移出白名单
6. 权限 — 无 balance_whitelist:manage 权限 → 403
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text


def _insert_customer(
    db_session,
    *,
    company_id,
    name,
    erp_system=None,
    is_disabled=False,
    deleted_at=None,
):
    """插入客户，返回客户 id"""
    return db_session.execute(
        text("""
            INSERT INTO customers
                (company_id, name, erp_system, is_disabled, deleted_at, created_at, updated_at)
            VALUES (:company_id, :name, :erp_system, :is_disabled, :deleted_at, NOW(), NOW())
            RETURNING id
        """),
        {
            "company_id": company_id,
            "name": name,
            "erp_system": erp_system,
            "is_disabled": is_disabled,
            "deleted_at": deleted_at,
        },
    ).scalar()


@pytest.fixture
async def auth_headers(auth_token):
    """获取认证请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


def _insert_whitelist(db_session, customer_id, static_balance, remark=None):
    """插入白名单记录，返回 id"""
    return db_session.execute(
        text("""
            INSERT INTO balance_whitelists (customer_id, static_balance, remark, created_at, updated_at)
            VALUES (:cid, :sb, :remark, NOW(), NOW())
            RETURNING id
        """),
        {"cid": customer_id, "sb": static_balance, "remark": remark},
    ).scalar()


class TestListBalanceWhitelist:
    """测试 GET /api/v1/balance-whitelists"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.get("/api/v1/balance-whitelists")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_returns_list(self, test_client, auth_headers, db_session):
        """认证后返回白名单列表（含客户名称/公司ID/ERP）"""
        cid1 = _insert_customer(
            db_session, company_id=1001, name="白名单客户A", erp_system="erp_cloud"
        )
        _insert_customer(db_session, company_id=1002, name="非白名单客户", erp_system="none")
        whitelist_id = _insert_whitelist(db_session, cid1, 1000)
        db_session.commit()

        _req, response = await test_client.get(
            "/api/v1/balance-whitelists",
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["data"]["total"] == 1
        item = data["data"]["items"][0]
        assert item["id"] == whitelist_id
        assert item["customer_id"] == cid1
        assert item["company_id"] == 1001
        assert item["customer_name"] == "白名单客户A"
        assert item["erp_system"] == "erp_cloud"
        assert item["static_balance"] == 1000.0
        assert item["remark"] is None

    @pytest.mark.asyncio
    async def test_keyword_filters(self, test_client, auth_headers, db_session):
        """keyword 按客户名称模糊 / 公司ID精确过滤"""
        cid1 = _insert_customer(db_session, company_id=2001, name="巧房科技", erp_system="qiaofang")
        cid2 = _insert_customer(db_session, company_id=2002, name="鼎尖信息", erp_system="dingjian")
        _insert_whitelist(db_session, cid1, 1000)
        _insert_whitelist(db_session, cid2, 2000)
        db_session.commit()

        # 名称模糊
        _req, response = await test_client.get(
            "/api/v1/balance-whitelists",
            params={"keyword": "巧房"},
            headers=auth_headers,
        )
        assert response.status == 200
        items = response.json["data"]["items"]
        assert [i["company_id"] for i in items] == [2001]

        # 公司ID精确
        _req, response = await test_client.get(
            "/api/v1/balance-whitelists",
            params={"keyword": "2002"},
            headers=auth_headers,
        )
        assert response.status == 200
        items = response.json["data"]["items"]
        assert [i["company_id"] for i in items] == [2002]


class TestAddBalanceWhitelist:
    """测试 POST /api/v1/balance-whitelists"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists", json={"customer_id": 1}
        )
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_add_default_balance(self, test_client, auth_headers, db_session):
        """单独添加，静态余额默认 1000 元"""
        cid = _insert_customer(db_session, company_id=3001, name="新客户")
        db_session.commit()

        _req, response = await test_client.post(
            "/api/v1/balance-whitelists",
            json={"customer_id": cid},
            headers=auth_headers,
        )
        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["customer_id"] == cid
        assert data["data"]["static_balance"] == 1000.0

    @pytest.mark.asyncio
    async def test_add_custom_balance(self, test_client, auth_headers, db_session):
        """单独添加，指定静态余额"""
        cid = _insert_customer(db_session, company_id=3002, name="定制余额客户")
        db_session.commit()

        _req, response = await test_client.post(
            "/api/v1/balance-whitelists",
            json={"customer_id": cid, "static_balance": 5000},
            headers=auth_headers,
        )
        assert response.status == 201
        assert response.json["data"]["static_balance"] == 5000.0

    @pytest.mark.asyncio
    async def test_add_customer_not_found(self, test_client, auth_headers, db_session):
        """客户不存在 → 400"""
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists",
            json={"customer_id": 999999},
            headers=auth_headers,
        )
        assert response.status == 400
        assert "不存在" in response.json["message"]

    @pytest.mark.asyncio
    async def test_add_duplicate(self, test_client, auth_headers, db_session):
        """重复添加已存在客户 → 400"""
        cid = _insert_customer(db_session, company_id=3003, name="重复客户")
        db_session.commit()
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists",
            json={"customer_id": cid},
            headers=auth_headers,
        )
        assert response.status == 201

        _req, response = await test_client.post(
            "/api/v1/balance-whitelists",
            json={"customer_id": cid},
            headers=auth_headers,
        )
        assert response.status == 400
        assert "已在余额白名单中" in response.json["message"]

    @pytest.mark.asyncio
    async def test_add_negative_balance(self, test_client, auth_headers, db_session):
        """静态余额为负 → 400"""
        cid = _insert_customer(db_session, company_id=3004, name="负数客户")
        db_session.commit()

        _req, response = await test_client.post(
            "/api/v1/balance-whitelists",
            json={"customer_id": cid, "static_balance": -100},
            headers=auth_headers,
        )
        assert response.status == 400
        assert "负数" in response.json["message"]

    @pytest.mark.asyncio
    async def test_add_after_soft_delete_restores(self, test_client, auth_headers, db_session):
        """移出后重新添加 → 恢复记录（非报错）"""
        cid = _insert_customer(db_session, company_id=3005, name="重入客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000)
        db_session.commit()

        # 移出（软删）
        _req, response = await test_client.delete(
            f"/api/v1/balance-whitelists/{wid}",
            headers=auth_headers,
        )
        assert response.status == 200

        # 重新添加 → 恢复成功
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists",
            json={"customer_id": cid, "static_balance": 2500},
            headers=auth_headers,
        )
        assert response.status == 201
        assert response.json["data"]["id"] == wid
        assert response.json["data"]["static_balance"] == 2500.0


class TestBatchImport:
    """测试 POST /api/v1/balance-whitelists/batch-import"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists/batch-import", json={"erp_system_value": "x"}
        )
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_requires_erp_value(self, test_client, auth_headers):
        """缺少 erp_system_value → 400"""
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists/batch-import",
            json={},
            headers=auth_headers,
        )
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_imports_all_erp_customers(self, test_client, auth_headers, db_session):
        """按 ERP 批量导入：仅该 ERP 有效客户，默认余额 1000"""
        _insert_customer(db_session, company_id=4001, name="ERP-A客户1", erp_system="erp_a")
        _insert_customer(db_session, company_id=4002, name="ERP-A客户2", erp_system="erp_a")
        _insert_customer(db_session, company_id=4003, name="ERP-B客户", erp_system="erp_b")
        # 停用/删除客户不导入
        _insert_customer(
            db_session, company_id=4004, name="停用客户", erp_system="erp_a", is_disabled=True
        )
        from datetime import datetime

        _insert_customer(
            db_session,
            company_id=4005,
            name="删除客户",
            erp_system="erp_a",
            deleted_at=datetime(2026, 1, 1),
        )
        db_session.commit()

        _req, response = await test_client.post(
            "/api/v1/balance-whitelists/batch-import",
            json={"erp_system_value": "erp_a"},
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json["data"]
        assert data["imported"] == 2
        assert data["skipped"] == 0

        # 校验落库值与默认余额
        rows = db_session.execute(
            text("""
                SELECT c.company_id, w.static_balance
                FROM balance_whitelists w
                JOIN customers c ON c.id = w.customer_id
                WHERE w.deleted_at IS NULL
            """)
        ).all()
        assert {r[0] for r in rows} == {4001, 4002}
        assert all(float(r[1]) == 1000.0 for r in rows)

    @pytest.mark.asyncio
    async def test_reimport_skips_without_overwrite(self, test_client, auth_headers, db_session):
        """重复导入跳过已存在客户，不覆盖其静态余额（AC6）"""
        cid1 = _insert_customer(db_session, company_id=4101, name="ERP-A客户", erp_system="erp_a")
        _insert_customer(db_session, company_id=4102, name="ERP-A客户2", erp_system="erp_a")
        db_session.commit()

        _req, response = await test_client.post(
            "/api/v1/balance-whitelists/batch-import",
            json={"erp_system_value": "erp_a"},
            headers=auth_headers,
        )
        assert response.json["data"]["imported"] == 2

        # 编辑第一个客户余额为 8000
        wid = db_session.execute(
            text("SELECT id FROM balance_whitelists WHERE customer_id = :cid"),
            {"cid": cid1},
        ).scalar()
        db_session.commit()
        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 8000},
            headers=auth_headers,
        )
        assert response.status == 200

        # 再次批量导入 → 全部跳过，余额仍 8000
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists/batch-import",
            json={"erp_system_value": "erp_a"},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["imported"] == 0
        assert response.json["data"]["skipped"] == 2

        balance = db_session.execute(
            text("SELECT static_balance FROM balance_whitelists WHERE customer_id = :cid"),
            {"cid": cid1},
        ).scalar()
        assert float(balance) == 8000.0

    @pytest.mark.asyncio
    async def test_reimport_restores_soft_deleted(self, test_client, auth_headers, db_session):
        """软删记录重新导入 → 恢复且保留原余额"""
        cid1 = _insert_customer(db_session, company_id=4201, name="ERP-A客户", erp_system="erp_a")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid1, 6666)
        db_session.commit()

        # 移出（软删）
        _req, response = await test_client.delete(
            f"/api/v1/balance-whitelists/{wid}",
            headers=auth_headers,
        )
        assert response.status == 200

        # 重新批量导入 → 恢复，保留原余额 6666（不覆盖为 1000）
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists/batch-import",
            json={"erp_system_value": "erp_a"},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["imported"] == 1
        assert response.json["data"]["skipped"] == 0

        balance = db_session.execute(
            text("SELECT static_balance FROM balance_whitelists WHERE id = :wid"),
            {"wid": wid},
        ).scalar()
        assert float(balance) == 6666.0

    @pytest.mark.asyncio
    async def test_import_dry_run_no_side_effect(self, test_client, auth_headers, db_session):
        """dry_run 预检：返回计数但不落库（二次确认契约）"""
        _insert_customer(db_session, company_id=4301, name="ERP-A客户", erp_system="erp_a")
        _insert_customer(db_session, company_id=4302, name="ERP-A客户2", erp_system="erp_a")
        db_session.commit()

        # 预检 → 返回 imported=2 且不落库
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists/batch-import",
            params={"dry_run": "true"},
            json={"erp_system_value": "erp_a"},
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json
        assert data["message"] == "预检查完成"
        assert data["data"]["dry_run"] is True
        assert data["data"]["imported"] == 2
        assert data["data"]["skipped"] == 0

        # 未落库
        count = db_session.execute(
            text("SELECT COUNT(*) FROM balance_whitelists WHERE deleted_at IS NULL")
        ).scalar()
        assert count == 0

        # 真实导入 → 落库 2 条
        _req, response = await test_client.post(
            "/api/v1/balance-whitelists/batch-import",
            json={"erp_system_value": "erp_a"},
            headers=auth_headers,
        )
        assert response.json["data"]["imported"] == 2
        count = db_session.execute(
            text("SELECT COUNT(*) FROM balance_whitelists WHERE deleted_at IS NULL")
        ).scalar()
        assert count == 2


class TestUpdateBalanceWhitelist:
    """测试 PUT /api/v1/balance-whitelists/<id>"""

    @pytest.mark.asyncio
    async def test_updates_balance(self, test_client, auth_headers, db_session):
        """编辑静态余额成功"""
        cid = _insert_customer(db_session, company_id=5001, name="编辑客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000)
        db_session.commit()

        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 8888.88},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["static_balance"] == 8888.88

    @pytest.mark.asyncio
    async def test_not_found(self, test_client, auth_headers, db_session):
        """不存在的记录 → 404"""
        _req, response = await test_client.put(
            "/api/v1/balance-whitelists/999999",
            json={"static_balance": 1000},
            headers=auth_headers,
        )
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_negative_balance_rejected(self, test_client, auth_headers, db_session):
        """负余额 → 400"""
        cid = _insert_customer(db_session, company_id=5002, name="负数客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000)
        db_session.commit()

        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": -1},
            headers=auth_headers,
        )
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_updates_remark(self, test_client, auth_headers, db_session):
        """编辑时提交备注 → 响应与列表均返回该备注"""
        cid = _insert_customer(db_session, company_id=5003, name="备注客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000)
        db_session.commit()

        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 1200, "remark": "临时调额至月底"},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["remark"] == "临时调额至月底"

        # 列表回读
        _req, response = await test_client.get(
            "/api/v1/balance-whitelists",
            headers=auth_headers,
        )
        item = response.json["data"]["items"][0]
        assert item["remark"] == "临时调额至月底"
        assert item["static_balance"] == 1200.0

    @pytest.mark.asyncio
    async def test_remark_trimmed(self, test_client, auth_headers, db_session):
        """备注首尾空白被去除后存储"""
        cid = _insert_customer(db_session, company_id=5004, name="去空白客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000)
        db_session.commit()

        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 1000, "remark": "  有空格  "},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["remark"] == "有空格"

    @pytest.mark.asyncio
    async def test_remark_cleared(self, test_client, auth_headers, db_session):
        """备注传空串/None → 清空为 null"""
        cid = _insert_customer(db_session, company_id=5005, name="清空备注客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000, remark="原备注")
        db_session.commit()

        # 空串清空
        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 1000, "remark": "   "},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["remark"] is None

        # 先写回备注，再用 null 清空
        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 1000, "remark": "再写一条"},
            headers=auth_headers,
        )
        assert response.json["data"]["remark"] == "再写一条"

        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 1000, "remark": None},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["remark"] is None

    @pytest.mark.asyncio
    async def test_remark_absent_keeps_value(self, test_client, auth_headers, db_session):
        """不传 remark 键 → 备注保持不变（向后兼容）"""
        cid = _insert_customer(db_session, company_id=5006, name="保留备注客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000, remark="既有备注")
        db_session.commit()

        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 1500},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["static_balance"] == 1500.0
        assert response.json["data"]["remark"] == "既有备注"

    @pytest.mark.asyncio
    async def test_remark_too_long_rejected(self, test_client, auth_headers, db_session):
        """备注超过 200 字符 → 400"""
        cid = _insert_customer(db_session, company_id=5007, name="超长备注客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000)
        db_session.commit()

        _req, response = await test_client.put(
            f"/api/v1/balance-whitelists/{wid}",
            json={"static_balance": 1000, "remark": "a" * 201},
            headers=auth_headers,
        )
        assert response.status == 400
        assert "200" in response.json["message"]


class TestRemoveBalanceWhitelist:
    """测试 DELETE /api/v1/balance-whitelists/<id>"""

    @pytest.mark.asyncio
    async def test_removes_record(self, test_client, auth_headers, db_session):
        """移出白名单成功（软删除）"""
        cid = _insert_customer(db_session, company_id=6001, name="移除客户")
        db_session.commit()
        wid = _insert_whitelist(db_session, cid, 1000)
        db_session.commit()

        _req, response = await test_client.delete(
            f"/api/v1/balance-whitelists/{wid}",
            headers=auth_headers,
        )
        assert response.status == 200

        # 列表不再包含
        _req, response = await test_client.get(
            "/api/v1/balance-whitelists",
            headers=auth_headers,
        )
        assert response.json["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_remove_not_found(self, test_client, auth_headers):
        """不存在的记录 → 404"""
        _req, response = await test_client.delete(
            "/api/v1/balance-whitelists/999999",
            headers=auth_headers,
        )
        assert response.status == 404


class TestPermission:
    """测试权限控制"""

    @pytest.mark.asyncio
    async def test_missing_permission_forbidden(self, test_client, db_session):
        """无 balance_whitelist:manage 权限 → 403"""
        import bcrypt

        username = "noperm_whitelist"
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        password_hash = bcrypt.hashpw(b"test123456", bcrypt.gensalt()).decode()
        db_session.execute(
            text("""
            INSERT INTO users (username, password_hash, email, is_active, created_at)
            VALUES (:username, :password_hash, :email, :is_active, NOW())
            """),
            {
                "username": username,
                "password_hash": password_hash,
                "email": "nopermwl@example.com",
                "is_active": True,
            },
        )
        db_session.commit()

        try:
            login_request, login_response = await test_client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "test123456"},
            )
            assert login_response.status == 200
            token = login_response.json["data"]["access_token"]

            from app.cache import permissions as perm_module

            original_get = perm_module.permission_cache.get_permissions
            perm_module.permission_cache.get_permissions = AsyncMock(return_value=set())

            try:
                _request, response = await test_client.get(
                    "/api/v1/balance-whitelists",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status == 403
            finally:
                perm_module.permission_cache.get_permissions = original_get
        finally:
            db_session.execute(
                text("DELETE FROM users WHERE username = :username"),
                {"username": username},
            )
            db_session.commit()
