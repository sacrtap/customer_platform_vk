# 客户详情字段补充设计文档

**创建日期**: 2026-04-14
**状态**: 待审查
**作者**: AI Assistant (brainstorming 流程)

---

## 1. 背景与目标

### 1.1 背景
业务部门提供了一份 Excel 数据表 (`docs/data.xlsx`)，包含 36 列客户相关数据。对比现有系统后发现，当前客户详情页缺少多个业务必要字段，影响运营效率和数据分析能力。

### 1.2 目标
在客户详情页的"基础信息"和"画像信息"两个 Tab 中补充核心业务字段，使系统数据与业务实际需求对齐。

---

## 2. 现状分析

### 2.1 Excel 数据源（36 列）

| 类别 | 字段 |
|------|------|
| **基础标识** | 公司id, 公司名称 |
| **账号属性** | App配置, 账号类型, 行业类型, 所属ERP, 客户等级 |
| **时间信息** | 首次回款时间, 接入时间 |
| **负责人** | 销售负责人, 运营负责人 |
| **状态标志** | 合作状态, 是否结算, 是否停用 |
| **定价** | 单层定价, 多层定价 |
| **画像指标** | 客户消费等级, 月均拍摄量, 月均拍摄量（测算）, 预估年消费, 25年实际消费 |
| **用量** | 全年合计, 1-12月数量 |
| **其他** | 备注, 销售负责人, 运营负责人, 合作状态, 是否结算, 是否停用 |

### 2.2 现有系统字段

**customers 表已有**：
`company_id, name, account_type, business_type, customer_level, price_policy, manager_id, settlement_cycle, settlement_type, is_key_customer, email`

**customer_profiles 表已有**：
`customer_id, scale_level, consume_level, industry, is_real_estate, description`

### 2.3 缺失字段差距分析

| Excel 字段 | 当前映射 | 状态 |
|------------|---------|------|
| 所属ERP | 无 | ❌ 缺失 |
| 首次回款时间 | 无 | ❌ 缺失 |
| 接入时间 | 无 (有 created_at 但不等同) | ❌ 缺失 |
| 销售负责人 | 无 (仅有 manager_id 运营负责人) | ❌ 缺失 |
| 合作状态 | 无 | ❌ 缺失 |
| 是否结算 | 无 | ❌ 缺失 |
| 是否停用 | 无 | ❌ 缺失 |
| 备注 | 无 (profile.description 存在但基础信息页无) | ❌ 缺失 |
| 月均拍摄量 | 无 | ❌ 缺失 |
| 月均拍摄量（测算） | 无 | ❌ 缺失 |
| 预估年消费 | 无 | ❌ 缺失 |
| 25年实际消费 | 无 | ❌ 缺失 |

---

## 3. 方案选型

### 3.1 方案对比

| 方案 | 字段数 | 复杂度 | 业务价值 | 推荐度 |
|------|--------|--------|---------|--------|
| A. 核心必要字段 | 12 个 | 中 | 高 | ⭐⭐⭐⭐⭐ |
| B. 全量字段 | 14+ 个 | 高 | 中 | ⭐⭐⭐ |
| C. 最小化 | 4 个 | 低 | 中 | ⭐⭐⭐ |

### 3.2 选定方案：A（核心必要字段）

选择理由：
- 覆盖 Excel 中除用量月份明细外的所有核心业务数据
- 用量月份数据已通过 `daily_usage` 表存储，无需重复
- 定价字段属于 `pricing_rules` 表职责，不在本次范围
- 平衡了业务价值与实现复杂度

---

## 4. 详细设计

### 4.1 数据库设计

#### 4.1.1 customers 表新增字段

| 字段名 | 类型 | 约束 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `erp_system` | String(100) | nullable | NULL | 所属 ERP 系统名称 |
| `first_payment_date` | Date | nullable | NULL | 首次回款时间 |
| `onboarding_date` | Date | nullable | NULL | 客户接入时间 |
| `sales_manager_id` | Integer | FK→users.id, nullable, index | NULL | 销售负责人 ID |
| `cooperation_status` | String(50) | nullable, index | 'active' | 合作状态：active/suspended/terminated |
| `is_settlement_enabled` | Boolean | nullable | True | 是否启用结算 |
| `is_disabled` | Boolean | nullable, index | False | 是否停用 |
| `notes` | Text | nullable | NULL | 备注信息 |

#### 4.1.2 customer_profiles 表新增字段

| 字段名 | 类型 | 约束 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `monthly_avg_shots` | Integer | nullable | NULL | 月均拍摄量（实际值） |
| `monthly_avg_shots_estimated` | Integer | nullable | NULL | 月均拍摄量（测算值） |
| `estimated_annual_spend` | Numeric(12,2) | nullable | NULL | 预估年消费金额 |
| `actual_annual_spend_2025` | Numeric(12,2) | nullable | NULL | 2025年实际消费金额 |

### 4.2 索引设计

