# 结算单详情状态实时更新优化设计

**日期**: 2026-04-28  
**状态**: 待审核  
**范围**: 结算单详情 Drawer 中操作按钮和时间线的实时更新

---

## 问题描述

在结算单管理页面的详情 Drawer 中，当结算单处于「待客户确认」状态时：

1. 点击「确认结算单」或「取消结算单」后，操作按钮没有根据新状态自动切换
2. 状态时间线没有显示新增的节点
3. `handleCancel` 方法没有调用后端 API，只是前端模拟成功

**根本原因**：操作成功后只刷新了列表数据，但 Drawer 中的 `selectedInvoice` 对象没有重新从后端获取最新数据。

---

## 解决方案概述

采用**最小修复方案**：操作成功后重新调用详情接口，更新 Drawer 中的结算单数据，使按钮状态和时间线自动响应。

---

## 详细设计

### 1. 数据库迁移

#### 1.1 新增字段

在 `invoices` 表中新增 `cancelled_at` 字段：

```python
# 迁移脚本
cancelled_at = Column(String(50))  # 取消时间
```

#### 1.2 Alembic 迁移命令

```bash
cd backend && python -m alembic revision --autogenerate -m "add cancelled_at to invoices"
cd backend && python -m alembic upgrade head
```

---

### 2. 后端修改

#### 2.1 Invoice 模型更新

**文件**: `backend/app/models/billing.py`

在 `Invoice` 类中新增字段：

```python
cancelled_at = Column(String(50))  # 取消时间
```

#### 2.2 InvoiceService 新增方法

**文件**: `backend/app/services/billing.py`

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

#### 2.3 新增取消路由

**文件**: `backend/app/routes/billing.py`

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
    
    await cache_service.invalidate_billing_cache()
    
    return json({"code": 0, "message": message})
```

---

### 3. 前端修改

#### 3.1 API 层新增函数

**文件**: `frontend/src/api/billing.ts`

```typescript
export function cancelInvoice(invoiceId: number) {
  return api.post(`/billing/invoices/${invoiceId}/cancel`)
}
```

#### 3.2 Invoice 类型定义更新

**文件**: `frontend/src/api/billing.ts`

在 `Invoice` 接口中新增：

```typescript
cancelled_at?: string
```

#### 3.3 Invoices.vue 操作方法修复

**文件**: `frontend/src/views/billing/Invoices.vue`

**核心修改模式**：所有状态操作成功后，重新获取详情数据：

```typescript
// 操作成功后刷新详情
if (selectedInvoice.value?.id === invoice.id) {
  const res = await getInvoice(invoice.id)
  selectedInvoice.value = res.data
}
```

**需要修复的方法**：

| 方法 | 当前问题 | 修复方式 |
|------|---------|---------|
| `handleConfirm` | 未刷新详情 | 调用 `getInvoice` 更新 |
| `handleCancel` | 未调用 API + 未刷新详情 | 调用 `cancelInvoice` + `getInvoice` |
| `handleSubmit` | 未刷新详情 | 调用 `getInvoice` 更新 |
| `handleComplete` | 未刷新详情 | 调用 `getInvoice` 更新 |

#### 3.4 导入新 API 函数

在 `Invoices.vue` 的 import 语句中新增：

```typescript
import {
  // ... 现有导入
  cancelInvoice,  // 新增
} from '@/api/billing'
```

---

### 4. 时间线组件更新

#### 4.1 支持取消节点

**文件**: `frontend/src/components/invoice/InvoiceTimeline.vue`

**Props 更新**：

```typescript
const props = defineProps<{
  invoice: {
    // ... 现有字段
    cancelled_at?: string;  // 新增
  };
}>();
```

**时间线事件更新**：

```typescript
if (props.invoice.cancelled_at) {
  events.push({
    time: formatDate(props.invoice.cancelled_at),
    label: '取消结算',
  });
}
```

#### 4.2 时间线节点颜色

使用 Arco Design Timeline 的 `color` 属性：

| 节点 | color 值 | 说明 |
|------|---------|------|
| 创建结算单 | 默认 | - |
| 提交结算 | 默认 | - |
| 客户确认 | 默认 | - |
| 确认付款 | 默认 | - |
| 完成结算 | `green` | 正常流程结束 |
| 取消结算 | `red` | 异常流程结束 |

**实现方式**：

```vue
<a-timeline-item
  v-for="event in timelineEvents"
  :key="event.time"
  :time="event.time"
  :color="event.color"
>
```

在 `timelineEvents` 计算属性中，为每个事件添加 `color` 字段：

```typescript
// 完成结算节点
if (props.invoice.completed_at) {
  events.push({
    time: formatDate(props.invoice.completed_at),
    label: '完成结算',
    color: 'green',
  });
}

// 取消结算节点
if (props.invoice.cancelled_at) {
  events.push({
    time: formatDate(props.invoice.cancelled_at),
    label: '取消结算',
    color: 'red',
  });
}
```

---

## 状态流转图

```
draft → pending_customer → customer_confirmed → paid → completed
  ↓           ↓
  └── cancelled ──┘
```

**可取消状态**: `draft`, `pending_customer`

---

## 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `backend/app/models/billing.py` | 新增字段 | `Invoice.cancelled_at` |
| `backend/app/services/billing.py` | 新增方法 | `InvoiceService.cancel_invoice()` |
| `backend/app/routes/billing.py` | 新增路由 | `POST /invoices/:id/cancel` |
| `frontend/src/api/billing.ts` | 新增函数 + 类型 | `cancelInvoice()` + `cancelled_at` |
| `frontend/src/views/billing/Invoices.vue` | 修改方法 | 4 个操作方法刷新详情 |
| `frontend/src/components/invoice/InvoiceTimeline.vue` | 新增节点 | 取消结算时间线节点 |

---

## 测试计划

### 后端测试

1. 测试 `cancel_invoice` 方法：
   - 草稿状态取消 → 成功
   - 待客户确认状态取消 → 成功
   - 已确认状态取消 → 失败
   - 不存在的结算单取消 → 失败

### 前端测试

1. 测试 Drawer 中操作后状态更新：
   - 确认结算单 → 按钮切换为「标记付款」，时间线新增节点
   - 取消结算单 → 按钮隐藏，时间线显示红色取消节点
   - 提交结算单 → 按钮切换为「确认结算单」，时间线新增节点
   - 完成结算 → 按钮隐藏，时间线显示绿色完成节点

---

## 验收标准

- [ ] 后端 `cancel_invoice` API 正常工作
- [ ] 前端调用取消 API 而非模拟成功
- [ ] Drawer 中操作后按钮状态自动更新
- [ ] 时间线显示新增的操作节点
- [ ] 取消节点显示红色，完成节点显示绿色
- [ ] 所有现有测试通过
