"""同步任务端到端测试"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """创建测试客户端"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


class TestSyncTaskE2E:
    """端到端测试"""

    async def test_full_sync_flow(self, client):
        """测试完整同步流程"""
        # 1. 创建任务
        start_date = (date.today() - timedelta(days=3)).isoformat()
        end_date = date.today().isoformat()

        response = await client.post(
            "/api/v1/sync-tasks",
            json={
                "start_date": start_date,
                "end_date": end_date,
                "sync_mode": "skip_existing",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        task_id = data["task_id"]
        assert data["status"] == "pending"
        assert data["total_days"] == 4

        # 2. 轮询进度
        import asyncio

        for _ in range(10):  # 最多等待 20 秒
            await asyncio.sleep(2)
            response = await client.get(f"/api/v1/sync-tasks/{task_id}/progress")
            assert response.status_code == 200
            progress = response.json()["data"]

            if progress["status"] in ["completed", "failed"]:
                break

        # 3. 验证最终状态
        assert progress["status"] == "completed"
        assert progress["completed_days"] == 4
        assert progress["percentage"] == 100

        # 4. 查询任务详情
        response = await client.get(f"/api/v1/sync-tasks/{task_id}")
        assert response.status_code == 200
        task = response.json()["data"]
        assert task["status"] == "completed"
        assert task["completed_at"] is not None

        # 5. 查询审计日志
        response = await client.get(
            "/api/v1/sync-logs",
            params={"task_name": "consumption_sync"},
        )
        assert response.status_code == 200
        logs = response.json()["data"]["list"]
        assert len(logs) > 0
        assert any(log["task_id"] == task_id for log in logs)

    async def test_concurrent_sync_conflict(self, client):
        """测试并发同步冲突"""
        start_date = (date.today() - timedelta(days=2)).isoformat()
        end_date = date.today().isoformat()

        # 创建第一个任务
        response1 = await client.post(
            "/api/v1/sync-tasks",
            json={
                "start_date": start_date,
                "end_date": end_date,
                "sync_mode": "skip_existing",
            },
        )
        assert response1.status_code == 201

        # 尝试创建第二个相同周期的任务
        response2 = await client.post(
            "/api/v1/sync-tasks",
            json={
                "start_date": start_date,
                "end_date": end_date,
                "sync_mode": "skip_existing",
            },
        )
        assert response2.status_code == 409
        assert "已有相同周期的同步任务正在执行" in response2.json()["message"]

    async def test_date_range_validation(self, client):
        """测试日期范围校验"""
        # 日期跨度超过 31 天
        start_date = (date.today() - timedelta(days=60)).isoformat()
        end_date = date.today().isoformat()

        response = await client.post(
            "/api/v1/sync-tasks",
            json={
                "start_date": start_date,
                "end_date": end_date,
                "sync_mode": "skip_existing",
            },
        )
        assert response.status_code == 400
        assert "日期跨度不能超过31天" in response.json()["message"]

        # 结束日期早于开始日期
        start_date = date.today().isoformat()
        end_date = (date.today() - timedelta(days=7)).isoformat()

        response = await client.post(
            "/api/v1/sync-tasks",
            json={
                "start_date": start_date,
                "end_date": end_date,
                "sync_mode": "skip_existing",
            },
        )
        assert response.status_code == 400
        assert "结束日期不能早于开始日期" in response.json()["message"]
