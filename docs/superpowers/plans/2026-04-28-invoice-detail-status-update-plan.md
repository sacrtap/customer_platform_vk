# 结算单详情状态实时更新优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复结算单详情 Drawer 中操作后按钮状态和时间线不实时更新的问题，并补充后端取消结算单 API。

**Architecture:** 在后端新增 `cancel_invoice` 方法和路由，前端操作成功后重新调用详情接口更新 `selectedInvoice` 对象，使 Vue 响应式系统自动更新按钮和时间线。

**Tech Stack:** Python 3.12 + Sanic + SQLAlchemy 2.0 (后端), Vue 3.4 + TypeScript + Arco Design (前端), Alembic (数据库迁移)

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/models/billing.py` | Invoice 模型定义，新增 `cancelled_at` 字段 |
| `backend/app/services/billing.py` | InvoiceService 业务逻辑，新增 `cancel_invoice()` 方法 |
| `backend/app/routes/billing.py` | API 路由层，新增 `POST /invoices/:id/cancel` 路由 |
| `backend/tests/test_billing_service.py` | Service 层单元测试，新增 `TestInvoiceService_Cancel` 测试类 |
| `backend/tests/integration/test_billing_api.py` | API 集成测试，新增取消接口测试 |
| `frontend/src/api/billing.ts` | API 客户端层，新增 `cancelInvoice()` 函数和 `cancelled_at` 类型 |
| `frontend/src/views/billing/Invoices.vue` | 结算单管理页面，修复 4 个操作方法刷新详情 |
| `frontend/src/components/invoice/InvoiceTimeline.vue` | 时间线组件，新增取消节点和颜色支持 |

---

## 后端实现

### Task 1: Invoice 模型新增 cancelled_at 字段

**Files:**
- Modify: `backend/app/models/billing.py:108`

- [ ] **Step 1: 在 Invoice 模型中添加 cancelled_at 字段**

在 `completed_at = Column(String(50))` 之后添加：

```python
completed_at = Column(String(50))
cancelled_at = Column(String(50))  # 取消时间
is_auto_generated = Column(Boolean, default=True)
```

- [ ] **Step 2: 生成并执行 Alembic 迁移**

```bash
cd backend && python -m alembic revision --autogenerate -m "add cancelled_at to invoices"
cd backend && python -m alembic upgrade head
```

预期输出：`INFO  [alembic.runtime.migration] Running upgrade -> xxx, add cancelled_at to invoices`

- [ ] **Step 3: 验证迁移成功**

```bash
cd backend && python -c "from app.models.billing import Invoice; print('cancelled_at' in [c.name for c in Invoice.__table__.columns])"
```

预期输出：`True`

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/billing.py backend/alembic/
git commit -m "feat(billing): add cancelled_at field to Invoice model"
```

---

### Task 2: InvoiceService 新增 cancel_invoice 方法

**Files:**
- Modify: `backend/app/services/billing.py:877` (在 `delete_invoice` 方法之前)
- Test: `backend/tests/test_billing_service.py:1496` (在 `TestInvoiceService_Delete` 类之前)

- [ ] **Step 1: 编写测试用例（TDD）**

在 `backend/tests/test_billing_service.py` 中，`TestInvoiceService_Delete` 类之前添加：

```python
class TestInvoiceService_Cancel:
    """InvoiceService.cancel_invoice 测试"""

    @pytest.mark.asyncio
    async def test_cancel_from_draft(self, invoice_service):
        """测试从草稿状态取消"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.cancel_invoice(invoice_id=1)

        assert success is True
        assert "取消成功" in message
        assert mock_invoice.status == "cancelled"
        assert mock_invoice.cancelled_at is not None

    @pytest.mark.asyncio
    async def test_cancel_from_pending(self, invoice_service):
        """测试从待客户确认状态取消"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="pending_customer",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.cancel_invoice(invoice_id=1)

        assert success is True
        assert mock_invoice.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_wrong_state(self, invoice_service):
        """测试状态不能取消（已确认状态）"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="customer_confirmed",  # 已确认，不能取消
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.cancel_invoice(invoice_id=1)

        assert success is False
        assert "不能取消" in message

    @pytest.mark.asyncio
    async def test_cancel_paid_invoice(self, invoice_service):
        """测试已付款状态不能取消"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="paid",  # 已付款，不能取消
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.cancel_invoice(invoice_id=1)

        assert success is False
        assert "不能取消" in message

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, invoice_service):
        """测试结算单不存在"""
        service, mock_db = invoice_service

        mock_db.execute.return_value = make_mock_execute_result([])

        success, message = await service.cancel_invoice(invoice_id=999)

        assert success is False
        assert "不存在" in message
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_billing_service.py::TestInvoiceService_Cancel -v
```

