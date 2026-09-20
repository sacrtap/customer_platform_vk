# Journal - sacrtap (Part 1)

> AI development session journal
> Started: 2026-08-12

---



## Session 1: 余额燃尽列：趋势列重设计为 burn-down 可视化

**Date**: 2026-08-12
**Task**: 余额燃尽列：趋势列重设计为 burn-down 可视化
**Branch**: `main`

### Summary

基于会议讨论实现余额燃尽功能：后端 get_balances API 扩展 daily_avg_cost/consumption_days/days_remaining 三字段（基于 daily_consumptions 真实数据+CTE 排序+Redis L1 缓存），前端合并趋势+预计耗尽两列为油表进度条（满=安全/空=紧急），新增即将耗尽 KPI 卡片，修复 Home 页 balance_days 恒等于 30 的 bug。9 文件变更，492 插入 201 删除，lint+type-check+测试全部通过。

### Git Commits

| Hash | Message |
|------|---------|
| `103a48d` | (see git log) |

### Status

[OK] **Completed**

---

## Session 2: 包年结算规则优化：设备类型和楼层类型字段可选化

**Date**: 2026-08-12
**Task**: 包年结算规则优化：设备类型和楼层类型字段可选化
**Branch**: `pricing-rules-bug-fix`

### Summary

包年结算只与套餐类型和时间有关，不应要求设备类型/楼层类型。改动：
- **后端模型**：`PricingRule.device_type` 与 `InvoiceItem.device_type` 改为 nullable
- **数据库迁移**：新增 `j9e0f1g2h3i4`，ALTER 两表 device_type DROP NOT NULL
- **后端服务**：新增 `_check_package_overlap`/`_check_package_conflict`，包年规则冲突只按 customer_id + pricing_type='package' + 有效期判断；create/update 走独立包年分支
- **费用计算**：cost_calc 新增 `_get_active_package_rule`，包年规则优先于 (device_type, layer_type) 匹配；发票明细生成同样优先包年规则
- **路由**：冲突检查端点 pricing_type 必填、device_type/layer_type 可选
- **前端**：PricingRuleModal 包年时隐藏设备/楼层字段、提交不传；列表设备类型显示 "-"；发票明细展示 "包年"
- **测试**：新增包年冲突/创建/费用计算用例，59 个相关单元测试 + 46 个 billing 集成测试全部通过

### Verification

- 后端 394 单元测试 + 46 billing 集成测试通过
- 前端 vue-tsc + eslint 通过
- 浏览器实测：包年弹框隐藏设备/楼层、创建/冲突检查/编辑回显/列表展示全部验证
- 数据库迁移已应用（alembic current = head）

### Git Commits

（未提交，等待 review 后提交）

### Status

[OK] **Implemented & Verified**（待提交）


## Session 2: 包年结算规则优化：设备类型和楼层类型字段可选化

**Date**: 2026-08-12
**Task**: 包年结算规则优化：设备类型和楼层类型字段可选化
**Branch**: `pricing-rules-bug-fix`

### Summary

包年结算只与套餐类型和时间有关，不应要求设备类型/楼层类型。后端 PricingRule/InvoiceItem device_type 改为 nullable，新增迁移；包年规则冲突检查只按 customer_id + pricing_type='package' + 有效期；cost_calc 包年规则优先于 (device_type, layer_type) 匹配；前端包年结算时隐藏设备/楼层字段，提交不传，列表展示 '-'。

### Git Commits

| Hash | Message |
|------|---------|
| `ea2be12` | (see git log) |

### Status

[OK] **Completed**


## Session 3: 余额管理增量同步与数据一致性修复

**Date**: 2026-08-12
**Task**: 余额管理增量同步与数据一致性修复
**Branch**: `pricing-rules-bug-fix`

### Summary

余额管理页只显示9个客户，根因是数据不一致：存量客户未建余额记录+测试客户软删未清理余额。一次性脚本删除310条孤儿记录、回填353条；get_balances惰性补建缺失余额记录（幂等、单次200条）；create_customer防御性按需创建；delete_customer同步软删余额；两页默认排序统一为company_id升序。验证：活跃客户1480=余额记录1480完全对齐，394单测+46集成通过。

