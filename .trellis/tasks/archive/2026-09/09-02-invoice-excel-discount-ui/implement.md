# Implement: 结算单明细文件生成+减免金额重构+详情UI优化

## 执行计划

### Phase 1: 后端数据层 + Excel 生成服务

- [ ] 1.1 创建 Alembic 迁移：Invoice 新增 `detail_file_path`, `detail_file_status` 字段
  - 文件: `backend/alembic/versions/p5q6r7s8t9u0_add_invoice_detail_file_fields.py`
  - down_revision: `o4p5q6r7s8t9`
  - 验证: `alembic upgrade head` 成功

- [ ] 1.2 修改 Invoice 模型：添加新字段
  - 文件: `backend/app/models/billing.py` — Invoice class
  - 添加: `detail_file_path = Column(String(255), nullable=True)` 和 `detail_file_status = Column(String(20), default="pending", nullable=False)`

- [ ] 1.3 创建 Excel 生成服务
  - 新建: `backend/app/services/invoice_excel.py`
  - 类: `InvoiceExcelService`
  - 方法:
    - `generate_detail_file(invoice_id, customer_id, period_start, period_end)` → 主方法
    - `_fetch_order_details(group_type, start, end, external_engine)` → 查询外部 DB
    - `_build_excel(invoice, customer, order_details, items)` → 生成 Excel (Sheet1 合计 + Sheet2 明细)
    - `_save_file(workbook, invoice_no)` → 保存到 `uploads/invoices/{YYYY}/{MM}/`
  - 依赖: `openpyxl`, `external_engine`, `InvoiceRepository`

- [ ] 1.4 创建异步任务
  - 新建: `backend/app/tasks/invoice_detail_generator.py`
  - 函数: `generate_invoice_detail(session_factory, external_engine, invoice_id)`
  - 逻辑: 读取 Invoice → status='generating' → 生成 → status='completed' / 'failed'
  - 错误处理: 捕获异常, status='failed', 记录到 logger

- [ ] 1.5 修改结算单生成路由：触发异步任务
  - 文件: `backend/app/routes/billing/invoices.py`
  - `generate_invoice` 路由: 创建 Invoice 后, `detail_file_status='pending'`, `scheduler.add_job(generate_invoice_detail, ...)` 即时触发
  - `generate_invoices_batch` 路由: 批量场景为每个 Invoice 触发异步任务

- [ ] 1.6 新增下载接口
  - 文件: `backend/app/routes/billing/invoices.py`
  - `GET /invoices/<id>/download-detail` → 返回 `response_file`
  - 校验: `detail_file_status == 'completed'` 且文件存在

- [ ] 1.7 新增重新生成接口
  - 文件: `backend/app/routes/billing/invoices.py`
  - `POST /invoices/<id>/regenerate-detail` → 重置 status='pending', 触发异步任务

- [ ] 1.8 新增结算单日志接口
  - 文件: `backend/app/routes/billing/invoices.py`
  - `GET /invoices/detail-logs` → 分页查询所有结算单的 `detail_file_status`, `invoice_no`, `customer_name`, `period`, 生成时间, 错误信息
  - 支持筛选: status, customer_id, date_range

- [ ] 1.9 修改列表和详情接口返回
  - `GET /invoices` 列表: 增加 `detail_file_status`
  - `GET /invoices/<id>` 详情: 增加 `detail_file_path`, `detail_file_status`

### Phase 2: 后端减免金额重构

- [ ] 2.1 修改 `apply_discount` 服务方法
  - 文件: `backend/app/services/billing.py` — `apply_discount()`
  - 移除: `if discount_amount > invoice.total_amount` 校验
  - 新增: `if discount_amount == 0` 校验（减免金额不能为 0）

- [ ] 2.2 修改 `submit_invoice` 路由：接收减免参数
  - 文件: `backend/app/routes/billing/invoices.py` — `submit_invoice()`
  - Body 增加可选字段: `discount_amount`, `discount_reason`, `discount_attachment`
  - 如果传入了减免信息, 先调用 `apply_discount`, 再执行 `submit_invoice`

