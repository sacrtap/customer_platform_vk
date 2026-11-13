# 验收记录：CRM 充值管理

> 目标：交付 CRM 回款镜像查询、客户绑定、人工原子导入充值的完整功能（无自动充值）。

## 1. 验收边界

| 维度 | 本次覆盖 | 说明 |
|---|---|---|
| 回款镜像读路径 | ✅ 真实浏览器 | 列表/筛选/分页/状态/阻断原因/双时间列 |
| 客户绑定 | ✅ 真实浏览器 + 集成测试 | 解绑、候选推荐、上游复核拒绝 |
| 原子导入资金 | ✅ 集成测试（HTTP stub 上游） | 入账一次、重复提交幂等、包年拒绝、改额冲突 |
| 手动/定时同步 | ✅ 单元 + 集成（stub 分页/契约失败） | 真实 CRM 账号联动未执行（无凭据） |
| 业务归期口径 | ✅ 集成测试 | 余额/充值记录按 `recharge_date` 过滤与展示 |
| 数据库清理保护 | ✅ 集成测试 | 存在 CRM 入账时整体拒绝 |

未覆盖（外部前提缺失）：真实 CRM 企业账号的全量同步与生产充值。需按计划「上线前检查清单」在隔离库以真实凭据执行，且业务线下核对存量账后才允许导入。

## 2. 本次实际变更文件

后端：

- `app/models/crm_recharge.py`（新增）、`app/models/customers.py`、`app/models/billing.py`、`app/models/__init__.py`
- `alembic/versions/k6l7m8n9o0p1_add_crm_recharge.py`（新增）
- `app/services/crm_client.py`、`app/services/crm_recharge.py`（新增）
- `app/services/billing.py`、`app/services/analytics.py`、`app/services/invoice_excel.py`（业务归期口径）
- `app/routes/crm_recharge.py`（新增）、`app/routes/customers.py`、`app/routes/billing/*.py`、`app/routes/database_management.py`
- `app/tasks/scheduler.py`、`app/main.py`、`app/config.py`、`app/cache/base.py`
- `scripts/seed.py`（4 个新权限码）
- `tests/unit/test_crm_recharge.py`、`tests/integration/test_crm_recharge_api.py`、`tests/_test_data.py`、`tests/unit/test_billing_service.py`

前端：

- `src/api/crmRecharge.ts`（新增，类型与请求同文件）
- `src/views/crm-recharge/Index.vue`（新增）
- `src/views/customers/components/CrmCustomerBinding.vue`（新增）
- `src/views/customers/detail/EditCustomerDialog.vue`、`src/views/billing/components/{BalanceTable,RechargeRecordModal}.vue`
- `src/router/index.ts`、`src/components/layout/AppSidebar.vue`、`src/views/roles/permissionGroups.ts`
- `src/views/crm-recharge/__tests__/Index.test.ts`（新增）、`src/views/customers/components/__tests__/CrmCustomerBinding.test.ts`（新增）

## 3. 已执行验证与结果

| 命令 | 结果 |
|---|---|
| `alembic current` / `alembic heads` | `k6l7m8n9o0p1 (head)`，开发库已在 head |
| `python scripts/check_schema_drift.py` | PASSED（模型/运行库一致） |
| `python scripts/seed.py --sync-permissions` | 新建 4 权限：`customers:crm_bind`、`crm_recharge:view/sync/import` |
| `pytest tests/unit/test_crm_recharge.py tests/unit/test_billing_service.py tests/unit/test_balance*.py` | 187 passed |
| `pytest tests/integration/test_crm_recharge_api.py tests/integration/test_billing_api.py` | 89 passed |
| `ruff check` + `ruff format --check`（改动文件） | 通过 |
| `pyright` | 0 errors |
| `npx vitest run` | 33 files / 278 tests passed |
| `npx eslint`（改动文件） | No issues |
| `npm run type-check` | 通过 |

## 4. 浏览器验收（1440×900，admin）

开发库临时插入 2 笔 CRM 回款（1 笔已绑定、1 笔未绑定），验收后已清理。

1. `/crm-recharge` 列表渲染 2 行，显示 `#900101 / 验收宜家家居 / ¥1,200.50 / 2026/11/05 / 已通过 / 房产经纪/二手房 / 宜家 / 待导入`；未绑定行额外显示「回款尚未绑定中台客户」。
2. 横向滚动可见「中台客户/状态/入账金额/归期/入账时间」列；`scroll.x` 修正为列宽合计 1916，避免列被挤压。
3. 未绑定时点击「导入充值」→ 弹窗展示实充 ¥800.00 与归期 2026/11/06，提交被拒并提示「该回款尚未绑定中台客户，请先在客户管理中完成绑定」，库中无充值记录。
4. CRM 未启用（本地无凭据）时：「同步CRM回款」「导入充值」按钮禁用，提示「当前 CRM 未启用，同步与导入暂不可用」。
5. 客户管理 → 编辑「宜家」→ 「CRM 客户绑定」显示 `验收宜家家居 CRM ID 900001`，「解绑」成功并提示「已解绑CRM客户」，区块变为未绑定。
6. 「查找CRM客户」推荐列表出现 `验收宜家家居 · 匹配度 86%`（名称相似度评分生效）。
7. 绑定提交在 CRM 未启用时返回明确提示「CRM 未启用，无法绑定时校验上游客户」（原为 503 → 前端统一「系统繁忙」，已改为 400 让真实原因可见）。

绑定成功与导入成功的完整链路由集成测试用 `httpx.MockTransport` 上游 stub 覆盖（白名单只允许官方域名，本地无法起真实 stub 域名）。

