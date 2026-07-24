# 技术债务重构设计文档

**创建日期**: 2026-06-29
**目标**: 解决高优先级技术债务 TD-001（后端单文件过大）和 TD-002（前端单文件过大）
**拆分策略**: 按业务功能完全模块化拆分
**目标文件大小**: 200-300 行

---

## 1. 概述

### 1.1 问题描述

当前项目存在 10 个超大文件，严重影响可维护性和团队协作：

**后端（5 个文件）**:
- `backend/app/routes/billing.py` - 1910 行
- `backend/app/services/analytics.py` - 1307 行
- `backend/app/services/billing.py` - 994 行
- `backend/app/routes/customers.py` - 949 行
- `backend/app/services/customers.py` - 917 行

**前端（5 个文件）**:
- `frontend/src/views/customers/Detail.vue` - 2331 行
- `frontend/src/views/customers/Index.vue` - 2026 行
- `frontend/src/views/Dashboard.vue` - 1689 行
- `frontend/src/views/billing/Balance.vue` - 1373 行
- `frontend/src/views/billing/Invoices.vue` - 1037 行

### 1.2 拆分原则

1. **单一职责**: 每个文件只负责一个明确的业务功能
2. **业务边界清晰**: 按业务模块组织，而非技术层次
3. **路由和服务对应**: 后端路由和服务层拆分保持一致
4. **最小影响**: 保持 API 接口不变，仅重构内部实现
5. **渐进式验证**: 每完成一个模块立即验证，确保功能正常

### 1.3 目标文件大小

- **后端**: 200-300 行（Python 文件）
- **前端**: 200-300 行（Vue 组件）

---

## 2. 后端拆分方案

### 2.1 billing 模块拆分

#### 2.1.1 routes/billing.py → routes/billing/

**原文件**: 1910 行
**拆分后**: 4 个文件，每个 300-500 行

| 新文件 | 行数 | 功能 | 包含的路由 |
|--------|------|------|-----------|
| `billing/invoices.py` | ~450 | 结算单 CRUD | `list_invoices`, `get_invoice`, `create_invoice`, `update_invoice`, `delete_invoice`, `submit_invoice`, `confirm_invoice`, `cancel_invoice`, `mark_paid`, `complete_invoice` |
| `billing/payments.py` | ~380 | 充值/扣款 | `recharge_balance`, `deduct_balance`, `get_payment_history`, `get_payment_detail` |
| `billing/pricing.py` | ~520 | 定价规则 | `list_pricing_rules`, `create_pricing_rule`, `update_pricing_rule`, `delete_pricing_rule`, `get_pricing_rule_detail`, `batch_update_pricing_rules` |
| `billing/balance.py` | ~320 | 余额查询 | `get_customer_balance`, `get_balance_list`, `export_balance_report` |

**目录结构**:
```
backend/app/routes/billing/
├── __init__.py          # Blueprint 定义和路由收集
├── invoices.py          # 结算单路由
├── payments.py          # 充值/扣款路由
├── pricing.py           # 定价规则路由
└── balance.py           # 余额查询路由
```

**`__init__.py` 示例**:
```python
from sanic import Blueprint
from . import invoices, payments, pricing, balance

bp = Blueprint('billing', url_prefix='/api/v1/billing')

# 收集所有子模块的路由
bp.route(invoices.routes)
bp.route(payments.routes)
bp.route(pricing.routes)
bp.route(balance.routes)
```

#### 2.1.2 services/billing.py → services/billing/

**原文件**: 994 行
**拆分后**: 4 个文件，每个 180-280 行

| 新文件 | 行数 | 功能 | 包含的类/函数 |
|--------|------|------|--------------|
| `billing/balance_service.py` | ~200 | 余额服务 | `BalanceService` 类（充值、消费、余额查询） |
| `billing/pricing_service.py` | ~260 | 定价服务 | `PricingService` 类（定价规则 CRUD） |
| `billing/invoice_calculation.py` | ~200 | 结算计算 | `calculate_items_from_rules`, `_calculate_tiered_price`, `generate_invoice` |
| `billing/invoice_service.py` | ~200 | 结算单服务 | `InvoiceService` 类（状态流转、列表详情、减免申请） |

