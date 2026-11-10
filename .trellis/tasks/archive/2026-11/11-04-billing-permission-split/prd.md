# 结算管理权限拆分：新增生成/提交/套餐专用码 + edit 收窄 + 子分区

## Goal
角色权限页「结算管理」组 19 码平铺、`billing:edit` 一码跨「计费配置」与「结算单生命周期」双业务面，无法按岗位授权；且缺少「生成结算单」「提交结算单」专用码（VR 组有 `vr_settlement:create` 对标，billing 组无）。

## Requirements
- R1 新增 `billing:invoice_generate`（试算/单张/批量生成）、`billing:invoice_submit`（提交/批量提交/取消/批量取消）、`billing:package_edit`、`billing:package_delete` 四个码；`billing:edit` 收窄为「计费规则 CRUD + 收款账户」
- R2 角色权限页「结算管理」卡片内按业务面渲染子分区（通用/计费规则/包年套餐/余额管理/结算单管理/审批与减免），与侧边栏子菜单同名
- R3 顺带修复：明细「重新生成」按钮从误用的 `billing:edit` 改回后端既有专用码 `billing:detail_regenerate`
- R4 纯切换无过渡双码；seed sync 自动补超管 + 预置角色（运营经理 +generate +submit）

## Acceptance Criteria
- [x] AC1 后端 10 处端点切换新码（invoices 7 + packages 3）；无码用户 40301、有码用户过权限校验（API 冒烟 9 项）
- [x] AC2 前端 12 处 can() 切换 + 子分区 UI：运营经理视角生成按钮可见；无 invoice_generate 角色隐藏且后端 403
- [x] AC3 子分区渲染 6 区、23 码全部正确归位（浏览器实测 DOM 核对）
- [x] AC4 套餐收窄生效：运营经理（edit 收窄后无 package_edit）POST /package-plans → 40301
- [x] AC5 后端全量 pytest + ruff + pyright 通过；前端 vue-tsc + vitest 262 passed（含子分区纯逻辑 6 新用例）
- [x] AC6 `seed.py --sync-permissions` 实测：新建 4、更新 1（edit 描述）、超管 +4、运营经理 +2

## Notes
- 方案决策记录：用户曾设想顶层完全拆分（module 真拆 + 4 个 view 码），因「持 billing:view 的自定义角色整模块失明」破坏面否决，改组内子分区；「计费规则/包年套餐」按用户决定拆开并新增 package_edit/delete 补全子组自洽
- 冒烟账号：tanshitao（运营经理）/baiyuliang（销售经理）dev 库密码重置为 admin123（原密码未知）
- 上线动作：持 `billing:edit` 的自定义角色需管理员手动勾选 `invoice_generate`/`invoice_submit`/`package_edit`/`package_delete`（如需）；运营经理预置已自动补 generate/submit，package_* 未预置（最小授权硬化）
