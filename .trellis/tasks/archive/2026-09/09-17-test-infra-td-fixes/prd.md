# 测试基础设施遗留项修复（TD-1/2/4/5）

## Goal

核实并修复 `docs/technical_debt/test-infrastructure-residue-2026-09.md` 中 **TD-1、TD-2、TD-4、TD-5** 四项遗留问题（TD-3 按用户要求排除），消除其中的重复副本与死配置，并在该文档中回写修复状态。

---

## Background（核实结论，2026-09-17）

四项**全部属实**，但 TD-1 与 TD-5 的文档描述需修正：

### TD-1（P2）结构性重复 —— 部分成立，且文档低估了范围

逐 fixture 相似度实测：

| fixture | e2e 行 | integration 行 | 相似度 | 判定 |
|---|---|---|---|---|
| `test_user` | 146 | 193 | 84% | 真重复 |
| `mock_cache` | 97 | 81 | 83% | 真重复（有实差） |
| `mock_scheduler` | 12 | 10 | 91% | 真重复 |
| `app` | 25 | 33 | 76% | 真重复 |
| `test_client` | 5 | 6 | 55% | 近重复 |
| `sync_test_engine` | 8 | 69 | **13%** | **本质不同** |
| `db_session` | 17 | 46 | **29%** | **本质不同** |

- 文档称「e2e 基本是 integration 的副本」「实质差异仅在 `test_client`」——**不准确**，`sync_test_engine` 与 `db_session` 差异极大；
- 文档称 `test_user` 含「38 项权限清单」——实为 **42 项**；
- **文档未提及的最大重复源**：该 42 项权限清单在 **4 处逐字重复**（已实测四份**完全一致**，同序）：

| 位置 | 行范围 |
|---|---|
| `tests/integration/conftest.py` `test_user` | 214–255 |
| `tests/integration/conftest.py` `mock_cache` 的 `FULL_PERMISSIONS` | 442–483 |
| `tests/e2e/conftest.py` `test_user` | 109–150 |
| `tests/e2e/conftest.py` `mock_cache` 的 `FULL_PERMISSIONS` | 265–306 |

- 第 5 个来源：`backend/scripts/seed.py` 的 `ALL_PERMISSIONS`（**48 条、4 元组含 description**，与测试侧 **3 元组 42 条形状不同**，非同源可直替）。

### TD-2（P3）`WEBHOOK_SECRET` 同型隐患 —— 完全成立

- `settings.webhook_secret` 为 `Field(default_factory=lambda: os.getenv("WEBHOOK_SECRET") or token_urlsafe(32))`，而 `settings` 是 `lru_cache` 模块级单例 → **最后加载者胜出**；
- integration:20 与 e2e:17 各自强制设置**不同**值；
- 唯一消费点 `app/routes/webhooks.py:151`（请求期读取）；
- integration/e2e 下**确无**任何 webhook 测试 → 当前无行为暴露，但与已修的 `JWT_SECRET` 401 缺陷同型。

### TD-4（P3）`[DEBUG]` 探针 —— 完全成立

`tests/integration/conftest.py` 的 `test_user` 内 8 处 `sys.stdout.write("[DEBUG] ...")` + `sys.stdout.flush()`（行 176/180/188/197/209/306/318/331）。另有 1 处 `[ERROR]`（行 314）。全仓仅此文件存在此类探针。

### TD-5（P3）实现钉死型断言 —— 成立，且问题比文档所述更严重

`tests/test_cache.py:48` `test_init_default_ttl_config` 断言整个 `_ttl_config`（20 条目）字典。核实发现：

