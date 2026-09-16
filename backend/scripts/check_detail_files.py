#!/usr/bin/env python3
"""结算单明细文件状态一致性检查与处置脚本

扫描 detail_file_status='completed' 的结算单，逐个检查磁盘文件是否存在。
对「状态 completed 但文件缺失」的记录提供检出和重置为 pending 的处置路径。

用法:
    # 默认：检测不一致记录（发现不一致时退出码=1）
    .venv/bin/python scripts/check_detail_files.py

    # 预览将重置的记录，不写库
    .venv/bin/python scripts/check_detail_files.py --reset-pending --dry-run

    # 将不一致记录重置为 pending（等待重新生成）
    .venv/bin/python scripts/check_detail_files.py --reset-pending

退出码:
    0 — 全部一致（或已处置完毕）
    1 — 存在不一致且未处置（未传 --reset-pending）
"""

import argparse
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载 .env 文件
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.billing import Invoice


def _get_sync_engine():
    """从 settings.database_url 创建同步引擎"""
    sync_url = settings.database_url
    # 异步 URL 转同步
    sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")
    sync_url = sync_url.replace("+asyncpg", "")
    return create_engine(sync_url, echo=False)


def _resolve_file_path(detail_file_path: str) -> str | None:
    """拼接存储根路径与相对路径，得到磁盘绝对路径。

    对绝对路径或包含 ``../`` 等越界路径，解析后若不在存储根之下，
    返回 None（表示无法可靠校验，需跳过并单列告警）。
    """
    storage_root = Path(settings.file_storage_path).resolve()
    resolved = (storage_root / detail_file_path).resolve()
    try:
        resolved.relative_to(storage_root)
    except ValueError:
        return None
    return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="检查结算单明细文件状态与磁盘实体一致性",
    )
    parser.add_argument(
        "--reset-pending",
        action="store_true",
        help="将不一致记录（completed 但文件缺失）重置为 pending",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不写库",
    )
    args = parser.parse_args()

    engine = _get_sync_engine()

    with Session(engine) as session:
        # 查询所有 detail_file_status='completed' 的结算单
        stmt = (
            select(Invoice.id, Invoice.invoice_no, Invoice.detail_file_path)
            .where(Invoice.detail_file_status == "completed")
            .where(Invoice.deleted_at.is_(None))
            .order_by(Invoice.id)
        )
        rows = session.execute(stmt).all()

        total_completed = len(rows)
        inconsistent = []  # (id, invoice_no, detail_file_path)
        out_of_root = []  # (id, invoice_no, detail_file_path)：越界路径，跳过校验

        for row in rows:
            inv_id, inv_no, rel_path = row
            if not rel_path:
                # completed 但路径为空，本身即为不一致
                inconsistent.append((inv_id, inv_no, "(空)"))
                continue

            abs_path = _resolve_file_path(rel_path)
            if abs_path is None:
                # 绝对路径或 ../ 越界：无法可靠校验，跳过并单列告警
                out_of_root.append((inv_id, inv_no, rel_path))
                continue
            # 用单次 getsize 取代 exists()+getsize() 两步检查：避免二者之间文件被
            # 并发删除导致的 TOCTOU（exists 通过后 getsize 抛 FileNotFoundError 中止脚本）。
            # getsize 抛 OSError（含文件已被删除、不可读）时视为「文件缺失」。
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                size = 0
            if size == 0:
                inconsistent.append((inv_id, inv_no, rel_path))

        # 输出
        print("=" * 70)
        print("结算单明细文件一致性检查" + ("（dry-run 模式）" if args.dry_run else ""))
        print("=" * 70)
        print(f"completed 状态结算单总数:   {total_completed}")
        print(
            f"一致（文件存在）:           {total_completed - len(inconsistent) - len(out_of_root)}"
        )
        print(f"不一致（文件缺失）:         {len(inconsistent)}")
        print(f"越界路径（跳过）:           {len(out_of_root)}")

        if inconsistent:
            print("\n不一致清单:")
            print(f"{'ID':<8} {'结算单号':<20} {'文件路径'}")
            print("-" * 70)
            for inv_id, inv_no, rel_path in inconsistent:
                print(f"{inv_id:<8} {inv_no:<20} {rel_path}")

        if out_of_root:
            print("\n越界路径告警（跳过校验，不参与重置）:")
            print(f"{'ID':<8} {'结算单号':<20} {'文件路径'}")
            print("-" * 70)
            for inv_id, inv_no, rel_path in out_of_root:
                print(f"{inv_id:<8} {inv_no:<20} {rel_path}")

        if args.reset_pending:
            print("\n" + "-" * 70)
            if args.dry_run:
                print(f"[dry-run] 将重置 {len(inconsistent)} 条记录为 pending，未写库。")
            else:
                # 写库：将不一致记录重置为 pending
                if inconsistent:
                    inconsistent_ids = [r[0] for r in inconsistent]
                    upd = (
                        update(Invoice)
                        .where(Invoice.id.in_(inconsistent_ids))
                        .values(detail_file_status="pending")
                    )
                    session.execute(upd)
                    session.commit()
                    print(f"已重置 {len(inconsistent_ids)} 条记录为 pending。")
                    print(f"受影响 ID: {inconsistent_ids}")
                else:
                    print("无不一致记录，无需重置。")

        # 退出码逻辑
        if inconsistent and not args.reset_pending:
            # 有不一致且未处置
            sys.exit(1)
        elif not inconsistent:
            if out_of_root:
                print("\n✅ 无不一致记录（存在越界路径告警，已跳过）。")
            else:
                print("\n✅ 全部一致，无需处置。")
            sys.exit(0)
        else:
            # 已处置（reset-pending 且非 dry-run）或 dry-run 模式下已预览
            sys.exit(0)


if __name__ == "__main__":
    main()
