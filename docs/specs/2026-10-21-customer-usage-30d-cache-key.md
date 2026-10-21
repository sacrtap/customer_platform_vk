# 修复客户列表「30天消耗」编辑后不显示（usage_30d 缓存 int/str key 不匹配）

## Context

客户管理页面（`views/customers/Index.vue`）中，点击某客户「编辑」改任意字段并关闭弹框后，列表「30天消耗」列部分客户不再显示，需刷新或重进页面才恢复；改「运营经理(manager_id)」最稳定复现。

**根因**：后端列表接口 `GET /customers` 的近30天消耗数据走独立缓存 `customer_usage_30d`（`routes/customers.py:192-230`）。缓存写入时 `usage_map` 的顶层 key 是 `int`（`row.customer_id`，line 225），但 `CacheService` 走 Redis 时用 `json.dumps`/`json.loads` 序列化（`cache/base.py:108-109,138`），JSON object 的 key 被强制转为 `str`。读取命中后 line 276 `usage_map.get(c.id, {})` 用 `int` 去查 `str-key` dict，永远命中默认 `{}` → `order_count=0` → `usage_30d=0`。前端 `CustomerTable.vue:112` 渲染条件 `record.usage_30d != null && record.usage_30d > 0`，0 即不显示。

**触发链**：进入页面 → usage 缓存未命中 → 重查 int-key map → 正常显示 → 写缓存（int→json→str）。编辑客户 → `update_customer` 调 `invalidate_customer_cache`（`base.py:186-199`）清 `customer_list:*` 但**不清 `customer_usage_30d:*`** → `handleSearch`（`useCustomerList.ts:192`，不带 force_refresh）→ customer_list 失效走 DB → **命中 str-key usage 缓存** → int/str 不匹配 → usage_30d=0 → 不显示。usage 缓存 TTL 300s 过期后重查 int-key 才恢复。所有字段编辑都会触发（都走 `update_customer`→清 customer_list→走 DB 命中 usage 缓存）；manager_id 在默认列表下不改变 customer_ids，稳定命中旧 str-key 缓存，故最稳定。

**已实证**：Python 模拟 `{123: {...}}` 经 `json.dumps`+`json.loads` 后 key 变 `'123'`，`get(123)` 返回 0（不显示），`get('123')` 返回真实值（显示）。

**测试盲区**：`tests/integration/test_customers_api.py:129-134` 的 `fake_get` 直接返回 int-key 的 Python dict，绕过 JSON 序列化，故 `test_list_customers_usage_30d_cache_hit` 通过却未捕获此 bug。

## Approach

### 1. 主修复：缓存命中时归一化 usage_map 顶层 key 为 int

文件 `backend/app/routes/customers.py`，`list_customers` 内 line 199-200：

当前：
```python
        if cached_usage is not None:
            usage_map = cached_usage
```
改为：
```python
        if cached_usage is not None:
            # Redis 经 json.dumps/json.loads 序列化后 dict 顶层 key 由 int 变 str，
            # 而 line 276/286 用 c.id(int) 查询会失配 → usage_30d 退化为 0。
            # 归一化顶层 key 回 int，保持与 c.id 类型一致。
            usage_map = {int(k): v for k, v in cached_usage.items()}
```

- 单点修复，下游 line 276 `usage_map.get(c.id, {}).get("order_count", 0)`、line 277 `...get("total_cost", 0.0)`、line 286 健康度 `usage_map.get(c.id, {}).get("order_count", 0) == 0` 全部用 int 查 int，自动正确，无需再改。
- value 内层 dict（`{"order_count","total_cost"}`）的 key 本就是 str、用 str 查，不受影响，仅归一化顶层 customer_id key。
- 缓存未命中走 line 201-228 重查分支时 `usage_map` 顶层 key 仍为 int（`row.customer_id`），与归一化后一致，无回归。

### 2. 回归测试：用真实 JSON 序列化路径复现 str-key 命中

文件 `backend/tests/integration/test_customers_api.py`，改造现有 `test_list_customers_usage_30d_cache_hit`（line 118-161）的 `fake_get`，使其返回**经 `json.dumps`/`json.loads` 的 dict**（str key），模拟真实 Redis 行为：

当前 line 132-133：
```python
        if namespace == "customer_usage_30d":
            return {customer_id: {"order_count": 7, "total_cost": 88.5}}
```
改为：
```python
        if namespace == "customer_usage_30d":
            # 模拟真实 Redis：CacheService.set 走 json.dumps、get 走 json.loads，
            # int 顶层 key 会被序列化为 str。直接复刻该序列化路径。
            import json
            return json.loads(json.dumps({customer_id: {"order_count": 7, "total_cost": 88.5}}))
```