### Git Commits

| Hash | Message |
|------|---------|
| `ad3ef5e` | (see git log) |

### Status

[OK] **Completed**


## Session 4: 预测消费页面 MVP 实现

**Date**: 2026-08-12
**Task**: 预测消费页面 MVP 实现
**Branch**: `feature/optimize-forecast-page`

### Summary

将预测回款页面改造为预测消费：基于 order_count 用量 × 单价矩阵估算消费、冷启动按消费等级分层、离群截断、活跃度判断、置信度计算。新增 3 接口（forecast/forecast-trend/data-readiness）、预测准确度追踪（MAPE 日志）、前端页面重构（数据就绪度横幅/置信度标签/设备拆解图/方法标注）。7 个单元测试。

### Git Commits

| Hash | Message |
|------|---------|
| `3ed7858` | (see git log) |

### Status

[OK] **Completed**

## 2026-08-13 预测消费单价配置 UI 优化

**任务**: forecast-price-config (已归档)
**提交**: 3a9b2aa feat(analytics): 预测消费单价配置UI与参数控制

### 完成内容
1. **后端**：
   - 新增 ForecastUnitPrice 模型（直接继承 Base，非 BaseModel）
   - GET/PUT /consumption/price-config API
   - 扩展 forecast/trend 接口支持 apply_to/forecast_months/forecast_until
   - 缓存 key 含参数，PUT 时 invalidate 预测缓存

2. **前端**：
   - 移除内联配置面板，改为筛选区"预测参数"按钮
   - 弹框式配置：单价输入 + 预测范围 radio + 月数 select
   - 保存时显示进度弹框（模拟进度条 + 阶段提示）
   - 取消时还原修改

3. **Bug 修复**：
   - ForecastUnitPrice 继承 BaseModel 导致生产 500（表缺少 id/deleted_at 列）
   - 改为直接继承 Base，手动声明三列

### 验证
- 后端 ruff check ✅
- 后端单元测试 ✅
- 前端 vue-tsc ✅
- 浏览器端到端验证 ✅（弹框打开/保存/进度/取消全流程）


## Session 5: 修复预测消费页面 apply_to 参数逻辑和年份选择器类型错误

**Date**: 2026-08-13
**Task**: 修复预测消费页面 apply_to 参数逻辑和年份选择器类型错误
**Branch**: `feature/optimize-forecast-page`

### Summary

1. 后端 get_forecast_trend 方法支持 apply_to 参数动态计算月份范围（all/future_only）\n2. 前端修复 selectedYear 类型处理，兼容 Date/dayjs/string 三种情况\n3. 前端图表根据后端返回数据动态生成 X 轴标签

### Git Commits

| Hash | Message |
|------|---------|
| `7de5a25` | (see git log) |

### Status

[OK] **Completed**


## Session 6: ERP 系统管理模块 + 客户筛选器增强 + account_type 修复 + company_id 唯一性检查

**Date**: 2026-08-25
**Task**: ERP 系统管理模块 + 客户筛选器增强 + account_type 修复 + company_id 唯一性检查
**Branch**: `main`

### Summary

完成 ERP 系统管理模块（模型/服务/路由/迁移/前端页面），客户筛选器支持更多展开（ERP系统/合作状态/结算方式），修复 account_type 选项不一致和 create_customer company_id 唯一性检查缺失问题

### Git Commits

| Hash | Message |
|------|---------|
| `e6bc38b` | (see git log) |

### Status

[OK] **Completed**


## Session 7: 开放平台API-Key管理与ERP余额查询接口

**Date**: 2026-08-26
**Task**: 开放平台API-Key管理与ERP余额查询接口
**Branch**: `add-qiangfang-balances`

### Summary

实现开放平台API-Key管理模块和ERP渠道客户余额查询API。后端新增ApiKey模型/服务/路由，auth中间件增加/api/v1/erp/前缀的API-Key认证分支，实现GET /api/v1/erp/balances接口。前端新增ApiKeyManagement管理页面和OpenApiGuide文档页面（/openapi公开访问）。修复sanic-ext蓝图名冲突（openapi→open_platform）和前端响应数据解析问题。渠道编码表动态从ERP系统配置加载。

