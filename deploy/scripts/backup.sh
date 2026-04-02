#!/bin/bash
# 数据库备份脚本

set -e

# 配置变量
DB_CONTAINER="customer_platform-db"
DB_NAME="customer_platform"
DB_USER="user"
BACKUP_DIR="./backups"
RETENTION_DAYS=7

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 创建备份目录
mkdir -p ${BACKUP_DIR}

# 生成备份文件名
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/db_${TIMESTAMP}.sql"

log_info "开始备份数据库..."

# 执行备份
podman exec ${DB_CONTAINER} pg_dump -U ${DB_USER} ${DB_NAME} > ${BACKUP_FILE}

if [ $? -eq 0 ]; then
    log_info "备份成功：${BACKUP_FILE}"
    
    # 压缩备份
    gzip ${BACKUP_FILE}
    log_info "压缩完成：${BACKUP_FILE}.gz"
    
    # 清理旧备份
    log_info "清理 ${RETENTION_DAYS} 天前的备份..."
    find ${BACKUP_DIR} -name "db_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
    
    # 显示备份信息
    BACKUP_SIZE=$(du -h ${BACKUP_FILE}.gz | cut -f1)
    log_info "备份大小：${BACKUP_SIZE}"
    
    # 列出所有备份
    echo ""
    log_info "当前备份列表:"
    ls -lh ${BACKUP_DIR}/db_*.sql.gz
else
    log_error "备份失败"
    exit 1
fi
