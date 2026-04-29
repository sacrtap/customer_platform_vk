# 客户运营中台 - 文档导航

> 最后更新: 2026-04-27

---

## 快速链接

| 文档类型       | 路径                                    | 说明                     |
| -------------- | --------------------------------------- | ------------------------ |
| **用户手册**   | [user-manual.md](user-manual.md)        | 面向最终用户的使用指南   |
| **开发指南**   | [guides/](guides/)                      | 本地环境搭建、数据库迁移等 |
| **设计文档**   | [design/](design/)                      | 设计规范、样式规范       |
| **数据库文档** | [database/](database/)                  | 数据库变更日志           |
| **性能优化**   | [performance/](performance/)            | 查询优化、缓存、监控     |
| **测试文档**   | [testing/](testing/)                    | 测试计划、报告、环境配置 |
| **前端组件**   | [frontend/components.md](frontend/components.md) | Vue 组件清单与复用指南 |
| **数据库文档** | [database/](database/)                  | 数据库变更日志           |
| **Superpowers** | [superpowers/](superpowers/)            | AI 工作流产出的规格与计划 |
| **原型**       | [prototypes/](prototypes/)              | HTML 原型文件            |

---

## 开发指南

| 文件                                              | 说明             |
| ------------------------------------------------- | ---------------- |
| [agents-guide.md](guides/agents-guide.md) | **Agent 开发指南** (完整命令/env/git/工作流) |
| [local-setup-guide.md](guides/local-setup-guide.md) | 本地环境搭建指南 (PostgreSQL + Redis + 后端 + 前端) |
| [database-migration-guide.md](guides/database-migration-guide.md) | 数据库迁移指南 |
| [test-optimization-guide.md](guides/test-optimization-guide.md) | 测试优化指南 |

## 设计文档

| 文件                                              | 说明             |
| ------------------------------------------------- | ---------------- |
| [DESIGN-SPEC.md](design/DESIGN-SPEC.md)           | 设计规格说明     |
| [QUICK-REFERENCE.md](design/QUICK-REFERENCE.md)   | 设计快速参考     |
| [TABLE-STYLE-UPDATE.md](design/TABLE-STYLE-UPDATE.md) | 表格样式更新记录 |
| [Design System MASTER](design/design-system/customer-platform-vk/MASTER.md) | 设计系统主文件 |

## 性能优化

| 文件                                                          | 说明             | 状态 |
| ------------------------------------------------------------- | ---------------- | ---- |
| [README.md](performance/README.md)                              | 性能优化文档索引 | -    |
| [db-query-optimization.md](performance/db-query-optimization.md) | 数据库查询优化   | ✅ 完成 |
| [query-optimization-examples.md](performance/query-optimization-examples.md) | 查询优化示例     | ✅ 完成 |
| [redis-cache-analysis.md](performance/redis-cache-analysis.md) | Redis 缓存分析   | ✅ 完成 |
| [structured-logging-config.md](performance/structured-logging-config.md) | 结构化日志配置   | ✅ 完成 |
| [sentry-integration-plan.md](performance/sentry-integration-plan.md) | Sentry 集成计划  | 📋 计划中 |
| [test-optimization-guide.md](../guides/test-optimization-guide.md) | 测试优化指南     | ✅ 完成 |

## 测试文档

### 测试计划
- [test-plan.md](testing/plans/test-plan.md) - 通用测试计划
- [phase0-7-test-plan.md](testing/plans/phase0-7-test-plan.md) - Phase 0-7 测试计划
- [customer-page-test-plan.md](testing/plans/customer-page-test-plan.md) - 客户页面测试计划
- [role-permission-test-plan.md](testing/plans/role-permission-test-plan.md) - 角色权限测试计划

### 测试报告
- [unit-test-report.md](testing/reports/unit-test-report.md) - 单元测试报告
- [customer-page-test-report.md](testing/reports/customer-page-test-report.md) - 客户页面测试报告
- [role-permission-test-report.md](testing/reports/role-permission-test-report.md) - 角色权限测试报告
- [final-fix-report.md](testing/reports/final-fix-report.md) - 最终修复报告
- [final-improvement-report.md](testing/reports/final-improvement-report.md) - 最终改进报告

### 测试环境
- [test-database-setup.md](testing/setup/test-database-setup.md) - 测试数据库配置

### 测试覆盖率
- HTML 覆盖率报告：运行 `make test-cov` 后在 `backend/htmlcov/index.html` 查看
- CI 覆盖率门槛：≥50%（当前 46%+）

