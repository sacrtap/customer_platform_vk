# 余额管理筛选项对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将余额管理页面的列表筛选项与客户管理页面对齐，添加「房产客户」和「结算方式」两个筛选项。

**Architecture:** 前端在 `Balance.vue` 添加两个筛选项 UI，通过 `getBalances` API 传递新参数；后端在 `billing.py` 路由中解析新参数并添加对应的 `where` 条件。

**Tech Stack:** Vue 3 + Arco Design + TypeScript (前端), Python + Sanic + SQLAlchemy (后端)

## Global Constraints

- 数据库事务：所有修改操作必须在 `async with db_session.begin():` 块内执行
- 权限校验：所有 API 端点必须添加 `@auth_required` 装饰器
- 测试覆盖率：CI 要求测试覆盖率 ≥50%
- Python 版本：必须使用 Python 3.12.x
- 向后兼容：新增参数为可选，不影响现有功能

---

## File Structure

### 修改文件
| 文件 | 职责 |
|------|------|
| `frontend/src/views/billing/Balance.vue` | 添加筛选项 UI，更新 filters 对象和 loadBalances 方法 |
| `frontend/src/api/billing.ts` | 扩展 getBalances 参数类型 |
| `backend/app/routes/billing.py` | 解析新筛选参数，添加查询条件 |

### 测试文件
| 文件 | 职责 |
|------|------|
| `backend/tests/integration/test_billing_api.py` | 后端 API 集成测试 |

---

## Task 1: 后端 API 扩展筛选参数

**Files:**
- Modify: `backend/app/routes/billing.py:32-100` (get_balances 函数)
- Test: `backend/tests/integration/test_billing_api.py`

**Interfaces:**
- Consumes: 现有 get_balances API 结构
- Produces: 支持 `is_real_estate` 和 `settlement_type` 参数的筛选功能

- [ ] **Step 1: 编写后端测试**

在 `backend/tests/integration/test_billing_api.py` 中添加测试：

```python
@pytest.mark.asyncio
async def test_get_balances_filter_is_real_estate(test_client, auth_headers, db_session):
    """测试余额列表按房产客户筛选"""
    from sqlalchemy import text
    
    # 清理已有数据
    db_session.execute(text("DELETE FROM customer_balances"))
    db_session.execute(text("DELETE FROM customers"))
    
    # 创建测试客户
    customers = [
        {"name": "房产客户A", "is_real_estate": True},
        {"name": "非房产客户B", "is_real_estate": False},
    ]
    for cust in customers:
        db_session.execute(text("""
            INSERT INTO customers (company_id, name, account_type, is_real_estate, created_at)
            VALUES (:company_id, :name, '正式账号', :is_real_estate, NOW())
        """), {"company_id": f"TEST{cust['name']}", "name": cust["name"], "is_real_estate": cust["is_real_estate"]})
    
    # 创建余额记录
    db_session.execute(text("""
        INSERT INTO customer_balances (customer_id, total_amount, used_total, created_at)
        SELECT id, 1000.0, 0.0, NOW() FROM customers WHERE name LIKE '房产客户%' OR name LIKE '非房产客户%'
    """))
    await db_session.commit()
    
    # 测试筛选 is_real_estate=true
    response = await test_client.get("/api/v1/billing/balances?is_real_estate=true", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "房产客户" in data["items"][0]["customer_name"]
    
    # 测试筛选 is_real_estate=false
    response = await test_client.get("/api/v1/billing/balances?is_real_estate=false", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "非房产客户" in data["items"][0]["customer_name"]


@pytest.mark.asyncio
async def test_get_balances_filter_settlement_type(test_client, auth_headers, db_session):
    """测试余额列表按结算方式筛选"""
    from sqlalchemy import text
    
    # 清理已有数据
    db_session.execute(text("DELETE FROM customer_balances"))
    db_session.execute(text("DELETE FROM customers"))
    
    # 创建测试客户
    customers = [
        {"name": "预付费客户A", "settlement_type": "prepaid"},
        {"name": "后付费客户B", "settlement_type": "postpaid"},
    ]
    for cust in customers:
        db_session.execute(text("""
            INSERT INTO customers (company_id, name, account_type, settlement_type, created_at)
            VALUES (:company_id, :name, '正式账号', :settlement_type, NOW())
        """), {"company_id": f"TEST{cust['name']}", "name": cust["name"], "settlement_type": cust["settlement_type"]})
    
    # 创建余额记录
    db_session.execute(text("""
        INSERT INTO customer_balances (customer_id, total_amount, used_total, created_at)
        SELECT id, 1000.0, 0.0, NOW() FROM customers WHERE name LIKE '预付费%' OR name LIKE '后付费%'
    """))
    await db_session.commit()
    
    # 测试筛选 prepaid
    response = await test_client.get("/api/v1/billing/balances?settlement_type=prepaid", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "预付费" in data["items"][0]["customer_name"]
    
    # 测试筛选 postpaid
    response = await test_client.get("/api/v1/billing/balances?settlement_type=postpaid", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "后付费" in data["items"][0]["customer_name"]
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && pytest tests/integration/test_billing_api.py::test_get_balances_filter_is_real_estate tests/integration/test_billing_api.py::test_get_balances_filter_settlement_type -v
```

