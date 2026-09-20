# 代码审查报告 — 客户管理页面功能优化（PR #28）

**日期**: 2026-09-21
**工具**: open-code-review (`ocr`) v1.12.5
**范围**: PR #28 合并提交 `origin/main^..origin/main`（38 个文件，+1134/-14，审查选中 18 个核心代码/测试文件）
**LLM**: bifrost 网关（qwen 系列，经 ocr 配置）
**审查耗时**: 约 9 分钟（首轮 4m51s + 核心文件补审 3m25s，含 429 限流重试）
**发现问题**: 0 个严重、0 个高、1 个中、4 个低
**已修复**: 4/5（4 个属实问题全部修复；1 个中等级别为误报）

---

## 审查文件清单

### 后端（4 个文件）
- `backend/app/services/customers.py`
- `backend/app/services/analytics.py`
- `backend/tests/unit/services/test_analytics_service.py`
- `backend/tests/unit/test_customer_service.py`

### 前端（10 个文件）
- `frontend/src/constants/customerOptions.ts`
- `frontend/src/api/analytics.ts`
- `frontend/src/api/customers.ts`
- `frontend/src/composables/useCustomerList.ts`
- `frontend/src/views/customers/Index.vue`
- `frontend/src/views/customers/components/CustomerFilters.vue`
- `frontend/src/views/customers/detail/CustomerProfileTab.vue`
- `frontend/src/views/customers/detail/EditCustomerDialog.vue`

### 说明
首轮审查 14 个文件产出 3 条评论，但 `analytics.py`、`CustomerProfileTab.vue`、`EditCustomerDialog.vue`、`api/analytics.ts` 4 个核心文件因 LLM 限流（HTTP 429）失败；已用 `--exclude` 聚焦重跑（并发 2、超时 30s）补齐，产出 2 条评论。两次结果合并共 5 条。

---

## 业务背景

PR #28 合并三个子任务（客户管理页面功能优化系列）：

1. **客户列表筛选增强** — 新增「是否结算」「是否停用」布尔筛选（后端 `list_customers`/`export_customers` 解析布尔参数，NULL 语义：`is_settlement_enabled` NULL=结算中、`is_disabled` NULL=未停用），前端 `CustomerFilters.vue` 新增 4 个 FilterDropdown（是否结算/是否重点客户/是否房产客户/是否停用）
2. **健康度评分排除规则** — `get_customer_health_score` 对不结算/客户测试账号/内部账号返回 `score=null` + `health_level=not_applicable`，前端 `CustomerProfileTab.vue` 显示「不参与评估」；顺带修复 `select(PricingRule)` 须 `.scalars().first()` 的既有 500 bug
3. **编辑弹窗 loading 居中** — `EditCustomerDialog.vue` a-spin 加载态图标居中修复（`.edit-dialog-spin.arco-spin-loading` 撑满 content-box）

技术栈：FastAPI + SQLAlchemy 2.0 + PostgreSQL 后端，Vue 3 + Arco Design 前端。

---

## 问题与修复

### 严重（0 个）

无。

### 高（0 个）

无。

### 中（1 个）

#### 1. 既有集成测试 mock 顺序未适配客户信息查询前置（误报，不修复）

- **文件**: `backend/tests/test_analytics_service.py`（OCR 报告路径）
- **类型**: test
- **描述**: OCR 认为新增的客户信息查询改变了 `db.execute` 调用顺序，既有 `TestGetCustomerHealthScore` 测试仍按「实际用量→定价规则→…」的固定 `side_effect` 顺序 mock，新代码首个 execute 会消费掉「实际用量」的 mock 结果，随后对 MagicMock 取 `float` 抛 TypeError。
- **核验结果**: **误报**。该测试类实际位于 `backend/tests/unit/services/test_analytics_service.py`（OCR 引用路径 `backend/tests/test_analytics_service.py` 不存在），且在实现阶段已同步更新：
  - `side_effect` 列表首项即为 `customer_result`（客户查询），与新增代码执行顺序一致；
  - 定价查询已 mock `pricing.scalars.return_value.first.return_value = None`（适配 `.scalars().first()` 新写法）；
  - 运行验证：`test_analytics_service.py` 11/11、`test_customer_service.py` 25/25 全部通过。
- **处理**: 不修复（代码与测试均已正确，无实际缺陷）。

### 低（4 个）

#### 2. `customers.py` 注释与代码自相矛盾

