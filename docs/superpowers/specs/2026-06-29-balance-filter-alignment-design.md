# 余额管理页面筛选项对齐设计

**日期**: 2026-06-29  
**状态**: 已批准

---

## 背景

客户管理页面和余额管理页面的列表筛选项不一致，导致用户体验割裂。需要让余额管理页面的筛选项与客户管理页面保持一致。

## 需求

将余额管理页面的基础筛选项与客户管理页面对齐，同时保留余额管理特有的业务筛选项（充值时间）。

## 当前状态对比

### 客户管理页面筛选项（7 项）
1. 关键词（公司名称/公司 ID）
2. 账号类型
3. 行业类型
4. 重点客户
5. **房产客户** ✓
6. **结算方式** ✓
7. 查询/重置按钮

### 余额管理页面筛选项（当前 6 项）
1. 关键词（公司名称/公司 ID）
2. 充值时间 ← 余额管理特有
3. 行业类型
4. 账号类型
5. 重点客户
6. 查询/重置按钮

**缺失**: 房产客户、结算方式

## 设计方案

### 方案选择
采用**方案 1：直接添加筛选项**

理由：
- 改动最小，风险最低
- 两个页面业务场景不同，未来可独立演进
- 实现简单，无需重构

### 改动范围

#### 1. 前端 `Balance.vue`
- 在筛选区域添加「房产客户」和「结算方式」两个筛选项
- 位置：在「重点客户」之后、「充值时间」之前
- `filters` 对象新增字段：
  - `is_real_estate: boolean | null`
  - `settlement_type: string | null`
- `loadBalances` 方法传递新参数给 API
- `handleReset` 方法重置新字段

#### 2. 前端 `api/billing.ts`
- `getBalances` 参数类型新增：
  - `is_real_estate?: boolean`
  - `settlement_type?: string`

#### 3. 后端 `billing.py` 路由
- `get_balances` 方法新增参数解析：
  - `is_real_estate`: 布尔值（true/false）
  - `settlement_type`: 字符串（prepaid/postpaid）
- 添加对应的 `where` 条件：
  - `Customer.is_real_estate == is_real_estate`
  - `Customer.settlement_type == settlement_type`

### 对齐后的筛选项顺序

| 序号 | 筛选项 | 说明 |
|------|--------|------|
| 1 | 关键词 | 公司名称/公司 ID |
| 2 | 账号类型 | 正式账号/测试账号 |
| 3 | 行业类型 | 多选下拉 |
| 4 | 重点客户 | 是/否 |
| 5 | **房产客户** | **新增** - 是/否 |
| 6 | **结算方式** | **新增** - 预付费/后付费 |
| 7 | 充值时间 | 余额管理特有，保留 |

### 高级筛选（不变）
- 运营经理
- 商务经理
- 标签筛选

## 技术细节

### 后端实现
```python
# 新增参数解析
is_real_estate = request.args.get("is_real_estate")
if is_real_estate is not None:
    is_real_estate = is_real_estate.lower() == "true"

settlement_type = request.args.get("settlement_type")

# 新增筛选条件
if is_real_estate is not None:
    base_stmt = base_stmt.where(Customer.is_real_estate == is_real_estate)

if settlement_type:
    base_stmt = base_stmt.where(Customer.settlement_type == settlement_type)
```

### 前端实现
```typescript
// filters 新增字段
const filters = reactive({
  // ... 现有字段
  is_real_estate: null as boolean | null,
  settlement_type: null as string | null,
})

// loadBalances 传递参数
const params = {
  // ... 现有参数
  is_real_estate: filters.is_real_estate ?? undefined,
  settlement_type: filters.settlement_type ?? undefined,
}

// handleReset 重置
filters.is_real_estate = null
filters.settlement_type = null
```

## 测试要点

1. 前端：筛选项 UI 显示正确，选择后触发查询
2. 前端：重置按钮清空新增筛选项
3. 后端：API 正确接收和处理新参数
4. 后端：筛选结果正确过滤
5. 集成：前后端联调正常

## 影响范围

- **修改文件**: 3 个
  - `frontend/src/views/billing/Balance.vue`
  - `frontend/src/api/billing.ts`
  - `backend/app/routes/billing.py`
- **影响功能**: 仅余额管理列表查询
- **向后兼容**: 是（新增参数为可选）
