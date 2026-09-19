# API 参考

开放平台对外提供标准 RESTful API，全部接口均需携带 API-Key 认证（见[认证方式](/guides/authentication)）。

## 接口索引

| 接口 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| [ERP 渠道客户余额查询](/api-reference/erp-balances) | `GET` | `/api/v1/erp/balances` | 返回指定 ERP 渠道下所有企业的客户 ID、名称和当前余额 |

::: tip 扩展说明
开放平台 API 持续建设中。新增接口将在此索引中同步更新，并在[变更日志](/changelog)中记录版本变化。
:::

## 公共约定

- **基础路径**：`https://customer-staging.jiazoushi.com/api/v1/erp`
- **认证**：所有接口必须携带 `Authorization: Bearer {api_key}` 请求头
- **响应结构**：统一为 `{ code, message, data }`，`code = 0` 表示成功
- **错误码**：见[错误码说明](/guides/error-codes)