**目录结构**:
```
backend/app/services/billing/
├── __init__.py                  # 导出所有服务类
├── balance_service.py           # BalanceService（充值、消费、余额查询）
├── pricing_service.py           # PricingService（定价规则 CRUD）
├── invoice_calculation.py       # 结算计算逻辑（calculate_items_from_rules 等）
└── invoice_service.py           # InvoiceService（状态流转、列表详情、减免）
```

### 2.2 customers 模块拆分

#### 2.2.1 routes/customers.py → routes/customers/

**原文件**: 949 行
**拆分后**: 3 个文件，每个 100-370 行

| 新文件 | 行数 | 功能 | 包含的路由 |
|--------|------|------|-----------|
| `customers/crud.py` | ~280 | 客户 CRUD | `list_customers`, `get_customer`, `create_customer`, `update_customer`, `batch_update_customers`, `delete_customer` |
| `customers/profile.py` | ~100 | 画像管理 | `get_profile`, `update_profile` |
| `customers/import_export.py` | ~370 | 导入导出 | `import_customers`, `download_import_template`, `export_customers` |

**目录结构**:
```
backend/app/routes/customers/
├── __init__.py              # Blueprint 定义和路由收集
├── crud.py                  # 客户 CRUD 路由
├── profile.py               # 画像管理路由
└── import_export.py         # 导入导出路由
```

#### 2.2.2 services/customers.py → services/customers/

**原文件**: 917 行（实际约 650 行有效代码）
**拆分后**: 5 个文件，每个 100-300 行

| 新文件 | 行数 | 功能 | 包含的类/函数 |
|--------|------|------|--------------|
| `customers/constants.py` | ~130 | 数据映射常量 | `ALLOWED_SORT_FIELDS`、映射字典、辅助转换函数 |
| `customers/customer_service.py` | ~300 | 客户服务 | `CustomerService` 类（核心 CRUD 方法） |
| `customers/profile_service.py` | ~150 | 画像服务 | 画像相关方法 |
| `customers/import_export_service.py` | ~200 | 导入导出服务 | 导入导出相关方法 |
| `customers/helpers.py` | ~100 | 辅助函数 | `clear_analytics_cache` 等模块级函数 |

**目录结构**:
```
backend/app/services/customers/
├── __init__.py                  # 导出所有服务类
├── constants.py                 # 数据映射常量和辅助转换函数
├── customer_service.py          # CustomerService 类（核心 CRUD）
├── profile_service.py           # 画像相关方法
├── import_export_service.py     # 导入导出相关方法
└── helpers.py                   # clear_analytics_cache 等辅助函数
```
### 2.3 analytics 模块拆分

#### 2.3.1 services/analytics.py → services/analytics/

**原文件**: 1307 行
**拆分后**: 7 个文件，每个 100-250 行

| 新文件 | 行数 | 功能 | 包含的函数 |
|--------|------|------|-----------|
| `analytics/consumption_service.py` | ~220 | 消耗分析 | `get_consumption_stats`, `get_consumption_trend`, `get_usage_distribution` |
| `analytics/payment_service.py` | ~200 | 回款分析 | `get_payment_stats`, `get_payment_trend`, `get_overdue_analysis` |
| `analytics/health_service.py` | ~180 | 健康度分析 | `get_health_score`, `get_health_indicators`, `get_health_trend` |
| `analytics/profile_service.py` | ~240 | 画像分析 | `get_profile_stats`, `get_industry_distribution`, `get_level_distribution` |
| `analytics/forecast_service.py` | ~160 | 预测分析 | `forecast_payment`, `forecast_consumption`, `get_prediction_accuracy` |
| `analytics/helpers.py` | ~120 | 辅助函数 | 缓存清理、数据转换等公共函数 |
| `analytics/constants.py` | ~80 | 常量定义 | 分析指标映射、等级阈值等 |