### Phase 3: 前端 — API 层 + 类型

- [ ] 3.1 更新 Invoice 类型定义
  - 文件: `frontend/src/api/billing.ts`
  - Invoice interface 增加: `detail_file_path?: string`, `detail_file_status?: string`
  - 新增函数: `downloadInvoiceDetail`, `regenerateInvoiceDetail`, `getInvoiceDetailLogs`
  - `submitInvoice` 增加可选参数: `discount_amount`, `discount_reason`, `discount_attachment`

### Phase 4: 前端 — 减免金额重构 (R2)

- [ ] 4.1 重构 `DiscountModal.vue` → `SubmitModal.vue`
  - 文件: `frontend/src/views/billing/components/DiscountModal.vue` (重命名)
  - 标题改为"提交结算单"
  - 金额字段: 去掉 `:min="0"`, 改为允许负值
  - 字段标签: "折扣金额" → "减免金额", "申请原因" → "减免说明"
  - 增加说明文字: "正值=减免，负值=加价"
  - 提交时同时调用 applyDiscount + submitInvoice (或合并为一次调用)

- [ ] 4.2 更新 `Invoices.vue` 引用
  - 文件: `frontend/src/views/billing/Invoices.vue`
  - 引用从 DiscountModal 改为 SubmitModal
  - 列表页表头: "折扣" → "减免"
  - 列表页金额显示: 减免金额为正显示绿色 -，为负显示红色 +

### Phase 5: 前端 — 详情页 UI 优化 (R1 + R3)

- [ ] 5.1 修改 `InvoiceDetailDrawer.vue`
  - 文件: `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`
  - "折后金额" → "最终结算金额"
  - "折扣金额" → "减免金额", "折扣原因" → "减免说明"
  - 优化金额层次: 用卡片式呈现（总金额 → 减免金额 → 最终结算金额）
  - 增加下载按钮: `detail_file_status === 'completed'` 时可下载, `'generating'` 时显示加载提示, `'failed'` 时显示重试按钮
  - 增加 `detail_file_status` 状态指示

- [ ] 5.2 列表页增加文件生成状态指示
  - 文件: `frontend/src/views/billing/Invoices.vue`
  - 增加"文件"列或状态图标: ✅(completed) / ⏳(generating) / ❌(failed) / -(pending)

### Phase 6: 前端 — 结算单日志页面 (R1.9)

- [ ] 6.1 新建 `InvoiceDetailLogs.vue` 页面
  - 文件: `frontend/src/views/system/InvoiceDetailLogs.vue`（或 billing 下）
  - 参考 `SyncLogs.vue` 结构
  - 列: 结算单号 | 客户名称 | 结算周期 | 文件状态 | 生成时间 | 操作（下载/重新生成）
  - 筛选: 状态, 客户, 日期范围
  - 分页

- [ ] 6.2 添加路由
  - 文件: `frontend/src/router/index.ts`
  - path: `system/invoice-detail-logs`
  - meta: `{ requiresPermission: 'system:view' }`

- [ ] 6.3 添加侧边栏入口
  - 文件: `frontend/src/components/layout/AppSidebar.vue`
  - 在"系统工具"组中添加"结算单日志"按钮

### 验证

```bash
# 后端
cd backend && ruff check app/
cd backend && python -m pytest tests/ -v
cd backend && alembic upgrade head

# 前端
cd frontend && pnpm type-check
cd frontend && pnpm build
```

### 风险点

- 外部数据库 SQL 29 列映射需联调测试，部分字段可能需要额外 JOIN
- `scheduler.add_job` 即时触发在 Sanic async 上下文中需确认不阻塞请求
- `openpyxl` 生成大 Excel 文件可能内存占用高（数百行级别无问题）
