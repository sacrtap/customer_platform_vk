# 性能优化文档

> 本目录收录数据库查询优化、缓存策略、监控集成、测试优化等性能相关文档。
> 最后更新: 2026-04-27

---

## 文档列表

| 文件 | 说明 | 状态 |
| ---- | ---- | ---- |
| [db-query-optimization.md](db-query-optimization.md) | 数据库查询优化策略与最佳实践 | ✅ 完成 |
| [query-optimization-examples.md](query-optimization-examples.md) | 具体查询优化示例与对比 | ✅ 完成 |
| [redis-cache-analysis.md](redis-cache-analysis.md) | Redis 缓存使用分析与优化建议 | ✅ 完成 |
| [structured-logging-config.md](structured-logging-config.md) | 结构化日志配置指南 | ✅ 完成 |
| [sentry-integration-plan.md](sentry-integration-plan.md) | Sentry 错误监控集成计划 | 📋 计划中 |

---

## 快速参考

- **N+1 查询问题** → 查看 `db-query-optimization.md`
- **具体优化案例** → 查看 `query-optimization-examples.md`
- **缓存策略** → 查看 `redis-cache-analysis.md`
- **日志配置** → 查看 `structured-logging-config.md`
- **错误监控** → 查看 `sentry-integration-plan.md`

## 相关文档

- **测试优化指南** → [../guides/test-optimization-guide.md](../guides/test-optimization-guide.md)
  - 测试并行化配置
  - 增量测试（pytest-testmon）
  - Fixture 优化
  - CI 与开发环境分离
