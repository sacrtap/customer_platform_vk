# 执行计划：测试基础设施遗留项修复（TD-1/2/4/5）

> 对应 `prd.md`（AC1–AC9）与 `design.md`。按「先立单一来源 → 再收敛环境变量 → 后清理噪声 → 最后动生产缓存配置」排序。

---

## 阶段 0：前置确认（勿跳过）

- [ ] `ls backend/tests/__init__.py` → 决定 `_test_data` 导入写法（`from tests._test_data import ...` vs `from _test_data import ...`）
- [ ] `grep -n "sys\." backend/tests/integration/conftest.py` → 确认 `test_user` 内除探针外是否还有 `sys.` 引用
- [ ] `grep -n "^import logging\|^logger = " backend/tests/integration/conftest.py` → 确认是否已有模块级 logger
- [ ] `python3 -c "import sys; sys.path.insert(0,'backend'); from scripts.seed import ALL_PERMISSIONS; print(len(ALL_PERMISSIONS), ALL_PERMISSIONS[0])"` → 确认 seed 元组形状（预期 4 元组、48 条）
- [ ] 记录基线：`cd backend && .venv/bin/python -m pytest tests/ -q` → 预期 **874 passed**
- [ ] 若任一确认项推翻 `design.md` 假设 → 回到 planning 修订设计

---

## 阶段 1：权限清单单一来源（R1/R2 → AC1/AC2）

### 1.1 新建 `backend/tests/_test_data.py`

- [ ] 定义 `PERMISSION_ROWS: list[tuple[str, str, str]]`，42 条，**逐字**取自 `tests/integration/conftest.py:214-255`（已实测四份一致，取任一份即可）
- [ ] 定义 `PERMISSION_CODES: frozenset[str]`，**由行数据派生**（`frozenset(code for code, _, _ in PERMISSION_ROWS)`）
- [ ] 模块 docstring 说明「唯一来源 + 为何派生」

### 1.2 四处替换

- [ ] `tests/integration/conftest.py` `test_user`：字面量列表 → 遍历 `PERMISSION_ROWS`
- [ ] `tests/integration/conftest.py` `mock_cache`：`FULL_PERMISSIONS = {...}` → `PERMISSION_CODES`
- [ ] `tests/e2e/conftest.py` `test_user`：同 integration
- [ ] `tests/e2e/conftest.py` `mock_cache`：同 integration
- [ ] 两文件顶部加导入语句（写法依阶段 0 结论）

### 1.3 漂移守护测试

- [ ] 新增测试断言 `PERMISSION_CODES ⊆ seed.ALL_PERMISSIONS 的 code 集合`

### 验证（AC1/AC2）

- [ ] `grep -rn '("customers:view", "查看客户", "customers")' backend/tests/ --include=*.py` → **仅 1 处**（`_test_data.py`）
- [ ] `grep -rn "FULL_PERMISSIONS" backend/tests/ --include=*.py` → 两处均为 `PERMISSION_CODES` 赋值，无字面量集合
- [ ] 漂移守护测试通过
- [ ] **反向验证**：临时把 `_test_data.py` 一个 code 改为 seed 未定义值 → 该测试失败；**改回**
- [ ] `pytest tests/integration/ -q` 与 `pytest tests/e2e/ -q` 分别全绿

---

## 阶段 2：`WEBHOOK_SECRET` 收敛（R3 → AC3/AC8）

- [ ] `tests/conftest.py`：在 `JWT_SECRET` 的 `setdefault` 后追加 `os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret-key")`
- [ ] `tests/integration/conftest.py:19-20`：删除强制赋值，替换为「基线由根 conftest 提供 / 需不同值应 monkeypatch」的说明注释（保留 JWT 解释性注释）
- [ ] `tests/e2e/conftest.py:17`：同上
- [ ] 确认两层的模块级引导序列（`cache_clear` + settings 重建）保持不变

### 验证（AC3/AC8）

- [ ] `grep -rn "WEBHOOK_SECRET" backend/tests/ --include=*.py` → **仅 1 处**（`tests/conftest.py`）
- [ ] `pytest tests/ --collect-only -q` → 无 error
- [ ] **同会话** `pytest tests/e2e/ tests/integration/ -q` → 全绿（基线 246 passed）

---

## 阶段 3：移除 stdout 探针（R4 → AC4）

- [ ] 删除 8 处 `sys.stdout.write("[DEBUG] ...")` + 紧邻 `sys.stdout.flush()`
- [ ] 行 314 的 `[ERROR]` → `logger.error("test_user: 用户创建后查询不到（username=%s）", username)`
- [ ] 删除该 fixture 内不再使用的 `import sys`（依阶段 0 结论）
- [ ] 需要时在模块顶部加 `logger = logging.getLogger(__name__)`
- [ ] **不得改变** `test_user` 的控制流（`count > 0` 提前 return 的分支必须原样保留）

### 验证（AC4）

- [ ] `grep -c "sys.stdout" backend/tests/integration/conftest.py` → **0**
- [ ] `grep -c "\[DEBUG\]" backend/tests/integration/conftest.py` → **0**
- [ ] `pytest tests/integration/ -q` 全绿

---

## 阶段 4：TTL 配置单一真相（R5 → AC5/AC6）

### 4.1 `app/cache/base.py`

- [ ] 新增 `ttl_for(prefix: str) -> int`（含 docstring 说明「唯一读取入口」）
- [ ] `set()` 内改用 `self.ttl_for(prefix)`
- [ ] `_ttl_config` 移除 `"billing_pricing_rules": 3600`

### 4.2 `app/routes/billing/balances.py`

- [ ] 行 87 附近：循环外取 `ttl = cache_service.ttl_for("billing_consumption")`，`pipe.setex(key, ttl, val)` 替换硬编码 `300`

