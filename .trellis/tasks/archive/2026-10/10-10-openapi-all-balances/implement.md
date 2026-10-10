# 执行计划: 开放平台「获取所有客户余额」接口

## 步骤

1. **后端改造**（3 文件）
   - `backend/app/middleware/auth.py`: `OPENAPI_PREFIX` → `OPENAPI_PREFIXES` 元组，`authenticate()` 中 `startswith` 判断同步更新。
   - `backend/app/routes/openapi.py`: 抽取 `_build_customer_balance_stmt(erp_channel=None)`；新增 `openapi_customer_bp`（`url_prefix="/api/v1"`）+ `GET /balances` 路由；既有 `get_erp_balances` 改用公共构建函数（行为不变）。
   - `backend/app/main.py`: 注册 `openapi_customer_bp`。

2. **集成测试**（新增 `backend/tests/integration/test_openapi_api.py`）
   - fixture: API-Key（`ApiKeyService.create_key`）+ 多渠道/无 ERP/软删除/停用客户 + 余额数据。
   - 用例: 无 Key 401、无效 Key 401、全量成功（含无 ERP、balance 计算、排序）、排除软删除/停用、渠道接口回归。

3. **文档站**（openapi-docs/ 4 文件）
   - 新增 `docs/api-reference/all-balances.md`；更新 `index.md`、`.vitepress/config.ts` sidebar、`changelog.md`。

4. **验证**
   - `cd backend && source .venv/bin/activate && ruff check app/ tests/ && ruff format --check app/ tests/ && pyright`
   - `pytest tests/integration/test_openapi_api.py -v --tb=short`（新用例）
   - `pytest tests/integration/ -q --tb=short`（回归，串行）
   - `cd openapi-docs && npm run docs:build`（文档构建）
   - 冒烟: 测试客户端调用 `GET /api/v1/balances` 与 `GET /api/v1/erp/balances`，观察响应。

5. **收尾**
   - `git add` + 提交（feat: 开放平台新增全量客户余额接口与文档）
   - trellis: `task.py finish` 前的 spec 沉淀（如有新约定）、`add_session`。

## 验证命令速查

```bash
cd backend && source .venv/bin/activate
ruff check app/ tests/
pytest tests/integration/test_openapi_api.py -v --tb=short
cd ../openapi-docs && npm run docs:build
```

## 验收对照

- [ ] `GET /api/v1/balances` 有效 Key 返回全部有效客户（含无 ERP、无余额=0.0、company_id 升序）
- [ ] 软删除/停用客户被排除；无效/缺 Key 401（40104/40105）
- [ ] `/api/v1/erp/balances` 回归通过
- [ ] ruff / pyright / docs:build 通过；覆盖率口径 ≥50%
- [ ] 文档站索引/sidebar/changelog 已更新
