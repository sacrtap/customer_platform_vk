"""
客户平台 API 负载测试脚本 - Locust

测试关键 API 端点的响应时间和并发能力

使用方法:
    cd backend
    locust -f tests/performance/test_api_load.py --host=http://localhost:8000

Web UI: http://localhost:8089
"""

from locust import HttpUser, task, between, events
import random
from datetime import datetime


class CustomerPlatformUser(HttpUser):
    """模拟真实用户行为的 Locust 用户类"""

    # 请求间隔 1-3 秒，模拟真实用户操作
    wait_time = between(1, 3)

    # 测试用户凭据（需要在数据库中存在）
    test_credentials = {
        "username": "admin",
        "password": "admin123",
    }

    # 存储认证 token
    access_token: str = None
    token_type: str = "Bearer"

    def on_start(self):
        """
        用户启动时执行 - 完成登录认证
        所有后续请求将使用获取到的 token
        """
        self._login()

    def _login(self):
        """执行登录并存储 token"""
        try:
            response = self.client.post(
                "/api/v1/auth/login",
                json=self.test_credentials,
                name="/api/v1/auth/login",
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0 and data.get("data"):
                    self.access_token = data["data"]["access_token"]
                    self.token_type = data["data"].get("token_type", "Bearer")
                    print(f"[{self._user_name}] 登录成功")
                else:
                    print(f"[{self._user_name}] 登录失败：{data.get('message')}")
            else:
                print(f"[{self._user_name}] 登录请求失败，状态码：{response.status_code}")
        except Exception as e:
            print(f"[{self._user_name}] 登录异常：{str(e)}")

    @property
    def _user_name(self):
        """获取当前用户标识"""
        return f"User-{id(self) % 1000}"

    @property
    def _auth_headers(self):
        """获取认证请求头"""
        if self.access_token:
            return {"Authorization": f"{self.token_type} {self.access_token}"}
        return {}

    @task(5)
    def get_customers(self):
        """
        获取客户列表 - 高频操作
        权重：5（最高频率）
        """
        # 随机参数组合，模拟真实查询场景
        params = {
            "page": random.randint(1, 5),
            "page_size": random.choice([10, 20, 50]),
        }

        # 随机添加筛选条件
        if random.random() > 0.5:
            params["keyword"] = random.choice(["科技", "贸易", "实业", "公司"])

        if random.random() > 0.7:
            params["account_type"] = random.choice(["enterprise", "individual"])

        if random.random() > 0.8:
            params["is_key_customer"] = random.choice(["true", "false"])

        self.client.get(
            "/api/v1/customers",
            headers=self._auth_headers,
            params=params,
            name="/api/v1/customers [GET]",
        )

    @task(3)
    def get_balance(self):
        """
        获取余额信息 - 中频操作
        权重：3
        """
        # 随机选择一个客户 ID 查询余额
        customer_id = random.randint(1, 100)

        self.client.get(
            f"/api/v1/billing/customers/{customer_id}/balance",
            headers=self._auth_headers,
            name="/api/v1/billing/customers/{id}/balance [GET]",
        )

    @task(2)
    def get_dashboard_stats(self):
        """
        获取仪表盘统计数据 - 低频操作
        权重：2
        """
        self.client.get(
            "/api/v1/analytics/dashboard/stats",
            headers=self._auth_headers,
            name="/api/v1/analytics/dashboard/stats [GET]",
        )

    @task(2)
    def get_billing_balances(self):
        """
        获取余额列表 - 中频操作
        权重：2
        """
        params = {
            "page": random.randint(1, 3),
            "page_size": random.choice([20, 50]),
        }

        if random.random() > 0.6:
            params["keyword"] = random.choice(["科技", "贸易"])

        self.client.get(
            "/api/v1/billing/balances",
            headers=self._auth_headers,
            params=params,
            name="/api/v1/billing/balances [GET]",
        )

    @task(1)
    def get_customer_detail(self):
        """
        获取客户详情 - 低频操作
        权重：1
        """
        customer_id = random.randint(1, 100)

        self.client.get(
            f"/api/v1/customers/{customer_id}",
            headers=self._auth_headers,
            name="/api/v1/customers/{id} [GET]",
        )

    @task(1)
    def get_consumption_records(self):
        """
        获取消费记录 - 低频操作
        权重：1
        """
        params = {
            "page": random.randint(1, 3),
            "page_size": random.choice([20, 50]),
            "customer_id": random.randint(1, 100) if random.random() > 0.5 else None,
        }

        # 移除 None 值
        params = {k: v for k, v in params.items() if v is not None}

        self.client.get(
            "/api/v1/billing/consumption-records",
            headers=self._auth_headers,
            params=params,
            name="/api/v1/billing/consumption-records [GET]",
        )

    @task(1)
    def get_pricing_rules(self):
        """
        获取定价规则 - 低频操作
        权重：1
        """
        params = {}

        if random.random() > 0.5:
            params["customer_id"] = random.randint(1, 100)

        if random.random() > 0.7:
            params["device_type"] = random.choice(["X", "Y", "Z"])

        self.client.get(
            "/api/v1/billing/pricing-rules",
            headers=self._auth_headers,
            params=params,
            name="/api/v1/billing/pricing-rules [GET]",
        )

    @task(1)
    def get_invoices(self):
        """
        获取结算单列表 - 低频操作
        权重：1
        """
        params = {
            "page": random.randint(1, 3),
            "page_size": random.choice([20, 50]),
        }

        if random.random() > 0.6:
            params["customer_id"] = random.randint(1, 100)

        if random.random() > 0.8:
            params["status"] = random.choice(
                ["draft", "submitted", "confirmed", "paid", "completed"]
            )

        self.client.get(
            "/api/v1/billing/invoices",
            headers=self._auth_headers,
            params=params,
            name="/api/v1/billing/invoices [GET]",
        )

    @task(1)
    def get_analytics_chart_data(self):
        """
        获取仪表盘图表数据 - 低频操作
        权重：1
        """
        params = {
            "months": random.choice([3, 6, 12]),
        }

        self.client.get(
            "/api/v1/analytics/dashboard/chart-data",
            headers=self._auth_headers,
            params=params,
            name="/api/v1/analytics/dashboard/chart-data [GET]",
        )

    @task(1)
    def get_current_user(self):
        """
        获取当前用户信息 - 低频操作
        权重：1
        """
        self.client.get(
            "/api/v1/auth/me",
            headers=self._auth_headers,
            name="/api/v1/auth/me [GET]",
        )


# ==================== 事件监听器 ====================


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时执行"""
    print("\n" + "=" * 60)
    print("客户平台 API 负载测试开始")
    print("=" * 60)
    print(f"目标主机：{environment.host}")
    print(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时执行 - 输出详细统计报告"""
    stats = environment.stats

    print("\n" + "=" * 60)
    print("负载测试完成 - 统计报告")
    print("=" * 60)
    print(f"结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 总体统计
    print("\n【总体统计】")
    print(f"  总请求数：{stats.total.num_requests:,}")
    print(f"  失败请求数：{stats.total.num_failures:,}")
    print(f"  成功率：{(1 - stats.total.fail_ratio) * 100:.2f}%")
    print(f"  平均响应时间：{stats.total.avg_response_time:.2f}ms")
    print(f"  最小响应时间：{stats.total.min_response_time:.2f}ms")
    print(f"  最大响应时间：{stats.total.max_response_time:.2f}ms")

    # 百分位响应时间
    print("\n【响应时间百分位】")
    print(f"  P50 (中位数): {stats.total.get_response_time_percentile(0.5):.2f}ms")
    print(f"  P66: {stats.total.get_response_time_percentile(0.66):.2f}ms")
    print(f"  P75: {stats.total.get_response_time_percentile(0.75):.2f}ms")
    print(f"  P80: {stats.total.get_response_time_percentile(0.80):.2f}ms")
    print(f"  P90: {stats.total.get_response_time_percentile(0.90):.2f}ms")
    print(f"  P95: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"  P98: {stats.total.get_response_time_percentile(0.98):.2f}ms")
    print(f"  P99: {stats.total.get_response_time_percentile(0.99):.2f}ms")

    # 按端点统计
    print("\n【按端点统计】")
    print(f"{'端点':<50} {'请求数':>10} {'失败数':>10} {'平均 (ms)':>12} {'P95 (ms)':>12}")
    print("-" * 94)

    for endpoint in sorted(stats.entries, key=lambda x: x[1]):
        if endpoint[0] == "GET" or endpoint[0] == "POST":
            method, name = endpoint
            entry = stats.get(name, method)
            if entry.num_requests > 0:
                p95 = entry.get_response_time_percentile(0.95)
                print(
                    f"{name:<50} {entry.num_requests:>10,} {entry.num_failures:>10,} "
                    f"{entry.avg_response_time:>12.2f} {p95:>12.2f}"
                )

    # 性能评估
    print("\n【性能评估】")
    p95_response_time = stats.total.get_response_time_percentile(0.95)
    fail_rate = stats.total.fail_ratio * 100

    if p95_response_time < 200 and fail_rate < 1:
        print("  ✓ 性能优秀 - P95 < 200ms 且 失败率 < 1%")
    elif p95_response_time < 500 and fail_rate < 5:
        print("  ⚠ 性能良好 - P95 < 500ms 且 失败率 < 5%")
    else:
        print("  ✗ 性能需优化 - P95 >= 500ms 或 失败率 >= 5%")

    print("=" * 60 + "\n")


@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    exception,
    response,
    context,
    **kwargs,
):
    """
    每个请求完成时执行
    可用于记录详细日志或自定义指标
    """
    if exception:
        # 记录失败请求详情
        print(f"[ERROR] {request_type} {name} - 错误：{str(exception)}")


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """
    Locust 退出时执行
    可用于生成报告文件或发送通知
    """
    stats = environment.stats

    # 检查性能指标是否达标
    p95 = stats.total.get_response_time_percentile(0.95)
    fail_rate = stats.total.fail_ratio * 100

    if p95 > 1000:
        print(f"\n⚠️  警告：P95 响应时间 ({p95:.2f}ms) 超过 1000ms 阈值")

    if fail_rate > 10:
        print(f"\n⚠️  警告：失败率 ({fail_rate:.2f}%) 超过 10% 阈值")


# ==================== 自定义测试场景 ====================


class StressTestUser(HttpUser):
    """
    压力测试用户 - 用于极限压力测试
    更短的思考时间，更高的请求频率
    """

    wait_time = between(0.1, 0.5)  # 极短间隔
    test_credentials = {"username": "admin", "password": "admin123"}

    def on_start(self):
        self._login()

    def _login(self):
        try:
            response = self.client.post("/api/v1/auth/login", json=self.test_credentials)
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("data", {}).get("access_token")
        except Exception:
            pass

    @task(10)
    def rapid_customer_list(self):
        """快速获取客户列表"""
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        self.client.get(
            "/api/v1/customers",
            headers=headers,
            params={"page": 1, "page_size": 20},
            name="/api/v1/customers [STRESS]",
        )

    @task(5)
    def rapid_dashboard(self):
        """快速获取仪表盘"""
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        self.client.get(
            "/api/v1/analytics/dashboard/stats",
            headers=headers,
            name="/api/v1/analytics/dashboard/stats [STRESS]",
        )


# ==================== 命令行运行示例 ====================

"""
# 基本负载测试（Web UI）
locust -f tests/performance/test_api_load.py --host=http://localhost:8000

# 无头模式 - 100 用户，10 用户/秒生成率，运行 5 分钟
locust -f tests/performance/test_api_load.py \
    --host=http://localhost:8000 \
    --headless \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --stop-timeout 30

# 压力测试模式（使用 StressTestUser）
locust -f tests/performance/test_api_load.py \
    --host=http://localhost:8000 \
    --headless \
    --users 200 \
    --spawn-rate 20 \
    --run-time 10m \
    --user-class StressTestUser

# 生成 HTML 报告
locust -f tests/performance/test_api_load.py \
    --host=http://localhost:8000 \
    --headless \
    --users 50 \
    --spawn-rate 5 \
    --run-time 3m \
    --html=report.html
"""
