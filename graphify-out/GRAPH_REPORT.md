# Graph Report - .  (2026-04-09)

## Corpus Check
- 186 files · ~156,854 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1529 nodes · 2591 edges · 77 communities detected
- Extraction: 57% EXTRACTED · 43% INFERRED · 0% AMBIGUOUS · INFERRED: 1122 edges (avg confidence: 0.5)
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
- `recharge()` --rationale_for--> `客户充值      Body:     {         "customer_id": 1,         "real_amount": 10000.00,`  [EXTRACTED]
  frontend/src/api/billing.ts → backend/app/routes/billing.py
- `Webhook 签名记录表 - 用于防止重放攻击` --uses--> `BaseModel`  [INFERRED]
  backend/app/models/webhooks.py → backend/app/models/base.py
- `CustomerGroupService` --uses--> `客户群组服务单元测试  测试 CustomerGroupService 的 CRUD 操作`  [INFERRED]
  backend/app/services/groups.py → backend/tests/unit/test_group_service.py
- `CustomerGroupService` --uses--> `创建 CustomerGroupService 实例`  [INFERRED]
  backend/app/services/groups.py → backend/tests/unit/test_group_service.py
- `CustomerService` --uses--> `客户运营中台 - CustomerService 批量创建客户单元测试  测试目标：CustomerService.batch_create_customers`  [INFERRED]
  backend/app/services/customers.py → backend/tests/unit/test_customer_service_batch.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (59): BaseModel, DailyUsage, create_customer(), Customer, CustomerProfile, CustomerService, export_customers(), import_customers() (+51 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (39): AnalyticsService, analytics_service(), _AsyncCM, make_mock_execute_result(), make_mock_row(), mock_db(), MockDBSession, 客户运营中台 - Analytics Service 单元测试  测试目标： 1. 消耗分析 - get_consumption_trend, get_top_ (+31 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (46): create_permission(), get_user_permissions(), 权限缓存服务  提供用户权限缓存功能，支持： - 用户权限列表缓存 - 权限缓存失效, 获取用户所有权限代码      Args:         session: 数据库会话         user_id: 用户ID      Returns:, 更新权限信息      Body:     {         "name": "string (optional)",         "descriptio, 创建权限      Body:     {         "code": "string (required)",         "name": "stri, update_permission(), Auth API 集成测试  测试覆盖： 1. /api/v1/auth/login - 登录成功、密码错误、用户不存在 2. /api/v1/auth/ref (+38 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (25): CacheService, 删除指定缓存          Args:             prefix: 缓存前缀             *parts: 键的组成部分, 批量删除匹配模式的缓存          Args:             pattern: 匹配模式，如 "cache:customer_list:*", 清除客户相关缓存          Args:             customer_id: 指定客户 ID 则只清除该客户缓存，None 则清除所有客户缓, 清除分析相关缓存          Args:             category: 指定类别，如 "dashboard", "health", "pro, 从缓存获取数据          Args:             prefix: 缓存前缀             *parts: 键的组成部分, 设置缓存数据          Args:             prefix: 缓存前缀             data: 要缓存的数据, cache_with_mock_redis() (+17 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (65): 获取客户健康度统计（优化：6次查询 → 2次查询）, 获取长期未消耗客户列表（优化：使用子查询替代 Python 集合操作）, 获取仪表盘统计数据（优化：6次查询 → 2次查询）, BalanceService, ConsumptionRecord, CustomerBalance, Invoice, InvoiceItem (+57 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (29): InvoiceStatus, Enum, str, Webhook Cleanup Tasks 单元测试 测试覆盖率目标：80%+, TestCleanupWebhookSignatures, Webhook 路由单元测试 测试覆盖率目标：85%+, 测试带 Z 后缀的时间戳 - 代码会移除 Z, TestCheckSignatureNotUsed (+21 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (29): AuthService, _check_permission(), forgot_password(), login(), 检查用户是否有指定权限（支持通配符匹配）      Args:         user_permissions: 用户权限集合         require, 检查用户是否有指定权限（支持通配符匹配）      Args:         user_permissions: 用户权限集合         require, 使用 Refresh Token 刷新 Access Token, 忘记密码 - 发送密码重置链接      Body:     {         "username": "string (required)", (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (51): make_mock_execute_result(), mock_db(), test_apply_discount_amount_too_large(), test_apply_discount_invoice_not_found(), test_apply_discount_success(), test_apply_discount_wrong_state(), test_complete_insufficient_balance(), test_complete_success() (+43 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (37): AsyncSession, customer_service(), make_mock_execute_result(), mock_db(), MockDBSession, 客户运营中台 - CustomerService 批量创建客户单元测试  测试目标：CustomerService.batch_create_customers, 验证 flush 在 add_all 之前调用, 创建 CustomerService 实例（不 patch 模型，使用真实模型类） (+29 more)

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (17): CustomerGroup, CustomerGroupMember, CustomerGroupService, _is_async_session(), 删除群组（软删除）          Args:             group_id: 群组 ID          Returns:, 添加成员到静态群组          Args:             group_id: 群组 ID             customer_id: 客户, 移除群组成员          Args:             group_id: 群组 ID             customer_id: 客户 ID, 获取群组成员列表          Args:             group_id: 群组 ID             page: 页码 (+9 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (0): 

### Community 11 - "Community 11"
Cohesion: 0.05
Nodes (16): BaseSettings, Config, get_settings(), Settings, ExternalAPIClient, 外部 API 客户端 - 用于同步业务系统数据, 获取用量统计数据          Args:             start_date: 开始日期             end_date: 结束日期, 获取客户每日用量数据          Args:             customer_id: 客户 ID             start_date: (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (33): list_audit_logs(), 获取审计日志列表（支持筛选和分页）      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20, BaseModel, 通用 Redis 缓存服务  提供热点数据缓存功能，支持： - 客户列表缓存 - 标签列表缓存 - 客户详情缓存 - 缓存失效管理, SoftDeleteMixin, TimestampMixin, AuditLog, app() (+25 more)

### Community 13 - "Community 13"
Cohesion: 0.06
Nodes (17): check_balance_warning(), _log_check_task(), P6-4: 余额预警检查任务 每小时检查客户余额，标记预警状态, 检查客户余额预警      执行时间：每小时     职责：检查所有客户余额，标记预警状态, SyncTaskLog, _log_email_task(), P6-7: 逾期提醒邮件任务 每日 9 点发送逾期账单提醒给商务, 发送逾期账单提醒邮件      执行时间：每日 09:00     职责：向商务发送逾期账单提醒 (+9 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (12): HttpUser, CustomerPlatformUser, 性能测试脚本 - Locust 测试 API 响应时间和并发能力, CustomerPlatformUser, on_quitting(), on_request(), 客户平台 API 负载测试脚本 - Locust  测试关键 API 端点的响应时间和并发能力  使用方法:     cd backend     locust, 每个请求完成时执行     可用于记录详细日志或自定义指标 (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.05
Nodes (7): apply_discount(), create_pricing_rule(), export_invoices(), generate_invoice(), getInvoices(), getRecentInvoices(), recharge()

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (7): Customers API 集成测试  测试覆盖： 1. GET /api/v1/customers - 客户列表（带筛选） 2. GET /api/v1/cu, 测试 Excel 导入客户 - 文件格式错误, 测试 Excel 导入客户 - 缺少必填列, 测试 Excel 导出客户 - 带筛选条件, test_export_customers_with_filters(), test_import_customers_missing_columns(), test_import_customers_wrong_format()

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (12): assign_permissions(), create_role(), list_roles(), 更新角色信息      Body:     {         "name": "string (optional)",         "descriptio, 更新角色信息      Body:     {         "name": "string (optional)",         "descriptio, 获取角色列表      Query:     - page: 页码 (默认 1)     - page_size: 每页数量 (默认 20), 为角色分配权限      Body:     {         "permission_ids": [1, 2, 3]     }, 为角色分配权限      Body:     {         "permission_ids": [1, 2, 3]     } (+4 more)

### Community 18 - "Community 18"
Cohesion: 0.1
Nodes (22): group_service(), make_mock_execute_result(), mock_db(), MockDBSession, 客户群组服务单元测试  测试 CustomerGroupService 的 CRUD 操作, 创建 CustomerGroupService 实例, test_add_member(), test_add_member_already_exists() (+14 more)

### Community 19 - "Community 19"
Cohesion: 0.06
Nodes (5): Billing API 集成测试  测试覆盖： 1. GET /api/v1/billing/balances - 获取余额列表 2. GET /api/v1/, 测试获取客户余额 - 余额不存在（返回 0）, 测试结算单完整工作流：生成 -> 提交 -> 确认 -> 付款 -> 完成, test_get_customer_balance_not_exists(), test_invoice_workflow_full()

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (8): 角色管理 API 集成测试  覆盖测试计划中的 API 测试用例: - TC-API-ROLE-001: 创建角色 API - TC-API-ROLE-002:, TestApiErrorHandling, TestAssignPermissions, TestCreateRole, TestDeleteRole, TestGetPermissions, TestGetRoles, TestUpdateRole

### Community 21 - "Community 21"
Cohesion: 0.08
Nodes (6): DeclarativeBase, EmailService, 渲染邮件模板          Args:             template_name: 模板文件名             **context: 模板, 发送邮件          Args:             to_emails: 收件人邮箱列表             subject: 邮件主题, Base, TestEmailService

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (9): auth_token(), Analytics API 集成测试  测试覆盖： 1. GET /api/v1/analytics/dashboard/stats - 获取仪表盘统计 2., 测试获取消耗趋势 - 使用默认日期（最近 6 个月）, 获取认证 Token - 直接创建用户并生成 JWT, 测试获取余额预警客户列表 - 使用默认阈值, 测试 Analytics API - 未授权访问, test_analytics_unauthorized(), test_consumption_trend_default_dates() (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.09
Nodes (6): 定时任务单元测试 测试覆盖率目标：85%+, TestBalanceCheckTask, TestFileCleanupTask, TestInvoiceGeneratorTask, TestUsageSyncTask, TestWebhookCleanupTask

### Community 24 - "Community 24"
Cohesion: 0.12
Nodes (9): auth_token(), Files API 集成测试  测试覆盖： 1. POST /api/v1/files/upload - 上传文件（成功、文件类型验证、大小限制） 2. GET, 测试获取文件详情 - 文件不存在（需要 files:read 权限）, 测试删除文件 - 文件不存在（需要 files:delete 权限）, 使用 test_user fixture 获取认证 Token, 测试上传文件 - 成功场景（.xlsx 文件）, test_delete_file_not_found(), test_get_file_not_found() (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.15
Nodes (2): TestUserImportEdgeCases, TestUserImportValidation

### Community 26 - "Community 26"
Cohesion: 0.17
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 0.22
Nodes (1): Users API 集成测试  测试覆盖： 1. GET /api/v1/users - 获取用户列表、筛选用户 2. POST /api/v1/users -

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (4): PermissionCache, 获取用户权限列表          Args:             user_id: 用户 ID          Returns:, 设置用户权限缓存          Args:             user_id: 用户 ID             permissions: 权限列表, 失效用户权限缓存          Args:             user_id: 用户 ID          Returns:

### Community 29 - "Community 29"
Cohesion: 0.29
Nodes (2): getCellValue(), rowComparator()

### Community 30 - "Community 30"
Cohesion: 0.29
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 0.29
Nodes (1): 集成测试 - API 端点测试  使用异步数据库操作，与生产环境一致 所有测试函数使用异步方式

### Community 32 - "Community 32"
Cohesion: 0.33
Nodes (5): downgrade(), add missing indexes for query optimization  Revision ID: 003 Revises: 002 Create, 添加缺失的索引以优化查询性能      索引添加说明:     1. recharge_records.created_at - 用于 ORDER BY 排序, 回滚索引删除      注意：生产环境删除索引前请评估对查询性能的影响, upgrade()

### Community 33 - "Community 33"
Cohesion: 0.33
Nodes (1): Audit Logs API 集成测试  测试覆盖： 1. GET /api/v1/audit-logs - 获取审计日志列表、筛选审计日志 2. GET /a

### Community 34 - "Community 34"
Cohesion: 0.5
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (1): add_webhook_signatures  Revision ID: 002 Revises: 001 Create Date: 2026-04-03

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (1): initial - create all tables  Revision ID: 001_initial Revises: Create Date: 2026

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (1): add customer groups models  Revision ID: 002 Revises: 001 Create Date: 2026-04-0

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (1): add_all_missing_tables  Revision ID: a5d21c5761aa Revises: 002 Create Date: 2026

### Community 39 - "Community 39"
Cohesion: 0.5
Nodes (1): add files table  Revision ID: 003 Revises: a5d21c5761aa Create Date: 2026-04-06

### Community 40 - "Community 40"
Cohesion: 0.67
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (2): get_or_create_permission(), seed()

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): E2E 测试指南

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): E2E 测试报告

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): 账号登录模块

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): 客户信息管理模块

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): 结算管理模块

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): 数据分析模块

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): 获取客户列表 - 高频操作         权重：5（最高频率）

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): 获取余额信息 - 中频操作         权重：3

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): 获取仪表盘统计数据 - 低频操作         权重：2

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): 获取余额列表 - 中频操作         权重：2

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): 获取客户详情 - 低频操作         权重：1

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): 获取消费记录 - 低频操作         权重：1

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): 获取定价规则 - 低频操作         权重：1

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): 获取结算单列表 - 低频操作         权重：1

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): 获取仪表盘图表数据 - 低频操作         权重：1

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): 获取当前用户信息 - 低频操作         权重：1

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试获取角色列表成功

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试分页参数

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试搜索功能

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-001: 测试创建角色成功

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-005: 测试创建重复角色

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-016: 测试创建角色 - 空名称验证

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-001: 测试创建角色时分配权限

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-002: 测试更新角色成功

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-007: 测试编辑系统角色 - 名称保护

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-003: 测试分配权限成功

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-015: 测试分配权限 - 空权限验证

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-008: 测试删除自定义角色

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-009: 测试删除系统角色 - 保护机制

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-006: 测试获取权限列表

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): TC-API-ROLE-006: 测试权限数据结构