**目录结构**:
```
backend/app/services/analytics/
├── __init__.py                  # 导出所有服务函数
├── consumption_service.py       # 消耗分析服务
├── payment_service.py           # 回款分析服务
├── health_service.py            # 健康度分析服务
├── profile_service.py           # 画像分析服务
├── forecast_service.py          # 预测分析服务
├── helpers.py                   # 辅助函数
└── constants.py                 # 常量定义
```

---

## 3. 前端拆分方案

### 3.1 customers/Detail.vue 拆分

**原文件**: 2331 行
**拆分后**: 5 个文件，每个 180-320 行

| 新文件 | 行数 | 功能 | 包含的内容 |
|--------|------|------|-----------|
| `detail/BasicInfoForm.vue` | ~280 | 基本信息表单 | 客户基础信息编辑表单（名称、联系人、电话、邮箱等） |
| `detail/ProfilePanel.vue` | ~320 | 画像信息面板 | 画像等级、消费等级、运营经理、商务经理等 |
| `detail/TagManager.vue` | ~240 | 标签管理 | 标签列表、添加/删除标签、可用标签筛选 |
| `detail/SettlementPanel.vue` | ~260 | 结算信息 | 结算周期、计费模式、定价规则、首次回款时间等 |
| `detail/index.vue` | ~180 | 主容器 | 组合所有子组件，管理整体状态和路由参数 |

**目录结构**:
```
frontend/src/views/customers/detail/
├── index.vue              # 主容器
├── BasicInfoForm.vue      # 基本信息表单
├── ProfilePanel.vue       # 画像信息面板
├── TagManager.vue         # 标签管理
└── SettlementPanel.vue    # 结算信息面板
```

### 3.2 customers/Index.vue 拆分

**原文件**: 2027 行
**拆分后**: 7 个文件，每个 90-290 行

| 新文件 | 行数 | 功能 | 包含的内容 |
|--------|------|------|-----------|
| `index/CustomerFilter.vue` | ~250 | 筛选区域 | 基础筛选（关键词、行业、等级）+ 高级筛选（标签、运营经理） |
| `index/CustomerTable.vue` | ~280 | 客户表格 | 表头列定义、行内操作（编辑/删除/查看）、空状态 |
| `index/BatchToolbar.vue` | ~90 | 批量操作工具栏 | 选择计数、批量编辑按钮、取消选择 |
| `index/CustomerFormModal.vue` | ~200 | 新建/编辑弹框 | 客户表单、验证、提交逻辑 |
| `index/BatchEditModal.vue` | ~290 | 批量编辑对话框 | 字段选择、预览确认、批量更新 |
| `index/CustomerImportModal.vue` | ~200 | 客户导入弹框 | 文件上传、模板下载、拖拽上传 |
| `index/index.vue` | ~180 | 主容器 | 组合子组件，管理筛选状态和表格数据 |

**目录结构**:
```
frontend/src/views/customers/index/
├── index.vue                  # 主容器
├── CustomerFilter.vue         # 筛选区域
├── CustomerTable.vue          # 客户表格
├── BatchToolbar.vue           # 批量操作工具栏
├── CustomerFormModal.vue      # 新建/编辑弹框
├── BatchEditModal.vue         # 批量编辑对话框
└── CustomerImportModal.vue    # 客户导入弹框
```

### 3.3 Dashboard.vue 拆分

**原文件**: 1689 行
**拆分后**: 5 个文件，每个 150-280 行