Expected: FAIL - 筛选参数未实现，返回所有客户

- [ ] **Step 3: 实现后端筛选逻辑**

在 `backend/app/routes/billing.py` 的 `get_balances` 函数中添加参数解析和筛选条件：

```python
# 在 is_key_customer 参数解析后添加（约第 69 行后）
is_real_estate = request.args.get("is_real_estate")
if is_real_estate is not None and is_real_estate.strip() != "":
    if is_real_estate.lower() not in ("true", "false"):
        return json(
            {"code": 40001, "message": "is_real_estate 参数必须为 'true' 或 'false'"},
            status=400,
        )
    is_real_estate = is_real_estate.lower() == "true"

settlement_type = request.args.get("settlement_type")
```

```python
# 在现有筛选条件后添加（约第 102 行后，industry 筛选之后）
if is_real_estate is not None:
    base_stmt = base_stmt.where(Customer.is_real_estate == is_real_estate)

if settlement_type:
    base_stmt = base_stmt.where(Customer.settlement_type == settlement_type)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && pytest tests/integration/test_billing_api.py::test_get_balances_filter_is_real_estate tests/integration/test_billing_api.py::test_get_balances_filter_settlement_type -v
```

Expected: PASS

- [ ] **Step 5: 提交后端改动**

```bash
git add backend/app/routes/billing.py backend/tests/integration/test_billing_api.py
git commit -m "feat(billing): add is_real_estate and settlement_type filters to balance API"
```

---

## Task 2: 前端 API 类型扩展

**Files:**
- Modify: `frontend/src/api/billing.ts:19-33`

**Interfaces:**
- Consumes: 现有 getBalances API
- Produces: 扩展后的参数类型定义

- [ ] **Step 1: 扩展 getBalances 参数类型**

在 `frontend/src/api/billing.ts` 中修改 `getBalances` 函数：

```typescript
export function getBalances(params?: {
  customer_id?: number
  keyword?: string
  account_type?: string
  industry?: string
  manager_id?: number
  sales_manager_id?: number
  recharge_date_from?: string
  recharge_date_to?: string
  tag_ids?: string
  is_key_customer?: boolean
  is_real_estate?: boolean      // 新增
  settlement_type?: string      // 新增
  page?: number
  page_size?: number
}) {
  return api.get('/billing/balances', { params })
}
```

- [ ] **Step 2: 提交前端 API 改动**

```bash
git add frontend/src/api/billing.ts
git commit -m "feat(api): extend getBalances params with is_real_estate and settlement_type"
```

---

## Task 3: 前端筛选项 UI 实现

