"""行业类型路由集成测试"""

import pytest


@pytest.fixture
async def auth_headers(auth_token):
    """获取认证请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestGetIndustryTypes:
    """测试 GET /api/v1/industry-types"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.get("/api/v1/industry-types")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_returns_success(self, test_client, auth_headers):
        """测试认证后成功返回行业类型列表"""
        _req, response = await test_client.get(
            "/api/v1/industry-types",
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert "data" in data
        assert isinstance(data["data"], list)


class TestCreateIndustryType:
    """测试 POST /api/v1/industry-types"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.post("/api/v1/industry-types")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_creates_success(self, test_client, auth_headers):
        """测试成功创建行业类型"""
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "测试行业", "sort_order": 100},
            headers=auth_headers,
        )
        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试行业"
        assert data["data"]["sort_order"] == 100
        assert "id" in data["data"]

    @pytest.mark.asyncio
    async def test_validates_required_fields(self, test_client, auth_headers):
        """测试缺少必填字段返回 422"""
        # 缺少 sort_order
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "测试行业"},
            headers=auth_headers,
        )
        assert response.status == 422

        # 缺少 name
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"sort_order": 100},
            headers=auth_headers,
        )
        assert response.status == 422

        # 都缺少
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={},
            headers=auth_headers,
        )
        assert response.status == 422

    @pytest.mark.asyncio
    async def test_prevents_duplicate_name(self, test_client, auth_headers):
        """测试重复名称返回 409"""
        # 创建第一个
        _req, _ = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "重复测试行业", "sort_order": 1},
            headers=auth_headers,
        )

        # 尝试创建同名
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "重复测试行业", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "已存在" in response.json["message"]


class TestUpdateIndustryType:
    """测试 PUT /api/v1/industry-types/{id}"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.put("/api/v1/industry-types/1")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_updates_success(self, test_client, auth_headers):
        """测试成功更新行业类型"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "原始名称", "sort_order": 1},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 更新
        _req, response = await test_client.put(
            f"/api/v1/industry-types/{industry_id}",
            json={"name": "新名称", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "新名称"
        assert data["data"]["sort_order"] == 2

    @pytest.mark.asyncio
    async def test_returns_404_for_not_found(self, test_client, auth_headers):
        """测试不存在的 ID 返回 404"""
        _req, response = await test_client.put(
            "/api/v1/industry-types/99999",
            json={"name": "新名称", "sort_order": 1},
            headers=auth_headers,
        )
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_validates_required_fields(self, test_client, auth_headers):
        """测试缺少必填字段返回 422"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "原始名称", "sort_order": 1},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 缺少 sort_order
        _req, response = await test_client.put(
            f"/api/v1/industry-types/{industry_id}",
            json={"name": "新名称"},
            headers=auth_headers,
        )
        assert response.status == 422

    @pytest.mark.asyncio
    async def test_prevents_duplicate_name(self, test_client, auth_headers):
        """测试更新时重复名称返回 409"""
        # 创建两个行业类型
        _req, resp1 = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "行业A", "sort_order": 1},
            headers=auth_headers,
        )
        id_a = resp1.json["data"]["id"]

        _req, resp2 = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "行业B", "sort_order": 2},
            headers=auth_headers,
        )

        # 尝试将行业A更新为行业B的名称（应失败）
        _req, response = await test_client.put(
            f"/api/v1/industry-types/{id_a}",
            json={"name": "行业B", "sort_order": 3},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "已存在" in response.json["message"]


class TestDeleteIndustryType:
    """测试 DELETE /api/v1/industry-types/{id}"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.delete("/api/v1/industry-types/1")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_deletes_success(self, test_client, auth_headers):
        """测试成功软删除"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "待删除", "sort_order": 1},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 删除
        _req, response = await test_client.delete(
            f"/api/v1/industry-types/{industry_id}",
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["code"] == 0

        # 验证不再出现在列表中
        _req, list_resp = await test_client.get("/api/v1/industry-types", headers=auth_headers)
        ids = [item["id"] for item in list_resp.json["data"]]
        assert industry_id not in ids

    @pytest.mark.asyncio
    async def test_returns_404_for_not_found(self, test_client, auth_headers):
        """测试不存在的 ID 返回 404"""
        _req, response = await test_client.delete(
            "/api/v1/industry-types/99999",
            headers=auth_headers,
        )
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_rejects_delete_when_industry_in_use(self, test_client, auth_headers, db_session):
        """被客户画像引用的行业禁止删除（共享主数据引用保护）"""
        from sqlalchemy import text

        # 造一个被引用的行业
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "被引用行业", "sort_order": 50},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 造一个引用该行业的客户画像（最小化：仅 industry_type_id）
        db_session.execute(
            text(
                """
                INSERT INTO customer_profiles (industry_type_id, created_at, updated_at)
                VALUES (:itid, NOW(), NOW())
                """
            ),
            {"itid": industry_id},
        )
        db_session.commit()

        try:
            _req, response = await test_client.delete(
                f"/api/v1/industry-types/{industry_id}",
                headers=auth_headers,
            )
            assert response.status == 409
            assert "使用" in response.json["message"]

            # 引用保护后行业仍存在
            _req, list_resp = await test_client.get("/api/v1/industry-types", headers=auth_headers)
            ids = [item["id"] for item in list_resp.json["data"]]
            assert industry_id in ids
        finally:
            db_session.execute(
                text("DELETE FROM customer_profiles WHERE industry_type_id = :itid"),
                {"itid": industry_id},
            )
            db_session.execute(
                text("DELETE FROM industry_types WHERE id = :itid"),
                {"itid": industry_id},
            )
            db_session.commit()

    @pytest.mark.asyncio
    async def test_update_writes_audit_log(self, test_client, auth_headers, db_session):
        """行业改名须写审计日志（共享主数据可追溯）"""
        from sqlalchemy import text

        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "审计前名称", "sort_order": 60},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        try:
            _req, response = await test_client.put(
                f"/api/v1/industry-types/{industry_id}",
                json={"name": "审计后名称", "sort_order": 61},
                headers=auth_headers,
            )
            assert response.status == 200

            audit = db_session.execute(
                text(
                    "SELECT action, record_type, record_id FROM audit_logs "
                    "WHERE module = 'industry_type' AND record_id = :id "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"id": industry_id},
            ).first()
            assert audit is not None, "行业改名未写入审计日志"
            assert audit[0] == "update"
            assert audit[1] == "industry_type"
            assert audit[2] == industry_id
        finally:
            db_session.execute(
                text("DELETE FROM industry_types WHERE id = :itid"),
                {"itid": industry_id},
            )
            db_session.commit()


