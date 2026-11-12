# 运行期配置：页面可维护的第三方凭据

> 适用场景：某个集成（CRM / ERP / 外部 SaaS）原本只能改部署环境变量，现在要让管理员在页面里配置开关与账号密码，并支持更换。

## 契约

| 关注点 | 约定 |
|---|---|
| 存储 | 单行配置表（`name='default'`，唯一约束），字段与集成一一对应；密码字段为 `*_cipher`，只存密文 |
| 加密 | `app/utils/crypto.py` 的 Fernet 加解密；密钥来自部署密钥（本项目 `CRM_CREDENTIAL_KEY`），**绝不入库、不写日志** |
| 缺密钥 | 加密抛 `CryptoNotConfigured` → 接口 400 并说明「未配置 XXX_KEY」，不能静默存明文 |
| 密钥轮换 | 解密抛 `DecryptFailed` → 调用方降级为「无密码」并告警，**不能**因旧密文打不开而 500 |
| 读取 | `app/services/<x>_config.py` 提供同步 `get_config()`：进程内缓存优先，未加载时才回退环境变量 |
| 加载 | `before_server_start` 里 `await load_config(session)`，且**必须注册在 `init_scheduler` 之前**（调度注册依赖生效配置） |
| 保存 | 服务层在调用方事务内写库并刷新缓存；密码语义固定为「留空=保留、有新值=覆盖、显式 clear=清除」 |
| 凭据更换 | 保存后立即删除 `{x}:token:{key}` 之类的上游会话缓存，并重注册/移除依赖开关的定时任务（`apply_<x>_job()`） |
| 返回体 | 接口只回 `password_set: bool` 与打码手机号；禁止任何明文回显 |
| 权限 | 新增 `<module>:config` 权限码，必须同时更新 `scripts/seed.py` 与 `tests/_test_data.py`（`test_test_data_consistency.py` 会校验两者一致性） |
| 验证 | 保存前先做只读自检（登录 + 最小查询），失败默认拒绝落库；`force=true` 二次确认才允许跳过 |

## 前端错误处理陷阱（本项目 axios 拦截器）

`src/api/index.ts` 的响应拦截器把业务错误 reject 成 **普通对象** `{ code, message, category }`，不是 `Error`，也**没有 `error.response`**：

- 取原因用 `error.message`，不要用 `error.response.data.message`；
- 「可强制继续」这类附加信号无法通过响应体 `data` 传递，必须编码成业务错误码（本项目 `42201/42202`，落在 422xx `BUSINESS_ERROR` 段，前端会原样展示后端 message）；
- 组件里 `@click="submit(payload)"` 必须写 `submit(payload)`，直接写 `@click="submit"` 会把 `MouseEvent` 当成第一个参数。

## 测试隔离要求（integ 测试很容易踩）

- 配置表的行会被 `before_server_start` 钩子加载到进程缓存：测试 fixture **开始和结束都要 DELETE** 该表，否则残留行会让后续文件的用例按错误的 corp_id/tenant 查询而 404；
- 每个用例 `reset_<x>_config_cache()`，并用 `monkeypatch.setattr(settings, "<x>_credential_key", Fernet.generate_key().decode())` 提供独立密钥。

## 参考实现

- `backend/app/services/crm_config.py`、`backend/app/routes/crm_recharge.py`（`/settings` 三个端点）
- `backend/app/tasks/scheduler.py`（`apply_crm_sync_job`）
- `backend/tests/integration/test_crm_settings_api.py`

## 用运行期配置做「只读探针」（结构核查的标准手法）

第三方接口结构变化时，**不要靠读代码猜**：页面已保存的凭据可以直接在本地只读探测上游，
这是把「上游契约」变成事实的最快路径（本次定位「回款字段缺少行业分类」即靠此）。

```python
# backend/.venv/bin/python - <<'PY'  （在 backend 目录执行）
import asyncio, psycopg2
from app.utils.crypto import decrypt_secret
from app.services.crm_client import CrmClient

conn = psycopg2.connect("postgresql://localhost/customer_platform"); conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT corp_id, phone, password_cipher, base_url FROM crm_settings "
            "WHERE enabled ORDER BY id DESC LIMIT 1")
corp, phone, cipher, base_url = cur.fetchone()

async def main():
    async with CrmClient(corp_id=corp, phone=phone,
                         password=decrypt_secret(cipher), base_url=base_url) as c:
        data = await c._request("GET", "/api/v2/custom_fields/received_payment/by_group")
        # 只打印结构：键名、类型、label/name，不打印 token、密码、客户手机号
        print(list(data.keys()))

asyncio.run(main())
```

约束：

- **只读**：只发 `GET`；不要用它触发写操作或导入，避免污染生产数据；
- **不落敏感值**：脚本里不打印 `password` / `user_token` / 客户电话等；需要留存响应就只存
  「键路径 + label/value 结构」的最小快照（脱敏后放进测试 fixture）；
- **探测结论必须转成 fixture**：见 `guides/cross-layer-thinking-guide.md`
  「第三方 JSON 解析：不要按已知键名白名单下钻」——只把结论写进文档不算完成。
