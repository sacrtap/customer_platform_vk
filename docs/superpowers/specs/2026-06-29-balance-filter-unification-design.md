# 余额管理页面筛选项统一设计文档

**日期**: 2026-06-29  
**状态**: 待实施  
**作者**: AI Assistant

---

## 1. 背景与目标

### 1.1 问题描述

当前系统中，"余额管理"页面和"客户管理"页面的列表筛选项存在不一致：

- **客户管理页面**包含：关键词、账号类型、行业类型、重点客户、**房产客户**、**结算方式**
- **余额管理页面**包含：客户（标签不一致）、充值时间、行业类型、账号类型、重点客户

### 1.2 需求目标

将客户管理页面的筛选项全部同步到余额管理页面，同时保留余额管理页面特有的"充值时间"筛选项。

### 1.3 验收标准

- 余额管理页面的筛选项顺序：关键词 → 账号类型 → 行业类型 → 重点客户 → 房产客户 → 结算方式 → 充值时间 → 查询/重置
- 新增"房产客户"和"结算方式"两个筛选项正常工作
- 查询和重置功能正常
- 后端 API 支持新筛选参数
- 分页总数与新筛选条件一致

---

## 2. 技术方案

### 2.1 方案选择

采用**最小改动方案**：

- 在余额管理页面添加缺失的筛选项
- 调整筛选项顺序和标签名称
- 后端 API 添加对新筛选参数的支持
- 不提取共享组件，避免过度设计

**选择理由**：
- 需求明确且范围可控
- 改动最小，风险最低
- 符合 YAGNI 原则

### 2.2 前端改动

**改动文件**: `frontend/src/views/billing/Balance.vue`

#### 2.2.1 修改 filters 数据结构（第 509-515 行）

```typescript
const createDefaultFilters = () => ({
  keyword: '',
  recharge_date: [] as string[],
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  account_type: '正式账号',
  is_key_customer: null as boolean | null,
  is_real_estate: null as boolean | null,  // 新增
  settlement_type: '',  // 新增
})
```

#### 2.2.2 修改模板筛选区域（第 35-98 行）

**调整顺序**：关键词 → 账号类型 → 行业类型 → 重点客户 → **房产客户** → **结算方式** → 充值时间 → 查询/重置按钮

**新增两个筛选项**：

```vue
<!-- 在"重点客户"后添加 -->
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

**调整"充值时间"位置**：移到"结算方式"之后，保持布局一致

#### 2.2.3 修改 loadBalances 函数（第 740-792 行）

在构建 API 参数时添加新筛选字段：

```typescript
const params: {
  // ... 现有参数
  is_real_estate?: boolean
  settlement_type?: string
} = {
  // ... 现有参数
}

// 在现有条件判断后添加
if (filters.is_real_estate !== null) params.is_real_estate = filters.is_real_estate
if (filters.settlement_type) params.settlement_type = filters.settlement_type
```

#### 2.2.4 修改 handleReset 函数（第 815-822 行）

确保重置时清空新增筛选字段（已通过 `createDefaultFilters()` 自动处理）

### 2.3 后端改动

**改动文件**: `backend/app/routes/billing.py`

#### 2.3.1 添加新筛选参数解析（第 47-68 行区域）

在现有的 `is_key_customer` 参数解析后添加：

```python
# 新增筛选参数
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

#### 2.3.2 添加筛选条件（第 113-114 行区域）

在 `is_key_customer` 筛选条件后添加：

```python
if is_real_estate is not None:
    base_stmt = base_stmt.where(Customer.is_real_estate == is_real_estate)

if settlement_type:
    base_stmt = base_stmt.where(Customer.settlement_type == settlement_type)
```

#### 2.3.3 同步更新计数查询（第 188 行后）

余额 API 有两个查询：数据查询和计数查询。需要在计数查询中也添加相同的筛选条件，确保分页总数正确。

在第 188 行 `if is_key_customer is not None:` 条件后添加：

```python
if is_real_estate is not None:
    count_stmt = count_stmt.where(Customer.is_real_estate == is_real_estate)

if settlement_type:
    count_stmt = count_stmt.where(Customer.settlement_type == settlement_type)
```

---

## 3. 测试策略

### 3.1 前端验收标准

- [ ] 余额管理页面筛选项顺序：关键词 → 账号类型 → 行业类型 → 重点客户 → 房产客户 → 结算方式 → 充值时间 → 查询/重置
- [ ] "房产客户"下拉框正常工作（是/否/清空）
- [ ] "结算方式"下拉框正常工作（预付费/后付费/清空）
- [ ] 查询按钮点击后，新筛选参数正确传递给后端 API
- [ ] 重置按钮点击后，新筛选字段恢复默认值
- [ ] 高级筛选（运营经理/商务经理/标签）不受影响

### 3.2 后端验收标准

- [ ] `GET /api/v1/billing/balances?is_real_estate=true` 返回房产客户余额
- [ ] `GET /api/v1/billing/balances?is_real_estate=false` 返回非房产客户余额
- [ ] `GET /api/v1/billing/balances?settlement_type=prepaid` 返回预付费客户余额
- [ ] `GET /api/v1/billing/balances?settlement_type=postpaid` 返回后付费客户余额
- [ ] 组合筛选正常工作（如 `is_real_estate=true&settlement_type=prepaid`）
- [ ] 分页总数与新筛选条件一致

### 3.3 测试用例

**后端单元测试**（新增到 `backend/tests/integration/test_billing_api.py`）：

1. `test_get_balances_filter_is_real_estate_true` — 验证房产客户筛选
2. `test_get_balances_filter_is_real_estate_false` — 验证非房产客户筛选
3. `test_get_balances_filter_settlement_type_prepaid` — 验证预付费筛选
4. `test_get_balances_filter_settlement_type_postpaid` — 验证后付费筛选
5. `test_get_balances_filter_combined` — 验证组合筛选

---

## 4. 不需要改动的部分

- 客户管理页面（保持不变）
- 余额管理的高级筛选（已一致）
- 数据库 schema（字段已存在）
- API 接口路径（不变）

---

## 5. 实施计划

1. **后端改动**（优先级高）
   - 修改 `backend/app/routes/billing.py`
   - 添加新筛选参数解析和筛选条件
   - 同步更新计数查询

2. **前端改动**
   - 修改 `frontend/src/views/billing/Balance.vue`
   - 调整 filters 数据结构
   - 修改模板筛选区域
   - 更新 loadBalances 函数

3. **测试验证**
   - 编写后端单元测试
   - 前端功能验收

---

## 6. 风险评估

- **风险等级**: 低
- **影响范围**: 仅余额管理页面
- **回滚方案**: 代码回退即可

---

## 7. 参考资料

- 客户管理页面实现: `frontend/src/views/customers/Index.vue`
- 客户管理后端 API: `backend/app/routes/customers.py`
- 余额管理页面: `frontend/src/views/billing/Balance.vue`
- 余额管理后端 API: `backend/app/routes/billing.py`