1. **`billing_pricing_rules`（3600）零消费**：`grep` 全仓仅出现在 `app/cache/base.py:42` 与测试断言中，无任何代码使用该前缀 → **死配置**；
2. **`billing_consumption` 是死配置**：`app/routes/billing/balances.py:47,87` 手工拼键 `f"cache:billing_consumption:{cid}:{today_str}"`，并以**硬编码 `pipe.setex(key, 300, val)`** 写缓存——从未查 `_ttl_config`。即配置里的 `300` 与硬编码 `300` 是**同一语义的两个副本**（本次已修复的同型问题）；
3. **`app/config.py:79-88` 的 9 个 `settings.cache_ttl_*` 字段生产读取 0 次**——第三份 TTL 语义副本，且被 `.env.example:133-157` 与 `docs/performance/cache-strategy.md` 当作运维可配项文档化（**照文档配置不生效**）。
4. 行为层覆盖情况：`setex` 断言已覆盖 `customer_list`/`customer_detail`/`tag_list`/`tag_stats`/`analytics` + 自定义 TTL + 未知前缀回退 `default`；**未覆盖**的是其余十多个条目（含两个死条目）。

---

## Requirements

### R1（TD-1）权限清单收敛为单一常量

- 新建 `backend/tests/_test_data.py`（下划线前缀，避免被 `python_files = test_*.py` 收集），导出：
  - `PERMISSION_ROWS: list[tuple[str, str, str]]` —— `(code, name, module)`，用于 DB 插入；
  - `PERMISSION_CODES: frozenset[str]` —— **由 `PERMISSION_ROWS` 派生**，用于 mock 权限缓存。
- 上述 4 处逐字副本全部改为导入该模块；`PERMISSION_CODES` 必须由行数据派生，使两份数据**结构上不可能漂移**。
- **不抽取** `sync_test_engine` / `db_session` / `mock_cache` / `app` / `test_user` 主体（差异过大，风险高于收益）。

### R2（TD-1 附加）权限清单与种子数据的漂移守护

- 新增一条测试：断言 `PERMISSION_CODES` ⊆ `scripts/seed.py::ALL_PERMISSIONS` 的 code 集合。
- 理由：测试权限与种子权限是同一语义的两个副本，漂移会导致「测试全绿但生产角色缺权限」——正是本类缺陷。
- `scripts` 已是包（含 `__init__.py`），`seed.py` 仅在 `__main__` 下执行，**导入无副作用**（已核实）。

### R3（TD-2）`WEBHOOK_SECRET` 收敛到基线

- `tests/conftest.py` 增加 `os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret-key")`（与既有 `JWT_SECRET` 的 `setdefault` 写法一致）；
- 删除 `tests/integration/conftest.py:19-20` 与 `tests/e2e/conftest.py:16-17` 的强制赋值及相应注释。

### R4（TD-4）移除 stdout 探针

- 删除 8 处 `[DEBUG]` 的 `sys.stdout.write` + `sys.stdout.flush()`；
- 1 处 `[ERROR]` 改为 `logger.error(...)`（保留失败可见性，符合 `.trellis/spec/backend/logging-guidelines.md`）；
- 清理因此不再使用的 `import sys`（该 fixture 内的局部导入）。

### R5（TD-5）TTL 配置单一真相

- `CacheService` 新增公开方法 `ttl_for(prefix: str) -> int`；`set()` 内部改为调用它；
- `_ttl_config` 移除零消费的 `billing_pricing_rules`；
- `app/routes/billing/balances.py:87` 的硬编码 `300` 改为引用 `cache_service.ttl_for("billing_consumption")`（消除同语义副本）；
- `tests/test_cache.py::test_init_default_ttl_config` 的整字典断言**替换**为 `ttl_for` 行为断言（含未知前缀回退 `default`），不再钉住实现。

### R6（Q1 新发现，用户批准纳入）清理零消费的 `settings.cache_ttl_*`

- `app/config.py:79-88`：删除 9 个 `cache_ttl_*` 字段（连同 `# 缓存 TTL 配置 (秒)` 注释）；
- `.env.example:130-157`：删除对应的说明注释块与被注释的 9 行环境变量；
- `docs/performance/cache-strategy.md:47-57`：删除误导性配置表格，改写为指向 `CacheService._ttl_config`（TTL 的唯一真实来源）；
- **安全依据（已实测，非推断）**：`pydantic-settings 2.1.0` 的 `BaseSettings.model_config['extra'] = 'forbid'`，但该 `extra` **仅约束 init 参数**；环境变量由 `EnvSettingsSource` 按字段名映射，**未知环境变量被忽略**。实测在 `os.environ['UNKNOWN_EXTRA_FIELD']='abc'` 下实例化 Settings 不报错 → 运维 `.env` 中遗留 `CACHE_TTL_*` 不会导致启动失败；
- 全仓核实：`.env`、`deploy/` 均未设置这些变量；`.env.example` 中仅为注释行。

