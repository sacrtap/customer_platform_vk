# Graph Report - .  (2026-04-09)

## Corpus Check
- 184 files · ~157,111 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1533 nodes · 2607 edges · 73 communities detected
- Extraction: 57% EXTRACTED · 43% INFERRED · 0% AMBIGUOUS · INFERRED: 1128 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Customer` - 94 edges
2. `CustomerBalance` - 81 edges
3. `Invoice` - 76 edges
4. `InvoiceService` - 65 edges
5. `AnalyticsService` - 64 edges
6. `BalanceService` - 60 edges
7. `PricingService` - 58 edges
8. `RechargeRecord` - 54 edges
9. `PricingRule` - 54 edges
10. `make_mock_execute_result()` - 51 edges

## Surprising Connections (you probably didn't know these)
- `Webhook 签名记录表 - 用于防止重放攻击` --uses--> `BaseModel`  [INFERRED]
  backend/app/models/webhooks.py → backend/app/models/base.py
- `集成测试配置 - 使用 Sanic ASGI Client + pytest-asyncio  架构说明： - 使用 Sanic 内置的 ASGI 测试客户端` --uses--> `BaseModel`  [INFERRED]
  backend/tests/integration/conftest.py → backend/app/models/base.py
- `Mock APScheduler 避免初始化问题` --uses--> `BaseModel`  [INFERRED]
  backend/tests/integration/conftest.py → backend/app/models/base.py
- `创建同步测试数据库引擎（用于 Analytics Service 等）` --uses--> `BaseModel`  [INFERRED]
  backend/tests/integration/conftest.py → backend/app/models/base.py
- `创建 Sanic 应用实例（使用异步数据库引擎）` --uses--> `BaseModel`  [INFERRED]
  backend/tests/integration/conftest.py → backend/app/models/base.py

## Communities

### Community 0 - "Backend API & Services"
Cohesion: 0.02
Nodes (69): list_audit_logs(), 获取审计日志列表（支持筛选和分页）      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20, 通用 Redis 缓存服务  提供热点数据缓存功能，支持： - 客户列表缓存 - 标签列表缓存 - 客户详情缓存 - 缓存失效管理, SoftDeleteMixin, TimestampMixin, AuditLog, allowed_extension(), delete_file() (+61 more)

### Community 1 - "Frontend Vue Components"
Cohesion: 0.03
Nodes (39): AnalyticsService, analytics_service(), _AsyncCM, make_mock_execute_result(), make_mock_row(), mock_db(), MockDBSession, 客户运营中台 - Analytics Service 单元测试  测试目标： 1. 消耗分析 - get_consumption_trend, get_top_ (+31 more)

### Community 2 - "Database Models & Schema"
Cohesion: 0.09
Nodes (71): 获取客户健康度统计（优化：6次查询 → 2次查询）, 获取长期未消耗客户列表（优化：使用子查询替代 Python 集合操作）, 获取仪表盘统计数据（优化：6次查询 → 2次查询）, BaseModel, BaseModel, BalanceService, ConsumptionRecord, CustomerBalance (+63 more)

### Community 3 - "Test Suite & Fixtures"
Cohesion: 0.03
Nodes (38): create_customer(), Customer, CustomerProfile, CustomerService, export_customers(), import_customers(), list_customers(), 客户服务类      支持同步和异步 Session (+30 more)

### Community 4 - "Design System & Tokens"
Cohesion: 0.03
Nodes (25): CacheService, 删除指定缓存          Args:             prefix: 缓存前缀             *parts: 键的组成部分, 批量删除匹配模式的缓存          Args:             pattern: 匹配模式，如 "cache:customer_list:*", 清除客户相关缓存          Args:             customer_id: 指定客户 ID 则只清除该客户缓存，None 则清除所有客户缓, 清除分析相关缓存          Args:             category: 指定类别，如 "dashboard", "health", "pro, 从缓存获取数据          Args:             prefix: 缓存前缀             *parts: 键的组成部分, 设置缓存数据          Args:             prefix: 缓存前缀             data: 要缓存的数据, cache_with_mock_redis() (+17 more)

### Community 5 - "Authentication & Auth"
Cohesion: 0.04
Nodes (29): InvoiceStatus, Enum, str, Webhook Cleanup Tasks 单元测试 测试覆盖率目标：80%+, TestCleanupWebhookSignatures, Webhook 路由单元测试 测试覆盖率目标：85%+, 测试带 Z 后缀的时间戳 - 代码会移除 Z, TestCheckSignatureNotUsed (+21 more)

### Community 6 - "Customer Management"
Cohesion: 0.04
Nodes (27): AuthService, _check_permission(), forgot_password(), login(), 检查用户是否有指定权限（支持通配符匹配）      Args:         user_permissions: 用户权限集合         require, 使用 Refresh Token 刷新 Access Token, 忘记密码 - 发送密码重置链接      Body:     {         "username": "string (required)",, # TODO: 发送重置邮件到 user.email (+19 more)

### Community 7 - "Documentation & Specs"
Cohesion: 0.07
Nodes (51): make_mock_execute_result(), mock_db(), test_apply_discount_amount_too_large(), test_apply_discount_invoice_not_found(), test_apply_discount_success(), test_apply_discount_wrong_state(), test_complete_insufficient_balance(), test_complete_success() (+43 more)

### Community 8 - "Deployment & DevOps"
Cohesion: 0.05
Nodes (25): check_balance_warning(), _log_check_task(), P6-4: 余额预警检查任务 每小时检查客户余额，标记预警状态, 检查客户余额预警      执行时间：每小时     职责：检查所有客户余额，标记预警状态, SyncTaskLog, _log_email_task(), P6-7: 逾期提醒邮件任务 每日 9 点发送逾期账单提醒给商务, 发送逾期账单提醒邮件      执行时间：每日 09:00     职责：向商务发送逾期账单提醒 (+17 more)

### Community 9 - "Table Components & UI"
Cohesion: 0.06
Nodes (37): AsyncSession, customer_service(), make_mock_execute_result(), mock_db(), MockDBSession, 客户运营中台 - CustomerService 批量创建客户单元测试  测试目标：CustomerService.batch_create_customers, 验证 flush 在 add_all 之前调用, 创建 CustomerService 实例（不 patch 模型，使用真实模型类） (+29 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (7): apply_discount(), create_pricing_rule(), export_invoices(), generate_invoice(), getInvoices(), getRecentInvoices(), recharge()

### Community 11 - "Community 11"
Cohesion: 0.05
Nodes (11): batch_add_customer_tags(), batch_remove_customer_tags(), create_tag(), list_tags(), 创建标签      Body:     {         "name": "string (required)",         "type": "stri, 更新标签      Body:     {         "name": "string (optional)",         "category": ", 获取标签列表（支持筛选）      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20), 批量给客户添加标签      Body:     {         "customer_ids": [1, 2, 3],         "tag_ids": (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (17): CustomerGroup, CustomerGroupMember, CustomerGroupService, _is_async_session(), 删除群组（软删除）          Args:             group_id: 群组 ID          Returns:, 添加成员到静态群组          Args:             group_id: 群组 ID             customer_id: 客户, 移除群组成员          Args:             group_id: 群组 ID             customer_id: 客户 ID, 获取群组成员列表          Args:             group_id: 群组 ID             page: 页码 (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (16): BaseSettings, Config, get_settings(), Settings, ExternalAPIClient, 外部 API 客户端 - 用于同步业务系统数据, 获取用量统计数据          Args:             start_date: 开始日期             end_date: 结束日期, 获取客户每日用量数据          Args:             customer_id: 客户 ID             start_date: (+8 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (12): HttpUser, CustomerPlatformUser, 性能测试脚本 - Locust 测试 API 响应时间和并发能力, CustomerPlatformUser, on_quitting(), on_request(), 客户平台 API 负载测试脚本 - Locust  测试关键 API 端点的响应时间和并发能力  使用方法:     cd backend     locust, 每个请求完成时执行     可用于记录详细日志或自定义指标 (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (0): 

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (7): Customers API 集成测试  测试覆盖： 1. GET /api/v1/customers - 客户列表（带筛选） 2. GET /api/v1/cu, 测试 Excel 导入客户 - 文件格式错误, 测试 Excel 导入客户 - 缺少必填列, 测试 Excel 导出客户 - 带筛选条件, test_export_customers_with_filters(), test_import_customers_missing_columns(), test_import_customers_wrong_format()

### Community 17 - "Community 17"
Cohesion: 0.1
Nodes (22): group_service(), make_mock_execute_result(), mock_db(), MockDBSession, 客户群组服务单元测试  测试 CustomerGroupService 的 CRUD 操作, 创建 CustomerGroupService 实例, test_add_member(), test_add_member_already_exists() (+14 more)

### Community 18 - "Community 18"
Cohesion: 0.06
Nodes (5): Billing API 集成测试  测试覆盖： 1. GET /api/v1/billing/balances - 获取余额列表 2. GET /api/v1/, 测试获取客户余额 - 余额不存在（返回 0）, 测试结算单完整工作流：生成 -> 提交 -> 确认 -> 付款 -> 完成, test_get_customer_balance_not_exists(), test_invoice_workflow_full()

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (8): 角色管理 API 集成测试  覆盖测试计划中的 API 测试用例: - TC-API-ROLE-001: 创建角色 API - TC-API-ROLE-002:, TestApiErrorHandling, TestAssignPermissions, TestCreateRole, TestDeleteRole, TestGetPermissions, TestGetRoles, TestUpdateRole

### Community 20 - "Community 20"
Cohesion: 0.08
Nodes (6): DeclarativeBase, EmailService, 渲染邮件模板          Args:             template_name: 模板文件名             **context: 模板, 发送邮件          Args:             to_emails: 收件人邮箱列表             subject: 邮件主题, Base, TestEmailService

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (9): auth_token(), Analytics API 集成测试  测试覆盖： 1. GET /api/v1/analytics/dashboard/stats - 获取仪表盘统计 2., 测试获取消耗趋势 - 使用默认日期（最近 6 个月）, 获取认证 Token - 直接创建用户并生成 JWT, 测试获取余额预警客户列表 - 使用默认阈值, 测试 Analytics API - 未授权访问, test_analytics_unauthorized(), test_consumption_trend_default_dates() (+1 more)

### Community 22 - "Community 22"
Cohesion: 0.09
Nodes (6): 定时任务单元测试 测试覆盖率目标：85%+, TestBalanceCheckTask, TestFileCleanupTask, TestInvoiceGeneratorTask, TestUsageSyncTask, TestWebhookCleanupTask

### Community 23 - "Community 23"
Cohesion: 0.11
Nodes (8): assign_permissions(), create_role(), list_roles(), 更新角色信息      Body:     {         "name": "string (optional)",         "descriptio, 获取角色列表      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20), 为角色分配权限      Body:     {         "permission_ids": [1, 2, 3]     }, 创建角色      Body:     {         "name": "string (required)",         "description", update_role()

### Community 24 - "Community 24"
Cohesion: 0.12
Nodes (9): auth_token(), Files API 集成测试  测试覆盖： 1. POST /api/v1/files/upload - 上传文件（成功、文件类型验证、大小限制） 2. GET, 测试获取文件详情 - 文件不存在（需要 files:read 权限）, 测试删除文件 - 文件不存在（需要 files:delete 权限）, 使用 test_user fixture 获取认证 Token, 测试上传文件 - 成功场景（.xlsx 文件）, test_delete_file_not_found(), test_get_file_not_found() (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (9): app(), mock_scheduler(), pytest_configure(), 集成测试配置 - 使用 Sanic ASGI Client + pytest-asyncio  架构说明： - 使用 Sanic 内置的 ASGI 测试客户端, 创建 Sanic 应用实例（使用异步数据库引擎）, pytest 配置 hook - 确保环境变量在任何测试前设置, Mock APScheduler 避免初始化问题, 创建同步测试数据库引擎（用于 Analytics Service 等） (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.15
Nodes (2): TestUserImportEdgeCases, TestUserImportValidation

### Community 27 - "Community 27"
Cohesion: 0.17
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 0.18
Nodes (11): frontend/src/views/customers/Detail.vue, frontend/src/views/customers/Index.vue, 客户管理页面体验优化实施计划, Task 1: 修复创建时间格式问题, Task 2: 优化重点客户样式显示, Task 3: 优化运营经理字段为下拉选择, Task 4: 优化筛选区域布局, Task 5: 在 Detail.vue 中添加缺失的编辑字段 (+3 more)

### Community 29 - "Community 29"
Cohesion: 0.22
Nodes (1): Users API 集成测试  测试覆盖： 1. GET /api/v1/users - 获取用户列表、筛选用户 2. POST /api/v1/users -

### Community 30 - "Community 30"
Cohesion: 0.25
Nodes (4): PermissionCache, 获取用户权限列表          Args:             user_id: 用户 ID          Returns:, 设置用户权限缓存          Args:             user_id: 用户 ID             permissions: 权限列表, 失效用户权限缓存          Args:             user_id: 用户 ID          Returns:

### Community 31 - "Community 31"
Cohesion: 0.29
Nodes (2): getCellValue(), rowComparator()

### Community 32 - "Community 32"
Cohesion: 0.29
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 0.29
Nodes (1): 集成测试 - API 端点测试  使用异步数据库操作，与生产环境一致 所有测试函数使用异步方式

### Community 34 - "Community 34"
Cohesion: 0.33
Nodes (5): downgrade(), add missing indexes for query optimization  Revision ID: 003 Revises: 002 Create, 添加缺失的索引以优化查询性能      索引添加说明:     1. recharge_records.created_at - 用于 ORDER BY 排序, 回滚索引删除      注意：生产环境删除索引前请评估对查询性能的影响, upgrade()

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (1): Audit Logs API 集成测试  测试覆盖： 1. GET /api/v1/audit-logs - 获取审计日志列表、筛选审计日志 2. GET /a

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (1): add_webhook_signatures  Revision ID: 002 Revises: 001 Create Date: 2026-04-03

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (1): create users roles permissions tables  Revision ID: 001_initial Revises: Create

### Community 39 - "Community 39"
Cohesion: 0.5
Nodes (1): add customer groups models  Revision ID: 002 Revises: 001 Create Date: 2026-04-0

### Community 40 - "Community 40"
Cohesion: 0.5
Nodes (1): add_all_missing_tables  Revision ID: a5d21c5761aa Revises: 002 Create Date: 2026

### Community 41 - "Community 41"
Cohesion: 0.5
Nodes (1): add files table  Revision ID: 003 Revises: a5d21c5761aa Create Date: 2026-04-06

### Community 42 - "Community 42"
Cohesion: 0.67
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (2): get_or_create_permission(), seed()

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试获取角色列表成功

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试分页参数

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试搜索功能

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-001: 测试创建角色成功

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试创建重复角色

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-016: 测试创建角色 - 空名称验证

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-001: 测试创建角色时分配权限

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-002: 测试更新角色成功

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-007: 测试编辑系统角色 - 名称保护

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-003: 测试分配权限成功

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-015: 测试分配权限 - 空权限验证

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-008: 测试删除自定义角色

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-009: 测试删除系统角色 - 保护机制

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-006: 测试获取权限列表

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-006: 测试权限数据结构

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): 获取客户列表 - 高频操作         权重：5（最高频率）

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): 获取余额信息 - 中频操作         权重：3

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): 获取仪表盘统计数据 - 低频操作         权重：2

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): 获取余额列表 - 中频操作         权重：2

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): 获取客户详情 - 低频操作         权重：1

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): 获取消费记录 - 低频操作         权重：1

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): 获取定价规则 - 低频操作         权重：1

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): 获取结算单列表 - 低频操作         权重：1

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): 获取仪表盘图表数据 - 低频操作         权重：1

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): 获取当前用户信息 - 低频操作         权重：1

## Knowledge Gaps
- **109 isolated node(s):** `add_webhook_signatures  Revision ID: 002 Revises: 001 Create Date: 2026-04-03`, `add missing indexes for query optimization  Revision ID: 003 Revises: 002 Create`, `添加缺失的索引以优化查询性能      索引添加说明:     1. recharge_records.created_at - 用于 ORDER BY 排序`, `回滚索引删除      注意：生产环境删除索引前请评估对查询性能的影响`, `create users roles permissions tables  Revision ID: 001_initial Revises: Create` (+104 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 44`** (2 nodes): `create_test_data.py`, `create_test_data()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `playwright.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `debug_middleware.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `TC-API-ROLE-005: 测试获取角色列表成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `TC-API-ROLE-005: 测试分页参数`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `TC-API-ROLE-005: 测试搜索功能`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `TC-API-ROLE-001: 测试创建角色成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `TC-API-ROLE-005: 测试创建重复角色`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `TC-API-ROLE-016: 测试创建角色 - 空名称验证`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `TC-API-ROLE-001: 测试创建角色时分配权限`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `TC-API-ROLE-002: 测试更新角色成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `TC-API-ROLE-007: 测试编辑系统角色 - 名称保护`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `TC-API-ROLE-003: 测试分配权限成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `TC-API-ROLE-015: 测试分配权限 - 空权限验证`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `TC-API-ROLE-008: 测试删除自定义角色`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `TC-API-ROLE-009: 测试删除系统角色 - 保护机制`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `TC-API-ROLE-006: 测试获取权限列表`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `TC-API-ROLE-006: 测试权限数据结构`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `获取客户列表 - 高频操作         权重：5（最高频率）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `获取余额信息 - 中频操作         权重：3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `获取仪表盘统计数据 - 低频操作         权重：2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `获取余额列表 - 中频操作         权重：2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `获取客户详情 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `获取消费记录 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `获取定价规则 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `获取结算单列表 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `获取仪表盘图表数据 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `获取当前用户信息 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Customer` connect `Test Suite & Fixtures` to `Frontend Vue Components`, `Database Models & Schema`, `Deployment & DevOps`, `Community 11`, `Community 12`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Why does `BaseModel` connect `Database Models & Schema` to `Backend API & Services`, `Test Suite & Fixtures`, `Authentication & Auth`, `Deployment & DevOps`, `Community 12`, `Community 25`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `CacheService` connect `Design System & Tokens` to `Backend API & Services`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Are the 91 inferred relationships involving `Customer` (e.g. with `P6-3: 月度结算单自动生成任务 为非重点客户自动生成上月结算单` and `自动生成月度结算单      执行时间：每月 1 日 02:00     职责：为非重点客户自动生成上月结算单`) actually correct?**
  _`Customer` has 91 INFERRED edges - model-reasoned connections that need verification._
- **Are the 78 inferred relationships involving `CustomerBalance` (e.g. with `P6-4: 余额预警检查任务 每小时检查客户余额，标记预警状态` and `检查客户余额预警      执行时间：每小时     职责：检查所有客户余额，标记预警状态`) actually correct?**
  _`CustomerBalance` has 78 INFERRED edges - model-reasoned connections that need verification._
- **Are the 74 inferred relationships involving `Invoice` (e.g. with `P6-3: 月度结算单自动生成任务 为非重点客户自动生成上月结算单` and `自动生成月度结算单      执行时间：每月 1 日 02:00     职责：为非重点客户自动生成上月结算单`) actually correct?**
  _`Invoice` has 74 INFERRED edges - model-reasoned connections that need verification._
- **Are the 54 inferred relationships involving `InvoiceService` (e.g. with `P6-3: 月度结算单自动生成任务 为非重点客户自动生成上月结算单` and `自动生成月度结算单      执行时间：每月 1 日 02:00     职责：为非重点客户自动生成上月结算单`) actually correct?**
  _`InvoiceService` has 54 INFERRED edges - model-reasoned connections that need verification._