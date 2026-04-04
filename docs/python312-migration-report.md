# Python 3.12 降级与集成测试修复报告

**执行日期**: 2026-04-04  
**执行人**: Backend Architect Agent  
**项目**: customer_platform_vk

---

## 1. 执行摘要

### 1.1 完成情况

| 任务 | 状态 | 说明 |
|------|------|------|
| Python 3.12 环境搭建 | ✅ 完成 | 使用 pyenv 安装 Python 3.12.0 |
| 依赖安装 | ✅ 完成 | 所有依赖包兼容 Python 3.12 |
| 单元测试 | ✅ 通过 | 58/58 测试通过 (100%) |
| 集成测试 | ⚠️ 部分通过 | 2/15 测试通过 (13%) |

### 1.2 当前环境

```
Python: 3.12.0
Sanic: 22.12.0
sanic-testing: 22.12.0
httpx: 0.23.3
asyncpg: 0.29.0
SQLAlchemy: 2.0.25
pytest: 7.4.4
pytest-asyncio: 0.23.4
```

---

## 2. Python 3.12 环境搭建

### 2.1 安装步骤

```bash
# 1. 使用 pyenv 安装 Python 3.12
pyenv install 3.12.0

# 2. 创建新的虚拟环境
cd backend
rm -rf .venv
~/.pyenv/versions/3.12.0/bin/python3.12 -m venv .venv

# 3. 激活虚拟环境
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt
```

### 2.2 验证结果

```bash
$ python --version
Python 3.12.0

$ pip list | grep -E "sanic|sqlalchemy|asyncpg"
sanic           22.12.0
sanic-testing   22.12.0
sqlalchemy      2.0.25
asyncpg         0.29.0
```

---

## 3. 测试结果

### 3.1 单元测试（✅ 全部通过）

```
======================== 58 passed, 8 warnings in 7.32s ========================
```

**测试覆盖率**: 18% (详细报告见 `backend/htmlcov/index.html`)

### 3.2 集成测试（⚠️ 部分通过）

```
=========================== short test summary info ============================
PASSED tests/integration/test_api.py::test_health_check
PASSED tests/integration/test_groups_api.py::TestListGroups::test_list_groups_unauthorized
FAILED tests/integration/test_api.py::test_login_success
FAILED tests/integration/test_api.py::test_login_invalid_credentials
FAILED tests/integration/test_api.py::test_get_customers_list
FAILED tests/integration/test_api.py::test_get_billing_balance
FAILED tests/integration/test_groups_api.py::TestCreateGroup::test_create_dynamic_group
FAILED tests/integration/test_groups_api.py::TestCreateGroup::test_create_static_group
FAILED tests/integration/test_groups_api.py::TestCreateGroup::test_create_group_missing_name
FAILED tests/integration/test_groups_api.py::TestListGroups::test_list_user_groups
FAILED tests/integration/test_groups_api.py::TestGetGroup::test_get_group_detail
FAILED tests/integration/test_groups_api.py::TestGetGroup::test_get_group_not_found
FAILED tests/integration/test_groups_api.py::TestDeleteGroup::test_delete_group
FAILED tests/integration/test_groups_api.py::TestGroupMembers::test_add_and_remove_member
FAILED tests/integration/test_groups_api.py::TestGroupStats::test_get_group_stats
================== 13 failed, 2 passed, 16 warnings in 29.77s ==================
```

---

## 4. 集成测试失败根因分析

### 4.1 错误类型

```
RuntimeError: Cannot run the event loop while another loop is running
```

### 4.2 问题根因

**核心冲突**: Sanic test_client 与 pytest-asyncio 事件循环冲突

1. **Sanic test_client** 在测试时创建独立事件循环运行 HTTP 服务器
2. **pytest-asyncio** 创建另一个事件循环管理异步 fixture（如 `db_session`）
3. **asyncpg** 通过 SQLAlchemy AsyncSession 需要事件循环执行数据库操作
4. **Python 3.12** 对事件循环管理更严格，不允许嵌套运行事件循环

### 4.3 尝试的解决方案

