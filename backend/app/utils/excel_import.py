"""Excel 批量导入的公共解析辅助"""

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def read_import_dataframe(body: bytes, first_column: str) -> "pd.DataFrame":
    """读取导入用 Excel，并丢弃模板第 2 行的中文说明行

    导入模板（各 `import-template` 端点生成）的结构为：第 1 行英文列名、
    第 2 行中文说明（以「必填：」/「可选：」开头）、第 3 行示例数据。
    说明行不是数据，必须丢弃，否则会被当作数据行产生一条虚假的行级错误。

    Args:
        body: 上传文件的字节内容
        first_column: 第 1 列的列名，用于判定说明行（如 company_id / name）

    Returns:
        说明行被丢弃后的 DataFrame；索引标签保持与真实 Excel 行号一致，
        即第 i 行数据的 Excel 行号为 `i + 2`
    """
    import pandas as pd

    df = pd.read_excel(io.BytesIO(body), engine="openpyxl")
    if _is_template_note_row(df, first_column):
        # 切片保留原始索引标签，行级错误才能定位到真实 Excel 行
        df = df.iloc[1:]
    return df


def _is_template_note_row(df: "pd.DataFrame", first_column: str) -> bool:
    """判断第 1 行是否为模板的中文说明行

    说明行首列要么精确等于「必填」/「可选」（旧逻辑与测试夹具使用的简写），
    要么以「必填：」/「可选：」开头（模板真实说明行格式）。不能只按
    「必填」/「可选」做前缀匹配：包年套餐模板首列 `name` 是自由文本，
    若用户首行数据 name 形如「可选服务包」会被误判为说明行而静默丢弃。
    """
    if df.empty or first_column not in df.columns:
        return False
    value = str(df.iloc[0].get(first_column, "")).strip()
    return value in ("必填", "可选") or value.startswith(("必填：", "可选："))
