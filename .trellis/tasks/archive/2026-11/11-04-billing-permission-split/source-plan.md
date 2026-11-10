# 结算管理权限拆分优化方案

> 2026-11-04 与用户确认定稿。用户原始诉求：角色权限页「结算管理」组是否应分组 + 补充「生成结算单」「提交结算单」权限。
> 决策记录：顶层完全拆分（module 真拆 + 4 个 view 码）因破坏面过大（持 `billing:view` 的自定义角色整模块失明）否决；采用**组内子分区**（方案 3）。「计费规则」与「包年套餐」按用户决定拆开，新增 `package_edit`/`package_delete` 补全子组自洽。

## 一、现状问题（已核实）

「结算管理」组 19 码平铺。核心病灶是 `billing:edit` 名为「修改定价规则」，实际同时把着两个业务面：

| 业务面 | 端点/入口 | 当前码 |
|---|---|---|
| 定价规则 CRUD | pricing.py:120/213/282 + PricingRules.vue | `billing:edit`/`billing:delete` |
| 包年套餐 CRUD | packages.py:141/286/433 + PackagePlans.vue | `billing:edit`/`billing:delete` |
| 收款账户更新 | invoices.py:973 + 抽屉 :402 | `billing:edit` |
| **生成结算单** | invoices.py:402 calculate / :598 generate-batch / :743 generate | `billing:edit` |
| **提交结算单** | invoices.py:1064 submit / :2439 batch-submit | `billing:edit` |
| **取消结算单** | invoices.py:1567 cancel / :2494 batch-cancel | `billing:edit` |
| 重新生成明细 | invoices.py:2599/2646（后端专用码） | 前端 Invoices.vue:145/155 误用 `billing:edit` |
| 删除结算单 | invoices.py:1624/2549 | `billing:delete` |

后果：无法授权「运营专员只能录结算单、不能动定价/套餐」；无法授权「财务只管计费配置、不碰结算单」。对照组 VR 组有 `vr_settlement:create` 独立成码，billing 组无对标码，双侧不对称。

## 二、方案（定稿）

### Part 1：新增 4 个权限码 + edit 收窄

| 新码 | 名称 | 覆盖端点 |
|---|---|---|
| `billing:invoice_generate` | 生成结算单 | invoices.py:402/598/743（试算/单张/批量生成） |
| `billing:invoice_submit` | 提交结算单 | invoices.py:1064/2439（提交/批量提交）、1567/2494（取消/批量取消，用户确认归入） |
| `billing:package_edit` | 编辑包年套餐 | packages.py:141/286 |
| `billing:package_delete` | 删除包年套餐 | packages.py:433 |

`billing:edit` 收窄为「计费规则与收款账户管理」：pricing.py:120/213、invoices.py:973。`billing:delete` 语义保持（pricing.py:282 + invoices.py:1624/2549 结算单删除，不动）。

切换方式：**纯切换**（无过渡双码 shim）。seed `--sync-permissions` / 全量 seed 自动补超管 + 预置角色；持 `billing:edit` 的自定义角色需管理员手动勾选新码（写进 PR 上线动作）。预置角色变更：运营经理 +`invoice_generate` +`invoice_submit`（保留 `edit`，零感知）；不预置 `package_edit`/`delete`（收窄后预置角色不再能改套餐，属最小授权硬化，PR 说明）。

### Part 2：角色权限页「结算管理」卡片内子分区

`permissionGroups.ts` 加 code→子区映射规则（零迁移、零 API 变动，兜底「其他」子区防漂移）：

| 子区 | 权限码 |
|---|---|
| 计费规则 | `billing:edit`、`billing:delete`、`billing:pricing_import`、`billing:pricing_export` |
| 包年套餐 | `billing:package_edit`(新)、`billing:package_delete`(新)、`billing:package_import`、`billing:package_export` |
| 余额管理 | `billing:recharge`、`billing:balance_import`、`billing:balance_export` |
| 结算单管理 | `billing:invoice_import`、`billing:invoice_export`、`billing:confirm`、`billing:detail_status_view`、`billing:detail_regenerate`、`billing:invoice_generate`(新)、`billing:invoice_submit`(新) |
| 审批与减免 | `billing:ops_approve`、`billing:sales_approve`、`billing:discount_approve`、`billing:discount_apply` |

`billing:view` 为组级入口码，置于卡片头部不归子区。

### Part 3：顺带修复

Invoices.vue:145/155 重新生成明细 `can('billing:edit')` → `can('billing:detail_regenerate')`（后端本就有专用码）。

## 三、完整切换清单

### 后端
- seed.py：ALL_PERMISSIONS +4 码；PRESET_ROLES 运营经理 +2 码；注释数 19→23
- tests/_test_data.py：+4 码（上次 `discount_apply` 漏同步导致 40301 的教训）
- invoices.py：402/598/743→`invoice_generate`；1064/1567/2439/2494→`invoice_submit`；973 保持
- packages.py：141/286→`package_edit`；433→`package_delete`
- pricing.py：不动

### 前端
- Invoices.vue：:24→`invoice_generate`；:40/:48→`invoice_submit`；:145/:155→`detail_regenerate`；:289→`billing:delete`
- InvoiceDetailDrawer.vue：:220→`invoice_submit`；:303→`invoice_submit`；:402 保持 `billing:edit`
- PackagePlans.vue：:21/:120→`package_edit`；:128→`package_delete`
- PricingRules.vue：不动
- permissionGroups.ts：子分区规则 + MODULE_NAME_MAP/ORDER 不变

### 测试
- 后端：路由权限单测换码（test_billing_api.py 等）；「权限数 79」类断言改 83；drift 豁免核对（均有装饰器，不涉及）
- 前端：Invoices/InvoiceDetailDrawer/PackagePlans 组件测试 mock 权限换码；子分区纯逻辑单测

## 四、验证

- pytest 单测+集成全量；ruff/pyright
- 前端 vue-tsc + vitest
- 冒烟：运营经理视角——生成按钮可见、提交 200；无 `invoice_generate` 角色生成按钮隐藏且后端 40303
- 手动跑 `seed.py --sync-permissions`（幂等）验证预置补齐

## 五、沉淀

- spec：权限码拆分模式（edit 收窄 + 纯切换 + seed 补预置）、子分区规则表与 seed 定义的漂移防护
- PR 上线动作：持 `billing:edit` 的自定义角色需手动勾选 `invoice_generate`/`invoice_submit`；运营经理预置已自动补
