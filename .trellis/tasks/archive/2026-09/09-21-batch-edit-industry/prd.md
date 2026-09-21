# 客户列表批量编辑增加行业与ERP编辑项

## Goal

在客户列表「批量编辑」弹框（`CustomerBatchEditModal.vue`）中新增编辑项：

1. **行业类型**（必选需求）：勾选后可批量设置/清除客户行业（`industry_type_id`）
2. **ERP 系统**（推荐需求）：勾选后可批量设置客户所属 ERP 系统（`erp_system`）
3. 检查并确认其余候选编辑项（日期字段、备注、名称/公司 ID/邮箱）**不纳入**本次范围

## Background / 现状

- 批量编辑弹框现有 13 个编辑项（运营经理、商务经理、合作状态、重点客户、房产客户、结算方式、结算周期、是否启用结算、停用、账号类型、计费策略、规模等级、消费等级）
- 后端 `backend/app/services/customers.py` 的 `batch_update_customers` 白名单（21 字段）**已包含** `industry_type_id` 与 `erp_system`：
  - `industry_type_id` 走 `CustomerProfile` 更新（profile 不存在时自动创建），传 `null` 即清空行业，有存在性校验与失败列表
  - `erp_system` 为 `Customer` 表字段，直接 setattr 更新
- 后端测试 `backend/tests/unit/test_batch_update.py` 已覆盖批量更新链路
- 前端字典已就绪：Index.vue 通过 `useCustomerDict` 已加载 `industryTypes`/`erpSystems` 并传入其他弹框

## Requirements

- 批量编辑弹框出现「行业类型」编辑项：checkbox（勾选=本次修改）+ select（allow-clear，清空=置 null 清除行业）
- 批量编辑弹框出现「ERP 系统」编辑项：checkbox（勾选=本次修改）+ select（allow-clear，清空=置 null）
- 勾选字段提交后：`batchUpdateCustomers(customerIds, { industry_type_id, erp_system, ... })`，后端校验失败项进入失败列表并在前端提示
- 预览弹框自动展示新增字段的修改值
- 弹框打开时重置新增字段（resetForm 同步扩展）
- 后端零改动

## Acceptance Criteria

- [ ] `CustomerBatchEditModal.vue` 中新增「行业类型」「ERP 系统」两个编辑项，样式与现有编辑项一致（checkbox + 控件，禁用态联动）
- [ ] props 从 Index.vue 接收 `industryTypes` / `erpSystems`（与 managers 同模式），Index.vue 已加载无需新接口
- [ ] 勾选行业并提交 → 客户详情/列表显示新行业；清空（clear）提交 → 行业置空
- [ ] 勾选 ERP 并提交 → 客户详情显示新 ERP；清空提交 → 置空
- [ ] 提交失败项（如非法 industry_type_id）进入失败列表并弹窗提示
- [ ] 预览弹框展示新增字段名与修改值
- [ ] 后端无改动；`backend/tests/unit/test_batch_update.py` 通过（回归）
- [ ] 浏览器实测：多选 → 批量编辑 → 勾选行业/ERP → 预览 → 提交 → 列表刷新验证

## Non-Goals

- 不增加首次回款时间/接入时间/备注/名称/公司 ID/邮箱的批量编辑（理由见 design.md 决策记录）
- 不改后端 service/路由/模型
