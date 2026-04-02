"""
P6-10: 临时文件清理任务
每日清理 7 天前的临时文件
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)


async def cleanup_temp_files():
    """
    清理临时文件

    执行时间：每日 03:00
    职责：清理 uploads 目录中 7 天前的文件
    """
    logger.info("🧹 开始执行临时文件清理任务")

    try:
        upload_dir = settings.file_storage_path
        retention_days = 7

        if not os.path.exists(upload_dir):
            logger.info(f"📁 上传目录不存在：{upload_dir}，跳过清理")
            return

        # 计算 cutoff 时间
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_time.timestamp()

        # 统计结果
        deleted_count = 0
        deleted_size = 0
        skipped_count = 0

        # 遍历上传目录
        for root, dirs, files in os.walk(upload_dir):
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

            # 清理空目录
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
