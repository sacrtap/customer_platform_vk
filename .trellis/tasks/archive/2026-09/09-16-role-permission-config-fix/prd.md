# 角色权限配置页权限清单修正

## Goal

按 `ROLE_PERMISSION_CONFIG_PLAN.md`（已归档为 `implement.md`）修正权限清单，让「角色权限」页展示的权限与实际功能一一对应：消除 code 不一致、删除 7 个孤儿权限、补全侧边栏 4 个缺失入口，权限总数收敛为 **42 个**（49 − 7）。

## Requirements

- 修正后端预测编辑权限 code（`analytics:forecast` → `analytics:forecast_edit`，2 处）
- 修正前端 3 处错误权限 code（`balance:import`→`billing:import`、`sync:view`→`system:view`、`audit:view`→`system:view`）
- 接上 `billing:export` 控制点（前端导出按钮 + 后端导出接口），预置「运营经理」「销售经理」补该权限保持行为不变
- 接上 `analytics:export` 后端控制点（健康度导出接口，前端无按钮、不补）
- 从种子 `ALL_PERMISSIONS` 删除 7 个孤儿权限并修正分组注释
- 清理脚本 `DEPRECATED_PERMISSIONS` 追加 7 个 code（幂等删除数据库已有记录）
- 清理 `permissionGroups.ts` 的 2 个冗余分组键（`industry_types`/`groups`）
- 补全侧边栏 4 个入口（套餐方案/ERP系统/API-Key管理/数据清空）及系统菜单高亮/展开配套
- 同步集成测试种子 `conftest.py`（删 4 加 1），避免测试种子漂移

## Acceptance Criteria

- [x] `git grep "analytics:forecast\"" backend/app` 无残留；`git grep "balance:import\|sync:view\|audit:view" frontend/src` 无结果
- [x] `ALL_PERMISSIONS` 长度 = 42；清理脚本可幂等删除 7 个孤儿权限
- [x] 后端全量测试通过（unit + integration，含同步后的 conftest）
- [x] 前端 `npm test -- --run` 通过（含 permissionGroups 一致性断言）
- [x] 前端 `npm run build` 通过（vue-tsc + vite）
- [x] 行为验证：无 `billing:export` 角色看不到导出按钮、后端导出返回 403；超管侧边栏出现 4 个新入口且系统菜单正确高亮/展开

## Notes

- 计划文档 `implement.md` 为权威执行步骤（9 步），本 PRD 只聚焦目标与验收
- 数据库清理脚本需在生产发版时执行一次
