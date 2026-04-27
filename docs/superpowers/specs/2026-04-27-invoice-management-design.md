# 结算单管理功能设计文档

**创建日期**: 2026-04-27  
**状态**: 已确认  
**相关模块**: 结算管理 (Billing)

---

## 1. 背景与现状

### 1.1 已完成部分
- ✅ 后端 API 完整实现（列表、详情、生成、折扣、提交、确认、付款、完成、删除、导出）
- ✅ 前端 API 封装 (`frontend/src/api/billing.ts`)
- ✅ 首页展示最近结算单列表（只读）
- ✅ 客户详情页结算单 tab（只读）

### 1.2 缺失部分
- ❌ 独立的结算单管理页面（列表 + 详情 + 操作）
- ❌ 路由配置 `/billing/invoices`
- ❌ 侧边栏导航入口
- ❌ 前端状态映射与后端不匹配
- ❌ 部分权限校验缺失

### 1.3 已知问题
| 问题 | 位置 | 影响 |
|------|------|------|
| 状态类型不匹配 | 前端 TypeScript 类型 vs 后端枚举 | 状态徽章显示错误 |
| `confirm_invoice` 缺权限校验 | 后端路由 | 任何有 billing:edit 的用户都能确认 |
| `pay_invoice`/`complete_invoice` 权限过宽 | 后端路由使用 billing:edit | 应为 billing:pay |
| 发票生成任务参数错误 | `invoice_generator.py` | 自动任务运行失败 |

---

## 2. 功能范围

### 2.1 核心功能
1. **结算单列表页** - 展示、搜索、筛选、分页
2. **结算单详情页** - 完整信息展示 + 操作按钮
3. **状态流转操作** - 生成、提交、确认、付款、完成、取消
4. **折扣申请** - 修改金额及原因
5. **批量导出** - Excel 导出

### 2.2 权限设计
| 操作 | 所需权限 | 角色限制 |
|------|----------|----------|
| 查看列表/详情 | `billing:view` | 无 |
| 生成结算单 | `billing:edit` | 无 |
| 申请折扣 | `billing:edit` | 无 |
| 提交结算单 | `billing:edit` | 无 |
| **确认结算单** | `billing:confirm` | 仅限商务经理 (sales_manager_id) 或运营经理 (manager_id) |
| **标记付款** | `billing:pay` | 无（新增权限） |
| **完成结算** | `billing:pay` | 无（修改权限） |
| 删除结算单 | `billing:delete` | 无 |
| 导出结算单 | `billing:view` | 无 |

### 2.3 状态机
```
draft (草稿)
  → submit → pending_customer (待客户确认)
    → confirm → customer_confirmed (客户已确认)
      → pay → paid (已付款)
        → complete → completed (已完成)
          
任意状态 → cancel → cancelled (已取消) [仅 draft/pending_customer]
```

---

## 3. 架构设计

### 3.1 前端布局：主从布局 (Master-Detail)

```
┌─────────────────────────────────────────────────────────┐
│  结算单管理                                              │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│  列表区域 (40%)       │  详情区域 (60%)                    │
│                      │                                  │
│  ┌────────────────┐  │  ┌────────────────────────────┐  │
│  │ 搜索/筛选栏     │  │  │ 结算单头部信息               │  │
│  │ 客户/状态/期间   │  │  │ 编号、客户、期间、状态        │  │
│  └────────────────┘  │  └────────────────────────────┘  │
│  ┌────────────────┐  │  ┌────────────────────────────┐  │
│  │                │  │  │ 结算项明细表格                │  │
│  │  结算单列表     │  │  │ 设备类型/层级/数量/单价/金额   │  │
│  │                │  │  └────────────────────────────┘  │
│  │  - 编号        │  │  ┌────────────────────────────┐  │
│  │  - 客户        │  │  │ 时间线                      │  │
│  │  - 期间        │  │  │ 创建→提交→确认→付款→完成      │  │
│  │  - 金额        │  │  └────────────────────────────┘  │
│  │  - 状态        │  │  ┌────────────────────────────┐  │
│  │  - 创建时间     │  │  │ 操作按钮区                   │  │
│  │                │  │  │ 根据状态和权限动态显示          │  │
│  └────────────────┘  │  └────────────────────────────┘  │
│                      │                                  │
└──────────────────────┴──────────────────────────────────┘
```