## 5. 验收中发现并修复的缺陷

| 缺陷 | 现象 | 修复 |
|---|---|---|
| 列表 500 | `select(CrmPayment, Customer, imported_subq)` 的 Row 按列摊平，`for payment, customer, imported in rows` 抛 `ValueError` | 改为显式选列 + `SimpleNamespace` 组装；补 2 个列表回归测试 |
| 未启用提示不可见 | 503 被前端 `handleError` 统一成「系统繁忙」 | 前置条件不满足改 400；列表响应新增 `crm_enabled`，前端据此禁用同步/导入并显示原因 |
| 表格列被挤压 | `scroll.x=1760` < 列宽合计 1916 | 改为 1916 |

## 6. 可复核方式

```bash
cd backend
.venv/bin/python -m pytest tests/integration/test_crm_recharge_api.py -q
.venv/bin/python -m pytest tests/unit/test_crm_recharge.py -q
cd ../frontend && npx vitest run src/views/crm-recharge src/views/customers/components/__tests__
```

浏览器复核：启动后端 8000 / 前端 5173，`admin/admin123` 登录，访问 `/crm-recharge` 与「客户管理 → 编辑 → CRM 客户绑定」。

## 7. 修复轮次 2：样式不统一 + 同步按钮不可点击

| 缺陷 | 根因 | 修复 |
|---|---|---|
| 页面按钮与搜索框样式与其他页不一致 | `crm-recharge/Index.vue` 与 `CrmCustomerBinding.vue` 的 scoped 样式只定义了 `.btn-sm`，项目约定的 `.btn`/`.btn.primary`/`.btn:disabled`/`.input`（每页各自定义，见 `VrSettlements.vue`）缺失，按钮回落到浏览器默认样式 | 按 `VrSettlements.vue` 补全 `.btn` 全套与 `.input`；搜索框改用共享组件 `CustomerSearchInput`（与其他列表页同一组件）；状态标签改用全局 `.tag amber/green/gray` 色板 |
| 同步CRM回款按钮不可点击 | 上一轮把 `:disabled="!crmEnabled"` 绑在按钮上，CRM 未配置时按钮变成死按钮、没有任何反馈 | 移除按钮级 `disabled`；改为点击后打开同步弹窗并在弹窗内说明缺少哪些配置（`CRM_ENABLED`/企业ID/手机号/密码），`submitSync` 前置校验给出 `Message.warning`。导入按钮同样处理，点击时提示「CRM 未启用：导入前需实时复核源回款」 |

验证：`npx vitest run`（33 文件 / 279 tests）、`npx eslint`、`npm run type-check` 全通过；浏览器 1440×900 实测 CRM 页与 VR 结算页的按钮、搜索框、状态标签视觉一致；同步按钮可点击并弹出警示说明，导入按钮点击给出明确 warning 且不打开确认框。

## 8. 页面内 CRM 配置与凭据验证（本轮新增）

### 目标

CRM 同步开关与凭据不再只能改部署环境变量：管理员在 `/crm-recharge` 页面直接配置、验证、更换，并且保存前先验证账号密码是否正确。

### 改动文件

| 层 | 文件 | 内容 |
|---|---|---|
| 后端 | `app/models/crm_setting.py`、`app/models/__init__.py` | 新表模型 `crm_settings`（单行 `default`） |
| 后端 | `alembic/versions/l7m8n9o0p1q2_add_crm_settings.py` | 建表迁移（不触碰既有表） |
| 后端 | `app/utils/crypto.py` | Fernet 加解密；未注入密钥抛 `CryptoNotConfigured`，密钥轮换抛 `DecryptFailed` |
| 后端 | `app/services/crm_config.py` | 运行期配置：DB 优先、环境变量兜底、进程内缓存、保存后失效 `crm:token:{corp_id}` |
| 后端 | `app/services/crm_client.py` | 默认凭据取运行期配置；新增 `CrmAuthError`、`probe()`（登录 + 客户列表 1 条只读自检）、`probe_credentials()` |
| 后端 | `app/routes/crm_recharge.py` | `GET /settings`、`POST /settings/test`、`PUT /settings`（保存前验证 + `force` 二次确认）；所有 `corp_id` 改取运行期配置 |
| 后端 | `app/tasks/scheduler.py` | 抽出 `apply_crm_sync_job()`，保存配置后即时注册/移除 22:00 任务 |
| 后端 | `app/main.py`、`app/config.py`、`app/constants/error_codes.py` | 启动加载运行期配置（先于调度器）；新增 `crm_credential_key`；新增 42201/42202 业务码 |
| 后端 | `scripts/seed.py`、`tests/_test_data.py` | 新增权限码 `crm_recharge:config` |
| 前端 | `src/api/crmRecharge.ts` | `getCrmSettings` / `testCrmCredentials` / `updateCrmSettings` 与类型 |
| 前端 | `src/views/crm-recharge/Index.vue` | 头部「CRM 配置」按钮 + 配置弹窗（开关/地址/企业ID/手机号/密码/清除密码、验证按钮、来源与打码展示、强制保存二次确认） |

### 行为规则

