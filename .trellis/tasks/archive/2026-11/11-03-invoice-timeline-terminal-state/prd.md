# 修复 InvoiceTimeline completed 终态末节点灰色缺陷

## Goal

结算单详情页（completed 状态）「操作记录」时间线的末节点「完成结算」被误判为「未到达」渲染成灰色。修复判定逻辑，与 VR 侧（`VrSettlementTimeline`）对齐。

## Root Cause

`InvoiceTimeline.vue` 节点三态判定：

```ts
const isCompleted = timeValue && index !== currentRemIndex
```

completed 终态下 `currentRemIndex` 指向末节点（`completed_at` 的 statusKey='completed'），导致末节点 `isCompleted=false` → 落入 else 分支渲染为灰色 pending。中间态无此问题（currentRemIndex 指向的节点本就该高亮），故缺陷只在终态显现——旧测试只覆盖中间态与取消态，缺终态断言，缺陷得以潜伏。

## Requirements

- R1 修复判定：`isCompleted = !!timeValue && !isCurrent`（与 VR 侧一致）
- R2 补终态回归用例：completed 全流程 6 节点全绿、无 current、无 pending（failing-before 验证）
- R3 spec 陷阱条目更新为两侧均已修，强调新时间线 wrapper 必须覆盖终态场景

## 验收边界

- 改动：`frontend/src/components/invoice/InvoiceTimeline.vue`（判定逻辑）、`frontend/src/components/invoice/__tests__/InvoiceTimeline.test.ts`（终态用例）、`.trellis/spec/frontend/component-guidelines.md`（spec 更新）
- 验证：修复前新用例 failing（pending-event=1）→ 修复后 passing；vitest 全量、vue-tsc、build 通过；浏览器实测 completed 发票 INV-20261022-1121-D0RJ 末节点绿色（截图存档）
- 提交：`add5a5a`