| 新文件 | 行数 | 功能 | 包含的内容 |
|--------|------|------|-----------|
| `dashboard/Sidebar.vue` | ~280 | 侧边栏 | 菜单导航、折叠/展开、权限控制 |
| `dashboard/Header.vue` | ~180 | 头部 | 用户信息、通知、退出登录 |
| `dashboard/UserDropdown.vue` | ~150 | 用户下拉菜单 | 用户头像、下拉选项、快捷操作 |
| `dashboard/ChangePasswordDialog.vue` | ~200 | 修改密码弹窗 | 密码表单、验证、提交逻辑 |
| `dashboard/index.vue` | ~200 | 主容器 | 组合 Sidebar、Header、ContentArea |

**目录结构**:
```
frontend/src/views/dashboard/
├── index.vue                  # 主容器
├── Sidebar.vue                # 侧边栏
├── Header.vue                 # 头部
├── UserDropdown.vue           # 用户下拉菜单
└── ChangePasswordDialog.vue   # 修改密码弹窗
```

### 3.4 billing/Balance.vue 拆分

**原文件**: 1373 行
**拆分后**: 4 个文件，每个 180-300 行

| 新文件 | 行数 | 功能 | 包含的内容 |
|--------|------|------|-----------|
| `balance/BalanceList.vue` | ~300 | 余额列表 | 表格展示、筛选、分页、批量操作 |
| `balance/RechargeDialog.vue` | ~240 | 充值弹窗 | 充值表单、金额输入、备注、确认 |
| `balance/DeductionDialog.vue` | ~220 | 扣款弹窗 | 扣款表单、金额输入、原因、确认 |
| `balance/index.vue` | ~180 | 主容器 | 组合子组件，管理余额数据和弹窗状态 |

**目录结构**:
```
frontend/src/views/billing/balance/
├── index.vue              # 主容器
├── BalanceList.vue        # 余额列表
├── RechargeDialog.vue     # 充值弹窗
└── DeductionDialog.vue    # 扣款弹窗
```

### 3.5 billing/Invoices.vue 拆分

**原文件**: 1037 行
**拆分后**: 4 个文件，每个 180-280 行

| 新文件 | 行数 | 功能 | 包含的内容 |
|--------|------|------|-----------|
| `invoices/InvoiceTable.vue` | ~280 | 结算单表格 | 表格列定义、排序、分页、状态标签 |
| `invoices/InvoiceFilter.vue` | ~200 | 筛选器 | 客户筛选、状态筛选、日期范围、金额范围 |
| `invoices/InvoiceDetail.vue` | ~260 | 详情抽屉 | 结算单详情、明细列表、操作按钮 |
| `invoices/index.vue` | ~180 | 主容器 | 组合子组件，管理查询参数和选中状态 |

**目录结构**:
```
frontend/src/views/billing/invoices/
├── index.vue              # 主容器
├── InvoiceTable.vue       # 结算单表格
├── InvoiceFilter.vue      # 筛选器
└── InvoiceDetail.vue      # 详情抽屉
```

---

## 4. 实施计划

### 4.1 分阶段实施

**第一阶段（3-4 天）**: billing 模块
1. 拆分 `routes/billing.py` → `routes/billing/`
2. 拆分 `services/billing.py` → `services/billing/`
3. 拆分 `Balance.vue` → `billing/balance/`
4. 拆分 `Invoices.vue` → `billing/invoices/`
5. 验证：运行测试套件 + 手动测试结算流程

**第二阶段（3-4 天）**: customers 模块
1. 拆分 `routes/customers.py` → `routes/customers/`
2. 拆分 `services/customers.py` → `services/customers/`
3. 拆分 `Detail.vue` → `customers/detail/`
4. 拆分 `Index.vue` → `customers/index/`
5. 验证：运行测试套件 + 手动测试客户管理流程

**第三阶段（2-3 天）**: analytics + dashboard
1. 拆分 `services/analytics.py` → `services/analytics/`
2. 拆分 `Dashboard.vue` → `dashboard/`
3. 验证：运行测试套件 + 手动测试数据分析功能