- 修复前：line 160 `assert item["usage_30d"] == 7` 失败（实际 0，因 str-key 命中 + int 查询失配）→ 测试转红，暴露 bug。
- 修复后：归一化使 `get(int)` 命中 → `usage_30d == 7`、`usage_30d_amount == 88.5` → 通过。
- 其余断言（usage_get 调用 1 次、usage_set 调用 0 次）不变。

## Critical files & anchors

- `backend/app/routes/customers.py:199-200` — 主修复点：usage 缓存命中后归一化顶层 key 为 int（标签 `#5979`）。
- `backend/app/cache/base.py:108-109,138` — 根因机制：`get` 走 `json.loads`、`set` 走 `json.dumps`，使 int key 变 str；此处不改，仅作理解依据。
- `backend/tests/integration/test_customers_api.py:129-134` — 测试盲区：`fake_get` 返回 int-key dict 绕过序列化；改造为 str-key 以复现（标签 `#D639`）。
- `frontend/src/views/customers/components/CustomerTable.vue:110-120` — 前端渲染条件 `usage_30d > 0` 才显示，确认 0 即消失（不改）。
- `backend/app/cache/base.py:186-199` — `invalidate_customer_cache` 不清 `customer_usage_30d:*`，是触发条件（不改，见 Assumptions）。

## Verification

### 自动化（修复前后对照）
前置：`backend/.venv` 已就绪，能连本地 Redis（`redis://localhost:6379/0`，已确认 `PONG`）。
```bash
cd backend
.venv/bin/pytest tests/integration/test_customers_api.py -k usage_30d_cache_hit -xvs
```
- 修复前（仅做测试改造、不做主修复）：该用例 `assert item["usage_30d"] == 7` 失败，实际为 0，复现 bug。
- 主修复后：该用例通过（usage_30d==7、usage_30d_amount==88.5）。
- 全量回归：`.venv/bin/pytest tests/integration/test_customers_api.py -x` 无回归。

### 手动端到端（用户原始路径）
1. 启动后端（`backend`，默认 8000）与前端（`frontend`，`npm run dev`）。
2. 登录进入「客户管理」页，确认「30天消耗」列正常显示（首次访问写入 usage 缓存，int→str）。
3. 任选一客户点「编辑」，把「运营经理」改为任意值，点保存关闭弹框。
4. 不刷新，观察列表「30天消耗」列：修复前该列（有消耗的客户）退化为空；修复后保持正常显示。
5. 额外验证：再编辑「名称」等其他字段，确认任意字段编辑后均不再丢失「30天消耗」。

## Assumptions & contingencies

- **主修复已根治显示问题**：归一化后缓存命中也返回正确值，编辑后立即正确显示，无需等待 TTL。若手动验证仍出现编辑后丢失，优先确认改动是否落在 line 199-200 且 `cached_usage` 非空分支（用日志打印 `type(next(iter(cached_usage)))` 应为 `str`、归一化后 `int`）。
- **不纳入的关联增强（可选，需用户确认）**：`invalidate_customer_cache`（base.py:196）不清 `customer_usage_30d:*`、`force_refresh`（customers.py:198）不跳过 usage 缓存读取——这两处是同缓存层的语义缺陷。本计划不修，因主修复后缓存命中即正确，不影响显示；若日后希望「编辑后即时失效 usage 缓存」或「数据刷新按钮强制重查 usage」，再单独处理，避免扩大本次范围。
- 前端无需改动：`handleSearch`(整体 reload) 与渲染条件均正确，问题完全在后端缓存 key 类型。

## 实施结果（2026-10-21，分支 `fix/customer-usage-30d-cache-key`）

- **主修复已落地**：`backend/app/routes/customers.py:199-203`，缓存命中分支归一化顶层 key 为 int（`usage_map = {int(k): v for k, v in cached_usage.items()}`）。
- **回归测试已落地**：`backend/tests/integration/test_customers_api.py` 的 `fake_get` 改为经 `json.loads(json.dumps(...))` 复刻真实 Redis 序列化路径。
- **验收边界**：仅改上述两个文件；修复范围为「30天消耗」编辑后显示问题，不含 `invalidate_customer_cache` 未清 usage 缓存等关联增强。
- **验证结果**：
  - 修复前（仅测试改造）：`pytest tests/integration/test_customers_api.py -k usage_30d_cache_hit` 失败，`assert item["usage_30d"] == 7` 实际为 0，复现 bug。
  - 修复后：该用例通过（`usage_30d == 7`、`usage_30d_amount == 88.5`）。
  - `tests/integration/test_customers_api.py` 全量回归：**63 passed**（77.93s，无回归）。
- **手动端到端**：由用户在真实环境（后端 8000 + 前端 dev）按上述步骤 2–5 复核；代码路径已由集成测试覆盖等价场景。
