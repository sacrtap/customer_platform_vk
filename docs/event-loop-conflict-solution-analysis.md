# 事件循环冲突问题解决方案分析报告

## 🔍 问题诊断

### 核心问题
**pytest-sanic 与 pytest-asyncio + asyncpg 事件循环不兼容**

错误信息：
```
RuntimeError: Task got Future attached to a different loop
```

### 根因分析

#### 1. 双重事件循环管理
- **pytest-sanic**: 自己管理事件循环（通过 `loop` fixture）
- **pytest-asyncio**: 也管理事件循环（通过 `event_loop` fixture）
- **结果**: 两个事件循环同时运行，导致冲突

#### 2. Fixture 架构冲突

**当前配置问题**：

```python
# tests/conftest.py (单元测试)
pytest_plugins = ("pytest_asyncio",)  # ❌ 引入 pytest-asyncio
pytestmark = pytest.mark.asyncio(scope="function")

@pytest.fixture(scope="session")
def event_loop():  # ❌ 创建独立事件循环
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

```python
# tests/integration/conftest.py (集成测试)
# ✅ 使用 pytest-sanic 的 sanic 和 sanic_client fixture
# 但受到了全局 pytest-asyncio 配置的影响
```

#### 3. 技术栈版本分析

| 组件 | 版本 | 事件循环管理 |
|------|------|-------------|
| Sanic | 22.12.0 | 自有事件循环 |
| sanic-testing | 22.12.0 | 依赖 Sanic 事件循环 |
| pytest-sanic | 1.9.1 | 创建独立 loop fixture |
| pytest-asyncio | 0.23.4 | 创建 event_loop fixture |
| asyncpg | 0.29.0 | 使用 asyncio.get_event_loop() |

---

## 💡 解决方案

### 方案 1：使用 Sanic ASGI Client（推荐 ⭐⭐⭐⭐⭐）

**核心思路**: 放弃 pytest-sanic，使用 sanic-testing 的 ASGI 客户端 + pytest-asyncio

#### 优势
- ✅ 官方推荐方案（Sanic 文档）
- ✅ 与 pytest-asyncio 完全兼容
- ✅ 支持异步测试，可 await 数据库操作
- ✅ 无需维护两个事件循环

#### 实施步骤

**Step 1: 修改 tests/conftest.py**
```python
# 移除 pytest-sanic 相关配置
# 保留 pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
pytestmark = pytest.mark.asyncio(scope="function")
```

**Step 2: 修改 tests/integration/conftest.py**
```python
import pytest
from sanic_testing import TestManager

@pytest.fixture(scope="function")
def test_client(app):
    """使用 Sanic ASGI 客户端"""
    return app.asgi_client  # 或 TestManager(app).asgi_client
```

**Step 3: 修改测试函数**
```python
# 所有测试使用异步方式
@pytest.mark.asyncio
async def test_health_check(test_client):
    request, response = await test_client.get("/health")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_login_success(test_client, db_session):
    # 可以直接 await 数据库操作
    await db_session.execute(...)
    await db_session.commit()
    
    # 异步调用 API
    request, response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "test", "password": "test123"}
    )
```

#### 参考文档
- https://github.com/sanic-org/sanic/blob/main/guide/content/en/plugins/sanic-testing/getting-started.md

---

### 方案 2：完全使用 pytest-sanic（不推荐 ⭐⭐）

**核心思路**: 完全移除 pytest-asyncio，所有测试使用 pytest-sanic 的事件循环

#### 实施步骤

**Step 1: 修改 tests/conftest.py**
```python
# 移除 pytest-asyncio
# pytest_plugins = ("pytest_asyncio",)  # ❌ 删除
# pytestmark = pytest.mark.asyncio  # ❌ 删除

# 使用 pytest-sanic
pytest_plugins = ("pytest_sanic",)
```

**Step 2: 修改 tests/integration/conftest.py**
```python
# 移除 event_loop fixture
# 使用 pytest-sanic 的 loop fixture

@pytest.fixture(scope="function")
async def test_client(sanic_client, app):
    """创建 TestClient"""
    client = await sanic_client(app)
    yield client
    await client.close()
```

**Step 3: 修改测试函数**
```python
# 不需要 @pytest.mark.asyncio
# pytest-sanic 会自动处理协程

def test_health_check(test_client):
    # 同步方式调用（pytest-sanic 内部处理）
    request, response = test_client.get("/health")
    assert response.status_code == 200
