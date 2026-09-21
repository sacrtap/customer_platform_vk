# Implement — 批量编辑弹框新增行业与 ERP 编辑项

## 步骤

1. **扩展 `CustomerBatchEditModal.vue`**
   - import：`getIndustryTypes`（`@/api/customers`）、`getErpSystemsList`（`@/api/erpSystems`）、类型 `IndustryType`/`ErpSystem`（`@/types`）
   - props 新增 `industryTypes?` / `erpSystems?`；`onMounted` 增加字典兜底加载
   - `batchForm` / `batchFieldsSelected` / `fieldNames` / `resetForm` 同步扩展
   - template 追加「行业类型」「ERP 系统」两个编辑项（checkbox + select，`allow-clear`）

2. **接线 `Index.vue`**：`CustomerBatchEditModal` 传 `:industry-types` / `:erp-systems`

3. **验证**
   - 前端类型检查：`frontend` 的 vue-tsc / lint（按仓库命令，见 Makefile）
   - 后端回归：`backend/tests/unit/test_batch_update.py`
   - 浏览器实测（多选 → 批量编辑 → 勾选行业/ERP → 预览 → 提交 → 列表刷新）

4. **收尾**：spec 沉淀（如有）、提交

## 命令

- 后端单测：`cd backend && .venv/bin/python -m pytest tests/unit/test_batch_update.py -q`（pre-commit 环境用 `$BACKEND_DIR/.venv/bin/python`）
- 前端检查：见 `frontend/package.json` scripts（type-check / lint）
