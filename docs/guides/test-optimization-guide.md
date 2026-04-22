# 测试套件优化指南

**创建日期**: 2026-04-22
**问题**: 测试套件运行时间过长（>2 分钟）

---

## 问题根因

| 根因                   | 影响程度  | 说明                                                                                         |
| ---------------------- | --------- | -------------------------------------------------------------------------------------------- |
| **默认开启覆盖率收集**     | ⚠️⚠️⚠️ 高 | `pytest.ini` 中 `addopts` 包含 `--cov=app --cov-report=html`，每次测试都收集覆盖率并生成 HTML 报告 |
| **无并行执行**          | ⚠️⚠️ 中   | 未使用 `pytest-xdist`，所有测试串行执行                                                        |
| **数据库 fixture 过重** | ⚠️⚠️ 中   | 每个集成测试都执行 `drop_all` + `create_all`，重复创建/删除所有表                                |
| **无测试分层机制**      | ⚠️ 低     | 无法单独运行单元测试（快速验证），必须运行全量测试                                           |

---

## 已实施的优化

### 1. 分离开发与 CI 的 pytest 配置

**修改文件**: `backend/pytest.ini`

**变更前**：
```ini
addopts = -v --tb=short --cov=app --cov-report=html --cov-report=term-missing
```

**变更后**：
```ini
addopts = -v --tb=short
```

**效果**：
- 开发环境默认运行：`pytest tests/`（快速，无覆盖率）
- CI 环境显式指定：`pytest --cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=50`

### 2. 添加并行测试支持

**修改文件**: `backend/requirements.txt`

新增依赖：
```
pytest-xdist==3.8.0
```

**使用方式**：
```bash
# 使用所有 CPU 核心并行运行测试
pytest tests/ -n auto

# 指定进程数
pytest tests/ -n 4
```

**预期加速比**：
- 4 核机器：约 3x 加速
- 8 核机器：约 5-6x 加速

### 3. 创建 Makefile 快捷命令

**新增文件**: `backend/Makefile`

| 命令                  | 用途                         | 预计时间      |
| --------------------- | ---------------------------- | ------------- |
| `make test`           | 运行所有测试（无覆盖率）       | ~30-60 秒     |
| `make test-fast`      | 仅运行单元测试（最快）         | ~5-10 秒      |
| `make test-parallel`  | 并行运行所有测试               | ~10-20 秒     |
| `make test-cov`       | 运行测试 + 覆盖率（CI 用）     | ~60-120 秒    |
| `make test-unit`      | 单元测试 + 覆盖率             | ~10-20 秒     |
| `make test-integration`| 集成测试 + 覆盖率             | ~40-80 秒     |
| `make test-report`    | 运行测试并打开 HTML 报告       | ~60-120 秒    |

---

## 使用指南

### 日常开发流程

```bash
# 1. 快速验证修改（推荐）
cd backend && make test-fast

# 2. 运行完整测试（无覆盖率）
cd backend && make test

# 3. 提交前运行并行测试
cd backend && make test-parallel
```

### CI/CD 流程

CI 已配置为显式使用覆盖率参数，不受本地配置影响：

```yaml
# .github/workflows/ci.yml
pytest --cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=50
```

### 覆盖率检查

```bash
# 生成覆盖率报告
cd backend && make test-cov

# 在浏览器中查看
open htmlcov/index.html
```

---

## 未来优化方向

### 1. 数据库事务回滚优化

当前每个测试都执行 `drop_all` + `create_all`，可以优化为：
- 使用事务回滚代替删除/创建表
- 使用 `SAVEPOINT` 实现测试间隔离

**预期效果**：集成测试速度提升 40-60%

### 2. 测试分层 fixture

优化 `conftest.py` 中的 fixture 作用域：
```python
# 使用 session scope 共享数据库连接
@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DB_URL)
    with engine.begin() as conn:
        BaseModel.metadata.create_all(conn)
    yield engine
    with engine.begin() as conn:
        BaseModel.metadata.drop_all(conn)
```

### 3. 增量测试

安装 `pytest-testmon` 插件，仅运行受更改影响的测试：
```bash
pip install pytest-testmon
pytest tests/ --testmon
```

**预期效果**：小改动时测试时间减少 70-90%

---

## 常见问题

**Q: 为什么本地测试不默认收集覆盖率？**
A: 覆盖率收集会增加 20-40% 的运行时间。开发阶段更关注快速反馈，覆盖率检查在 CI 中统一执行即可。

**Q: 并行测试会破坏测试隔离吗？**
A: pytest-xdist 为每个进程创建独立的测试环境。但如果有共享外部资源（如数据库），需要确保测试间正确隔离。当前项目的集成测试使用独立的数据库 fixture，可以安全并行。

**Q: 如何在 VS Code 中使用新的配置？**
A: VS Code 的 Python 测试插件会自动读取 `pytest.ini`。运行测试时默认不使用覆盖率，如需覆盖率可在设置中添加参数。