```python
# customers 表新增索引
Index("idx_customer_sales_manager", "sales_manager_id")
Index("idx_customer_cooperation_status", "cooperation_status")
Index("idx_customer_disabled", "is_disabled")

# customer_profiles 表无需新增索引（字段用于展示，非高频筛选）
```

### 4.3 API 设计

#### 4.3.1 现有 API 扩展

**GET /api/v1/customers/:id**
- 响应新增 8 个字段
- 无需新增端点

**PATCH /api/v1/customers/:id**
- 请求体新增 8 个可更新字段
- 权限校验：`customers:write`

**GET /api/v1/customers/:id/profile**
- 响应新增 4 个字段
- 无需新增端点

**PATCH /api/v1/customers/:id/profile**
- 请求体新增 4 个可更新字段
- 权限校验：`profiles:write`

### 4.4 前端设计

#### 4.4.1 基础信息 Tab 新增行

在现有表格中插入以下行（按逻辑顺序排列）：

| 行位置 | 标签 | 展示形式 | 数据源 |
|--------|------|---------|--------|
| 客户名称后 | 所属 ERP | 文本标签 | `customer.erp_system` |
| 账号类型后 | 合作状态 | Tag 标签 (绿/黄/红) | `customer.cooperation_status` |
| 行业类型后 | 销售负责人 | 文本（关联 users 表） | `customer.sales_manager_id` → user.real_name |
| 客户等级后 | 是否结算 | Switch 开关 | `customer.is_settlement_enabled` |
| 重点客户后 | 是否停用 | Switch 开关 | `customer.is_disabled` |
| 结算方式后 | 首次回款时间 | 日期格式化文本 | `customer.first_payment_date` |
| 结算周期后 | 接入时间 | 日期格式化文本 | `customer.onboarding_date` |
| 邮箱后 | 备注 | 多行文本（可展开） | `customer.notes` |

#### 4.4.2 画像信息 Tab 新增指标卡片

在现有 2x2 网格下方新增第 2 行（或扩展为 2x3/2x4 网格）：

| 卡片 | 标签 | 数据源 | 样式 |
|------|------|--------|------|
| 第 5 卡 | 月均拍摄量（实际） | `profile.monthly_avg_shots` | 普通卡片 |
| 第 6 卡 | 月均拍摄量（测算） | `profile.monthly_avg_shots_estimated` | 普通卡片 |
| 第 7 卡 | 预估年消费 | `profile.estimated_annual_spend` | 普通卡片（货币格式化） |
| 第 8 卡 | 25年实际消费 | `profile.actual_annual_spend_2025` | 普通卡片（货币格式化） |

#### 4.4.3 编辑对话框更新

**编辑客户对话框**新增表单字段：
- 所属 ERP（文本输入）
- 销售负责人（下拉选择，复用 managers 加载逻辑）
- 合作状态（下拉选择：活跃/暂停/终止）
- 首次回款时间（日期选择器）
- 接入时间（日期选择器）
- 是否结算（Switch）
- 是否停用（Switch）
- 备注（多行文本域）

**编辑画像对话框**（如需）新增：
- 月均拍摄量（实际）（数字输入）
- 月均拍摄量（测算）（数字输入）
- 预估年消费（数字输入，2位小数）
- 25年实际消费（数字输入，2位小数）

---

## 5. 影响分析

### 5.1 影响文件清单

根据 Graphify 知识图谱分析：

| 层级 | 文件 | 变更类型 |
|------|------|---------|
| **Model** | `backend/app/models/customers.py` | 新增字段定义 |
| **Migration** | `backend/alembic/versions/xxx_.py` | 新建迁移脚本 |
| **Type** | `frontend/src/types/index.ts` | Customer/CustomerProfile 接口扩展 |
| **API** | `frontend/src/api/customers.ts` | 无需变更（字段自动透传） |
| **View** | `frontend/src/views/customers/Detail.vue` | 模板+脚本更新 |
| **Test** | `backend/tests/` | 测试数据更新 |

### 5.2 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 字段 nullable 导致空值展示 | 低 | 前端使用 `-` 占位符 |
| sales_manager_id 外键约束 | 中 | 确保 users 表数据完整，允许 NULL |
| 编辑表单复杂度增加 | 低 | 分组展示，基础/高级可折叠 |
| 性能影响 | 极低 | 仅新增 12 个字段，单表查询 |

---

## 6. 实现优先级

### Phase 1（核心）
1. 数据库迁移脚本
2. Model 层更新
3. TypeScript 类型定义
4. 前端展示（只读）

### Phase 2（增强）
5. 前端编辑功能
6. Excel 导入/导出适配

### Phase 3（可选）
7. 画像指标自动化计算（基于用量数据）
8. 字段筛选/列表展示

---

## 7. 验收标准

- [ ] 数据库迁移成功执行，无数据丢失
- [ ] 客户详情页基础信息 Tab 展示所有新增字段
- [ ] 客户详情页画像信息 Tab 展示所有新增指标
- [ ] 编辑对话框可更新所有新增字段
- [ ] TypeScript 类型检查通过（无 any）
- [ ] 后端测试覆盖率不下降
- [ ] 前端 lint/format/type-check 通过
