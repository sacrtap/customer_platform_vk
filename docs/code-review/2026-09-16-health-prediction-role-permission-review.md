# 代码审查报告 — 健康度/预测消费修复 + 角色权限修正 + 部署加固

**日期**: 2026-09-16
**工具**: open-code-review (`ocr`) v1.12.3
**范围**: `main..fix/health-prediction-bugs`（17 个代码文件，+671/-61）
**审查方式**: `ocr review --audience agent --from main --to HEAD`
**LLM**: 经 retry 恢复 48 次（原 49/137 请求受影响，1 次未恢复）
**发现问题**: 0 严重、0 高、4 中、3 低（共 7 条）
**已修复**: 7/7（全部修复，其中修复 1 引发测试适配已一并处理）

---

## 审查文件清单

- `backend/app/routes/analytics.py`
- `backend/app/routes/billing/invoices.py`
- `backend/app/services/analytics.py`
- `backend/app/models/__init__.py`
- `backend/alembic/versions/t9u0v1w2x3y4_add_forecast_unit_prices_table.py`
- `backend/scripts/cleanup_deprecated_permissions.py`
- `backend/scripts/seed.py`
- `backend/tests/integration/conftest.py`
- `backend/tests/unit/services/test_analytics_service.py`
- `deploy/docker-compose.yml`
- `deploy/scripts/deploy.sh`
- `frontend/src/composables/useAppLayout.ts`
- `frontend/src/views/billing/Balance.vue`
- `frontend/src/views/billing/Invoices.vue`
- `frontend/src/views/roles/permissionGroups.ts`

## 发现与修复明细

### Medium（4 条，全部修复）

1. **`backend/app/services/analytics.py:1940`** [bug] — `get_unit_prices` 的 `except Exception` 捕获范围远超注释所述"表缺失"场景，连接失败/权限错误等会被静默吞掉返回默认值，生产难以排查。
   - ✅ 修复：缩窄为 `sqlalchemy.exc.ProgrammingError`（覆盖表不存在场景），并新增模块级 `logger`，回退时记录 `logger.warning(...)` 实际异常。

2. **`frontend/src/composables/useAppLayout.ts`** [maintainability] — `database-management`（数据清空）被放在 `tools` 分组，但实际侧边栏组件 `AppSidebar.vue` 将「数据清空」归在「系统管理」分组，watch handler 也将 `/system/database-management` 归入 system 分支，三处数据不一致。
   - ✅ 修复：将 `database-management` 从 `tools` 分组移至 `system` 分组（erp-systems、api-keys 之后），与 `AppSidebar.vue` 实际分组一致。

3. **`frontend/src/composables/useAppLayout.ts:205-207`** [maintainability] — `isSubmenuActive('system')` 新增了 `/system/erp-systems` 与 `/system/api-keys`，但遗漏了同样属于系统管理分组的 `/system/database-management`，与 watch handler 分类不一致（导航时父菜单不高亮）。
   - ✅ 修复：`isSubmenuActive('system')` 分支补充 `p === '/system/database-management'`。

4. **`backend/alembic/versions/t9u0v1w2x3y4_add_forecast_unit_prices_table.py:45-51`** [bug] — 迁移创建了 `created_at` 列，但 `ForecastUnitPrice` 模型继承 `Base`，未定义 `created_at`，ORM 与 DB schema 不一致（ORM 插入后访问 `obj.created_at` 抛 `AttributeError`）。
   - ✅ 修复：`backend/app/models/forecast_config.py` 模型补充 `created_at = Column(DateTime, server_default=func.now(), nullable=False)`。

### Low（3 条，全部修复）

5. **`backend/app/routes/billing/invoices.py:1334`** [maintainability] — `from sanic.response import raw` 放在函数体内，而文件顶部已导入 `file`/`json`，应统一为顶部导入。
   - ✅ 修复：合并到顶部导入区 `from sanic.response import json, raw`，删除函数内行内导入。

6. **`backend/tests/unit/services/test_analytics_service.py:128`** [test] — 两处兜底测试硬编码 `{"L": 14.5, "N": 30.0, "X": 30.0}`，config.py 默认值变更后测试易过时且报错不直观。
   - ✅ 修复：改为从 `app.config.get_settings().consumption_forecast_unit_prices` 动态导入断言；同时将 `side_effect` 从 `Exception` 调整为 `ProgrammingError`（配合修复 1 的异常缩窄）。

7. **`backend/alembic/versions/t9u0v1w2x3y4_add_forecast_unit_prices_table.py:52-58`** [maintainability] — `updated_at` 迁移声明 `nullable=False`，但模型未显式指定 `nullable`（SQLAlchemy 默认 `True`），认知不一致。
   - ✅ 修复：模型中 `updated_at` 显式添加 `nullable=False`。

## 验证

- 后端单元测试：447 passed（含 `test_analytics_service.py` 6 项，适配 `ProgrammingError` 后通过）
- 前端测试：89 passed
- 前端构建：`vue-tsc` + vite 通过（chunk 大小警告为既有问题，非本次引入）
- ruff lint/format：全部通过

## 备注

- LLM 审查期间 49/137 请求受 provider/限流影响，48 次经重试恢复，1 次未恢复（不影响结果，规划阶段单个文件组）
- 审查范围含 `.trellis/tasks/archive/**/task.json` 2 个元数据文件（本次无对应问题）