1. 密码只存 Fernet 密文；接口只返回 `password_set` 与打码手机号（`138****1111`），永不回明文。
2. 密码留空 = 保留已保存密码；`clear_password=true` = 清除；填新值 = 覆盖。
3. 「验证账号密码」使用表单里正在填写的值（未填则回退已保存值），只读调用 CRM 登录 + 客户列表 1 条，返回可见客户数，不写镜像、不触发充值。
4. 保存默认先验证：凭据错误返回 `42201`（HTTP 400）、上游不可用返回 `42202`（HTTP 502），前端弹出「验证未通过，仍要保存吗？」；确认后带 `force=true` 才跳过验证落库。
5. 保存后立即刷新运行期配置、失效旧 token、重注册/移除 22:00 定时任务；`enabled=false` 或凭据不完整时 `active=false`，同步与导入按既有逻辑拒绝。
6. 未保存过页面配置时仍回退 `CRM_ENABLED/CRM_BASE_URL/CRM_CORP_ID/CRM_PHONE/CRM_PASSWORD`，既有部署行为不变。

### 已执行验证

```bash
cd backend
.venv/bin/python -m alembic upgrade head                 # 建表成功
.venv/bin/python scripts/check_schema_drift.py           # ✅ PASSED
.venv/bin/python scripts/seed.py --sync-permissions      # 新建权限 crm_recharge:config
.venv/bin/python -m pytest tests/unit -q                 # 942 passed
.venv/bin/python -m pytest tests/integration/test_crm_settings_api.py \
    tests/integration/test_crm_recharge_api.py -q        # 21 passed
.venv/bin/python -m pytest tests/integration/test_migrations.py tests/integration/test_roles_api.py -q  # 26 passed
.venv/bin/python -m pyright app/services/crm_config.py app/utils/crypto.py app/routes/crm_recharge.py \
    app/tasks/scheduler.py app/main.py app/models/crm_setting.py   # 0 errors
cd ../frontend
npx vitest run                                           # 33 files / 284 tests passed
npx eslint src/views/crm-recharge src/api/crmRecharge.ts # No issues
npm run type-check                                       # 通过
```

浏览器实测（后端 `CRM_CREDENTIAL_KEY=<临时 Fernet key>` + 前端 5173，admin 登录，1365×768）：

1. `/crm-recharge` 头部出现「CRM 配置」按钮，点击打开弹窗：开关、API 地址、企业ID、登录手机号、登录密码、来源/掩码摘要齐全，与页面 `.btn` 样式一致。
2. 未保存过配置时摘要显示「当前来源：部署环境变量；已保存手机号：未配置；密码：未配置」。
3. 填 `999999 / 13800000000 / wrong-pass-1` 点「验证账号密码」：真实请求上游后返回红框「CRM 登录失败：账号或密码不正确」（上游业务 code 透传为明确原因）。
4. 点「保存配置」：弹出「验证未通过，仍要保存吗？」+ 具体原因；「返回修改」保留表单，「仍然保存」以 `force=true` 落库，顶部提示「CRM 配置已保存」。
5. 保存后 DB `crm_settings` 为 Fernet 密文（`gAAAAA...`），`updated_by=43`；重新打开弹窗显示「当前来源：页面保存的配置；已保存手机号：138****0000；密码：已配置」；页面同步提示不再显示「未启用」。
6. 验收后已清理开发库 `crm_settings` 行，避免假凭据留在开发环境。

### 部署前提

- 必须注入 `CRM_CREDENTIAL_KEY`（`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`）；未注入时页面可保存非密码字段，但保存密码会返回「未配置 CRM_CREDENTIAL_KEY」。
- 更换该密钥会使已保存密码无法解密：配置降级为「无密码」（`password_set=false`），需在页面重新填写密码，不会 500。
- 新增权限码需执行 `scripts/seed.py --sync-permissions` 并授予相应角色。

---

## 2026-11-11 线上缺陷修复（同步回款 500）

### 目标
「CRM 回款 → 选择月份 → 确认」不再返回 500「系统繁忙」，而是创建同步任务（202）。

### 实际变更文件
| 文件 | 变更 |
|---|---|
| `backend/app/utils/db.py` | 新增 `begin_write()`：先结束请求级隐式事务再开显式写事务 |
| `backend/app/routes/crm_recharge.py` | `create_crm_sync_run` 等 4 处写事务改用 `begin_write` |
| `backend/app/routes/{users,roles,industry_type_routes,balance_whitelist_routes,database_management}.py`、`billing/{balances,imports}.py` | 同上（全仓 11 处统一） |
| `backend/app/routes/customers.py` | follow-up：`async with db.begin(): pass` → `await db.commit()`（审计真实落库） |
| `backend/tests/integration/test_crm_sync_routes.py` | 新增 7 用例（202/409/400×2/未启用/helper 语义/冷缓存） |
| `backend/tests/integration/test_customers_api.py` | 新增 follow-up 落库回归用例 |
| `.trellis/spec/backend/{database-guidelines,index}.md`、`.trellis/spec/guides/cross-layer-thinking-guide.md` | 事务边界契约与「系统繁忙」排查指南 |

### 已执行验证
```bash
cd backend
# 缺陷复现（修复前）：500 + traceback InvalidRequestError: A transaction is already begun
# 修复后同请求：202 {"data":{"id":...,"status":"pending"}}
.venv/bin/python -m pytest tests/integration/test_crm_sync_routes.py -q          # 6 passed
.venv/bin/python -m pytest tests/integration/test_crm_*.py -q                   # 30 passed
.venv/bin/python -m pytest tests/integration/test_customers_api.py -q           # 68 passed
.venv/bin/python -m pytest tests/integration/test_billing_api.py \
    tests/integration/test_billing_import_export_api.py -q                      # 126 passed
.venv/bin/python -m pytest tests/integration/test_users_api.py tests/integration/test_roles_api.py \
    tests/integration/test_industry_type_routes.py tests/integration/test_balance_whitelist_routes.py \
    tests/integration/test_audit_logs_api.py tests/integration/test_admin_import_export_api.py -q  # 101 passed
.venv/bin/python -m pytest tests/unit -q                                        # 954 passed
ruff check app/ tests/ / pyright app/routes app/utils/db.py                      # 0 error
```

