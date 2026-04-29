"""测试导入字段映射转换函数"""

import pytest
from datetime import datetime

from app.services.customers import (
    convert_account_type,
    convert_bool_field,
    convert_date_field,
)


class TestConvertAccountType:
    def test_formal_account(self):
        assert convert_account_type("正式") == "正式账号"

    def test_test_account(self):
        assert convert_account_type("客户测试账号") == "客户测试账号"

    def test_internal_account(self):
        assert convert_account_type("众趣内部") == "内部账号"

    def test_unknown_value_passthrough(self):
        assert convert_account_type("其他") == "其他"

    def test_none_value(self):
        assert convert_account_type(None) is None

    def test_whitespace_stripped(self):
        assert convert_account_type(" 正式 ") == "正式账号"


class TestConvertBoolField:
    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("是", True),
            ("否", False),
            ("true", True),
            ("false", False),
            ("1", True),
            ("0", False),
            (True, True),
            (False, False),
            (None, None),
            ("yes", True),
            ("no", False),
        ],
    )
    def test_bool_conversion(self, input_val, expected):
        assert convert_bool_field(input_val) == expected

    def test_unknown_returns_none(self):
        assert convert_bool_field("unknown") is None


class TestConvertDateField:
    def test_none_value(self):
        assert convert_date_field(None) is None

    def test_na_value(self):
        assert convert_date_field("#N/A") is None

    def test_date_format_yyyy_mm_dd(self):
        assert convert_date_field("2024-01-15") == "2024-01-15"

    def test_date_format_yyyy_mm_dd_slash(self):
        assert convert_date_field("2024/01/15") == "2024-01-15"

    def test_empty_string(self):
        assert convert_date_field("") is None

    def test_datetime_object(self):
        dt = datetime(2024, 3, 15)
        assert convert_date_field(dt) == "2024-03-15"

    def test_unparseable_returns_none(self):
        assert convert_date_field("not-a-date") is None