### Git Commits

| Hash | Message |
|------|---------|
| `21ec5d5` | (see git log) |

### Status

[OK] **Completed**


## Session 8: 订单结算范围扩大+时区重构+同步日志加固
<!-- trellis-session: v=2 fp=075305e168199a03 -->

**Date**: 2026-09-07
**Task**: 订单结算范围扩大+时区重构+同步日志加固
**Branch**: `check-order-nums`

### Summary

将订单同步SQL过滤条件从 order_status > 3 AND < 11 改为 >= 3 AND <= 12，移除 nest_id != '' 过滤。sync_date 从 date 升级为 datetime(timezone=True)，全链路使用 UTC 范围查询。sync_task_service 新增数据完整性校验方法和逐天同步日志加固。修复 timezone.py utc_to_cst_date_str 兼容 date 对象。排查确认广州共和地产 144 vs 145 差异根因为 status=3 被正确过滤。全量验证 23 个客户订单数，7 个精确匹配，其余差异来自外部数据源本身。

### Git Commits

| Hash | Message |
|------|---------|
| `6d0c54a` | fix(billing): 扩大订单结算范围+时区重构+同步日志加固 |

### Status

[OK] **Completed**


## Session 9: better-harness 4 个 finding 修复 + 收尾摩擦消除
<!-- trellis-session: v=2 fp=41064c8b6909eb20 -->

**Date**: 2026-09-12
**Task**: better-harness 4 个 finding 修复 + 收尾摩擦消除
**Branch**: `fix-bug`

### Summary

修复 billing-validation-loop/billing-no-diagnostics/migration-no-gate/no-correlation-id 4 个 finding；lifecycle-tail-friction：pre-commit 环境规则、提交→finish-work 次序文档化、pre-push 阻塞修复（级联删测试断言+industry_type_id）、收尾全链路验证

### Git Commits

| Hash | Message |
|------|---------|
| `8f375c4` | chore(workflow): 明确提交与 finish-work 次序 + pre-commit 环境规则落地 |
| `33fd579` | fix(quality): 修复 pre-push 阻塞 - 级联删除测试断言与 industry_type_id 类型 |
| `094a3a4` | chore(task): archive 09-12-lifecycle-tail-verify |

### Status

[OK] **Completed**


## Session 10: 修复分析页面报错+角色权限清单修正+部署加固
<!-- trellis-session: v=2 fp=7764d308c608bed9 -->

**Date**: 2026-09-16
**Task**: 修复分析页面报错+角色权限清单修正+部署加固
**Branch**: `fix/health-prediction-bugs`

### Summary

1) 修复健康度分析与预测消费页面 500：get_inactive_customers 日期类型错误（date-datetime 相减 TypeError）+ forecast_unit_prices 表无迁移致远程缺表，补建迁移、注册模型、get_unit_prices 表缺失兜底，新增 6 项单元测试（b674bbf）。2) 按 ROLE_PERMISSION_CONFIG_PLAN.md 修正角色权限清单：analytics:forecast→forecast_edit、billing:export 接上控制点、删 7 孤儿权限（权限总数 49→42）、清理脚本追加 8 code（含历史残留 profiles:export）、permissionGroups 删冗余键、侧边栏补 4 入口、conftest 同步，并修复导出接口 response_file 传参 bug（648ba1c）。3) 部署加固：清理脚本增加代码引用校验（防误删在用权限，容器内无 frontend 自动降级），compose 新增 cleanup 一次性服务，deploy.sh 接入 migrate→seed→cleanup 链（d39e0ea）。

### Git Commits

| Hash | Message |
|------|---------|
| `b674bbf` | fix(analytics): 修复健康度分析与预测消费页面 500 报错 |
| `648ba1c` | fix(roles): 角色权限清单修正 - 消除 code 不一致与孤儿权限 |
| `d39e0ea` | chore(deploy): 弃用权限清理脚本接入部署流程并增加代码引用校验 |

