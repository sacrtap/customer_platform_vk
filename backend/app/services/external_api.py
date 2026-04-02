"""
外部 API 客户端 - 用于同步业务系统数据
"""

import httpx
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date

from ..config import settings

logger = logging.getLogger(__name__)


class ExternalAPIClient:
    """外部业务系统 API 客户端"""

    def __init__(self):
        self.base_url = settings.external_api_base_url
        self.token = settings.external_api_token
        self.timeout = 30.0  # 秒

    async def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_daily_usage(
        self, customer_id: int, start_date: date, end_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        获取客户每日用量数据

        Args:
            customer_id: 客户 ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            用量数据字典，包含 total_usage, device_breakdown 等
        """
        url = f"{self.base_url}/usage/daily"
        params = {
            "customer_id": customer_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, params=params, headers=await self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data")
        except httpx.HTTPError as e:
            logger.error(f"获取用量数据失败 customer_id={customer_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取用量数据异常 customer_id={customer_id}: {str(e)}")
            return None

    async def get_customer_info(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        获取客户详细信息

        Args:
            customer_id: 客户 ID

        Returns:
            客户信息字典
        """
        url = f"{self.base_url}/customers/{customer_id}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=await self._get_headers())
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
                return data.get("data")
        except httpx.HTTPError as e:
            logger.error(f"获取客户信息失败 customer_id={customer_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取客户信息异常 customer_id={customer_id}: {str(e)}")
            return None

    async def sync_customer_data(self, customer_id: int) -> bool:
        """
        同步客户数据到业务系统

        Args:
            customer_id: 客户 ID

        Returns:
            bool: 同步是否成功
        """
        url = f"{self.base_url}/customers/{customer_id}/sync"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=await self._get_headers())
                response.raise_for_status()
                return True
        except httpx.HTTPError as e:
            logger.error(f"同步客户数据失败 customer_id={customer_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"同步客户数据异常 customer_id={customer_id}: {str(e)}")
            return False

    async def get_usage_statistics(
        self, start_date: date, end_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        获取用量统计数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计数据字典
        """
        url = f"{self.base_url}/usage/statistics"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, params=params, headers=await self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data")
        except httpx.HTTPError as e:
            logger.error(f"获取用量统计失败：{str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取用量统计异常：{str(e)}")
            return None


# 全局 API 客户端实例
external_api_client = ExternalAPIClient()


def get_external_api_client() -> ExternalAPIClient:
    """获取外部 API 客户端实例"""
    return external_api_client
