# 运行期技术债修复：logger 误用、错误提示、导入校验与无效补建

## Goal

修复本次导入导出开发过程中核实出的 5 项运行期/契约缺陷。每项均已完成代码定位与实验验证（证据见下），修复后不改变任何正常业务行为。

## 背景与核实证据

| # | 问题 | 核实手段 | 实测证据 |
|---|------|---------|---------|
| P1 | middleware 误用 `app.logger`（Sanic 无此属性） | 运行实验 + 代码定位 | `hasattr(Sanic,'logger')=False`；request 中间件抛错时客户端收到 **HTML 500**；共 5 处：`auth.py:65,82,91,163` + `audit.py:156` |
| P2 | 前端 axios 未解析 Blob 错误体 | 浏览器实测 | 空数据导出提示 `Bad Request`（英文），后端实为 `40002 没有找到符合条件的余额数据` |
| P3 | 计费规则导入缺字段校验 | 实测导入 | `device_type`/`layer_type` 留空的 fixed 规则导入返回 `success_count: 1`，库中 `device_type=None` |
| P4 | 文档引用已废弃权限码 | grep | `docs/specs/balance-import-prd.md` 8 处 `billing:import` |
| P5 | 余额惰性补建逻辑无效 | DB 行数对比 + 根因定位 | 新建客户只调导出 → balance 行数仍 0（`main.py:85-87` 只 `close()` 无 `commit`）；列表返回 `total=0` 却带 1 行 |

## Requirements

### REQ-1 middleware logger 误用（P1）

- REQ-1.1 `backend/app/middleware/auth.py`：新增 `import logging` 与模块级 `logger = logging.getLogger(__name__)`，将 4 处 `app.logger.<level>(...)` 改为 `logger.<level>(...)`。
- REQ-1.2 `backend/app/middleware/audit.py:156`：改用该文件已存在的模块级 `logger`。
- REQ-1.3 移除上述 5 处随之失效的 `# pyright: ignore[reportAttributeAccessIssue]` 抑制注释。
- REQ-1.4 认证中间件兜底 except（`auth.py:91`）在触发时必须返回约定 JSON（`ErrorCodes.INTERNAL_ERROR` / status 500），而非 Sanic 默认 HTML 错误页。

### REQ-2 前端解析 Blob 错误体（P2）

- REQ-2.1 `frontend/src/api/index.ts` 响应拦截器错误分支：当 `error.response.data instanceof Blob` 时，先 `await data.text()` 再 `JSON.parse`，从结果中提取 `message` 与 `code`。
- REQ-2.2 解析失败或响应体非 Blob 时，保持现有回退语义（`statusText` / `status * 100`），错误分类仍经 `getErrorCategory`。
- REQ-2.3 修复需覆盖全部下载链路（客户/余额/计费规则/包年套餐/结算单导出与各模板下载），不新增调用方改动。

### REQ-3 计费规则导入字段校验（P3）

- REQ-3.1 `backend/app/routes/billing/pricing.py` 的 `import_pricing_rules`：当行内 `pricing_type != "package"` 时，`device_type` 与 `layer_type` 均为必填，缺失时记为该行的行级错误（不影响其他行）。
- REQ-3.2 校验口径与 UI 表单一致（`PricingRuleModal.vue` 的设备类型/楼层类型均为 `required`）。
- REQ-3.3 模板生成端（`/pricing-rules/import-template`）与端点 docstring 中相应字段的「可选」表述改为「非包年必填」，避免模板契约与实现再次分叉。
- REQ-3.4 取值域校验：`device_type` ∈ {`X`,`N`,`L`}，`layer_type` ∈ {`single`,`multi`,`single_and_multi`}；非法值记为行级错误（与 UI 下拉选项一致）。

### REQ-4 文档旧权限码（P4）

- REQ-4.1 `docs/specs/balance-import-prd.md` 中 8 处 `billing:import` 更新为 `billing:balance_import`。
- REQ-4.2 文档内补充一句权限码迁移说明（`billing:import`/`billing:export` 已拆分为 8 个细粒度码）。

### REQ-5 删除无效惰性补建（P5）

- REQ-5.1 删除 `backend/app/routes/billing/balances.py` 中 `_query_balance_rows` 内的惰性补建块（`missing_stmt` 查询 + `db.add_all` + `db.flush` 及其 IntegrityError 分支）。
- REQ-5.2 列表（`GET /billing/balances`）与导出（`GET /billing/balances/export`）响应的 `total` 与 `list`/行数据必须一致；两个端点保持**只读**（无 INSERT/UPDATE）。
- REQ-5.3 提供一次性补偿 SQL（为历史缺失余额档案的客户建档），以脚本形式交付，不自动执行、不接入启动流程。
- REQ-5.4 删除后清理不再被引用的 import 与辅助变量，不遗留死代码。

