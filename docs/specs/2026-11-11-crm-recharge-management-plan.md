# CRM充值管理：功能调研与开发实施方案

- 日期：2026-11-11
- 状态：调研与设计完成，等待方案审批；未批准实施。
- 本轮为只读规划模式，方案保存在 `local://crm-recharge-plan.md`；未修改业务代码、未执行迁移或真实充值。

## 背景与目标

在系统管理下新增 CRM 充值管理；客户编辑支持 CRM 客户搜索、模糊推荐与手动绑定；每天 22 点读取当月行业分类为房产经纪、新房开发且审批已通过的回款，由人工选择后充值到指定客户。充值实际时间取 CRM 回款时间，原创建时间继续保留。

核心数据流程固定：定时任务执行→经CRM接口完整读取当月符合原行业及审批条件的回款→幂等录入CRM充值管理的回款列表（无论是否绑定中台客户）→人工逐笔核对；未绑定时在客户管理找到指定客户并绑定，返回回款列表刷新→填写实充/赠送并点击“导入充值”→原子增加指定客户余额并新增其余额管理充值记录。同步本身不创建充值记录、不改变余额；取消确认或导入失败也不改变余额。

## 调研记录

### 外部接口验证（2026-11-11，只读业务访问）

- 已用提供的凭据成功认证独立版 `https://lxcrm.weiwenjia.com/api/v2/auth/login`，HTTP 200、业务 code=0，返回企业ID匹配、is_expired=false；api_host=`https://lxcrm-api.weiwenjia.com`。另外三个官方版本域名均返回 code=100400。凭据和令牌不入方案。
- 客户列表 `GET /api/v2/customers?per_page=1&page=1` 成功，账号可见 total_count=5032；合同列表同参数成功，total_count=7117。这是账号可见量，不等价于证明企业全量权限。
- 客户名称查询 `GET /api/v2/customers/by_name` 实测精确同名搜索成功；模糊推荐仍需本地实现，不能把它描述为已验证的模糊匹配引擎。
- 回款元数据 `GET /api/v2/custom_fields/received_payment/by_group` 证实筛选字段是 `text_asset_3565dc`（行业分类、nested_select_field），不是客户的 industry。房产经纪根值 `ba2503bf-06b0-4e90-80fe-fea73d3ef4e5`，子项新业绩 `1b1ae256-e806-4417-8449-a2d6300093dd`、老业绩 `943a9513-8ff3-4f80-912a-c12a6ac11dc5`；新房开发根值 `bdb440d1-1be2-46ed-acfb-e919b5d245b4`。应包含根及全部后代，运行时验证元数据。
- 官方合同下回款入口 `GET /api/v2/contracts/:contract_id/received_payments` 实测成功并取得非空样本；列表不含行业值，详情 `GET /api/v2/contracts/:contract_id/received_payments/:id` 实测包含该自定义字段。样本 receive_date=2026-11-09、approve_status=applying，正式筛选必须排除。
- 文档外 `GET /api/v2/received_payments` 无筛选及带当月日期+approved筛选均返回业务 code=500；不能作为主路径。其 filter_sort_group 成功不代表列表可用。采用官方合同枚举→回款列表→必要详情，不按合同创建月份过滤，避免漏历史合同当月回款。
- receive_date 文档和实测只有 YYYY-MM-DD，无时分秒；不以CRM创建或审批时间冒充实际回款时刻。官方限频10次/10秒，7117合同意味着同步需节流和进度状态。

### 现有资金路径（只读子代理核实）

- `backend/app/services/billing.py:163-210` 的 `BalanceService.recharge(customer_id, real_amount, bonus_amount, operator_id, payment_proof=None, remark=None)` 内直接提交、无行锁；CRM导入不能先调用此提交式实现再另标记已导入，必须原子记账。
- RechargeRecord.created_at 为现有创建时间；本月卡片、最近充值筛选排序、趋势及结算Excel使用它。独立业务日期如何影响统计须产品决策。
- 包年当前允许充值但余额展示取套餐额度，CRM导入需明确边界。

### 官方资料

