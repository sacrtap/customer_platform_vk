# 执行计划：批量为 7 个管理页面新增导入/导出

## Phase A：共享基建（主会话，串行，无并行冲突）

- [ ] A1. `backend/app/utils/excel_export.py`（新建，见 design.md 2.2；实现前读 `routes/billing/balances.py:1020-1040` 的 X-Truncated 先例与 customers.py:1550-1666 的空数据处理）
- [ ] A2. `backend/app/utils/excel_template.py`（新建，见 design.md 2.3）
- [ ] A3. `frontend/src/api/_excel.ts`（新建）+ `billing.ts` 改造（删本地定义 :11/:18-22/:25-27，import + re-export `importFile`/`fetchImportTemplate`/`fetchExport`）
- [ ] A4. 权限码四处同步：
  - A4a. `scripts/seed.py` ALL_PERMISSIONS 追加 13 条（module 见 design.md 2.5）
  - A4b. `tests/_test_data.py` PERMISSION_ROWS 追加 13 条（3 元组）
  - A4c. `tests/integration/conftest.py` 权限注册列表 + FULL_PERMISSIONS（先读文件确认结构）
  - A4d. `scripts/fix_add_import_export_permissions.py`（新建，仿 fix_add_view_all_permission.py；从 seed import ALL_PERMISSIONS 过滤 `_import`/`_export` 后缀）
  - A4e. `frontend/src/views/roles/permissionGroups.ts` 补 MODULE_NAME_MAP + MODULE_ORDER
- [ ] A5. 跑 `pytest tests/unit/test_test_data_consistency.py` 确认权限一致性（阻塞后续）

## Phase B：7 个页面实现（并行子代理，每页独立文件集）

每页交付物 = 后端路由端点 + 前端页面接线 + api 模块函数；契约见 design.md §2.1/§2.4/§3。

- [ ] B1. 行业类型：`routes/industry_type_routes.py` + `views/system/IndustryTypes.vue` + `api/industryTypes.ts`
- [ ] B2. 合作状态：`routes/cooperation_status_routes.py` + `views/system/CooperationStatuses.vue` + `api/cooperationStatuses.ts`
- [ ] B3. 标签：`routes/tags.py` + `views/tags/Index.vue` + `api/tags.ts`
- [ ] B4. 用户（legacy 重写，最复杂）：`routes/users.py` POST /import 重写 + GET /export + GET /import-template + `views/users/Index.vue` + `api/users.ts` + **改写 `tests/unit/test_user_import.py`**
- [ ] B5. 角色权限：`routes/roles.py` + `views/roles/Index.vue` + `api/roles.ts`
- [ ] B6. 余额白名单：`routes/balance_whitelist_routes.py` + `views/system/BalanceWhitelist.vue` + `api/balanceWhitelist.ts`
- [ ] B7. API-Key（仅导出）：`routes/api_keys.py` + `views/system/ApiKeyManagement.vue` + `api/apiKeys.ts`

## Phase C：测试与验证

- [ ] C1. 集成测试 `tests/integration/test_admin_import_export_api.py`（新建）：覆盖 6 导入端点 + 7 导出端点的——成功导入/落库、dry_run 不落库、重复行级错误、模板 3 行结构与说明行剥离、必填列缺失 40003、无权限 403、导出行数与列名、X-Truncated 头（对齐 import-export.md「Tests Required」）
- [ ] C2. 逐页 smoke 脚本（登录→模板→dry_run→正式→重复→导出→清理），先跑行业类型样板再复用
- [ ] C3. `pytest tests/unit/test_user_import.py` 通过
- [ ] C4. 后端全量回归 `pytest --cov-fail-under=50`
- [ ] C5. 前端 `npm run typecheck` + `npm run test`
- [ ] C6. 前端 UI 手动验证（dev server + 超管登录，7 页按钮/弹窗/导出下载，API-Key 无导入按钮）

## Phase D：收尾

- [ ] D1. 更新 `.trellis/spec/backend/import-export.md`（端点清单、权限码清单、新踩坑：嵌套事务/软删查重/X-Truncated total）
- [ ] D2. 按逻辑改动拆分 commit（基建 / 权限 / 每页 / 测试）
- [ ] D3. 本文件末尾写「验收边界 + 最终验证结果」
- [ ] D4. `task.py archive`

## 验证命令速查

```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_test_data_consistency.py -v
.venv/bin/python -m pytest tests/unit/test_user_import.py -v
.venv/bin/python -m pytest --cov-fail-under=50
.venv/bin/python -m scripts.fix_add_import_export_permissions   # 存量库补权限（幂等）
cd ../frontend
npm run typecheck && npm run test
```

## Rollback points

- A 阶段完成即一个可回滚点（纯新增基建，不影响现有端点）。
- 每页 B 完成后独立可验证；B4（users 重写）是唯一破坏性变更，失败可单独 revert 该 commit。