class TestCreateIndustryTypeWithId:
    """测试新增时指定 ID（Bug fix：行业类型 ID 可设定，不允许重复）"""

    @pytest.mark.asyncio
    async def test_creates_with_specified_id(self, test_client, auth_headers):
        """测试指定 id 创建成功"""
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "指定ID行业", "sort_order": 10, "id": 8000001},
            headers=auth_headers,
        )
        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["id"] == 8000001
        assert data["data"]["name"] == "指定ID行业"

    @pytest.mark.asyncio
    async def test_rejects_duplicate_id(self, test_client, auth_headers):
        """测试指定已存在的 id 返回 409"""
        # 先创建一条
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "ID占用行业", "sort_order": 11},
            headers=auth_headers,
        )
        existing_id = create_resp.json["data"]["id"]

        # 用相同 id 再创建 → 409
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "ID冲突行业", "sort_order": 12, "id": existing_id},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "ID" in response.json["message"]

    @pytest.mark.asyncio
    async def test_rejects_id_conflict_with_soft_deleted(
        self, test_client, auth_headers, db_session
    ):
        """软删记录仍占用主键 id，指定其 id 必须返回 409"""
        from sqlalchemy import text

        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "软删ID占用", "sort_order": 13},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        try:
            # 软删除该记录（id 仍占用主键空间）
            _req, _ = await test_client.delete(
                f"/api/v1/industry-types/{industry_id}",
                headers=auth_headers,
            )

            _req, response = await test_client.post(
                "/api/v1/industry-types",
                json={"name": "想用该ID", "sort_order": 14, "id": industry_id},
                headers=auth_headers,
            )
            assert response.status == 409
            assert "ID" in response.json["message"]
        finally:
            db_session.execute(
                text("DELETE FROM industry_types WHERE id = :itid"),
                {"itid": industry_id},
            )
            db_session.commit()

    @pytest.mark.asyncio
    async def test_validates_id_must_be_positive_int(self, test_client, auth_headers):
        """测试非法 id 返回 422"""
        # id=0
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "零ID", "sort_order": 15, "id": 0},
            headers=auth_headers,
        )
        assert response.status == 422

        # id 为字符串
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "字符串ID", "sort_order": 16, "id": "abc"},
            headers=auth_headers,
        )
        assert response.status == 422


