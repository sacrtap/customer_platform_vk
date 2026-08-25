# Implementation Plan: 客户管理筛选器增加更多筛选项

## Ordered Checklist

### Phase 1: 后端 — ERP 系统管理模块

- [ ] 1.1 创建 `ErpSystem` 模型 (`backend/app/models/erp_system.py`)
- [ ] 1.2 在 `backend/app/models/__init__.py` 注册模型
- [ ] 1.3 创建 Alembic 迁移脚本（创建 `erp_systems` 表）
- [ ] 1.4 创建 `ErpSystemService` (`backend/app/services/erp_system_service.py`)
- [ ] 1.5 创建路由 (`backend/app/routes/erp_system_routes.py`)
- [ ] 1.6 在 `backend/app/app.py` 注册 Blueprint
- [ ] 1.7 在权限种子数据中添加 `erp_systems:manage` 权限
- [ ] 1.8 验证：运行迁移，测试 API

### Phase 2: 前端 — ERP 系统管理页面

- [ ] 2.1 创建类型定义 `ErpSystem` (`frontend/src/types/index.ts`)
- [ ] 2.2 创建 API 模块 (`frontend/src/api/erpSystems.ts`)
- [ ] 2.3 创建管理页面 (`frontend/src/views/system/ErpSystems.vue`) — 参考 `IndustryTypes.vue`
- [ ] 2.4 在路由中注册 (`frontend/src/router/index.ts`)
- [ ] 2.5 在侧边栏导航添加入口
- [ ] 2.6 验证：页面可正常 CRUD

### Phase 3: 后端 — 客户筛选支持

- [ ] 3.1 `list_customers` 路由接收 `erp_system` 和 `cooperation_status` 参数
- [ ] 3.2 `get_all_customers` 服务方法处理新筛选条件
- [ ] 3.3 验证：API 筛选正确

### Phase 4: 前端 — 筛选器 UI 改造

- [ ] 4.1 `useCustomerList.ts` 新增 `erp_system` 和 `cooperation_status` 字段
- [ ] 4.2 `CustomerFilters.vue` 重构布局：首行 + "更多"按钮 + 展开行 + "筛选"按钮固定右侧
- [ ] 4.3 `CustomerFilters.vue` 新增三个 FilterDropdown（ERP系统、合作状态、结算方式）
- [ ] 4.4 `CustomerFilters.vue` 新增 `cooperationStatuses` 和 `erpSystems` props
- [ ] 4.5 `Index.vue` 加载 ERP 系统和合作状态数据并传递给 `CustomerFilters`
- [ ] 4.6 验证：展开/收起交互正常，筛选功能正确

### Phase 5: EditCustomerDialog 同步改造

- [ ] 5.1 `EditCustomerDialog.vue` ERP 系统选项来源改为 `getErpSystemsList()`
- [ ] 5.2 验证：编辑客户弹窗 ERP 系统下拉正确

### Phase 6: 质量检查

- [ ] 6.1 后端 linter 检查
- [ ] 6.2 前端 linter 检查
- [ ] 6.3 后端单元测试（如有）
- [ ] 6.4 手动验证全部验收标准

## Validation Commands

```bash
# 后端迁移
cd backend && alembic upgrade head

# 后端 linter
cd backend && ruff check app/ --fix

# 前端 linter
cd frontend && npx tsc --noEmit

# 后端测试
cd backend && python -m pytest tests/ -v
```

## Risky Files / Rollback Points

- `backend/app/models/__init__.py` — 模型注册，影响 SQLAlchemy metadata
- `backend/app/app.py` — Blueprint 注册
- `backend/alembic/versions/` — 迁移脚本，down_revision 需正确
- `frontend/src/router/index.ts` — 路由配置
- `frontend/src/composables/useCustomerList.ts` — 筛选状态管理，影响整个客户列表页
- `frontend/src/views/customers/components/CustomerFilters.vue` — 核心 UI 改造
- `frontend/src/views/customers/Index.vue` — 数据加载和 props 传递

## Rollback Plan

- 后端：`alembic downgrade -1` 回滚迁移
- 前端：git revert 相关 commit
- ERP 系统模块为新增，不影响现有功能
- 筛选器改造如有问题，可回退到原有 flex-wrap 布局
