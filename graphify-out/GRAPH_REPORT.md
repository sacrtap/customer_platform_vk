# Graph Report - .  (2026-04-08)

## Corpus Check
- Large corpus: 229 files · ~126,716 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 1478 nodes · 2553 edges · 63 communities detected
- Extraction: 56% EXTRACTED · 44% INFERRED · 0% AMBIGUOUS · INFERRED: 1119 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Customer` - 91 edges
2. `CustomerBalance` - 78 edges
3. `Invoice` - 76 edges
4. `InvoiceService` - 65 edges
5. `AnalyticsService` - 64 edges
6. `BalanceService` - 60 edges
7. `PricingService` - 58 edges
8. `RechargeRecord` - 54 edges
9. `PricingRule` - 54 edges
10. `make_mock_execute_result()` - 51 edges

## Surprising Connections (you probably didn't know these)
- `客户充值      Body:     {         "customer_id": 1,         "real_amount": 10000.00,` --rationale_for--> `recharge()`  [EXTRACTED]
  backend/app/routes/billing.py → frontend/src/api/billing.ts
- `创建权限      Body:     {         "code": "string (required)",         "name": "stri` --uses--> `Permission`  [INFERRED]
  backend/app/routes/permissions.py → backend/app/models/users.py
- `更新权限信息      Body:     {         "name": "string (optional)",         "descriptio` --uses--> `Permission`  [INFERRED]
  backend/app/routes/permissions.py → backend/app/models/users.py
- `Webhook 签名记录表 - 用于防止重放攻击` --uses--> `BaseModel`  [INFERRED]
  backend/app/models/webhooks.py → backend/app/models/base.py
- `测试配置 - 设置测试环境变量  注意：此文件在 pytest 启动时最先加载，必须确保环境变量在任何 app 代码导入前设置。` --uses--> `BaseModel`  [INFERRED]
  backend/tests/conftest.py → backend/app/models/base.py

## Communities

### Community 0 - "Analytics Service"
Cohesion: 0.02
Nodes (59): AnalyticsService, Customer, CustomerProfile, CustomerService, 客户服务类      支持同步和异步 Session, 批量创建客户（优化版：批量检查重复，减少 N+1 查询）          Args:             customers_data: 客户数据列表, 获取客户列表（支持筛选和分页）          Args:             page: 页码             page_size: 每页数量, analytics_service() (+51 more)

### Community 1 - "Permission System & Tests"
Cohesion: 0.03
Nodes (40): 获取用户所有权限代码      Args:         session: 数据库会话         user_id: 用户ID      Returns:, Auth API 集成测试  测试覆盖： 1. /api/v1/auth/login - 登录成功、密码错误、用户不存在 2. /api/v1/auth/ref, 测试刷新 Token API - 成功场景, 测试刷新 Token API - 无效 Token, 测试获取当前用户信息 API - 成功场景, test_get_me_success(), test_refresh_token_invalid(), test_refresh_token_success() (+32 more)

### Community 2 - "Analytics Rationale Docs"
Cohesion: 0.09
Nodes (74): 获取客户健康度统计（优化：6次查询 → 2次查询）, 获取长期未消耗客户列表（优化：使用子查询替代 Python 集合操作）, 获取仪表盘统计数据（优化：6次查询 → 2次查询）, BaseModel, BaseModel, BalanceService, ConsumptionRecord, CustomerBalance (+66 more)

### Community 3 - "Cache Service"
Cohesion: 0.03
Nodes (25): CacheService, 删除指定缓存          Args:             prefix: 缓存前缀             *parts: 键的组成部分, 批量删除匹配模式的缓存          Args:             pattern: 匹配模式，如 "cache:customer_list:*", 清除客户相关缓存          Args:             customer_id: 指定客户 ID 则只清除该客户缓存，None 则清除所有客户缓, 清除分析相关缓存          Args:             category: 指定类别，如 "dashboard", "health", "pro, 从缓存获取数据          Args:             prefix: 缓存前缀             *parts: 键的组成部分, 设置缓存数据          Args:             prefix: 缓存前缀             data: 要缓存的数据, cache_with_mock_redis() (+17 more)

### Community 4 - "Billing Enums & Types"
Cohesion: 0.04
Nodes (29): InvoiceStatus, Enum, str, Webhook Cleanup Tasks 单元测试 测试覆盖率目标：80%+, TestCleanupWebhookSignatures, Webhook 路由单元测试 测试覆盖率目标：85%+, 测试带 Z 后缀的时间戳 - 代码会移除 Z, TestCheckSignatureNotUsed (+21 more)

### Community 5 - "Auth Middleware"
Cohesion: 0.04
Nodes (27): AuthService, _check_permission(), forgot_password(), login(), 检查用户是否有指定权限（支持通配符匹配）      Args:         user_permissions: 用户权限集合         require, 使用 Refresh Token 刷新 Access Token, 忘记密码 - 发送密码重置链接      Body:     {         "username": "string (required)",, # TODO: 发送重置邮件到 user.email (+19 more)

### Community 6 - "Billing Service Tests"
Cohesion: 0.07
Nodes (51): make_mock_execute_result(), mock_db(), test_apply_discount_amount_too_large(), test_apply_discount_invoice_not_found(), test_apply_discount_success(), test_apply_discount_wrong_state(), test_complete_insufficient_balance(), test_complete_success() (+43 more)

### Community 7 - "Balance Check Tasks"
Cohesion: 0.05
Nodes (25): check_balance_warning(), _log_check_task(), P6-4: 余额预警检查任务 每小时检查客户余额，标记预警状态, 检查客户余额预警      执行时间：每小时     职责：检查所有客户余额，标记预警状态, SyncTaskLog, _log_email_task(), P6-7: 逾期提醒邮件任务 每日 9 点发送逾期账单提醒给商务, 发送逾期账单提醒邮件      执行时间：每日 09:00     职责：向商务发送逾期账单提醒 (+17 more)

### Community 8 - "Customer Service Batch Tests"
Cohesion: 0.06
Nodes (37): AsyncSession, customer_service(), make_mock_execute_result(), mock_db(), MockDBSession, 客户运营中台 - CustomerService 批量创建客户单元测试  测试目标：CustomerService.batch_create_customers, 验证 flush 在 add_all 之前调用, 创建 CustomerService 实例（不 patch 模型，使用真实模型类） (+29 more)

### Community 9 - "Tag Management"
Cohesion: 0.05
Nodes (11): batch_add_customer_tags(), batch_remove_customer_tags(), create_tag(), list_tags(), 创建标签      Body:     {         "name": "string (required)",         "type": "stri, 更新标签      Body:     {         "name": "string (optional)",         "category": ", 获取标签列表（支持筛选）      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20), 批量给客户添加标签      Body:     {         "customer_ids": [1, 2, 3],         "tag_ids": (+3 more)

### Community 10 - "Customer Groups"
Cohesion: 0.07
Nodes (17): CustomerGroup, CustomerGroupMember, CustomerGroupService, _is_async_session(), 删除群组（软删除）          Args:             group_id: 群组 ID          Returns:, 添加成员到静态群组          Args:             group_id: 群组 ID             customer_id: 客户, 移除群组成员          Args:             group_id: 群组 ID             customer_id: 客户 ID, 获取群组成员列表          Args:             group_id: 群组 ID             page: 页码 (+9 more)

### Community 11 - "Analytics API"
Cohesion: 0.04
Nodes (0): 

### Community 12 - "Email Service"
Cohesion: 0.05
Nodes (16): DeclarativeBase, EmailService, 渲染邮件模板          Args:             template_name: 模板文件名             **context: 模板, 发送邮件          Args:             to_emails: 收件人邮箱列表             subject: 邮件主题, Base, create_permission(), get_user_permissions(), PermissionCache (+8 more)

### Community 13 - "Performance Tests"
Cohesion: 0.05
Nodes (12): HttpUser, CustomerPlatformUser, 性能测试脚本 - Locust 测试 API 响应时间和并发能力, CustomerPlatformUser, on_quitting(), on_request(), 客户平台 API 负载测试脚本 - Locust  测试关键 API 端点的响应时间和并发能力  使用方法:     cd backend     locust, 每个请求完成时执行     可用于记录详细日志或自定义指标 (+4 more)

### Community 14 - "Audit Logs"
Cohesion: 0.08
Nodes (31): list_audit_logs(), 获取审计日志列表（支持筛选和分页）      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20, 通用 Redis 缓存服务  提供热点数据缓存功能，支持： - 客户列表缓存 - 标签列表缓存 - 客户详情缓存 - 缓存失效管理, SoftDeleteMixin, TimestampMixin, BaseSettings, AuditLog, Config (+23 more)

### Community 15 - "User Service Tests"
Cohesion: 0.05
Nodes (7): apply_discount(), create_pricing_rule(), export_invoices(), generate_invoice(), getInvoices(), getRecentInvoices(), recharge()

### Community 16 - "Group Service Tests"
Cohesion: 0.07
Nodes (7): ExternalAPIClient, 外部 API 客户端 - 用于同步业务系统数据, 获取用量统计数据          Args:             start_date: 开始日期             end_date: 结束日期, 获取客户每日用量数据          Args:             customer_id: 客户 ID             start_date:, 获取客户详细信息          Args:             customer_id: 客户 ID          Returns:, 同步客户数据到业务系统          Args:             customer_id: 客户 ID          Returns:, TestExternalAPIClient

### Community 17 - "Role Service Tests"
Cohesion: 0.06
Nodes (7): Customers API 集成测试  测试覆盖： 1. GET /api/v1/customers - 客户列表（带筛选） 2. GET /api/v1/cu, 测试 Excel 导入客户 - 文件格式错误, 测试 Excel 导入客户 - 缺少必填列, 测试 Excel 导出客户 - 带筛选条件, test_export_customers_with_filters(), test_import_customers_missing_columns(), test_import_customers_wrong_format()

### Community 18 - "Customer Service Tests"
Cohesion: 0.1
Nodes (22): group_service(), make_mock_execute_result(), mock_db(), MockDBSession, 客户群组服务单元测试  测试 CustomerGroupService 的 CRUD 操作, 创建 CustomerGroupService 实例, test_add_member(), test_add_member_already_exists() (+14 more)

### Community 19 - "Webhook Tests"
Cohesion: 0.06
Nodes (5): Billing API 集成测试  测试覆盖： 1. GET /api/v1/billing/balances - 获取余额列表 2. GET /api/v1/, 测试获取客户余额 - 余额不存在（返回 0）, 测试结算单完整工作流：生成 -> 提交 -> 确认 -> 付款 -> 完成, test_get_customer_balance_not_exists(), test_invoice_workflow_full()

### Community 20 - "Task Tests"
Cohesion: 0.09
Nodes (9): assign_permissions(), create_role(), list_roles(), 更新角色信息      Body:     {         "name": "string (optional)",         "descriptio, 获取角色列表      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20), 为角色分配权限      Body:     {         "permission_ids": [1, 2, 3]     }, 创建角色      Body:     {         "name": "string (required)",         "description", RoleService (+1 more)

### Community 21 - "Model Tests"
Cohesion: 0.07
Nodes (12): create_customer(), export_customers(), import_customers(), list_customers(), 创建客户      Body:     {         "company_id": "string (required)",         "name":, 获取客户列表（支持筛选）      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20), 更新客户信息      Body:     {         "name": "string (optional)",         "account_ty, 创建或更新客户画像      Body:     {         "scale_level": "string (optional)",         " (+4 more)

### Community 22 - "Permission Service Tests"
Cohesion: 0.07
Nodes (9): auth_token(), Analytics API 集成测试  测试覆盖： 1. GET /api/v1/analytics/dashboard/stats - 获取仪表盘统计 2., 测试获取消耗趋势 - 使用默认日期（最近 6 个月）, 获取认证 Token - 直接创建用户并生成 JWT, 测试获取余额预警客户列表 - 使用默认阈值, 测试 Analytics API - 未授权访问, test_analytics_unauthorized(), test_consumption_trend_default_dates() (+1 more)

### Community 23 - "Email Task Tests"
Cohesion: 0.09
Nodes (6): 定时任务单元测试 测试覆盖率目标：85%+, TestBalanceCheckTask, TestFileCleanupTask, TestInvoiceGeneratorTask, TestUsageSyncTask, TestWebhookCleanupTask

### Community 24 - "Auth Service Tests"
Cohesion: 0.12
Nodes (9): auth_token(), Files API 集成测试  测试覆盖： 1. POST /api/v1/files/upload - 上传文件（成功、文件类型验证、大小限制） 2. GET, 测试获取文件详情 - 文件不存在（需要 files:read 权限）, 测试删除文件 - 文件不存在（需要 files:delete 权限）, 使用 test_user fixture 获取认证 Token, 测试上传文件 - 成功场景（.xlsx 文件）, test_delete_file_not_found(), test_get_file_not_found() (+1 more)

### Community 25 - "User Import Tests"
Cohesion: 0.14
Nodes (9): app(), mock_scheduler(), pytest_configure(), 测试配置 - 设置测试环境变量  注意：此文件在 pytest 启动时最先加载，必须确保环境变量在任何 app 代码导入前设置。, 创建 Sanic 应用实例（使用异步数据库引擎）, pytest 配置 hook - 确保环境变量在任何测试前设置, Mock APScheduler 避免初始化问题, 创建同步测试数据库引擎（用于 Analytics Service 等） (+1 more)

### Community 26 - "Frontend API - Customers"
Cohesion: 0.15
Nodes (2): TestUserImportEdgeCases, TestUserImportValidation

### Community 27 - "Frontend API - Analytics"
Cohesion: 0.17
Nodes (0): 

### Community 28 - "Frontend API - Billing"
Cohesion: 0.18
Nodes (0): 

### Community 29 - "Frontend API - Users"
Cohesion: 0.22
Nodes (1): Users API 集成测试  测试覆盖： 1. GET /api/v1/users - 获取用户列表、筛选用户 2. POST /api/v1/users -

### Community 30 - "Frontend API - Roles"
Cohesion: 0.29
Nodes (2): getCellValue(), rowComparator()

### Community 31 - "Frontend API - Tags"
Cohesion: 0.29
Nodes (0): 

### Community 32 - "Frontend Store"
Cohesion: 0.29
Nodes (1): 集成测试 - API 端点测试  使用异步数据库操作，与生产环境一致 所有测试函数使用异步方式

### Community 33 - "Frontend Router"
Cohesion: 0.33
Nodes (5): downgrade(), add missing indexes for query optimization  Revision ID: 003 Revises: 002 Create, 添加缺失的索引以优化查询性能      索引添加说明:     1. recharge_records.created_at - 用于 ORDER BY 排序, 回滚索引删除      注意：生产环境删除索引前请评估对查询性能的影响, upgrade()

### Community 34 - "E2E Test Fixtures"
Cohesion: 0.33
Nodes (1): Audit Logs API 集成测试  测试覆盖： 1. GET /api/v1/audit-logs - 获取审计日志列表、筛选审计日志 2. GET /a

### Community 35 - "Login Flow Tests"
Cohesion: 0.5
Nodes (0): 

### Community 36 - "Customer CRUD Tests"
Cohesion: 0.5
Nodes (1): add_webhook_signatures  Revision ID: 002 Revises: 001 Create Date: 2026-04-03

### Community 37 - "Invoice Workflow Tests"
Cohesion: 0.5
Nodes (1): initial - create all tables  Revision ID: 001_initial Revises: Create Date: 2026

### Community 38 - "Balance Recharge Tests"
Cohesion: 0.5
Nodes (1): add customer groups models  Revision ID: 002 Revises: 001 Create Date: 2026-04-0

### Community 39 - "Core Pages Rendering Tests"
Cohesion: 0.5
Nodes (1): add_all_missing_tables  Revision ID: a5d21c5761aa Revises: 002 Create Date: 2026

### Community 40 - "User Management Tests"
Cohesion: 0.5
Nodes (1): add files table  Revision ID: 003 Revises: a5d21c5761aa Create Date: 2026-04-06

### Community 41 - "Role Management Tests"
Cohesion: 0.67
Nodes (0): 

### Community 42 - "Tag Management Tests"
Cohesion: 1.0
Nodes (2): get_or_create_permission(), seed()

### Community 43 - "Analytics E2E Tests"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Billing Workflow E2E Tests"
Cohesion: 1.0
Nodes (1): E2E 测试指南

### Community 45 - "Customer Management Tests"
Cohesion: 1.0
Nodes (1): E2E 测试报告

### Community 46 - "Playwright Reports"
Cohesion: 1.0
Nodes (1): 账号登录模块

### Community 47 - "Deployment Docs"
Cohesion: 1.0
Nodes (1): 客户信息管理模块

### Community 48 - "Design System"
Cohesion: 1.0
Nodes (1): 结算管理模块

### Community 49 - "Design Specs"
Cohesion: 1.0
Nodes (1): 数据分析模块

### Community 50 - "Optimization Docs"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Testing Docs"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Implementation Plans"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Backend Routes"
Cohesion: 1.0
Nodes (1): 获取客户列表 - 高频操作         权重：5（最高频率）

### Community 54 - "Backend Services"
Cohesion: 1.0
Nodes (1): 获取余额信息 - 中频操作         权重：3

### Community 55 - "Backend Models"
Cohesion: 1.0
Nodes (1): 获取仪表盘统计数据 - 低频操作         权重：2

### Community 56 - "Backend Tasks"
Cohesion: 1.0
Nodes (1): 获取余额列表 - 中频操作         权重：2

### Community 57 - "Alembic Migrations"
Cohesion: 1.0
Nodes (1): 获取客户详情 - 低频操作         权重：1

### Community 58 - "Config & Main"
Cohesion: 1.0
Nodes (1): 获取消费记录 - 低频操作         权重：1

### Community 59 - "Middleware"
Cohesion: 1.0
Nodes (1): 获取定价规则 - 低频操作         权重：1

### Community 60 - "External API Service"
Cohesion: 1.0
Nodes (1): 获取结算单列表 - 低频操作         权重：1

### Community 61 - "AGENTS.md & README"
Cohesion: 1.0
Nodes (1): 获取仪表盘图表数据 - 低频操作         权重：1

### Community 62 - "Requirements"
Cohesion: 1.0
Nodes (1): 获取当前用户信息 - 低频操作         权重：1

## Knowledge Gaps
- **84 isolated node(s):** `E2E 测试指南`, `E2E 测试报告`, `账号登录模块`, `客户信息管理模块`, `结算管理模块` (+79 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Analytics E2E Tests`** (2 nodes): `create_test_data.py`, `create_test_data()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Billing Workflow E2E Tests`** (1 nodes): `E2E 测试指南`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Customer Management Tests`** (1 nodes): `E2E 测试报告`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Playwright Reports`** (1 nodes): `账号登录模块`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Deployment Docs`** (1 nodes): `客户信息管理模块`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Design System`** (1 nodes): `结算管理模块`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Design Specs`** (1 nodes): `数据分析模块`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Optimization Docs`** (1 nodes): `playwright.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Testing Docs`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Implementation Plans`** (1 nodes): `debug_middleware.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backend Routes`** (1 nodes): `获取客户列表 - 高频操作         权重：5（最高频率）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backend Services`** (1 nodes): `获取余额信息 - 中频操作         权重：3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backend Models`** (1 nodes): `获取仪表盘统计数据 - 低频操作         权重：2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backend Tasks`** (1 nodes): `获取余额列表 - 中频操作         权重：2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Alembic Migrations`** (1 nodes): `获取客户详情 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Config & Main`** (1 nodes): `获取消费记录 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Middleware`** (1 nodes): `获取定价规则 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `External API Service`** (1 nodes): `获取结算单列表 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `AGENTS.md & README`** (1 nodes): `获取仪表盘图表数据 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Requirements`** (1 nodes): `获取当前用户信息 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Customer` connect `Analytics Service` to `Analytics Rationale Docs`, `Balance Check Tasks`, `Tag Management`, `Customer Groups`, `Model Tests`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._
- **Why does `BaseModel` connect `Analytics Rationale Docs` to `Analytics Service`, `Permission System & Tests`, `Billing Enums & Types`, `Balance Check Tasks`, `Customer Groups`, `Audit Logs`, `User Import Tests`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `CacheService` connect `Cache Service` to `Audit Logs`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 88 inferred relationships involving `Customer` (e.g. with `P6-3: 月度结算单自动生成任务 为非重点客户自动生成上月结算单` and `自动生成月度结算单      执行时间：每月 1 日 02:00     职责：为非重点客户自动生成上月结算单`) actually correct?**
  _`Customer` has 88 INFERRED edges - model-reasoned connections that need verification._
- **Are the 75 inferred relationships involving `CustomerBalance` (e.g. with `P6-4: 余额预警检查任务 每小时检查客户余额，标记预警状态` and `检查客户余额预警      执行时间：每小时     职责：检查所有客户余额，标记预警状态`) actually correct?**
  _`CustomerBalance` has 75 INFERRED edges - model-reasoned connections that need verification._
- **Are the 74 inferred relationships involving `Invoice` (e.g. with `P6-3: 月度结算单自动生成任务 为非重点客户自动生成上月结算单` and `自动生成月度结算单      执行时间：每月 1 日 02:00     职责：为非重点客户自动生成上月结算单`) actually correct?**
  _`Invoice` has 74 INFERRED edges - model-reasoned connections that need verification._
- **Are the 54 inferred relationships involving `InvoiceService` (e.g. with `P6-3: 月度结算单自动生成任务 为非重点客户自动生成上月结算单` and `自动生成月度结算单      执行时间：每月 1 日 02:00     职责：为非重点客户自动生成上月结算单`) actually correct?**
  _`InvoiceService` has 54 INFERRED edges - model-reasoned connections that need verification._