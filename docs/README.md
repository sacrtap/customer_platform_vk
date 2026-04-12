# 客户运营中台 - 文档导航

> 最后更新: 2026-04-13

---

## 快速链接

| 文档类型       | 路径                                    | 说明                     |
| -------------- | --------------------------------------- | ------------------------ |
| **用户手册**   | [user-manual.md](user-manual.md)        | 面向最终用户的使用指南   |
| **开发指南**   | [guides/](guides/)                      | 数据库迁移等开发操作指南 |
| **设计文档**   | [design/](design/)                      | 设计规范、样式规范       |
| **性能优化**   | [performance/](performance/)            | 查询优化、缓存、监控     |
| **测试文档**   | [testing/](testing/)                    | 测试计划、报告、环境配置 |
| **Superpowers** | [superpowers/](superpowers/)            | AI 工作流产出的规格与计划 |
| **原型**       | [prototypes/](prototypes/)              | HTML 原型文件            |

---

## 设计文档

| 文件                                              | 说明             |
| ------------------------------------------------- | ---------------- |
| [DESIGN-SPEC.md](design/DESIGN-SPEC.md)           | 设计规格说明     |
| [QUICK-REFERENCE.md](design/QUICK-REFERENCE.md)   | 设计快速参考     |
| [TABLE-STYLE-UPDATE.md](design/TABLE-STYLE-UPDATE.md) | 表格样式更新记录 |
| [Design System MASTER](design/design-system/customer-platform-vk/MASTER.md) | 设计系统主文件 |

## 性能优化

| 文件                                                          | 说明             |
| ------------------------------------------------------------- | ---------------- |
| [db-query-optimization.md](performance/db-query-optimization.md) | 数据库查询优化   |
| [query-optimization-examples.md](performance/query-optimization-examples.md) | 查询优化示例     |
| [redis-cache-analysis.md](performance/redis-cache-analysis.md) | Redis 缓存分析   |
| [structured-logging-config.md](performance/structured-logging-config.md) | 结构化日志配置   |
| [sentry-integration-plan.md](performance/sentry-integration-plan.md) | Sentry 集成计划  |

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

## Superpowers 工作流

### 设计规格 (specs)
- [2026-04-01-customer-platform-design.md](superpowers/specs/2026-04-01-customer-platform-design.md) - 客户运营中台系统设计
- [2026-04-01-customer-platform-implementation-plan.md](superpowers/specs/2026-04-01-customer-platform-implementation-plan.md) - 实现计划
- [2026-04-03-customer-groups-design.md](superpowers/specs/2026-04-03-customer-groups-design.md) - 客户分组设计
- [2026-04-06-frontend-redesign.md](superpowers/specs/2026-04-06-frontend-redesign.md) - 前端重设计规格
- [2026-04-12-customer-detail-redesign.md](superpowers/specs/2026-04-12-customer-detail-redesign.md) - 客户详情重设计规格

### 实现计划 (plans)
- [2026-04-01-phase0-backend-initialization.md](superpowers/plans/2026-04-01-phase0-backend-initialization.md) - Phase 0 后端初始化
- [2026-04-02-permission-checker-implementation.md](superpowers/plans/2026-04-02-permission-checker-implementation.md) - 权限检查器实现
- [2026-04-03-customer-groups-implementation.md](superpowers/plans/2026-04-03-customer-groups-implementation.md) - 客户分组实现
- [2026-04-07-ux-ui-improvements.md](superpowers/plans/2026-04-07-ux-ui-improvements.md) - UX/UI 改进
- [2026-04-09-customer-management-optimization.md](superpowers/plans/2026-04-09-customer-management-optimization.md) - 客户管理优化
- [2026-04-12-customer-detail-redesign.md](superpowers/plans/2026-04-12-customer-detail-redesign.md) - 客户详情重设计

---

## 文档规范

- **设计规格** → `superpowers/specs/`
- **实现计划** → `superpowers/plans/`
- **测试计划** → `testing/plans/`
- **测试报告** → `testing/reports/`
- **性能/优化** → `performance/`
- **开发指南** → `guides/`
