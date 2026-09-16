"""测试导入字段映射转换函数"""

from datetime import date, datetime

import pandas as pd
import pytest

from app.services.customers import (
    convert_account_type,
    convert_bool_field,
    convert_date_field,
    parse_date_to_object,
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


class TestParseDateToObject:
    """parse_date_to_object：Excel 日期单元格（datetime/Timestamp）应归一化为纯 date"""

    def test_datetime_normalized_to_date(self):
        # pd.read_excel 会把 Excel 日期型单元格解析为 datetime，需归一化为纯 date
        result = parse_date_to_object(datetime(2024, 3, 15, 8, 30))
        assert result == date(2024, 3, 15)
        assert type(result) is date

    def test_timestamp_normalized_to_date(self):
        # pandas Timestamp 是 datetime 子类，同样需归一化
        result = parse_date_to_object(pd.Timestamp("2024-03-15"))
        assert result == date(2024, 3, 15)
        assert type(result) is date

    def test_date_passthrough(self):
        result = parse_date_to_object(date(2024, 3, 15))
        assert result == date(2024, 3, 15)
        assert type(result) is date

    def test_string_parse(self):
        assert parse_date_to_object("2024-01-15") == date(2024, 1, 15)

    def test_none_and_empty(self):
        assert parse_date_to_object(None) is None
        assert parse_date_to_object("") is None
