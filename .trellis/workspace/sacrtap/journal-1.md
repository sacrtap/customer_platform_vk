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
