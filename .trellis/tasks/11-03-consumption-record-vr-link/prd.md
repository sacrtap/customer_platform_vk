# 修复消耗记录接口缺失 VR 结算单关联字段

## Goal

VR 编辑费用结算单完成客户确认后，余额页「消耗记录」中已产生扣款流水，但「关联结算单」列显示 `-`，无法追溯到来源 VR 结算单。

## Root Cause

三层链路中两层缺失（DB 层正常）：

| 层 | 状态 | 说明 |
|---|---|---|
| DB 写入 | ✅ | `BalanceService.consume(vr_settlement_id=)` → `ConsumptionRecord.vr_settlement_id` 正常落库 |
| API 序列化 | ❌ | `GET /billing/consumption-records` 只下发 `invoice_id/invoice_no`，无 VR 字段 |
| 前端展示 | ❌ | `RechargeRecordModal` 关联列 slot 只渲染 `invoice_no`，VR 记录落入 `v-else` 显示 `-` |

根因分类：Change Propagation Failure（C）+ Test Coverage Gap（D）复合——VR 扣款链路叠加到既有 invoice 体系时，只改了写入点与 DB 模型，遗漏了序列化出口与展示层；既有 AC3 验证只断言 DB 行，未打接口响应，缺口未被发现。

## Requirements

- R1 `GET /billing/consumption-records` 响应同时下发 `vr_settlement_id` / `vr_settlement_no`（与 invoice 组独立、互斥时有且只有一组非空）
- R2 前端「关联结算单」列对 VR 记录显示单号并链接 `/billing/vr-settlements?highlight={id}`
- R3 单号查询走批量 map，不引入 N+1
- R4 回归守护：集成测试断言接口层 `vr_settlement_no`；组件测试覆盖 VR/发票/无关联三态渲染

## 验收边界

- 改动文件：`backend/app/routes/billing/balances.py`（序列化 + VR 单号批量查询）、`frontend/src/api/billing.ts`（类型）、`frontend/src/views/billing/components/RechargeRecordModal.vue`（渲染分支）、`backend/tests/integration/test_vr_settlement_api.py`（接口层断言）、`frontend/src/views/billing/components/__tests__/RechargeRecordModal.consumption.test.ts`（新增组件测试）
- 最终验证：后端单测 848 passed；VR 集成 11 passed（含新断言）；billing 集成 73 passed；前端 vue-tsc 通过、vitest 222 passed（含新 3 例）、`npm run build` 通过
- 未改动：DB 模型/迁移（字段已存在）、数据可见性 scope 逻辑（VR 记录扣客户自身余额，`cr_customer_owned` 已覆盖）
