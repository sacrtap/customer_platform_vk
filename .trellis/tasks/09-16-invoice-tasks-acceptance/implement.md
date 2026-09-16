# 结算单两任务验收与归档 — 实施记录

**执行日期**：2026-09-16
**验收对象**：`09-02-invoice-excel-discount-ui`（7 项 AC）、`09-03-invoice-preview-enhance`（10 项 AC）

## 验收环境

| 项 | 值 |
|---|---|
| 后端 | `http://localhost:8000`（用户启动进程，**无 `--reload`**，故修复需新实例验证） |
| 验证实例 | `http://127.0.0.1:8001`（验收期间另起，加载含修复的代码；收尾时已停止） |
| 前端 | `http://localhost:5173`（vite，HMR 生效） |
| 数据库 | PostgreSQL 5432；外部 MySQL 可连接（`nest_model_order`） |
| 登录 | `admin` / `admin123` |

## 一、09-03-invoice-preview-enhance 验收结果（10/10 通过）

| AC | 结论 | 证据 |
|---|---|---|
| AC1 周期保留 + 客户清空 | ✅ **修复后通过** | 浏览器：关闭前 `customer=太平洋房屋`、`period=2026-07-01~2026-07-31`；点「取消」关闭（校验 `getBoundingClientRect().width=0`）后重开 → `customer=""`、`period` 保留、预览清空。**首次判定为不通过**（客户输入框仍显示旧客户名），修复见「三、修复 2」 |
| AC2 选客户自动刷新 | ✅ 通过 | 周期已有值（2026-08-01~08-31）时选定客户「太平洋房屋」→ 预览自动出现，无需手动改周期 |
| AC3 改周期自动刷新 | ✅ 通过 | 周期 2026-08-01~08-31 → 改 2026-07-01~07-31 后预览自动刷新：单层 4644→4590 单、合计 ¥76,800.00→¥76,455.00 |
| AC4 定价渲染 | ✅ 通过 | 预览「计费类型=定价 / 设备类型=L / 楼层=单层 / 用量=4644 / 计费规则=单价 ¥15.00/单 / 小计=¥69,660.00」 |
| AC5 阶梯渲染 | ✅ 通过 | 临时造样本后实测：`阶梯` + `0~1000 @ ¥10.00 / 1001~5000 @ ¥8.00 / 5001+ @ ¥5.00` + `平均单价 ¥8.59`，两行合计 ¥33,792.00，与 API 返回 `subtotal` 29122+4670 完全一致 |
| AC6 包年不限量渲染 | ✅ 通过 | 临时造样本后实测：`包年 — — 3752 层` + `不限量套餐 年费 ¥36,500.00 → 日费 ¥100.00` + `周期 31 天 × ¥100.00/天`，小计 ¥3,100.00 |
| AC7 包年限量渲染 | ✅ 通过 | 客户 11423 原规则实测：`包年 — — 3586` + `限量套餐 年费 ¥55,000.00 / 套餐内 10000 单 @ ¥5.50/单 / 套餐内费用 ¥19,723.00`，小计 ¥19,723.00（用量未超限，故不渲染超量行，符合 `overQty > 0` 才输出的实现） |
| AC8 多规则多行 | ✅ 通过 | 客户 11420 两条 fixed 规则（单层/多层）→ 预览渲染 2 行，各带独立单价与小计 |
| AC9 API 字段透传 | ✅ 通过 | `POST /billing/invoices/calculate-items`（客户 11421，2026-08）→ `code=0`，首条 item **19 个键**且无缺失：`pricing_type`/`package_type`/`limit_count`/`over_limit_quantity`/`over_limit_unit_price`/`over_limit_cost`/`usage_cost`/`period_days`/`pricing_rule_id`/`tiers` 等 |
| AC10 批量周期保留 | ✅ 通过 | 批量模式设周期 2026-08-01~08-31 → 取消关闭 → 重开（默认回 customer 模式）→ 切「按计费类型」→ 批量周期仍为 2026-08-01~08-31 |

