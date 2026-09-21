# 代码审查报告 — 批量编辑弹框新增行业与 ERP 编辑项

**日期**: 2026-09-21
**工具**: open-code-review (`ocr`) v1.12.7
**范围**: commit `c258d8a`（批量编辑弹框新增「行业类型」「ERP 系统」编辑项，2 个文件，+67/-2）
**LLM**: bifrost 网关（deepseek-v4-pro，经 ocr 配置，语言中文）
**审查耗时**: 约 5 分钟（4m47s，3 次请求遇 429 限流重试后成功）
**发现问题**: 0 个严重、1 个高、2 个中、0 个低
**已修复**: 3/3（全部属实并修复，含 1 处审查未覆盖的实锤缺陷）

---

## 审查文件清单

- `frontend/src/views/customers/components/CustomerBatchEditModal.vue`（3 条评论）
- `frontend/src/views/customers/Index.vue`（0 条评论）

## 业务背景

客户运营中台客户管理模块的批量编辑功能优化。commit `c258d8a` 纯前端改动：在客户列表批量编辑弹框（`CustomerBatchEditModal.vue`）新增「行业类型」（`industry_type_id`，存储于 `CustomerProfile` 表，FK `industry_types`，清空置 null 即删除行业）和「ERP 系统」（`erp_system`，`Customer` 表字段）两个编辑项。每个编辑项为 checkbox（勾选=本次修改该字段）+ select（allow-clear）组合，未勾选字段不提交；`Index.vue` 传入 `useCustomerList` 已加载的字典（组件内另有 onMounted 兜底自载）。后端 `POST /customers/batch-update` 白名单已支持两字段（含 `industry_type_id` 存在性校验与 profile 自动创建），后端零改动。技术栈：Vue 3 + Arco Design + TypeScript；批量上限 100 客户，提交失败项进 `failed_list` 弹窗提示。

## 问题与修复

### 严重（0 个）

无。

### 高（1 个）

#### 1. 勾选但未选值会提交空值导致批量清空；allow-clear 清除值被 JSON 丢弃

- **文件**: `frontend/src/views/customers/components/CustomerBatchEditModal.vue`（confirmBatchSubmit / previewRows）
- **类型**: bug
- **问题**: 用户勾选 checkbox 但未选择值即提交时，`industry_type_id: null`（删行业）/ `erp_system: ''`（清 ERP）会被无条件提交，最多对 100 个客户执行清空，属误操作数据丢失；且原 previewRows 对空值跳过，预览表为空但确认后仍会提交，预览与提交语义不一致。另外 Arco `allow-clear` 清空选项后值为 `''`（部分版本为 undefined），undefined 键被 JSON 序列化丢弃，「主动清空」意图到不了后端；空串 `''` 则会误导后端校验（实测 `industry_type_id: ''` 走存在性查询必失败）。
- **修复**:
  - `previewRows` 对 null/undefined/'' 值显性展示为「清空」，用户确认时明确看到将执行的清空操作，杜绝无感知清空
  - `confirmBatchSubmit` 提交前将 undefined/'' 统一归一为 `null`，使清空语义（`industry_type_id=null` 删行业 / `erp_system=null` 清空）可靠到达后端
- **验证**: 浏览器实测——勾选行业不选值 → 预览显示「行业类型 → 清空」；选择后再 allow-clear → 预览「清空」→ 提交拦截 payload 为 `{"fields":{"industry_type_id":null}}` → 后端核验客户行业已清空（审计 `{"fields": {"industry_type_id": null}}`）

### 中（2 个）

#### 2. 字典兜底自载条件永不触发（空数组是真值）

- **文件**: `frontend/src/views/customers/components/CustomerBatchEditModal.vue:321-338`
- **类型**: bug
- **问题**: `if (!props.industryTypes)` / `if (!props.erpSystems)` —— 父级 `Index.vue` 始终以数组传入（`erpSystems` 初始 `[]`，`industryTypes` 初始为硬编码 3 项数组），数组是真值，条件恒为 false，兜底加载形同虚设。父级字典请求一旦失败，下拉永久无选项且不能自愈。
- **修复**: 改为 `if (!props.industryTypes?.length)` / `if (!props.erpSystems?.length)`；同时 `industryTypes`/`erpSystems` computed 由 `props.xxx || inner` 改为「非空才用 props、否则回退内部加载」。
- **验证**: vue-tsc 通过；实测父级传入真实字典时仍优先使用父级数据。

#### 3. resetForm 无调用方，再次打开弹框残留上一批勾选与值

- **文件**: `frontend/src/views/customers/components/CustomerBatchEditModal.vue:519`
- **类型**: bug
- **问题**: `resetForm` 仅被 `defineExpose` 导出，全项目无调用方，注释「Reset form when dialog opens」未实现。组件始终挂载、按 `visible` 显隐，再次打开会保留上一批客户的勾选与值（含新增字段），导致下一批客户不自觉被带入上一次的批量修改。
- **修复**: 新增 `watch(() => props.visible, (v) => { if (v) resetForm() })`，弹框每次打开即重置。
- **验证**: 浏览器实测——上一批勾选行业并提交后关闭弹框，重新打开弹框勾选字段为空、行业值为空。

## 额外发现（审查未覆盖，修复过程中实测确认）

- **Arco `allow-clear` 清除后的实际值为 `''`（空串）而非 undefined**：初版归一逻辑仅处理 undefined，实测拦截到 `{"industry_type_id":""}` 错误 payload（后端行业存在性查询失败）。已扩展归一条件为 `value === undefined || value === ''`，二次实测 payload 正确为 `null`。

## 验证汇总

- `vue-tsc --noEmit` 通过；ESLint 无问题
- 后端 `tests/unit/test_batch_update.py` 8 passed（回归，后端未改动）
- 浏览器端到端（localhost:5173）：
  1. 勾选 3 客户 → 批量编辑 → 勾选行业/ERP → 选「房产经纪」「自研」→ 预览正确 → 提交成功 → DB 核验 `industry_type_id=2` / `erp_system='self'`，审计完整记录
  2. 勾选行业不选值 → 预览显示「行业类型 → 清空」（显性化）
  3. 选值后 allow-clear → 预览「清空」→ 提交 payload `{"industry_type_id":null}` → DB 行业清空
  4. 关闭重开弹框 → 表单已重置（watch visible 生效）
