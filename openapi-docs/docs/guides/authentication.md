# 认证方式

开放平台 API 使用 **API-Key** 进行认证，所有接口请求必须携带有效的 API-Key。

## 1. 获取 API-Key

API-Key 由系统管理员在客户运营中台内创建：

1. 登录客户运营中台，进入「系统管理 → **API-Key 管理**」页面。
2. 点击「创建」，填写以下信息：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| 名称 | 是 | 用于标识 Key 的用途，如「巧房 ERP 对接」 |
| 描述 | 否 | 补充说明 |
| 过期时间 | 否 | 留空表示长期有效；设置后到期自动失效 |

3. 创建成功后，系统返回完整密钥，形如 `vk_xxxxxxxxxxxxxxxxxxxx`。

::: danger 重要
完整密钥**仅在创建时展示一次**，关闭弹窗后无法再次查看。请立即复制并安全保存。
:::

## 2. 传递方式

每个请求必须在请求头中携带 `Authorization`：

```
Authorization: Bearer {api_key}
```

curl 示例：

```bash
curl -X GET \
  "https://customer-staging.jiazoushi.com/api/v1/erp/balances?erp_channel=qiaofang" \
  -H "Authorization: Bearer vk_your_api_key_here"
```

Python 示例：

```python
import requests

headers = {"Authorization": "Bearer vk_your_api_key_here"}
resp = requests.get(
    "https://customer-staging.jiazoushi.com/api/v1/erp/balances",
    params={"erp_channel": "qiaofang"},
    headers=headers,
)
print(resp.json())
```

## 3. API-Key 状态

| 状态 | 说明 | 认证结果 |
| --- | --- | --- |
| 启用中 | 可正常调用 | 通过 |
| 已停用 | 在管理页面手动停用 | 拒绝（`40104`） |
| 已过期 | 超过设置的过期时间 | 拒绝（`40105`） |
| 已删除 | 在管理页面删除 | 拒绝（`40104`） |

在「API-Key 管理」页面可随时**停用 / 启用 / 删除**密钥，变更即时生效。

## 4. 安全注意事项

- API-Key 只应在服务端保存与使用，**严禁**暴露在浏览器前端代码、Git 仓库或日志中。
- 不要将密钥分享给无关人员；不同合作方建议使用独立密钥，便于审计与隔离。
- 如怀疑密钥泄露，请立即在管理页面**停用**该 Key 并重新创建。
- 建议为密钥设置过期时间，定期轮换。

## 5. 认证失败错误码

| 错误码 | 含义 | HTTP 状态 |
| --- | --- | --- |
| `40104` | API-Key 无效或已停用 | 401 |
| `40105` | API-Key 已过期 | 401 |

错误响应示例：

```json
{
  "code": 40104,
  "message": "API-Key 无效"
}
```
