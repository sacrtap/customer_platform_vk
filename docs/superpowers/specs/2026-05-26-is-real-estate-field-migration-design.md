# 设计文档：is_real_estate 字段迁移至 customers 主表

**创建日期**: 2026-05-26  
**状态**: 待用户审查  
**作者**: Prometheus + 用户协作

---

## TL;DR

将 `is_real_estate`（是否房产客户）从 `customer_profiles` 画像表迁移到 `customers` 客户主表，并在前端详情页显示、两个编辑弹窗中新增该字段的设置入口。

**核心变更**：数据库迁移 + 后端 API 字段支持 + 前端三处 UI 改动
**涉及范围**：1 个迁移文件 + 2 个 Python 文件 + 2 个 Vue 文件 + 2 个 TS 类型文件

---

## 1. 现状调研

### 1.1 `is_real_estate` 当前位置

| 层级       | 位置                                                                 |
| ---------- | -------------------------------------------------------------------- |
| 数据库表   | `customer_profiles.is_real_estate` (Boolean, nullable=True, default=False) |
| 详情 API   | `GET /customers/{id}` 返回 `profile.is_real_estate`                      |
| 列表 API   | `GET /customers` 不返回该字段                                            |
| 更新 API   | `PUT /customers/{id}/profile` 可更新                                     |

### 1.2 前端现有结构

| 页面         | 文件                             | 表单提交方式                                    |
| ------------ | -------------------------------- | ----------------------------------------------- |
| 详情页展示   | `frontend/src/views/customers/Detail.vue` | info-grid 显示，`customer` 对象渲染              |
| 详情页编辑   | `Detail.vue` (弹窗，1100px, 3 列)  | `Promise.all([updateCustomer, updateProfile])`   |
| 列表页编辑   | `frontend/src/views/customers/Index.vue`  | `updateCustomer()` 单 API，10 个主表字段           |
| 类型定义     | `frontend/src/types/index.ts`    | `Customer` 接口 + `CustomerProfile` 接口           |

---

## 2. 设计决策

### 2.1 迁移方案：方案 A（渐进式迁移）

- `customers` 表新增 `is_real_estate` 列（Boolean, nullable=True, default=None）
- 迁移脚本：从 `customer_profiles` 复制已有数据到主表
- `customer_profiles` 旧列保留不动（向后兼容，不影响 profile API）

**理由**：风险最低，历史数据不丢失，旧列保留做安全网

### 2.2 前端显示格式

三种状态区分：
- `null/未设置` → 显示 "-"（灰色）
- `true` → 绿色标签 "是"
- `false` → 灰色标签 "否"

**理由**：完整区分未设置和有意识的 false，便于运营识别哪些客户尚未配置该标识

### 2.3 编辑入口

- 详情页编辑弹窗："基础信息"列新增下拉选择
- 列表页编辑弹窗："结算方式"右侧新增下拉选择

---

## 3. 详细实现

### 3.1 数据库迁移

**文件**：`backend/alembic/versions/XXX_add_is_real_estate_to_customers.py`

```python
def upgrade():
    # 1. customers 表新增列
    op.add_column("customers", 
        sa.Column("is_real_estate", sa.Boolean(), nullable=True, server_default=sa.text("NULL")))
    
    # 2. 从 profile 表复制数据到主表
    op.execute("""
        UPDATE customers SET is_real_estate = (
            SELECT customer_profiles.is_real_estate 
            FROM customer_profiles 
            WHERE customer_profiles.customer_id = customers.id
        )
        WHERE EXISTS (
            SELECT 1 FROM customer_profiles 
            WHERE customer_profiles.customer_id = customers.id
        )
    """)

def downgrade():
    op.drop_column("customers", "is_real_estate")
```

### 3.2 数据模型

**文件**：`backend/app/models/customers.py`

```python
class Customer(BaseModel):
    # ... 已有字段
    is_real_estate = Column(Boolean, nullable=True, default=None)  # 新增
```

### 3.3 后端 API 变更

#### list_customers 端点

**文件**：`backend/app/routes/customers.py`，列表项字典 ~第 125 行

```python
"is_real_estate": c.is_real_estate,  # 新增
```

#### create_customer / update_customer 端点

- 请求体接受 `is_real_estate` 字段
- update_customer 将该字段加入可更新字段列表
- 写入 `Customer` 模型（非 profile 模型）

#### Profile API（保持兼容）

- `update_profile` 端点中的 `is_real_estate` 保持不变
- 旧列 `customer_profiles.is_real_estate` 保留不动
- 后续可逐步废弃

### 3.4 前端详情页显示

**文件**：`frontend/src/views/customers/Detail.vue`，info-grid 中新增

