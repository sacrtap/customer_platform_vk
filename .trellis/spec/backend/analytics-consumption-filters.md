# Analytics 消耗分析筛选契约

> 消耗分析页（`/analytics/consumption`）多维度筛选的跨层契约。新增筛选项时必须同步
> 四个位置，否则出现「筛选似生效但数据不变」。

## Scope / Trigger

- 触发：消耗分析页新增/修改筛选项
- 涉及端点：`/consumption/trend`、`/consumption/top`、`/consumption/device-distribution`
  （该页筛选器为**三者共用**，见 `Consumption.vue` 注释「统一筛选（趋势图 + 设备分布 + 客户排行共用）」）
- 既有筛选项：时间范围、关键词、账号类型、行业、规模等级、消费等级、运营经理、销售经理、ERP系统

## 四处必须同步（漏一处即缺陷）

| 层 | 文件 | 内容 |
|---|---|---|
| 1 前端筛选态 | `frontend/src/views/analytics/Consumption.vue` | `createDefaultFilters()` 加字段 + `handleReset()` 重置 + 模板 `FilterDropdown` + 字典 ref/加载函数/`onMounted` 调用 |
| 2 前端 API 签名 | `frontend/src/api/analytics.ts` | `getConsumptionTrend` / `getTopCustomers` / `getDeviceDistribution` 三个函数签名加参数 |
| 3 路由 | `backend/app/routes/analytics.py` | 读 `request.args.get(...)` → 透传 service → **cache_key 纳入** |
| 4 服务 | `backend/app/services/analytics.py` | `get_consumption_trend_with_metric` / `get_top_customers_with_metric` / `get_device_type_distribution_with_metric` 加参数 + `stmt.where(...)` |

## 缓存 key 陷阱（最关键）

三个端点均有 Redis 缓存，namespace 分别为 `analytics_consumption_trend` /
`analytics_top_customers` / `analytics_device_distribution`（TTL 900s）。

**新增筛选参数若不纳入 cache_key，切筛选值后会命中上一次筛选的缓存**，表现为：
UI 显示已选新值、网络请求已发出、但返回数据与上一次完全相同。这是本类需求最
高发的假生效 bug。

三个 cache_key 均为 f-string 拼接，`erp_system` 插在 `consume_level` 与 `manager_id` 之间：

```python
cache_key = f"{start_date}:{end_date}:{cid}:{account_type}:{industry}:{scale_level}:{consume_level}:{erp_system}:{manager_id}:{sales_manager_id}:scope:{scope_user_id or 'all'}"
```

> 注：`top` 端点的 key 在前面多 `{limit}:{metric}:{keyword}`，结构不同，勿盲目复制。

## ERP 系统筛选取值口径

- 存储：`Customer.erp_system`（`String(100)`），存 **`ErpSystem.value`**（如 `yonyou`/`kingdee`），**不是 name**
- 字典：`GET /api/v1/erp-systems` → `[{id, name, value, sort_order, created_at}]`
- 前端选项：`label = es.name`，`value = es.value`（与客户管理页/余额管理页/结算单页完全一致）
- 后端匹配：`stmt.where(Customer.erp_system == erp_system)` 精确等值
- 三个 service 查询**均已 join `Customer`**（`DailyConsumption.customer_id == Customer.id`），
  故只需追加 where，**无需新增 join**；也不要放进 `if industry or scale_level or consume_level:`
  的 CustomerProfile join 守卫块内（ERP 字段在 Customer 表，不在 CustomerProfile）

## 空值与不存在值

| 输入 | 行为 |
|---|---|
| 空串 / 缺失 | 不加 where，返回全量（前端用 `filters.x \|\| undefined` 不拼参） |
| 不存在的 value | 结果为空列表（非报错）；device-distribution 返回 `[]`，trend/top 返回 `[]` |

## 数据可见性

`mine_user_id` scope 约束（服务端强制，无 `customers:view_all` 时仅统计当前用户负责的客户）
与 ERP 筛选是叠加关系：ERP 只是在 scope 之上再追加 where。scope 已并入 cache_key
（`scope:{scope_user_id or 'all'}` 后缀），新增筛选不要破坏该后缀。

## Validation & Error Matrix

| 场景 | 预期 |
|---|---|
| `?erp_system=yiao` | 仅返回 erp_system=yiao 的客户的消耗 |
| `?erp_system=`（空串） | 全量 |
| `?erp_system=nonexistent` | `[]` |
| 连续请求不同 erp_system | 各自返回各自数据（缓存不串味） |

## Tests Required

`backend/tests/integration/test_analytics_api.py`：

- `test_consumption_trend_filter_erp_system` — 命中/不存在值/全量对比
- `test_top_customers_filter_erp_system` — 按 customer_id 断言命中与排除
- `test_device_distribution_filter_erp_system` — 命中/不存在值
- `test_consumption_trend_erp_system_cache_isolation` — **断言 cache_key 含筛选值**

### 缓存隔离测试的正确写法（踩坑记录）

**不要**依赖 `mock_cache` fixture 替换全局 `base.cache_service` 来捕获 key：

1. `routes/analytics.py` 是 `from ..cache.base import cache_service` 的**模块级绑定**。
   若该模块在 fixture 替换全局之后被重新导入，请求会打到未 mock 的真实实例，
   捕获不到任何调用（表现为全量跑时 `mock_cache.set.call_args_list == []`，单跑却正常）。
2. 也不要做「端到端命中断言」：测试环境无 Redis，真实 `cache_service.get()` 遇连接
   异常会**静默返回 None**（异常被 `except` 吞掉只打 warning），永远"未命中"，
   无法暴露 cache_key 漏参缺陷。

**正确写法**：测试内 patch 路由模块的 cache_service，并断言 `set` 收到的 key。

```python
spy_cache = MagicMock()
spy_cache.get = AsyncMock(return_value=None)   # 永不命中，确保每次都写缓存
spy_cache.set = AsyncMock(return_value=True)
original = analytics_routes.cache_service
analytics_routes.cache_service = spy_cache
try:
    ...
    # cache_service.set(prefix, data, key) → key 是第三个位置参数
    trend_keys = [c.args for c in spy_cache.set.call_args_list
                  if c.args and c.args[0] == "analytics_consumption_trend"]
    assert any("yonyou" in str(a) for a in trend_keys[-1][2:])
finally:
    analytics_routes.cache_service = original
```

**有效性必须实证**：改好后注入 bug（临时从 cache_key 删掉 `:{erp_system}`）确认测试
FAILED，再还原确认 PASSED。只跑通过不注入验证，无法证明测试真的能捕获缺陷。
