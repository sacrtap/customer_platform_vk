# 设计：测试基础设施修复

## 决策概览

| 编号 | 问题 | 决策 | 理由 |
|---|---|---|---|
| **D1** | 同名测试文件冲突 | `pytest.ini` 的 `addopts` 增加 `--import-mode=importlib` | 单行改动即可覆盖全部同类冲突，且**不移动、不合并任何测试文件**（满足 REQ-1「不牺牲覆盖」）；4 个文件的内容经实测确认为互补 |
| **D2** | 遗留测试引用过时接口 | 逐点修正到当前模型接口 | 这些测试仍验证真实行为（仓储层 CRUD、排序白名单），修正成本远低于重写 |
| **D3** | `search` 抛 `'.type'` TypeError | 修**生产代码**：`cast(Customer.company_id, String)` | 该失败是真实缺陷，非测试问题（详见下节） |
| **D4** | `.trellis` 产物缺尾换行 | 在 `io.write_text_atomic` 统一保证 | 单点覆盖全部调用方（`write_json`、`index.md`、journal），无需逐处修补 |

## REQ-1：消除同名冲突

### 选用方案：`--import-mode=importlib`

`backend/pytest.ini` 现状 `addopts = -v --tb=short` → 改为 `addopts = -v --tb=short --import-mode=importlib`。

**为什么放在 `addopts`**：CI（`pr-checks.yml` / `backend-integration.yml`）以命令行追加 `-n auto --cov=...` 调用 pytest，`addopts` 对其同样生效，一处修改同时覆盖本地与 CI；无需改动任何 workflow（满足 AC-5）。

### 兼容性论证（已验证 / 待 implement 验证）

| 关注点 | 结论 | 依据 |
|---|---|---|
| `tests/conftest.py` 清理 `sys.modules`、`sys.path.insert(backend_dir)` | 与 import-mode 正交 | conftest 由 pytest 内部的 import_path 机制加载，不经 test 文件的 import-mode；`sys.path` 注入服务于 `import app.*`（解释器层），`sys.modules` 清理服务于模块缓存层 —— 二者均不依赖 basename 解析 |
| `tests/integration/conftest.py` 的 `sys.modules['aiosmtplib']=MagicMock()`、清理 `Sanic._app_registry` | 同上，正交 | 同上 |
| pytest-xdist 3.8.0 | 官方兼容（`importlib` 正是并行场景下规避 basename 冲突的推荐模式） | 实测待补：`pytest tests/unit/ -n auto --import-mode=importlib` |

**已完成的实测**：
- `pytest tests/unit/ tests/integration/ --import-mode=importlib` → **690 passed**（此前因 correlation 同名冲突无法在同一 session 运行）
- `pytest tests/ --import-mode=importlib` → 收集**成功**（无 collection error），运行 `34 failed, 843 passed, 3 errors`

### 备选方案（未选用）

| 方案 | 缺点 |
|---|---|
| 重命名重复文件（如 `test_correlation_middleware_integration.py`） | 改动 2 个文件名 + 可能有外部引用；新增同名文件时问题复现 |
| 给 `tests/`、`tests/unit/` 等目录补 `__init__.py` | 会把测试目录变成包，改变导入语义；对 `tests/` 根目录与子目录的既有混合结构影响面更大 |
| 删除其中一个重复文件 | 违反 REQ-1：两组均为互补（root analytics 64 测试 vs unit 6 测试；correlation unit 15 用例 vs integration 5 用例） |

## REQ-2：修正遗留测试

### 修复点清单

**（1）`tests/test_customers_sorting.py::TestSortConstants::test_allowed_sort_fields_contains_expected_fields`**

`expected_fields` 集只有 10 项，而 `app/services/customers.py:19-41` 的 `ALLOWED_SORT_FIELDS` 为 **17 项**，且源码已按语义分组注释：

```python
ALLOWED_SORT_FIELDS = {
    # Customer 表原生字段（10）
    "id", "company_id", "name", "account_type", "created_at", "updated_at",
    "settlement_type", "manager_id", "sales_manager_id", "is_key_customer",
    # CustomerProfile 表字段（需 JOIN）（4）
    "industry_type_id", "industry", "scale_level", "consume_level",
    # CustomerBalance 表字段（需 JOIN）（1）
    "balance",
    # 占位字段（无实际 DB 列，排序时退化为按 id 排序）（2）
    "usage_30d", "health",
}
```

→ 将断言的 `expected_fields` 补齐为完整 17 项。

**（2）`tests/test_customers_sorting.py::TestSortEdgeCases::test_all_allowed_sort_fields_are_valid_customer_attributes`**

