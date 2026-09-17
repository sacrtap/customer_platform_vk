# 结算单明细文件生成+减免金额重构+详情UI优化

## Goal

在结算单创建流程中增加自动生成明细 Excel 文件能力，让运营人员可直接下载结算单明细供客户对账；同时将"折扣"语义重构为"减免"（允许负值=加价），并优化详情页信息呈现，使金额结构更易识别。

## Background

### 现有状态

- `Invoice` 模型已有 `discount_amount`(DECIMAL)、`discount_reason`(Text)、`discount_attachment`(String(255)) 字段
- 前端 `DiscountModal.vue` 弹窗标题"申请折扣"，`discount_amount` 限制 `min=0`，只允许正折扣
- 详情页 `InvoiceDetailDrawer.vue` 显示"折扣金额"和"折后金额"标签
- 后端已有 `openpyxl` 依赖和 Excel 导出功能（`/invoices/export` 导出列表）
- 项目已有 `external_mysql_engine`（外部 MySQL），`OrderSyncService` 已有查询 `nest_model_order` 的 SQL
- `DailyConsumption` 表存储按客户+日期+设备+楼层聚合的消费汇总，不包含逐条订单明细

### Excel 模板结构（参考文件）

模板文件：`/Users/sacrtap/Downloads/安溪如是VR房源模型消费2026年7月结算单.xlsx`

**Sheet 1 "合计"**（汇总信息）：
- 标题行：客户名称 + "VR房源模型消费结算汇总"
- 列：结算周期 | 单价（元/套）| 模型总数量（套）| 计费模型数量（套）| 模型金额（元）| 减免金额 | 模型费用结余（元）| 当月充值金额（元）| 备注

**Sheet 2 "月份明细"**（逐条订单，29 列）：
- 房源名称 | 房源id | 城市 | 业务部门 | 订单编号 | 项目链接 | 创建人 | 创建时间 | 所属人 | 面积 | 订单状态 | 编辑状态 | 备注 | 编辑人账号 | 编辑人姓名 | 上传完成时间 | 处理完成时间 | 第一次分配时间 | uv | pv | 户型图绘制时间 | 户型图最新绘制人 | 审核发布时间 | 楼层层数 | 设备编号 | 接单时间 | 复审状态 | 发布人 | 户型图修模状态

- 明细数据来自外部数据库 `nest_model_order` 表（通过 `external_mysql_engine` 查询）
- 数据库字段映射参考：`/Users/sacrtap/Documents/product_workspace/database/doc/db-map/订单数据字段图谱.md`

## Requirements

### R1: 创建结算单后异步生成明细 Excel 文件

**R1.1** 创建结算单成功后（`/invoices/generate` 和 `/invoices/generate-batch`），后端异步生成 Excel 明细文件并持久化存储。生成过程中结算单有状态指示（pending/generating/completed/failed）。

**R1.2** Excel 文件包含两个 Sheet：
- Sheet 1 "合计"：汇总信息（结算周期、单价、数量、金额、减免金额、结余等），格式参考模板
- Sheet 2 "月份明细"：逐条订单明细（29 列），数据从外部数据库 `nest_model_order` 查询

**R1.3** `Invoice` 模型新增字段：
- `detail_file_path`（String(255)）：生成的 Excel 文件路径
- `detail_file_status`（String(20)）：文件生成状态（pending/generating/completed/failed）

**R1.4** 详情接口 `GET /invoices/<id>` 返回 `detail_file_path` 和 `detail_file_status` 字段。列表接口同步返回 `detail_file_status`。

**R1.5** 新增下载接口 `GET /invoices/<id>/download-detail`，返回 Excel 文件。

**R1.6** 新增重新生成接口 `POST /invoices/<id>/regenerate-detail`，用于失败后手动触发重新生成。

**R1.7** 前端详情页 `InvoiceDetailDrawer.vue` 增加下载按钮（completed 时可点击）、生成中提示（generating 时）、重试按钮（failed 时）。

**R1.8** 结算单列表页显示明细文件生成状态指示（图标/文字）。

**R1.9** 侧边栏「系统工具」新增「结算单日志」入口，查看所有结算单的文件生成任务状态及记录日志（列表页，含状态筛选、时间、错误信息）。

### R2: 减免金额重构

**R2.1** 将"折扣"语义改为"减免"：`discount_amount` 允许为负值（负值=加价）。
- 最终结算金额 = 总金额 - 减免金额
- 减免金额 > 0 → 减免（减少结算金额）
- 减免金额 < 0 → 加价（增加结算金额）

**R2.2** 提交结算单时（draft → pending_ops 流程），增加减免金额、减免说明、减免附件的录入。

**R2.3** 前端提交操作需弹出表单填写减免信息（金额、说明、附件），替代或改造现有 `DiscountModal.vue`。
- 金额允许为负（去掉 `min=0` 限制）
- 减免说明改为必填
- 附件选填

**R2.4** 详情页和列表页中"折扣金额"改为"减免金额"，"折后金额"改为"最终结算金额"。

### R3: 详情页信息呈现优化

**R3.1** 详情页 `InvoiceDetailDrawer.vue` 中"折后金额"标签改为"最终结算金额"。

**R3.2** 优化金额信息呈现结构，使总金额、减免金额、最终结算金额的层次关系更清晰易读。

## Acceptance Criteria

- [ ] AC1: 创建结算单后，异步生成 Excel 明细文件，完成后可通过详情页下载
- [ ] AC1b: 列表页和详情页显示明细文件的生成状态（pending/generating/completed/failed）
- [ ] AC1c: 系统工具侧边栏有「结算单日志」入口，可查看所有生成任务状态
- [ ] AC1d: 明细文件生成失败后，可通过详情页重试按钮或「结算单日志」页面手动触发重新生成
- [ ] AC2: 下载的 Excel 包含两个 Sheet（合计+明细），格式与模板一致
- [ ] AC3: 明细 Sheet 数据来源于外部数据库 `nest_model_order`，字段映射正确
- [ ] AC4: 提交结算单时可填写减免金额（允许负值）、减免说明、附件
- [ ] AC5: 最终结算金额 = 总金额 - 减免金额（正负值均正确计算）
- [ ] AC6: 详情页显示"减免金额"和"最终结算金额"，不再出现"折扣"/"折后"字样
- [ ] AC7: 列表页同步更新标签文字

## Out of Scope

- Excel 模板样式（合并单元格、字体、边框等）的像素级还原——保持基本格式即可
- 外部数据库中无法匹配的订单的处理（暂跳过，日志记录）

## Resolved Decisions

1. **Excel 生成时机**：全部异步生成。单次和批量创建结算单后均异步生成 Excel 明细文件。列表页和详情页有生成中状态指示。侧边栏「系统工具」新增「结算单日志」入口查看所有生成任务状态及记录。

2. **外部数据库不可用时**：仍允许创建结算单，`detail_file_status` 标记为 `failed`，后续可通过详情页重试按钮或「结算单日志」页面手动触发重新生成。

3. **明细文件存储位置**：本地 `uploads/invoices/` 目录，按年月分子目录（如 `uploads/invoices/2026/07/`）。