### 4.2 每个文件的拆分步骤

1. **分析依赖**: 使用 codegraph 分析文件的依赖关系
2. **创建目录**: 创建新的子目录结构
3. **提取代码**: 按功能分组提取代码到新文件
4. **更新导入**: 更新所有引用该文件的 import 语句
5. **验证功能**: 运行测试 + 手动验证关键功能
6. **提交代码**: 每个文件拆分后立即提交

### 4.3 验证策略

**自动化验证**:
```bash
# 后端测试
cd backend && pytest tests/ -v --cov=app --cov-fail-under=50

# 前端测试
cd frontend && npm run test:coverage

# E2E 测试
cd frontend && npm run test:e2e
```

**手动验证**:
- 结算流程：创建结算单 → 提交 → 确认 → 付款 → 完成
- 客户管理：创建客户 → 编辑信息 → 导入/导出 → 删除
- 数据分析：查看消耗分析 → 回款分析 → 健康度分析

**依赖验证**:
```bash
# 使用 codegraph 验证依赖完整性
codegraph explore "billing routes" --verify
codegraph explore "customers services" --verify
```

---

## 5. 风险与缓解

### 5.1 风险识别

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 导入路径错误 | 高 | 中 | 每个文件拆分后立即运行测试 |
| 循环依赖 | 高 | 低 | 使用 codegraph 提前分析依赖关系 |
| 功能遗漏 | 中 | 中 | 对照原文件逐行检查，确保所有功能都已迁移 |
| 测试失败 | 中 | 中 | 保持测试覆盖率 ≥50%，失败时立即修复 |
| 性能下降 | 低 | 低 | 文件拆分不影响运行时性能，仅影响开发体验 |

### 5.2 回滚策略

- 每个阶段完成后提交到 Git
- 如果某个阶段出现问题，可以回滚到上一个稳定版本
- 保留原文件作为参考，直到所有验证通过

---

## 6. 成功标准

### 6.1 量化指标

- ✅ 所有 10 个大文件都拆分到 200-300 行
- ✅ 后端测试覆盖率 ≥50%
- ✅ 前端测试覆盖率 ≥50%
- ✅ E2E 测试全部通过
- ✅ 无循环依赖
- ✅ 所有 API 接口保持不变

### 6.2 质量指标

- ✅ 代码可读性提升（通过代码审查验证）
- ✅ 文件职责单一（每个文件只做一件事）
- ✅ 模块边界清晰（路由和服务一一对应）
- ✅ 便于团队协作（不同人负责不同模块）

---

## 7. 附录

### 7.1 文件行数统计

**拆分前**:
| 文件 | 行数 |
|------|------|
| backend/app/routes/billing.py | 1910 |
| backend/app/services/analytics.py | 1307 |
| backend/app/services/billing.py | 994 |
| backend/app/routes/customers.py | 949 |
| backend/app/services/customers.py | 917 |
| frontend/src/views/customers/Detail.vue | 2331 |
| frontend/src/views/customers/Index.vue | 2026 |
| frontend/src/views/Dashboard.vue | 1689 |
| frontend/src/views/billing/Balance.vue | 1373 |
| frontend/src/views/billing/Invoices.vue | 1037 |

**拆分后（预计）**:
| 模块 | 文件数 | 平均行数 |
|------|--------|---------|
| billing routes | 4 | ~420 |
| billing services | 4 | ~240 |
| customers routes | 3 | ~250 |
| customers services | 3 | ~270 |
| analytics services | 5 | ~200 |
| Detail.vue | 5 | ~260 |
| Index.vue | 4 | ~260 |
| Dashboard.vue | 4 | ~270 |
| Balance.vue | 4 | ~240 |
| Invoices.vue | 4 | ~230 |

### 7.2 依赖关系图

使用 codegraph 生成的依赖关系图（略）

---

**文档版本**: 1.0
**最后更新**: 2026-06-29
**审核状态**: 待审核