预期：所有测试失败，因为 `cancel_invoice` 方法不存在

- [ ] **Step 3: 实现 cancel_invoice 方法**

在 `backend/app/services/billing.py` 中，`delete_invoice` 方法之前添加：

```python
async def cancel_invoice(self, invoice_id: int) -> Tuple[bool, str]:
    """取消结算单"""
    invoice = await self.get_invoice_by_id(invoice_id)

    if not invoice:
        return False, "结算单不存在"

    # 只有草稿和待客户确认状态可以取消
    if invoice.status not in ("draft", "pending_customer"):
        return False, f"当前状态不能取消：{invoice.status}"

    invoice.status = "cancelled"
    invoice.cancelled_at = datetime.now().isoformat()

    await self.db.commit()

    return True, "取消成功"
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_billing_service.py::TestInvoiceService_Cancel -v
```

预期：5 个测试全部通过

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/billing.py backend/tests/test_billing_service.py
git commit -m "feat(billing): add cancel_invoice method to InvoiceService"
```

---

### Task 3: 新增取消结算单 API 路由

**Files:**
- Modify: `backend/app/routes/billing.py:919` (在 `delete_invoice` 路由之前)
- Test: `backend/tests/integration/test_billing_api.py`

- [ ] **Step 1: 编写集成测试**

在 `backend/tests/integration/test_billing_api.py` 中添加取消接口测试：

```python
class TestCancelInvoiceAPI:
    """取消结算单 API 测试"""

    @pytest.mark.asyncio
    async def test_cancel_invoice_success(self, test_client, test_db):
        """测试取消结算单成功"""
        from app.models.billing import Invoice
        from datetime import date

        # 创建测试结算单
        invoice = Invoice(
            customer_id=1,
            invoice_no="INV-TEST-CANCEL",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            total_amount=100.00,
            status="pending_customer",
        )
        test_db.add(invoice)
        await test_db.commit()

        # 调用取消接口
        response = await test_client.post(f"/api/v1/billing/invoices/{invoice.id}/cancel")

        assert response.status == 200
        data = response.json
        assert data["code"] == 0

        # 验证数据库状态
        await test_db.refresh(invoice)
        assert invoice.status == "cancelled"
        assert invoice.cancelled_at is not None

    @pytest.mark.asyncio
    async def test_cancel_invoice_wrong_state(self, test_client, test_db):
        """测试错误状态不能取消"""
        from app.models.billing import Invoice
        from datetime import date

        invoice = Invoice(
            customer_id=1,
            invoice_no="INV-TEST-CANCEL-ERR",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            total_amount=100.00,
            status="customer_confirmed",  # 已确认，不能取消
        )
        test_db.add(invoice)
        await test_db.commit()

        response = await test_client.post(f"/api/v1/billing/invoices/{invoice.id}/cancel")

        assert response.status == 400
        data = response.json
        assert data["code"] == 40001
        assert "不能取消" in data["message"]
```

- [ ] **Step 2: 实现取消路由**

在 `backend/app/routes/billing.py` 中，`delete_invoice` 路由之前添加：

```python
@billing_bp.post("/invoices/<invoice_id:int>/cancel")
@auth_required
@require_permission("billing:edit")
async def cancel_invoice_route(request: Request, invoice_id: int):
    """取消结算单"""
    db: AsyncSession = request.ctx.db_session
    invoice_service = InvoiceService(db)

    success, message = await invoice_service.cancel_invoice(invoice_id=invoice_id)

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    # 结算单取消后清除相关缓存
    await cache_service.invalidate_billing_cache()

    return json({"code": 0, "message": message})
```

- [ ] **Step 3: 运行集成测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_billing_api.py::TestCancelInvoiceAPI -v
```

预期：2 个测试全部通过

- [ ] **Step 4: 提交**

```bash
git add backend/app/routes/billing.py backend/tests/integration/test_billing_api.py
git commit -m "feat(billing): add cancel invoice API endpoint"
```

---

## 前端实现

### Task 4: API 层新增 cancelInvoice 函数和类型

**Files:**
- Modify: `frontend/src/api/billing.ts:180` (Invoice 接口) 和 `frontend/src/api/billing.ts:242` (在 deleteInvoice 之后)

