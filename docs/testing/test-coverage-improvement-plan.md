# 测试覆盖率提升计划

**项目**: 客户运营中台 (customer_platform_vk)  
**创建日期**: 2026-04-04  
**当前覆盖率**: 57%  
**目标覆盖率**: 70%+

---

## 📊 测试验证结果

### 后端测试状态
```
✅ 295 passed, 1 skipped, 36 warnings in 54.59s
✅ 总覆盖率：57%
```

### 前端 E2E 测试状态
```
✅ 84 passed (2.1m)
✅ Chromium + Mobile Chrome 双浏览器覆盖
```

---

## 🎯 优先补充模块

### P0: 核心业务模块 (覆盖率 < 30%)

| 模块 | 当前覆盖率 | 目标 | 未覆盖行数 | 优先级 |
|------|-----------|------|-----------|--------|
| `app/routes/webhooks.py` | 46% | 70% | 194-305, 330-444 | 🔴 |
| `app/routes/billing.py` | 21% | 60% | 22-77, 107-128, 163-193, 257-283 | 🔴 |
| `app/routes/customers.py` | 25% | 60% | 108-179, 202-230, 263-285, 407-463 | 🔴 |
| `app/routes/tags.py` | 25% | 60% | 25-71, 115-138, 298-318, 341-359 | 🟡 |
| `app/routes/users.py` | 26% | 60% | 103-127, 154-169, 188-204 | 🟡 |
| `app/routes/sync_logs.py` | 25% | 50% | 42-106, 137-208 | 🟡 |

### P1: 服务层模块 (覆盖率 < 50%)

| 模块 | 当前覆盖率 | 目标 | 说明 |
|------|-----------|------|------|
| `app/services/email.py` | 0% | 60% | 邮件发送服务 (未实现测试) |
| `app/services/external_api.py` | 25% | 60% | 外部 API 调用服务 |
| `app/services/users.py` | 58% | 70% | 用户服务 (补充边界测试) |

### P2: 定时任务模块

| 模块 | 当前覆盖率 | 目标 | 说明 |
|------|-----------|------|------|
| `app/tasks/email_tasks.py` | 20% | 60% | 邮件发送任务 |
| `app/tasks/file_cleanup.py` | 28% | 60% | 文件清理任务 |
| `app/tasks/webhook_cleanup.py` | 35% | 60% | Webhook 清理任务 |

---

## 📝 测试补充计划

### 第一阶段：Webhook 路由测试 (预计 1 天)

**文件**: `tests/unit/test_webhooks_routes.py`

```python
# 测试场景
1. Webhook 签名验证 - 有效签名
2. Webhook 签名验证 - 无效签名
3. Webhook 时间戳验证 - 有效窗口内
4. Webhook 时间戳验证 - 过期时间戳
5. Webhook 重放攻击检测 - 签名已使用
6. Webhook 重放攻击检测 - 新签名
7. Webhook 回调处理 - 客户确认结算单
8. Webhook 回调处理 - 结算单不存在
9. Webhook 回调处理 - 状态非法流转
10. Webhook 回调处理 - 审计日志记录
```

### 第二阶段：Billing 路由测试 (预计 1.5 天)

**文件**: `tests/unit/test_billing_routes.py`

```python
# 余额管理测试
1. GET /balances - 获取余额列表
2. GET /balances?customer_id=X - 按客户筛选
3. GET /balances?keyword=XXX - 关键词搜索
4. GET /balances/{id} - 获取余额详情
5. POST /balances/{id}/recharge - 余额充值
6. POST /balances/{id}/recharge - 充值金额验证
7. POST /balances/{id}/adjust - 余额调整
8. GET /balances/{id}/transactions - 流水记录

# 计费规则测试
9. GET /pricing-rules - 获取计费规则列表
10. POST /pricing-rules - 创建计费规则
11. PUT /pricing-rules/{id} - 更新计费规则
12. DELETE /pricing-rules/{id} - 删除计费规则

# 结算单测试
13. POST /invoices - 生成结算单
14. GET /invoices - 结算单列表
15. PUT /invoices/{id}/status - 状态流转
```

### 第三阶段：Customers 路由测试 (预计 1 天)

**文件**: `tests/unit/test_customers_routes.py`