```

#### 缺点
- ❌ 无法与 asyncpg 配合使用（事件循环冲突）
- ❌ pytest-sanic 已不再积极维护
- ❌ 测试代码需要改写为同步风格

---

### 方案 3：进程隔离测试（高级方案 ⭐⭐⭐）

**核心思路**: 将集成测试放在独立进程中运行，完全隔离事件循环

#### 实施步骤

**Step 1: 安装 pytest-xdist**
```bash
pip install pytest-xdist
```

**Step 2: 创建独立测试配置**
```python
# tests/integration/conftest.py
import multiprocessing
import pytest

# 强制每个测试在独立进程中运行
@pytest.fixture(scope="session", autouse=True)
def isolate_event_loop():
    multiprocessing.set_start_method('spawn', force=True)
    yield
```

**Step 3: 运行测试使用 -n 参数**
```bash
python -m pytest tests/integration/ -v -n 1
```

#### 缺点
- ❌ 配置复杂
- ❌ 测试执行速度慢
- ❌ 调试困难

---

## 🎯 推荐方案：方案 1（ASGI Client）

### 详细实施计划

### 第一阶段：准备工作（30 分钟）

1. **备份当前配置**
   ```bash
   cp tests/conftest.py tests/conftest.py.backup
   cp tests/integration/conftest.py tests/integration/conftest.py.backup
   ```

2. **卸载 pytest-sanic**
   ```bash
   pip uninstall pytest-sanic
   ```

### 第二阶段：修改配置（1 小时）

3. **修改 tests/conftest.py**
   - 保留 pytest-asyncio 配置
   - 移除与 pytest-sanic 相关的任何引用

4. **修改 tests/integration/conftest.py**
   ```python
   # 移除 pytest-sanic 相关代码
   # 使用 app.asgi_client 作为 test_client
   
   @pytest.fixture(scope="function")
   def test_client(app):
       return app.asgi_client
   ```

5. **修改测试函数**
   - 所有测试添加 `@pytest.mark.asyncio`
   - 所有 API 调用改为 `await test_client.get/post/...`

### 第三阶段：验证测试（1 小时）

6. **运行单个测试验证**
   ```bash
   python -m pytest tests/integration/test_api.py::test_health_check -v
   ```

7. **运行所有集成测试**
   ```bash
   python -m pytest tests/integration/ -v
   ```

8. **确保单元测试仍然通过**
   ```bash
   python -m pytest tests/ -v
   ```

### 第四阶段：清理优化（30 分钟）

9. **移除 pytest-sanic 依赖**
   ```bash
   # requirements.txt
   # 删除 sanic-testing==22.12.0（如果不再需要同步测试）
   ```

10. **更新文档**
    - 更新测试指南
    - 记录最佳实践

---

## 📊 方案对比

| 维度 | 方案 1 (ASGI) | 方案 2 (pytest-sanic) | 方案 3 (进程隔离) |
|------|-------------|---------------------|-----------------|
| **兼容性** | ✅ 优秀 | ❌ 差 | ✅ 优秀 |
| **维护成本** | ✅ 低 | ⚠️ 中 | ❌ 高 |
| **测试性能** | ✅ 快 | ✅ 快 | ❌ 慢 |
| **代码改动** | ⚠️ 中等 | ⚠️ 中等 | ❌ 大量 |
| **官方支持** | ✅ 官方推荐 | ❌ 已弃用 | ⚠️ 社区方案 |
| **asyncpg 支持** | ✅ 完全支持 | ❌ 不支持 | ✅ 支持 |
| **推荐指数** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |

---

## ⚠️ 风险评估

### 方案 1 风险
- **风险**: 低
- **缓解**: ASGI Client 是 Sanic 官方推荐方案，文档完善

### 方案 2 风险
- **风险**: 高
- **原因**: pytest-sanic 与 asyncpg 不兼容，可能导致集成测试继续失败

### 方案 3 风险
- **风险**: 中
- **原因**: 配置复杂，可能引入新的问题

---

## 📝 结论

**强烈推荐使用方案 1（Sanic ASGI Client + pytest-asyncio）**

### 理由
1. ✅ 官方推荐，长期支持
2. ✅ 与 pytest-asyncio 完全兼容
3. ✅ 支持异步数据库操作
4. ✅ 代码改动量适中
5. ✅ 测试性能优秀

### 预计工作量
- **总时间**: 2-3 小时
- **风险**: 低
- **成功率**: 95%+

---

**最后更新**: 2026-04-04  
**作者**: AI Assistant  
**状态**: 待执行
