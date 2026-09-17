# 实施计划

## 有序实施清单

### Phase 1：后端 middleware logger（P1，无行为变更）

1. `backend/app/middleware/auth.py`
   - 顶部新增 `import logging` 与 `logger = logging.getLogger(__name__)`（放在既有 import 区块内，与其他 middleware 文件一致）
   - 65 行：`app.logger.warning(f"Token verification failed: {e}")` → `logger.warning("Token verification failed: %s", e)`
   - 82 行：`app.logger.info(f"Blacklisted token used: {jti}")` → `logger.info("Blacklisted token used: %s", jti)`
   - 91 行：`app.logger.error(f"认证中间件异常：{e}")` → `logger.error("认证中间件异常：%s", e, exc_info=True)`
   - 163 行：`app.logger.warning(f"Failed to update last_used_at for API-Key {api_key.id}")` → `logger.warning("Failed to update last_used_at for API-Key %s", api_key.id)`
   - 移除 4 处 `# pyright: ignore[reportAttributeAccessIssue]`
2. `backend/app/middleware/audit.py`
   - 156 行：`app.logger.error(f"Audit log failed: {e}")` → `logger.error("Audit log failed: %s", e, exc_info=True)`（该文件 22 行已有模块级 logger）
   - 移除该行 `# pyright: ignore[...]`

### Phase 2：前端 Blob 错误体（P2，仅失败路径）

3. `frontend/src/api/index.ts` 响应拦截器错误分支（现 162-172 行）
   - 按 design 中给出的实现替换错误信息提取逻辑：`Blob` 分支 `await data.text()` + `JSON.parse`；非 Blob 分支保持原语义
   - 保持 `getErrorCategory(typeof code === 'number' ? code : 50000)` 与 reject 结构不变

### Phase 3：计费规则导入校验（P3，唯一行为变更）

4. `backend/app/routes/billing/pricing.py`
   - `import_pricing_rules` 行循环内、`package_type` 必填校验之后，插入「非包年结算：device_type / layer_type 必填」行级校验（复用已解析的 `device_type` / `layer_type` 变量）
   - 更新同函数 docstring 中 `device_type (可选)` / `layer_type (可选)` 的表述为「非包年必填」
   - 更新 `pricing_rules_import_template` 生成的第 2 行说明文案：`可选：X/N/L` → `非包年必填：X/N/L`；`可选：single/multi` → `非包年必填：single/multi`
   - （待用户确认）若纳入值域校验：追加 `device_type ∈ {X,N,L}`、`layer_type ∈ {single,multi,single_and_multi}` 校验

### Phase 4：文档旧权限码（P4）

5. `docs/specs/balance-import-prd.md`
   - 8 处 `billing:import` → `billing:balance_import`（正文、mermaid 流程图、验收清单、决策表、术语表）
   - 文档头部补充权限码迁移说明

### Phase 5：删除无效惰性补建（P5）

6. `backend/app/routes/billing/balances.py`
   - 删除 `_query_balance_rows` 内 421-445 行补建块（注释 + `missing_stmt` + `missing_ids` + `db.add_all` + `flush` + `IntegrityError` 分支 + `logger.info`）
   - 删除第 10 行 `from sqlalchemy.exc import IntegrityError`（核实为唯一使用点）
   - 保留 `logger` 与 `CustomerBalance` import（其他位置仍在用）
7. 新增 `backend/scripts/backfill_balance_archives.sql`（一次性补偿脚本，人工执行，不接入启动流程）

### Phase 6：测试与验证

8. 后端集成测试（`backend/tests/integration/`）
   - 认证中间件异常 → JSON 500 且 `code == 50000`（monkeypatch `TokenBlacklistService.is_blacklisted`）
   - 计费规则导入：非包年缺 `device_type` → 行级错误（文案含「设备类型」）；同文件 `package` 行仍成功
   - 余额列表 `total` 与 `list` 长度一致，且调用后不为缺失档案客户建档（证明无写操作）
   - 模板回灌：下载模板 → 填写 → 导入仍正常（回归 F1 修复）
9. 前端验证：`npm run type-check`、`npm run lint`；浏览器实测空数据导出提示为后端中文文案
10. 回归验证：五页面导入导出按钮、导出下载 200 + xlsx、模板下载 200 + xlsx、部分成功导入（成功 1 / 失败 1）
11. 规范更新：若产生新的可复用契约（如中间件错误响应约定），追加到 `.trellis/spec/backend/` 对应文件

## 验证命令

```bash
# 后端定点测试
cd backend && .venv/bin/python -m pytest tests/integration/test_billing_import_export_api.py -q --no-cov
# 后端相关套件（认证 + billing + 客户）
cd backend && .venv/bin/python -m pytest tests/integration/test_auth_api.py tests/integration/test_billing_api.py tests/integration/test_customers_api.py -q --no-cov
# 全量覆盖率（CI 门槛）
cd backend && .venv/bin/python -m pytest tests/ -q --cov=app --cov-report=term --cov-fail-under=50
# 前端
cd frontend && npm run type-check && npm run lint

# AC 静态校验
grep -rn "app\.logger" backend/app            # 期望无输出
grep -rn "billing:import\|billing:export" docs/  # 期望无输出
```

## 风险文件 / 回滚点

| 文件 | 风险 | 回滚 |
|------|------|------|
| `backend/app/middleware/auth.py` | 认证路径改动（仅日志器） | git revert 单文件 |
| `backend/app/middleware/audit.py` | 审计失败日志格式 | git revert 单文件 |
| `frontend/src/api/index.ts` | 全局错误提示（仅失败分支） | git revert 单文件 |
| `backend/app/routes/billing/pricing.py` | 导入行为变更（新增行级校验） | git revert 单文件 |
| `backend/app/routes/billing/balances.py` | 删除补建（本就无效） | git revert 单文件 + 执行补偿 SQL |
| `docs/specs/balance-import-prd.md` | 文档 | git revert 单文件 |

## task.py start 前检查

- [ ] prd.md 需求与验收完整（REQ-1..5 / AC-1..8）
- [ ] design.md 覆盖全部修复点的文件:行号与改法
- [ ] 唯一行为变更（P3）已在 PRD 中明示并有回归验证项
- [ ] 补偿 SQL 明确不自动执行
- [ ] 所有实测证据已清理，开发库无残留脏数据
