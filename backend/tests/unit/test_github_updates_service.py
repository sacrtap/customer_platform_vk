"""GitHub 部署更新客户端单元测试（mocked httpx）"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.github_updates import GitHubUpdatesClient

# ==================== Fixtures ====================


def make_run(head_sha: str, created_at: str, conclusion: str = "success") -> dict:
    """构造一条 workflow run（GitHub API 结构）"""
    return {
        "head_sha": head_sha,
        "created_at": created_at,
        "status": "completed",
        "conclusion": conclusion,
        "head_commit": {
            "message": f"deploy {head_sha[:7]}\n\nbody line",
            "author": {"name": "deployer"},
        },
    }


def make_compare(sha: str, message: str, author: str, date: str) -> dict:
    """构造一条 compare 提交条目"""
    return {
        "sha": sha,
        "commit": {
            "message": f"{message}\n\nbody line",
            "author": {"name": author, "date": date},
        },
    }


def make_response(payload) -> MagicMock:
    """构造 httpx 响应 mock（200）"""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


def make_http_client(response_for_path: dict) -> AsyncMock:
    """构造 httpx.AsyncClient mock：按 URL 路径分发表态响应"""

    async def _get(url, *args, **kwargs):
        for path, response in response_for_path.items():
            if path in url:
                return response
        raise AssertionError(f"未预期的 GitHub 请求: {url}")

    client = AsyncMock()
    client.get = AsyncMock(side_effect=_get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.fixture
def client():
    """创建 GitHubUpdatesClient 实例（配置取默认值）"""
    return GitHubUpdatesClient()


# ==================== get_recent_updates ====================


class TestGetRecentUpdates:
    """最近部署更新摘要测试"""

    @pytest.mark.asyncio
    async def test_normal_three_updates_with_compare_commits(self, client):
        """4 条成功部署 → 返回 3 条，commits 来自相邻 compare"""
        runs = [
            make_run("a" * 40, "2026-10-20T03:00:00Z"),
            make_run("b" * 40, "2026-10-13T03:00:00Z"),
            make_run("c" * 40, "2026-10-06T03:00:00Z"),
            make_run("d" * 40, "2026-09-29T03:00:00Z"),
        ]
        responses = {
            "/runs?per_page=8": make_response({"workflow_runs": runs}),
            f"/compare/{'d' * 40}...{'c' * 40}": make_response(
                {
                    "status": "ahead",
                    "total_commits": 2,
                    "commits": [
                        make_compare("e" * 40, "feat: 新功能", "张三", "2026-10-05T01:00:00Z"),
                        make_compare("f" * 40, "fix: 修复缺陷", "李四", "2026-10-06T01:00:00Z"),
                    ],
                }
            ),
            f"/compare/{'c' * 40}...{'b' * 40}": make_response(
                {
                    "status": "ahead",
                    "total_commits": 1,
                    "commits": [
                        make_compare("1" * 40, "chore: 依赖升级", "王五", "2026-10-12T01:00:00Z")
                    ],
                }
            ),
            f"/compare/{'b' * 40}...{'a' * 40}": make_response(
                {
                    "status": "ahead",
                    "total_commits": 1,
                    "commits": [
                        make_compare("2" * 40, "docs: 更新文档", "赵六", "2026-10-19T01:00:00Z")
                    ],
                }
            ),
        }

        with patch("httpx.AsyncClient", return_value=make_http_client(responses)):
            updates = await client.get_recent_updates(3)

        assert len(updates) == 3
        # 最新部署：字段透传 + commits 取相对上次部署
        latest = updates[0]
        assert latest["deployed_at"] == "2026-10-20T03:00:00Z"
        assert latest["head_sha"] == "aaaaaaa"
        assert latest["status"] == "success"
        assert latest["commits"] == [
            {
                "sha": "2222222",
                "message": "docs: 更新文档",
                "author": "赵六",
                "date": "2026-10-19T01:00:00Z",
            }
        ]
        # 第二条部署：commits 来自对应 compare
        assert updates[1]["head_sha"] == "bbbbbbb"
        assert updates[1]["commits"] == [
            {
                "sha": "1111111",
                "message": "chore: 依赖升级",
                "author": "王五",
                "date": "2026-10-12T01:00:00Z",
            }
        ]
        # 第三条部署
        assert updates[2]["head_sha"] == "ccccccc"
        assert [c["message"] for c in updates[2]["commits"]] == ["feat: 新功能", "fix: 修复缺陷"]

    @pytest.mark.asyncio
    async def test_identical_compare_returns_empty_commits(self, client):
        """重新部署同一 SHA（compare identical）→ 该部署 commits 为空列表，不报错"""
        runs = [
            make_run("a" * 40, "2026-10-20T03:00:00Z"),
            make_run("a" * 40, "2026-10-20T02:00:00Z"),
        ]
        responses = {
            "/runs?per_page=8": make_response({"workflow_runs": runs}),
            f"/compare/{'a' * 40}...{'a' * 40}": make_response(
                {"status": "identical", "total_commits": 0, "commits": []}
            ),
        }

        with patch("httpx.AsyncClient", return_value=make_http_client(responses)):
            updates = await client.get_recent_updates(3)

        assert len(updates) == 2
        # 最新部署相对上次同 SHA：identical，commits 为空
        assert updates[0]["commits"] == []
        assert updates[0]["deployed_at"] == "2026-10-20T03:00:00Z"
        # 最旧部署无前序基线：回退 head_commit 单条摘要
        assert updates[1]["commits"] == [
            {
                "sha": "aaaaaaa",
                "message": "deploy aaaaaaa",
                "author": "deployer",
                "date": "2026-10-20T02:00:00Z",
            }
        ]

    @pytest.mark.asyncio
    async def test_single_successful_run_falls_back_to_head_commit(self, client):
        """成功部署不足 count（仅 1 条）→ 返回 1 条，回退 head_commit 单条摘要"""
        runs = [
            make_run("a" * 40, "2026-10-20T03:00:00Z"),
            # 非成功部署被过滤
            make_run("b" * 40, "2026-10-19T03:00:00Z", conclusion="failure"),
        ]
        responses = {"/runs?per_page=8": make_response({"workflow_runs": runs})}

        with patch("httpx.AsyncClient", return_value=make_http_client(responses)):
            updates = await client.get_recent_updates(3)

        assert len(updates) == 1
        assert updates[0]["head_sha"] == "aaaaaaa"
        assert updates[0]["commits"] == [
            {
                "sha": "aaaaaaa",
                "message": "deploy aaaaaaa",
                "author": "deployer",
                "date": "2026-10-20T03:00:00Z",
            }
        ]

    @pytest.mark.asyncio
    async def test_github_unreachable_returns_empty(self, client):
        """GitHub 不可达/限流（请求全部失败）→ 返回 []"""
        client_mock = AsyncMock()
        client_mock.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        client_mock.__aenter__ = AsyncMock(return_value=client_mock)
        client_mock.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client_mock):
            updates = await client.get_recent_updates(3)

        assert updates == []

    @pytest.mark.asyncio
    async def test_no_successful_runs_returns_empty(self, client):
        """无成功部署 → 返回 []"""
        runs = [make_run("a" * 40, "2026-10-20T03:00:00Z", conclusion="cancelled")]
        responses = {"/runs?per_page=8": make_response({"workflow_runs": runs})}

        with patch("httpx.AsyncClient", return_value=make_http_client(responses)):
            updates = await client.get_recent_updates(3)

        assert updates == []