### Status

[OK] **Completed**


## Session 11: 导入导出功能优化：结算页面补齐导入导出与权限码细粒度拆分
<!-- trellis-session: v=2 fp=a960171db6b0b824 -->

**Date**: 2026-09-16
**Task**: 导入导出功能优化：结算页面补齐导入导出与权限码细粒度拆分
**Branch**: `feature/import-export-optimization`

### Summary

检查客户管理导入导出链路并修复两处硬缺陷（模板中文说明行被当数据行、日期列写字符串导致 500）；为余额管理补导出、计费规则/包年套餐补导入导出、结算单管理补导入；权限码拆分 8 个细粒度码并完成存量等价迁移与旧码清理；新增集成测试 27 项；浏览器端到端验证五页面按钮/导出下载/模板下载及部分成功导入（成功1失败1，行号定位准确、列表刷新）；覆盖率 50.95% 达标
## Session 18: 同步日志执行信息优化与定时同步配置化
<!-- trellis-session: v=2 fp=8d717d52ed24607f -->

**Date**: 2026-09-18
**Task**: 同步日志执行信息优化与定时同步配置化
**Branch**: `feature/sync-execution-info`

### Summary

同步日志「错误信息」列改为「执行信息」三态（警告/正常/错误）+明细Drawer（含客户ID/名称）；定时任务合并为每日自动同步（原01:00订单+01:30费用），纳入同步日志页配置（开关/时间/模式，权限system:sync_schedule仅超管）；遗留/consumption/sync统一进任务链路。AC1-AC10全量实证通过（浏览器+接口）；发现并修复2个缺陷（迁移缺created_at/updated_at/deleted_at列、local_yesterday_utc_start().date()取UTC日期致同步前天而非昨天）。全量测试835 passed（28+3为既有失败）。

### Git Commits

| Hash | Message |
|------|---------|
| `043d2a5` | feat(billing): 结算页面补齐导入导出并细粒度拆分权限码 |
| `f5b3cdf` | docs(spec): 收录导入导出端点契约与前端组件规范 |

### Status

[OK] **Completed**


## Session 12: 运行期技术债修复：middleware logger / Blob 错误体 / 导入校验 / 无效补建
<!-- trellis-session: v=2 fp=a534966fa8fc325f -->

**Date**: 2026-09-16
**Task**: 运行期技术债修复：middleware logger / Blob 错误体 / 导入校验 / 无效补建
**Branch**: `feature/import-export-optimization`

### Summary

修复 5 项运行期缺陷：P1 middleware 误用 app.logger（共 5 处；request 中间件异常时返回 HTML 500 而非约定 JSON，真实异常被 AttributeError 掩盖）；P2 前端 axios 未解析 Blob 错误体（下载链路失败提示英文 Bad Request）；P3 计费规则导入缺 device_type/layer_type 行级校验（可写脏数据）；P4 docs/specs 旧权限码迁移至 billing:balance_import；P5 删除余额无效惰性补建（写入被回滚）并交付补偿脚本 backfill_balance_archives.sql。新增 3 个回归测试（中间件 JSON 500 / 导入字段校验 / 余额列表无写入）；相关集成测试 37 passed、unit+integration 690 passed 且覆盖率 51.47%；前端 type-check+lint 通过；浏览器实测五页面导入导出与模板下载。同步更新 spec：logging-guidelines（中间件禁用 app.logger，此为本次缺陷源头规范）、import-export（收录新增校验规则）、component-guidelines。另发现既有测试基础设施问题未在本次修复：同名测试文件跨目录冲突致 pytest 收集失败 2 例、根目录老测试引用已变更模型字段致 34 failed（使 make test-cov 失效）。

### Git Commits

| Hash | Message |
|------|---------|
| `76f71fc` | fix(runtime): 修复 middleware logger 误用、Blob 错误提示与导入校验 |

### Status

[OK] **Completed**


## Session 14: 测试基础设施修复：收集冲突、遗留测试过时与 3 处生产缺陷
<!-- trellis-session: v=2 fp=21d1c7bd65e22cf8 -->

