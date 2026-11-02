# Implement：VR编辑费用结算模块

## 执行清单（按序）

### 阶段 1：数据模型与数据库迁移

- [ ] 1.1 新建 `backend/app/models/vr_settlement.py`：`VrSettlementStatus` 枚举（8 态）+ `VrSettlement`（照抄 `models/billing.py:134-186` Invoice 风格，`Mapped`/`mapped_column` + `BaseModel`，字段见 design.md 数据模型节）+ `VrSettlementDiscountHistory`（照抄 `models/billing.py:193-216`）。`status` 列宽 `String(30)`。
- [ ] 1.2 `backend/app/models/billing.py` `ConsumptionRecord`（246-269 行）内新增 `vr_settlement_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("vr_settlements.id"), nullable=True, index=True)`，其余不动。
- [ ] 1.3 `backend/app/models/__init__.py`：`from . import billing` 后加 `from . import vr_settlement  # noqa: E402`，`__all__` 加 `"vr_settlement"`。
- [ ] 1.4 新建迁移 `backend/alembic/versions/d0e1f2a3b4c5_add_vr_settlements.py`（down_revision `c9d0e1f2a3b4`）：建两表+索引 → `consumption_records` 加列加索引 → 幂等插 8 权限码 + 关联超管（照抄 `a7b8c9d0e1f2:70-103` 两段 SQL）→ downgrade 逆序。
- [ ] 1.5 应用迁移并验证：`cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python scripts/check_schema_drift.py`

### 阶段 2：权限码与预置角色

- [ ] 2.1 `backend/scripts/seed.py`：`ALL_PERMISSIONS` billing 组后追加 VR 组 8 码；`PRESET_ROLES` 运营经理追加 4 码、销售经理追加 2 码、末尾追加「客服主管」「销售主管」两角色。
- [ ] 2.2 `backend/tests/_test_data.py`：`PERMISSION_ROWS` 按 **3 元组** `(code, name, module)` 追加同样 8 码。
- [ ] 2.3 `cd backend && .venv/bin/python scripts/seed.py --sync-permissions`

### 阶段 3：服务层

- [ ] 3.1 新建 `backend/app/services/vr_settlement.py`：`VrSettlementService(db)` + 方法表见 prd.md R3（create_settlement / get_settlements / get_settlement_by_id / get_discount_histories / submit / confirm_cs_supervisor / confirm_sales / confirm_sales_supervisor / reject_sales_supervisor / apply_discount / confirm_customer / _execute_deduction / retry_deduction / cancel / delete_settlement）。状态不匹配统一 `(False, f"当前状态（{status}）不允许该操作")`；不存在 `(False, "结算单不存在")`。扣款调 `BalanceService(BalanceRepository(self.db)).consume(customer_id=..., amount=..., vr_settlement_id=...)`。
- [ ] 3.2 `backend/app/services/billing.py` `BalanceService.consume`（222-343）：签名加 `vr_settlement_id: Optional[int] = None`，`ConsumptionRecord(...)` 构造加 `vr_settlement_id=vr_settlement_id`；其余零改动。

### 阶段 4：路由层

- [ ] 4.1 新建 `backend/app/routes/billing/vr_settlements.py`：导入块照抄 `invoices.py:1-45`；`_ensure_settlement_scope` / `_ensure_customer_scope` 两个私有助手；13 端点见 prd.md R4 表（装饰器顺序 `@billing_bp.<m>` → `@auth_required` → `@require_permission`）；8 动作端点手动审计，action 字面量 `submit_vr_settlement / confirm_cs_supervisor / confirm_sales / confirm_sales_supervisor / reject_sales_supervisor / confirm_vr_settlement / retry_vr_deduction / cancel_vr_settlement`。
- [ ] 4.2 `backend/app/routes/billing/__init__.py` 末行导入加 `vr_settlements`。
- [ ] 4.3 `backend/app/middleware/audit.py` invoices 跳过块后追加 VR 动作端点跳过块（8 个后缀）。

### 阶段 5：前端

