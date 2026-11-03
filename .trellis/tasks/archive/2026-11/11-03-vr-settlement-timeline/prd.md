# VR 结算单详情页添加操作记录时间线

## Goal

VR 结算单详情页（`VrSettlementDetailDrawer.vue`）当前只有「减免修改历史」，缺少**状态流转操作记录**。参照结算单详情页（`InvoiceDetailDrawer.vue` → `InvoiceTimeline`）的成熟模式，为 VR 结算单增加同款「操作记录」时间线，使审批流转（创建→客服主管→销售→销售主管→客户确认→完成/取消）对用户可见、可追溯。

## Background（已核实的基座）

- VR 详情接口 `GET /billing/vr-settlements/<id>` **已下发全部所需字段**：`created_by_name`、`cs_supervisor_confirmed_at/name`、`sales_confirmed_at/name`、`sales_supervisor_confirmed_at/name`、`customer_confirmed_at/name`、`completed_at/name`、`cancelled_at/name`、`discount_approval_comment`、`discount_histories`（含 `applied_by_name/applied_at`）——**后端零改动**
- `InvoiceTimeline.vue` 结构：哑渲染模板（`a-timeline` + dotColor/textClass 三态）+ computed 从 props 字段推导节点；渲染层与推导层可分离
- `VrSettlementDetailDrawer.vue` 已有「减免修改历史」section（127 行），新 section 加装点明确

## Requirements

- R1 VR 详情页新增「操作记录」区块，渲染 `a-timeline` 时间线，位于「减免修改历史」之后
- R2 节点集（有值才显示）：创建结算单 → 客服主管审批 → 销售审批 → 销售主管审批（含减免审批意见）→ 客户确认 → 完成结算；取消状态末插红色「取消结算单」节点
- R3 三态着色与发票一致：当前节点 `blue`/`current-event`、已完成 `green`/`completed-event`、未到达 `gray`/`pending-event`、取消 `red`/`cancelled-event`
- R4 减免历史事件按发票同款规则插入「创建结算单」之后（正序，多次标注「第 N 次」）
- R5 共享渲染层抽取为 `components/common/StatusTimeline.vue`；`InvoiceTimeline.vue` 改为 wrapper，computed 逻辑零改动，发票页零回归
- R6 时间格式化复用 `InvoiceTimeline.formatDate`（`toDate` + `zh-CN` locale），VR 组件同规则

## 验收标准（AC）

- AC1 VR 结算单详情页展示操作记录时间线；各审批节点显示操作人姓名 + 时间 + （销售主管节点）减免审批意见
- AC2 取消的结算单时间线末位显示红色「取消结算单」节点
- AC3 当前所处流程节点高亮（蓝色加粗），未发生节点不显示
- AC4 组件测试覆盖 VR 时间线：已完成/当前/取消三态 + 减免历史插入
- AC5 发票详情页 `InvoiceTimeline` 行为不变（既有测试全绿 + 页面冒烟）

## 验证命令

```bash
cd frontend
npx vitest run src/components src/views/billing   # 组件测试
npx vue-tsc --noEmit                              # 类型检查
npm run build                                     # 构建
```

## 非目标

- 不改 DB 模型/迁移/接口序列化（字段已就绪）
- 不做「操作日志」审计表（本需求是状态机时间线，与发票页同口径）
- 不改发票侧任何行为
