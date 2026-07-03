# 设计文档：行业类型外键关联改造

**日期**: 2026-05-11
**状态**: 已批准
**方案**: 方案 A - 完整外键替换

---

## 1. 背景与目标

### 1.1 当前问题

客户管理页面中的"行业类型"字段与"系统设置-行业类型"之间仅通过字符串值匹配，没有数据库级别的外键约束。存在以下风险：

- 客户记录中的 `industry` 是纯字符串，数据库不保证值的有效性
- 删除行业类型后，已关联的客户记录不受影响（产生孤儿数据）
- 修改行业类型名称后，已关联的客户记录不会自动更新

### 1.2 改造目标

将字符串值匹配升级为外键引用关联，确保客户记录中的行业类型始终指向系统设置中定义的有效行业类型，以"系统设置-行业类型"为唯一标准。

### 1.3 关键决策

| 决策项       | 选择                                                       |
| ------------ | ---------------------------------------------------------- |
| 删除策略     | `ON DELETE SET NULL`（删除行业类型时，客户记录的字段设为 NULL） |
| 历史数据处理 | 无法匹配的 `industry` 值设为 NULL                              |
| 迁移策略     | 完整替换，删除旧 `industry` 列                                 |

---

## 2. 数据库迁移设计

### 2.1 迁移步骤

```python
def upgrade():
    # Step 1: 新增 industry_type_id 列（允许 NULL）
    op.add_column('customer_profiles',
        sa.Column('industry_type_id', sa.Integer(), nullable=True))
    
    # Step 2: 数据回填 - 根据 industry 名称匹配 industry_types.id
    op.execute("""
        UPDATE customer_profiles cp
        SET industry_type_id = it.id
        FROM industry_types it
        WHERE cp.industry = it.name
    """)
    
    # Step 3: 添加外键约束（ON DELETE SET NULL）
    op.create_foreign_key(
        'fk_customer_profiles_industry_type',
        'customer_profiles', 'industry_types',
        ['industry_type_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Step 4: 删除旧的 industry 列
    op.drop_column('customer_profiles', 'industry')

def downgrade():
    # 反向操作：恢复 industry 列，从 industry_types 回填名称
    op.add_column('customer_profiles',
        sa.Column('industry', sa.String(length=100), nullable=True))
    op.execute("""
        UPDATE customer_profiles cp
        SET industry = it.name
        FROM industry_types it
        WHERE cp.industry_type_id = it.id
    """)
    op.drop_constraint('fk_customer_profiles_industry_type', 'customer_profiles')
    op.drop_column('customer_profiles', 'industry_type_id')
```

### 2.2 风险评估

| 风险项                   | 缓解措施                                         |
| ------------------------ | ------------------------------------------------ |
| 无法匹配的 industry 值   | 设为 NULL，迁移后通过查询确认数量                |
| 迁移过程中服务中断       | 迁移脚本短小，预计执行时间 < 1 秒                |
| 旧列删除后无法恢复       | downgrade 脚本已编写，可随时回滚                 |

---

## 3. 后端模型改造

### 3.1 CustomerProfile 模型变更

**文件**: `backend/app/models/customers.py`

**变更前**:
```python
class CustomerProfile(BaseModel):
    __tablename__ = "customer_profiles"
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), unique=True)
    scale_level = Column(String(50))
    consume_level = Column(String(50))
    industry = Column(String(100))  # 纯字符串
    is_real_estate = Column(Boolean, default=False)
    description = Column(Text)
    # ... 其他字段
    
    customer = relationship("Customer", back_populates="profile")
    tags = relationship("ProfileTag", back_populates="profile", lazy="selectin")
```

**变更后**:
```python
class CustomerProfile(BaseModel):
    __tablename__ = "customer_profiles"
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), unique=True)
    scale_level = Column(String(50))
    consume_level = Column(String(50))
    industry_type_id = Column(Integer, ForeignKey("industry_types.id", ondelete="SET NULL"), nullable=True)
    is_real_estate = Column(Boolean, default=False)
    description = Column(Text)
    # ... 其他字段
    
    customer = relationship("Customer", back_populates="profile")
    industry_type = relationship("IndustryType")  # 新增关联
    tags = relationship("ProfileTag", back_populates="profile", lazy="selectin")
```

### 3.2 需要 import 的模型

确保 `IndustryType` 在 relationship 中可用（可能需要延迟导入或调整模型加载顺序）。

---

## 4. 后端 API 改造

### 4.1 列表接口 `GET /api/v1/customers`

**文件**: `backend/app/routes/customers.py`

**改动**: JOIN 查询返回行业类型名称，保持向后兼容

```python
# 返回数据中（第 107 行附近）:
"industry": c.profile.industry_type.name if (c.profile and c.profile.industry_type) else None,
```