**Date**: 2026-09-16
**Task**: 测试基础设施修复：收集冲突、遗留测试过时与 3 处生产缺陷
**Branch**: `feature/import-export-optimization`

### Summary

修复 pytest 全量收集冲突（--import-mode=importlib，恢复被同名遮蔽的 23 项）、tests/ 根目录遗留测试过时断言、.trellis 脚本产物缺尾换行导致的 pre-commit 反复阻断。定位过程中额外修复 3 处生产缺陷（customer_repo 的 cast 误用必抛 TypeError；sync_logs 返回体缺 task_id/operator_id/start_date/end_date/sync_mode；sync_task_service.get_progress 用 bytes 键查 decode_responses=True 的 Redis 导致进度恒为空）与 2 处测试隔离缺陷（JWT_SECRET 单例冲突致 e2e 401；mock_cache 未覆盖模块级 import 绑定致端点绕过 mock）。二分定位方法：tests/unit 根目录逐级收敛至 test_avatar_upload.py。最终 872 passed / 0 failed，覆盖率 57.61%，unit 447、integration 243。

### Git Commits

| Hash | Message |
|------|---------|
| `f94e54a` | fix(test): 修复全量测试收集冲突、遗留测试过时与 3 处生产缺陷 |

### Status

[OK] **Completed**


## Session 15: 结算单两任务验收与归档（09-02 / 09-03）
<!-- trellis-session: v=2 fp=5bb021c8faf5fc2c -->

**Date**: 2026-09-16
**Task**: 结算单两任务验收与归档（09-02 / 09-03）
**Branch**: `feature/import-export-optimization`

### Summary

逐条验收 09-02（7 AC）与 09-03（10 AC）共 17 项 AC，全部通过；期间发现并修复 3 处缺陷：detail-logs 端点因未预加载关系抛 MissingGreenlet 导致 500、生成结算单弹窗重开后客户输入框未清空、列表页与提交提示残留「折扣」文案；同步沉淀 2 条 spec 惯例（异步 ORM 关系序列化必须预加载、受控显示文本组件需 :key 重建）；两份 prd 的 AC 已回写并归档两个历史任务。

### Git Commits

| Hash | Message |
|------|---------|
| `8f82ba1` | fix(billing): 修复明细日志 500、弹窗客户清空与减免文案残留 |

### Status

[OK] **Completed**


## Session 16: 遗留项修复：清理任务误删业务凭证、tiers 契约冲突与文案统一
<!-- trellis-session: v=2 fp=a1efc468b7818758 -->

**Date**: 2026-09-17
**Task**: 遗留项修复：清理任务误删业务凭证、tiers 契约冲突与文案统一
**Branch**: `feature/import-export-optimization`

### Summary

定位并修复 09-16 验收暴露的四个遗留缺陷。主因：cleanup_temp_files 每日以存储根为 os.walk 起点且无排除规则，把 7 天前的业务文件当临时文件删除（DB 实测 5 条 completed 记录中 4 条文件缺失，不一致率 80%）；修复为物理收缩到 uploads/temp/ 子树并补软链接防御与启动期相对路径告警。次要：pricing_rules.tiers 契约冲突（导入写数组、结算读对象必 500）收敛为数组单一形态并建立前后端各一归一化 owner；min_quantity/threshold 键名残留清除；补 max>=min、price>=0 关系校验避免静默错值。后端 8 处用户可见折扣文案统一为减免（保留模板必填/可选前缀与列序）。前端三份 tiers 解析合并为单一实现。门禁：pytest 874 passed 覆盖率 58%、ruff check/format、pnpm type-check 全绿；浏览器实跑三处阶梯渲染正确。spec 更新 backend/file-storage.md（新增临时文件清理边界契约并修正事故根因归因）与 guides/cross-layer-thinking-guide.md（两处反面案例标注修复）。

### Git Commits

| Hash | Message |
|------|---------|
| `a619eda` | fix(billing): 修复清理任务误删业务凭证、tiers 契约冲突与文案不一致 |

### Status

[OK] **Completed**