```python
# 客户 CRUD 测试
1. GET /customers - 客户列表 (分页)
2. GET /customers?keyword=XXX - 关键词搜索
3. GET /customers/{id} - 客户详情
4. POST /customers - 创建客户
5. PUT /customers/{id} - 更新客户
6. DELETE /customers/{id} - 删除客户

# Excel 导入导出测试
7. POST /customers/import - Excel 导入
8. GET /customers/export - Excel 导出
9. GET /customers/import-template - 下载模板

# 客户分组测试
10. PUT /customers/{id}/group - 分配客户组
```

### 第四阶段：服务层测试 (预计 1 天)

**文件**: `tests/unit/test_email_service.py`
**文件**: `tests/unit/test_external_api_service.py`

### 第五阶段：定时任务测试 (预计 1 天)

**文件**: `tests/unit/test_email_tasks.py`
**文件**: `tests/unit/test_file_cleanup_tasks.py`

---

## 🧪 测试编写规范

### 测试结构

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

class TestWebhookRoutes:
    """Webhook 路由测试"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock 数据库会话"""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session
    
    @pytest.fixture
    def valid_webhook_payload(self):
        """有效的 Webhook 载荷"""
        return {
            "invoice_id": 1,
            "action": "confirm",
            "timestamp": datetime.utcnow().isoformat(),
            "signature": "valid_signature_here"
        }
    
    async def test_webhook_valid_signature(
        self, mock_session, valid_webhook_payload
    ):
        """测试有效签名"""
        # Arrange
        with patch('app.routes.webhooks.verify_timestamp_window') as mock_ts:
            mock_ts.return_value = True
            
            # Act
            response = await webhooks_bp.asgi_client.post(
                "/api/v1/webhooks/invoice-callback",
                json=valid_webhook_payload
            )
            
            # Assert
            assert response.status == 200
            assert response.json()["code"] == 0
```

### Mock 使用指南

```python
# 数据库 Mock
mock_session.execute = AsyncMock(return_value=mock_result)

# 服务层 Mock
with patch('app.services.billing.BalanceService') as mock_service:
    mock_service.return_value.get_balance = AsyncMock(return_value=balance)
    
# 缓存 Mock
with patch('app.cache.base.cache_service.get') as mock_get:
    mock_get.return_value = cached_data
```

---

## 📈 覆盖率目标追踪

| 阶段 | 模块 | 当前 | 目标 | 状态 |
|------|------|------|------|------|
| Phase 1 | webhooks.py | 46% | 70% | ⏳ |
| Phase 2 | billing.py | 21% | 60% | ⏳ |
| Phase 3 | customers.py | 25% | 60% | ⏳ |
| Phase 4 | email.py, external_api.py | 0%/25% | 60% | ⏳ |
| Phase 5 | tasks/* | 20-35% | 60% | ⏳ |
| **总计** | **All** | **57%** | **70%+** | ⏳ |

---

## 🚀 执行命令

### 运行单个测试文件
```bash
cd backend
source .venv/bin/activate

# Webhook 测试
python -m pytest tests/unit/test_webhooks_routes.py -v

# Billing 测试
python -m pytest tests/unit/test_billing_routes.py -v

# Customers 测试
python -m pytest tests/unit/test_customers_routes.py -v
```

### 生成覆盖率报告
```bash
# 生成 HTML 报告
python -m pytest --cov=app --cov-report=html

# 查看覆盖率
open htmlcov/index.html

# 终端显示未覆盖行
python -m pytest --cov=app --cov-report=term-missing
```

---

## ⚠️ 注意事项

1. **事务回滚**: 集成测试使用事务回滚，确保测试隔离
2. **Mock 外部依赖**: 邮件、外部 API 等必须 Mock
3. **异步测试**: 所有异步函数使用 `async def` + `await`
4. **测试数据**: 使用 pytest fixture 管理测试数据
5. **并发安全**: 余额相关测试需验证行级锁

---

## 📅 时间估算

| 阶段 | 工作量 | 累计 |
|------|--------|------|
| Phase 1: Webhook | 1 天 | 1 天 |
| Phase 2: Billing | 1.5 天 | 2.5 天 |
| Phase 3: Customers | 1 天 | 3.5 天 |
| Phase 4: Services | 1 天 | 4.5 天 |
| Phase 5: Tasks | 1 天 | 5.5 天 |
| **总计** | **5.5 天** | **5.5 天** |

---

**最后更新**: 2026-04-04  
**负责人**: 开发团队  
**审核状态**: 待审核