真实进程验证（`uvicorn --port 8014` + 开发库）：
- `POST /api/v1/crm-recharge/sync-runs {"month":"2026-11"}` → **202**，后台 run 落库；
  上游凭据为假时 run 终态 `failed` + 明确原因（不会静默成功）。
- `POST /api/v1/customers/{id}/follow-up` → **200**，`audit_logs` 新增
  `customer_follow_up` 行且 `changes.note` 正确（修复前该端点必然 500）。

### 通过/失败
- 通过：上述全部。
- 环境说明：**本地同一时刻只能跑一个 pytest 进程**。本次排查中曾因两个 pytest 进程共用
  `customer_platform_test` 产生 79 个假失败（`test_user` 的 session 级 TRUNCATE 与另一
  进程断言互相踩），串行重跑全部通过。
- 遗留（需产品决策）：`GET/PUT /users/me/preferences` 无持久化列且前端零调用；
  修复前 PUT 必然 500。建议删除端点或补列迁移。

### 开发库数据影响
为复现，曾清空开发库 `crm_settings` 并插入临时 `corp-test` 配置，**验证后已删除该行**；
若你此前在页面保存过真实凭据，需要重新填写一次（密文已被本次复现覆盖）。

---

## 2026-11-12 元数据解析修复（同步 failed：回款字段缺少「行业分类」）

### 目标
手动/自动同步不再因元数据解析失败而 failed；本月可导入回款能在同步早期出现。

### 实际变更文件
| 文件 | 变更 |
|---|---|
| `backend/app/services/crm_recharge.py` | `_walk_dicts` 取消键名白名单，改为全量遍历；`resolve_industry_paths` 缺字段时输出实际顶层键与节点数 |
| `backend/app/services/crm_client.py` | `iter_contracts` 改 `order=desc`（新签合同优先，全量语义不变） |
| `backend/tests/unit/test_crm_recharge.py` | 解析器 fixture 换成上游**真实结构**（`custom_field_groups[].custom_fields[].input_field_options.collection_options[]`），新增镜像分支/无关字段/重名/诊断信息用例 |
| `backend/tests/unit/test_crm_client_iters.py` | 新增：合同枚举必须 `sort=created_at&order=desc`、客户枚举保持 asc、分页按 total_count 收敛 |
| `frontend/src/views/crm-recharge/Index.vue` | 同步弹窗显示中文阶段 + 已扫描合同数（合同阶段耗时长，避免被当成卡死） |
| `.trellis/spec/guides/cross-layer-thinking-guide.md`、`guides/index.md` | 新增「第三方 JSON 解析：不要按已知键名白名单下钻」 |

### 真实上游证据（只读接口 + 真实同步）
```bash
# 元数据解析：真实响应 4 个允许值
resolve_industry_paths(real_by_group) -> {房产经纪根, 新业绩, 老业绩, 新房开发根}

# 真实样本回款（合同 34916658 / 回款 14430502，方案文档记录的那一笔）
_evaluate_payment(...) -> eligible=True, amount=5016.0, receive_date=2026-11-03,
                            industry_label=房产经纪/老业绩

# 真实同步 run=4（修复后，扫到前 50 个合同时的快照）
crm_payments 镜像 11 笔（2026-11-04 ~ 11-09），其中 9 笔 eligible=true，
industry_label 为「房产经纪/老业绩」「房产经纪/新业绩（新合同回款）」
（run 计数：contract_count=50 / payment_count=11 / eligible_count=9）
```
- 修复前 run=2：`failed`，`CRM 回款字段缺少「行业分类」`（解析器看不见 `custom_fields`）。
- 修复后 run=3/4：字段校验通过 → 客户 5032 完成 → 合同阶段正常推进。
- 扫描顺序实测：`order=asc` 扫 1100 个历史合同仍 `payment_count=0`（这些合同
  `received_payments_amount=0`）；`order=desc` 前 50 个合同内即出现 11 笔本月回款（9 笔可导入）。

### 已执行验证
```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_crm_recharge.py -q                 # 51 passed
.venv/bin/python -m pytest tests/unit/test_crm_client_iters.py -q             # 4 passed
.venv/bin/python -m pytest tests/unit -q                                     # 见本轮运行结果
ruff check app/ tests/ ; pyright                                             # 0 error
cd ../frontend
npx vitest run src/views/crm-recharge                                        # 12 passed
npx eslint src/views/crm-recharge ; npx vue-tsc --noEmit                      # 通过
```

### 遗留（需产品决策）：全量同步约 2.4 小时

- 合同阶段为「全量逐合同拉回款」：上游 `GET /api/v2/contracts` 共 **7118** 个合同，
  限流 1.25s/请求 → **实测 ~50 合同/分钟 ≈ 2.4 小时**/次完整同步。
- 已验证**不能**用 `contract.updated_at` 缩小范围（会漏）：
  回款 14421562（2026-11-03）所属合同 `updated_at=2025-12-18`；
  回款 14427458（2026-11-04）所属合同 `updated_at=2025-11-23` ——
  新增回款不会更新合同 `updated_at`。与方案文档「不按合同创建月份过滤」一致。
- 全局回款列表 `GET /api/v2/received_payments` 在调研阶段返回业务 code=500，不可用。
- 可选方向（需业务/上游确认）：① 接受夜间 2.4h 全量；② 断点续扫（游标分轮完成，
  不减覆盖面）；③ 与 CRM 侧确认按日期过滤的回款接口/权限。