## Session 17: 测试基础设施遗留项修复（TD-1/2/4/5 + R6）
<!-- trellis-session: v=2 fp=739135da0778c5f9 -->

**Date**: 2026-09-17
**Task**: 测试基础设施遗留项修复（TD-1/2/4/5 + R6）
**Branch**: `feature/import-export-optimization`

### Summary

修复 TD-1/2/4/5（TD-3 按用户要求排除）：42 项权限清单 4 处逐字副本收敛为 tests/_test_data.py 单一常量并加种子漂移守护；WEBHOOK_SECRET 收敛至 tests/conftest.py 一处 setdefault；移除 test_user 内 8 处 [DEBUG] stdout 探针；TTL 收敛为 _ttl_config + ttl_for() 单一入口（清 5 个零消费/谎值条目、拆 analytics_prediction_forecast 前缀、消除 analytics.py 9 处与 balances.py 1 处硬编码副本）。R6 删除 app/config.py 的 9 个零消费 cache_ttl_* 字段并清理 .env.example 与 cache-strategy.md 的误导性可配项文档。零行为变更。验证：876 passed（基线 874），覆盖率 57.65%；同会话 e2e+integration 246 passed。

### Git Commits

| Hash | Message |
|------|---------|
| `b60d3cd` | fix(test,cache): 收敛测试权限清单与 TTL 配置为单一真相 |
| `1d0d78c` | docs: 回写 TD-1/2/4/5 修复状态（提交 b60d3cd） |
| `0a5f5b0` | docs(spec): 沉淀 TTL 配置单一真相契约（_ttl_config + ttl_for） |
| `23a0a1d` | feat(sync): 新增执行明细与定时配置迁移（建表/operator_id可空/权限） |
| `7fcbce5` | feat(sync): 新增 SyncTaskLogDetail/SyncScheduleConfig 模型与 SyncDetail DTO |
| `ba889b8` | feat(sync): 订单同步与费用计算注入 detail_collector 埋点（警告/错误/成功聚合） |
| `f6df04f` | feat(sync): 任务服务支持明细收集落库/三态回退/计数聚合/operator可空 |
| `afdabbb` | feat(sync): 执行明细接口/定时配置接口(权限隔离)/遗留 consumption/sync 纳入任务链路 |
| `1fcedd1` | feat(sync): 定时任务合并为每日自动同步并支持动态配置注册（删除旧任务文件） |
| `dccd38e` | feat(sync): 同步日志页执行信息三态/明细Drawer/定时配置区（权限隔离） |
| `fc0c766` | test(sync): 新增明细落库/三态回退/接口权限测试并适配既有断言 |

### Status

[OK] **Completed**


## Session 19: 运营工作台页面功能修复（3 个显示问题）
<!-- trellis-session: v=2 fp=b5bb8d3dd491ab6c -->

**Date**: 2026-09-18
**Task**: 运营工作台页面功能修复（3 个显示问题）
**Branch**: `feature/dashboard-visual-fixes`

### Summary

修复运营工作台 3 个问题：1)「异常与待办」宽度——hero grid 子项 min-width:0 恢复 1.35fr/0.65fr（800/385px），根因 echarts canvas 固定宽撑破 fr 轨道；2)「经营趋势」图表空白——前端改按 tab 请求 /dashboard/trend（consumption 用 DailyConsumption 真实数据，payment 修 list.get 500，customer_count/health 补真实源），tab 切换数据源+空态文案；3)「今日优先跟进客户」表格空——后端 risk_customers 键不存在改为 get_risk_customers 真实查询（余额覆盖不足+流失风险）。AC1-AC8 全通过（浏览器实测+接口验证），全量测试 835 passed 与基线一致无新增回归。

### Git Commits

| Hash | Message |
|------|---------|
| `38d43e1` | feat(analytics): 新增消耗趋势/客户数趋势/风险客户服务方法（Dashboard 数据源） |
| `7c4b03b` | fix(analytics): 修复 dashboard/trend 各 metric 与 priority-customers 风险客户数据源 |
| `e82c325` | fix(dashboard): 经营趋势按 tab 切换数据源、hero 宽度修复、优先跟进表格空态 |

