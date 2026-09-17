# Design: 结算单明细文件生成+减免金额重构+详情UI优化

## Architecture & Boundaries

### 层次划分

```
R1 Excel 生成:
  routes/billing/invoices.py   → 新增 download-detail, regenerate-detail 路由
  services/invoice_excel.py    → 新建 Excel 生成服务（查询外部 DB + 生成 Excel）
  tasks/invoice_detail_generator.py → 异步任务（APScheduler add_job 即时执行）
  models/billing.py            → Invoice 新增 detail_file_path, detail_file_status
  alembic migration             → 新增字段迁移

R2 减免重构:
  services/billing.py          → apply_discount 去掉 >total_amount 校验，允许负值
  routes/billing/invoices.py   → submit 路由增加 discount 参数接收
  frontend/components/DiscountModal.vue → 重命名为 SubmitModal，金额允许负值
  frontend/api/billing.ts      → submitInvoice 增加减免参数

R3 详情 UI:
  frontend/components/InvoiceDetailDrawer.vue → 标签重命名 + 金额层次优化 + 下载按钮
  frontend/views/billing/Invoices.vue       → 列表页标签同步
```

### 关键设计决策

## Data Flow

### R1: Excel 生成流程

```
1. POST /invoices/generate (或 /invoices/generate-batch)
   → InvoiceService.generate_invoice() 创建 Invoice
   → detail_file_status = 'pending'
   → commit
   → 触发异步任务: _generate_invoice_detail(invoice_id, customer_id, period_start, period_end)

2. 异步任务执行:
   → detail_file_status = 'generating'
   → 查询外部 DB: nest_model_order + JOIN nest_user (按 group_type 匹配客户)
   → 查询本库: InvoiceItem (计费明细), Customer (客户名称)
   → 生成 Excel (openpyxl): Sheet1 合计 + Sheet2 明细
   → 保存到 uploads/invoices/{YYYY}/{MM}/{invoice_no}.xlsx
   → detail_file_path = 文件路径
   → detail_file_status = 'completed'
   → 异常时: detail_file_status = 'failed', 记录日志

3. GET /invoices/<id>/download-detail
   → 读取 detail_file_path
   → 返回文件流

4. POST /invoices/<id>/regenerate-detail
   → 重置 detail_file_status = 'pending'
   → 触发异步任务
```

### R2: 减免金额流程

```
提交结算单时 (draft → pending_ops):
1. 前端弹出 SubmitModal (原 DiscountModal 重命名)
   → 填写: 减免金额(允许负值), 减免说明(必填), 附件(选填)
   → 提交时调用 applyDiscount(invoice_id, {discount_amount, discount_reason, attachment})
2. 后端 apply_discount():
   → 去掉 discount_amount > total_amount 校验
   → 保留 discount_amount != 0 校验
   → 更新 discount_amount, discount_reason, discount_attachment, discount_applied_at
3. submitInvoice(invoice_id) → 状态从 draft → pending_ops
```

### 外部数据库 SQL（明细 Sheet 数据源）

基于现有 `OrderSyncService._fetch_orders` SQL 扩展，查询 `nest_model_order` + JOIN `nest_user` 获取完整 29 列数据：

```sql
SELECT
  D.project_name,          -- 房源名称
  D.custom_code,            -- 房源id
  D.city,                  -- 城市
  D.department,            -- 业务部门
  D.order_code,            -- 订单编号
  CONCAT('https://beyond.3dnest.cn/house/?m=', D.nest_id) AS project_link,  -- 项目链接
  U_creator.owner_name,    -- 创建人
  D.create_date,           -- 创建时间
  U_personal.owner_name,   -- 所属人
  D.nest_area,             -- 面积
  -- order_status 映射为中文
  D.order_status,
  -- 编辑状态、备注等字段需 LEFT JOIN nest_edit_task
  D.remarks,               -- 备注
  -- ... 其他字段按 db-map 映射
FROM nest_model_order D
LEFT JOIN nest_user U_creator ON U_creator.id = D.creator
LEFT JOIN nest_user U_personal ON U_personal.id = D.personal
WHERE D.group_type = :group_type
  AND D.upload_date >= :start AND D.upload_date < :end
  AND D.nest_id != ''
  AND ((D.order_status > 3 AND D.order_status < 11) OR D.order_status = 15)
ORDER BY D.create_date DESC
```

注意：29 列中部分字段（uv/pv、编辑人账号/姓名、审核发布时间等）可能需要额外 JOIN 或在第一版中留空/标注"-"。按 PRD Out of Scope 处理：无法匹配的暂跳过。

## API Contracts

### 新增接口

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| GET | `/invoices/<id>/download-detail` | 下载 Excel 明细文件 | billing:view |
| POST | `/invoices/<id>/regenerate-detail` | 重新生成 Excel | billing:edit |
| GET | `/invoices/detail-logs` | 结算单日志列表（分页+筛选） | billing:view |

### 修改的接口

| Method | Path | 变更 |
|--------|------|------|
| GET | `/invoices` | 列表返回增加 `detail_file_status` |
| GET | `/invoices/<id>` | 详情返回增加 `detail_file_path`, `detail_file_status` |
| POST | `/invoices/<id>/submit` | 接收可选 `discount_amount`, `discount_reason`, `discount_attachment`（减免信息随提交一起传入） |
| PUT | `/invoices/<id>/discount` | 去掉 `discount_amount > total_amount` 校验 |

### 前端 API 新增

```typescript
// frontend/src/api/billing.ts
export function downloadInvoiceDetail(id: number) {
  return api.get(`/billing/invoices/${id}/download-detail`, { responseType: 'blob' })
}
export function regenerateInvoiceDetail(id: number) {
  return api.post(`/billing/invoices/${id}/regenerate-detail`)
}
export function getInvoiceDetailLogs(params?: {...}) {
  return api.get('/billing/invoices/detail-logs', { params })
}
```

## Compatibility & Migration

### Alembic 迁移

新增迁移：`p5q6r7s8t9u0_add_invoice_detail_file_fields.py`
- down_revision: `o4p5q6r7s8t9` (最新迁移)
- 新增 Invoice 字段：
  - `detail_file_path` String(255), nullable=True
  - `detail_file_status` String(20), default='pending', nullable=False

### 向后兼容

- `discount_amount` 字段保持不变，语义从"折扣（正数减价）"扩展为"减免（正减负加）"
- `final_amount` 计算公式不变：`total_amount - discount_amount`（负数时自动加价）
- 现有数据 `discount_amount=0` 的结算单不受影响
- `apply_discount` 方法现有校验 `discount_amount > total_amount` 需移除，改为不校验上限（或只校验 `discount_amount != 0`）

## Trade-offs

1. **Excel 生成使用 APScheduler 即时异步**：不新建消息队列，复用现有 `scheduler.add_job()` 即时触发。缺点：服务器重启时正在生成的任务会丢失（`detail_file_status` 卡在 `generating`）。缓解：`regenerate-detail` 接口可手动重试。
2. **29 列部分字段留空**：第一版不 JOIN 所有表（uv/pv 等需要额外查询），无法获取的字段显示为"-"。
3. **文件存储本地**：不支持水平扩展。如后续部署多节点，需迁移到 OSS。
