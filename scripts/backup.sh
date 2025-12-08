#!/bin/bash
# Скрипт создания бэкапа

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="backup_${TIMESTAMP}"

echo "💾 Создание бэкапа..."

mkdir -p $BACKUP_DIR

tar -czf "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" volumes/

if [ $? -eq 0 ]; then
    echo "✓ Бэкап создан: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
else
    echo "❌ Ошибка при создании бэкапа"
    exit 1
fi

