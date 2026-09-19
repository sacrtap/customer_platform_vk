# 快速开始

欢迎使用客户运营中台开放平台。本文档帮助你在 5 分钟内完成首次 API 调用。

## 1. API 基础信息

| 项目 | 说明 |
| --- | --- |
| API 基础路径 | `https://customer-staging.jiazoushi.com/api/v1/erp` |
| 请求方式 | `GET` / `POST` / `PUT` / `DELETE`（以接口说明为准） |
| 数据格式 | JSON（`Content-Type: application/json`） |
| 字符编码 | UTF-8 |
| 认证方式 | API-Key（`Authorization: Bearer {api_key}`） |

## 2. 获取 API-Key

1. 登录客户运营中台。
2. 进入「系统管理 → **API-Key 管理**」页面。
3. 点击「创建」，填写名称（必填）、描述与过期时间（可选）。
4. 创建后，完整密钥（`vk_` 开头）**仅在此时展示一次**，请立即复制并妥善保存。

::: warning 安全提示
密钥不再展示第二次。如丢失，请停用后重新创建。
:::

## 3. 发起首次请求

```bash
curl -X GET \
  "https://customer-staging.jiazoushi.com/api/v1/erp/balances?erp_channel=qiaofang" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Python 示例：

```python
import requests

resp = requests.get(
    "https://customer-staging.jiazoushi.com/api/v1/erp/balances",
    params={"erp_channel": "qiaofang"},
    headers={"Authorization": "Bearer YOUR_API_KEY"},
)
print(resp.json())
```

## 4. 统一响应结构

所有接口返回统一 JSON 结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

- `code`：`0` 表示成功，非零表示失败（详见[错误码说明](/guides/error-codes)）。
- `message`：人类可读的提示信息。
- `data`：业务数据，结构随接口不同。

## 下一步

- 了解[认证方式](/guides/authentication)的完整说明
- 查看[接口索引](/api-reference/)开始对接