**Files:**
- Modify: `frontend/src/views/billing/Balance.vue:34-98` (筛选区域), `frontend/src/views/billing/Balance.vue:509-525` (filters 定义), `frontend/src/views/billing/Balance.vue:650-700` (loadBalances 方法)

**Interfaces:**
- Consumes: 扩展后的 getBalances API
- Produces: 完整的筛选项 UI 和交互逻辑

- [ ] **Step 1: 更新 filters 对象**

在 `frontend/src/views/billing/Balance.vue` 中修改 `createDefaultFilters` 函数（约第 509 行）：

```typescript
const createDefaultFilters = () => ({
  keyword: '',
  recharge_date: [] as string[],
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  account_type: '正式账号',
  is_key_customer: null as boolean | null,
  is_real_estate: null as boolean | null,      // 新增
  settlement_type: null as string | null,      // 新增
})
```

- [ ] **Step 2: 添加筛选项 UI**

在 `frontend/src/views/billing/Balance.vue` 的筛选区域（约第 82-88 行，重点客户筛选项之后）添加两个新筛选项：

```vue
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="房产客户">
              <a-select v-model="filters.is_real_estate" placeholder="请选择" allow-clear>
                <a-option :value="true">是</a-option>
                <a-option :value="false">否</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="结算方式">
              <a-select v-model="filters.settlement_type" placeholder="请选择" allow-clear>
                <a-option value="prepaid">预付费</a-option>
                <a-option value="postpaid">后付费</a-option>
              </a-select>
            </a-form-item>
          </a-col>
```

- [ ] **Step 3: 更新 loadBalances 方法传递新参数**

找到 `loadBalances` 方法（约第 650 行），在构建 params 对象时添加新参数：

```typescript
const params = {
  keyword: filters.keyword || undefined,
  account_type: filters.account_type || undefined,
  industry: filters.industry.length > 0 ? filters.industry.join(',') : undefined,
  is_key_customer: filters.is_key_customer ?? undefined,
  is_real_estate: filters.is_real_estate ?? undefined,      // 新增
  settlement_type: filters.settlement_type || undefined,    // 新增
  // ... 其他现有参数
}
```

- [ ] **Step 4: 更新 handleReset 方法**

找到 `handleReset` 方法，确保重置新字段：

```typescript
const handleReset = () => {
  Object.assign(filters, createDefaultFilters())
  // ... 其他重置逻辑
}
```

注意：由于使用 `createDefaultFilters()` 工厂函数，新字段会自动被重置。

- [ ] **Step 5: 运行前端测试（如有）**

```bash
cd frontend && npm run test -- --run Balance
```

Expected: 无相关测试失败（或无测试）

- [ ] **Step 6: 提交前端 UI 改动**

```bash
git add frontend/src/views/billing/Balance.vue
git commit -m "feat(balance): add is_real_estate and settlement_type filter UI"
```

---

## Task 4: 集成验证

**Files:**
- 无新增文件

**Interfaces:**
- Consumes: Task 1-3 的所有改动
- Produces: 验证通过的可工作功能

- [ ] **Step 1: 启动后端服务**

```bash
cd backend && make run
```

- [ ] **Step 2: 启动前端服务**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: 手动验证筛选项功能**

1. 访问余额管理页面
2. 验证「房产客户」和「结算方式」筛选项显示正确
3. 选择筛选项后点击查询，验证列表正确过滤
4. 点击重置，验证筛选项清空

- [ ] **Step 4: 运行后端测试套件**

```bash
cd backend && pytest tests/integration/test_billing_api.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: 最终提交（如有遗漏）**

```bash
git add .
git commit -m "feat: align balance page filters with customer page"
```

---

## 验收标准

1. ✅ 余额管理页面显示「房产客户」和「结算方式」筛选项
2. ✅ 筛选项位置在「重点客户」之后
3. ✅ 筛选功能正常工作，正确过滤列表数据
4. ✅ 重置按钮清空新增筛选项
5. ✅ 后端 API 支持新参数，向后兼容
6. ✅ 所有测试通过
