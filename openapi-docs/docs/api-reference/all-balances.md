# 客户余额查询（全量）

获取全部客户的客户 ID、客户名称和当前可用余额列表，不限定 ERP 渠道。

## 接口信息

| 项目 | 说明 |
| --- | --- |
| 方法 | `GET` |
| 路径 | `/api/v1/balances` |
| 认证 | 必填（`Authorization: Bearer {api_key}`） |
| 数据来源 | `backend/app/routes/openapi.py` |

## 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `Authorization` | Header | string | 是 | 认证令牌，格式：`Bearer {api_key}` |

::: tip 与渠道版接口的区别
本接口与 [ERP 渠道客户余额查询](/api-reference/erp-balances) 响应结构一致，区别在于**不传 `erp_channel`**：返回全部有效客户（含未绑定 ERP / `noerp` 客户），适用于一次获取全量余额的场景。
:::

## 请求示例

curl：

```bash
curl -X GET \
  "https://customer-staging.jiazoushi.com/api/v1/balances" \
  -H "Authorization: Bearer vk_your_api_key_here"
```

Python：

```python
import requests

resp = requests.get(
    "https://customer-staging.jiazoushi.com/api/v1/balances",
    headers={"Authorization": "Bearer vk_your_api_key_here"},
)
print(resp.status_code)
print(resp.json())
```

## 响应参数

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `code` | number | 错误码，`0` 表示成功 |
| `message` | string | 提示信息 |
| `data` | array | 客户余额列表 |
| `data[].customer_id` | string | 客户在 ERP 系统中的企业 ID（company_id） |
| `data[].customer_name` | string | 客户名称（企业全称） |
| `data[].balance` | number | 当前可用余额（总金额 - 已用金额，保留两位小数） |

::: tip 口径说明
返回**全部有效客户**（未删除、未停用，不限 ERP 渠道，含无 ERP / `noerp` 客户）；无余额记录的客户 `balance` 为 `0.0`；列表按 `customer_id` 升序排列。
:::

## 响应示例

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "customer_id": "615",
      "customer_name": "北京金诚阜业房地产经纪有限公司",
      "balance": 100000.0
    },
    {
      "customer_id": "1552",
      "customer_name": "荣城地产",
      "balance": 0.0
    }
  ]
}
```

## 本接口错误码

| 错误码 | 含义 | HTTP 状态 |
| --- | --- | --- |
| `40104` | API-Key 无效或已停用 | 401 |
| `40105` | API-Key 已过期 | 401 |
| `50000` | 服务器内部错误 | 500 |
