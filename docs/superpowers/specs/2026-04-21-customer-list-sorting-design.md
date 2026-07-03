# 客户管理页面表头排序功能设计

**创建日期**: 2026-04-21
**状态**: 已确认
**关联页面**: http://localhost:5173/customers

---

## 需求概述

在客户管理页面的搜索结果列表中,为每个表头添加排序功能,支持通过点击表头后的排序图标实现正序(asc)和逆序(desc)切换。

---

## 当前状态分析

### 前端已有基础设施
- `sortState` 响应式对象管理排序状态 (`sort_by: 'id'`, `sort_order: 'asc' | 'desc'`)
- `handleSort(dataIndex, direction)` 函数已实现,处理排序事件并重新加载数据
- `@sort` 事件已绑定到 `<a-table>` 组件
- API `getCustomers()` 已支持 `sort_by` 和 `sort_order` 参数

### 当前限制
- 只有「公司 ID」和「客户名称」两列设置了 `sortable: true`
- 后端 `ALLOWED_SORT_FIELDS` 只允许: `id`, `company_id`, `name`, `created_at`, `updated_at`
- 业务列(行业类型、结算方式、运营经理、重点客户)未开启排序

---

## 设计方案

### 1. 后端变更

**文件**: `backend/app/services/customers.py`

#### 1.1 扩展 ALLOWED_SORT_FIELDS (第 16 行)

```python
ALLOWED_SORT_FIELDS = {
    "id", "company_id", "name", "created_at", "updated_at",
    "industry", "settlement_type", "manager_id", "is_key_customer"
}
```

新增字段说明:
| 字段            | 所属表             | 说明       |
| --------------- | ------------------ | ---------- |
| `industry`      | `CustomerProfile`  | 行业类型   |
| `settlement_type` | `Customer`       | 结算方式   |
| `manager_id`    | `Customer`         | 运营经理   |
| `is_key_customer` | `Customer`       | 重点客户   |

#### 1.2 排序逻辑适配 (第 211-216 行)

由于 `industry` 字段在 `CustomerProfile` 表中,需要特殊处理:

```python
# 排序逻辑
if sort_by == "industry":
    sort_column = getattr(CustomerProfile, "industry")
else:
    sort_column = getattr(Customer, sort_by)

if sort_order == "desc":
    stmt = stmt.order_by(sort_column.desc())
else:
    stmt = stmt.order_by(sort_column.asc())
```

**注意**: `get_all_customers` 方法在行业筛选时已经有 `outerjoin(CustomerProfile)` 的逻辑,但排序时可能没有 join。需要确保排序时如果 `sort_by == "industry"` 则添加 join。

**完整修正逻辑**:
```python
# 验证排序参数
if sort_by not in ALLOWED_SORT_FIELDS:
    raise ValueError(f"Invalid sort field: {sort_by}")
if sort_order not in VALID_SORT_ORDERS:
    raise ValueError(f"Invalid sort order: {sort_order}")

# 构建基础查询 (已在前面处理了筛选条件的 join)
# 如果按 industry 排序且前面没有因为筛选而 join,需要确保 join
if sort_by == "industry":
    stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
    sort_column = CustomerProfile.industry
else:
    sort_column = getattr(Customer, sort_by)

if sort_order == "desc":
    stmt = stmt.order_by(sort_column.desc())
else:
    stmt = stmt.order_by(sort_column.asc())
```

### 2. 前端变更

**文件**: `frontend/src/views/customers/Index.vue`

#### 2.1 columns 数组更新 (第 510-519 行)

将 `sortable: true` 改为 `sortable: { sortType: 'all' }`,并为所有业务列添加 sortable:

```typescript
const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 140, sortable: { sortType: 'all' }, ellipsis: true, tooltip: true },
  { title: '客户名称', dataIndex: 'name', width: 250, sortable: { sortType: 'all' }, ellipsis: true, tooltip: true },
  { title: '行业类型', dataIndex: 'industry', width: 100, sortable: { sortType: 'all' } },
  { title: '结算方式', slotName: 'settlementType', width: 100, sortable: { sortType: 'all' } },
  { title: '运营经理', slotName: 'manager', width: 150, sortable: { sortType: 'all' }, ellipsis: true, tooltip: true },
  { title: '重点客户', slotName: 'isKeyCustomer', width: 100, sortable: { sortType: 'all' } },
  { title: '创建时间', slotName: 'createdAt', width: 180, sortable: { sortType: 'all' } },
  { title: '操作', slotName: 'action', width: 320, fixed: 'right' as const },
]
```

**说明**:
- `sortable: { sortType: 'all' }` 支持三种状态循环: 升序 → 降序 → 取消排序
- 操作列保持不可排序
- `slotName` 列的排序使用 `dataIndex` 作为排序字段名,需要确认 Arco Design 的行为

**重要**: 对于使用 `slotName` 的列(Arco Design 表格),`sortable` 的 `dataIndex` 属性需要明确指定排序字段。需要检查 `handleSort` 接收的 `dataIndex` 参数是否正确。

当前 `handleSort` 签名:
```typescript
const handleSort = (dataIndex: string, direction: 'asc' | 'desc' | '') => { ... }
```

对于使用 `slotName` 的列,需要在列定义中添加 `dataIndex`:
```typescript
{ title: '结算方式', dataIndex: 'settlement_type', slotName: 'settlementType', width: 100, sortable: { sortType: 'all' } },
{ title: '运营经理', dataIndex: 'manager_id', slotName: 'manager', width: 150, sortable: { sortType: 'all' }, ... },
{ title: '重点客户', dataIndex: 'is_key_customer', slotName: 'isKeyCustomer', width: 100, sortable: { sortType: 'all' } },
{ title: '创建时间', dataIndex: 'created_at', slotName: 'createdAt', width: 180, sortable: { sortType: 'all' } },
```

### 3. 交互流程

```
用户点击表头
  ↓
Arco Table 触发 @sort 事件 (dataIndex, direction)
  ↓
handleSort(dataIndex, direction) 被调用
  ↓
更新 sortState.sort_by = dataIndex
更新 sortState.sort_order = direction ('asc' | 'desc')
  ↓
重置 pagination.current = 1
调用 loadCustomers()
  ↓
后端接收 sort_by + sort_order 参数
执行 ORDER BY 查询
  ↓
返回排序后的数据
表格刷新显示
```

### 4. 边界情况处理

| 场景                     | 处理方式                                        |
| ------------------------ | ----------------------------------------------- |
| 点击同一列切换排序       | asc → desc → 取消排序(空字符串) → asc 循环      |
| 点击不同列               | 新列从 asc 开始,旧列自动清除排序状态             |
| 取消排序(direction='')   | 恢复默认 sort_by='id', sort_order='asc'          |
| 行业类型为 NULL 的记录   | PostgreSQL 默认排序: NULL 值在 ORDER BY 中排在最后 |
| 后端返回非法排序字段错误 | 前端已有 catch 处理,Message.error 显示错误信息   |

---

## 涉及文件清单

| 文件                                           | 变更类型 | 变更内容                 |
| ---------------------------------------------- | -------- | ------------------------ |
| `backend/app/services/customers.py`            | 修改     | 扩展 ALLOWED_SORT_FIELDS + 排序逻辑适配 |
| `frontend/src/views/customers/Index.vue`       | 修改     | columns 数组添加 sortable |

---

## 验收标准

1. ✅ 所有 7 个业务列表头(公司 ID、客户名称、行业类型、结算方式、运营经理、重点客户、创建时间)显示排序图标
2. ✅ 点击表头可切换升序/降序/取消排序三种状态
3. ✅ 排序后数据正确刷新,分页重置到第 1 页
4. ✅ 操作列不可排序
5. ✅ 排序与筛选条件可同时生效