- [对接流程](https://apidoc.weiwenjia.com/docs/crm_open_api/crm_open_api-1f8mjkto9cnk5)
- [开发须知](https://apidoc.weiwenjia.com/docs/crm_open_api/crm_open_api-1f8mjm3kdttee)
- [客户名称查询](https://apidoc.weiwenjia.com/docs/crm_open_api/customer_list_by_name)
- [合同列表](https://apidoc.weiwenjia.com/docs/crm_open_api/contract_list)
- [回款列表](https://apidoc.weiwenjia.com/docs/crm_open_api/crm_open_api-1hhj3605thq9t)
- [回款详情](https://apidoc.weiwenjia.com/docs/crm_open_api/contract_crp_detials)
- [自定义字段](https://apidoc.weiwenjia.com/docs/crm_open_api/crm_open_api-1b2f6p3ttp3id)

## 已确认产品决策

- 一对一严格绑定；一笔回款只允许生成一条充值记录，只入其CRM客户绑定的中台客户。实充与赠送均提供填写项：实充默认CRM回款金额，提交时必须等于源回款金额；赠送默认0，可额外填写非负金额，不占用回款金额。例如回款1000，填写实充1000、赠送200，则增加总余额1200。CRM导入不允许负数，两个值不能同时0；现有手动/Excel扣减行为不变。
- 最近充值、本月充值、充值趋势及结算明细按实际回款日期；历史记录回填原创建日期；created_at保持原值。
- 每天22点仅自动拉当月；另提供按月份手动同步，补上月及历史月份。
- CRM导入禁止包年客户；不改变现有手动/Excel充值的客户类型规则。

## 补充验证证据

- 真实已通过样本：回款ID=14430502，receive_date=2026-11-03，approve_status=approved，行业值为 `ba2503bf-06b0-4e90-80fe-fea73d3ef4e5/943a9513-8ff3-4f80-912a-c12a6ac11dc5`，即房产经纪/老业绩；字段展示名为 `text_asset_3565dc_display`。必须按斜杠路径解析，不能将完整值与根UUID做等值比较。
- 返回的 api_host 上全局回款列表仍code=500，排除仅页面主机错误；正式路径保持合同下接口。客户名称子串搜索实测code=0、5条命中且含原客户。
- LSP已确认 BalanceService.recharge 生产调用仅 `backend/app/routes/billing/balances.py:1682`；批量导入为另一入口 `backend/app/routes/billing/imports.py:224` → batch_import_recharge。
- `backend/app/utils/audit_helpers.py::create_audit_entry(..., auto_commit=False)` 可直接复用以使审计与资金同事务；不得照抄当前手动充值auto_commit=True或consume预先commit调用方事务。
- `.trellis/spec/backend/permission-model.md`明确新增权限使用seed.py ALL_PERMISSIONS + `--sync-permissions`，无需新增历史fix权限脚本；前端导航还包括 `frontend/src/composables/useAppLayout.ts::navSections`，不能只改AppSidebar。
- 当前消费同步锁有30分钟超时，而CRM需枚举7117合同；不复用绑定MySQL的SyncTaskService及其30分钟卡死策略，复用监控装饰器与会话惯例，新CRM任务独立持久化进度。
- 补充客户详情只读实测：`GET /api/v2/customers/:id` 业务code=0、ID匹配且名称非空；approved正样本的行业展示值实测为“房产经纪/老业绩”。
- `backend/app/routes/database_management.py::clear_balance_data` 使用物理DELETE清空充值记录。新增CRM来源后必须保护已导入凭据，不能删除记录后让同源回款再次入账，具体兼容策略见实施步骤5。
- 本轮重新读取 `frontend/src/views/billing/components/RechargeModal.vue`：现有充值表单独立填写real_amount、bonus_amount及备注，均保留2位小数，允许仅赠送以及负数扣减，禁止两项同时0。`BalanceService.recharge` 分别增加实充和赠送余额，总余额为两者之和。CRM导入参考双金额表单及记账结构，但采用本方案更严格的源金额一致、非负校验，不复制手动扣减规则。
- 本轮产品确认：实充必须等于源回款金额、赠送额外增加、CRM导入两项非负；已据此修订导入API、服务签名、表单、幂等金额冲突、审计和行为验收。该确认替代原方案赠送固定0的约束，不改变定时同步只落回款、不写余额的边界。

## 实施方案

以下新路径、字段、接口和符号均为本方案明确指定的新增设计，不声称仓库已经存在。现有路径锚点以本次只读研究为依据，实施前重读。顺序为1→2→3→4→5→6→7；第6步前端与第5步后端可在第4步接口契约固定后并行，但由同一集成负责人验收。

### 1. 固定业务契约与数据结构

采用“CRM只读镜像→人工确认→本地原子充值”，不向CRM创建、修改或审批任何业务记录。上线前由业务线下核对当月已有手动/Excel充值；用户明确不增加历史关联、标记已处理或自动金额匹配功能。CRM唯一键只能防止本模块重复导入，不能识别上线前手工记过的账；页面确认框必须提示这一限制。

在 `backend/app/models/crm_recharge.py` 新建三个typed ORM模型，沿用BaseModel、软删除与CST naive创建时间，不建立通用集成平台：

| 模型/表 | 精确新增字段与约束 |
|---|---|
| `CrmCustomer` / `crm_customers` | `corp_id VARCHAR(64) NOT NULL`、`external_id BIGINT NOT NULL`、`name VARCHAR(255) NOT NULL`、`normalized_name VARCHAR(255) NOT NULL`、`owner_name VARCHAR(255) NULL`、`last_seen_at DateTime NOT NULL`；唯一 `(corp_id, external_id)`。只存推荐所需字段，不复制电话、联系人等无关个人资料。 |
| `CrmPayment` / `crm_payments` | `corp_id VARCHAR(64) NOT NULL`、`external_id BIGINT NOT NULL`、`crm_customer_id INTEGER NULL FK crm_customers.id`、`contract_external_id BIGINT NOT NULL`、`contract_title VARCHAR(255) NULL`、`customer_external_id BIGINT NOT NULL`、`customer_name VARCHAR(255) NOT NULL`、`amount NUMERIC(12,2) NULL`、`receive_date DATE NULL`、`approve_status VARCHAR(32) NOT NULL`、`industry_path TEXT NULL`、`industry_label TEXT NULL`、`source_updated_at VARCHAR(64) NULL`、`eligible BOOLEAN NOT NULL`、`blocked_reason TEXT NULL`、`last_seen_at DateTime NOT NULL`、`imported_snapshot JSONB NULL`、`source_changed BOOLEAN NOT NULL DEFAULT false`；唯一 `(corp_id, external_id)`；索引 `(receive_date, eligible)`、`crm_customer_id`。金额或日期异常可保留行并给原因，不把异常解析成0或当前日期。 |
| `CrmSyncRun` / `crm_sync_runs` | `corp_id VARCHAR(64) NOT NULL`、`month DATE NOT NULL`（月首）、`trigger VARCHAR(16) NOT NULL`（scheduled/manual）、`operator_id INTEGER NULL FK users.id`、`status VARCHAR(16) NOT NULL`（pending/running/succeeded/failed）、`phase VARCHAR(24) NOT NULL`（customers/contracts/payments/completed）、`heartbeat_at DateTime NOT NULL`、`started_at DateTime NULL`、`finished_at DateTime NULL`、`customer_count INTEGER NOT NULL DEFAULT 0`、`contract_count INTEGER NOT NULL DEFAULT 0`、`scanned_contract_count INTEGER NOT NULL DEFAULT 0`、`payment_count INTEGER NOT NULL DEFAULT 0`、`eligible_count INTEGER NOT NULL DEFAULT 0`、`error_message TEXT NULL`；部分唯一索引 `uq_crm_sync_active_corp(corp_id) WHERE status IN ('pending','running')`。单企业同时只跑一个月份，避免多个扫描抢额度。 |

在 `backend/app/models/customers.py::Customer` 增加 `crm_customer_id INTEGER NULL FK crm_customers.id`，部分唯一索引 `uq_customer_active_crm_binding(crm_customer_id) WHERE deleted_at IS NULL AND crm_customer_id IS NOT NULL`，一名存活中台客户只能绑定一个CRM客户，一个CRM客户只能绑定一名存活中台客户。这里FK指向CRM镜像表，**不是**复用 `settlement_account_id` 指向中台customers自身。CRM镜像ID为内部ID，所有界面同时展示外部external_id避免误认。CRM公司与ERP company_id无关。

在 `backend/app/models/billing.py::RechargeRecord` 增加 `recharge_date DATE NOT NULL`、`crm_payment_id INTEGER NULL FK crm_payments.id UNIQUE`；唯一约束覆盖软删除行，不能软删除充值后再次导入原回款。`crm_payment_id IS NULL` 为手动/Excel充值，非NULL为CRM来源，无需新增可漂移的source枚举。由充值记录反查导入状态、操作者及created_at，不另建重复的imported标志或recharge_record_id双向外键。

迁移放 `backend/alembic/versions/`；本次已读唯一head为 `j5k6l7m8n9`，实施开始先用 `.venv/bin/python -m alembic heads` 读取实际head，若变化则直接接实际唯一head。单个新revision依次建镜像表、run表、客户FK、新充值列和约束：recharge_date先nullable→`UPDATE recharge_records SET recharge_date=created_at::date`→设NOT NULL并设服务端默认 `CURRENT_DATE`（PG会话Asia/Shanghai）。**不得覆盖任何历史created_at、余额或金额**。新手动/Excel写入仍显式传 `cst_today()`，服务端默认只兜底既有直接INSERT。为新模型补 `backend/app/models/__init__.py` 的模型导入（unverified — confirm first：实施时先定位现有模型注册列表），确保Alembic与测试metadata可见。downgrade按反向依赖删新增列和表；有CRM已入账数据时不做生产降级，改停用同步并保留表和资金记录。

### 2. 实现受控CRM读取客户端

新增 `backend/app/services/crm_client.py::CrmClient`，复用已安装 `httpx==0.28.1`，不加SDK、模糊匹配库或任务队列。通过构造注入配置和Redis；`async with CrmClient(...)` 内复用一个AsyncClient连接池，HTTP timeout=30秒。只暴露以下协程：

```python
async def get_customer_fields(self) -> dict: ...
async def get_payment_fields(self) -> dict: ...
async def iter_customers(self): ...  # AsyncIterator[dict]
async def iter_contracts(self): ...  # AsyncIterator[dict]
async def iter_contract_payments(self, contract_id: int): ...  # AsyncIterator[dict]
async def get_customer(self, customer_id: int) -> dict: ...
async def get_payment(self, contract_id: int, payment_id: int) -> dict: ...
```

正式实现必须完整，以上省略号只是签名说明。路径依次复用官方 `/api/v2/custom_fields/customer/by_group`、`/api/v2/custom_fields/received_payment/by_group`、`/api/v2/customers`、`/api/v2/contracts`、`/api/v2/contracts/{id}/received_payments`、`/api/v2/customers/{id}`、`/api/v2/contracts/{contract_id}/received_payments/{id}`；客户详情路径本轮已补实测：业务code=0、返回ID与请求一致且有客户名称，作为绑定时上游存在性校验，不凭名称或浏览器提交值认定存在。

`backend/app/config.py::Settings` 新增开关（bool，默认false）、官方基址（默认 `https://lxcrm.weiwenjia.com`）、企业ID、登录手机号及登录密码（后三项str，默认空），分别映射 `CRM_ENABLED/CRM_BASE_URL/CRM_CORP_ID/CRM_PHONE/CRM_PASSWORD`，属性命名沿用现有Settings的环境变量小写惯例。环境变量仅是「未在页面保存过配置」时的出厂默认值：管理员可在「CRM充值管理 → CRM 配置」（权限 `crm_recharge:config`）直接维护开关、API 地址、企业ID、登录手机号与密码，并支持随时更换；保存前默认先调用只读自检（登录 + 客户列表 1 条）验证账号密码，验证失败拒绝落库，仅在明确二次确认后允许 `force` 跳过。登录密码用 Fernet 对称加密后落库（表 `crm_settings.password_cipher`），密钥 `CRM_CREDENTIAL_KEY` 由部署密钥注入且不入库、不写日志；更换该密钥会导致旧密文不可解密，配置降级为「无密码」并需在页面重新填写。配置保存后即时刷新进程内运行期配置、失效 `crm:token:{corp_id}` 旧凭证，并重注册/移除 22:00 定时同步任务。本计划不保存实际值或可展开的凭据占位符。配置校验仅允许官方HTTPS域名，不接受请求体指定host；企业ID改变后按新corp分区查询，不串用旧绑定或旧token。启用但缺凭据时同步/绑定外部校验/导入返回HTTP503+SERVICE_ERROR，已有本地记录仍可查。

CRM_ENABLED=false时不注册自动任务，并拒绝手动同步、新绑定/换绑的上游校验及首次导入（503）；已有镜像与已导入凭据仍可按权限查询，解绑不依赖CRM。同源已成功导入的幂等查询可以继续返回原结果，不重写资金。

认证固定 `POST /api/v2/auth/login`，JSON含 `device='open_api'`、`login=配置手机号`、官方契约要求的密码字段和 `corp_id=配置企业ID`；验证 `code==0`、非空 `data.user_token`、返回corp_id一致、`is_expired`不为true。后续header `Authorization: Token token={user_token}, device=open_api, version_code=9.9.9`。HTTP200但业务code!=0仍为失败，禁止当空列表成功。不得记录请求body、token、Authorization或完整上游响应。

所有本功能外部请求（含登录、同步、导入前复核）共用Redis企业级节流：`crm:rate:{corp_id}` 用SET NX PX=1250控制每1.25秒最多启动一个请求；等待期间不持有PG事务/连接。Redis不可用则拒绝发起外部请求，返回可诊断失败，不能退化各进程独立限流。共享token键 `crm:token:{corp_id}`；在CacheService `_ttl_config` 登记crm_token=1800秒，通过ttl_for读取，TTL只是本地缓存寿命，不宣称是CRM有效期。登录由 `crm:login:{corp_id}` 的带随机owner锁串行化（TTL60秒，30秒请求超时）；释放以owner比较删除；锁未拿到等待共享token或超时失败。每次请求读取当前token；上游100401/HTTP401最多重新获取token并重放一次GET，其他失败不无限重试；只失效本次实际使用且仍相同的token，避免误删别的worker刷新结果。

分页：客户和合同per_page=100已实测生效，指定page从1递增、`sort=created_at&order=asc`；合同回款请求per_page=100但按响应per_page计算，不假设服务端一定采纳。使用响应has_next_page（存在时）、total_count/per_page和空页收敛；逐页去重external_id，出现重复页/未到声明总量即异常空页则任务失败，不把第一页当全量。不按客户绑定、客户行业、合同创建日期或合同审批状态缩小合同集，避免漏回款。

### 3. 全量枚举、月度筛选、幂等镜像与调度

新增 `backend/app/services/crm_recharge.py::CrmRechargeService`，同文件放以下专用纯函数，不建通用规则引擎：`normalize_crm_name(value: str) -> str`、`score_crm_candidate(query: str, candidate: str) -> float`、`resolve_industry_paths(metadata: dict) -> set[str]`、`parse_industry_path(value: object) -> list[str]`。

`resolve_industry_paths`从回款字段中按精确label='行业分类'找到name，并要求其等于本租户已验证的 `text_asset_3565dc`；从元数据定位两个根标签房产经纪、新房开发并递归收集后代。根缺失、重名或字段不可见→任务failed并显示配置契约变化，不改用客户industry猜测。解析字符串按 `/` 分段；数组值按每个元素的 `/` 分段展开；未知结构保留blocked_reason并禁止导入，不用字符串contains误匹配UUID。

新增服务入口：`async def create_sync_run(self, month: date, trigger: str, operator_id: int | None) -> CrmSyncRun`、`async def execute_sync_run(self, run_id: int, session_factory) -> None`、`async def recover_stale_sync_runs(self) -> int`。读HTTP与写PG分离：每次镜像upsert、进度推进及run状态转换均使用短session的 `async with db_session.begin():`，HTTP不在事务内；不将活跃PG session跨后台协程共享。

执行顺序固定：

1. create_sync_run在事务中先将heartbeat超过2分钟的pending/running置failed（error_message='同步进程中断，请手动重新同步'），再插pending；同企业活跃唯一索引冲突→409、BAD_REQUEST、'已有CRM同步任务正在执行'。pending创建成功后以现有Sanic后台任务方式启动，立即返回run_id；执行以原子 `UPDATE ... WHERE status='pending' RETURNING` 领取running，未领取的worker不执行。
2. 每30秒独立短事务刷新heartbeat；每次写进度或镜像前确认run仍为running。失去任务所有权则终止，不写succeeded。启动钩子仅恢复超过2分钟的旧任务，不把其他worker刚开始的任务误置failed。进程死亡后不自动充值；用户可重新同步，已落库镜像按唯一键更新。
3. 完整分页客户镜像：按 `(corp_id, external_id)` upsert名称及normalization等必要字段，last_seen_at取本次CST；不物理删除上游暂不可见客户、不清空已有绑定。不完整抓取不能宣布客户目录完整。
4. 完整分页全部账号可见合同，逐合同枚举全部回款分页。先按回款列表 `receive_date` 落在 `[month首日, next_month首日)`、`approve_status=='approved'` 本地筛选；对这些候选和已镜像但本次列表状态改变的记录读取详情，取回款级行业字段并再次校验日期和审批。列表不含行业，不能只用列表判断。缓存客户目录用于回款customer_external_id映射，目录暂缺则该回款crm_customer_id=NULL、blocked_reason='CRM客户不可见或已删除'，不丢掉符合日期的记录。
5. 详情行业路径含任一允许根或其后代，且同企业、customer/contract ID有效、金额为有限正数且精确到最多2位小数、日期有效→eligible=true；不满足则false并给原因（不把负回款转换成退款操作）。amount转Decimal只从上游字符串转换；超NUMERIC(12,2)边界或非有限金额不能写入资金。
6. 镜像upsert以 `(corp_id, external_id)` 幂等；不允许同步修改RechargeRecord或余额。未导入行保存最新观察；已导入行的imported_snapshot存最小白名单 `{customer_external_id, contract_external_id, amount, receive_date, industry_path, approve_status}`，与新详情比较业务内容，变化则source_changed=true并提示人工核对，但保留原充值金额/日期/created_at，不自动冲正或补差。枚举中已镜像记录变成非approved/移出月份/行业变化时更新eligible=false；已经导入的记录仍可查询。
7. 对本次开始前就存在的该月所有镜像（包括已导入和未导入）但扫描未再见到的源ID，额外GET原合同下详情复核；明确404则标不可用，已导入同时标source_changed=true，不改原账；不以一次未列出认定删除。权限/网络/业务失败使run失败，保留原镜像及上次成功时间。导入入口仍始终实时复核，部分同步结果不等同于已完整核对。
8. 全部分页及必要详情成功才将run置succeeded、phase=completed、finished_at；网络/授权/分页/解析契约失败置failed并保存不含敏感数据的error_message及进度。中途完成的镜像保留以便重跑，页面明确显示失败及最后完整成功时间，不能显示“本月无回款”。

在 `backend/app/tasks/scheduler.py::init_scheduler` 内注册无参协程 `_sync_crm_payments()`，`@monitored_task('crm_payment_sync', 'CRM回款同步')`，`CronTrigger(hour=22, minute=0, timezone=CST)`，`id='crm_payment_sync'`、replace_existing=True、max_instances=1、coalesce=True。仅crm_enabled且凭据完整时注册；业务运行月份在触发时用cst_today确定，不在应用启动时冻结。无日期day约束，即**每天**22点，不是每月22点。调度协程启动并await同一execute方法，人工入口后台启动该方法；跨worker互斥靠DB活跃唯一索引，而非max_instances。添加至现有scheduler-status查询job集合（实际列表挂点实施时在scheduler.py按job_id列表定位）。在 `main.py::on_start` 独立调用recover_stale_sync_runs；不复用绑定MySQL的SyncTaskService和30分钟TTL锁。

手动同步只接受 `month='YYYY-MM'`，不能未来月，任一历史月份均可，保持与自动任务相同筛选口径；每次一个月。旧月份不会被自动补取，UI常驻提示月底22点后新增/跨月才审批通过需手动补同步。首次启用由管理员手动同步当月以填充客户目录，再进行绑定；不在迁移或后台初始化时自动入账。

按本轮量级，至少72页合同+约7117个合同回款请求+51页客户，按1.25秒启动间隔仅基础枚举下限约2.5小时（[INFERENCE]，不含详情、分页与网络时延）。因此22点是开始时刻，不承诺22点立即可导入；展示真实进度且不能用现有30分钟卡死阈值。如果供应商后续修复全局接口，另行验证后才调整主链路，本次不把未验证入口作为自动fallback。

### 4. 绑定、推荐和后台API权限契约

新增蓝图 `backend/app/routes/crm_recharge.py::crm_recharge_bp`，prefix=`/api/v1/crm-recharge`，在已读 `backend/app/main.py::create_app` 注册。所有端点均 `@auth_required` 并挂下表权限；多权限叠加使用多个require_permission，沿用ErrorCodes，不新增错误码类别。`403→FORBIDDEN`、`404→NOT_FOUND`、`400/409→BAD_REQUEST`、上游失败`502→SERVICE_ERROR`、未配置/Redis不可用`503→SERVICE_ERROR`；列表仍沿用 `{code,message,data}`。

| 请求 | 精确请求/响应重点 | 所需权限 |
|---|---|---|
| `GET /customers/candidates` | query: `customer_id` 必需、`query` 可选、`page`默认1、`page_size`默认20上限50；query未传时用中台客户名称返回推荐top10，传非空query返回名称包含匹配（规范化后），无包含则按相似度；data=`{list:[{id,external_id,name,owner_name,score,bound_to_current,unavailable}],total,page,page_size,directory_updated_at}`。id是本地crm_customers.id。 | customers:edit + customers:crm_bind |
| `PUT /customers/<customer_id:int>/binding` | body=`{crm_customer_id: number|null}`；正整数候选ID绑定，null解绑，空字符串归一null；非空非法类型400，不能将任意非法值静默解绑；返回 `{crm_customer_id,crm_customer_external_id,crm_customer_name}`。 | customers:edit + customers:crm_bind |
| `GET /payments` | query: `month=YYYY-MM`、`keyword`（回款ID/合同名/CRM客户名/绑定客户名）、`status=pending|imported|blocked|all`默认all、page=1、page_size=20上限100；状态由是否存在关联RechargeRecord及eligible/绑定/包年/源变更推导；pending=未导入且可操作，blocked=未导入且任一门槛不满足。默认全部以便未绑定回款也可见；行级权限仍生效。已导入行另返回充值记录的real_amount、bonus_amount、total_amount（两位小数字符串），与源回款amount分开展示。 | crm_recharge:view |
| `GET /payments/<payment_id:int>` | 本地镜像详情、行业路径、回款日期、金额、目标客户、资格阻塞原因、导入人/创建时间/充值记录ID、source_changed；不返回原始CRM全量JSON。 | crm_recharge:view |
| `POST /sync-runs` | body=`{month:'YYYY-MM'}`，HTTP202 data=`{id,status:'pending'}`；冲突409含现有run_id供查看。 | crm_recharge:sync + customers:view_all |
| `GET /sync-runs` | month可选、page=1、page_size=20上限100，返回各run计数、阶段、起止时间与错误；另data.latest_success_at为所选月最后成功时间。 | crm_recharge:sync + customers:view_all |
| `POST /payments/<payment_id:int>/import` | body=`{customer_id:number,real_amount:string,bonus_amount:string}`，两个金额使用十进制定点字符串，real_amount必填，bonus_amount省略则0；禁止客户端覆盖源amount或recharge_date。HTTP200返回 `{recharge_record_id,customer_id,real_amount,bonus_amount,total_amount,recharge_date,created_at,already_imported,balance:{real_amount,bonus_amount,total_amount}}`；金额均为两位小数字符串。real_amount必须等于实时复核的CRM回款金额，bonus_amount为额外赠送，不要求两者之和等于回款金额。 | crm_recharge:import + billing:recharge |

所有CRM镜像查询强制 `corp_id==settings.crm_corp_id`。绑定/候选/导入先用customer_scope_user_id确定中台客户可见范围；绑定目标必须是当前有效企业的CRM镜像、且上游客户详情仍可读；将HTTP校验放事务外，事务内再锁客户和CRM候选行并复查唯一占用。同一已绑定ID重复保存幂等成功；候选被其他客户占用→409“该CRM客户已绑定其他中台客户”，不泄露越权客户名称。绑定持有客户行锁，与导入对目标客户相同锁序协调；解绑/换绑不修改历史充值归属。软删除的中台客户不占新绑定唯一位，但历史回款唯一导入约束始终有效。普通客户编辑/批量编辑/Excel不接受crm_customer_id修改，绑定唯一写入口是此API。

推荐完全在客户镜像中运行，无现成CRM外部推荐实现，故新增专用评分函数：NFKC→casefold→移除Unicode空白与标点，保留数字汉字字母，不擅自剥除地域或公司后缀。规范名完全相等score=1；非空包含关系score=`0.8+0.19*min_len/max_len`；其余用标准库difflib.SequenceMatcher(autojunk=False).ratio()*0.79。推荐过滤score<0.35，再按score降序、external_id升序，返回top10；同名多条均展示，绝不自动绑定，空规范名返回空列表不推荐全部。关键词搜索≤200字符、清空query回推荐；候选已被其他客户占用显示不可选（不带其他客户资料）。仅本地候选查询不触发上游、不写镜像。目录为空时返回空列表和“CRM客户目录尚未同步，请管理员先同步”，而不是报无匹配或偷偷请求前端直连CRM。

支付列表行级可见性：有customers:view_all可看未绑定和全部匹配回款；否则INNER JOIN当前绑定Customer并强制 manager_id==uid OR sales_manager_id==uid，未绑定/他人客户的回款、金额及总数全部不可见；已导入行按RechargeRecord.customer_id做可见性，不因后来解绑换绑改变历史归属。详情、导入直接传ID同样校验；新权限不绕过客户范围。同步与企业级进度只给具备view_all且crm_recharge:sync者。

`backend/scripts/seed.py::ALL_PERMISSIONS` 新增四码：`customers:crm_bind`（绑定CRM客户，module=customers）、`crm_recharge:view`（查看CRM回款）、`crm_recharge:sync`（同步CRM回款）、`crm_recharge:import`（导入CRM充值），后三者module=crm_recharge。默认只通过超管全权限获得，不自动授予运营/销售预置角色；自定义角色由管理员配置。同步 `backend/tests/_test_data.py::PERMISSION_ROWS`、前端permissionGroups的MODULE_NAME_MAP/MODULE_ORDER，展示“CRM充值管理”。上线用现有 `seed.py --sync-permissions`，不新建fix脚本。

### 5. 原子充值与业务日期统一切换

修改已读 `BalanceService.recharge` 为无提交的事务内记账函数，完整签名指定：

```python
async def recharge(
    self,
    customer_id: int,
    real_amount: Decimal,
    bonus_amount: Decimal,
    operator_id: int,
    payment_proof: str | None = None,
    remark: str | None = None,
    *,
    recharge_date: date | None = None,
    crm_payment_id: int | None = None,
) -> RechargeRecord:
```

其前置为调用方已有 `async with db_session.begin():`；若无事务则拒绝而不是私自commit。先锁Customer行，再用PostgreSQL INSERT customer_balances ON CONFLICT(customer_id) DO NOTHING保证无余额行首次并发只创建一行，随后SELECT CustomerBalance FOR UPDATE（populate_existing=True避免预读ORM旧值），写金额/记录后flush、不commit/rollback、不做外部HTTP。遇到soft-deleted余额行不另建重复FK：用同customer_id原行且非零历史余额时拒绝操作并报告需核对；全零软删行恢复deleted_at=None再充值，保持单行唯一。所有金额运算Decimal并校验NUMERIC(12,2)溢出；手动/Excel保留现有允许负值及赠金的行为，CRM实充等于正的源回款、赠送可额外填写但必须非负。不照抄consume的“先提交调用方事务”模式，不扩大到其他扣款流程重构。

迁移全部生产调用：LSP本轮证明手动只有 `backend/app/routes/billing/balances.py::recharge`；另将 `BalanceService.batch_import_recharge` 内重复的记账代码改调用recharge，唯一调用为 `backend/app/routes/billing/imports.py::import_balance`。手动路由和Excel路由分别拥有外层事务；开始写事务前结束由权限/预检引发的只读autobegin（仅这些已审计为无写入的阶段允许 `await db.rollback()`，先把身份/解析数据复制为标量），然后在显式begin内重新执行可见性/客户存在性关键检查；禁止直接rollback未知调用方脏数据。Excel外层begin中每行用begin_nested savepoint隔离错误并保留现有逐行success_count/errors语义，移除service统一commit和失败后继续使用已失效session。手动/Excel审计采用已读create_audit_entry(auto_commit=False)在外层事务内写入；after/before捕获Decimal标量，不持共享ORM对象快照。成功提交后才清缓存，响应契约保持兼容。

新增 `CrmRechargeService.import_payment(payment_id: int, customer_id: int, real_amount: Decimal, bonus_amount: Decimal, operator_id: int, scope_user_id: int | None, ip_address: str | None) -> dict`，由CRM路由拥有事务。路由拒绝布尔/非字符串金额、空字符串、NaN/Infinity、负数及超过2位小数，Decimal从字符串解析，不四舍五入掩盖错误；校验单项、充值合计及入账后各余额均不超过NUMERIC(12,2)上界。步骤固定：

1. 只读查本地payment与既有RechargeRecord（包括软删充值凭据）；已导入且同目标客户、提交实充/赠送等于原充值记录且仍有访问权限→返回原记录、already_imported=true，不访问CRM也不写钱；不同目标或任一金额不同→409“该回款已导入，不能更改客户或充值金额”，不覆盖原赠送。并发后查到原记录也采用同一规则。
2. 未导入时事务外GET源回款详情及行业元数据，验证企业、源ID、回款所属客户/合同、approved、允许行业、正金额及有效日期。源不存在/不可见/HTTP失败→拒绝入账并给可见原因；金额/日期/客户/行业与页面镜像不一致→409“CRM回款已变更，请同步并重新确认”，不静默按新金额导入。
   实时复核通过后必须比较real_amount与源回款amount，数值不等返回400“实充金额必须等于CRM回款金额”；bonus_amount非负且与实充不能同时0。不能用两者合计代替实充与回款核对，不将赠送值写回源镜像amount或imported_snapshot。
3. 结束只读autobegin，进入 `async with db_session.begin():`；锁顺序固定 `Customer FOR UPDATE`→`CrmPayment FOR UPDATE`→余额行。重新查权限/客户有效性、客户price_policy和生效包年规则（复用 `batch_query_package_info`；任一表明包年即拒绝）、绑定仍等于payment.crm_customer_id、企业一致、eligible、source_changed=false、未被其他事务导入；在锁内再次比较实时GET快照与当前锁定镜像的源客户/合同/金额/日期/行业/审批白名单，任一变化409，不能拿事务前ORM旧值直接入账。非绑定客户400，包年400，已停用/已删除客户400。严格指定目标自身余额，不沿settlement_account_id转存另一个客户。
4. 若其他请求已提交同一源回款，按步骤1比较目标与两项金额后返回或409，不能再加款；否则调用事务内recharge(... real_amount=提交实充, bonus_amount=提交赠送, recharge_date=源receive_date, crm_payment_id=payment.id, payment_proof=None, remark=f'CRM回款 {external_id}')；将源白名单复制到imported_snapshot，该快照仅记录CRM源值，赠送由RechargeRecord保存；写审计action='crm_recharge_import'、module='crm_recharge'，包括源回款金额、实充金额、赠送金额、充值合计、源ID、目标客户、充值ID、日期和余额前后快照，全部同一事务。任何写入/审计异常均回滚，唯一约束是最终防线。
5. 提交后沿用现有充值的health/dashboard/customer/billing_consumption缓存失效，同时失效充值趋势所属analytics缓存。缓存失败不得谎报“未充值”诱导人工重复操作；依靠幂等重试返回已入账结果。返回原created_at（真实导入时刻），recharge_date仅格式YYYY-MM-DD，不生成00:00:00伪时刻。

兼容现有危险清理入口：`backend/app/routes/database_management.py::clear_balance_data` 在同一显式事务、任何DELETE和审计之前先 `LOCK TABLE customers IN EXCLUSIVE MODE`，与所有充值先 `Customer FOR UPDATE` 以及新客户INSERT互斥，待活跃充值提交后再检查所有RechargeRecord（包括软删行）是否存在crm_payment_id非NULL；存在即HTTP409拒绝整次清空并提示“存在CRM导入记录，不能清除入账凭据”，余额与消费记录也不能部分删除。无CRM来源时保持原有清空结果，审计和DELETE同一begin提交，提交后失效缓存；不得通过删除crm_payments、清空源关联、软删除过滤绕过。表锁仅用于既有全库危险清理，不加到日常充值。该保护不增加历史核对或新的清理功能。测试以已导入记录存在及与CRM导入并发为输入，证明清空与充值无法交错后丢失导入凭据。

新增日期必须贯穿以下已核实读点，不保留一半按创建时间、一半按业务日期的混合状态：

- `backend/app/routes/billing/balances.py`：最近充值 `MAX(RechargeRecord.created_at)` 的筛选、排序、last_recharge_map全部改recharge_date；`get_balance_stats` 本月用 `[cst月首日, 下月首日)` date范围；导出“最新充值时间”改“最近充值日期”。原last_recharge_at wire字段保持名称但返回YYYY-MM-DD以兼容既有Balance调用方；前端标明日期并按自然日算距上次充值天数，不new Date后转UTC。
- `backend/app/services/analytics.py::get_balance_trend`：充值月份聚合和窗口前充值累计改recharge_date；消费记录时间口径不动；只改变归月、不回放历史扣款，也不重算余额或账单已确认金额。
- `backend/app/services/invoice_excel.py::_query_balance_info`：当期充值改按recharge_date和上海业务日窗口。period_start/end若aware先astimezone(CST)再取date，结束为end的CST日期+1天，使用半开区间；naive则按现有CST约定取date，不直接剥UTC tzinfo。原有已生成文件不自动覆盖；用户主动重新生成时采用新口径，既有结算单金额/消费items不变。
- `backend/app/services/billing.py::get_recharge_records`：列表维持按created_at倒序的操作追溯顺序（同值再按id倒序），这是创建记录浏览，不作为财务归期。响应在 `routes/billing/balances.py::get_recharge_records` 增加recharge_date、crm_payment_id、crm_payment_external_id，保留created_at；关联源数据只传ID，不泄露额外CRM字段。
- `frontend/src/api/billing.ts::RechargeRecord` 与 `frontend/src/types/index.ts::RechargeRecord` 两处类型同时补新字段；`frontend/src/views/billing/components/RechargeRecordModal.vue` 展示“实际充值日期”“创建时间”“来源（CRM回款#ID/手动或Excel）”。`frontend/src/views/billing/components/BalanceTable.vue` 最近充值展示及天数计算与新日期对齐；`frontend/src/composables/useBalance.ts`（已由子代理定位）对应筛选标签统一“充值日期”。
- 实施前用精确grep `RechargeRecord.created_at|recharge_records.created_at` 范围backend确认剩余命中；除创建时间展示、操作记录排序、历史回填迁移/原始审计外，所有用于充值业务归期的命中改recharge_date。用LSP追踪受改签名引用，全部迁移，不保留旧提交式别名。

### 6. 客户编辑与CRM充值管理页面

在已读 `frontend/src/views/customers/detail/EditCustomerDialog.vue` 加“CRM客户绑定”独立区块，覆盖列表和详情两处复用入口；组件新增 `frontend/src/views/customers/components/CrmCustomerBinding.vue`，props=`{customerId:number}`，在打开或customerId改变时重新载入绑定和推荐，清空上次请求结果；300ms搜索防抖，用请求序号丢弃乱序响应。复用既有Arco输入/列表/确认弹窗，不直接复用硬编码getCustomers的CustomerAutoComplete来搜索CRM；它搜的是本地客户，数据源不同，不能误接。

绑定区显示当前名称/CRM外部ID，自动推荐最多10项及匹配百分比、负责人、占用禁用态；支持关键词搜索分页，用户点选后必须点击“确认绑定”，解绑/换绑均确认。绑定操作独立立即保存，文案“绑定独立保存，关闭编辑窗口不会撤销已保存绑定”；这样不改现有CustomerService.update_customer内部提交方式，也不会出现客户信息保存失败但用户不知道绑定已生效。成功后刷新绑定显示并使客户详情缓存失效；无customers:crm_bind者仅显示已有绑定（详情API新增只读字段crm_customer_id/crm_customer_external_id/crm_customer_name，通过现有客户权限读取），不提供候选搜索或操作。候选空/目录未同步/请求失败分别展示，不自动选第一个结果。

新增 `frontend/src/api/crmRecharge.ts`（独立typed函数）与 `frontend/src/views/system/CrmRecharge.vue`。采用既有PageHeader、DataTable、EmptyState、formatCurrency/日期工具和handleError，不新增视觉体系。路由 `/system/crm-recharge`、name='CrmRecharge'、meta.requiresPermission='crm_recharge:view'；同时更新 `frontend/src/router/index.ts`、`frontend/src/components/layout/AppSidebar.vue` 及 `frontend/src/composables/useAppLayout.ts::navSections`，在ERP系统之后放“CRM充值管理”。

页面结构固定：标题+同步月份选择（默认当前CST月）+“同步此月”按钮（仅sync+view_all）；状态区域显示最近完整成功时刻、当前运行阶段/合同扫描进度、失败原因，活跃run时每5秒轮询、页面卸载停止；筛选栏month、keyword、状态（待导入/已导入/不可导入/全部，默认全部）；回款表列：回款ID、CRM客户、绑定中台客户、合同、行业分类、源回款金额、实际回款日期、CRM审批状态、导入状态、创建时间（导入后）、操作。已导入详情展示实充/赠送/充值合计，源金额与充值合计不得混为一个字段。用现有固定操作列样式，不改全局z-index。

每行“导入充值”仅可操作行显示/启用：弹窗只读展示CRM回款ID、行业、源金额、日期、绑定目标名称+company_id；参考 `frontend/src/views/billing/components/RechargeModal.vue` 的双金额表单，实充可填写、默认源回款金额，赠送默认0，均2位小数且min=0；实充不等于源金额时提示“实充金额必须等于CRM回款金额”并禁止确认。实时展示充值合计=实充+赠送，文案“赠送额外增加余额，不从CRM回款金额中扣除；创建时间为本次导入时刻”，勾选“已核对该回款未通过手动或Excel入账”后提交。仅复用已有表单交互模式，不能调用普通充值API绕过CRM原子入口；发送金额前转为两位小数字符串，不添加任意客户下拉。未绑定行提示“请在客户管理中找到指定客户并绑定CRM客户”，绑定后返回刷新即可导入，无需再次同步CRM；包年/停用/源变更/审批异常展示具体原因。取消不写入；提交禁用按钮；成功或already_imported刷新回款行并可打开指定客户的余额充值记录，同时显示实充、赠送、合计、源回款ID及双日期；409展示原导入金额，不自动改值重试。本次只做单笔人工导入，不增加批量或自动充值。

### 7. 验证与上线开关

以下命令是批准后实施阶段执行，本轮未执行代码测试/迁移/真实充值。先以资金TDD覆盖原子性和重复导入，再实现；其余使用现有同类测试结构。后端必须Python3.12.x、项目`.venv/bin/python`，真实PG/Redis使用专用测试实例，绝不让集成fixture连接生产/开发业务库；测试fixture会清表，先核对POSTGRES_DB=customer_platform_test。依赖已存在则不重装。

## 关键文件与非显然锚点

| 已读文件与锚点 | 为什么影响实施 |
|---|---|
| `.trellis/spec/backend/permission-model.md:54-64,114-116` | 新码唯一上线入口是seed sync/部署seed，不使用旧fix脚本。 |
| `backend/app/utils/audit_helpers.py::create_audit_entry` | auto_commit=False已现成可用，让资金、源关联和审计同事务。 |
| `backend/app/repository/balance_repo.py::get_or_create` | 仅查后建，无锁且首次并发可能唯一冲突，不能直接作为CRM安全记账基础。 |
| `backend/app/services/invoice_excel.py::_query_balance_info:262-277` | 原created_at与aware period的处理不适用于新业务date，必须转CST自然日再筛选。 |
| `frontend/src/composables/useAppLayout.ts::navSections` | 另一套导航数据源，单改AppSidebar会漏部分布局的菜单。 |

## 验证：输入、预期结果与执行命令

### 已完成调研验证结果

真实认证成功、企业ID匹配；客户精确/子串搜索成功；客户/合同100条分页生效；合同回款空列表、非空列表、详情均成功；已取得approved且房产经纪/老业绩的正样本及applying的负样本。全局回款列表在独立版页面host与返回api_host均失败，故不作为上线依赖。未证明账号拥有企业全部数据权限、未完整扫描5032客户/7117合同、未读取当月全部符合记录、未执行任何真实充值；不把有界抽样说成全量核对。

### 必须通过的行为证据

| 检查 | 固定输入/情境 | 可观测验收 |
|---|---|---|
| 行业与审批 | 房产经纪根/新业绩/老业绩、新房开发；另公共安全、applying | 前四者在当月approved时可导入，另两者不可；斜杠路径不漏老业绩，不能按客户所属行业判断。 |
| 全分页 | mocked外部103个客户、101个合同，第二页历史合同含当月approved回款，所有记录独立ID | 该回款出现在镜像；第一页/绑定客户预过滤实现会使测试失败。中途业务code500则run=failed且不报告本月空成功。 |
| 月界 | 2026-11-01、2026-11-30、2026-12-01三笔；另10月回款11月审批 | 11月同步只前两笔；10月只有手动选择10月同步才能补取，自动任务不悄悄改成上月+当月。 |
| 绑定并发 | 两个存活中台客户同时绑定同一CRM客户；另一请求越权customer_id | 仅一方成功，另一409；越权403且返回中无其他客户姓名。解绑后可重绑，但原已导入源仍不能再入账。 |
| 候选排序 | 客户名='测试公司A'，候选同名、包含名、轻微错字、无关名；输入空白/清空 | 确定顺序、top10阈值、相似候选由人选择；打开编辑无自动绑定；切换客户不残留上一次候选。 |
| 原子双金额入账 | 初始real=1000、bonus=50；CRM回款200，填写实充200、赠送40，回款日2026-10-31，11月执行 | 余额real=1200、bonus=90、total=1290；唯一充值记录real=200、bonus=40、合计240，recharge_date=2026-10-31、created_at为执行时刻；源amount仍为200；审计及源关联同时存在。审计/flush失败则全部不变。 |
| 重试与并发 | 同回款并发两次导入；不同回款各200/300并发充值同客户；另手动100与CRM200并发 | 同源只加一次并返回同充值ID；异源都不丢账；手动与CRM合计正确；余额尚无记录时也不出现两个余额行或丢款。 |
| 幂等赠送保护 | 同一回款200/40成功后重试200/40，再请求200/60；另200/40与200/60并发 | 同值重试返回原ID，不再加实充或赠送；改赠送返回409；并发只有一组金额成功，另一组409，原赠送不被覆盖。 |
| 同步与绑定分离 | 同步两条符合条件回款，一条未绑定；刷新、重复同步；绑定后取消一次导入，再确认200/40 | 管理员默认全部列表能看到两条及未绑定提示；同步/绑定/取消阶段余额和充值记录均不变；绑定后无需重同步即可导入，成功仅新增一条双金额充值。 |
| 入账门槛 | CRM回款200，填写实充160/赠送40；另负数、两项0、NaN、超精度/超范围、伪造日期、未绑定/错目标/包年/停用/删除、上游撤审/源变更 | 160+40虽等于200仍拒绝，因为实充不等于源金额；其余均拒绝且无半成功。填写200/0和200/40均可成功；负赠送不照搬手动扣减；源变化须重新同步确认。 |
| 业务日期切换 | 10月31日实充200+赠送40在11月导入；11月1日另实充300+赠送60 | 最近日期=11月1日；11月充值统计仅归入该月300实充+60赠送，10月归入200实充+40赠送；各现有统计的实充/赠送/合计指标维持原加总定义，仅归期切换；created_at不变。 |
| CST边界 | period_start=2026-10-31T16:00:00Z、period_end=2026-11-30T15:59:59Z | 业务窗口11月1日至11月30日，11月1日/30日都包含，10月31日不包含；不偏移8小时。 |
| 已导入源变更 | 导入200后源变300/撤审，同步再次执行 | 原充值200和日期不变，source_changed展示；重试不补100、不再加200，不自动退款。 |
| 调度与长任务 | 注入CST 2026-11-30 22点触发，run运行超过30分钟且heartbeat持续；另两个worker重复触发 | month=2026-11-01且仍running；只有一个run获得执行权；超过2分钟无heartbeat的任务可被恢复为failed，手动重跑镜像幂等。 |
| 权限隔离 | 无模块权限用户、仅view用户、仅import无billing:recharge用户、无view_all的业务用户 | 无权直连403；view无写入；import需充值权限；业务用户看不到未绑定/他人回款及金额/总数；超管正常。 |
| 迁移回填 | 一条迁移前created_at='2026-10-31 23:59:00'的充值 | upgrade后recharge_date=2026-10-31且created_at字节语义未变；迁移可在隔离库upgrade/downgrade；非空/唯一约束实际生效。 |

新增永久测试限定于高风险消费者行为：`backend/tests/unit/test_crm_recharge.py`（行业/评分/分页失败）、`backend/tests/integration/test_crm_recharge_api.py`（上述真实PG事务、并发、权限、日期）、在既有billing/invoice_excel集成文件添加跨月回归，并在既有migration测试中覆盖新列。测试中的CRM响应使用脱敏结构化fixture，不能用生产凭据或实时CRM决定通过；HTTP客户端用httpx.MockTransport测业务code/分页错误，不写只断言“调用过某mock”的透传测试。前端新增 `frontend/src/views/system/__tests__/CrmRecharge.test.ts` 与绑定组件测试，只测人选绑定、确认导入、越权禁用和乱序搜索可见结果，不测试样式字符串。

```bash
# 工作目录：backend；Python须3.12.x，PG localhost:5432和专用Redis已启动。
# POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_HOST由本地测试配置提供；先确认测试库，不得指向业务库。
POSTGRES_DB=customer_platform_test .venv/bin/python -m pytest tests/unit/test_crm_recharge.py tests/unit/test_billing_service.py tests/unit/test_permission_drift.py tests/unit/test_route_names.py -q
POSTGRES_DB=customer_platform_test .venv/bin/python -m pytest tests/integration/test_crm_recharge_api.py tests/integration/test_billing_api.py tests/integration/test_billing_import_export_api.py tests/integration/test_invoice_excel.py -q
POSTGRES_DB=customer_platform_test .venv/bin/python -m pytest tests/integration/test_migrations.py -q

# 工作目录：frontend；复用已安装依赖。
npx vitest run src/views/system/__tests__/CrmRecharge.test.ts src/views/customers/components/__tests__/CrmCustomerBinding.test.ts src/views/billing/components/__tests__/RechargeRecordModal.consumption.test.ts src/views/billing/components/__tests__/BalanceTable.test.ts src/composables/__tests__/useBalance.test.ts
```

浏览器实际验收不只跑类型检查：在隔离开发库应用迁移和权限sync后，后端沿现有命令 `.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`，前端 `npm run dev -- --port 5173`；使用browser打开5173，管理员完成“手动同步测试月→客户列表编辑→查看推荐→搜索并绑定→CRM列表确认一条→余额记录查看双时间→重复点击不重复入账”，再以非超管检查菜单/越权/绑定冲突。开发验收使用隔离CRM测试数据源或HTTP stub，不把生产CRM记录充值进开发业务库；生产联通验收只读，真实资金导入只能由业务明确选定且线下核对过的回款执行。保存主页面、确认框和余额双时间截图；宽屏和窄屏检查横滚、固定操作列不越过Header，状态/金额不折叠误读。

上线前先在隔离库验收，再注入 `CRM_CREDENTIAL_KEY`，CRM_ENABLED保持false完成迁移与权限同步（`scripts/seed.py --sync-permissions` 会新增 `crm_recharge:config`）；由管理员校验该CRM账号具备企业全量客户/合同/回款读取权限及开放API授权（5032/7117只是本次可见计数），确认限频额度未被其他集成占满。随后启用开关并手动跑当月完整同步，检查run=succeeded和页面数量；业务完成存量账线下核对后才使用导入按钮。同步失败不得启用“自动充值”（本功能始终没有自动充值）。验收记录必须落仓库任务笔记，写明目标、实际变更文件、上述已执行命令/输出/截图位置和通过/失败；本计划的抽样结果不能充当实现后的测试证据。

## 假设与已决定的应对

- 用户已选严格一对一、业务日期归期、当月自动+手动历史月、CRM禁包年、存量线下核对；若要改变须更新本文件及受影响验收，不允许实现者自行放宽。
- 实际回款仅有日期，故永久字段选DATE而非编造时分秒；若供应商返回新增真实时刻，本次仍使用receive_date自然日，不擅自改接口精度。
- 供应商全局列表当前code500，本方案不依赖其修复；合同下接口即使较慢也保持全量语义。若正式账号看不到全企业数据，必须先补CRM权限，不能以“当前账号可见”悄悄替代“全部内容”宣称交付。
- 在合同下回款分页/详情遇到未验证结构时按明确failed/blocked处理；保留已读镜像、不入账、不以0/空日期/跳页假成功。核心字段不可获取属于外部前提缺失，给出具体失败接口和run证据后停止启用充值，而非交付假数据。
- 上游在实时复核结束与本地事务提交之间仍可能被CRM人员改动：两个独立系统无分布式事务，本次以人工确认后最近一次成功GET的业务快照入账；后续同步标出变化、不自动冲正。数据库幂等确保本地最多一次，不宣称跨系统完全串行一致。
- 本轮是调研与实施设计，未改工作树、未运行迁移/构建/测试、未真实充值。最终验收边界为本文件列出的绑定、全量月度同步、人工原子入账、双时间和关联统计，不以只完成页面或只拉第一页为完成。

## 本轮交付验收记录

- 验收目标：产出经过真实只读接口验证、覆盖用户已确认业务决策的完整功能与实施设计，不交付业务实现。
- 实际文件：`local://crm-recharge-plan.md`。当前规划模式禁止写入仓库，尝试持久化仓库方案被工具拒绝；获准进入实施后应先将本方案归档到 `docs/specs/2026-11-11-crm-recharge-management-plan.md` 并建立规范任务文件。
- 已执行验证：真实登录企业匹配；客户名称精确/子串查询；客户详情存在性；客户/合同100条分页容量；合同下回款列表与详情；回款行业元数据及approved/applying正负样本；全局回款列表在两个主机的失败边界。结果与接口路径记录在本文件调研章节。
- 最终结论：调研和设计已完成；合同下主链路抽样可行，全局回款入口本次不可用。未证明企业全量权限，未完成月度全量扫描，未运行实现后的原子充值/并发/迁移/UI验收，不能宣称功能已实现或测试通过。
- 可复核方式：通过授权密钥配置，按本文件官方资料、接口路径和筛选字段只读复查；不保存或依赖对话内敏感值。接口现状可能变化，以复查结果为准。

### 本轮核心流程复核

- 已读取现有充值弹窗与BalanceService.recharge源码，核实实充/赠送分别记账、总余额相加的现有行为；仅参考双金额交互，不复制手动充值的负数扣减规则。
- 已确认并写入：同步所有符合原筛选条件的当月回款，未绑定不漏；人工到客户管理绑定，返回逐笔确认；实充对应源回款，赠送额外增加；成功后指定客户余额管理出现一条双金额、双日期、CRM来源可追溯的充值记录。
- 本轮为规划复核，未修改业务文件，未执行实现测试或真实充值；新增验收用例覆盖同步不入账、绑定后无需重同步、赠送额外入账、重复提交不重复赠送、修改已导入金额409拒绝。
