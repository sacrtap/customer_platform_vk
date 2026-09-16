"""同步任务端到端测试

使用 Sanic 内置 asgi_client（非 httpx AsyncClient）——后者与
Sanic 22.12 的 Signal 系统不兼容，会触发
``TypeError: 'NoneType' object is not callable``。
"""

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestSyncTaskE2E:
    """端到端测试"""

    async def test_full_sync_flow(self, test_client, auth_headers, db_session):
        """测试完整同步流程

        外部 ERP 数据源（EXTERNAL_MYSQL_URL）在测试环境不可用，
        因此 mock OrderSyncService 使其返回成功结果，
        验证的是「创建 → 后台执行 → 轮询 → 完态 → 审计日志」全链路。
        """
        # 1. 创建任务
        start_date = (date.today() - timedelta(days=3)).isoformat()
        end_date = date.today().isoformat()

        with patch("app.services.sync_task_service.OrderSyncService") as MockOrderSync:
            mock_order_service = AsyncMock()
            mock_order_service.sync_orders = AsyncMock(
                return_value=MagicMock(success=10, failed=0, skipped=0, unmatched=0)
            )
            MockOrderSync.return_value = mock_order_service

            _request, response = await test_client.post(
                "/api/v1/sync-tasks",
                json={
                    "start_date": start_date,
                    "end_date": end_date,
                    "sync_mode": "skip_existing",
                },
                headers=auth_headers,
            )
            assert response.status == 201, f"创建任务失败: {response.text}"
            data = response.json["data"]
            task_id = data["task_id"]
            assert data["status"] == "pending"
            assert data["total_days"] == 4

            # 2. 轮询进度
            progress = None
            for _ in range(10):  # 最多等待 20 秒
                await asyncio.sleep(2)
                _request, response = await test_client.get(
                    f"/api/v1/sync-tasks/{task_id}/progress",
                    headers=auth_headers,
                )
                assert response.status == 200
                progress = response.json["data"]

                if progress["status"] in ["completed", "failed", "partial"]:
                    break

            # 3. 验证最终状态
            assert progress is not None, "未获取到进度信息"
            assert progress["status"] == "completed", (
                f"任务未成功完成: status={progress['status']}, "
                f"error={progress.get('error_message', '')}"
            )
            assert progress["completed_days"] == 4
            assert progress["percentage"] == 1.0  # 0-1 小数格式（Arco Design 期望）

            # 4. 查询任务详情
            _request, response = await test_client.get(
                f"/api/v1/sync-tasks/{task_id}",
                headers=auth_headers,
            )
            assert response.status == 200
            task = response.json["data"]
            assert task["status"] == "completed"
            assert task["completed_at"] is not None

            # 5. 查询审计日志
            _request, response = await test_client.get(
                "/api/v1/sync-logs",
                params={"task_name": "consumption_sync"},
                headers=auth_headers,
            )
            assert response.status == 200
            logs = response.json["data"]["list"]
            assert len(logs) > 0
            assert any(log["task_id"] == task_id for log in logs)

    async def test_concurrent_sync_conflict(self, test_client, auth_headers, db_session):
        """测试并发同步冲突

        第一个任务创建成功后，mock SyncTaskService.create_task 使其
        在第二次调用时抛出「已有相同周期的同步任务正在执行」异常，
        验证路由层正确返回 409。
        """
        from app.services.sync_task_service import SyncTaskService

        start_date = (date.today() - timedelta(days=2)).isoformat()
        end_date = date.today().isoformat()

        # 第一个 POST 成功后会触发 request.app.add_task(run_task())，后台任务会在同一
        # 事件循环里真实执行 execute_task → OrderSyncService.sync_orders：若测试环境配置了
        # EXTERNAL_MYSQL_URL 会发起真实外网连接，即便未配置也会写库并与 db_session 夹具
        # teardown 对 sync_tasks/sync_task_logs 的清理竞态。本用例只验证 409，故对第一个
        # 请求同样 mock OrderSyncService（与 test_full_sync_flow 一致），消除真实外连与副作用。
        with patch("app.services.sync_task_service.OrderSyncService") as MockOrderSync:
            mock_order_service = AsyncMock()
            mock_order_service.sync_orders = AsyncMock(
                return_value=MagicMock(success=0, failed=0, skipped=0, unmatched=0)
            )
            MockOrderSync.return_value = mock_order_service

            # 创建第一个任务
            _request, response1 = await test_client.post(
                "/api/v1/sync-tasks",
                json={
                    "start_date": start_date,
                    "end_date": end_date,
                    "sync_mode": "skip_existing",
                },
                headers=auth_headers,
            )
            assert response1.status == 201

            # 第二次调用 create_task 抛冲突异常，模拟锁竞争
            with patch.object(
                SyncTaskService,
                "create_task",
                new=AsyncMock(side_effect=Exception("已有相同周期的同步任务正在执行")),
            ):
                _request, response2 = await test_client.post(
                    "/api/v1/sync-tasks",
                    json={
                        "start_date": start_date,
                        "end_date": end_date,
                        "sync_mode": "skip_existing",
                    },
                    headers=auth_headers,
                )
                assert response2.status == 409
                assert "已有相同周期的同步任务正在执行" in response2.json["message"]

    async def test_date_range_validation(self, test_client, auth_headers):
        """测试日期范围校验"""
        # 日期跨度超过 31 天
        start_date = (date.today() - timedelta(days=60)).isoformat()
        end_date = date.today().isoformat()

        _request, response = await test_client.post(
            "/api/v1/sync-tasks",
            json={
                "start_date": start_date,
                "end_date": end_date,
                "sync_mode": "skip_existing",
            },
            headers=auth_headers,
        )
        assert response.status == 400
        assert "日期跨度不能超过31天" in response.json["message"]

        # 结束日期早于开始日期
        start_date = date.today().isoformat()
        end_date = (date.today() - timedelta(days=7)).isoformat()

        _request, response = await test_client.post(
            "/api/v1/sync-tasks",
            json={
                "start_date": start_date,
                "end_date": end_date,
                "sync_mode": "skip_existing",
            },
            headers=auth_headers,
        )
        assert response.status == 400
        assert "结束日期不能早于开始日期" in response.json["message"]