## Knowledge Gaps
- **110 isolated node(s):** `E2E 测试指南`, `E2E 测试报告`, `账号登录模块`, `客户信息管理模块`, `结算管理模块` (+105 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 42`** (2 nodes): `create_test_data.py`, `create_test_data()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `E2E 测试指南`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `E2E 测试报告`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `账号登录模块`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `客户信息管理模块`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `结算管理模块`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `数据分析模块`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `playwright.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `debug_middleware.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `获取客户列表 - 高频操作         权重：5（最高频率）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `获取余额信息 - 中频操作         权重：3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `获取仪表盘统计数据 - 低频操作         权重：2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `获取余额列表 - 中频操作         权重：2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `获取客户详情 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `获取消费记录 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `获取定价规则 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `获取结算单列表 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `获取仪表盘图表数据 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `获取当前用户信息 - 低频操作         权重：1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `TC-API-ROLE-005: 测试获取角色列表成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `TC-API-ROLE-005: 测试分页参数`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `TC-API-ROLE-005: 测试搜索功能`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `TC-API-ROLE-001: 测试创建角色成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `TC-API-ROLE-005: 测试创建重复角色`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `TC-API-ROLE-016: 测试创建角色 - 空名称验证`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `TC-API-ROLE-001: 测试创建角色时分配权限`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `TC-API-ROLE-002: 测试更新角色成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `TC-API-ROLE-007: 测试编辑系统角色 - 名称保护`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `TC-API-ROLE-003: 测试分配权限成功`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `TC-API-ROLE-015: 测试分配权限 - 空权限验证`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `TC-API-ROLE-008: 测试删除自定义角色`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `TC-API-ROLE-009: 测试删除系统角色 - 保护机制`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `TC-API-ROLE-006: 测试获取权限列表`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `TC-API-ROLE-006: 测试权限数据结构`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.