### 3.2 组件结构

```
frontend/src/views/billing/Invoices.vue          # 主页面
frontend/src/components/invoice/
  ├── InvoiceList.vue          # 列表组件（表格 + 分页）
  ├── InvoiceFilter.vue        # 筛选组件
  ├── InvoiceDetail.vue        # 详情面板
  ├── InvoiceTimeline.vue      # 状态时间线
  ├── InvoiceActions.vue       # 操作按钮组
  └── InvoiceStatusBadge.vue   # 状态徽章
```

### 3.3 数据流

```
用户操作 → 组件 → API 调用 → 后端路由 → Service 层 → 数据库
                                    ↓
                              权限校验装饰器
                                    ↓
                              返回结果 → 前端更新状态 → UI 刷新
```

---

## 4. 详细设计

### 4.1 列表区域

#### 4.1.1 筛选条件
| 筛选项 | 类型 | 说明 |
|--------|------|------|
| 客户 | 下拉选择 | 支持搜索，对应 `customer_id` |
| 状态 | 多选下拉 | 对应 `status` |
| 结算周期 | 日期范围 | 对应 `period_start` ~ `period_end` |
| 关键字 | 文本输入 | 搜索编号/客户名称 |

#### 4.1.2 表格列
| 列名 | 字段 | 宽度 | 说明 |
|------|------|------|------|
| 结算单号 | `invoice_no` | 180px | 可点击查看详情 |
| 客户名称 | `customer_name` | 自适应 | - |
| 结算周期 | `period_start` ~ `period_end` | 160px | 格式化显示 |
| 总金额 | `total_amount` | 120px | 右对齐，货币格式 |
| 折后金额 | `final_amount` | 120px | 右对齐，有折扣时高亮 |
| 状态 | `status` | 100px | 状态徽章 |
| 创建时间 | `created_at` | 160px | - |
| 操作 | - | 120px | 查看/编辑/删除 |

#### 4.1.3 分页
- 默认每页 20 条
- 支持 10/20/50/100 切换
- 显示总数统计

### 4.2 详情区域

#### 4.2.1 头部信息
- 结算单号（带复制按钮）
- 客户名称（可跳转至客户详情）
- 结算周期
- 状态徽章
- 自动生成标识

#### 4.2.2 金额信息
| 字段 | 说明 |
|------|------|
| 总金额 | `total_amount` |
| 折扣金额 | `discount_amount`（有值时显示） |
| 折扣原因 | `discount_reason` |
| 折后金额 | `final_amount` |

#### 4.2.3 结算项明细
表格展示 `items`：
- 设备类型
- 层级类型
- 数量
- 单价
- 小计（数量 × 单价）

#### 4.2.4 时间线
按时间顺序展示关键节点：
1. 创建 (`created_at`)
2. 提交 (`approved_at`)
3. 客户确认 (`customer_confirmed_at`)
4. 付款 (`paid_at`) + 付款凭证
5. 完成 (`completed_at`)

#### 4.2.5 操作按钮（根据状态和权限动态显示）

| 当前状态 | 显示按钮 | 权限要求 |
|----------|----------|----------|
| draft | 提交、申请折扣、删除 | billing:edit / billing:delete |
| pending_customer | 确认、取消 | billing:confirm (限经理) / billing:edit |
| customer_confirmed | 标记付款 | billing:pay |
| paid | 完成结算 | billing:pay |
| completed | - | - |
| cancelled | - | - |

**确认操作的特殊权限逻辑**：
- 仅当当前用户是商务经理 (`sales_manager_id`) 或运营经理 (`manager_id`) 时可用
- 其他用户即使有 `billing:confirm` 权限也不可见
- 后端增加 `@permission_required('billing:confirm')` 装饰器

### 4.3 状态映射修正

#### 4.3.1 后端状态枚举
```python
InvoiceStatus:
  DRAFT = "draft"
  PENDING_CUSTOMER = "pending_customer"
  CUSTOMER_CONFIRMED = "customer_confirmed"
  PAID = "paid"
  COMPLETED = "completed"
  CANCELLED = "cancelled"
```

