"""错误码常量单元测试"""

from app.constants import ErrorCodes


class TestErrorCodes:
    """错误码常量测试类"""

    def test_success_code_is_zero(self):
        """成功错误码应为 0"""
        assert ErrorCodes.SUCCESS == 0

    def test_client_error_codes_range(self):
        """客户端错误码应在 40000-40999 范围内"""
        client_codes = [
            ErrorCodes.BAD_REQUEST,
            ErrorCodes.INVALID_FORMAT,
            ErrorCodes.INVALID_FILE,
            ErrorCodes.MISSING_PARAMETER,
        ]
        for code in client_codes:
            assert 40000 <= code < 41000

    def test_auth_error_codes_range(self):
        """认证错误码应在 40100-40199 范围内"""
        auth_codes = [
            ErrorCodes.UNAUTHORIZED,
            ErrorCodes.TOKEN_INVALID,
            ErrorCodes.TOKEN_BLACKLISTED,
        ]
        for code in auth_codes:
            assert 40100 <= code < 40200

    def test_forbidden_error_code(self):
        """权限错误码应为 40301"""
        assert ErrorCodes.FORBIDDEN == 40301

    def test_not_found_error_code(self):
        """资源不存在错误码应为 40401"""
        assert ErrorCodes.NOT_FOUND == 40401

    def test_server_error_codes_range(self):
        """服务器错误码应 >= 50000"""
        server_codes = [
            ErrorCodes.INTERNAL_ERROR,
            ErrorCodes.SERVICE_ERROR,
        ]
        for code in server_codes:
            assert code >= 50000

    def test_error_codes_are_unique(self):
        """所有错误码应唯一"""
        all_codes = [
            ErrorCodes.SUCCESS,
            ErrorCodes.BAD_REQUEST,
            ErrorCodes.INVALID_FORMAT,
            ErrorCodes.INVALID_FILE,
            ErrorCodes.MISSING_PARAMETER,
            ErrorCodes.UNAUTHORIZED,
            ErrorCodes.TOKEN_INVALID,
            ErrorCodes.TOKEN_BLACKLISTED,
            ErrorCodes.FORBIDDEN,
            ErrorCodes.NOT_FOUND,
            ErrorCodes.INTERNAL_ERROR,
            ErrorCodes.SERVICE_ERROR,
        ]
        assert len(all_codes) == len(set(all_codes)), "存在重复的错误码"