### 关于 AC5/AC6 的样本构造（Resolved Decision #1 授权的写入性验收）

库中计费规则实际分布为：`fixed` 12 条（6 客户）、`package/A`（限量）2 条，**无 `tiered`、无 `package-unlimited` 样本**。为满足 AC-3「UI 行为须有实跑证据」，临时改造 `pricing_rules.id=34`（客户 11423 长春新发地产）：

1. → `tiered` + `tiers={"ranges":[...]}` + `device_type='L'`/`layer_type='single'`（AC5）
2. → `package` + `package_limits={"base_fee":36500,"is_unlimited":true,...}`（AC6）

**已恢复原值**并校验：`package` / `package_type=A` / `unit_price=150.68` / `package_limits={"base_fee":55000.0,"is_unlimited":false,"limit_count":10000,"over_limit_unit_price":5.5}` / `tiers=NULL` / `device_type=NULL` / `layer_type=NULL`。

> 构造过程中发现一处**后端健壮性观察项（非本次 AC 范围）**：`_calculate_tiered_price` 直接读 `tiers["ranges"]`，若 `tiers` 被写成裸数组（前端 `parseTiers` 同时兼容数组与对象两种形态），后端会抛 `AttributeError` 并返回 HTTP 500，而非降级为 0 或 400。已恢复原值，未做改动，建议另开任务评估。

## 二、09-02-invoice-excel-discount-ui 验收结果（10/10 通过）

| AC | 结论 | 证据 |
|---|---|---|
| AC1 生成 + 下载 | ✅ 通过 | `GET /billing/invoices/39/download-detail` → HTTP 200、**208,201 bytes**、响应体以 `PK` 开头（有效 xlsx） |
| AC1b 状态字段 | ✅ 通过 | 列表接口首条含 `detail_file_status=pending`；详情接口同字段；`detail-logs` 返回 `completed` 记录 |
| AC1c 侧边栏日志入口 | ✅ 通过 | 浏览器 `/system/invoice-logs` 渲染「结算单日志 / 监控结算单明细文件生成状态 / 刷新 / 表格」。**接口层首次为 HTTP 500**，修复见「三、修复 1」；修复后同一接口返回 `code=0`、`total=5`，首条 `customer_name=房大全`、`detail_file_status=completed` |
| AC1d 重新生成 | ✅ 通过 | `POST /billing/invoices/39/regenerate-detail` → `code=0`「明细文件重新生成中」；轮询 `pending→generating→completed`（约 6 秒） |
| AC2 双 Sheet 与结构 | ✅ 通过 | 下载文件用 openpyxl 读取：Sheet 列表 **`['合计','2026-08','计费明细']`**（含「合计」汇总页与月份明细页）；明细表头 **29 列**、与 `DETAIL_HEADERS` 逐项比对**缺失=无**；数据 **1023 行** |
| AC3 数据来源与映射 | ✅ 通过 | `DETAIL_SQL` 引用的 21 个字段在外部库 `nest_model_order` 中**缺失=无**；外部库样例与 Excel 明细样例字段可对应（`房源名称`/`房源编号`/`订单编号`/`项目链接` 等） |
| AC4 提交可填减免（含负值） | ✅ 通过 | 「提交结算单」弹窗字段：`请输入减免金额（可为负值）`（`min=null`，无 `min=0`）、`填写了减免金额时必填`（减免说明）、`file`（附件）；提示语「正值为减免，负值为加价；不填则无减免」。`DiscountEditModal` 同样无 `min` 限制 |
| AC5 最终金额计算 | ✅ 通过 | 写入性验收：对 `INV-20260916-10297-2316`（总金额 ¥1,234.56）提交**负减免 -100** → 列表显示 `总金额 ¥1,234.56 / 减免金额 +¥100.00 / 最终结算金额 ¥1,334.56`（= 1234.56 − (−100)，负值=加价正确） |
| AC6 详情页文案 | ✅ 通过 | 详情抽屉显示 `总金额 ¥1,234.56 / 减免金额 无减免 / 最终结算金额 ¥1,234.56`；`折扣` 与 `折后` **均不存在** |
| AC7 列表页文案 | ✅ 通过 | 表头 `总金额 减免金额 最终结算金额`。**首次判定为不通过**（仍渲染「折扣」），修复见「三、修复 3」，修复后 `折扣`/`折后` 在全 `frontend/src` 下**零残留** |