### Status

[OK] **Completed**


## Session 20: 修复PR #26 CI E2E失败：seed.py循环变量遮蔽导致admin权限不足
<!-- trellis-session: v=2 fp=a686c8f547e0dc29 -->

**Date**: 2026-09-19
**Task**: 修复PR #26 CI E2E失败：seed.py循环变量遮蔽导致admin权限不足
**Branch**: `feat/sync-task-log-page`

### Summary

PR #26（feat/sync-task-log-page）的 CI E2E Tests job 失败根因定位：backend/scripts/seed.py 中步骤2.6/2.7 的 for role in all_roles: 循环变量遮蔽了步骤2定义的「超级管理员」role 变量（Python 无块级作用域），循环结束后 role 指向 all_roles 最后一个角色（销售经理），步骤3 admin.roles.append(role) 将 admin 错误绑定到销售经理角色（8权限，缺 customers:create），导致 CI 全新库上 POST /api/v1/customers 403 权限不足。修复：超级管理员角色改用独立变量 super_admin_role，迁移/清理循环改用 iter_role。全新库 ci_repro 完整模拟 CI 流程验证：修复前 admin 仅销售经理（8权限），修复后正确绑定超级管理员（49权限）。单元测试 test_sync_task_details + test_test_data_consistency 通过。CI 重跑后 7/7 job 全绿（含 E2E Tests 与 PR Quality Gate）。经验沉淀至 .trellis/spec/backend/quality-guidelines.md（陷阱：脚本中循环变量遮蔽外层主对象变量）并 learn 记录。

### Git Commits

| Hash | Message |
|------|---------|
| `1d91e59` | fix(seed): 修复超级管理员角色被循环变量遮蔽导致admin权限不足 |
| `c1236c3` | docs(spec): 沉淀seed.py循环变量遮蔽导致admin权限不足的排查经验 |

### Status

[OK] **Completed**


## Session 21: 合并 PR #26：同步任务日志页面功能优化落地 main
<!-- trellis-session: v=2 fp=03a9f76fa34fbc7d -->

**Date**: 2026-09-19
**Task**: 合并 PR #26：同步任务日志页面功能优化落地 main
**Branch**: `main`

### Summary

PR #26（feat/sync-task-log-page → main，同步任务日志页面功能优化：筛选/搜索/字段展示/小计/布局）已合并，merge commit bb9ff15。合并前 CI 7/7 job 全绿（含 E2E Tests 与 PR Quality Gate）；合并方式为 merge commit，与仓库惯例一致。此前轮次已修复该 PR 的 CI E2E 失败（根因：backend/scripts/seed.py 步骤2.6/2.7 的 for role in all_roles: 循环变量遮蔽步骤2的超级管理员 role 变量，导致 admin 被错误绑定销售经理角色、缺 customers:create 权限，CI 全新库上 POST /api/v1/customers 403；修复为 super_admin_role/iter_role 独立变量，commit 1d91e59；经验沉淀 spec c1236c3 与 learn）。本地已切回 main 并同步远端。

### Git Commits

| Hash | Message |
|------|---------|
| `bb9ff15` | Merge pull request #26 from sacrtap/feat/sync-task-log-page |

### Status

[OK] **Completed**


## Session 22: 开放平台 VitePress 文档站搭建与 PR #27 合并
<!-- trellis-session: v=2 fp=b126cd4f203869ca -->

**Date**: 2026-09-20
**Task**: 开放平台 VitePress 文档站搭建与 PR #27 合并
**Branch**: `api-docs`

### Summary

基于 VitePress 搭建开放平台文档站（openapi-docs/），替换前端 SPA 手写 OpenApiGuide.vue；认证围绕 API-Key 管理；nginx 集成 /openapi/ 静态托管；修复 PR checks 集成测试超时（paths-filter + timeout 60）与 acceptance record 上传（if: always()）；沉淀 spec 经验指南

### Git Commits

| Hash | Message |
|------|---------|
| `0b22c51` | Merge pull request #27 from sacrtap/api-docs |

### Status

[OK] **Completed**
