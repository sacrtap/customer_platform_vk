# 余额白名单备注 — 技术设计

## 架构与边界

跨层最小改动，数据流自底向上：

```
balance_whitelists 表（新增 remark 列，String(200) NULL）
  └─ BalanceWhitelist 模型（remark: Mapped[str | None]）
       └─ BalanceWhitelistService
            ├─ get_all()  → 每条 item 增加 "remark"
            └─ update(id, static_balance, remark=..., remark_provided=...) → 写 remark
                 └─ PUT /api/v1/balance-whitelists/<id>（解析/校验 remark）
                      └─ frontend api updateBalanceWhitelist(id, static_balance, remark?)
                           └─ BalanceWhitelist.vue：新增「备注」列 + 编辑弹窗备注输入
```

边界：仅管理页 CRUD 路径；不触碰开放平台 `/api/v1/balances`、批量导入、结算链路。

## 数据模型

`balance_whitelists` 新增列：

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| remark | String(200) | nullable | 备注；NULL 表示无备注 |

- 历史行迁移后为 NULL（无备注），语义正确。
- 选择 `String(200)` 而非 `Text`：与 200 字符上限强一致，DB 层兜底。

## 后端 API 契约

### `GET /api/v1/balance-whitelists`
item 增加字段：`remark: string | null`。其余不变。

### `PUT /api/v1/balance-whitelists/<id>`
Request Body:
- `static_balance`: number (required，行为不变)
- `remark`: string | null (optional)

语义（区分「未传」与「传空」）：
- body 不含 `remark` 键 → **不改备注**（向后兼容旧前端/调用）。
- `remark` 为 `null` 或去空白后为空串 → 存 `NULL`（清空）。
- `remark` 去空白后长度 > 200 → 400 `INVALID_FORMAT`「备注最长 200 字符」。
- 合法值 → strip 后存原样（保留内部空格）。

Response data 增加 `remark` 字段（与列表一致）。

实现要点：路由用 `"remark" in data` 判定是否提供；服务 `update()` 增加参数，例如
`update(id, static_balance, remark: str | None = None, remark_provided: bool = False)`，
仅当 `remark_provided` 为真时写库。校验放在路由或服务内静态方法 `_normalize_remark()`（与余额校验风格一致）。

## 前端契约

- `types/index.ts` `BalanceWhitelistItem` 增加 `remark: string | null`。
- `api/balanceWhitelist.ts`：`updateBalanceWhitelist(id, static_balance, remark?: string | null)`，
  body 始终带 `remark` 键（编辑弹窗必填语义为「以当前弹窗值为准」，含清空）。

## 兼容性与迁移

- alembic 迁移 `down_revision = "w2x3y4z5a6b7"`（当前 head）。
- 测试库按 ORM metadata 自动补列（提交 `6f53fe5`），pytest 前不依赖手工执行迁移。
- 旧客户端不传 `remark` → 备注保持，不受影响。

## 权衡

- 「未传 vs 传空」双语义避免旧调用误清空备注；代价是路由需显式判定键存在。
- 备注不进搜索索引：需求未要求，避免过度设计。
