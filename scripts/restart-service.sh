#!/bin/bash
# Скрипт перезапуска отдельного сервиса
# Использование: ./restart-service.sh [service_name]

if [ -z "$1" ]; then
    echo "Использование: $0 [service_name]"
    echo ""
    echo "Доступные сервисы:"
    echo "  - n8n"
    echo "  - langflow"
    echo "  - supabase-db"
    echo "  - supabase-studio"
    echo "  - ollama"
    exit 1
fi

SERVICE=$1

echo "🔄 Перезапуск сервиса: $SERVICE"

docker-compose restart $SERVICE

if [ $? -eq 0 ]; then
    echo "✓ Сервис $SERVICE перезапущен"
else
    echo "❌ Ошибка при перезапуске сервиса $SERVICE"
    exit 1
fi

