#!/usr/bin/env python
"""Schema drift check: 模型声明的表/列是否都存在于运行中的数据库。

用途
----
防止「改了 ORM 模型但忘了把迁移应用到运行库」这一类 bug
（2026-10-13 事故：给 Customer 加了 balance_warning_level 字段与迁移，
但运行库停在旧版本 → 所有 select(Customer) 查询 500
`column customers.balance_warning_level does not exist`）。

与 `alembic check` 的区别
------------------------
`alembic check` 会报出本仓库既有的历史噪声（遗留表 daily_usage、
api_keys 索引差异、手工备份表等），无法直接作为门禁。
本脚本**只关注一种高危异常**：模型里有、运行库里没有的 **表 / 列**
（add_table / add_column）——这正是会让查询直接 500 的形态；
对「库里有、模型没有」（遗留）以及纯索引差异默认忽略，可加 --strict。

用法
----
    cd backend
    python scripts/check_schema_drift.py            # 只查缺失的表/列（推荐门禁）
    python scripts/check_schema_drift.py --strict   # 额外报出库中多余对象

退出码：0 = 无缺失；1 = 存在缺失（门禁失败）。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 允许以 `python scripts/check_schema_drift.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from app.models import Base  # noqa: E402


def _sync_url() -> str:
    """把 async DSN 转成同步 DSN（compare_metadata 需要同步连接）。"""
    from app.config import settings

    url = os.getenv("DATABASE_URL") or settings.database_url
    return (
        url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("postgresql+psycopg://", "postgresql+psycopg2://")
        .replace("postgresql://", "postgresql+psycopg2://")
    )


def _describe(entry: tuple) -> str:
    """把 autogenerate diff 元组渲染成 `table.name` / `table` 文本。

    compare_metadata 的返回形态（实测）：
      ('add_table',    Table)                         → 2 元组
      ('add_column',   None, 'table_name', Column)    → 4 元组，表名在 [2]、列在 [3]
      ('remove_index', Index)                         → 2 元组
    因此优先取 [3] 作对象、[2] 作表名，回退到对象自身属性。
    """
    obj = entry[3] if len(entry) > 3 else (entry[1] if len(entry) > 1 else None)
    table_hint = entry[2] if len(entry) > 3 else None
    name = getattr(obj, "name", "") or ""
    tname = table_hint or getattr(getattr(obj, "table", None), "name", "") or ""
    if tname and name:
        return f"{tname}.{name}"
    return str(tname or name)


def main() -> int:
    parser = argparse.ArgumentParser(description="检测 ORM 模型与运行库的 schema 漂移")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="同时把「库中多出、模型没有」的对象视为失败（默认忽略遗留噪声）",
    )
    args = parser.parse_args()

    engine = create_engine(_sync_url())
    missing_tables: list[str] = []
    missing_columns: list[str] = []
    extra_objects: list[str] = []

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        diff = compare_metadata(ctx, Base.metadata)

    for entry in diff:
        kind = entry[0]
        obj = entry[3] if len(entry) > 3 else (entry[1] if len(entry) > 1 else None)
        if kind == "add_table":
            missing_tables.append(getattr(obj, "name", str(obj)))
        elif kind == "add_column":
            missing_columns.append(_describe(entry))
        elif kind in ("remove_table", "remove_column"):
            extra_objects.append(f"{kind}:{_describe(entry)}")
        elif kind in ("remove_index", "add_index"):
            extra_objects.append(f"{kind}:{_describe(entry)}")

    print("=" * 60)
    print("Schema Drift Check")
    print("=" * 60)
    print(f"数据库: {_sync_url().split('@')[-1]}")

    if not missing_tables and not missing_columns:
        print("✅ 模型声明的表/列全部存在于运行库")
    else:
        if missing_tables:
            print(f"\n❌ 运行库缺少表（模型已声明）：{missing_tables}")
            print("   → 极可能未执行 `alembic upgrade head`")
        if missing_columns:
            print(f"\n❌ 运行库缺少列（模型已声明）：{missing_columns}")
            print("   → 极可能未执行 `alembic upgrade head`")

    if args.strict and extra_objects:
        print(f"\n⚠️  库中存在模型未声明的对象（--strict 视为失败）：{extra_objects}")
    elif extra_objects:
        print(f"\nℹ️  忽略 {len(extra_objects)} 个遗留对象/索引差异（加 --strict 可查看）")

    failed = bool(missing_tables or missing_columns) or (args.strict and extra_objects)
    print()
    print("❌ FAILED" if failed else "✅ PASSED")
    engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
