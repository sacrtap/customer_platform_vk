# -*- coding: utf-8 -*-
"""GitHub 部署更新客户端 - 读取 Deploy workflow 最近部署摘要

数据源：仓库的 Deploy workflow 成功运行 + 相邻两次成功部署间的 compare 提交。
本仓库无 GitHub Releases，部署即 workflow 运行，故以成功运行作为「部署更新」。
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class GitHubUpdatesClient:
    """GitHub 部署更新客户端（只读，无需 db_session）"""

    def __init__(self):
        self.repo = settings.github_repo
        self.token = settings.github_token or None
        self.workflow_file = settings.github_workflow_file
        self.timeout = 15.0  # 秒
        self.base = "https://api.github.com"

    def _headers(self) -> Dict[str, str]:
        """构建请求头（匿名请求可带 Accept/版本头；有 Token 时加鉴权）"""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _get(self, path: str) -> Optional[dict]:
        """GET GitHub API；404（如 workflow 文件不存在）与网络/限流错误均返回 None"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base}{path}", headers=self._headers())
                if response.status_code == 404:
                    logger.warning("GitHub 资源不存在: %s", path)
                    return None
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("GitHub API 请求失败 %s: %s", path, e)
            return None

    @staticmethod
    def _commit_brief(commit: Dict[str, Any]) -> Dict[str, str]:
        """从 compare 提交条目提取摘要字段"""
        commit_detail = commit.get("commit", {}) or {}
        author = commit_detail.get("author", {}) or {}
        return {
            "sha": commit["sha"][:7],
            "message": (commit_detail.get("message", "") or "").split("\n")[0],
            "author": author.get("name", ""),
            "date": author.get("date", ""),
        }

    async def get_recent_updates(self, count: int = 3) -> List[Dict[str, Any]]:
        """获取最近 count 次成功部署的更新摘要

        每次部署的 commits 取「相对上一次成功部署」的新增提交（compare API）；
        最旧一条无前序基线时回退为该次部署 head_commit 的单条摘要。

        Args:
            count: 返回的部署更新条数上限

        Returns:
            部署更新列表（按部署时间倒序）；GitHub 不可达/无成功部署时返回 []
        """
        # 需要 count 次成功部署 + 1 条前序基线做 compare；多取几条以过滤非成功运行
        runs_json = await self._get(
            f"/repos/{self.repo}/actions/workflows/{self.workflow_file}/runs?per_page={count + 5}"
        )
        if not runs_json or not runs_json.get("workflow_runs"):
            return []

        successful_runs = [
            run
            for run in runs_json["workflow_runs"]
            if run.get("status") == "completed" and run.get("conclusion") == "success"
        ]
        if not successful_runs:
            return []

        updates: List[Dict[str, Any]] = []
        for i, run in enumerate(successful_runs[:count]):
            commits: List[Dict[str, str]] = []
            if i + 1 < len(successful_runs):
                # 本次部署相对上次部署的新增提交（重新部署同 SHA 时 compare 返回
                # status=identical、commits 为空，属正常场景）
                compare_json = await self._get(
                    f"/repos/{self.repo}/compare/"
                    f"{successful_runs[i + 1]['head_sha']}...{run['head_sha']}"
                )
                if compare_json and compare_json.get("commits"):
                    commits = [self._commit_brief(c) for c in compare_json["commits"]]
            else:
                # 最旧的可见部署无前序基线：回退用 head_commit 作单条摘要
                head_commit = run.get("head_commit") or {}
                message = (head_commit.get("message", "") or "").split("\n")[0]
                if message:
                    commits = [
                        {
                            "sha": run["head_sha"][:7],
                            "message": message,
                            "author": (head_commit.get("author", {}) or {}).get("name", ""),
                            "date": run.get("created_at", ""),
                        }
                    ]
            updates.append(
                {
                    "deployed_at": run["created_at"],  # ISO UTC，前端按词法比较已读
                    "head_sha": run["head_sha"][:7],
                    "status": "success",
                    "commits": commits,
                }
            )
        return updates


# 全局客户端实例
github_updates_client = GitHubUpdatesClient()


def get_github_updates_client() -> GitHubUpdatesClient:
    """获取 GitHub 部署更新客户端实例"""
    return github_updates_client
