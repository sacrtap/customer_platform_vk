# Implement：客户「自动发起结算」

## 实施步骤

1. **后端模型/迁移**：`customers.py` 加字段；`alembic revision` 生成骨架并修复模板 `Union` 导入缺失（`script.py.mako` 产物），填充 `op.add_column`。
2. **Service**：`create_customer` 默认 True；`update_customer` updatable_fields；`get_all_customers` 筛选（NULL=是兼容）；`batch_update_customers` 白名单。
3. **Routes**：list/export 布尔参数解析（`replace_all` 一次改两处同构块）；列表项、详情、导出列序列化。
4. **测试**：单元（默认值断言用 `add.call_args_list[0][0][0]` 取真实对象——mock flush 替换对象无法验证默认值；筛选 SQL 片段断言）；集成（POST/PUT/GET 真实 DB，`force_refresh=true` 避开列表缓存）。
5. **测试库补列**：integration/e2e conftest 的 `create_all` 不修改已有表，补 `ALTER TABLE`（与 `is_real_estate` 既有模式一致）。
6. **前端**：类型/API/筛选/表单/详情展示/批量编辑全链路。
7. **沉淀**：database-guidelines.md 追加 NULL 语义；本任务 prd/design/implement。

## 验证结果

| 验证 | 命令 | 结果 |
|---|---|---|
| 单元测试 | `pytest tests/unit/test_customer_service.py --no-cov -p no:cacheprovider -p no:testmon` | 28 passed |
| 集成测试 | `pytest tests/integration/test_customers_api.py --no-cov -p no:cacheprovider -p no:testmon` | 54 passed |
| 前端类型 | `npm run type-check`（vue-tsc --noEmit） | 0 errors |
| 前端构建 | `npm run build` | 成功（11.6s） |

> 注意：e2e 与 integration 共用同一测试库，分层套件必须串行执行（项目既有约定）。

## 验收边界

- 目标：客户新增/编辑表单 + 列表筛选支持「自动发起结算」（默认是/全部），后端全链路持久化与 NULL 兼容。
- 涉及文件：后端模型/迁移/服务/路由/测试 + 前端类型/API/组合式/4 个组件 + 2 个测试 conftest + `.trellis/spec` 与任务文档。
- 未覆盖：Excel 导入/导出模板、结算引擎消费逻辑（属性仅存储与展示，消费方后续接入）。