---

## Acceptance Criteria

- [ ] **AC1**：`grep -c '("customers:view", "查看客户", "customers")' tests/` 结果由 4 → **1**（仅 `_test_data.py`）；`grep -A2 'FULL_PERMISSIONS = {'` 两处均为从常量派生而非字面量列表
- [ ] **AC2**：新增的漂移守护测试存在且在全量套件中通过；将 `_test_data.py` 中任一 code 改成 seed 未定义的值时，该测试**必须失败**（反向验证）
- [ ] **AC3**：`grep -rn 'WEBHOOK_SECRET' tests/` 仅剩 `tests/conftest.py` 一处 `setdefault`
- [ ] **AC4**：`grep -c 'sys.stdout' tests/integration/conftest.py` 为 **0**；`grep -c '\[DEBUG\]' tests/integration/conftest.py` 为 **0**
- [ ] **AC5**：`grep -n 'setex' app/routes/billing/balances.py` 不再含硬编码字面量（改为 `ttl_for` 调用）
- [ ] **AC6**：`_ttl_config` 每个 key 均有真实消费点（`billing_pricing_rules` 已移除；`billing_consumption` 经 `ttl_for` 被 balances 使用）
- [ ] **AC7**：`pytest tests/ -q` 全绿，通过数不低于既有基线（**874 passed**，覆盖率 ≥50%）
- [ ] **AC8**：**同会话** `pytest tests/e2e/ tests/integration/ -q` 全绿（TD-2 的验证点）
- [ ] **AC9**：`docs/technical_debt/test-infrastructure-residue-2026-09.md` 中 TD-1/2/4/5 已回写修复状态（含提交哈希与验证命令）
- [ ] **AC10**：`grep -rn "cache_ttl_" backend/app/ --include=*.py` 为 **0**；`.env.example` 与 `docs/performance/cache-strategy.md` 不再把 `CACHE_TTL_*` 描述为可配项；`docs/party-mode-memories/` 等历史记录不改（并在文档中说明理由）
- [ ] **AC11**：TTL 的唯一真实来源被明确定位为 `CacheService._ttl_config` + `ttl_for()`，且 `docs/performance/cache-strategy.md` 的配置说明与之相符（含 `billing_consumption` 条目、不含已删的 `billing_pricing_rules`）

---

## Resolved Decisions

1. **TD-3 排除**：用户明确要求（`.trellis/scripts` 的 6 处直接写入不在本次范围）。
2. **TD-1 取窄范围**：仅提取 4 份重复的权限清单；完整 fixture 抽取因 `sync_test_engine`(13%)、`db_session`(29%) 本质不同而**不做**。
3. **TD-5 取彻底处置**：替换断言 + 清死配置 + 修硬编码（用户确认）。
4. **TD-2/TD-4 按文档建议方案执行**。
5. **Q1 纳入本次（用户选 A）**：删除 `app/config.py` 的 9 个零消费 `cache_ttl_*` 字段，并同步清理 `.env.example` 与 `docs/performance/cache-strategy.md` 的误导性文档。
   - **安全依据（已实测）**：`extra='forbid'` 仅约束 init 参数；未知环境变量被 `EnvSettingsSource` 忽略 → 删除字段不会导致既有部署启动失败（详见 R6）。

## Open Questions

（无 —— Q1 已由用户决策闭合。）

## Notes

- 本次为**测试基础设施 + 缓存配置**改动，已按复杂度准备 `design.md` 与 `implement.md`。
- 相关 spec：`.trellis/spec/backend/quality-guidelines.md`（测试隔离两条陷阱）、`.trellis/spec/backend/logging-guidelines.md`（日志约定）、`.trellis/spec/backend/database-guidelines.md`。
- 基线：`pytest tests/ -q` → 874 passed；`tests/e2e/ + tests/integration/` 同会话 → 246 passed（见技术债文档「附」节）。
