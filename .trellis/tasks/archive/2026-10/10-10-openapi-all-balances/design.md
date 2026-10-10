# 技术设计: 开放平台「获取所有客户余额」接口

## 1. 变更边界

**行为缺口**: 开放平台仅支持按 ERP 渠道查询余额（`/api/v1/erp/balances`），缺少全量客户余额能力；且新路径需与 `erp` 平级，认证中间件的 API-Key 前缀仅覆盖 `/api/v1/erp/`。

**改动文件与理由**:

| 文件 | 改动 | 必要性 |
| --- | --- | --- |
| `backend/app/middleware/auth.py` | `OPENAPI_PREFIX` 单字符串 → 多前缀匹配 | 新路径必须走 API-Key 认证，否则 401 JWT 拦截 |
| `backend/app/routes/openapi.py` | 新增蓝图 + `GET /balances` 路由；抽取公共查询构建 | 接口实现本体；复用余额/过滤逻辑防漂移 |
| `backend/app/main.py` | 注册新蓝图 | 新路由生效前提 |
| `backend/tests/integration/test_openapi_api.py` | 新增集成测试（首次为开放平台接口补测） | 验收与回归保障 |
| `openapi-docs/docs/api-reference/all-balances.md` | 新增文档页 | 用户需求（补充开放平台 API 文档） |
| `openapi-docs/docs/api-reference/index.md` | 索引加行 | 文档一致性 |
| `openapi-docs/docs/.vitepress/config.ts` | sidebar 加条目 | 文档站导航 |
| `openapi-docs/docs/changelog.md` | 变更记录 | 文档站约定 |

**明确不做**: 不改 `/api/v1/erp/balances` 语义；不加分页；不动前端；不加数据库字段/迁移。

## 2. 路由设计

现有 `openapi_bp` 以 `url_prefix="/api/v1/erp"` 注册。新接口 `GET /api/v1/balances` 与 `erp` 平级，**保留现有蓝图不动**，新增独立蓝图：

```python
# openapi.py
openapi_customer_bp = Blueprint("open_platform_customer", url_prefix="/api/v1")

@openapi_customer_bp.get("/balances")
async def get_all_customer_balances(request: Request): ...
```

`main.py` 追加 `app.blueprint(openapi_customer_bp)`。

## 3. 认证改造（auth.py）

```python
# 开放平台 API 路径前缀，使用 API-Key 认证而非 JWT
OPENAPI_PREFIXES = ("/api/v1/erp/", "/api/v1/balances")

# 在 authenticate() 中
if request.path.startswith(OPENAPI_PREFIXES):
    return await _authenticate_api_key(request, app)
```

- `str.startswith` 接受元组；`/api/v1/balances` 前缀同时覆盖未来可能的子路径。
- 与内部 JWT 接口（`/api/v1/billing/balances` 等）不冲突：`startswith("/api/v1/balances")` 不会命中 `/api/v1/billing/...`。
- 现有 `/api/v1/erp/` 行为不变。

## 4. 查询逻辑（复用，防漂移）

抽取公共构建函数，渠道过滤可空：

```python
def _build_customer_balance_stmt(erp_channel: str | None = None):
    stmt = (
        select(
            Customer.company_id,
            Customer.name,
            CustomerBalance.total_amount,
            CustomerBalance.used_total,
        )
        .select_from(
            outerjoin(Customer, CustomerBalance, Customer.id == CustomerBalance.customer_id)
        )
        .where(
            Customer.deleted_at.is_(None),
            Customer.is_disabled.isnot(True),
        )
        .order_by(Customer.company_id.asc())
    )
    if erp_channel:
        stmt = stmt.where(Customer.erp_system == erp_channel)
    return stmt
```

- `get_erp_balances` 改为调用 `_build_customer_balance_stmt(erp_channel)` —— 行为逐字节不变（回归路径）。
- `get_all_customer_balances` 调用 `_build_customer_balance_stmt()` —— 无渠道过滤，即"全部有效客户"。
- 响应组装（`balance = round(total - used, 2)`、`str(company_id)`）两路由共用同一格式化逻辑，与既有响应结构一致。

## 5. 测试设计（integration）

fixture 构造: 通过 `ApiKeyService.create_key()` 生成 API-Key（测试库真实入库）；造多渠道客户 + 无 ERP 客户 + 软删除/停用客户 + 有/无余额客户。

| 用例 | 断言 |
| --- | --- |
| 无 Authorization 头 | 401 + `40104` |
| 无效 API-Key | 401 + `40104` |
| 有效 Key 请求全量 | 200、`code=0`、返回所有有效客户（含无 ERP）、`balance` 计算正确（含无余额=0.0）、按 company_id 升序 |
| 软删除 / 停用客户 | 不出现在 data 中 |
| 渠道接口回归 | `GET /api/v1/erp/balances?erp_channel=xxx` 仅返回该渠道客户 |

测试文件遵循 `backend/tests/integration/` 现有约定（`test_client`、`db_session` fixture；用例内清理数据）。

## 6. 文档设计

- 新文档页 `all-balances.md`（标题「客户余额查询（全量）」），结构对齐 `erp-balances.md`：接口信息表（路径 `/api/v1/balances`、认证、数据来源 `backend/app/routes/openapi.py`）、请求参数（仅认证头）、curl / Python 示例、响应参数与示例、错误码表、与渠道版接口的差异说明。
- `index.md` 接口索引表新增一行；`config.ts` sidebar 在「API 参考」下加条目；`changelog.md` 按现有格式追加一行。

## 7. 兼容性与回滚

- **兼容性**: 新接口纯增量；认证前缀扩展对既有 `/api/v1/erp/` 无影响；内部路径无冲突。
- **回滚**: 回退分支即可；无数据库迁移涉及。