- run=4 为验证用任务：扫到 600 个合同时已镜像 13 笔本月回款（10 笔可导入），
  对比修复前 asc 顺序 1150 个合同 0 笔；验证完成后已手动终止（error_message 已注明非功能失败）。

---

## 2026-11-12 同步提速：全局回款列表路径（2.4h → 约 2 分钟）

### 目标
解决「逐合同枚举 7118 个合同 × 1.25s 限流 ≈ 2.4 小时」的全量同步耗时问题。

### 上游事实复核（只读，真实凭据）
| 探测 | 结果 |
|---|---|
| `GET /api/v2/received_payments` | HTTP 200 + `code=500`，`error=no_method_error`，`original_message=undefined method ...` → **上游代码 bug**，任何参数组合都失败 |
| `GET /api/v2/received_payments/filter_sort_group` | `code=0`，声明支持 `receive_date`（time）筛选与 `sort=receive_date` |
| `GET /api/v2/received_payments/list` | **`code=0` 可用**；`approve_status=approved` → total=1536 |
| `receive_date[start]/[end]` 叠加 | **被服务端忽略**（窄区间仍返回 1536 条），只能本地过滤 |
| `/received_payments/export`、`/excel`、`/customers/{id}/received_payments` | 全部 404，不存在 |
| 全量 approved 拉取 | 1536 条 / 16 页 / **22.46s**；`receive_date` 覆盖 2024-11 ~ 2026-11 |
| 2026-11 approved | **14 笔**；与已镜像 13 笔完全对上，另 1 笔（14421748）为新出现，非回显 |
| 列表项字段 | 含 `contract_id` / `customer_id` / `receive_date` / `amount` / `approve_status`；**不含行业自定义字段**，需详情补齐 |

### 实际变更
| 文件 | 变更 |
|---|---|
| `backend/app/services/crm_client.py` | 新增 `iter_payments()`（`/received_payments/list?approve_status=approved`），docstring 记录上游 bug 与筛选失效 |
| `backend/app/services/crm_recharge.py` | 新增 `_scan_via_payment_list()` 主路径；`_sync_month` 优先列表路径、`CrmUpstreamError` 时回退合同枚举（不遗漏保底）；抽出共用 `_write_evaluated_payment()` / `_recheck_missing_payments()` |
| `backend/app/models/crm_recharge.py` + `alembic/versions/m8n9o0p1q2r3_add_scanned_payment_count.py` | 新增 `scanned_payment_count`（区分「已检查回款数」与「已扫描合同数」） |
| `backend/app/routes/crm_recharge.py` | `/sync-runs` 返回 `scanned_payment_count` |
| `frontend/src/views/crm-recharge/Index.vue`、`api/crmRecharge.ts` | 新增 `payments` 阶段（「拉取回款列表」）+「已检查 N 笔回款」进度 |
| `backend/tests/unit/test_crm_sync_paths.py`（新）、`test_crm_client_iters.py` | 6 + 1 个用例：当月才调详情、缺 contract_id 报错、详情 404 不写、缺失镜像复核、列表失败回退合同枚举、`/list` 路径与 approved 参数 |

### 语义保持
- 覆盖范围不变：仍取「当月 + approve_status=approved」，只是数据源从「逐合同拉回款」换成「全量 approved 列表本地过滤」；
- 既有镜像复核逻辑不变（未再见到的本月镜像逐笔复核，不因一次未列出认定删除）；
- 回退保底：列表接口若再次不可用（如上游改路径/权限变化），自动回退合同枚举，`phase=contracts` 并清零 `scanned_payment_count`。

### 验证
```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_crm_sync_paths.py tests/unit/test_crm_client_iters.py -q   # 12 passed
.venv/bin/python -m alembic upgrade head && .venv/bin/python scripts/check_schema_drift.py            # PASSED
cd ../frontend && npx vue-tsc --noEmit && npx eslint src/views/crm-recharge/Index.vue && npx vitest run src/views/crm-recharge  # 12 passed
```
真实端到端（生产凭据只读镜像，run=5）：

```
06:36:21 running|customers|cus=400
06:37:21 running|customers|cus=4600
06:37:31 running|payments|scanned_pay=400      ← 列表路径生效
06:37:51 running|payments|scanned_pay=1400     ← 1536 条列表拉完
06:38:11 succeeded|completed|scanned_pay=1536|pay=14|elig=10
```

- 总耗时 **110 秒**（客户 5032 ≈ 70s + 回款列表 1536 ≈ 22s + 当月 14 笔详情 ≈ 18s），对比合同路径 2.4 小时；
- `crm_payments` 2026-11 共 **14 笔**，10 笔 `eligible=true`（行业为房产经纪/新业绩/老业绩）；
  4 笔被阻断且原因正确（QVERSE其他 / 酒店民宿租房 / 展馆展厅 / 高校教育 不在允许行业）；
- 对比旧路径 run=4（扫 600 个合同仅得 13 笔、10 可导入）：新路径覆盖更完整（14 笔）；
- `GET /sync-runs` 返回 `scanned_payment_count=1536 / scanned_contract_count=0`，前端进度语义正确。

### 仍需上游（业务侧）
- `/api/v2/received_payments` 的 `no_method_error` 属 CRM 服务端缺陷，本方案不依赖它；
  若厂商修复并支持 `receive_date` 服务端筛选，可进一步把 22s 降到 1 页；
- `/filter_sort_group` 声明了 `receive_date` 但服务端忽略，属同一处缺陷的连带问题。