## 三、验收期间修复（3 处，均经 Resolved Decision #2 授权，取最小改动）

| # | 文件 | 改动 | 触发的不通过项 |
|---|---|---|---|
| 1 | `backend/app/routes/billing/invoices.py` | `get_invoice_detail_logs` 增加 `from sqlalchemy.orm import selectinload`，查询改为 `select(Invoice).options(selectinload(Invoice.customer))` | AC1c：序列化读 `inv.customer.name`，而 `Invoice.customer = relationship("Customer")` 未配置 `lazy="selectin"`，异步会话下懒加载抛 `MissingGreenlet` → HTTP 500 |
| 2 | `frontend/src/views/billing/components/GenerateInvoiceModal.vue` | 新增 `customerPickerKey` ref；`watch(() => props.visible)` 打开分支 `customerPickerKey.value += 1`；模板 `<CustomerAutoComplete :key="customerPickerKey">` | AC1：`CustomerAutoComplete` 的显示文本取自其内部 `displayText` ref（`:model-value="displayText"`），不随 `modelValue` 变化，父组件置 `form.customer_id = undefined` 无法清空输入框。09-03 的 Out of Scope 明确「不改动该组件本身」，故以 `:key` 重建实现 |
| 3 | `frontend/src/views/billing/Invoices.vue`、`frontend/src/composables/useInvoice.ts` | 表头 `折扣`→`减免金额`；提示语 `'折扣申请提交成功'`→`'减免申请提交成功'` | AC6/AC7：R2.4 要求不再出现「折扣」/「折后」字样，属残留 |

**修复后重跑**：AC1（周期保留 + 客户清空，完整重跑）、AC2/AC3/AC4/AC8（同流程复验，预览数值一致）、AC5/AC6/AC7（造样本实测）、AC1c（接口 200）、AC6/AC7（文案零残留）。

## 四、副作用登记（写入性验收产物）

| 类型 | 对象 | 说明 | 处置 |
|---|---|---|---|
| 结算单 | `INV-20260916-10297-2316`（id 见列表，猪用户，原总金额 ¥1,234.56） | AC4/AC5 验收：提交并写入减免 −100 → `最终结算金额 ¥1,334.56`，状态 `草稿`→`待客户确认` | **保留**（测试数据；如需回滚请清零 `discount_amount` 并回退状态） |
| 结算单 | `INV-20260904-11433-37PB`（id=39，客户 房大全） | AC1/AC1d 验收：`regenerate-detail` 重新生成明细文件（原 `completed` 但磁盘文件缺失，属环境数据不一致） | **保留**（重新生成即修复该不一致） |
| 文件 | `backend/uploads/invoices/2026/08/invoice_39.xlsx`（208 KB） | 上述重新生成的交付物 | 保留（正常业务产物） |
| 计费规则 | `pricing_rules.id=34`（客户 11423） | 为 AC5/AC6 临时改造为 `tiered` / `package-unlimited` | **已恢复原值**并校验（见一节末） |
| 验证实例 | 后端 `127.0.0.1:8001` | 因用户 8000 进程无 `--reload`，另起实例验证修复 | **已停止** |
| 临时脚本 | `/tmp/accept_l2_api.py`、`/tmp/accept_02_excel.py`、`/tmp/acceptance_files/invoice_39.xlsx`、`/tmp/ac_rule34_backup.txt` | 验收脚本与产物 | 均位于 `/tmp`，**不在仓库内**；已登记，可随时删除 |

