"""
P6-10: 临时文件清理任务
每日清理 7 天前的临时文件

本任务只清理显式临时目录（<FILE_STORAGE_PATH>/temp/），业务数据
（invoices/、avatars/、<YYYY>/<MM>/）永不被清理。
历史事故见 prd.md 缺陷 B：原实现以存储根为 os.walk 根，无差别删除
超过保留期的业务凭证文件，导致 DB 状态与磁盘实体永久脱节。
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

# 业务文件与临时文件的物理隔离边界：唯一被清理的子目录。
TEMP_SUBDIR = "temp"


async def cleanup_temp_files():
    """
    清理临时文件

    执行时间：每日 03:00
    职责：仅清理 <FILE_STORAGE_PATH>/temp/ 目录中 7 天前的文件及空目录。
    业务目录（invoices/、avatars/、<YYYY>/<MM>/）永不被遍历。
    """
    logger.info("🧹 开始执行临时文件清理任务")

    try:
        storage_root = Path(settings.file_storage_path).resolve()
        temp_dir = storage_root / TEMP_SUBDIR

        # temp/ 不存在 → 无文件可清理，直接返回（不遍历存储根、不报错）
        if not temp_dir.exists():
            logger.info("📁 临时目录不存在（%s），无文件可清理", temp_dir)
            return

        # 软链接防御：temp/ 解析后的实际路径必须恰为存储根下的一级目录 temp。
        # 若 temp/ 被误配为指向存储根内部（如 invoices/、avatars/、<YYYY>/<MM>/）
        # 或外部的软链接，解析路径都不等于 storage_root/temp，一律拒绝清理，
        # 防止误删业务凭证文件（历史事故 B：DB 状态与磁盘实体脱节）。
        resolved_temp = temp_dir.resolve()
        if resolved_temp != storage_root / TEMP_SUBDIR:
            logger.error(
                "❌ 临时目录 %s 解析后（%s）不是存储根 %s 下的一级目录 temp，疑似软链接越界，拒绝清理",
                temp_dir,
                resolved_temp,
                storage_root,
            )
            return

        retention_days = 7

        # 计算 cutoff 时间
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_time.timestamp()

        # 统计结果
        deleted_count = 0
        deleted_size = 0
        skipped_count = 0

        # 仅遍历 temp_dir —— 不再以存储根为 os.walk 的根
        for root, dirs, files in os.walk(resolved_temp):
            for file in files:
                file_path = os.path.join(root, file)

                try:
                    # 获取文件修改时间
                    file_mtime = os.path.getmtime(file_path)

                    if file_mtime < cutoff_timestamp:
                        # 文件超过保留期限，删除
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        deleted_size += file_size
                        logger.debug(f"🗑️  删除文件：{file_path} ({file_size} bytes)")
                    else:
                        skipped_count += 1

                except Exception as e:
                    logger.error(f"❌ 文件处理失败 {file_path}: {str(e)}")
                    continue

            # 空目录清理：同样只作用于 temp/ 子树
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):
                        shutil.rmtree(dir_path)
                        logger.debug(f"🗑️  删除空目录：{dir_path}")
                except Exception as e:
                    logger.error(f"❌ 目录清理失败 {dir_path}: {str(e)}")

        # 转换大小为可读格式
        if deleted_size < 1024:
            size_str = f"{deleted_size} B"
        elif deleted_size < 1024 * 1024:
            size_str = f"{deleted_size / 1024:.2f} KB"
        elif deleted_size < 1024 * 1024 * 1024:
            size_str = f"{deleted_size / (1024 * 1024):.2f} MB"
        else:
            size_str = f"{deleted_size / (1024 * 1024 * 1024):.2f} GB"

        logger.info(
            f"✅ 临时文件清理完成 | "
            f"删除：{deleted_count} 个文件 | "
            f"释放空间：{size_str} | "
            f"保留：{skipped_count} 个文件"
        )

    except Exception as e:
        logger.error(f"❌ 临时文件清理任务执行失败：{str(e)}")
        raise