---

## 2026-11-12 录入范围收紧：只镜像「房产经纪 / 新房开发」

### 需求口径
只录入同时满足以下条件的回款记录：
1. **审批状态 = 已通过**（`approve_status=approved`）；
2. **行业分类属于「房产经纪」或「新房开发」类别**（含其子级，如「房产经纪/老业绩」「房产经纪/新业绩（新合同回款）」）；
3. 回款日期在当前同步月份内。

其他行业分类（QVERSE其他 / 酒店民宿租房 / 展馆展厅 / 高校教育 …）**不再写入镜像列表**。

### 实现
| 位置 | 变更 |
|---|---|
| `_evaluate_payment` | 返回值新增 `industry_ok`（直接判断，不靠 `blocked_reason` 字符串匹配） |
| `_scan_via_payment_list` / 合同回退路径 | `industry_ok=False` 时**不写入镜像**，收集到 `out_of_scope` |
| `_delete_out_of_scope_payments`（新） | 非目标行业：未导入 → **物理删除**（2026-11-12 按业务要求从软删除改为删除）；**已导入 → 保留镜像**只标 `eligible=False`，避免已入账资金失去来源凭据 |
| `_recheck_missing_payments` | 既有镜像的行业改为非目标范围时按同一规则移出 |
| `tests/unit/test_crm_sync_paths.py` | 新增「非目标行业不入镜像」「复核发现行业越界则移出」；删掉与新口径冲突的「无行业也镜像」用例 |

### 真实端到端（run=6，生产凭据只读）
```
08:55:08 → 08:57:09 succeeded|completed|pay=10|elig=10（客户 5032 + 列表 1536 + 当月 14 笔详情，121s）
```
数据库结果：

| 指标 | 值 |
|---|---|
| 本月镜像（`deleted_at IS NULL`） | **10 笔，全部 eligible=true** |
| 非目标行业（已清理） | **4 笔**：QVERSE其他 / 酒店民宿租房 / 展馆展厅 / 高校教育 —— 一次性删除后表内仅剩 10 行 |
| `GET /crm-recharge/payments?month=2026-11` | `total=10`，全部「房产经纪/…」+ approved |

### 数据源确认（是否「通过回款记录」查询）
| 用途 | 接口 |
|---|---|
| 回款列表 | `GET /api/v2/received_payments/list?approve_status=approved`（回款记录列表） |
| 单条回款详情（取行业字段） | `GET /api/v2/contracts/{contract_id}/received_payments/{payment_id}`（回款记录详情） |
| 回退路径 | `GET /api/v2/contracts/{id}/received_payments`（合同下的回款记录） |
| 行业字段定义 | `GET /api/v2/custom_fields/received_payment/by_group`（**回款**自定义字段，非客户字段） |
| 客户仅用于绑定映射 | `GET /api/v2/customers`（不参与行业/审批判定） |

结论：全部经由**回款记录**接口查询；行业分类取自回款记录自身的 `asset_3565dc` 字段，不从客户画像推断。


### 后续：其他行业改为物理删除（2026-11-12）

- 代码：`_retire_out_of_scope_payments` 改名 `_delete_out_of_scope_payments`，`drop` 分支由
  `UPDATE ... deleted_at` 改为 `DELETE FROM crm_payments`；已导入（`recharge_records.crm_payment_id`
  命中）仍保留镜像并标 `eligible=False`。
- 存量清理（开发库）：

  ```sql
  DELETE FROM crm_payments p
  WHERE p.industry_label IS NOT NULL
    AND NOT (p.industry_label LIKE '房产经纪%' OR p.industry_label LIKE '新房开发%')
    AND NOT EXISTS (SELECT 1 FROM recharge_records r WHERE r.crm_payment_id = p.external_id);
  -- DELETE 4；表内剩余 10 行，全部「房产经纪/…」且 eligible
  ```
- 导入引用检查：`SELECT count(*) FROM recharge_records WHERE crm_payment_id IS NOT NULL` = 0，
  删除无审计/资金风险。
- 幂等验证：run=7 重新同步后仍为 10 行（非目标行业不复活，见下方结果）。

---

## 2026-11-12 绑定 CRM 客户页「负责人」为空

### 根因
上游 `GET /api/v2/customers` 的负责人字段是 **`user_name`**（另有 `user_id`、`assist_users[]` 协办人），
**不存在** `owner_name` / `owner.name`。同步代码按旧假设取这两个键，导致 5032 个客户
`crm_customers.owner_name` 全为 NULL → 绑定页显示「负责人 -」，且同步仍 `succeeded`（静默失败）。

| 证据 | 结果 |
|---|---|
| `SELECT count(*), count(*) FILTER (WHERE owner_name IS NOT NULL) FROM crm_customers`（修复前） | `5032 / 0` |
| 真实客户项字段（实测） | `id / user_id / **user_name** / assist_users[] / name / company_name / …` |
| 真实客户项在 `owner` / `owner_name` 上 | 均不存在 |

### 变更
| 文件 | 变更 |
|---|---|
| `backend/app/services/crm_recharge.py` | 新增 `_extract_owner_name()`（优先 `user_name`，保留 `owner_name`/`owner.name` 兜底）；客户段统计 `owner_count`，为 0 且客户数>0 时 `logger.warning` 提示核对上游字段名 |
| `backend/tests/unit/test_crm_sync_paths.py` | +5 用例：`user_name` 提取与优先级、空白/缺失、旧字段兜底、回退同步批次里 owner 落库、填充率为 0 触发告警 |
| `.trellis/spec/guides/cross-layer-thinking-guide.md` | 新增「第三方字段名：结构对了，字段名也可能错」 |
| `.trellis/spec/backend/crm-upstream-quirks.md` | 新增第 9 节「字段映射表（实测）」：客户/回款列表/回款详情/合同的字段清单 |

