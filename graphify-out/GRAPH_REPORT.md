# Graph Report - .  (2026-04-13)

## Corpus Check
- 175 files · ~131,036 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1715 nodes · 2882 edges · 84 communities detected
- Extraction: 69% EXTRACTED · 31% INFERRED · 0% AMBIGUOUS · INFERRED: 880 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Customer` - 98 edges
2. `CustomerBalance` - 85 edges
3. `Invoice` - 74 edges
4. `AnalyticsService` - 74 edges
5. `InvoiceService` - 65 edges
6. `BalanceService` - 60 edges
7. `RechargeRecord` - 58 edges
8. `PricingRule` - 58 edges
9. `PricingService` - 58 edges
10. `make_mock_execute_result()` - 51 edges

## Surprising Connections (you probably didn't know these)
- `Documentation Navigation Index` --conceptually_related_to--> `Documentation Directory Convention`  [INFERRED]
  docs/README.md → AGENTS.md
- `Security Constraints: Transactions/Row Locks/Auth/Audit` --conceptually_related_to--> `RBAC Permission Model`  [INFERRED]
  AGENTS.md → README.md
- `创建权限      Body:     {         "code": "string (required)",         "name": "stri` --uses--> `Permission`  [INFERRED]
  backend/app/routes/permissions.py → backend/app/models/users.py
- `更新权限信息      Body:     {         "name": "string (optional)",         "descriptio` --uses--> `Permission`  [INFERRED]
  backend/app/routes/permissions.py → backend/app/models/users.py
- `Webhook 签名记录表 - 用于防止重放攻击` --uses--> `BaseModel`  [INFERRED]
  backend/app/models/webhooks.py → backend/app/models/base.py

## Hyperedges (group relationships)
- **Graphify Query Methods** — graphify_md_command_query, graphify_md_command_path, graphify_md_command_explain, graphify_md_structural_query, graphify_md_path_analysis [INFERRED 0.85]
- **Customer Detail Visualization System** — plan_health_gauge_component, plan_balance_trend_chart, plan_usage_distribution_chart, plan_vue_echarts_install [INFERRED 0.85]
- **Health Score Weighted Components** — spec_usage_rate_calc, spec_balance_rate_calc, spec_payment_rate_calc, spec_health_calculation_formula [INFERRED 0.90]
- **Basic Info Tab Component Set** — spec_customer_name_card, spec_info_grid, spec_tag_cloud [INFERRED 0.80]

## Communities

### Community 0 - "Analytics Business Logic"
Cohesion: 0.02
Nodes (66): AnalyticsService, Customer, CustomerProfile, CustomerService, 客户服务类      支持同步和异步 Session, 批量创建客户（优化版：批量检查重复，减少 N+1 查询）          Args:             customers_data: 客户数据列表, 获取客户列表（支持筛选和分页）          Args:             page: 页码             page_size: 每页数量, analytics_service() (+58 more)

### Community 1 - "Health Score Queries"
Cohesion: 0.09
Nodes (76): 获取客户健康度统计（优化：6次查询 → 2次查询）, 获取长期未消耗客户列表（优化：使用子查询替代 Python 集合操作）, 获取单个客户的健康度评分          健康度 = 用量达标率 × 50% + 余额充足率 × 30% + 回款及时率 × 20%          Ret, 计算用量达标率          用量达标率 = min(实际用量 / 预期用量，1.0) × 100, 计算余额充足率          余额充足率 = min(当前余额 / 月均消耗，1.0) × 100, 计算回款及时率          回款及时率 = 按时付款结算单数 / 总结算单数 × 100         按时付款定义为：结算单状态为 paid 或 co, 获取仪表盘统计数据（优化：6次查询 → 2次查询）, BaseModel (+68 more)

### Community 2 - "Analytics API Routes"
Cohesion: 0.02
Nodes (7): apply_discount(), create_pricing_rule(), export_invoices(), generate_invoice(), getInvoices(), getRecentInvoices(), recharge()

### Community 3 - "Core Business Concepts"
Cohesion: 0.05
Nodes (87): 客户分析, 审计日志, 余额管理, 结算管理, 游标分页, 客户分群, 客户画像, 动态群组 (+79 more)

### Community 4 - "Redis Cache Service"
Cohesion: 0.03
Nodes (24): CacheService, 删除指定缓存          Args:             prefix: 缓存前缀             *parts: 键的组成部分, 批量删除匹配模式的缓存          Args:             pattern: 匹配模式，如 "cache:customer_list:*", 清除客户相关缓存          Args:             customer_id: 指定客户 ID 则只清除该客户缓存，None 则清除所有客户缓, 清除分析相关缓存          Args:             category: 指定类别，如 "dashboard", "health", "pro, 从缓存获取数据          Args:             prefix: 缓存前缀             *parts: 键的组成部分, 设置缓存数据          Args:             prefix: 缓存前缀             data: 要缓存的数据, cache_with_mock_redis() (+16 more)

### Community 5 - "Audit Log System"
Cohesion: 0.04
Nodes (40): list_audit_logs(), 获取审计日志列表（支持筛选和分页）      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20, AuditLog, allowed_extension(), delete_file(), File, generate_secure_filename(), get_file() (+32 more)

### Community 6 - "Tag Management"
Cohesion: 0.04
Nodes (21): batch_add_customer_tags(), batch_remove_customer_tags(), create_tag(), CustomerTag, list_tags(), ProfileTag, 创建标签      Body:     {         "name": "string (required)",         "type": "stri, 更新标签      Body:     {         "name": "string (optional)",         "category": " (+13 more)

### Community 7 - "Authentication Middleware"
Cohesion: 0.04
Nodes (27): AuthService, _check_permission(), forgot_password(), login(), 检查用户是否有指定权限（支持通配符匹配）      Args:         user_permissions: 用户权限集合         require, 使用 Refresh Token 刷新 Access Token, 忘记密码 - 发送密码重置链接      Body:     {         "username": "string (required)",, # TODO: 发送重置邮件到 user.email (+19 more)

### Community 8 - "Design Standards & Guidelines"
Cohesion: 0.06
Nodes (60): WCAG 2.1 AA Accessibility Standards, AGENTS.md - Development Guide, Alembic Database Migration, Customer Analytics: Consumption/Collection/Health/Profile, Design Anti-Patterns: No emojis, no purple gradients, no layout shift, Backend Python Dependencies, Balance Management: Real + Bonus Amounts, Three Billing Modes: Fixed/Tiered/Annual (+52 more)

### Community 9 - "Billing Service Tests"
Cohesion: 0.07
Nodes (50): make_mock_execute_result(), test_apply_discount_amount_too_large(), test_apply_discount_invoice_not_found(), test_apply_discount_success(), test_apply_discount_wrong_state(), test_complete_insufficient_balance(), test_complete_success(), test_complete_wrong_state() (+42 more)

### Community 10 - "Customer Service Tests"
Cohesion: 0.06
Nodes (37): AsyncSession, customer_service(), make_mock_execute_result(), mock_db(), MockDBSession, 客户运营中台 - CustomerService 批量创建客户单元测试  测试目标：CustomerService.batch_create_customers, 验证 flush 在 add_all 之前调用, 创建 CustomerService 实例（不 patch 模型，使用真实模型类） (+29 more)

### Community 11 - "Customer Group Management"
Cohesion: 0.07
Nodes (17): CustomerGroup, CustomerGroupMember, CustomerGroupService, _is_async_session(), 删除群组（软删除）          Args:             group_id: 群组 ID          Returns:, 添加成员到静态群组          Args:             group_id: 群组 ID             customer_id: 客户, 移除群组成员          Args:             group_id: 群组 ID             customer_id: 客户 ID, 获取群组成员列表          Args:             group_id: 群组 ID             page: 页码 (+9 more)

### Community 12 - "Database Models & Base Classes"
Cohesion: 0.04
Nodes (25): 通用 Redis 缓存服务  提供热点数据缓存功能，支持： - 客户列表缓存 - 标签列表缓存 - 客户详情缓存 - 缓存失效管理, SoftDeleteMixin, TimestampMixin, create_customer(), export_customers(), import_customers(), list_customers(), 创建客户      Body:     {         "company_id": "string (required)",         "name": (+17 more)

### Community 13 - "Application Configuration"
Cohesion: 0.05
Nodes (16): BaseSettings, Config, get_settings(), Settings, ExternalAPIClient, 外部 API 客户端 - 用于同步业务系统数据, 获取用量统计数据          Args:             start_date: 开始日期             end_date: 结束日期, 获取客户每日用量数据          Args:             customer_id: 客户 ID             start_date: (+8 more)

### Community 14 - "Invoice & Webhook Tasks"
Cohesion: 0.07
Nodes (23): InvoiceStatus, Enum, str, Webhook Cleanup Tasks 单元测试 测试覆盖率目标：80%+, TestCleanupWebhookSignatures, cleanup_webhook_signatures(), P6-8: Webhook 签名清理任务 每日清理已过期的 Webhook 签名记录，防止数据库膨胀, 清理过期的 Webhook 签名记录      保留最近 5 天的签名记录，删除更早的记录 (+15 more)

### Community 15 - "Role & Permission Management"
Cohesion: 0.06
Nodes (14): assign_permissions(), create_role(), list_roles(), 更新角色信息      Body:     {         "name": "string (optional)",         "descriptio, 获取角色列表      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20), 为角色分配权限      Body:     {         "permission_ids": [1, 2, 3]     }, 创建角色      Body:     {         "name": "string (required)",         "description", RoleService (+6 more)

### Community 16 - "Load Testing (Locust)"
Cohesion: 0.05
Nodes (12): HttpUser, CustomerPlatformUser, 性能测试脚本 - Locust 测试 API 响应时间和并发能力, CustomerPlatformUser, on_quitting(), on_request(), 客户平台 API 负载测试脚本 - Locust  测试关键 API 端点的响应时间和并发能力  使用方法:     cd backend     locust, 用户启动时执行 - 完成登录认证         所有后续请求将使用获取到的 token (+4 more)

### Community 17 - "Analytics API Integration Tests"
Cohesion: 0.06
Nodes (11): auth_token(), Analytics API 集成测试  测试覆盖： 1. GET /api/v1/analytics/dashboard/stats - 获取仪表盘统计 2., 测试获取消耗趋势 - 使用默认日期（最近 6 个月）, 获取认证 Token - 直接创建用户并生成 JWT, 测试获取余额预警客户列表 - 使用默认阈值, 测试 Analytics API - 未授权访问, test_analytics_unauthorized(), test_consumption_trend_default_dates() (+3 more)

### Community 18 - "Customer API Integration Tests"
Cohesion: 0.06
Nodes (7): Customers API 集成测试  测试覆盖： 1. GET /api/v1/customers - 客户列表（带筛选） 2. GET /api/v1/cu, 测试 Excel 导入客户 - 文件格式错误, 测试 Excel 导入客户 - 缺少必填列, 测试 Excel 导出客户 - 带筛选条件, test_export_customers_with_filters(), test_import_customers_missing_columns(), test_import_customers_wrong_format()

### Community 19 - "Group Service Tests"
Cohesion: 0.1
Nodes (22): group_service(), make_mock_execute_result(), mock_db(), MockDBSession, 客户群组服务单元测试  测试 CustomerGroupService 的 CRUD 操作, 创建 CustomerGroupService 实例, test_add_member(), test_add_member_already_exists() (+14 more)

### Community 20 - "E2E Test Workflows"
Cohesion: 0.06
Nodes (5): Billing API 集成测试  测试覆盖： 1. GET /api/v1/billing/balances - 获取余额列表 2. GET /api/v1/, 测试获取客户余额 - 余额不存在（返回 0）, 测试结算单完整工作流：生成 -> 提交 -> 确认 -> 付款 -> 完成, test_get_customer_balance_not_exists(), test_invoice_workflow_full()

### Community 21 - "Frontend Vue Components"
Cohesion: 0.07
Nodes (8): 角色管理 API 集成测试  覆盖测试计划中的 API 测试用例: - TC-API-ROLE-001: 创建角色 API - TC-API-ROLE-002:, TestApiErrorHandling, TestAssignPermissions, TestCreateRole, TestDeleteRole, TestGetPermissions, TestGetRoles, TestUpdateRole

### Community 22 - "Customer Service Layer"
Cohesion: 0.07
Nodes (6): Webhook 路由单元测试 测试覆盖率目标：85%+, 测试带 Z 后缀的时间戳 - 代码会移除 Z, TestCheckSignatureNotUsed, TestRecordWebhookSignature, TestVerifyTimestampWindow, TestVerifyWebhookSignature

### Community 23 - "Billing Service Layer"
Cohesion: 0.08
Nodes (6): DeclarativeBase, EmailService, 渲染邮件模板          Args:             template_name: 模板文件名             **context: 模板, 发送邮件          Args:             to_emails: 收件人邮箱列表             subject: 邮件主题, Base, TestEmailService

### Community 24 - "Frontend API Client"
Cohesion: 0.08
Nodes (4): Email Tasks 单元测试 - 逾期提醒邮件任务, TestEmailTasksIntegration, TestLogEmailTask, TestSendOverdueEmails

### Community 25 - "Frontend State Management"
Cohesion: 0.09
Nodes (6): 定时任务单元测试 测试覆盖率目标：85%+, TestBalanceCheckTask, TestFileCleanupTask, TestInvoiceGeneratorTask, TestUsageSyncTask, TestWebhookCleanupTask

### Community 26 - "Frontend Router Config"
Cohesion: 0.13
Nodes (17): check_balance_warning(), _log_check_task(), P6-4: 余额预警检查任务 每小时检查客户余额，标记预警状态, 检查客户余额预警      执行时间：每小时     职责：检查所有客户余额，标记预警状态, SyncTaskLog, _log_email_task(), P6-7: 逾期提醒邮件任务 每日 9 点发送逾期账单提醒给商务, 发送逾期账单提醒邮件      执行时间：每日 09:00     职责：向商务发送逾期账单提醒 (+9 more)

### Community 27 - "Database Migration Scripts"
Cohesion: 0.14
Nodes (17): Analytics Routes (backend/app/routes/analytics.py), AnalyticsService (backend/app/services/analytics.py), Balance Trend API Route, BalanceTrendChart Vue Component, Balance Trend Service Method, ConsumeLevelProgress Vue Component, Customer Detail Page Refactor, HealthGauge Vue Component (+9 more)

### Community 28 - "Test Fixtures & Helpers"
Cohesion: 0.12
Nodes (9): auth_token(), Files API 集成测试  测试覆盖： 1. POST /api/v1/files/upload - 上传文件（成功、文件类型验证、大小限制） 2. GET, 测试获取文件详情 - 文件不存在（需要 files:read 权限）, 测试删除文件 - 文件不存在（需要 files:delete 权限）, 使用 test_user fixture 获取认证 Token, 测试上传文件 - 成功场景（.xlsx 文件）, test_delete_file_not_found(), test_get_file_not_found() (+1 more)

### Community 29 - "User Management"
Cohesion: 0.14
Nodes (9): app(), mock_scheduler(), pytest_configure(), 集成测试配置 - 使用 Sanic ASGI Client + pytest-asyncio  架构说明： - 使用 Sanic 内置的 ASGI 测试客户端, 创建 Sanic 应用实例（使用异步数据库引擎）, pytest 配置 hook - 确保环境变量在任何测试前设置, Mock APScheduler 避免初始化问题, 创建同步测试数据库引擎（用于 Analytics Service 等） (+1 more)

### Community 30 - "Balance Management"
Cohesion: 0.15
Nodes (0): 

### Community 31 - "Pricing Configuration"
Cohesion: 0.15
Nodes (2): TestUserImportEdgeCases, TestUserImportValidation

### Community 32 - "Frontend Type Definitions"
Cohesion: 0.17
Nodes (3): Permission Service 单元测试, TestPermissionService_GetUserPermissions, TestPermissionService_Integration

### Community 33 - "Deployment Configuration"
Cohesion: 0.17
Nodes (7): Auth API 集成测试  测试覆盖： 1. /api/v1/auth/login - 登录成功、密码错误、用户不存在 2. /api/v1/auth/ref, 测试刷新 Token API - 成功场景, 测试刷新 Token API - 无效 Token, 测试获取当前用户信息 API - 成功场景, test_get_me_success(), test_refresh_token_invalid(), test_refresh_token_success()

### Community 34 - "Performance Test Reports"
Cohesion: 0.22
Nodes (1): Users API 集成测试  测试覆盖： 1. GET /api/v1/users - 获取用户列表、筛选用户 2. POST /api/v1/users -

### Community 35 - "Usage Tracking"
Cohesion: 0.29
Nodes (0): 

### Community 36 - "Email Notification System"
Cohesion: 0.29
Nodes (1): 集成测试 - API 端点测试  使用异步数据库操作，与生产环境一致 所有测试函数使用异步方式

### Community 37 - "File Import/Export"
Cohesion: 0.33
Nodes (5): downgrade(), add missing indexes for query optimization  Revision ID: 003 Revises: 002 Create, 添加缺失的索引以优化查询性能      索引添加说明:     1. recharge_records.created_at - 用于 ORDER BY 排序, 回滚索引删除      注意：生产环境删除索引前请评估对查询性能的影响, upgrade()

### Community 38 - "Search & Filter Logic"
Cohesion: 0.33
Nodes (1): Audit Logs API 集成测试  测试覆盖： 1. GET /api/v1/audit-logs - 获取审计日志列表、筛选审计日志 2. GET /a

### Community 39 - "Data Validation & Schemas"
Cohesion: 0.4
Nodes (5): Command: /graphify path, Command: /graphify query, Graph-First Reasoning Principle, Path Analysis Strategy, Structural Query Strategy

### Community 40 - "Error Handling"
Cohesion: 0.5
Nodes (5): Component Hierarchy (Detail.vue Structure), CustomerNameCard Component, InfoGrid Component, ScaleLevelBadge Component, TagCloud Component

### Community 41 - "Scheduler & Cron Tasks"
Cohesion: 0.5
Nodes (0): 

### Community 42 - "Dashboard Statistics"
Cohesion: 0.5
Nodes (1): add_webhook_signatures  Revision ID: 002 Revises: 001 Create Date: 2026-04-03

### Community 43 - "Payment Collection"
Cohesion: 0.5
Nodes (1): create users roles permissions tables  Revision ID: 001_initial Revises: Create

### Community 44 - "Customer Profile Data"
Cohesion: 0.5
Nodes (1): add customer groups models  Revision ID: 002 Revises: 001 Create Date: 2026-04-0

### Community 45 - "Test Database Setup"
Cohesion: 0.5
Nodes (1): add_all_missing_tables  Revision ID: a5d21c5761aa Revises: 002 Create Date: 2026

### Community 46 - "UI Design System"
Cohesion: 0.5
Nodes (1): add files table  Revision ID: 003 Revises: a5d21c5761aa Create Date: 2026-04-06

### Community 47 - "API Response Formatting"
Cohesion: 0.67
Nodes (0): 

### Community 48 - "Frontend Utility Functions"
Cohesion: 1.0
Nodes (2): get_or_create_permission(), seed()

### Community 49 - "Security & JWT"
Cohesion: 0.67
Nodes (3): Animation Specs (150-400ms), Card Style (Light Shadow + White Background), Color System (Primary + Neutral + Functional)

### Community 50 - "Logging Configuration"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Docker Compose Config"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Documentation Index"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Phase Implementation Plans"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Customer Groups Design"
Cohesion: 1.0
Nodes (1): 测试权限去重（用户有多个角色包含相同权限）

### Community 55 - "Frontend Redesign Specs"
Cohesion: 1.0
Nodes (1): 测试 months 参数（默认 6，最大 12）

### Community 56 - "Platform Design Spec"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试获取角色列表成功

### Community 57 - "Test Plans"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试分页参数

### Community 58 - "Test Reports"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试搜索功能

### Community 59 - "Performance Optimization"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-001: 测试创建角色成功

### Community 60 - "Permission Checker"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试创建重复角色

### Community 61 - "Customer Management Optimization"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-016: 测试创建角色 - 空名称验证

### Community 62 - "Backend Initialization"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-001: 测试创建角色时分配权限

### Community 63 - "UX/UI Improvements"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-002: 测试更新角色成功

### Community 64 - "User Manual"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-007: 测试编辑系统角色 - 名称保护

### Community 65 - "Development Guide (AGENTS)"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-003: 测试分配权限成功

### Community 66 - "Project README"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-015: 测试分配权限 - 空权限验证

### Community 67 - "Database Migration Guide"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-008: 测试删除自定义角色

### Community 68 - "Redis Cache Analysis"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-009: 测试删除系统角色 - 保护机制

### Community 69 - "Query Optimization"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-006: 测试获取权限列表

### Community 70 - "Sentry Integration Plan"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-006: 测试权限数据结构

### Community 71 - "Structured Logging Config"
Cohesion: 1.0
Nodes (1): 获取客户列表 - 高频操作         权重：5（最高频率）

### Community 72 - "Sanic Integration"
Cohesion: 1.0
Nodes (1): 获取余额信息 - 中频操作         权重：3

### Community 73 - "Role Permission Tests"
Cohesion: 1.0
Nodes (1): 获取仪表盘统计数据 - 低频操作         权重：2

### Community 74 - "Customer Page Tests"
Cohesion: 1.0
Nodes (1): 获取余额列表 - 中频操作         权重：2

### Community 75 - "Phase 0-7 Tests"
Cohesion: 1.0
Nodes (1): 获取客户详情 - 低频操作         权重：1

### Community 76 - "E2E Test Reports"
Cohesion: 1.0
Nodes (1): 获取消费记录 - 低频操作         权重：1

### Community 77 - "Final Fix Reports"
Cohesion: 1.0
Nodes (1): 获取定价规则 - 低频操作         权重：1

### Community 78 - "Podman macOS Deploy"
Cohesion: 1.0
Nodes (1): 获取结算单列表 - 低频操作         权重：1

### Community 79 - "Deploy Scripts"
Cohesion: 1.0
Nodes (1): 获取仪表盘图表数据 - 低频操作         权重：1

### Community 80 - "Backend Requirements"
Cohesion: 1.0
Nodes (1): 获取当前用户信息 - 低频操作         权重：1

### Community 81 - "Frontend Config Files"
Cohesion: 1.0
Nodes (1): God Nodes (Highly Connected Components)

### Community 82 - "Vite Build Config"
Cohesion: 1.0
Nodes (1): Command: /graphify explain

### Community 83 - "Playwright Config"
Cohesion: 1.0
Nodes (1): BalanceCards Component

## Knowledge Gaps
- **166 isolated node(s):** `add_webhook_signatures  Revision ID: 002 Revises: 001 Create Date: 2026-04-03`, `add missing indexes for query optimization  Revision ID: 003 Revises: 002 Create`, `添加缺失的索引以优化查询性能      索引添加说明:     1. recharge_records.created_at - 用于 ORDER BY 排序`, `回滚索引删除      注意：生产环境删除索引前请评估对查询性能的影响`, `create users roles permissions tables  Revision ID: 001_initial Revises: Create` (+161 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Logging Configuration`** (2 nodes): `create_test_data.py`, `create_test_data()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Docker Compose Config`** (1 nodes): `playwright.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Documentation Index`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Phase Implementation Plans`** (1 nodes): `debug_middleware.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Customer Groups Design`** (1 nodes): `测试权限去重（用户有多个角色包含相同权限）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Frontend Redesign Specs`** (1 nodes): `测试 months 参数（默认 6，最大 12）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Platform Design Spec`** (1 nodes): `TC-API-ROLE-005: 测试获取角色列表成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Test Plans`** (1 nodes): `TC-API-ROLE-005: 测试分页参数`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Test Reports`** (1 nodes): `TC-API-ROLE-005: 测试搜索功能`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Performance Optimization`** (1 nodes): `TC-API-ROLE-001: 测试创建角色成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Permission Checker`** (1 nodes): `TC-API-ROLE-005: 测试创建重复角色`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Customer Management Optimization`** (1 nodes): `TC-API-ROLE-016: 测试创建角色 - 空名称验证`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backend Initialization`** (1 nodes): `TC-API-ROLE-001: 测试创建角色时分配权限`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `UX/UI Improvements`** (1 nodes): `TC-API-ROLE-002: 测试更新角色成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `User Manual`** (1 nodes): `TC-API-ROLE-007: 测试编辑系统角色 - 名称保护`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Development Guide (AGENTS)`** (1 nodes): `TC-API-ROLE-003: 测试分配权限成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Project README`** (1 nodes): `TC-API-ROLE-015: 测试分配权限 - 空权限验证`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Database Migration Guide`** (1 nodes): `TC-API-ROLE-008: 测试删除自定义角色`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Redis Cache Analysis`** (1 nodes): `TC-API-ROLE-009: 测试删除系统角色 - 保护机制`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Query Optimization`** (1 nodes): `TC-API-ROLE-006: 测试获取权限列表`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Sentry Integration Plan`** (1 nodes): `TC-API-ROLE-006: 测试权限数据结构`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Structured Logging Config`** (1 nodes): `获取客户列表 - 高频操作         权重：5（最高频率）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Sanic Integration`** (1 nodes): `获取余额信息 - 中频操作         权重：3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Role Permission Tests`** (1 nodes): `获取仪表盘统计数据 - 低频操作         权重：2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Customer Page Tests`** (1 nodes): `获取余额列表 - 中频操作         权重：2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Phase 0-7 Tests`** (1 nodes): `获取客户详情 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `E2E Test Reports`** (1 nodes): `获取消费记录 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Final Fix Reports`** (1 nodes): `获取定价规则 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Podman macOS Deploy`** (1 nodes): `获取结算单列表 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Deploy Scripts`** (1 nodes): `获取仪表盘图表数据 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backend Requirements`** (1 nodes): `获取当前用户信息 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Frontend Config Files`** (1 nodes): `God Nodes (Highly Connected Components)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Build Config`** (1 nodes): `Command: /graphify explain`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Playwright Config`** (1 nodes): `BalanceCards Component`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Customer` connect `Analytics Business Logic` to `Health Score Queries`, `Tag Management`, `Customer Group Management`, `Database Models & Base Classes`, `Frontend Router Config`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `BaseModel` connect `Health Score Queries` to `Analytics Business Logic`, `Audit Log System`, `Tag Management`, `Customer Group Management`, `Database Models & Base Classes`, `Invoice & Webhook Tasks`, `Frontend Router Config`, `User Management`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `CacheService` connect `Redis Cache Service` to `Database Models & Base Classes`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 95 inferred relationships involving `Customer` (e.g. with `P6-3: 月度结算单自动生成任务 为非重点客户自动生成上月结算单` and `自动生成月度结算单      执行时间：每月 1 日 02:00     职责：为非重点客户自动生成上月结算单`) actually correct?**
  _`Customer` has 95 INFERRED edges - model-reasoned connections that need verification._
- **Are the 82 inferred relationships involving `CustomerBalance` (e.g. with `P6-4: 余额预警检查任务 每小时检查客户余额，标记预警状态` and `检查客户余额预警      执行时间：每小时     职责：检查所有客户余额，标记预警状态`) actually correct?**
  _`CustomerBalance` has 82 INFERRED edges - model-reasoned connections that need verification._
- **Are the 72 inferred relationships involving `Invoice` (e.g. with `P6-3: 月度结算单自动生成任务 为非重点客户自动生成上月结算单` and `自动生成月度结算单      执行时间：每月 1 日 02:00     职责：为非重点客户自动生成上月结算单`) actually correct?**
  _`Invoice` has 72 INFERRED edges - model-reasoned connections that need verification._
- **Are the 48 inferred relationships involving `AnalyticsService` (e.g. with `Customer` and `CustomerProfile`) actually correct?**
  _`AnalyticsService` has 48 INFERRED edges - model-reasoned connections that need verification._