## 五、附带结论

- **`backend/app/routes/billing/invoices.py` 的 `detail-logs` 500 属 09-02 遗留实现缺陷**（不影响 09-02 的 AC1/AC1b/AC1d 主链路，但直接导致 AC1c 入口不可用），已在本次修复。
- **环境数据不一致**：`invoice_39` 状态为 `completed` 但磁盘无文件（`backend/uploads/invoices/2026/` 为空，项目根 `uploads/invoices/2026/07/` 有 5 天前文件），说明历史上曾从不同 cwd 启动后端写入 `uploads/`。`FILE_STORAGE_PATH` 未设置，默认相对路径 `./uploads` 随 cwd 变化。重新生成后已一致，但**该配置风险建议另开任务处理**。
- 09-03 缺 `design.md`/`implement.md`：按 PRD「已知缺口」约定，以本记录补记，不补完整规划。

## 六、独立复核（`trellis-check` 子代理，只读）

复核 3 处修复，全部通过，无回归：

| 复核项 | 结论 |
|---|---|
| 修复 1 根因链 | 证实：`models/billing.py:152` `Invoice.customer` 未配 `lazy="selectin"`（对比 `:103` `PricingRule.customer` 配了）；`invoices.py:1730` 序列化读 `inv.customer.name`；原查询无预加载 → `MissingGreenlet` |
| 修复 1 运行时 | 另起 8002 实例实测 `GET /api/v1/billing/invoices/detail-logs` → **HTTP 200 / code=0 / total=5**，首条 `customer_name=房大全`；**反证**：去掉 `selectinload` 复现 `MissingGreenlet`，加上即恢复 |
| 修复 1 同类调用点 | 无遗漏：列表 `invoices.py:85`、详情 `:220` 经 `InvoiceService` 内部已 `selectinload(Invoice.customer)`（`services/billing.py:1401/1451`）；导出 `:1179-1181` 亦已预加载；其余 `select(Invoice)`（`tasks/invoice_generator.py:61`、`tasks/email_tasks.py:30`、`routes/webhooks.py:247/391`）不读该关系 |
| 修复 2 | `:key` 仅绑在唯一实例（`:22`）；递增位于 `watch(props.visible)` 的 `if (val)` 打开分支（`:390`）；`CustomerAutoComplete` 无 `props.modelValue` watcher，重建后 `displayText` 初值 `''` |
| 修复 3 | `frontend/` 全域检索 `折扣\|折后` **零匹配** |
| 表头宽度 | 90px 不截断（4 中文字 ≈ 48px + 20px padding < 90px；`.table` 为 `table-layout: auto` 且外层 `overflow: auto`） |
| 静态检查 | `vue-tsc --noEmit` exit 0 无输出；`ruff check app/routes/billing/invoices.py` All passed；`eslint` 上述 3 个前端文件 exit 0 |
| 资源回收 | 8002 实例已停（`exited exit=0`，端口无监听）；用户 8000 进程未受影响（PID 17004 存活，`/health` 200） |

### 范围外观察（未改动，建议另开任务）

后端仍存 8 处「折扣」字样，**不属于** 09-02 的 AC6/AC7（该两项明确限定「详情页」「列表页」前端文案）：

- `routes/billing/invoices.py:1259` 导出表头「折扣金额」
- `routes/billing/invoices.py:1365`、`:1595` 导入模板说明
- `routes/billing/invoices.py:1473`、`:1476`、`:1479` 导入校验错误文案
- `models/billing.py:126`、`middleware/audit.py:91` 注释

即：**同一份导出/导入文件里，前端叫「减免金额」、后端表头仍叫「折扣金额」**，语义一致性存在缺口。建议另开任务统一（含面向用户的导入错误文案）。