### 验证
```bash
cd backend && .venv/bin/python -m pytest tests/unit -q          # 976 passed
.venv/bin/python -m pytest tests/integration/test_crm_recharge_api.py \
  tests/integration/test_crm_sync_routes.py tests/integration/test_crm_settings_api.py -q  # 30 passed
.venv/bin/python -m pyright                                     # 0 error
```

真实端到端（run=9，生产凭据只读，121s）：

| 指标 | 修复前 | 修复后 |
|---|---|---|
| `crm_customers` 总数 | 5032 | 5032 |
| `owner_name` 非空 | **0** | **5032**（17 个不同负责人） |
| `GET /crm-recharge/customers/candidates` | 负责人 `-` | 例：64037063「上海鹰真安防器材有限公司」→ **秦晓龙**（score 0.8633） |
| 同步结果 | succeeded（静默失败） | succeeded，`pay=10 / elig=10` 不受影响 |

---

## 2026-11-12 同步进度不可见 + 导入必现 409

### 问题 1：点击同步后无实时进度

| 现象 | 根因 |
|---|---|
| 主页面无进度、同步记录弹窗停在「执行中」不动 | `submitSync` 创建任务后直接 `schedulePoll()`，但 `activeRun` 仍为 `null`；`pollSync` 首行 `if (!activeRun.value) return` → **第一轮轮询即退出，之后再也不轮询** |
| 弹窗表格看不到进度 | 弹窗仅在打开时拉一次列表，无刷新；状态列无阶段/计数 |

后端进度本身是实的（`_progress` 每 200 笔回款、每 200 客户更新一次）。真实采样（run #11，125s）：

```
 3s running customers
85s running payments
89s running payments scanned=200
92s running payments scanned=400
95s running payments scanned=600
98s running payments scanned=1000
101s running payments scanned=1200
104s running payments scanned=1400
125s succeeded completed scanned=1536 payment_count=10 eligible_count=10
```

修复：
- `submitSync` 创建后先 `loadLatestSync()` 回读 run 再轮询；
- `pollSync` 去掉 `activeRun` 前置判断，改为「查最近任务 → 有 active 就续、没有就刷新列表」；
- 轮询不再按月份过滤，用户切换筛选时状态条不丢；
- 连续 5 次失败才停轮询；
- 主页面 `sync-bar` 常驻状态胶囊：任务号 / 阶段 / 已同步客户 / 已检查回款 / 已镜像回款；
- 同步记录弹窗：状态改彩色 tag，新增「进度」「开始时间」列，打开弹窗时复用主轮询实时刷新。

### 问题 2：「CRM回款已变更，请同步并重新确认」→ 导入必现失败

根因（真实复现）：上游详情金额是 **`"50000.0"`**，镜像列 `NUMERIC(12,2)` 读回 **`"50000.00"`**。
导入前复核快照 `str(Decimal("50000.0")) == "50000.0"` 与锁定镜像快照 `"50000.00"` 直接比较字符串
→ 永远不相等 → **每一次导入都 409**（不是偶发）。

```json
live: {"amount": "50000.0",  ...其余 5 字段完全一致}
db  : {"amount": "50000.00", ...}
equal: false
```

附带后果：即便导入成功，下一次同步也会把该行标成 `source_changed=true`，永久显示「已变更」。

修复：`_business_snapshot` 统一把金额量化到 2 位；新增 `_snapshots_differ()` 作为唯一比较入口
（两侧 normalize，兼容历史未量化快照）；替换 3 处裸比较。

### 验证

```bash
cd backend && .venv/bin/python -m pytest tests/unit -q                     # 978 passed
.venv/bin/python -m pytest tests/integration/test_crm_recharge_api.py \
  tests/integration/test_crm_sync_routes.py tests/integration/test_crm_settings_api.py -q
.venv/bin/python -m pyright                                                # 0 error
cd ../frontend && npx vitest run src/views/crm-recharge/__tests__/Index.test.ts  # 13 passed
npx vue-tsc --noEmit && npx eslint src/views/crm-recharge/Index.vue        # 通过
```

真实端到端（开发库 + 生产 CRM 凭据只读）：

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 导入「宿州诚信房产 14427678 / 50000.00」 | 409「CRM回款已变更」 | `code 0 充值成功`，record 4662，余额 50000 → 50000/0 |
| 重复导入 | — | `already_imported: true`，余额不变 |
| 回款列表状态 | — | `imported`，`source_changed=false` |
| 同步 run #11 结束后该行 `source_changed` | 会变 true（永久误报） | `false`（全库 `source_changed` 计数 0/44） |

---

## 2026-11-12 撤销 CRM 充值导入（绑定错误后的回滚路径）

### 背景
绑定错了 CRM 客户后导入的充值，原系统**没有任何撤销路径**：
`recharge_records.crm_payment_id` 是覆盖软删的唯一键（软删也判定「已导入」），
`BillingService` 只有 recharge/consume，`bind()` 不看导入记录。

