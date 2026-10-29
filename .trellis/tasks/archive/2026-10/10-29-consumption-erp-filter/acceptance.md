# 验收边界与最终验证结果

## 目标

在「消耗分析」页筛选器新增「ERP系统」筛选项（字典取 `ErpSystem`，`value` 匹配
`Customer.erp_system`），贯通趋势图 / 客户排行 / 设备分布三个端点，并保证筛选
**真实生效**（Redis 缓存 key 纳入该参数）。

## 改动文件

| 文件 | 改动 |
|---|---|
| `backend/app/services/analytics.py` | 3 个方法（`get_consumption_trend_with_metric` / `get_top_customers_with_metric` / `get_device_type_distribution_with_metric`）新增 `erp_system` 参数与 `Customer.erp_system == erp_system` where |
| `backend/app/routes/analytics.py` | 3 个端点读 `erp_system` arg、透传 service、**cache_key 纳入**（共 9 处） |
| `frontend/src/api/analytics.ts` | 3 个 API 签名新增 `erp_system?: string` |
| `frontend/src/views/analytics/Consumption.vue` | filters 默认值、`erpSystemOptions`、ERP 字典加载、模板 `FilterDropdown`、`handleReset` 重置、3 个 load 函数拼参 |
| `backend/tests/integration/test_analytics_api.py` | 新增 4 个测试；**顺带修复既有缺陷**：`auth_token` fixture 签发 JWT 改用 `AuthService.create_access_token` |
| `.trellis/spec/backend/analytics-consumption-filters.md` | 新增跨层契约 spec（含缓存隔离测试正确写法） |

## 验证结果

| 验证项 | 命令 | 结果 |
|---|---|---|
| 后端 lint | `ruff check app/ tests/integration/test_analytics_api.py` | ✅ All checks passed |
| 后端类型 | `pyright app/routes/analytics.py app/services/analytics.py` | ✅ 0 errors |
| 后端全量测试 | `pytest tests/ -q` | ✅ **1392 passed, 0 failed** |
| 前端类型 | `pnpm type-check` | ✅ 通过 |
| 前端 lint | `eslint Consumption.vue analytics.ts` | ✅ No issues found |
| API 端到端 | curl 三端点 `erp_system=yiao` vs 无筛选 | ✅ trend 599,520.81→24,664.00；top 385,993.5→22,696；device 599,520.81→24,664；不存在值 → `[]` |
| 缓存隔离（真实 Redis） | 连续请求 yiao / dingjian / fangxin / yiao | ✅ 24,664 / 12,410 / 0 / 24,664 —— 无串味 |
| 浏览器 UI | 选择「易遨」→ 筛选 | ✅ 总消耗 ¥599,520.81→¥24,664.00；订单 47,583→3,083；活跃客户 100→19；最高客户 乐有家→濮阳金辉地产 |
| 浏览器 UI 重置 | 点击「重置」 | ✅ ERP系统 回「全部」，总消耗恢复 ¥599,520.81 |
| ERP 字典选项 | 展开下拉 | ✅ 全部/无/鼎尖/易遨/房信/房管家/好房通/上海梵讯/巧房/房融云/享/自研/房在线（13 项） |

## 测试有效性实证（关键）

缓存隔离测试不是「跑绿即信」。注入 bug（临时从 cache_key 删除 `:{erp_system}`）后：

- 单跑 → **FAILED**：`AssertionError: cache_key 必须包含 ERP 筛选值`
- 全量跑 → **FAILED**（1 failed, 31 passed）

还原后单跑与全量均 **32 passed**。证明该测试确实能捕获 cache_key 漏参缺陷。

## 后端全量测试（含澄清）

```
cd backend && .venv/bin/python -m pytest tests/ -q
================ 1392 passed, 456 warnings in 444.40s (0:07:24) ================
```

> 过程中曾出现一次 `16 failed, 276 errors` 的结果，根因是**两个 pytest 全量套件并行
> 争用同一个测试库**（`test_roles_api.py` 报 `auth_token: 用户 admin 无角色关联`，
> 即一个套件 TRUNCATE 掉 users 表、另一个套件的 session 级 fixture 读不到角色）。
> 与本次 ERP 改动无关。串行重跑后 1392 passed 0 failed，结论以此为准。
> **教训：本项目测试库不支持并行跑多份全量套件。**

## 顺带修复的既有缺陷

`test_analytics_api.py` 的 function 级 `auth_token` fixture 用
`os.environ.get("JWT_SECRET", "test-secret")` 自签 JWT，而中间件按
`settings.jwt_secret`（conftest setdefault 的 `test-secret-key`）验签 → 任何显式
请求 `db_session` 的测试都会 401 `Token 无效或已过期`。改为走
`AuthService.create_access_token` 统一 secret 来源，保留「超级管理员角色」的自签意图。
该文件原有 28 个测试不请求 `db_session` 故未触发，属于潜在雷区。
