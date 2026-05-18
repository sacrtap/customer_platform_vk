"""统一错误码定义

错误码格式: XXXXX (5 位数字)
- 第 1 位: 错误大类 (4=客户端错误, 5=服务器错误)
- 第 2-3 位: 错误小类 (00=通用, 01=参数, 02=格式, 03=认证, 04=权限, 05=资源不存在)
- 第 4-5 位: 具体错误序号

示例:
- 40001: 通用参数错误
- 40101: Token 缺失/未认证
- 40102: Token 无效或已过期
- 40301: 权限不足
- 40401: 资源不存在
- 50000: 服务器内部错误
"""


class ErrorCodes:
    # 成功
    SUCCESS = 0

    # 400xx - 客户端请求错误
    BAD_REQUEST = 40001  # 通用参数错误
    INVALID_FORMAT = 40002  # 格式错误 (邮箱、手机号等)
    INVALID_FILE = 40003  # 文件格式错误
    MISSING_PARAMETER = 40004  # 缺少必要参数

    # 401xx - 认证错误
    UNAUTHORIZED = 40101  # 未认证/缺少 Token
    TOKEN_INVALID = 40102  # Token 无效或已过期
    TOKEN_BLACKLISTED = 40103  # Token 已失效

    # 403xx - 权限错误
    FORBIDDEN = 40301  # 权限不足

    # 404xx - 资源不存在
    NOT_FOUND = 40401  # 通用资源不存在

    # 500xx - 服务器内部错误
    INTERNAL_ERROR = 50000  # 通用服务器错误
    SERVICE_ERROR = 50001  # 服务处理失败
