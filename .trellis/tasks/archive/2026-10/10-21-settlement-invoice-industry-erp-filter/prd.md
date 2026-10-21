# 结算单管理页面新增行业类型/ERP系统筛选

## Goal

结算单管理页（路由 `/billing/invoices`）筛选栏新增「行业类型」「ERP系统」两个单选下拉筛选项，选中后结算单列表按对应客户属性做服务端过滤，「重置」清空。

## Requirements

- 筛选栏出现两个单选下拉，与既有「状态」筛选同构（复用 `FilterDropdown` 单选模式）
- 后端 `GET /api/v1/billing/invoices` 支持 `industry_type`、`erp_system` 查询参数
- 行业按 `IndustryType.name` 精确匹配（经由 `CustomerProfile.industry_type_id` 外键）；ERP 按 `Customer.erp_system`（值为 `ErpSystem.value`）精确匹配——与客户列表后端既有约定一致，不建第二套口径
- 数据查询与计数查询（`count_stmt`）必须同时受新 join/where 影响
- 「重置」行为由 `defaultFilters()` 扩展自动覆盖，无额外逻辑
- 导出（`exportInvoices`）不扩范围，仍仅传 `status`

## Constraints

- 权限不变：路由仍 `@auth_required` + `@require_permission("billing:view")`；`customer_scope_user_id` 数据可见性逻辑不改
- 响应字段不增不减（列表项无需回显这两个筛选字段）
- 不改 `sort_field_map`、不改 `mine_user_id` 逻辑
- 前端字典接口复用客户页已在用的 `getIndustryTypes()` 与 `getErpSystemsList()`，防御式解包 `res.data?.data || res.data || []`
- 遵循硬规则：数据库修改操作用事务、新测试遵循既有造数范式、Python 3.12

## Acceptance Criteria

- [x] `GET /api/v1/billing/invoices?industry_type=互联网` 仅返回该行业客户的结算单
- [x] `GET /api/v1/billing/invoices?erp_system=kingdee` 仅返回该 ERP 客户的结算单
- [x] 不带筛选参数时返回全量（outerjoin 不产生重复行、不遗漏行）
- [x] 前端筛选栏出现「行业类型」「ERP系统」两个下拉且选项加载成功
- [x] 选中筛选即触发列表重查（重置到第 1 页）；「重置」清空两个下拉并恢复全量
- [x] 新增集成测试 `test_get_invoices_filter_industry_type_and_erp_system` 通过
- [x] 既有 `test_get_invoices_list` 不回归；前端 type-check 与 `useInvoice.test.ts` 单测通过

## Notes

- 需求文档：`docs/specs/2026-10-21-settlement-invoice-industry-erp-filter.md`
- 技术方案与执行计划见 `implement.md`（由 spec 落盘）
