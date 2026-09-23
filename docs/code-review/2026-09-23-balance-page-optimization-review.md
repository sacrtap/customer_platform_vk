# 代码审查报告 — 余额管理页功能优化（工作区改动）

**日期**: 2026-09-23
**工具**: open-code-review (`ocr`) v1.12.7
**范围**: 工作区未提交改动（15 个修改文件 + 1 个新增文件，+1049/-379；审查选中 7 个核心代码文件）
**LLM**: bifrost 网关（经 ocr 配置）。初选 `deepseek-v4-pro` 连续 3 轮被网关限流（HTTP 429）/超时（HTTP 504）全组失败；改用 `deepseek-v4-flash --concurrency 1` 后跑通（29m57s，约 180 万 token）
**审查耗时**: 约 30 分钟（含限流导致的 3 次失败重试，约 80 分钟）
**发现问题**: 0 个严重、1 个高、1 个中、1 个低
**已修复**: 3/3（全部属实，均已修复并实测验证）

---

## 审查文件清单

### 后端（2 个文件）
- `backend/app/routes/billing/balances.py`
- `backend/tests/integration/test_billing_api.py`

### 前端（5 个文件）
- `frontend/src/views/billing/Balance.vue`
- `frontend/src/views/billing/components/BalanceFilters.vue`
- `frontend/src/views/billing/components/BalanceTable.vue`
- `frontend/src/composables/useBalance.ts`
- `frontend/src/api/billing.ts`

> 未纳入 LLM 审查的改动：测试与 E2E/文档（`useBalance.test.ts`、`BalanceTable.test.ts`、`test_visual_regression.spec.ts` 及基线 PNG、`.trellis/spec/**`）。

---

## 业务背景

余额管理页两轮功能优化（客户运营中台，Sanic + SQLAlchemy 2.0 + Vue 3 + Arco Design）：

1. **第一轮 — 口径拆分与视觉修复**：
   - KPI 统计按结算类型拆分：新增 `total_balance_prepaid`/`prepaid_customers`/`total_balance_postpaid`/`postpaid_customers`/`postpaid_receivable`（应收款 = 后付费余额合计相反数）；**未设置结算类型的客户归入预付费**（`coalesce(settlement_type,'prepaid') != 'postpaid'`）
   - 移除「零余额客户」卡片；「余额不足」「即将耗尽」口径修正为**仅统计预付费**
   - `balance-stats` 响应字段重构（删除 `total_balance`/`total_customers`/`zero_balance_count`）；余额列表新增 `settlement_group` 分组筛选参数
   - 操作列 `position: sticky` 防裁切；零余额不标红、负余额加「欠费」标签；「更新」改「重算」；删除未实现的批量操作（含 `BalanceBatchToolbar.vue`）

2. **第二轮 — 筛选对齐与默认视图修复**：
   - 筛选区参照客户管理页重构：首行（搜索/账号类型/行业/结算类型/余额范围/运营经理/销售经理）+ 右侧按钮组（更多▾/筛选）+ 第二行折叠更多（是否结算/是否重点客户/是否房产客户/标签）
   - 后端 `_parse_balance_filters` 与 `get_balance_stats` 新增 `is_settlement_enabled` 过滤
   - 默认行业从固定 3 项改为全部（对齐客户管理页，修复默认视图为空）
   - 客户ID 列去掉 `customer_id` 回退，与客户管理页取值一致

---

## 问题与修复

### 严重（0 个）

无。

### 高（1 个）

#### 1. 运营经理/销售经理下拉选项 label 恒为空

- **文件**: `frontend/src/views/billing/components/BalanceFilters.vue:174-180`
- **类型**: bug
- **描述**: `managerOptions`/`salesOptions` 用 `m.name` 取用户姓名，但 `getManagers()`（GET /users）返回的 `User` 类型只有 `real_name` 字段、**没有 `name`**（`src/types/index.ts:55`）。运行时 `m.name` 为 `undefined` → 下拉所有选项 label 都是空字符串，仅剩「全部」占位。客户管理页 `CustomerFilters.vue:199-202` 的正确写法是 `label: m.real_name || \`#${m.id}\``。
- **修复**: 改为 `label: String(m.real_name ?? m.id)`（经理无 `real_name` 时回退显示 `#id`，与客户管理页语义一致）。
- **状态**: 已修复（浏览器实测下拉显示「谭世涛 / 郭富乾 / 系统管理员」）

### 中（1 个）

#### 2. 「余额不足」KPI 点击后列表与卡片口径不一致

- **文件**: `frontend/src/views/billing/Balance.vue:219-224`
- **类型**: bug
- **描述**: 后端 `low_balance_count` 已改为**仅统计预付费客户**（后付费欠款属应收款），但点击「余额不足」卡片只设置 `filters.balance_range='low'`（`min=null` 含负余额），列表仍会包含后付费欠款客户 → 列表条数多于卡片数字，口径不一致。
- **修复**: `applyKpiFilter('low')` 分支同时设置 `filters.settlement_group = 'prepaid'`（并清空 `settlement_type`），列表与卡片共用同一「仅预付费 + 余额<1万」口径。
- **状态**: 已修复（浏览器实测：卡片 22 → 点击后列表 22 条、后付费行 0）

### 低（1 个）

#### 3. 「加载中...」行 colspan 与表头错位

- **文件**: `frontend/src/views/billing/components/BalanceTable.vue:107`
- **类型**: other（布局）
- **描述**: 删除表格复选框列后，空态行 colspan 已改 `columns.length + 1`，但「加载中...」行仍是 `columns.length + 2`（当前实际列数 = columns + 1），加载态单元格多占一列、与表头错位。
- **修复**: `columns.length + 2` → `columns.length + 1`。
- **状态**: 已修复

---

## 汇总

| 严重程度 | 数量 | 属实 | 已修复 | 误报 |
|----------|------|------|--------|------|
| 严重 | 0 | 0 | 0 | 0 |
| 高 | 1 | 1 | 1 | 0 |
| 中 | 1 | 1 | 1 | 0 |
| 低 | 1 | 1 | 1 | 0 |
| **合计** | **3** | **3** | **3** | **0** |

3 个问题全部属实并已修复。

## 验证

- 后端：`pytest tests/integration/test_billing_api.py` 全量 → 54 个用例全部通过（本审查不改后端，仅复核）
- 前端：`vue-tsc --noEmit` 通过；`vitest run`（useBalance 29 + BalanceTable 12）41 个用例全部通过；`eslint` 无问题
- 浏览器实测（localhost:5173 + 本地开发库）：
  - 「运营经理」下拉展开显示真实姓名（修复前为空 label）
  - 点击「余额不足」KPI → 徽标「余额不足 ✕」、列表 22 条、无后付费行，与卡片数字一致（修复前含后付费欠款客户）
  - 「加载中...」行 colspan 修正后与表头对齐

## 附注：审查过程限流处理

bifrost 网关对 ocr 的批量请求持续限流（HTTP 429）与网关超时（HTTP 504）。尝试路径：默认并发 8 → `--effort low --concurrency 2` → `--concurrency 1` 均失败（planning/core 阶段被 429/504 重试耗尽）；最终 `--model deepseek-v4-flash --concurrency 1 --effort low` 跑通。此过程消耗约 305 万 token（多数为失败重试）。