- [ ] **Step 1: 更新 Invoice 接口类型**

在 `Invoice` 接口中添加 `cancelled_at` 字段：

```typescript
export interface Invoice {
  id: number
  invoice_no: string
  customer_id: number
  customer_name?: string
  period_start: string
  period_end: string
  total_amount: number
  discount_amount?: number
  discount_reason?: string
  discount_attachment?: string
  final_amount: number
  status: 'draft' | 'pending_customer' | 'customer_confirmed' | 'paid' | 'completed' | 'cancelled'
  is_auto_generated: boolean
  items?: InvoiceItem[]
  approver_id?: number
  approved_at?: string
  customer_confirmed_at?: string
  paid_at?: string
  completed_at?: string
  cancelled_at?: string  // 新增：取消时间
  created_at: string
}
```

- [ ] **Step 2: 新增 cancelInvoice API 函数**

在 `deleteInvoice` 函数之后添加：

```typescript
export function cancelInvoice(invoiceId: number) {
  return api.post(`/billing/invoices/${invoiceId}/cancel`)
}
```

- [ ] **Step 3: 运行 TypeScript 类型检查**

```bash
cd frontend && npm run type-check
```

预期：无类型错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/billing.ts
git commit -m "feat(billing): add cancelInvoice API function and cancelled_at type"
```

---

### Task 5: 修复 Invoices.vue 中的操作方法

**Files:**
- Modify: `frontend/src/views/billing/Invoices.vue:384-396` (import 语句) 和 `frontend/src/views/billing/Invoices.vue:610-731` (操作方法)

- [ ] **Step 1: 更新 import 语句**

在 import 语句中添加 `cancelInvoice`：

```typescript
import {
  getInvoices,
  getInvoice,
  submitInvoice,
  confirmInvoice,
  payInvoice,
  completeInvoice,
  deleteInvoice,
  applyDiscount,
  generateInvoice,
  calculateInvoiceItems,
  cancelInvoice,  // 新增
  type Invoice,
} from '@/api/billing'
```

- [ ] **Step 2: 修复 handleSubmit 方法**

替换现有的 `handleSubmit` 方法：

```typescript
// 提交结算单
async function handleSubmit(invoice: Invoice) {
  Modal.confirm({
    title: '确认提交',
    content: `确定要提交结算单 ${invoice.invoice_no} 吗？提交后将进入待确认状态。`,
    onOk: async () => {
      try {
        await submitInvoice(invoice.id)
        Message.success('提交成功')
        loadData()
        // 刷新详情，更新 Drawer 中的状态
        if (selectedInvoice.value?.id === invoice.id) {
          const res = await getInvoice(invoice.id)
          selectedInvoice.value = res.data
        }
      } catch (error) {
        Message.error('提交失败')
      }
    },
  })
}
```

- [ ] **Step 3: 修复 handleConfirm 方法**

替换现有的 `handleConfirm` 方法：

```typescript
// 确认结算单
async function handleConfirm(invoice: Invoice) {
  try {
    await confirmInvoice(invoice.id)
    Message.success('确认成功')
    loadData()
    // 刷新详情，更新 Drawer 中的状态
    if (selectedInvoice.value?.id === invoice.id) {
      const res = await getInvoice(invoice.id)
      selectedInvoice.value = res.data
    }
  } catch (error) {
    Message.error('确认失败')
  }
}
```

- [ ] **Step 4: 修复 handleCancel 方法**

替换现有的 `handleCancel` 方法：

```typescript
// 取消结算单
async function handleCancel(invoice: Invoice) {
  Modal.confirm({
    title: '确认取消',
    content: '确定要取消该结算单吗？',
    onOk: async () => {
      try {
        await cancelInvoice(invoice.id)  // 调用真实 API
        Message.success('取消成功')
        loadData()
        // 刷新详情，更新 Drawer 中的状态
        if (selectedInvoice.value?.id === invoice.id) {
          const res = await getInvoice(invoice.id)
          selectedInvoice.value = res.data
        }
      } catch (error) {
        Message.error('取消失败')
      }
    },
  })
}
```

- [ ] **Step 5: 修复 handleComplete 方法**

替换现有的 `handleComplete` 方法：

```typescript
// 完成结算
async function handleComplete(invoice: Invoice) {
  try {
    await completeInvoice(invoice.id)
    Message.success('结算完成')
    loadData()
    // 刷新详情，更新 Drawer 中的状态
    if (selectedInvoice.value?.id === invoice.id) {
      const res = await getInvoice(invoice.id)
      selectedInvoice.value = res.data
    }
  } catch (error) {
    Message.error('结算失败')
  }
}
```

- [ ] **Step 6: 运行 lint 和类型检查**

```bash
cd frontend && npm run lint && npm run type-check
```

预期：无错误

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/billing/Invoices.vue
git commit -m "fix(billing): refresh invoice details after status change operations"
```