**筛选逻辑**: 保持不变，仍通过 `industry` 参数按名称匹配（在 `CustomerService` 中处理）

### 4.2 详情接口 `GET /api/v1/customers/<id>`

**改动**: 返回 `industry_type_id` + `industry` 名称

```python
# profile 对象中（第 182 行附近）:
"industry_type_id": customer.profile.industry_type_id,
"industry": customer.profile.industry_type.name if customer.profile.industry_type else None,
```

### 4.3 创建接口 `POST /api/v1/customers`

**改动**: 接受 `industry_type_id` 参数，验证外键存在性

```python
# 在 create_customer 路由中（第 248 行附近）:
industry_type_id = data.get("industry_type_id")
if industry_type_id is not None:
    from ..models.industry_type import IndustryType
    from sqlalchemy import select
    result = await db_session.execute(
        select(IndustryType).where(IndustryType.id == industry_type_id)
    )
    if not result.scalar_one_or_none():
        return json({"code": 40004, "message": "行业类型不存在"}, status=400)
```

**CustomerService.create_customer**: 传递 `industry_type_id` 到 profile 创建逻辑

### 4.4 更新接口 `PUT /api/v1/customers/<id>`

**改动**: 同创建接口，验证 `industry_type_id` 存在性

### 4.5 画像接口 `PUT /api/v1/customers/<id>/profile`

**改动**: 接受 `industry_type_id` 替代 `industry`

```python
# 请求体示例:
{
    "scale_level": "B",
    "consume_level": "C2",
    "industry_type_id": 3,  # 替代原来的 "industry": "房产ERP"
    "is_real_estate": true,
    "description": "..."
}
```

### 4.6 导出接口 `GET /api/v1/customers/export`

**改动**: JOIN 查询返回行业类型名称

```python
# 第 740 行附近:
"industry": c.profile.industry_type.name if (c.profile and c.profile.industry_type) else None,
```

### 4.7 导入接口 `POST /api/v1/customers/import`

**改动**: Excel 中的 `industry` 列需查找 `industry_types` 表转换为 `industry_type_id`

```python
# 在导入处理逻辑中（第 540 行附近）:
industry_name = row.get("industry")
if industry_name:
    from ..models.industry_type import IndustryType
    from sqlalchemy import select
    result = await db_session.execute(
        select(IndustryType).where(IndustryType.name == industry_name)
    )
    it = result.scalar_one_or_none()
    if not it:
        errors.append(f"第 {idx} 行：行业类型 '{industry_name}' 不存在")
        continue
    row["industry_type_id"] = it.id
    del row["industry"]  # 移除旧字段
```

### 4.8 CustomerService 改造

**文件**: `backend/app/services/customers.py`

需要修改的方法：
- `create_customer`: 接受 `industry_type_id` 替代 `industry`
- `update_customer`: 同上
- `create_or_update_profile`: 同上
- `get_all_customers`: 筛选逻辑兼容 `industry` 参数（按名称 JOIN 查询）

---

## 5. 前端改造

### 5.1 客户列表页 `frontend/src/views/customers/Index.vue`

#### 5.1.1 筛选区（第 98-115 行）

**保持不变**: 仍用 `item.name` 作为 value，后端筛选逻辑兼容 name 匹配

```vue
<a-select v-model="filters.industry" multiple>
  <a-option v-for="item in industryTypes" :key="item.id" :value="item.name">
    {{ item.name }}
  </a-option>
</a-select>
```

#### 5.1.2 列表列定义（第 566 行）

**保持不变**: 后端返回的 `industry` 字段仍为名称字符串

```javascript
{ title: '行业类型', dataIndex: 'industry', width: 120 }
```

#### 5.1.3 新增/编辑弹窗（第 326-340 行）

**改动**: 改用 `industry_type_id` 绑定

```vue
<a-form-item field="industry_type_id" label="行业类型">
  <a-select v-model="editForm.industry_type_id" placeholder="请选择行业类型" allow-clear>
    <a-option v-for="item in industryTypes" :key="item.id" :value="item.id">
      {{ item.name }}
    </a-option>
  </a-select>
</a-form-item>
```

**表单提交逻辑**: 提交 `industry_type_id` 到后端

### 5.2 客户详情页 `frontend/src/views/customers/Detail.vue`

#### 5.2.1 编辑表单（第 396-400 行）

**改动**: 改用 `industry_type_id` 绑定

```vue
<a-form-item field="industry_type_id" label="行业类型">
  <a-select v-model="editForm.industry_type_id" placeholder="请选择行业类型" allow-clear :loading="industryTypesLoading">
    <a-option v-for="type in industryTypes" :key="type.id" :value="type.id">
      {{ type.name }}
    </a-option>
  </a-select>
</a-form-item>
```

#### 5.2.2 详情显示（第 51 行）

**保持不变**: 显示行业类型名称

