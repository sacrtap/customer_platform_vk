# Error Handling

> How errors are handled in this project.

---

## Overview

The project uses a **unified error code system** with 5-digit numeric codes. There are no custom exception classes — routes catch `ValueError` (business validation) and generic `Exception` (unexpected errors) and return structured JSON responses.

---

## Error Code System

[来源: 项目源码 — `backend/app/constants/error_codes.py`]

All error codes are defined in the `ErrorCodes` class:

```python
class ErrorCodes:
    SUCCESS = 0

    # 400xx — 客户端请求错误
    BAD_REQUEST = 40001       # 通用参数错误
    INVALID_FORMAT = 40002    # 格式错误 (邮箱、手机号等)
    INVALID_FILE = 40003      # 文件格式错误
    MISSING_PARAMETER = 40004 # 缺少必要参数

    # 401xx — 认证错误
    UNAUTHORIZED = 40101      # 未认证/缺少 Token
    TOKEN_INVALID = 40102     # Token 无效或已过期
    TOKEN_BLACKLISTED = 40103 # Token 已失效

    # 403xx — 权限错误
    FORBIDDEN = 40301         # 权限不足

    # 404xx — 资源不存在
    NOT_FOUND = 40401         # 通用资源不存在

    # 500xx — 服务器内部错误
    INTERNAL_ERROR = 50000    # 通用服务器错误
    SERVICE_ERROR = 50001     # 服务处理失败
```

**Code format**: `XXXXX` (5 digits)
- Digit 1: error class (4=client, 5=server)
- Digits 2-3: sub-category (00=general, 01=params, 02=format, 03=auth, 04=permission, 05=not found)
- Digits 4-5: specific sequence

---

## API Error Response Format

All API responses (success and error) follow the same envelope:

```json
{
  "code": 40001,
  "message": "公司 ID 和客户名称不能为空"
}
```

Success responses include `data`:

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

---

## Error Handling Patterns

### Pattern 1: Input validation in route → return 400

[来源: 项目源码 — `backend/app/routes/customers.py:344-352`]

```python
data = request.json
if not data.get("company_id") or not data.get("name"):
    return json({"code": 40001, "message": "公司 ID 和客户名称不能为空"}, status=400)

email = data.get("email")
if email:
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        return json({"code": 40002, "message": "邮箱格式不正确"}, status=400)
```

### Pattern 2: Service raises ValueError → catch in route → return 400

[来源: 项目源码 — `backend/app/routes/customers.py:371-376`]

```python
try:
    customer = await service.create_customer(data)
except ValueError as e:
    return json({"code": 40003, "message": str(e)}, status=400)
except Exception as e:
    return json({"code": 50001, "message": str(e)}, status=400)
```

### Pattern 3: Resource not found → return 404

[来源: 项目源码 — `backend/app/routes/customers.py:229-230`]

```python
if not customer:
    return json({"code": 40401, "message": "客户不存在"}, status=404)
```

### Pattern 4: Service returns (success, message) tuple

[来源: 项目源码 — `backend/app/routes/billing/invoices.py:514-522`]

```python
success, message = await invoice_service.apply_discount(
    invoice_id=invoice_id,
    discount_amount=Decimal(str(data.get("discount_amount", 0))),
    discount_reason=data.get("discount_reason", ""),
)
if not success:
    return json({"code": 40001, "message": message}, status=400)
```

---

## Forbidden Patterns

- ❌ **Do NOT create custom exception classes** — the project uses `ValueError` for business errors and generic `Exception` for unexpected errors
- ❌ **Do NOT use bare `except:`** — always catch `ValueError` separately from `Exception`
- ❌ **Do NOT return error responses without an error code** — always use `ErrorCodes` constants or numeric codes matching the 5-digit format
- ❌ **Do NOT leak internal error details in production** — the current code returns `str(e)` in some catch blocks; prefer user-friendly messages

---

## Common Mistakes

1. **Catching `Exception` and returning status=400** — generic exceptions should return 500, not 400 (see `customers.py:376` which returns status=400 for all exceptions — this is a known inconsistency)
2. **Forgetting to invalidate cache after mutations** — after create/update/delete, call `cache_service.invalidate_*()` (see `customers.py:379`)
