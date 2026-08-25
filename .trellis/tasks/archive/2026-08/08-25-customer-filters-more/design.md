# Design: 客户管理筛选器增加更多筛选项

## Architecture

本任务分为两个独立交付物：
1. **ERP 系统管理模块** — 仿照 `IndustryType` / `CooperationStatus` 的完整字典管理模块
2. **客户筛选器 UI 改造** — `CustomerFilters.vue` 增加"更多"展开/收起 + 三个新筛选项

## Data Flow

### ERP 系统管理模块数据流

```
ErpSystems.vue → erpSystems.ts API → erp_system_routes.py → ErpSystemService → ErpSystem model
```

### 客户筛选器数据流

```
Index.vue
  ├── useCustomerList.ts (filters.erp_system, filters.cooperation_status)
  ├── loadErpSystems() → getErpSystemsList() → /api/v1/erp-systems
  ├── loadCooperationStatuses() → getCooperationStatusesList() → /api/v1/cooperation-statuses
  └── CustomerFilters.vue (props: erpSystems, cooperationStatuses)
        ├── FilterDropdown "ERP系统" → filters.erp_system
        ├── FilterDropdown "合作状态" → filters.cooperation_status
        └── FilterDropdown "结算方式" → filters.settlement_type
              ↓ handleSearch()
        useCustomerList.buildParams() → GET /api/v1/customers?erp_system=xxx&cooperation_status=yyy
              ↓
        list_customers route → CustomerService.get_all_customers(filters)
```

## Contracts

### ErpSystem Model (`backend/app/models/erp_system.py`)

```python
class ErpSystem(BaseModel):
    __tablename__ = "erp_systems"
    name = Column(String(100), unique=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
```

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/erp-systems` | auth_required | 列表 |
| POST | `/api/v1/erp-systems` | `erp_systems:manage` | 创建 |
| PUT | `/api/v1/erp-systems/<id>` | `erp_systems:manage` | 更新 |
| DELETE | `/api/v1/erp-systems/<id>` | `erp_systems:manage` | 软删除 |

### Frontend Types

```typescript
interface ErpSystem {
  id: number
  name: string
  sort_order: number
  created_at?: string
}
```

### CustomerFilters Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ [搜索框] [账号类型] [行业] [规模等级] [消费等级] [运营经理] [销售经理] [更多▼] [筛选] │
│ [ERP系统] [合作状态] [结算方式]                                    │ ← 展开时显示
└─────────────────────────────────────────────────────────────────┘
```

- 首行使用 `display: flex; flex-wrap: nowrap`（或 wrap），"筛选"按钮用 `margin-left: auto` 固定右侧
- 展开行使用 `display: flex; flex-wrap: wrap; gap: 8px`，左对齐

## Compatibility & Migration

- 新增 `erp_systems` 表，不修改现有表结构
- Customer 模型的 `erp_system` 字段保持 VARCHAR 不变（不改为外键）
- `EditCustomerDialog.vue` 中 ERP 系统选项来源切换为 API，不影响已存数据
- Alembic 迁移 down_revision 指向当前最新版本

## Trade-offs

- **ERP 系统字段不做外键关联**：Customer.erp_system 保持字符串，与 ErpSystem.name 对应。优点是不需要数据迁移，缺点是无法保证引用完整性。在 MVP 阶段可接受。
- **展开/收起不持久化到 localStorage**：每次进入页面默认收起。简化实现，后续可加。