- **文件**: `backend/app/services/customers.py:304`
- **类型**: maintainability
- **描述**: 「是否结算筛选」块注释声称 `is_disabled 不存在历史 NULL`，但紧随其后的「是否停用」筛选块注释与代码（`or_(False, None)` 兼容 NULL）以及模型定义（`is_disabled = Column(Boolean, nullable=True, default=False)`）均表明历史数据存在 NULL。错误论断会误导后续维护。
- **修复**: 删除第一句错误论断，保留与代码一致的说明「is_settlement_enabled 存在历史 NULL，NULL 视为结算中，筛选"是"需兼容 NULL」。
- **状态**: 已修复

#### 3. `IS_REAL_ESTATE_OPTIONS` 与 `BOOLEAN_FILTER_OPTIONS` 语义重复且前者无引用

- **文件**: `frontend/src/constants/customerOptions.ts:109-118`
- **类型**: maintainability
- **描述**: 新增的 `BOOLEAN_FILTER_OPTIONS`（字符串值「是/否」）与既有 `IS_REAL_ESTATE_OPTIONS`（布尔值「是/否」）语义完全重复；检索整个 `*.ts/*.vue` 代码库后 `IS_REAL_ESTATE_OPTIONS` 已无任何引用。同一语义维护两套选项易造成后续改动遗漏。
- **修复**: 删除无引用的 `IS_REAL_ESTATE_OPTIONS`，保留 `BOOLEAN_FILTER_OPTIONS` 作为布尔筛选项单一来源（FilterDropdown 统一消费字符串值，布尔桥接在 computed 层转换）。
- **状态**: 已修复

#### 4. 「是否重点客户」下拉与 KPI 徽标状态不同步（脏状态）

- **文件**: `frontend/src/views/customers/Index.vue` / `CustomerFilters.vue:64-69`
- **类型**: maintainability
- **描述**: KPI 徽标（`applyKpiFilter` 直接写 `filters.is_key_customer`）与新增「是否重点客户」下拉共享同一筛选字段，但互不同步：点击 KPI「重点客户」徽标后，若在下拉改为「否」或「全部」，`is_key_customer` 被更新而 `activeKpi` 仍为 `'key'`，徽标继续显示「重点客户」，出现「徽标与列表筛选结果不一致」的脏状态。
- **修复**: 在 `Index.vue` 增加 `watch(() => filters.is_key_customer)`：当用户手动修改该字段且与激活的 key 徽标冲突（值不再是 `true`）时，将 `activeKpi` 复位为 `'all'`（仅清除徽标状态，保留用户手动选择的筛选值）。为避免 `applyKpiFilter` 内部「先清后设」的中间态误触发，增加 `applyingKpi` 写入标志，KPI 联动自身写入时跳过 watch。
- **状态**: 已修复（浏览器实测：点 KPI「重点客户」→ 徽标「重点客户 ✕」出现 → 下拉改「否」→ 徽标消失且下拉保留「否」，双向不再互相覆盖）

#### 5. `score !== null` 边界健壮性

- **文件**: `frontend/src/views/customers/detail/CustomerProfileTab.vue:75`
- **类型**: maintainability
- **描述**: 条件仅用 `score !== null` 判断，若后端异常未返回 `score` 字段（值为 `undefined`），`undefined !== null` 为 true，会将 `undefined` 传入 HealthGauge，图表渲染出 NaN 并落入红色分档，而非展示「不参与评估」。与 `CustomerHealthScore.score: number | null` 语义不贴合。
- **修复**: 改为 `healthScore.score != null`（同时排除 null 与 undefined）。
- **状态**: 已修复

---

## 汇总

| 严重程度 | 数量 | 属实 | 已修复 | 误报 |
|----------|------|------|--------|------|
| 严重 | 0 | 0 | 0 | 0 |
| 高 | 0 | 0 | 0 | 0 |
| 中 | 1 | 0 | 0 | 1 |
| 低 | 4 | 4 | 4 | 0 |
| **合计** | **5** | **4** | **4** | **1** |

4 个属实问题（均为 low/maintainability）全部修复。中等级别评论经实证核验为误报（测试文件已同步更新且全部通过），未做无效改动。

## 验证

- 后端：`pytest tests/unit/services/test_analytics_service.py tests/unit/test_customer_service.py` → 36 个用例全部通过
- 前端：`vue-tsc --noEmit` 通过；`npm run build` 成功（仅既有 chunk 体积警告）
- 浏览器实测（localhost:5173）：KPI「重点客户」徽标 → 下拉「否」→ 徽标消失、筛选值保留；下拉值与徽标双向一致，无脏状态