- [ ] 5.1 `frontend/src/api/vrSettlement.ts`（照抄 api/billing.ts 模式；明细上传复用 `uploadDiscountAttachment`）
- [ ] 5.2 `frontend/src/constants/vrSettlementStatus.ts`（照抄 invoiceStatus.ts）
- [ ] 5.3 `frontend/src/composables/useVrSettlement.ts`（照抄 useInvoice.ts，去轮询；filters 仅 keyword/status/customer_id）
- [ ] 5.4 `frontend/src/views/billing/VrSettlements.vue`（列宽/scroll 1440/storage-key `vr_settlements_table_columns`；操作按钮规则表见 prd R5）
- [ ] 5.5 `frontend/src/views/billing/components/VrSettlementCreateModal.vue`（自动创建 disabled + 「待开发」tag）
- [ ] 5.6 `frontend/src/views/billing/components/VrSettlementDiscountModal.vue`
- [ ] 5.7 `frontend/src/views/billing/components/VrSettlementApprovalModal.vue`
- [ ] 5.8 `frontend/src/views/billing/components/VrSettlementDetailDrawer.vue`（6 步流程条，映射 `draft:1, pending_cs_supervisor:2, pending_sales:3, pending_sales_supervisor:4, pending_customer:5, customer_confirmed:6, completed:6, cancelled:1`）
- [ ] 5.9 `frontend/src/router/index.ts` billing children 加 VrSettlements 路由
- [ ] 5.10 `frontend/src/composables/useAppLayout.ts`：navSections 加项 + routeMap 加 `VrSettlements`
- [ ] 5.11 `frontend/src/components/layout/AppSidebar.vue`：「结算单管理」按钮后插入同构按钮
- [ ] 5.12 `frontend/src/views/roles/permissionGroups.ts`：`MODULE_NAME_MAP` 加 `vr_settlement`，`MODULE_ORDER` 在 `'billing'` 后插入

### 阶段 6：测试

- [ ] 6.1 `backend/tests/integration/conftest.py`：db_session TRUNCATE 列表加 `vr_settlement_discount_histories, vr_settlements`（放 `invoices` 前）
- [ ] 6.2 新建 `backend/tests/integration/test_vr_settlement_api.py`：fixture（test_customer 带 sales_manager_id + 1000 余额）+ 9 组用例（AC1-AC11）
- [ ] 6.3 新建 `frontend/src/composables/__tests__/useVrSettlement.test.ts`（照抄 useInvoice.test.ts mock 结构）

## 验证命令（按序，全过才算完成）

```bash
cd backend && .venv/bin/python -m alembic upgrade head
cd backend && .venv/bin/python scripts/check_schema_drift.py
cd backend && .venv/bin/python scripts/seed.py --sync-permissions
cd backend && .venv/bin/python -m pytest tests/unit/ -q
cd backend && .venv/bin/python -m pytest tests/integration/test_vr_settlement_api.py -q
cd backend && .venv/bin/python -m pytest tests/ -q          # 全量 + --cov-fail-under=50
cd frontend && npx vitest run src/composables/__tests__/useVrSettlement.test.ts
cd frontend && npx vue-tsc --noEmit && npm run build
```

## 风险文件与回滚点

| 文件 | 风险 | 回滚 |
|---|---|---|
| `services/billing.py` consume | 改签名影响所有既有扣款调用方 | kwarg 有默认值；出问题 revert 单文件即恢复 |
| `alembic/versions/d0e1f2a3b4c5` | 权限 SQL 写错导致迁移失败 | downgrade 完整；重写迁移前先 drop |
| `middleware/audit.py` | 跳过块路径写错导致双审计或漏审计 | 精确 endswith 后缀匹配，与 invoices 同构 |
| `tests/_test_data.py` | 漏加码 → test_test_data_consistency 失败 | 按 seed 组顺序同步追加 |

## 收尾（task.py start 前复查）

- [ ] prd/design/implement 三件套齐备且 AC 可观测
- [ ] 4 处 PLAN 偏差修正已记录（prd.md Technical Notes）
- [ ] implement.jsonl / check.jsonl 已各含至少一条真实条目（spec/research 清单）