```vue
<span class="label">行业类型</span>
<span class="value">{{ customer.profile?.industry || '-' }}</span>
```

### 5.3 余额页 `frontend/src/views/billing/Balance.vue`

**筛选区**: 同列表页，保持 name 匹配，无需改动

### 5.4 TypeScript 类型定义 `frontend/src/types/index.ts`

**改动**: 更新 `CustomerProfile` 接口

```typescript
export interface CustomerProfile {
  id: number
  customer_id: number
  scale_level: string | null
  consume_level: string | null
  industry_type_id: number | null  // 新增
  industry?: string                 // 保留用于显示名称（向后兼容）
  is_real_estate: boolean
  description: string | null
  // ... 其他字段
}
```

---

## 6. 数据流图

```
系统设置-行业类型 (industry_types 表)
    ↓ CRUD 管理
    ↓ 提供 /api/v1/industry-types 和 /api/v1/dicts/industry_types
    ↓
客户管理页面
    ├── 筛选项：调用 /dicts/industry_types → 下拉选项 → 传 name 给后端筛选
    ├── 列表显示：后端 JOIN 查询 → 返回 industry 名称字符串
    ├── 新增/编辑：选择 industry_type_id → 提交给后端 → 验证外键存在性
    └── 删除行业类型：外键 ON DELETE SET NULL → 客户 industry_type_id 变 NULL
```

---

## 7. 测试策略

### 7.1 迁移测试

| 测试项                     | 验证方法                                         |
| -------------------------- | ------------------------------------------------ |
| 数据回填正确性             | 迁移后查询 `industry_type_id IS NOT NULL` 的数量 |
| 无法匹配的值设为 NULL      | 查询 `industry IS NOT NULL AND industry_type_id IS NULL` 的数量 |
| 外键约束生效               | 尝试插入不存在的 `industry_type_id`，应报错      |
| ON DELETE SET NULL 生效    | 删除行业类型后，关联客户的 `industry_type_id` 应为 NULL |

### 7.2 单元测试

| 测试项                     | 验证方法                                         |
| -------------------------- | ------------------------------------------------ |
| industry_type_id 验证逻辑  | 传入不存在的 ID，应返回 400                      |
| 创建客户时关联行业类型     | 创建后查询详情，应返回正确的行业类型名称         |
| 更新客户时修改行业类型     | 更新后查询详情，应返回新的行业类型名称           |
| 删除行业类型后客户数据     | 删除后查询客户详情，industry 应为 NULL           |

### 7.3 集成测试

| 测试项                     | 验证方法                                         |
| -------------------------- | ------------------------------------------------ |
| 列表筛选按行业类型名称     | 筛选后返回的客户应匹配指定行业类型               |
| 导出文件包含行业类型名称   | 导出 Excel 中 industry 列应为名称字符串          |
| 导入时行业类型名称转换     | 导入包含有效行业类型名称的 Excel，应成功创建     |
| 导入时行业类型名称不存在   | 导入包含无效行业类型名称的 Excel，应报错         |

### 7.4 E2E 测试

| 测试项                     | 验证方法                                         |
| -------------------------- | ------------------------------------------------ |
| 前端表单绑定               | 新增客户时选择行业类型，提交后列表应显示正确名称 |
| 筛选功能                   | 筛选行业类型后，列表应只显示匹配的客户           |
| 列表显示                   | 列表页行业类型列应显示名称而非 ID                |

---

## 8. 实施步骤

### Phase 1: 数据库迁移

1. 创建 Alembic 迁移脚本
2. 本地测试迁移（先备份数据）
3. 验证数据回填正确性
4. 确认外键约束生效

### Phase 2: 后端改造

1. 修改 `CustomerProfile` 模型
2. 修改 `CustomerService` 相关方法
3. 更新所有 API 端点
4. 更新单元测试

### Phase 3: 前端改造

1. 修改列表页表单绑定
2. 修改详情页表单绑定
3. 更新 TypeScript 类型定义
4. 验证 UI 交互

### Phase 4: 验证与清理

1. 运行完整测试套件
2. 端到端测试验证
3. 确认无遗留的 `industry` 字符串引用
4. 更新文档

---

## 9. 回滚方案

如果迁移或改造出现问题：

1. **数据库回滚**: 运行 `alembic downgrade -1`，恢复 `industry` 列
2. **代码回滚**: 回退 git commit，恢复旧版本代码
3. **数据恢复**: 迁移脚本的 downgrade 会自动回填 `industry` 名称

---

## 10. 注意事项

1. **迁移前备份**: 执行迁移前务必备份数据库
2. **缓存清理**: 迁移后需清理客户列表缓存
3. **Excel 模板更新**: 导入模板的说明行需更新，提示行业类型必须是系统设置中已存在的值
4. **审计日志**: 行业类型变更应记录到审计日志中