| 方案 | 结果 | 说明 |
|------|------|------|
| 使用同步数据库引擎 | ❌ 失败 | 服务层硬编码使用异步代码 |
| 统一事件循环策略 | ❌ 失败 | Sanic test_client 内部创建独立循环 |
| 禁用 uvloop | ❌ 失败 | uvloop 仍被 Sanic 使用 |
| 使用 ASGI 客户端 | ❌ 失败 | 需要异步调用方式 |
| 自定义 event_loop fixture | ❌ 失败 | 与 Sanic test_client 冲突 |

---

## 5. 推荐解决方案

### 5.1 方案 A: 使用 pytest-sanic 插件（推荐）

**优点**:
- 专门为 Sanic 设计的测试插件
- 自动处理事件循环管理
- 与 Sanic 生态系统完全兼容

**实施步骤**:
```bash
# 1. 安装 pytest-sanic
pip install pytest-sanic

# 2. 修改 conftest.py 使用 sanic 测试 fixture
# 3. 更新测试用例使用异步方式
```

### 5.2 方案 B: 进程隔离测试

**优点**:
- 完全避免事件循环冲突
- 最接近生产环境测试

**实施步骤**:
```python
# 1. 在测试中启动独立 Sanic 进程
# 2. 使用 httpx 异步客户端进行 HTTP 测试
# 3. 测试完成后关闭进程
```

### 5.3 方案 C: 服务层同步/异步双模式支持

**优点**:
- 保持现有测试架构
- 提高代码灵活性

**实施步骤**:
```python
# 1. 修改所有服务层方法使用 _execute 辅助方法
# 2. 根据 Session 类型自动选择同步/异步执行
# 3. 集成测试使用同步数据库引擎
```

**已实施部分**:
- `app/services/users.py` 已添加 `_execute` 辅助方法
- `get_user_by_id` 和 `get_user_by_username` 已修改

**待完成**:
- 修改其他服务方法（`get_all_users`, `create_user`, `update_user` 等）
- 修改 groups、customers、billing 等服务层

---

## 6. 修改的文件清单

### 6.1 配置文件

| 文件 | 修改内容 |
|------|----------|
| `backend/pytest.ini` | 添加 `asyncio_default_fixture_loop_scope = function` |

### 6.2 测试配置

| 文件 | 修改内容 |
|------|----------|
| `backend/tests/integration/conftest.py` | 1. 设置 `SANIC_NO_UVLOOP=1`<br>2. 设置 asyncio 事件循环策略<br>3. 使用异步数据库引擎<br>4. 添加异步 fixture |

### 6.3 测试文件

| 文件 | 修改内容 |
|------|----------|
| `backend/tests/integration/test_api.py` | 1. 修改文档说明<br>2. 添加 `@pytest.mark.asyncio` 标记<br>3. 使用异步数据库操作 |

### 6.4 服务层

| 文件 | 修改内容 |
|------|----------|
| `backend/app/services/users.py` | 1. `get_user_by_id` 使用 `_execute`<br>2. `get_user_by_username` 使用 `_execute` |

---

## 7. 下一步建议

### 7.1 短期（1-2 天）

1. **安装 pytest-sanic 插件**
   ```bash
   pip install pytest-sanic
   ```

2. **按照 pytest-sanic 文档重构集成测试**
   - 使用 `sanic_app` fixture
   - 使用 `sanic_client` 进行测试

3. **验证所有集成测试通过**

### 7.2 中期（1 周）

1. **完成服务层同步/异步双模式支持**
   - 修改所有服务类使用 `_execute` 辅助方法
   - 添加完整的同步/异步检测逻辑

2. **添加集成测试覆盖率**
   - 覆盖所有 API 端点
   - 添加边界条件测试

### 7.3 长期

1. **考虑升级 Sanic 版本**
   - Sanic 22.12.0 较旧，可能存在兼容性问题
   - 评估升级到 Sanic 23.x 或 24.x

2. **改进测试架构**
   - 考虑使用测试容器（Testcontainers）进行数据库测试
   - 添加端到端测试

---

## 8. 参考资源

- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [Sanic 测试文档](https://sanic.dev/en/guide/testing/testing.html)
- [SQLAlchemy 异步支持](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Python 3.12 事件循环变更](https://docs.python.org/3/whatsnew/3.12.html)

---

**报告生成时间**: 2026-04-04 08:50:00  
**Python 版本**: 3.12.0  
**测试状态**: 单元测试 ✅ | 集成测试 ⚠️