## Acceptance Criteria

- [x] AC-1 `grep -rn "app\.logger" backend/app` 无匹配；`auth.py` 与 `audit.py` 均使用模块级 logger。
- [x] AC-2 request 中间件内异常时客户端收到 JSON 500（`code=50000`），不再是 HTML 错误页 —— 集成测试 `test_auth_middleware_exception_returns_json_500`（独立 app 注册真实中间件，令黑名单服务抛异常）。
- [x] AC-3 浏览器实测：空结果导出提示为后端中文消息「没有找到符合条件的余额数据」（修复前为英文 `Bad Request`）。
- [x] AC-4 导入缺/非法 `device_type`、`layer_type` 的行 → 行级错误且文案含字段名；同文件 `package` 行仍成功 —— `test_import_pricing_rules_requires_device_and_layer_for_non_package`（success 1 / error 4，四条校验分支全覆盖）。
- [x] AC-5 `docs/specs/` 下无使用性旧码引用（`billing:import` 仅出现在 balance-import-prd.md 头部迁移说明中）。**口径说明**：`docs/superpowers/` 下 3 个 2026-04 的冻结历史计划/设计档案仍含旧码名，属历史记录，本次不改写（Out of Scope）。
- [x] AC-6 `_query_balance_rows` 函数体内无 `add/add_all/flush/commit`；无余额档案客户调用列表时 `total == len(list) == 0` 且不产生写入 —— `test_balances_list_excludes_customer_without_archive`。
- [x] AC-7 后端相关套件 128 passed；健康测试集（`tests/unit/` + `tests/integration/`）**690 passed，覆盖率 51.47% ≥ 50%**；前端 `npm run type-check` 与 `npm run lint` 通过。
      **口径说明（既有问题，非本次引入）**：`pytest tests/`（全量，即 `make test-cov` 的命令）无法给出有效覆盖率 —— ① 同名测试文件跨目录冲突（根目录 `tests/test_analytics_service.py` vs `tests/unit/services/test_analytics_service.py`；`test_correlation_middleware.py` 在 `integration/` 与 `unit/` 各一份）导致 2 个 collection error（`import file mismatch`，pytest `prepend` 导入模式按 basename 注册模块）；② 根目录老测试引用已变更的模型字段（`Customer.scale_level`、`Customer.contact_person`、`PricingRule.name`）导致 34 failed + 3 errors。两者均与本次改动无关（`git status` 确认未触碰 `app/models/`、`alembic/`），已单独记录待处理。
- [x] AC-8 浏览器回归：五页面按钮就位、导出 200 + xlsx、导入弹窗与模板下载正常、部分成功导入（成功 1 / 失败 1）。

## Out of Scope

- 批量选择导出功能的实现（`Balance.vue` 中 `批量导出功能开发中` 占位，属既有 PRD 明确排除项）
- 认证/审计中间件的整体重构（仅修 logger 误用与错误响应形态）
- 数据库表结构或迁移变更
- `docs/specs/` 其他历史文档的全面梳理（仅处理确认存在旧权限码的 balance-import-prd.md）

## 关键决策记录

| ID | 决策 | 理由 | 确认 |
|----|------|------|------|
| D1 | 计费规则字段口径统一到「导入端加校验」 | 与 UI 表单 required 一致，堵住脏数据入口；放宽 UI 会引入同类脏数据 | 用户确认 2026-09-16 |
| D2 | 删除余额惰性补建逻辑（而非补 commit 使其生效） | 正常业务路径已自动建档（实测 API 创建客户即建 balance 行，`customers.py:576/1196` 覆盖单条与批量导入）；补 commit 会让 GET/导出写库 | 用户确认 2026-09-16 |
| D3 | 5 项一并修复并创建 Trellis 任务 | 问题关联同一批代码区域，统一验证成本更低 | 用户确认 2026-09-16 |
| D4 | P3 一并加字段取值域校验（非仅必填） | 必填只堵"缺失"，不堵"非法值"（如 `device_type="abc"`）；UI 为下拉，导入亦应约束值域 | 用户确认 2026-09-16 |

## Notes

- 修复不得改变正常业务行为：P1 仅换日志器、P2 仅失败路径、P3 仅新增行级校验、P5 删除的是被回滚的无效写入。
- 所有实测证据均在开发库（`customer_platform`）构造并已清理，无残留脏数据。