#### 4.3.2 前端状态映射
```typescript
const statusMap: Record<string, { text: string; color: string }> = {
  draft: { text: '草稿', color: 'gray' },
  pending_customer: { text: '待客户确认', color: 'orange' },
  customer_confirmed: { text: '客户已确认', color: 'blue' },
  paid: { text: '已付款', color: 'green' },
  completed: { text: '已完成', color: 'arcoblue' },
  cancelled: { text: '已取消', color: 'red' },
};
```

#### 4.3.3 需要同步修正的文件
- `frontend/src/api/billing.ts` - `Invoice.status` 类型定义
- `frontend/src/views/Home.vue` - 状态映射
- `frontend/src/views/customers/Detail.vue` - 状态映射

### 4.4 弹窗组件

#### 4.4.1 生成结算单弹窗
- 客户选择（必填）
- 结算周期（日期范围，必填）
- 结算项表格（动态添加行）
  - 设备类型（下拉）
  - 层级类型（下拉）
  - 数量（数字输入）
  - 单价（数字输入，可自动从定价规则获取）
- 提交前校验

#### 4.4.2 申请折扣弹窗
- 折扣金额（数字输入，不能超过总金额）
- 折扣原因（文本域，必填）
- 附件上传（可选）

#### 4.4.3 标记付款弹窗
- 付款凭证上传（可选）
- 备注（可选）

---

## 5. 后端修改清单

### 5.1 权限修正
| 文件 | 修改内容 | 当前 | 目标 |
|------|----------|------|------|
| `app/routes/billing.py` | `confirm_invoice` | `@permission_required('billing:edit')` | `@permission_required('billing:confirm')` |
| `app/routes/billing.py` | `pay_invoice` | `@permission_required('billing:edit')` | `@permission_required('billing:pay')` |
| `app/routes/billing.py` | `complete_invoice` | `@permission_required('billing:edit')` | `@permission_required('billing:pay')` |

### 5.2 新增权限
需要在权限初始化脚本中添加：
- `billing:confirm` - 确认结算单
- `billing:pay` - 标记付款/完成结算

### 5.3 发票生成任务修复
| 文件 | 修改内容 |
|------|----------|
| `app/tasks/invoice_generator.py` | `billing_start` → `period_start` |
| `app/tasks/invoice_generator.py` | `billing_end` → `period_end` |
| `app/tasks/invoice_generator.py` | `auto_generated=True` → `is_auto_generated=True` |

---

## 6. 路由与导航

### 6.1 路由配置
```typescript
// frontend/src/router/index.ts
{
  path: 'billing',
  name: 'Billing',
  children: [
    { path: 'balances', name: 'Balance', ... },
    { path: 'pricing-rules', name: 'PricingRules', ... },
    { path: 'invoices', name: 'Invoices', ... },  // 新增
  ],
}
```

### 6.2 导航菜单
在侧边栏"结算管理"下新增"结算单管理"子菜单项。

---

## 7. 测试策略

### 7.1 单元测试
- 前端组件单元测试（Vue Test Utils）
- 状态映射函数测试
- 权限判断逻辑测试

### 7.2 集成测试
- 后端 API 集成测试已存在，验证新增权限是否生效
- 前端 E2E 测试（Playwright）

### 7.3 手动测试清单
- [ ] 列表筛选功能
- [ ] 详情展示完整性
- [ ] 状态流转全流程
- [ ] 权限控制验证
- [ ] 金额计算准确性
- [ ] 导出功能

---

## 8. 依赖关系

### 8.1 前置依赖
- 现有 `billing.ts` API 封装（已完整）
- 现有后端路由和 Service 层（需权限修正）

### 8.2 外部依赖
- Arco Design Vue 组件库（表格、表单、弹窗、时间线）
- Vue Router（路由配置）
- Pinia（状态管理，可选）

---

## 9. 实施顺序建议

1. **后端权限修正**（独立修改，风险低）
2. **前端基础结构**（路由 + 导航 + 空页面）
3. **列表功能**（表格 + 筛选 + 分页）
4. **详情功能**（详情面板 + 时间线）
5. **操作功能**（弹窗 + 状态流转）
6. **状态映射修正**（全局一致性修复）
7. **发票生成任务修复**（独立修改）