### E2E 测试
- [前端 E2E 测试指南](../frontend/tests/e2e/README.md) - Playwright E2E 测试指南 (57 个客户管理测试)
- [HTML 测试报告](../frontend/tests/e2e/playwright-report/index.html) - 最新测试报告 (需运行测试后生成)

### 测试优化
- [测试优化指南](guides/test-optimization-guide.md) - 测试并行化、增量测试、fixture 优化

## Superpowers 工作流

### 设计规格 (specs)

| 文件 | 日期 | 说明 | 状态 |
| ---- | ---- | ---- | ---- |
| [2026-04-01-customer-platform-design.md](superpowers/specs/2026-04-01-customer-platform-design.md) | 04-01 | 客户运营中台系统设计 | ✅ 完成 |
| [2026-04-01-customer-platform-implementation-plan.md](superpowers/specs/2026-04-01-customer-platform-implementation-plan.md) | 04-01 | 实现计划 | ✅ 完成 |
| [2026-04-03-customer-groups-design.md](superpowers/specs/2026-04-03-customer-groups-design.md) | 04-03 | 客户分组设计 | ✅ 完成 |
| [2026-04-06-frontend-redesign.md](superpowers/specs/2026-04-06-frontend-redesign.md) | 04-06 | 前端重设计规格 | ✅ 完成 |
| [2026-04-12-customer-detail-redesign.md](superpowers/specs/2026-04-12-customer-detail-redesign.md) | 04-12 | 客户详情重设计规格 | ✅ 完成 |
| [2026-04-14-business-type-to-industry-type-design.md](superpowers/specs/2026-04-14-business-type-to-industry-type-design.md) | 04-14 | 业务类型→行业类型转换 | ✅ 完成 |
| [2026-04-14-customer-detail-fields-design.md](superpowers/specs/2026-04-14-customer-detail-fields-design.md) | 04-14 | 客户详情字段扩展 | ✅ 完成 |
| [2026-04-14-fine-grained-permissions-design.md](superpowers/specs/2026-04-14-fine-grained-permissions-design.md) | 04-14 | 细粒度权限设计 | ✅ 完成 |
| [2026-04-15-customer-detail-optimization-design.md](superpowers/specs/2026-04-15-customer-detail-optimization-design.md) | 04-15 | 客户详情优化 | ✅ 完成 |
| [2026-04-15-customer-edit-dialog-optimization-design.md](superpowers/specs/2026-04-15-customer-edit-dialog-optimization-design.md) | 04-15 | 客户编辑弹窗优化 | ✅ 完成 |
| [2026-04-15-customer-import-template-fix-design.md](superpowers/specs/2026-04-15-customer-import-template-fix-design.md) | 04-15 | 客户导入模板修复 | ✅ 完成 |
| [2026-04-15-delete-business-type-use-profile-industry-design.md](superpowers/specs/2026-04-15-delete-business-type-use-profile-industry-design.md) | 04-15 | 删除业务类型使用行业类型 | ✅ 完成 |
| [2026-04-17-customer-data-import-type-migration-design.md](superpowers/specs/2026-04-17-customer-data-import-type-migration-design.md) | 04-17 | 客户导入类型迁移 | ✅ 完成 |
| [2026-04-20-customer-import-extension-design.md](superpowers/specs/2026-04-20-customer-import-extension-design.md) | 04-20 | 客户导入扩展 | ✅ 完成 |
| [2026-04-21-customer-detail-layout-unify-design.md](superpowers/specs/2026-04-21-customer-detail-layout-unify-design.md) | 04-21 | 客户详情布局统一 | ✅ 完成 |
| [2026-04-21-customer-list-sorting-design.md](superpowers/specs/2026-04-21-customer-list-sorting-design.md) | 04-21 | 客户列表排序 | ✅ 完成 |
| [2026-04-22-customer-filter-settlement-type-design.md](superpowers/specs/2026-04-22-customer-filter-settlement-type-design.md) | 04-22 | 客户筛选结算方式 | ✅ 完成 |
| [2026-04-22-profile-dashboard-design.md](superpowers/specs/2026-04-22-profile-dashboard-design.md) | 04-22 | 画像仪表盘设计 | ✅ 完成 |
| [2026-04-22-profile-pages-merge-design.md](superpowers/specs/2026-04-22-profile-pages-merge-design.md) | 04-22 | 画像页面合并 | ✅ 完成 |
| [2026-04-23-customer-search-filter-design.md](superpowers/specs/2026-04-23-customer-search-filter-design.md) | 04-23 | 客户筛选器输入检索 | ✅ 完成 |

### 实现计划 (plans)

