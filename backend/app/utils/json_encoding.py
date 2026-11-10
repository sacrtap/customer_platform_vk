"""JSON 序列化工具

ORM 列值（``Decimal`` / ``uuid.UUID`` / ``datetime`` / ``Enum``）不是 JSON 原生类型，
直接写进 JSON 列会在 flush 时抛
``TypeError: Object of type Decimal is not JSON serializable``。
审计路径上这个异常被中间件的 except 吞掉，表现为「业务成功但审计静默丢失」，
因此这里提供两条防线：

1. ``to_jsonable``：显式归一（审计 before 快照在捕获时就用）
2. ``dumps_json``：引擎级 ``json_serializer`` 兜底，覆盖所有 JSON 列的所有写入方
"""

import json
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any


def to_jsonable(value: Any) -> Any:
    """把任意值归一成 JSON 原生类型

    - ``Decimal`` → ``str``：DECIMAL(12,2) 转 str 保留精确十进制文本；转 float 会引入二进制误差
    - ``datetime`` / ``date`` / ``time`` → ISO 字符串
    - ``uuid.UUID`` → ``str``
    - ``Enum`` → 其 ``value``（递归归一）
    - 其余未知类型 → ``str``（兜底，保证不抛）
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def dumps_json(value: Any) -> str:
    """宽容 JSON 序列化：非原生值转字符串，而不是抛 ``TypeError``

    作为 ``create_engine(json_serializer=...)`` 使用，对所有 JSON 列生效。
    """
    return json.dumps(value, default=to_jsonable)