class TestCreateRestoresSoftDeleted:
    """测试同名软删记录自动恢复（Bug fix：无法新增「项目」——name 唯一索引
    被软删记录占用，仅查未删除会漏掉占用，INSERT 撞唯一约束报 500）"""

    @pytest.mark.asyncio
    async def test_restores_soft_deleted_same_name(self, test_client, auth_headers, db_session):
        """同名行业被软删后再次新增：应恢复原记录而非新建"""
        from sqlalchemy import text

        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "待恢复行业", "sort_order": 20},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        try:
            # 软删除
            _req, _ = await test_client.delete(
                f"/api/v1/industry-types/{industry_id}",
                headers=auth_headers,
            )

            # 再次新增同名 → 应恢复原记录（id 不变）
            _req, response = await test_client.post(
                "/api/v1/industry-types",
                json={"name": "待恢复行业", "sort_order": 21},
                headers=auth_headers,
            )
            assert response.status == 201
            data = response.json
            assert data["code"] == 0
            assert data["data"]["id"] == industry_id
            assert data["data"]["sort_order"] == 21

            # 列表中出现且 id 一致
            _req, list_resp = await test_client.get(
                "/api/v1/industry-types",
                headers=auth_headers,
            )
            ids = [item["id"] for item in list_resp.json["data"]]
            assert industry_id in ids
        finally:
            db_session.execute(
                text("DELETE FROM industry_types WHERE id = :itid"),
                {"itid": industry_id},
            )
            db_session.commit()

    @pytest.mark.asyncio
    async def test_restore_keeps_customer_reference(self, test_client, auth_headers, db_session):
        """恢复时保留原 id：被软删行业引用的客户画像不悬空"""
        from sqlalchemy import text

        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "恢复引用行业", "sort_order": 22},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        try:
            # 先软删除（无引用，可删）
            _req, _ = await test_client.delete(
                f"/api/v1/industry-types/{industry_id}",
                headers=auth_headers,
            )

            # 软删后仍有客户画像引用该 id（历史遗留：如「项目」软删但 849 客户仍引用）
            db_session.execute(
                text(
                    """
                    INSERT INTO customer_profiles (industry_type_id, created_at, updated_at)
                    VALUES (:itid, NOW(), NOW())
                    """
                ),
                {"itid": industry_id},
            )
            db_session.commit()

            # 新增同名 → 恢复，原 id 不变
            _req, response = await test_client.post(
                "/api/v1/industry-types",
                json={"name": "恢复引用行业", "sort_order": 23},
                headers=auth_headers,
            )
            assert response.status == 201
            assert response.json["data"]["id"] == industry_id

            # 客户引用仍指向原 id（未悬空）
            ref = db_session.execute(
                text("SELECT count(*) FROM customer_profiles WHERE industry_type_id = :itid"),
                {"itid": industry_id},
            ).scalar()
            assert ref == 1
        finally:
            db_session.execute(
                text("DELETE FROM customer_profiles WHERE industry_type_id = :itid"),
                {"itid": industry_id},
            )
            db_session.execute(
                text("DELETE FROM industry_types WHERE id = :itid"),
                {"itid": industry_id},
            )
            db_session.commit()


