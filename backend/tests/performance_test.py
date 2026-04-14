"""
性能测试脚本 - Locust
测试 API 响应时间和并发能力
"""

from locust import HttpUser, task, between, events
import random


class CustomerPlatformUser(HttpUser):
    """模拟用户行为"""

    wait_time = between(1, 3)  # 请求间隔 1-3 秒

    # 测试数据
    test_user = {
        "username": f"test_user_{random.randint(1000, 9999)}",
        "password": "test123456",
        "email": "test@example.com",
    }

    def on_start(self):
        """用户开始时的初始化"""
        # 登录获取 Token
        response = self.client.post("/api/v1/auth/login", json=self.test_user)
        if response.status_code == 200:
            data = response.json()
            self.token = data["data"]["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}

    @task(3)
    def get_customers(self):
        """获取客户列表"""
        self.client.get("/api/v1/customers", headers=self.headers, name="/api/v1/customers")

    @task(2)
    def get_dashboard_stats(self):
        """获取仪表盘统计"""
        self.client.get(
            "/api/v1/analytics/dashboard/stats",
            headers=self.headers,
            name="/api/v1/analytics/dashboard/stats",
        )

    @task(1)
    def get_balances(self):
        """获取余额列表"""
        self.client.get(
            "/api/v1/billing/balances",
            headers=self.headers,
            name="/api/v1/billing/balances",
        )

    @task(1)
    def get_tags(self):
        """获取标签列表"""
        self.client.get("/api/v1/tags", headers=self.headers, name="/api/v1/tags")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """记录请求日志"""
    if exception:
        print(f"请求失败：{name}, 错误：{exception}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时"""
    print("=" * 50)
    print("性能测试开始")
    print("=" * 50)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时"""
    print("=" * 50)
    print("性能测试结束")
    print("=" * 50)

    # 输出统计信息
    stats = environment.stats
    print(f"\n总请求数：{stats.total.num_requests}")
    print(f"失败请求数：{stats.total.num_failures}")
    print(f"成功率：{(1 - stats.total.fail_ratio) * 100:.2f}%")
    print(f"平均响应时间：{stats.total.avg_response_time:.2f}ms")
    print(f"P95 响应时间：{stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"P99 响应时间：{stats.total.get_response_time_percentile(0.99):.2f}ms")
