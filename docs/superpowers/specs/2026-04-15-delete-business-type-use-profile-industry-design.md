# 设计文档：删除 customers.business_type，改用 customer_profiles.industry

**日期**: 2026-04-15
**状态**: 待批准
**范围**: 客户管理模块 - 行业类型字段统一

---

## 一、背景与目标

### 问题

当前系统中存在两个"行业类型"字段：
- `customers.business_type` (VARCHAR(50))：列表页显示
- `customer_profiles.industry` (VARCHAR(100))：详情页显示

两个字段存储相同语义的数据，但值可能不同步，导致列表页和详情页显示不一致。

### 目标

1. **删除冗余字段**：删除 `customers.business_type` 列
2. **统一数据源**：行业类型数据统一存储在 `customer_profiles.industry`
3. **列表页改造**：通过 JOIN `customer_profiles` 获取行业类型
4. **保持前端兼容**：后端 API 返回字段名保持 `business_type`（前端无需大改）

---

## 二、方案设计

### 2.1 数据库变更

**删除列**：
```sql
ALTER TABLE customers DROP COLUMN business_type;
```

**删除索引**：
```sql
DROP INDEX idx_customer_business_settlement;
-- 重建不含 business_type 的复合索引（如需要）
```

**数据迁移**：
- 确保所有客户都有对应的 `customer_profiles` 记录
- 没有 profile 记录的客户，创建空记录（`customer_id` 关联，其他字段为 NULL）
- 现有 `customers.business_type` 值**不迁移**（以 `profile.industry` 为准）

### 2.2 后端变更

#### 模型层

**文件**: `backend/app/models/customers.py`

- 删除 `Customer.business_type` 列定义
- 删除 `Index("idx_customer_business_settlement", "business_type", "settlement_type")`

#### 查询层

**文件**: `backend/app/services/customers.py`

- 列表查询改为 JOIN `CustomerProfile`：
```python
stmt = (
    select(Customer, CustomerProfile.industry.label("industry"))
    .outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
    .where(...)
)
```

- 筛选条件改为使用 `CustomerProfile.industry`：
```python
if business_type := filters.get("business_type"):
    conditions.append(CustomerProfile.industry == business_type)
```

#### 响应层

**文件**: `backend/app/routes/customers.py`

- 响应中保持字段名 `business_type`，但值来自 `profile.industry`：
```python
"business_type": row.industry,  # 来自 JOIN 结果
```

- 新建/编辑客户时，行业类型写入 `profile.industry` 而非 `customer.business_type`

#### 文件模块

**文件**: `backend/app/models/files.py`, `backend/app/routes/files.py`

- `File` 模型中的 `business_type` 字段**不受影响**（这是文件的业务类型，与客户行业类型不同）

### 2.3 前端变更

**无需大改**（因为后端返回字段名保持 `business_type`）：

- 列表页 `dataIndex: 'business_type'` 保持不变
- 筛选条件 `business_type` 参数保持不变
- 详情页显示 `profile.industry` 的逻辑保持不变

### 2.4 Alembic 迁移

1. 检查所有客户是否有 `customer_profiles` 记录，没有的创建空记录
2. 删除 `customers.business_type` 列
3. 删除 `idx_customer_business_settlement` 索引

---

## 三、影响范围

### 后端需要修改的文件

| 文件 | 变更内容 |
| ---- | -------- |
| `backend/app/models/customers.py` | 删除 `business_type` 列和索引 |
| `backend/app/services/customers.py` | 查询改为 JOIN，筛选条件用 `CustomerProfile.industry` |
| `backend/app/routes/customers.py` | 响应字段值来源改为 `profile.industry` |
| `backend/alembic/versions/` | 新增迁移脚本 |

### 前端需要修改的文件

**无需修改**（后端保持 `business_type` 字段名返回）

### 测试需要修改的文件

| 文件 | 变更内容 |
| ---- | -------- |
| `backend/tests/` 中引用 `Customer.business_type` 的测试 | 改用 `CustomerProfile.industry` |

---

## 四、风险与缓解

| 风险 | 缓解措施 |
| ---- | -------- |
| 客户无 profile 记录导致 LEFT JOIN 返回 NULL | 迁移脚本确保所有客户都有 profile 记录 |
| 现有 business_type 数据丢失 | 已确认不迁移，以 profile.industry 为准 |
| 筛选性能下降（JOIN 比单表慢） | 确保 `customer_profiles.customer_id` 有索引（已有 unique 约束） |

---

## 五、验收标准

1. `customers` 表无 `business_type` 列
2. 客户列表 API 返回的 `business_type` 值来自 `customer_profiles.industry`
3. 列表页和详情页显示的行业类型一致
4. 按行业类型筛选功能正常
5. 新建/编辑客户时，行业类型写入 `customer_profiles.industry`
6. 所有测试通过