### 4.3 `tests/test_cache.py`

- [ ] 删除 `test_init_default_ttl_config`（整字典断言）
- [ ] 新增 `test_ttl_for_returns_configured_values` 与 `test_ttl_for_unknown_prefix_falls_back_to_default`

### 验证（AC5/AC6）

- [ ] `grep -n "setex" backend/app/routes/billing/balances.py` → 无硬编码数字字面量
- [ ] `grep -rn "billing_pricing_rules" backend/ --include=*.py` → 0 命中
- [ ] `pytest tests/test_cache.py -q` 全绿
- [ ] 人工核对：`_ttl_config` 每个 key 均有消费点（`billing_consumption` 经 `ttl_for` 被 balances 使用）

---

## 阶段 5：清理零消费的 `settings.cache_ttl_*`（R6 → AC10/AC11）

### 5.1 `backend/app/config.py`

- [ ] 删除 `# 缓存 TTL 配置 (秒)` 注释与 9 个 `cache_ttl_*` 字段（第 79-88 行）
- [ ] **不得**触碰同文件其它字段（`consumption_forecast_unit_prices` 等必须原样保留）

### 5.2 `.env.example`

- [ ] 删除对应注释块与被注释的 9 行 `CACHE_TTL_*`（第 130-157 行区间）
- [ ] 保留相邻其它配置段不变

### 5.3 `docs/performance/cache-strategy.md`

- [ ] 删除第 49-57 行的配置表（其把 `cache_ttl_*` 描述为运维可配项，属误导）
- [ ] 改写为：**TTL 的唯一真实来源**是 `app/cache/base.py::CacheService._ttl_config`，读取入口为 `ttl_for(prefix)`；修改 TTL 需改代码而非环境变量
- [ ] 列出的条目须与 `_ttl_config` 实际内容一致（含 `billing_consumption`，**不含**已删的 `billing_pricing_rules`）

### 5.4 不改动

- [ ] `docs/party-mode-memories/2026-08-12-consumption-forecast-memory.md:61`（历史会话记录，属不可变史料）

### 验证（AC10/AC11）

- [ ] `grep -rn "cache_ttl_" backend/app/ --include=*.py` → **0**
- [ ] `grep -n "CACHE_TTL" .env.example` → **0**
- [ ] `grep -n "cache_ttl_" docs/performance/cache-strategy.md` → **0**
- [ ] `cd backend && .venv/bin/python -c "from app.config import Settings; s=Settings(); print('Settings 实例化成功')"` → 无 ValidationError（证明删字段不影响启动）
- [ ] `docs/performance/cache-strategy.md` 的条目清单与 `_ttl_config` 逐条对照一致

---

## 阶段 6：整体验证与文档回写

- [ ] 后端全量：`cd backend && .venv/bin/python -m pytest tests/ -q` → 全绿且 ≥ 874 passed
- [ ] 覆盖率：`.venv/bin/python -m pytest tests/ --cov=app --cov-fail-under=50 -q`
- [ ] `cd backend && .venv/bin/ruff check app/ tests/ scripts/` + `ruff format --check app/ tests/ scripts/`
- [ ] 前端（未改动，确认无回归）：`cd frontend && pnpm type-check`
- [ ] **同会话** integration + e2e 回归（AC8）
- [ ] 回写 `docs/technical_debt/test-infrastructure-residue-2026-09.md`：
  - 总览表增加「修复状态」列（TD-1/2/4/5 = 已修复，TD-3 = 按用户要求排除）
  - 各条目下追加「修复记录」小节：核实修正（TD-1 相似度数据、42 项而非 38 项）、实际改动、验证命令、提交哈希
  - TD-5 补充新发现（`settings.cache_ttl_*` 零消费）并记录处置决策
- [ ] 更新 spec（若适用）：`spec/backend/quality-guidelines.md` 增补「同一语义多副本」的测试侧案例
- [ ] 归档任务

---

## 验收映射表

| AC | 覆盖阶段 | 关键验证手段 |
|---|---|---|
| AC1 权限清单唯一 | 1 | `grep` 4 → 1 |
| AC2 漂移守护有效 | 1 | 新测试 + 反向验证 |
| AC3 WEBHOOK_SECRET 唯一 | 2 | `grep` 仅 1 处 |
| AC4 无 stdout 探针 | 3 | `grep` 计数为 0 |
| AC5 无硬编码 TTL | 4 | `grep setex` |
| AC6 无死配置条目 | 4 | `grep` + 人工核对 |
| AC7 全量全绿 | 6 | `pytest tests/ -q` ≥874 passed |
| AC8 同会话双层全绿 | 2 / 6 | `pytest tests/e2e/ tests/integration/ -q` |
| AC9 文档回写 | 6 | 文档 diff |
| AC10 死字段清除 | 5 | `grep cache_ttl_` 为 0 + Settings 实例化成功 |
| AC11 TTL 来源文档化 | 5 | cache-strategy.md 与 `_ttl_config` 逐条对照 |

---

## 子代理上下文清单（`implement.jsonl` / `check.jsonl` 用）

```jsonl
{"file": ".trellis/spec/backend/quality-guidelines.md", "reason": "测试隔离两条陷阱（模块级 from ... import 使属性替换失效；子层 conftest 不得覆盖 settings 单例）——R1/R3 的直接判据"}
{"file": ".trellis/spec/backend/logging-guidelines.md", "reason": "R4 将 stdout 探针改为 logger.error 的约定依据"}
{"file": ".trellis/spec/backend/database-guidelines.md", "reason": "测试库表结构与权限插入的既有先例"}
{"file": ".trellis/spec/guides/code-reuse-thinking-guide.md", "reason": "同一语义多副本的识别与收敛方法论（R1/R5 共用）"}
```