现断言：`industry_type_id` 检查 `CustomerProfile`，其余一律 `hasattr(Customer, field)` —— 与实现不符（`consume_level`/`scale_level` 在 `CustomerProfile`，`balance` 在 `CustomerBalance`，`usage_30d`/`health` 为派生/占位）。

→ 改写为按 4 类分别校验，并**加一条更强的断言**：每个白名单字段在 `get_all_customers` 的排序分派（`app/services/customers.py:334-378`）中都有对应处理分支 —— 这才是该白名单的真实契约（防止"白名单加了字段但排序未实现"这类缺陷）。

**（3）`tests/test_repository/conftest.py::sample_pricing_rule`（133-149 行）**

传入 `name` / `price_type` / `effective_from` / `is_active` —— `PricingRule`（`app/models/billing.py:85-113`）真实字段为 `customer_id` / `device_type` / `layer_type` / `pricing_type` / `unit_price` / `effective_date` / `expiry_date` 等。

→ 改为：

```python
PricingRule(
    customer_id=sample_customer.id,
    device_type="X",          # 值域 X/N/L
    layer_type="single",      # 值域 single/multi/single_and_multi
    pricing_type="fixed",     # 值域 fixed/tiered/package
    unit_price=Decimal("100.00"),
    effective_date=date(2026, 1, 1),
)
```

该 fixture 失效是 **3 个 error + 4 个 failed** 的共同根因（`test_pricing_repo.py` 全部依赖它）。

**（4）`tests/test_repository/test_customer_repo.py::TestCustomerRepository::test_create`**

`Customer(contact_person=…, phone=…)` —— 两字段已从模型移除。

→ 改用当前必填/代表性字段（`company_id`、`name`、`account_type`、`manager_id` 等），断言仍验证 CRUD 语义（`id` 生成、`created_at` 填充）。

**（5）`tests/test_repository/test_customer_repo.py::TestCustomerRepository::test_search` — 暴露生产代码缺陷**

失败为 `TypeError: Object '' associated with '.type' attribute is not a TypeEngine class or object`。根因在 `app/repository/customer_repo.py:35-42`：

```python
Customer.company_id.cast(str).ilike(f"%{keyword}%")   # ← 缺陷
```

SQLAlchemy 列元素没有 `.cast()` 这种用法，且 `str` 不是 `TypeEngine` 实例；正确写法是 `cast(Customer.company_id, String)`（需 `from sqlalchemy import String, cast`）。

→ **修生产代码**（不是改测试）：这是被遗留测试掩盖的真实缺陷 —— 任何调用 `CustomerRepository.search()` 的路径（关键词搜索公司 ID）都会抛 TypeError。修复后保留该测试作为回归保护。

> 注：此修复使本次改动从"纯测试基础设施"扩展为含 1 处生产代码修复。该修复由 REQ-2 的「修正到当前真实接口」自然引出，且是让测试通过的**唯一正确**方式（改测试去规避会掩盖缺陷）。

## REQ-3：`.trellis` 产物尾换行

在 `.trellis/scripts/common/io.py` 的 `write_text_atomic` 中，写入前统一规范化：

```python
with f:
    f.write(text if text.endswith("\n") else text + "\n")
```

**为何选此处**：`write_json`（`json.dumps` 输出无尾换行）与 `add_session.py:1059`（`"\n".join(new_lines)`）是 `.trellis` 状态文件的**唯一两条写入路径**，均经由 `write_text_atomic`。单点修复即可覆盖 `task.json`、`index.md`、journal，且不依赖 pre-commit 排除（满足 REQ-3）。

**不选 pre-commit 排除方案的理由**：`.pre-commit-config.yaml` 的 `end-of-file-fixer` 无 `exclude`，仓库也无 `.trellis/` 排除先例；排除等于让脚本持续产出不合规文件，并把"该 hook 对 .trellis 失效"这一例外扩散到今后所有脚本产物。

## 风险与回滚

| 改动 | 风险 | 回滚 |
|---|---|---|
| `pytest.ini` 加 `--import-mode=importlib` | 低（影响模块解析策略；已实测 unit+integration 690 passed） | 删该参数 |
| 测试文件修正 | 低（仅测试代码） | `git revert` |
| `app/repository/customer_repo.py` 修 `cast` | 中（生产查询路径） | `git revert` 单文件 |
| `io.py` 尾换行 | 低（写入语义不变，仅补一个 `\n`） | `git revert` |

## 验证计划

1. `pytest tests/ --collect-only -q` → 0 error
2. `make test-cov` → 退出码 0 且覆盖率 ≥50%
3. `pytest tests/unit/ -q` ≥447 passed；`pytest tests/integration/ -q` 全通过
4. `pytest tests/unit/ -n auto`（xdist 兼容性）
5. `task.py create` + `archive` + `add_session.py` 实跑一轮，检查 auto-commit 不再被 hook 阻断
