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
本脚本关注两类**会让行为分叉或查询直接 500** 的高危异常：
1. 模型里有、运行库里没有的 **表 / 列**（add_table / add_column）——
   正是会让查询直接 500 的形态；
2. **可空性漂移**（modify_nullable）——列两侧都存在但 nullable 不一致，
   同一条 INSERT 会在测试库（按 metadata 建表）与生产库（历史迁移）行为分叉。
   2026-10-23 实例：`Mapped[Any]` 的 JSON 列被推断 nullable=False，
   生产库实为 nullable=YES。
对「库里有、模型没有」（遗留）以及纯索引差异默认忽略，可加 --strict。

用法
----
    cd backend
    python scripts/check_schema_drift.py            # 查缺失表/列 + 可空性漂移（推荐门禁）
    python scripts/check_schema_drift.py --strict   # 额外报出库中多余对象

退出码：0 = 无缺失、无漂移；1 = 存在缺失或漂移（门禁失败）。
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


def _unwrap(entry):
    """解包 compare_metadata 的 diff 条目。

    `modify_*` 条目的形态是**外层 list 包裹一个 tuple**：
        [('modify_nullable', None, 'audit_logs', 'changes', {...}, True, False)]
    而 `add_table` / `remove_index` 等是裸 tuple：
        ('remove_index', Index)
    统一返回 (kind, obj_or_none, table_name, column_name, payload, extra...)。
    """
    if isinstance(entry, list) and len(entry) == 1 and isinstance(entry[0], (list, tuple)):
        return entry[0]
    return entry


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


def _collect_nullable_diffs(diff: list) -> list[str]:
    """抽取 `modify_nullable` 条目，渲染为 `table.col: 模型=X 库=Y`。

    compare_metadata 只在**列已存在于两侧**但可空性不一致时产出该条目。
    这正是 2026-10-23 漂移的形态：`Mapped[Any]`（JSON 列）被 SQLAlchemy 推断
    nullable=False，而生产库是历史迁移建的 nullable=YES → 测试库按 metadata
    建表 NOT NULL、生产库 NULL，两侧行为分叉（同一个 ORM INSERT，一侧炸一侧不炸）。
    """
    out: list[str] = []
    for entry in diff:
        inner = _unwrap(entry)
        if not isinstance(inner, (list, tuple)) or not inner:
            continue
        if inner[0] != "modify_nullable":
            continue
        # ('modify_nullable', schema, table, column, {existing_*}, model_nullable, db_nullable)
        # 实测 [5]=模型侧（existing conn 的 reflected）[6]=metadata 侧，方向以脚本输出为准校准
        table, column = inner[2], inner[3]
        model_nullable, db_nullable = inner[6], inner[5]
        out.append(f"{table}.{column}: 模型={model_nullable} 库={db_nullable}")
    return out


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
    nullable_drifts: list[str] = []

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        diff = compare_metadata(ctx, Base.metadata)

    for entry in diff:
        entry = _unwrap(entry)
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

    # 可空性漂移单独收集（compare_metadata 的 modify_nullable 条目是外层 list 包裹 tuple）
    nullable_drifts = _collect_nullable_diffs(diff)

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

    if nullable_drifts:
        print(f"\n❌ 可空性漂移（模型与运行库 nullable 不一致，共 {len(nullable_drifts)} 处）：")
        for item in nullable_drifts:
            print(f"   - {item}")
        print("   → 同一条 INSERT 会在两侧行为分叉（测试库按 metadata 建表 vs 生产库历史迁移）")
        print("   → 修法二选一：模型显式 nullable=True 对齐生产库，或写迁移 ALTER COLUMN")
    else:
        print("\n✅ 模型与运行库的可空性一致")

    if args.strict and extra_objects:
        print(f"\n⚠️  库中存在模型未声明的对象（--strict 视为失败）：{extra_objects}")
    elif extra_objects:
        print(f"\nℹ️  忽略 {len(extra_objects)} 个遗留对象/索引差异（加 --strict 可查看）")

    failed = (
        bool(missing_tables or missing_columns)
        or bool(nullable_drifts)
        or (args.strict and extra_objects)
    )
    print()
    print("❌ FAILED" if failed else "✅ PASSED")
    engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
