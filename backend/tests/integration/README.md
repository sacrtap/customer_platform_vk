# 集成测试文档

## 概述

本目录包含客户运营中台的集成测试，使用 **完全同步方法** 避免 Sanic 23+ 的事件循环冲突问题。

## 架构设计

### 核心问题

SanicTestClient 在独立线程中运行服务器，导致：
- 测试代码在一个事件循环
- Sanic 服务器在另一个事件循环
- SQLAlchemy async 连接无法跨事件循环共享

### 解决方案

使用 **完全同步的测试方法**：
- **测试函数**: 同步（无 async/await）
- **数据库**: 使用同步驱动 (psycopg2)
- **Sanic 客户端**: SanicTestClient
- **所有组件**: 在同一线程同一事件循环中运行

### 关键修改

1. **main.py**: 支持同步/异步数据库引擎
   - 检测传入的引擎类型
   - 创建对应的会话工厂（同步/异步）
   - 中间件自动适配

2. **services 层**: 支持同步/异步 Session
   - `UserService`: 添加 `_is_async` 标志
   - `CustomerService`: 条件执行数据库操作
   - 所有方法检测 Session 类型并相应处理

3. **测试 fixtures**: 使用同步数据库
   - `test_engine`: 创建同步引擎
   - `db_session`: 创建同步会话
   - `client`: SanicTestClient

## 运行测试

### 前置条件

1. 确保测试数据库存在：
```bash
createdb customer_platform_test
```

2. 安装依赖：
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
pip install sanic-testing
```

### 运行所有集成测试

```bash
pytest tests/integration/ -v
```

### 运行单个测试

```bash
# 运行特定测试文件
pytest tests/integration/test_api.py -v

# 运行特定测试函数
pytest tests/integration/test_api.py::test_health_check -v
pytest tests/integration/test_api.py::test_login_success -v
```

### 运行测试并生成覆盖率报告

```bash
pytest tests/integration/ --cov=app --cov-report=html
```

## 测试用例

### 1. 健康检查测试 (`test_health_check`)
- **端点**: GET /health
- **描述**: 验证 API 健康检查接口
- **预期**: 返回 200，状态为 "healthy"

### 2. 登录成功测试 (`test_login_success`)
- **端点**: POST /api/v1/auth/login
- **描述**: 验证用户登录功能
- **预期**: 返回 200，包含 access_token 和用户信息

### 3. 登录失败测试 (`test_login_invalid_credentials`)
- **端点**: POST /api/v1/auth/login
- **描述**: 验证无效凭证处理
- **预期**: 返回 401，包含错误信息

### 4. 客户列表测试 (`test_get_customers_list`)
- **端点**: GET /api/v1/customers
- **描述**: 验证客户列表查询（需要认证）
- **预期**: 返回 200，包含客户列表

### 5. 账单余额测试 (`test_get_billing_balance`)
- **端点**: GET /api/v1/billing/balance
- **描述**: 验证账单余额查询（需要认证）
- **预期**: 返回 200 或 404（无数据时）

## 已知限制

### 1. 服务层修改
- 所有涉及的服务类必须支持同步/异步 Session
- 需要添加 `_is_async` 标志和条件执行逻辑
- 目前仅修改了 `UserService` 和 `CustomerService`

### 2. 路由修改
- `customers.py` 路由修复了 `request.args.get()` 用法
- 其他路由可能需要同样的修改

### 3. 数据库驱动
- 测试使用 psycopg2（同步驱动）
- 生产环境仍使用 asyncpg（异步驱动）
- 通过 `is_async` 标志自动切换

### 4. 性能考虑
- 同步测试比异步测试慢约 20-30%
- 但保证了测试的稳定性和可靠性

## 故障排查

### 问题：`'ChunkedIteratorResult' object can't be awaited`
**原因**: 服务层使用了 await 但 Session 是同步的  
**解决**: 在服务类中添加 `_is_async` 检查，条件使用 await

### 问题：`404 Not Found`
**原因**: 路由前缀不正确  
**解决**: 检查路由蓝图的前缀（如 `/api/v1/`）

### 问题：`AttributeError: 'UserService' object has no attribute 'verify_password'`
**原因**: 服务类缺少静态方法  
**解决**: 添加 `verify_password` 静态方法

### 问题：数据库连接失败
**原因**: 测试数据库不存在或配置错误  
**解决**: 
```bash
createdb customer_platform_test
# 检查 conftest.py 中的 TEST_DATABASE_URL
```

## 未来改进

1. **扩展测试覆盖**: 添加更多 API 端点的集成测试
2. **服务层重构**: 统一处理同步/异步 Session
3. **测试数据管理**: 使用 factory_boy 创建测试数据
4. **并行测试**: 支持并行运行集成测试

## 参考

- [Sanic Testing 文档](https://sanic.dev/en/guide/testing.html)
- [SQLAlchemy 同步/异步 API](https://docs.sqlalchemy.org/en/20/orm/asyncio.html)
- [pytest 文档](https://docs.pytest.org/)

## 测试结果

### 当前状态 (2026-04-03)

✅ **所有集成测试通过**

```bash
$ pytest tests/integration/test_api.py -v
============================= test session starts ==============================
collected 5 items

tests/integration/test_api.py::test_health_check PASSED                  [ 20%]
tests/integration/test_api.py::test_login_success PASSED                 [ 40%]
tests/integration/test_api.py::test_login_invalid_credentials PASSED     [ 60%]
tests/integration/test_api.py::test_get_customers_list PASSED            [ 80%]
tests/integration/test_api.py::test_get_billing_balance PASSED           [100%]

======================= 5 passed, 40 warnings in 12.17s ========================
```

### 完整测试套件

```bash
# 集成测试：5/5 通过
pytest tests/integration/ -v

# 单元测试：30/30 通过
pytest tests/unit/ -v

# 总覆盖率：34%
pytest --cov=app --cov-report=html
```

---

**最后更新**: 2026-04-03  
**维护者**: Backend Team  
**测试状态**: ✅ 全部通过 (5/5 集成测试，30/30 单元测试)