```html
<div class="info-item">
  <span class="label">是否房产客户</span>
  <span class="value">
    <span v-if="customer?.is_real_estate === null" class="text-muted">-</span>
    <a-tag v-else-if="customer?.is_real_estate" color="green" size="small">是</a-tag>
    <a-tag v-else color="gray" size="small">否</a-tag>
  </span>
</div>
```

迁移到主表后，直接从 `customer.is_real_estate` 读取（不再走 `customer.profile.is_real_estate`）。

### 3.5 前端详情页编辑弹窗

**文件**：`frontend/src/views/customers/Detail.vue`，"基础信息"列

```html
<a-form-item field="is_real_estate" label="是否房产客户">
  <a-select v-model="editForm.is_real_estate" placeholder="请选择" allow-clear>
    <a-option :value="null">-</a-option>
    <a-option :value="true">是</a-option>
    <a-option :value="false">否</a-option>
  </a-select>
</a-form-item>
```

**EditForm 接口新增**：
```typescript
interface EditForm {
  is_real_estate: boolean | null
}
```

**Submit 变更**：`editForm.is_real_estate` 传入 `updateCustomer()` API，同时从 `updateProfile()` 中移除（该字段不再走 profile 渠道）

### 3.6 前端列表页编辑弹窗

**文件**：`frontend/src/views/customers/Index.vue`，"结算方式"表单项后右侧

```html
<a-col :span="12">
  <a-form-item field="is_real_estate" label="是否房产客户">
    <a-select v-model="customerForm.is_real_estate" placeholder="请选择" allow-clear>
      <a-option :value="null">-</a-option>
      <a-option :value="true">是</a-option>
      <a-option :value="false">否</a-option>
    </a-select>
  </a-form-item>
</a-col>
```

**customerForm 新增**：
```typescript
const customerForm = reactive({
  is_real_estate: null as boolean | null,
})
```

### 3.7 前端类型定义

**文件**：`frontend/src/types/index.ts`

```typescript
export interface Customer {
  // ...现有字段
  is_real_estate: boolean | null  // 新增
}
```

### 3.8 前端 API 调用

**文件**：`frontend/src/api/customers.ts`

- `createCustomer()` 请求体新增：`is_real_estate?: boolean | null`
- `updateCustomer()` 请求体新增：`is_real_estate?: boolean | null`

---

## 4. 测试计划

### 4.1 后端测试

| 测试场景                    | 验证内容                                  |
| --------------------------- | ----------------------------------------- |
| 迁移脚本                    | 升级/降级正常，数据正确复制                 |
| list_customers              | 列表响应包含 `is_real_estate` 字段         |
| create_customer             | 创建时传入 `is_real_estate` 正确保存        |
| update_customer             | 更新时 `is_real_estate` 可被修改             |
| update_profile（兼容性）     | Profile API 仍可接受该字段，不报错          |

### 4.2 前端测试

| 测试场景                        | 验证内容                                  |
| ------------------------------- | ----------------------------------------- |
| 详情页显示 null 值              | 显示 "-"                                    |
| 详情页显示 true 值              | 绿色"是"标签                                |
| 详情页显示 false 值             | 灰色"否"标签                                |
| 详情页编辑：修改并提交            | `updateCustomer` 调用成功，值正确           |
| 列表页编辑：修改并提交            | `updateCustomer` 调用成功，值正确           |
| 列表页：新建客户                  | 不传 `is_real_estate`（默认 null），创建正常  |

---

## 5. 风险与缓解

| 风险                     | 缓解措施                                                |
| ------------------------ | ------------------------------------------------------- |
| 迁移脚本失败             | downgrade 回滚支持，先测试环境验证                        |
| 历史数据丢失             | 迁移时从 profile 表显式复制，旧列保留不删                  |
| Profile API 依赖 `is_real_estate` | 旧列保留不动，profile API 仍可读写，向后兼容 |
| 前端显示类型冲突（Boolean vs null） | TypeScript 类型定义为 `boolean | null`，严格区分三种状态 |

---

## 6. 执行计划（概要）

### Wave 1（数据库 + 模型，可并行）
1. Alembic 迁移文件创建 + 数据复制脚本
2. Customer 模型新增 `is_real_estate` 列

### Wave 2（后端 API，可并行）
3. list_customers 返回 `is_real_estate`
4. create/update_customer 接受 `is_real_estate`

### Wave 3（前端改动，可并行）
5. 详情页 info-grid 显示 + 编辑弹窗字段
6. 列表页编辑弹窗字段 + customerForm 更新
7. 类型定义（types/index.ts）+ API 调用（api/customers.ts）

### Wave 4（验证）
8. 后端测试 + 前端 E2E 测试