| 文件 | 日期 | 说明 | 状态 |
| ---- | ---- | ---- | ---- |
| [2026-04-01-phase0-backend-initialization.md](superpowers/plans/2026-04-01-phase0-backend-initialization.md) | 04-01 | Phase 0 后端初始化 | ✅ 完成 |
| [2026-04-02-permission-checker-implementation.md](superpowers/plans/2026-04-02-permission-checker-implementation.md) | 04-02 | 权限检查器实现 | ✅ 完成 |
| [2026-04-03-customer-groups-implementation.md](superpowers/plans/2026-04-03-customer-groups-implementation.md) | 04-03 | 客户分组实现 | ✅ 完成 |
| [2026-04-07-ux-ui-improvements.md](superpowers/plans/2026-04-07-ux-ui-improvements.md) | 04-07 | UX/UI 改进 | ✅ 完成 |
| [2026-04-09-customer-management-optimization.md](superpowers/plans/2026-04-09-customer-management-optimization.md) | 04-09 | 客户管理优化 | ✅ 完成 |
| [2026-04-12-customer-detail-redesign.md](superpowers/plans/2026-04-12-customer-detail-redesign.md) | 04-12 | 客户详情重设计 | ✅ 完成 |
| [2026-04-14-business-type-to-industry-type-plan.md](superpowers/plans/2026-04-14-business-type-to-industry-type-plan.md) | 04-14 | 业务类型→行业类型转换 | ✅ 完成 |
| [2026-04-14-customer-detail-fields.md](superpowers/plans/2026-04-14-customer-detail-fields.md) | 04-14 | 客户详情字段 | ✅ 完成 |
| [2026-04-14-fine-grained-permissions-plan.md](superpowers/plans/2026-04-14-fine-grained-permissions-plan.md) | 04-14 | 细粒度权限 | ✅ 完成 |
| [2026-04-15-customer-detail-optimization-plan.md](superpowers/plans/2026-04-15-customer-detail-optimization-plan.md) | 04-15 | 客户详情优化 | ✅ 完成 |
| [2026-04-15-customer-edit-dialog-optimization.md](superpowers/plans/2026-04-15-customer-edit-dialog-optimization.md) | 04-15 | 客户编辑弹窗优化 | ✅ 完成 |
| [2026-04-15-customer-import-template-fix-plan.md](superpowers/plans/2026-04-15-customer-import-template-fix-plan.md) | 04-15 | 客户导入模板修复 | ✅ 完成 |
| [2026-04-15-delete-business-type-use-profile-industry-plan.md](superpowers/plans/2026-04-15-delete-business-type-use-profile-industry-plan.md) | 04-15 | 删除业务类型使用行业类型 | ✅ 完成 |
| [2026-04-17-customer-data-import-type-migration-plan.md](superpowers/plans/2026-04-17-customer-data-import-type-migration-plan.md) | 04-17 | 客户导入类型迁移 | ✅ 完成 |
| [2026-04-20-customer-import-extension-plan.md](superpowers/plans/2026-04-20-customer-import-extension-plan.md) | 04-20 | 客户导入扩展 | ✅ 完成 |
| [2026-04-21-customer-detail-layout-unify-plan.md](superpowers/plans/2026-04-21-customer-detail-layout-unify-plan.md) | 04-21 | 客户详情布局统一 | ✅ 完成 |
| [2026-04-21-customer-list-sorting-plan.md](superpowers/plans/2026-04-21-customer-list-sorting-plan.md) | 04-21 | 客户列表排序 | ✅ 完成 |
| [2026-04-22-customer-filter-settlement-type-plan.md](superpowers/plans/2026-04-22-customer-filter-settlement-type-plan.md) | 04-22 | 客户筛选结算方式 | ✅ 完成 |
| [2026-04-22-profile-dashboard-plan.md](superpowers/plans/2026-04-22-profile-dashboard-plan.md) | 04-22 | 画像仪表盘 | ✅ 完成 |
| [2026-04-22-profile-pages-merge-plan.md](superpowers/plans/2026-04-22-profile-pages-merge-plan.md) | 04-22 | 画像页面合并 | ✅ 完成 |
| [2026-04-23-customer-search-filter-implementation.md](superpowers/plans/2026-04-23-customer-search-filter-implementation.md) | 04-23 | 客户筛选器输入检索 | ✅ 完成 |

---

## 文档规范

- **设计规格** → `superpowers/specs/`
- **实现计划** → `superpowers/plans/`
- **测试计划** → `testing/plans/`
- **测试报告** → `testing/reports/`
- **性能/优化** → `performance/`
- **开发指南** → `guides/`