---

### Task 6: 更新 InvoiceTimeline 组件支持颜色

**Files:**
- Modify: `frontend/src/components/invoice/InvoiceTimeline.vue:1-94`

- [ ] **Step 1: 更新 props 类型定义**

```typescript
const props = defineProps<{
  invoice: {
    created_at: string;
    approved_at?: string;
    customer_confirmed_at?: string;
    paid_at?: string;
    completed_at?: string;
    cancelled_at?: string;  // 新增
    payment_proof?: string;
  };
}>();
```

- [ ] **Step 2: 更新 timelineEvents 计算属性，添加 color 字段**

替换整个 `timelineEvents` 计算属性：

```typescript
const timelineEvents = computed(() => {
  const events: Array<{ time: string; label: string; detail?: string; color?: string }> = [];

  if (props.invoice.created_at) {
    events.push({
      time: formatDate(props.invoice.created_at),
      label: '创建结算单',
    });
  }

  if (props.invoice.approved_at) {
    events.push({
      time: formatDate(props.invoice.approved_at),
      label: '提交结算',
    });
  }

  if (props.invoice.customer_confirmed_at) {
    events.push({
      time: formatDate(props.invoice.customer_confirmed_at),
      label: '客户确认',
    });
  }

  if (props.invoice.paid_at) {
    events.push({
      time: formatDate(props.invoice.paid_at),
      label: '确认付款',
      detail: props.invoice.payment_proof ? `凭证：${props.invoice.payment_proof}` : undefined,
    });
  }

  if (props.invoice.completed_at) {
    events.push({
      time: formatDate(props.invoice.completed_at),
      label: '完成结算',
      color: 'green',
    });
  }

  if (props.invoice.cancelled_at) {
    events.push({
      time: formatDate(props.invoice.cancelled_at),
      label: '取消结算',
      color: 'red',
    });
  }

  return events;
});
```

- [ ] **Step 3: 更新模板，添加 color 属性绑定**

```vue
<template>
  <a-timeline>
    <a-timeline-item
      v-for="event in timelineEvents"
      :key="event.time"
      :time="event.time"
      :color="event.color"
    >
      <div class="timeline-content">
        <strong>{{ event.label }}</strong>
        <p v-if="event.detail" class="timeline-detail">{{ event.detail }}</p>
      </div>
    </a-timeline-item>
  </a-timeline>
</template>
```

- [ ] **Step 4: 运行 lint 和类型检查**

```bash
cd frontend && npm run lint && npm run type-check
```

预期：无错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/invoice/InvoiceTimeline.vue
git commit -m "feat(billing): add color support and cancelled_at node to InvoiceTimeline"
```

---

## 最终验证

### Task 7: 运行完整测试套件

- [ ] **Step 1: 运行后端单元测试**

```bash
cd backend && make test-cov
```

预期：所有测试通过，覆盖率 ≥50%

- [ ] **Step 2: 运行后端集成测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_billing_api.py -v
```

预期：所有集成测试通过

- [ ] **Step 3: 运行前端类型检查**

```bash
cd frontend && npm run type-check
```

预期：无类型错误

- [ ] **Step 4: 运行前端 lint**

```bash
cd frontend && npm run lint
```

预期：无 lint 错误

- [ ] **Step 5: 最终提交**

```bash
git add -A
git commit -m "chore: final verification - all tests passing"
```

---

## 验收清单

- [ ] 后端 `cancel_invoice` API 正常工作（可通过 curl 或 Postman 测试）
- [ ] 前端调用取消 API 而非模拟成功
- [ ] Drawer 中确认操作后按钮状态自动更新为「标记付款」
- [ ] Drawer 中取消操作后按钮隐藏，时间线显示红色取消节点
- [ ] Drawer 中提交操作后按钮切换为「确认结算单」，时间线新增节点
- [ ] Drawer 中完成操作后按钮隐藏，时间线显示绿色完成节点
- [ ] 所有现有测试通过
- [ ] 新增测试覆盖取消功能