class TestUpdateIndustryTypeId:
    """测试编辑时修改 ID（允许修改主键，不允许重复）"""

    @pytest.mark.asyncio
    async def test_updates_id_success(self, test_client, auth_headers, db_session):
        """测试未被引用的行业修改 id 成功"""
        from sqlalchemy import text

        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "改ID行业", "sort_order": 30},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        try:
            _req, response = await test_client.put(
                f"/api/v1/industry-types/{industry_id}",
                json={"name": "改ID行业", "sort_order": 30, "id": 9000001},
                headers=auth_headers,
            )
            assert response.status == 200
            data = response.json
            assert data["code"] == 0
            assert data["data"]["id"] == 9000001
            assert data["data"]["name"] == "改ID行业"
        finally:
            db_session.execute(
                text("DELETE FROM industry_types WHERE id = :itid"),
                {"itid": 9000001},
            )
            db_session.commit()

    @pytest.mark.asyncio
    async def test_rejects_duplicate_new_id(self, test_client, auth_headers, db_session):
        """测试修改 id 撞已占用 id 返回 409"""
        from sqlalchemy import text

        _req, resp_a = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "目标ID行业", "sort_order": 31},
            headers=auth_headers,
        )
        id_a = resp_a.json["data"]["id"]

        _req, resp_b = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "改ID撞车", "sort_order": 32},
            headers=auth_headers,
        )
        id_b = resp_b.json["data"]["id"]

        try:
            _req, response = await test_client.put(
                f"/api/v1/industry-types/{id_b}",
                json={"name": "改ID撞车", "sort_order": 32, "id": id_a},
                headers=auth_headers,
            )
            assert response.status == 409
            assert "ID" in response.json["message"]
        finally:
            db_session.execute(
                text("DELETE FROM industry_types WHERE id IN (:a, :b)"),
                {"a": id_a, "b": id_b},
            )
            db_session.commit()

    @pytest.mark.asyncio
    async def test_rejects_id_change_when_in_use(self, test_client, auth_headers, db_session):
        """被客户画像引用的行业禁止修改 id（引用保护，与删除同理）"""
        from sqlalchemy import text

        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "引用改ID行业", "sort_order": 33},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        try:
            # 造一个引用该行业的客户画像
            db_session.execute(
                text(
                    """
                    INSERT INTO customer_profiles (industry_type_id, created_at, updated_at)
                    VALUES (:itid, NOW(), NOW())
                    """
                ),
                {"itid": industry_id},
            )
            db_session.commit()

            _req, response = await test_client.put(
                f"/api/v1/industry-types/{industry_id}",
                json={"name": "引用改ID行业", "sort_order": 33, "id": 9000002},
                headers=auth_headers,
            )
            assert response.status == 409
            assert "使用" in response.json["message"]

            # id 未被修改
            _req, list_resp = await test_client.get(
                "/api/v1/industry-types",
                headers=auth_headers,
            )
            ids = [item["id"] for item in list_resp.json["data"]]
            assert industry_id in ids
            assert 9000002 not in ids
        finally:
            db_session.execute(
                text("DELETE FROM customer_profiles WHERE industry_type_id = :itid"),
                {"itid": industry_id},
            )
            db_session.execute(
                text("DELETE FROM industry_types WHERE id = :itid"),
                {"itid": industry_id},
            )
            db_session.commit()