### 契约
| 项 | 决定 |
|---|---|
| 接口 | `POST /api/v1/crm-recharge/payments/<id>/import/revoke`，body `{customer_id, reason, force?}` |
| 权限 | 新增 `crm_recharge:revoke`（+ `billing:recharge`）；仅超级管理员预授 |
| 必填 | `reason`（≤500 字，写入审计） |
| 余额充足 | 扣回 real/bonus，物理删除充值记录，清 `imported_snapshot`/`source_changed` |
| 余额不足（资金已消耗） | 非超管 403；超管须显式 `force=true`（否则 409）；撤销后余额可为负（欠款），结果与审计带 `needs_manual_reconciliation` + `shortfall_*` |
| 绑关系 | **不改**。正确顺序：撤销 → 改绑 → 重新导入 |
| 改绑护栏 | 客户存在 `crm_payment_id IS NOT NULL` 的充值记录时，解绑/改绑一律 409「请先撤销导入再修改绑定」 |
| 审计 | `action=crm_recharge_import_revoke`，before 余额 + 金额 + 原因 + 强制标记 + shortfall |

物理删除的理由：唯一键覆盖软删，软删后该回款永远无法重新导入；审计留痕由 `audit_logs` 的 before 快照承担。
无 FK 引用 `recharge_records.id`，删除安全。

### 权限补丁
存量库需执行（幂等，只补权限并关联超级管理员，失效权限缓存）：
```bash
cd backend && .venv/bin/python scripts/fix_add_crm_revoke_permission.py
```

### 验证

```bash
.venv/bin/python -m pytest tests/unit -q                                    # 986 passed
.venv/bin/python -m pytest tests/integration/test_crm_recharge_api.py -q    # 15 passed
.venv/bin/python -m pyright                                                 # 0 error
cd ../frontend && npx vitest run src/views/crm-recharge/__tests__/Index.test.ts  # 14 passed
```

真实端到端（开发库 + 真实回款 14427678 / 客户 27647）：

| 场景 | 结果 |
|---|---|
| 导入态下解绑 | `409 该客户已有CRM充值导入记录，请先撤销导入再修改绑定` |
| 撤销 | `200`，余额 `50000.00 → 0.00`，record 4662 删除，`imported_snapshot` 置空 |
| 撤销后重新导入 | `200`，新 record 4663，`already_imported=false`，余额回到 50000 |
| 余额被消耗（人为置 20000）后非强制撤销 | `409 余额不足以回退，请确认强制撤销并线下核对欠款` |
| 超管 `force=true` | `200`，`needs_manual_reconciliation=true`，`shortfall_real=30000.00`，余额 `-30000.00` |
| 审计 | 两条 `crm_recharge_import_revoke`，reason 与 manual 标记正确 |

---

## 审计详情可读化（追加）

> 目标：审计列表与详情从「原始英文 JSON」变为可核对的业务语言，同时保留原始数据用于追责；修复充值审计前后值相同的根因与重复审计。

### 验收边界

| 维度 | 覆盖 | 证据 |
|---|---|---|
| 描述器（各 changes 结构 → 中文摘要/字段表） | ✅ 单元测试 | `tests/unit/test_audit_describe.py`（13 passed） |
| 列表接口返回 `description` | ✅ 集成测试 | `tests/integration/test_audit_logs_api.py`（4 passed） |
| 充值审计前后快照正确 + 只一条 | ✅ 集成测试 | `tests/integration/test_audit_recharge_snapshot.py`（1 passed） |
| 前端列表中文列 / 详情弹窗 / 原始 JSON 折叠 | ✅ 真实浏览器（1440 宽 + 800 窄屏） | 截图：`~/Downloads/screenshot/audit-detail-wide.png`、`audit-detail-narrow.png` |
| 历史数据（旧快照 before==after） | ✅ 真实浏览器 | 仍显示金额摘要，无字段表（不臆造变化） |

未覆盖：历史审计记录的 `changes` 无法重算真实前后值（写入时已固化错误快照），只保证描述层不再空白；新写入路径由集成测试锚定。

### 变更文件

- `backend/app/services/audit_describe.py`（新增）
- `backend/app/routes/audit_logs.py`、`backend/app/middleware/audit.py`
- `backend/app/routes/billing/balances.py`（before 快照先固化）
- `frontend/src/views/system/AuditLogs.vue`
- `backend/tests/unit/test_audit_describe.py`、`backend/tests/integration/test_audit_recharge_snapshot.py`（新增）
- `.trellis/spec/backend/audit-log-description.md`（新增）

### 已执行验证

```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_audit_describe.py tests/unit/test_recharge_revoke.py \
  tests/integration/test_audit_logs_api.py tests/integration/test_audit_helpers_db.py \
  tests/integration/test_audit_recharge_snapshot.py -q          # 30 passed
.venv/bin/python -m pytest tests/integration/test_billing_api.py -q   # 79 passed
.venv/bin/python -m pyright app/services/audit_describe.py app/routes/audit_logs.py \
  app/middleware/audit.py app/routes/billing/balances.py       # 0 errors
.venv/bin/python -m ruff check（上述文件）                      # All checks passed

cd ../frontend && npx eslint src/views/system/AuditLogs.vue     # 0 errors
```

真实浏览器（开发库 127.0.0.1:5173 审计日志页）：

| 场景 | 结果 |
|---|---|
| 撤销充值记录 #4669 详情 | 摘要 5 条（客户/金额/原因/余额合计/原入账时间）+ 字段表 2 行，时间 `2026-11-12 12:54:35` |
| 历史充值记录 #4669（旧数据 before==after） | 显示金额摘要，无字段表，原始 JSON 可展开 |
| 创建客户 #27672 详情 | `新建客户，涉及 5 个字段` + 公司ID/名称/账号类型/结算周期/结算类型（值中文化） |
| 800px 窄屏 | 弹窗 `min(760px, 100vw-32px)`，`document.scrollWidth == innerWidth`，无横向溢出 |
