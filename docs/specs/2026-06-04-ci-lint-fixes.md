# CI lint 失败修复与本地/pre-commit 检查对齐

> 归档来源：`.omo/plans/fix-ci-failures.md`、`.omo/plans/ci-eslint-any-fix.md`（2026-11-19 蒸馏合并，原件已删除）
> 状态：已落地 —— `.pre-commit-config.yaml` 已有 `eslint` 本地 hook（`files: ^frontend/(src|tests)/`）；`frontend/env.d.ts` 现为 `DefineComponent<object, object, unknown>`；`BatchFailedItem` 现位于 `frontend/src/views/customers/components/CustomerBatchEditModal.vue`
> 锚点说明：文中 `文件:行号` 为 2026-06-04 期快照，定位以符号名与路径为准

## Context

两起 CI 失败，根因不同但同属"静态检查"类：

**① CI Run `#26412452696` 两个 job 失败**：

- Frontend Quick Check / ESLint：`frontend/env.d.ts:5` — `@typescript-eslint/ban-types`（`{}` 作类型）×2 + `@typescript-eslint/no-explicit-any`（`any`）×1
- Backend Quick Check / Ruff Format：`app/services/analytics.py` — `Would reformat: app/services/analytics.py`

修法：`DefineComponent<{}, {}, any>` → `DefineComponent<object, object, unknown>`（Vue 默认模板写法）；`ruff format` 自动格式化，零逻辑变更。

**② 批量编辑结果处理的 `any`**：`Index.vue` 批量编辑 `submitBatchUpdate` 处理 `failed_list` 时用 `(item: any)` 触发 `no-explicit-any`。根因是 `failed_list` 元素无类型——后端返回 `list[dict]`（`customer_id: int`、`reason: str`）。修法：定义 `BatchFailedItem` 接口（`customer_id: number`、`reason: string`）替换 `any`。

**③ 本地与 CI 检查项不一致**：

| 检查项 | CI (ci.yml) | pre-commit-check.sh | 缺失? |
|--------|:-----------:|:-------------------:|:-----:|
| ruff check | ✅ | ✅ | - |
| ruff format | ✅ | ✅ | - |
| pytest unit | ✅ | ✅ | - |
| **ESLint** | ✅ npm run lint | ❌ | **是** |
| vue-tsc | ✅ | ✅ | - |
| npm run build | ✅ | ✅ | - |
| npm audit | - | ✅ (非阻断) | - |
| safety check | - | ✅ (非阻断) | - |

**结论：pre-commit 缺 ESLint → 本地过、CI 挂。** 修复：pre-commit 前端检查段加入 `npm run lint -- --max-warnings 0`（步骤编号 [1/3]-[3/3] → [1/4]-[4/4]）。该 hook 现已固化为 `.pre-commit-config.yaml` 的 `eslint`（`files: ^frontend/(src|tests)/`）。

## Approach

护栏（三轮均遵守）：不改 ESLint/ruff 配置绕过问题；不引入 `as any` / `@ts-ignore`；不动业务逻辑。

1. `frontend/env.d.ts`：`{}` → `object`、`any` → `unknown`
2. `backend/app/services/analytics.py`：`ruff format` 自动格式化
3. `Index.vue`：新增 `BatchFailedItem` 接口，`(item: any)` → `(item: BatchFailedItem)`（组件重构后该类型随 `CustomerBatchEditModal.vue` 落位）
4. `scripts/pre-commit-check.sh`：补 ESLint 步骤，编号改 4 步

## Critical files & anchors

- `frontend/env.d.ts` — Vue 组件类型声明三处泛型
- `backend/app/services/analytics.py` — ruff format 目标文件
- `frontend/src/views/customers/`（原 `Index.vue`）— `BatchFailedItem` 定义与 `failed_list` map 回调
- `scripts/pre-commit-check.sh` / `.pre-commit-config.yaml` — ESLint 检查入口

## Verification

- `cd frontend && npm run lint` → 0 errors / 0 warnings
- `cd backend && ruff format --check app/ tests/` → 全部 already formatted
- `pre-commit run --all-files` → 退出码 0，全部检查通过
- CI 重跑通过（push 后 GitHub Actions 绿）

## Assumptions

- `BatchFailedItem` 字段以后端 `batch_update_customers` 返回契为准（`customer_id` / `reason`），见 `docs/specs/2026-06-02-customer-batch-edit-plan.md`。
- ESLint 进 pre-commit 用 `--max-warnings 0`，与 CI 口径一致。
