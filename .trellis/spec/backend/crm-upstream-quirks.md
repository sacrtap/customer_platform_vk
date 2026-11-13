# CRM 上游接口的已知怪癖（实测）

> 本文记录 CRM 开放 API 与「文档/直觉」不一致、且会直接影响同步耗时或正确性的行为。
> 每条都附实测证据。改动 `app/services/crm_client.py` 或同步策略前先读这里。

## 1. 全局回款列表：只有 `/list` 可用

```
GET /api/v2/received_payments          → HTTP 200 + {"code":500,"error":"no_method_error",
                                          "original_message":"undefined method `received_p...'"}
GET /api/v2/received_payments/list     → {"code":0,"data":{"received_payments":[...],"total_count":1536}}
```

`/received_payments` 是上游服务端 bug（Ruby `undefined method`），任何参数组合都 `code=500`；
`/export`、`/excel`、`/customers/{id}/received_payments` 全部 404。
**不要**为了「官方路径」去调 `/received_payments`，它就是坏的。

## 2. `receive_date` 筛选被服务端忽略

`GET /api/v2/received_payments/filter_sort_group` 声明支持：

```json
{"label":"回款日期","field_name":"receive_date","filter_field_type":"time"}
```

但实际叠加 `receive_date[start]/[end]`（或 `start_date/end_date`、`receive_date=start,end`）
后返回的 `total_count` 与不带日期完全一致 → **服务端不实现该筛选**。
结论：按日期区间请求没有意义，只能拉全量后本地过滤。

## 3. 默认筛选是「待审批」，不是全量

| 参数 | total_count |
|---|---|
| 无参数 | 5（applying 待审批） |
| `approve_status=approved` | 1536 |
| `approve_status=applying` | 5 |

同步必须显式传 `approve_status=approved`，否则只能看到待审批记录。

## 4. 列表项字段够用，但缺自定义字段

`/list` 每项含 `id / contract_id / customer_id / customer_name / contract_title /
receive_date / amount / approve_status`，**不含** `asset_3565dc`（行业分类）。
行业字段只能在详情 `GET /api/v2/contracts/{contract_id}/received_payments/{id}` 取。
因此策略是「全量列表本地筛当月 → 只对当月命中项调详情」。

## 5. 合同 `updated_at` 不能用来判断「本月是否有回款」

实测反例：

```
回款 14421562（2026-11-03）→ contract 29404477.updated_at = 2025-12-18
回款 14427458（2026-11-04）→ contract 29365311.updated_at = 2025-11-23
```

历史合同新增回款**不会**更新合同的 `updated_at`。任何「按合同 `updated_at` 增量同步」
的想法都会漏掉历史合同的本月回款（业务要求不遗漏）。

## 6. 量级与耗时（本租户，2026-11 实测）

| 资源 | 数量 | 备注 |
|---|---|---|
| 客户 | 5032 | `per_page=100`，约 70s |
| 合同 | 7118 | 逐合同拉回款 ≈ 2.4 小时（限流 1.25s/请求） |
| 全量 approved 回款 | 1536 | 16 页，22s |
| 当月 approved 回款 | 14 | 详情 14 次 ≈ 18s |

限流是**全企业串行**（Redis 键 `crm:rate:{corp}`），并发不能提速。

## 7. 同步策略的当前选择

1. 客户全量（必须，用于推荐绑定的 `customer_map`）；
2. 回款：优先 `iter_payments()`（`/list?approve_status=approved` 分页全量 → 本地按当月过滤 → 当月项补详情）；
   **只镜像行业分类属于「房产经纪 / 新房开发」类别（含子级）的回款**，其他行业不入库
   （未导入的直接 `DELETE`，已导入的保留镜像并 `eligible=False`，见 `_delete_out_of_scope_payments`）；
3. `/list` 不可用时自动回退 `iter_contracts()` 逐合同枚举（保底不遗漏，`phase=contracts`）；
4. 未再见到的既有镜像逐笔复核，不因一次未列出认定删除。

实现：`app/services/crm_recharge.py::_sync_month` / `_scan_via_payment_list`，
测试：`tests/unit/test_crm_sync_paths.py`、`tests/unit/test_crm_client_iters.py`。

## 8. 探测方法

用页面已保存的凭据做只读探针（不打印凭据、不落盘 token）：

```bash
cd backend && .venv/bin/python - <<'PY'
import asyncio, psycopg2
from app.utils.crypto import decrypt_secret
from app.services.crm_client import CrmClient

conn = psycopg2.connect("postgresql://localhost/customer_platform"); conn.autocommit = True
cur = conn.cursor(); cur.execute("SELECT corp_id, phone, password_cipher, base_url FROM crm_settings WHERE enabled ORDER BY id DESC LIMIT 1")
corp, phone, cipher, base_url = cur.fetchone()

async def main():
    async with CrmClient(corp_id=corp, phone=phone, password=decrypt_secret(cipher), base_url=base_url) as c:
        print(await c._request("GET", "/api/v2/received_payments/list", {"approve_status": "approved", "page": 1, "per_page": 1}))

asyncio.run(main())
PY
```

需要看 HTTP 状态码与原始 body 时用 `c._http_client.get(...)`（`_request` 会把 `code!=0` 抛成异常并丢掉细节）。

## 9. 字段映射表（2026-11-12 实测，直接照抄，不要凭直觉命名）

### 客户 `GET /api/v2/customers`（每项）

| 业务含义 | 上游字段 | 备注 |
|---|---|---|
| 客户 ID | `id` | 字符串数字 |
| 客户名称 | `name` | 另有 `company_name`（可能为空） |
| **负责人** | **`user_name`** | 另有 `user_id`；**不存在** `owner_name` / `owner.name` |
| 协办人 | `assist_users[]` | 元素含 `id/uid/user_name`，当前未入库 |
| 审批状态 | `approve_status` / `approve_status_i18n` | `approved` / 已通过 |
| 状态/分类 | `status_mapped` / `category_mapped` | |
| 电话 | `phones_data[]` | 元素含 `phone/label` |
| 标签 | `labels[]` | 元素含 `content/color` |
| 地址/联系人 | `address{}` / `contacts[]` | |

> 事故：同步曾用 `owner_name` → `owner.name` 两个兜底，上游都没有，导致 **5032 个客户
> 负责人全部为空**，绑定 CRM 客户页面显示「-」。修复见 `_extract_owner_name`。

### 回款列表 `GET /api/v2/received_payments/list`

`id / title / payment_type_mapped / created_at / amount / receive_date /
approve_status / approve_status_i18n / contract_id / contract_title /
customer_id / customer_name / user{} / receive_user{}`

不含行业自定义字段，需详情补齐。

### 回款详情 `GET /api/v2/contracts/{cid}/received_payments/{pid}`

`id / customer_id / customer_name / contract_id / contract_title / amount /
receive_date / approve_status / updated_at / text_asset_3565dc（行业，UUID 路径）/
text_asset_3565dc_display（行业中文）`

### 合同 `GET /api/v2/contracts`

`id / title / created_at / updated_at / amount / received_payments_amount /
customer_id / customer_name / status_* …`

> `updated_at` 不随新增回款变化（见第 5 节），不能当增量依据。
