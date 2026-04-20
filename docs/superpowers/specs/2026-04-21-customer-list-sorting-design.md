# 设计文档：客户管理列表排序功能

**日期**: 2026-04-21
**状态**: 已批准
**模块**: 客户管理 (Customer Management)

---

## 需求概述

在客户管理结果列表中增加排序功能：
1. 支持按**公司ID** (`company_id`) 排序
2. **默认排序**改为按**客户ID** (`id`) 递增排序
3. 支持多列点击排序（用户可点击列标题切换升序/降序）

---

## 当前状态分析

| 方面 | 当前状态 |
|------|----------|
| **默认排序** | `created_at DESC`（后端硬编码） |
| **可配置排序** | 不支持 - 后端无 `sort_by`/`sort_order` 参数 |
| **前端排序** | 未启用 - 列定义无 `sortable`，无 sort 事件处理 |
| **缓存** | 基于 filters + pagination，不包含排序信息 |
| **ID 字段** | `id` (自增主键) + `company_id` (业务唯一标识) |

---

## 设计方案

### 1. 后端 API 改动

#### 1.1 路由层 (`backend/app/routes/customers.py`)

在 `GET /api/v1/customers` 端点新增查询参数：
- `sort_by` (string, 可选): 排序字段，默认 `id`
- `sort_order` (string, 可选): 排序方向，`asc` 或 `desc`，默认 `asc`

#### 1.2 服务层 (`backend/app/services/customers.py`)

修改 `get_all_customers()` 方法：
1. 新增参数：`sort_by: str = "id"`, `sort_order: str = "asc"`
2. 定义排序字段白名单：
   ```python
   ALLOWED_SORT_FIELDS = {"id", "company_id", "name", "created_at", "updated_at"}
   ```
3. 验证逻辑：
   - `sort_by` 必须在白名单中，否则抛 `ValueError`
   - `sort_order` 必须为 `asc` 或 `desc`
4. 替换硬编码排序：
   ```python
   # 旧代码
   stmt = stmt.order_by(Customer.created_at.desc())
   
   # 新代码
   sort_column = getattr(Customer, sort_by)
   if sort_order == "desc":
       stmt = stmt.order_by(sort_column.desc())
   else:
       stmt = stmt.order_by(sort_column.asc())
   ```
5. 更新缓存key：
   ```python
   # 旧格式
   f"customers:list:{page}:{page_size}:{filters_hash}"
   
   # 新格式
   f"customers:list:{page}:{page_size}:{sort_by}:{sort_order}:{filters_hash}"
   ```

#### 1.3 错误处理

- `sort_by` 不在白名单 → 返回 `400 Bad Request` + `"Invalid sort field: {sort_by}"`
- `sort_order` 非法 → 返回 `400 Bad Request` + `"Invalid sort order: {sort_order}"`

---

### 2. 前端改动

#### 2.1 API 层 (`frontend/src/api/customers.ts`)

更新 `getCustomers()` 函数签名：
```typescript
export function getCustomers(params?: {
  page?: number
  page_size?: number
  keyword?: string
  account_type?: string
  industry?: string
  manager_id?: number
  settlement_type?: string
  is_key_customer?: boolean
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}) {
  return api.get('/customers', { params })
}
```

#### 2.2 页面组件 (`frontend/src/views/customers/Index.vue`)

1. **列定义修改**：
   ```typescript
   const columns = [
     { title: '公司ID', dataIndex: 'company_id', width: 140, sortable: true, ellipsis: true, tooltip: true },
     // ... 其他列
   ]
   ```

2. **排序状态管理**：
   ```typescript
   const sortState = reactive({
     sort_by: 'id',
     sort_order: 'asc' as 'asc' | 'desc',
   })
   ```

3. **排序事件处理**：
   ```typescript
   const handleSort = (dataIndex: string, direction: 'asc' | 'desc' | '') => {
     if (!direction) {
       // 取消排序时恢复默认
       sortState.sort_by = 'id'
       sortState.sort_order = 'asc'
     } else {
       sortState.sort_by = dataIndex
       sortState.sort_order = direction
     }
     pagination.current = 1 // 重置到第一页
     loadCustomers()
   }
   ```

4. **数据加载更新**：
   ```typescript
   const loadCustomers = async () => {
     const params: any = {
       page: pagination.current,
       page_size: pagination.pageSize,
       sort_by: sortState.sort_by,
       sort_order: sortState.sort_order,
       // ... 其他筛选参数
     }
     const res = await getCustomers(params)
     customers.value = res.data.list || []
     pagination.total = res.data.total || 0
   }
   ```

5. **表格绑定**：
   ```vue
   <a-table
     :columns="columns"
     :data="customers"
     @sort="handleSort"
     ...
   />
   ```

---

### 3. 数据流

```
用户点击列标题 → Arco Table 触发 @sort 事件
  → 前端更新 sortState (sort_by, sort_order)
  → 调用 loadCustomers() 传入排序参数
  → API 请求 GET /api/v1/customers?sort_by=id&sort_order=asc
  → 后端验证 sort_by 在白名单中
  → 动态构建 ORDER BY 子句
  → 更新缓存key（包含排序维度）
  → 返回排序后的数据
  → 前端更新表格显示
```

---

### 4. 涉及文件清单

| 文件路径 | 改动类型 | 说明 |
|----------|----------|------|
| `backend/app/services/customers.py` | 修改 | 支持动态排序，更新缓存key |
| `backend/app/routes/customers.py` | 修改 | 解析并传递排序参数 |
| `frontend/src/api/customers.ts` | 修改 | 添加排序参数类型定义 |
| `frontend/src/views/customers/Index.vue` | 修改 | 启用列排序，添加状态管理和事件处理 |

---

### 5. 测试要点

1. **后端测试**：
   - 验证默认排序 `id ASC` 生效
   - 验证 `sort_by=company_id&sort_order=desc` 正确排序
   - 验证非法 `sort_by` 返回 400 错误
   - 验证非法 `sort_order` 返回 400 错误
   - 验证缓存key包含排序维度

2. **前端测试**：
   - 验证点击列标题触发排序
   - 验证默认排序状态正确显示
   - 验证排序后分页保持正确
   - 验证 Arco Design 排序图标显示正常

---

## 验收标准

- [ ] 客户列表默认按客户ID递增排序
- [ ] 用户可以点击"公司ID"列标题进行升序/降序排序
- [ ] 排序后分页数据正确
- [ ] 非法排序参数被正确拒绝
- [ ] 缓存策略正确区分不同排序状态
