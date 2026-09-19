# ERP 渠道客户余额查询

获取指定 ERP 渠道下所有企业的客户 ID、客户名称和当前可用余额列表。

## 接口信息

| 项目 | 说明 |
| --- | --- |
| 方法 | `GET` |
| 路径 | `/api/v1/erp/balances` |
| 认证 | 必填（`Authorization: Bearer {api_key}`） |
| 数据来源 | `backend/app/routes/openapi.py` |

## 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `erp_channel` | Query | string | 是 | ERP 渠道编码，如巧房传 `qiaofang` |
| `Authorization` | Header | string | 是 | 认证令牌，格式：`Bearer {api_key}` |

## 请求示例

curl：

```bash
curl -X GET \
  "https://customer-staging.jiazoushi.com/api/v1/erp/balances?erp_channel=qiaofang" \
  -H "Authorization: Bearer vk_your_api_key_here"
```

Python：

```python
import requests

resp = requests.get(
    "https://customer-staging.jiazoushi.com/api/v1/erp/balances",
    params={"erp_channel": "qiaofang"},
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

失败响应（缺少必要参数）：

```json
{
  "code": 40004,
  "message": "缺少必要参数: erp_channel"
}
```

## 本接口错误码

| 错误码 | 含义 | HTTP 状态 |
| --- | --- | --- |
| `40004` | 缺少必要参数 `erp_channel` | 400 |
| `40104` | API-Key 无效或已停用 | 401 |
| `40105` | API-Key 已过期 | 401 |
| `50000` | 服务器内部错误 | 500 |

## 渠道编码对照表

以下为当前系统中已配置的 ERP 渠道编码，与「系统管理 → ERP 系统」页面中的配置保持一致：

| ERP 系统 | 渠道编码 |
| --- | --- |
| 无 | `noerp` |
| 鼎尖 | `dingjian` |
| 易遨 | `yiao` |
| 房信 | `fangxin` |
| 房管家 | `fangguanjia` |
| 好房通 | `haofangtong` |
| 上海梵讯 | `shanghaifanxun` |
| 巧房 | `qiaofang` |
| 房融 | `fangrong` |
| 云享 | `yunxiang` |
| 自研 | `self` |
| 房在线 | `fangzaixian` |
